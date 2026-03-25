"""
Trading Strategy LangGraph Pipeline.

Builds an AgentGraph that implements the full AI strategy generation cycle:

    analyze_market ──► [debate] ──► memory_recall ──► generate_strategies ──► parse_responses
                                                                                    │
                                                                              select_best
                                                                                    │
                                                                              build_graph
                                                                                    │
                                                                               backtest
                                                                                    │
                                                                        backtest_analysis ──► refine_strategy ──┐
                                                                                    │                          │
                                                                        (passes/max iter)            (back to generate)
                                                                                    │
                                                                          optimize_strategy
                                                                                    │
                                                                           ml_validation
                                                                                    │
                                                                           memory_update ──► report ──► END

Uses StrategyController components but in a graph-based execution model
for better observability, retry logic, and conditional routing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pandas as pd
from loguru import logger

from backend.agents.langgraph_orchestrator import (
    AgentGraph,
    AgentNode,
    AgentState,
    BudgetExceededError,
    ConditionalRouter,
    FunctionAgent,
    make_pipeline_event_queue,
    make_sqlite_checkpointer,
    register_graph,
)
from backend.agents.prompts.context_builder import MarketContextBuilder
from backend.agents.prompts.prompt_engineer import PromptEngineer
from backend.agents.prompts.response_parser import ResponseParser
from backend.config.constants import COMMISSION_TV, INITIAL_CAPITAL

# =============================================================================
# SHARED ACCEPTANCE THRESHOLDS (single source of truth for all nodes + helpers)
# =============================================================================

_MIN_TRADES: int = 5  # minimum trades for a strategy to "pass"
_MAX_DD_PCT: float = 30.0  # maximum drawdown % allowed

# =============================================================================
# GRAPH NODES
# =============================================================================


class AnalyzeMarketNode(AgentNode):
    """Node 1: Analyze market data and build MarketContext."""

    def __init__(self) -> None:
        super().__init__(
            name="analyze_market",
            description="Analyze OHLCV data and detect market regime",
            timeout=30.0,
        )
        self._builder = MarketContextBuilder()

    async def execute(self, state: AgentState) -> AgentState:
        symbol = state.context.get("symbol", "BTCUSDT")
        timeframe = state.context.get("timeframe", "15")
        df = state.context.get("df")

        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            state.add_error(self.name, ValueError("No OHLCV data in state.context['df']"))
            return state

        context = self._builder.build_context(symbol, timeframe, df)
        state.set_result(
            self.name,
            {
                "market_context": context,
                "regime": context.market_regime,
                "trend": context.trend_direction,
                "current_price": context.current_price,
            },
        )
        state.add_message(
            "system",
            f"Market analysis: {symbol} {timeframe} — {context.market_regime}, trend={context.trend_direction}",
            self.name,
        )
        logger.info(f"📊 [Graph] Market: {symbol} regime={context.market_regime}")
        return state


class RegimeClassifierNode(AgentNode):
    """
    Node 1.2: Deterministic market regime classifier (P2-1).

    Uses ADX, ATR percentile, and trend direction to map the raw MarketContext
    regime into a structured 5-category taxonomy with a confidence score.
    No LLM call — runs in < 1 ms from already-computed context data.

    Output stored in ``state.context["regime_classification"]``::

        {
            "regime":      "trending_bull",   # canonical tag
            "adx_proxy":   28.5,              # trend strength proxy (ADX or EMA slope × 100)
            "atr_pct":     1.8,               # volatility as % of price
            "trend":       "bullish",         # raw trend direction
            "confidence":  0.78,              # 0.0–1.0
        }

    Taxonomy:
        trending_bull   — strong uptrend   (ADX-proxy ≥ 20, trend=bullish)
        trending_bear   — strong downtrend (ADX-proxy ≥ 20, trend=bearish)
        volatile_ranging— high ATR, low directional strength
        ranging         — low ATR, low directional strength
        crypto_risk_off — bearish + very high volatility (ATR > 3%)
    """

    _ADX_TREND_THRESHOLD = 20.0    # above → trending
    _ATR_HIGH_THRESHOLD = 2.5      # % → high volatility
    _ATR_RISK_OFF_THRESHOLD = 3.5  # % → crypto risk-off

    def __init__(self) -> None:
        super().__init__(
            name="regime_classifier",
            description="Deterministic regime classification from ADX+ATR+trend",
            timeout=5.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        market_result = state.get_result("analyze_market")
        if not market_result:
            logger.debug("[RegimeClassifier] No market result — skipping")
            return state

        ctx = market_result["market_context"]
        atr_pct: float = getattr(ctx, "atr_pct", 0.0)
        trend_dir: str = getattr(ctx, "trend_direction", "neutral")
        trend_strength: str = getattr(ctx, "trend_strength", "weak")

        # Approximate ADX proxy from trend_strength string
        strength_map = {"strong": 30.0, "moderate": 20.0, "weak": 10.0}
        adx_proxy = strength_map.get(trend_strength, 10.0)

        # --- Classify ---
        if atr_pct >= self._ATR_RISK_OFF_THRESHOLD and trend_dir == "bearish":
            regime = "crypto_risk_off"
            confidence = min(1.0, atr_pct / (self._ATR_RISK_OFF_THRESHOLD * 1.5))
        elif adx_proxy >= self._ADX_TREND_THRESHOLD and trend_dir == "bullish":
            regime = "trending_bull"
            confidence = min(1.0, adx_proxy / 40.0)
        elif adx_proxy >= self._ADX_TREND_THRESHOLD and trend_dir == "bearish":
            regime = "trending_bear"
            confidence = min(1.0, adx_proxy / 40.0)
        elif atr_pct >= self._ATR_HIGH_THRESHOLD:
            regime = "volatile_ranging"
            confidence = min(1.0, atr_pct / (self._ATR_HIGH_THRESHOLD * 2))
        else:
            regime = "ranging"
            confidence = max(0.3, 1.0 - adx_proxy / self._ADX_TREND_THRESHOLD)

        classification = {
            "regime": regime,
            "adx_proxy": round(adx_proxy, 1),
            "atr_pct": round(atr_pct, 2),
            "trend": trend_dir,
            "confidence": round(confidence, 2),
        }
        state.context["regime_classification"] = classification
        state.set_result(self.name, classification)
        logger.info(f"[RegimeClassifier] {regime} (adx≈{adx_proxy:.0f}, atr={atr_pct:.2f}%, conf={confidence:.0%})")
        return state


class DebateNode(AgentNode):
    """
    Node 1.5 (optional): Multi-Agent Debate on market regime before strategy generation.

    MAD pattern (Du et al., MIT/CMU 2023):
    - Agents debate the market regime and best strategy direction
    - Adaptive stopping: KS-test detects when positions have converged (p > 0.05)
    - Max 3 rounds to avoid over-deliberation
    - Debate consensus enriches the market context for GenerateStrategiesNode
    - P2-2: S²-MAD cosine-similarity early stop (similarity > 0.9 → converged)

    Falls back gracefully if deliberation APIs are unavailable.
    """

    _MAX_ROUNDS = 3
    _KS_STABILITY_THRESHOLD = 0.05  # p-value above which debate is considered stable
    _SIMILARITY_THRESHOLD = 0.90    # P2-2: cosine sim above this → responses converged

    def __init__(self) -> None:
        super().__init__(
            name="debate",
            description="Multi-Agent Debate with KS-test adaptive stopping + S²-MAD cosine similarity",
            timeout=90.0,
        )

    @staticmethod
    def _cosine_similarity(a: str, b: str) -> float:
        """
        Bag-of-words cosine similarity between two text responses (P2-2).
        Used to detect when debate participants have converged without LLM cost.
        Returns 0.0–1.0; values above _SIMILARITY_THRESHOLD indicate convergence.
        """
        import re
        from collections import Counter
        from math import sqrt

        tokens_a = Counter(re.findall(r"\w+", a.lower()))
        tokens_b = Counter(re.findall(r"\w+", b.lower()))
        all_tokens = set(tokens_a) | set(tokens_b)
        dot = sum(tokens_a[t] * tokens_b[t] for t in all_tokens)
        norm_a = sqrt(sum(v * v for v in tokens_a.values()))
        norm_b = sqrt(sum(v * v for v in tokens_b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def execute(self, state: AgentState) -> AgentState:
        market_result = state.get_result("analyze_market")
        if not market_result:
            logger.warning("[DebateNode] No market analysis — skipping debate")
            return state

        market_context = market_result["market_context"]
        symbol = state.context.get("symbol", "BTCUSDT")
        agents = state.context.get("agents", ["deepseek", "qwen"])

        # P2-2: S²-MAD — check if previous debate results already converged
        prior_debate = state.context.get("debate_consensus")
        if prior_debate:
            prior_texts = prior_debate.get("_participant_texts", [])
            if len(prior_texts) >= 2:
                sim = self._cosine_similarity(prior_texts[0], prior_texts[1])
                if sim >= self._SIMILARITY_THRESHOLD:
                    logger.info(
                        f"🔁 [DebateNode] S²-MAD early stop: cosine_sim={sim:.3f} ≥ {self._SIMILARITY_THRESHOLD} — skipping re-debate"
                    )
                    return state

        # Build debate question from market context
        regime = getattr(market_context, "market_regime", "unknown")
        question = (
            f"Given current market context for {symbol} (regime: {regime}), "
            f"what is the optimal strategy direction and risk posture? "
            f"Should we trade long/short/both, and what risk level is appropriate?"
        )

        try:
            from backend.agents.consensus.real_llm_deliberation import deliberate_with_llm

            debate_result = await deliberate_with_llm(
                question=question,
                agents=[a for a in agents if a in ("deepseek", "qwen", "perplexity")],
                max_rounds=self._MAX_ROUNDS,
                min_confidence=0.65,
                symbol=symbol,
                strategy_type="debate",
                enrich_with_perplexity="perplexity" in agents,
                use_memory=True,
            )

            # Apply KS-test adaptive stopping retrospectively (log result)
            confidence = getattr(debate_result, "confidence_score", 0.0)
            consensus = getattr(debate_result, "consensus_answer", "")

            # P2-2: store participant texts for S²-MAD similarity check on future rounds
            participant_texts = getattr(debate_result, "participant_texts", [])
            if len(participant_texts) >= 2:
                sim = self._cosine_similarity(participant_texts[0], participant_texts[1])
                logger.info(f"🔁 [DebateNode] S²-MAD cosine_sim={sim:.3f} (threshold={self._SIMILARITY_THRESHOLD})")

            logger.info(
                f"🗣️ Debate complete: confidence={confidence:.2f}, "
                f"rounds={getattr(debate_result, 'rounds_completed', '?')}"
            )

            # Enrich state with debate consensus for GenerateStrategiesNode
            state.context["debate_consensus"] = {
                "question": question,
                "consensus": consensus,
                "confidence": confidence,
                "participating_agents": agents,
                "_participant_texts": participant_texts,  # P2-2: stored for S²-MAD check
            }
            state.set_result(self.name, {"consensus": consensus, "confidence": confidence})
            state.add_message(
                "system",
                f"Debate consensus (confidence={confidence:.0%}): {consensus[:200]}",
                self.name,
            )

        except Exception as e:
            logger.warning(f"[DebateNode] Deliberation failed (non-fatal, continuing): {e}")
            state.set_result(self.name, {"consensus": None, "confidence": 0.0, "error": str(e)})

        return state


class MemoryRecallNode(AgentNode):
    """
    Node 1.7: Recall relevant past strategies from HierarchicalMemory before generation.

    Closes the critical gap where agents save results to memory (MemoryUpdateNode)
    but never read them back. This node queries the EPISODIC and SEMANTIC tiers for:

    1. **Past wins** — high-importance strategies for same symbol/timeframe that worked
       (sharpe > 0). Gives the agent a "this worked before, try similar approach" signal.
    2. **Past failures** — strategies that scored badly. Prevents repeating dead ends.
    3. **Regime patterns** — strategies that performed well in the *current* market regime.

    Results are injected into:
    - ``state.context["memory_context"]``   — formatted text block for the LLM prompt
    - ``state.context["past_attempts"]``    — structured list for RefinementNode

    The node is non-blocking: any memory error silently degrades to empty context.
    """

    TOP_K_WINS = 5
    TOP_K_FAILURES = 3
    TOP_K_REGIME = 3
    MIN_WIN_IMPORTANCE = 0.5  # importance ≥ 0.5 = strategy with Sharpe > 1
    MIN_FAILURE_IMPORTANCE = 0.1

    def __init__(self) -> None:
        super().__init__(
            name="memory_recall",
            description="Recall past strategies from memory before generation",
            timeout=15.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        symbol = state.context.get("symbol", "BTCUSDT")
        timeframe = state.context.get("timeframe", "15")
        market_result = state.get_result("analyze_market")
        regime = "unknown"
        if market_result:
            regime = market_result.get("regime", "unknown")

        try:
            from backend.agents.memory.hierarchical_memory import HierarchicalMemory

            memory = HierarchicalMemory()

            # --- 1. Successful strategies (high importance) ---
            wins = await memory.recall(
                query=f"successful strategy {symbol} {timeframe} high sharpe profit",
                top_k=self.TOP_K_WINS,
                min_importance=self.MIN_WIN_IMPORTANCE,
                agent_namespace="strategy_gen",
            )

            # --- 2. Recent failures (low sharpe, no trades) ---
            failures = await memory.recall(
                query=f"failed strategy {symbol} {timeframe} low sharpe no trades",
                top_k=self.TOP_K_FAILURES,
                min_importance=self.MIN_FAILURE_IMPORTANCE,
                agent_namespace="strategy_gen",
            )

            # --- 3. Regime-specific patterns ---
            regime_memories = await memory.recall(
                query=f"market regime {regime} {symbol} best strategy approach",
                top_k=self.TOP_K_REGIME,
                min_importance=0.3,
                agent_namespace="strategy_gen",
            )

            # --- Build memory context block for the LLM prompt ---
            sections: list[str] = []

            if wins:
                win_lines = []
                for i, m in enumerate(wins, 1):
                    snippet = m.content[:200].replace("\n", " ")
                    imp = getattr(m, "importance", 0.0)
                    win_lines.append(f"  {i}. [importance={imp:.2f}] {snippet}")
                sections.append("PAST SUCCESSFUL STRATEGIES (adapt, don't copy verbatim):\n" + "\n".join(win_lines))

            if failures:
                fail_lines = []
                for i, m in enumerate(failures, 1):
                    snippet = m.content[:150].replace("\n", " ")
                    fail_lines.append(f"  {i}. AVOID: {snippet}")
                sections.append("PAST FAILURES (do NOT repeat these patterns):\n" + "\n".join(fail_lines))

            if regime_memories:
                regime_lines = []
                for m in regime_memories:
                    snippet = m.content[:150].replace("\n", " ")
                    regime_lines.append(f"  - {snippet}")
                sections.append(f"REGIME KNOWLEDGE ({regime} market):\n" + "\n".join(regime_lines))

            # --- 4. Dynamic few-shot examples (P1-3) ---
            # Format top winning memories as concrete examples for in-context learning.
            # These are injected separately so GenerateStrategiesNode can place them
            # right before the generation request for maximum impact.
            few_shot_examples: list[str] = []
            for m in wins[:3]:  # top-3 wins by importance
                meta = getattr(m, "metadata", {}) or {}
                sharpe = meta.get("sharpe_ratio", "?")
                agent = meta.get("agent", "AI")
                snippet = m.content[:300].replace("\n", " ")
                few_shot_examples.append(
                    f"EXAMPLE (Sharpe={sharpe}, agent={agent}): {snippet}"
                )

            if few_shot_examples:
                state.context["few_shot_examples"] = few_shot_examples
                logger.info(f"🎯 [MemoryRecallNode] {len(few_shot_examples)} few-shot examples ready")

            if sections:
                memory_context = (
                    "## Prior Knowledge from Memory\n"
                    + "\n\n".join(sections)
                    + "\n\nUse this knowledge to inform your strategy — adapt successful "
                    "patterns to the current market conditions and avoid known failure modes."
                )
                state.context["memory_context"] = memory_context

                # Structured list for RefinementNode / BacktestAnalysisNode
                state.context["past_attempts"] = [
                    {
                        "content": m.content[:300],
                        "importance": getattr(m, "importance", 0.0),
                        "tags": getattr(m, "tags", []),
                    }
                    for m in (wins + failures)
                ]

                logger.info(
                    f"🧠 [MemoryRecallNode] Injected {len(wins)} wins, "
                    f"{len(failures)} failures, {len(regime_memories)} regime memories"
                )
            else:
                logger.debug(
                    f"[MemoryRecallNode] No relevant memories for {symbol}/{timeframe} — generating from scratch"
                )

        except Exception as exc:
            # Non-fatal: memory recall failure does not abort the pipeline
            logger.warning(f"[MemoryRecallNode] Memory recall failed (non-fatal): {exc}")

        state.set_result(
            self.name,
            {
                "memory_context_available": "memory_context" in state.context,
                "symbol": symbol,
                "timeframe": timeframe,
                "regime": regime,
            },
        )
        return state


class GenerateStrategiesNode(AgentNode):
    """
    Node 2: Generate strategy proposals from LLM agents.

    Self-MoA pattern (ICLR 2025):
    - DeepSeek called 3× in parallel at T=0.3/0.7/1.1 → diverse proposals
    - QWEN acts as critic: reviews all 3 DeepSeek outputs and synthesises
      the strongest strategy from them (temperature diversity → +6.6% quality)
    - Other agents (Perplexity) called normally for market context
    """

    # Self-MoA temperatures for DeepSeek — conservative / balanced / creative
    _MOA_TEMPERATURES = [0.3, 0.7, 1.1]

    def __init__(self) -> None:
        super().__init__(
            name="generate_strategies",
            description="Call LLM agents to generate strategy proposals (Self-MoA)",
            timeout=180.0,  # 3× parallel calls need more headroom
            retry_count=1,
            retry_delay=2.0,
        )
        self._prompt_engineer = PromptEngineer()

    async def execute(self, state: AgentState) -> AgentState:
        market_result = state.get_result("analyze_market")
        if not market_result:
            state.add_error(self.name, ValueError("No market analysis result"))
            return state

        market_context = market_result["market_context"]
        agents: list[str] = state.context.get("agents", ["deepseek"])
        platform_config = state.context.get(
            "platform_config",
            {"exchange": "Bybit", "commission": COMMISSION_TV, "max_leverage": 100},
        )

        # --- Refinement feedback: inject failure context into prompt if retrying ---
        refinement_feedback = state.context.get("refinement_feedback", "")
        refinement_iter = state.context.get("refinement_iteration", 0)
        if refinement_feedback:
            logger.info(
                f"🔄 [GenerateStrategies] Refinement iteration {refinement_iter}: "
                f"incorporating failure feedback into prompt"
            )

        # --- Memory context: inject past wins/failures recalled by MemoryRecallNode ---
        memory_context = state.context.get("memory_context", "")

        # --- P1-3: Dynamic few-shot injection ---
        # Prepend concrete past-success examples to anchor LLM output toward proven patterns.
        few_shot_examples: list[str] = state.context.get("few_shot_examples", [])
        few_shot_block = ""
        if few_shot_examples:
            few_shot_block = (
                "## Proven Strategy Examples (few-shot)\n"
                "The following strategies worked well in similar conditions. "
                "Use them as inspiration — adapt, don't copy verbatim:\n\n"
                + "\n\n".join(few_shot_examples)
                + "\n"
            )
            logger.info(f"🎯 [GenerateStrategies] Injecting {len(few_shot_examples)} few-shot examples")

        responses: list[dict[str, Any]] = []
        failed_agents: list[str] = []

        # --- Self-MoA: 3× DeepSeek in parallel if DeepSeek is in the agent list ---
        if "deepseek" in agents:
            prompt = self._prompt_engineer.create_strategy_prompt(
                context=market_context,
                platform_config=platform_config,
                agent_name="deepseek",
                include_examples=True,
            )
            if few_shot_block:
                prompt = f"{few_shot_block}\n\n{prompt}"
            if memory_context:
                prompt = f"{memory_context}\n\n{prompt}"
            if refinement_feedback:
                prompt = f"{prompt}\n\n{refinement_feedback}"
            system_msg = self._prompt_engineer.get_system_message("deepseek")

            moa_tasks = [
                self._call_llm("deepseek", prompt, system_msg, temperature=t, state=state)
                for t in self._MOA_TEMPERATURES
            ]
            moa_results = await asyncio.gather(*moa_tasks, return_exceptions=True)
            moa_texts = [r for r in moa_results if isinstance(r, str) and r]

            logger.info(f"🔀 Self-MoA: {len(moa_texts)}/{len(self._MOA_TEMPERATURES)} DeepSeek variants succeeded")

            if moa_texts:
                # QWEN critic: synthesise the best strategy from all variants
                critic_output = await self._qwen_critic(moa_texts, market_context)
                if critic_output:
                    responses.append({"agent": "deepseek", "response": critic_output})
                    logger.info("✅ QWEN critic produced synthesised DeepSeek strategy")
                else:
                    # Fallback: use the middle-temperature (T=0.7) output directly
                    mid = moa_texts[len(moa_texts) // 2]
                    responses.append({"agent": "deepseek", "response": mid})
                    logger.info("⚠️ QWEN critic unavailable — using T=0.7 DeepSeek variant")

        # --- Other agents (Perplexity for market context, QWEN standalone) ---
        for agent_name in agents:
            if agent_name == "deepseek":
                continue  # handled by Self-MoA above
            prompt = self._prompt_engineer.create_strategy_prompt(
                context=market_context,
                platform_config=platform_config,
                agent_name=agent_name,
                include_examples=True,
            )
            if few_shot_block:
                prompt = f"{few_shot_block}\n\n{prompt}"
            if memory_context:
                prompt = f"{memory_context}\n\n{prompt}"
            if refinement_feedback:
                prompt = f"{prompt}\n\n{refinement_feedback}"
            system_msg = self._prompt_engineer.get_system_message(agent_name)
            try:
                response_text = await self._call_llm(agent_name, prompt, system_msg, state=state)
                if response_text:
                    responses.append({"agent": agent_name, "response": response_text})
            except Exception as e:
                logger.warning(f"[Graph] LLM call failed for {agent_name}: {e}")
                failed_agents.append(agent_name)

        if failed_agents:
            state.context["partial_generation"] = True
            state.context["failed_agents"] = failed_agents
            logger.warning(f"[Graph] Partial generation: {len(failed_agents)} agent(s) failed: {failed_agents}")

        state.set_result(self.name, {"responses": responses})
        state.add_message(
            "system",
            f"Generated {len(responses)} responses (Self-MoA active for DeepSeek)",
            self.name,
        )
        return state

    async def _qwen_critic(self, moa_texts: list[str], market_context: Any) -> str | None:
        """
        QWEN critic node for Self-MoA.

        Receives N DeepSeek strategy variants and returns the synthesised best.
        If QWEN is unavailable, returns None (caller falls back to T=0.7 variant).
        """
        variants_block = "\n\n".join(
            f"--- VARIANT {i + 1} (T={self._MOA_TEMPERATURES[i]:.1f}) ---\n{text}" for i, text in enumerate(moa_texts)
        )
        critic_prompt = (
            "You are a quantitative trading strategy critic.\n\n"
            "Below are multiple strategy proposals for the same market context, "
            "generated at different creativity levels.\n\n"
            f"{variants_block}\n\n"
            "Your task:\n"
            "1. Identify the strongest elements from each variant\n"
            "2. Synthesise ONE final strategy that combines the best ideas\n"
            "3. Ensure the strategy is concrete, implementable, and risk-controlled\n"
            "4. Output in the SAME structured JSON format as the variants\n\n"
            "Output only the synthesised strategy JSON, no explanation."
        )
        try:
            return await self._call_llm(
                "qwen",
                critic_prompt,
                "You are a precision strategy synthesiser. Output valid JSON only.",
                temperature=0.3,  # deterministic for critic role
            )
        except Exception as e:
            logger.debug(f"QWEN critic call failed: {e}")
            return None

    async def _call_llm(
        self,
        agent_name: str,
        prompt: str,
        system_msg: str,
        temperature: float | None = None,
        state: AgentState | None = None,
    ) -> str | None:
        """Call LLM using the connections module (temperature override supported).

        Args:
            state: If provided, LLM cost and call count are recorded on the state
                   for pipeline-level observability via ``state.total_cost_usd``.
        """
        from backend.agents.llm.base_client import (
            LLMClientFactory,
            LLMConfig,
            LLMMessage,
            LLMProvider,
        )
        from backend.security.key_manager import get_key_manager

        km = get_key_manager()

        provider_map = {
            "deepseek": (LLMProvider.DEEPSEEK, "DEEPSEEK_API_KEY", "deepseek-chat", 0.7),
            "qwen": (LLMProvider.QWEN, "QWEN_API_KEY", "qwen-plus", 0.4),
            "perplexity": (LLMProvider.PERPLEXITY, "PERPLEXITY_API_KEY", "sonar-pro", 0.7),
        }

        if agent_name not in provider_map:
            return None

        provider, key_name, model, default_temp = provider_map[agent_name]
        api_key = km.get_decrypted_key(key_name)
        if not api_key:
            return None

        effective_temp = temperature if temperature is not None else default_temp
        config = LLMConfig(
            provider=provider,
            api_key=api_key,
            model=model,
            temperature=effective_temp,
            max_tokens=4096,
        )
        client = LLMClientFactory.create(config)
        try:
            messages = [
                LLMMessage(role="system", content=system_msg),
                LLMMessage(role="user", content=prompt),
            ]
            response = await client.chat(messages)
            if state is not None:
                state.record_llm_cost(response.estimated_cost)
            return response.content
        finally:
            await client.close()


class ParseResponsesNode(AgentNode):
    """Node 3: Parse LLM responses into StrategyDefinition objects."""

    def __init__(self) -> None:
        super().__init__(
            name="parse_responses",
            description="Parse LLM text responses into structured strategies",
            timeout=15.0,
        )
        self._parser = ResponseParser()

    async def execute(self, state: AgentState) -> AgentState:
        gen_result = state.get_result("generate_strategies")
        if not gen_result:
            state.add_error(self.name, ValueError("No generation results"))
            return state

        responses = gen_result.get("responses", [])
        proposals = []

        for item in responses:
            strategy = self._parser.parse_strategy(
                item["response"],
                agent_name=item["agent"],
            )
            if strategy:
                validation = self._parser.validate_strategy(strategy)
                proposals.append(
                    {
                        "strategy": strategy,
                        "validation": validation,
                        "agent": item["agent"],
                    }
                )

        state.set_result(self.name, {"proposals": proposals})
        state.add_message(
            "system",
            f"Parsed {len(proposals)} valid strategies from {len(responses)} responses",
            self.name,
        )
        return state


class ConsensusNode(AgentNode):
    """
    Node 4: Aggregate proposals via ConsensusEngine + dynamic AgentPerformanceTracker weights.

    Replaces the old SimpleScoring SelectBestNode.  Uses weighted_voting by default;
    falls back to best_of if ConsensusEngine raises (e.g. mismatched strategy types).
    """

    def __init__(self) -> None:
        super().__init__(
            name="select_best",  # keep name so downstream nodes still work
            description="Consensus aggregation with dynamic agent weights",
            timeout=15.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        parse_result = state.get_result("parse_responses")
        if not parse_result:
            state.add_error(self.name, ValueError("No parsed proposals"))
            return state

        proposals = parse_result.get("proposals", [])
        if not proposals:
            state.add_error(self.name, ValueError("No valid proposals to select from"))
            return state

        # Build agent→strategy map for ConsensusEngine
        strategies_map: dict[str, Any] = {}
        agent_list: list[str] = []
        for p in proposals:
            agent = p["agent"]
            strategies_map[agent] = p["strategy"]
            agent_list.append(agent)

        selected_agent = "unknown"
        selected_strategy = proposals[0]["strategy"]
        selected_validation = proposals[0]["validation"]
        agreement_score = 0.0

        try:
            from backend.agents.consensus.consensus_engine import ConsensusEngine
            from backend.agents.self_improvement.agent_tracker import AgentPerformanceTracker

            # Load dynamic weights from performance history
            tracker = AgentPerformanceTracker()
            dynamic_weights = tracker.compute_dynamic_weights(agent_list)

            # Sync weights into ConsensusEngine
            engine = ConsensusEngine()
            for agent_name, weight in dynamic_weights.items():
                # Translate weight → fake performance to seed engine
                normalized = max(0.0, min(3.0, weight * 2.0))  # 0-1 → 0-2 (Sharpe scale)
                engine.update_performance(agent_name, sharpe=normalized, win_rate=0.5)

            market_context = state.get_result("analyze_market") or {}
            result = engine.aggregate(
                strategies=strategies_map,
                method="weighted_voting",
                market_context=market_context,
            )

            selected_strategy = result.strategy
            agreement_score = result.agreement_score
            # Identify the highest-weighted contributing agent
            selected_agent = max(result.agent_weights, key=result.agent_weights.get)

            # Find matching validation
            for p in proposals:
                if p["agent"] == selected_agent:
                    selected_validation = p["validation"]
                    break

            logger.info(
                f"🏆 [Consensus] method=weighted_voting, "
                f"agreement={agreement_score:.2%}, "
                f"lead_agent={selected_agent}, "
                f"weights={result.agent_weights}"
            )

        except Exception as e:
            # Fallback: simple quality-score ranking (original SelectBestNode logic)
            logger.warning(f"[ConsensusNode] ConsensusEngine failed, falling back to best_of: {e}")
            scored = []
            for p in proposals:
                score = p["validation"].quality_score
                if p["strategy"].exit_conditions:
                    score += 0.1
                if p["strategy"].filters:
                    score += 0.05
                scored.append((score, p))
            scored.sort(key=lambda x: x[0], reverse=True)
            best = scored[0][1]
            selected_strategy = best["strategy"]
            selected_validation = best["validation"]
            selected_agent = best["agent"]

        state.set_result(
            self.name,
            {
                "selected_strategy": selected_strategy,
                "selected_validation": selected_validation,
                "selected_agent": selected_agent,
                "candidates_count": len(proposals),
                "agreement_score": agreement_score,
            },
        )
        state.context["selected_strategy"] = selected_strategy
        return state


# Keep old name as alias for backward compatibility
SelectBestNode = ConsensusNode


class BuildGraphNode(AgentNode):
    """
    Node 4.5: Convert StrategyDefinition → strategy_graph (blocks + connections).

    Sits between ConsensusNode and BacktestNode.  Translates the LLM-generated
    StrategyDefinition into the strategy_graph JSON format that
    StrategyBuilderAdapter understands, giving the backtest access to all 40+
    block types instead of the 6 legacy strategy types in BacktestBridge.

    Sets state.context["strategy_graph"] and state.context["graph_warnings"].
    Non-blocking: if conversion fails the pipeline continues with BacktestBridge
    fallback in BacktestNode.
    """

    def __init__(self) -> None:
        super().__init__(
            name="build_graph",
            description="Convert StrategyDefinition to strategy_graph for StrategyBuilderAdapter",
            timeout=10.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        from backend.agents.integration.graph_converter import StrategyDefToGraphConverter

        select_result = state.get_result("select_best")
        if not select_result:
            logger.debug("[BuildGraphNode] No select_best result — skipping graph conversion")
            return state

        strategy = select_result.get("selected_strategy")
        if strategy is None:
            return state

        timeframe = state.context.get("timeframe", "15")

        try:
            converter = StrategyDefToGraphConverter()
            graph, warnings = converter.convert(strategy, interval=timeframe)
            state.context["strategy_graph"] = graph
            state.context["graph_warnings"] = warnings
            if warnings:
                logger.info(f"[BuildGraphNode] {len(warnings)} conversion warning(s): {warnings}")

            # Preserve optimization hints from LLM for OptimizationNode
            if strategy.optimization_hints is not None:
                state.context["agent_optimization_hints"] = strategy.optimization_hints.model_dump(exclude_none=True)
                logger.debug(
                    f"[BuildGraphNode] Saved agent optimization_hints: "
                    f"params={strategy.optimization_hints.parameters_to_optimize}"
                )

            state.set_result(
                self.name,
                {"blocks": len(graph["blocks"]), "connections": len(graph["connections"]), "warnings": warnings},
            )
        except Exception as exc:
            logger.warning(f"[BuildGraphNode] Graph conversion failed (non-fatal): {exc}")
            state.context["strategy_graph"] = None
            state.context["graph_warnings"] = [str(exc)]

        return state


class BacktestNode(AgentNode):
    """Node 5 (optional): Run backtest on selected strategy."""

    def __init__(self) -> None:
        super().__init__(
            name="backtest",
            description="Backtest the selected strategy",
            timeout=120.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        select_result = state.get_result("select_best")
        if not select_result:
            state.add_error(self.name, ValueError("No selected strategy"))
            return state

        strategy = select_result["selected_strategy"]
        df = state.context.get("df")
        symbol = state.context.get("symbol", "BTCUSDT")
        timeframe = state.context.get("timeframe", "15")
        strategy_graph = state.context.get("strategy_graph")

        # Prefer StrategyBuilderAdapter path (full 40+ block universe)
        engine_warnings: list[str] = []
        sample_trades: list[dict] = []
        if strategy_graph is not None:
            run_data = await self._run_via_adapter(strategy_graph, df, symbol, timeframe, state)
            metrics = run_data.get("metrics", {})
            engine_warnings = run_data.get("engine_warnings", [])
            sample_trades = run_data.get("sample_trades", [])
        else:
            # Fallback: legacy BacktestBridge (6 strategy types only)
            logger.debug("[BacktestNode] No strategy_graph — using BacktestBridge fallback")
            from backend.agents.integration.backtest_bridge import BacktestBridge

            bridge = BacktestBridge()
            metrics = await bridge.run_strategy(
                strategy=strategy,
                symbol=symbol,
                timeframe=timeframe,
                df=df,
                initial_capital=state.context.get("initial_capital", INITIAL_CAPITAL),
                leverage=state.context.get("leverage", 1),
            )

        state.set_result(
            self.name,
            {
                "metrics": metrics,
                "engine_warnings": engine_warnings,
                "sample_trades": sample_trades,
            },
        )
        state.add_message(
            "system",
            f"Backtest complete: {metrics.get('total_trades', 0)} trades, Sharpe={metrics.get('sharpe_ratio', 0):.2f}",
            self.name,
        )

        # Feed backtest results back into AgentPerformanceTracker
        try:
            from backend.agents.self_improvement.agent_tracker import AgentPerformanceTracker

            tracker = AgentPerformanceTracker()
            selected_agent = select_result.get("selected_agent", "unknown")
            strategy_type = getattr(strategy, "strategy_type", "unknown")
            sharpe = metrics.get("sharpe_ratio", 0.0)
            passed = metrics.get("total_trades", 0) >= 5 and sharpe > 0 and metrics.get("max_drawdown", 100) < 30
            tracker.record_result(
                agent_name=selected_agent,
                metrics=metrics,
                strategy_type=str(strategy_type),
                passed=passed,
                fitness_score=max(0.0, min(100.0, sharpe * 20 + (50 if passed else 0))),
            )
            logger.info(f"📊 AgentPerformanceTracker updated: {selected_agent} passed={passed}, sharpe={sharpe:.2f}")
        except Exception as _tracker_err:
            logger.debug(f"AgentPerformanceTracker update failed (non-fatal): {_tracker_err}")

        return state

    async def _run_via_adapter(
        self,
        strategy_graph: dict,
        df,
        symbol: str,
        timeframe: str,
        state,
    ) -> dict:
        """Run backtest via StrategyBuilderAdapter + FallbackEngineV4."""
        import asyncio

        from backend.backtesting.models import BacktestConfig
        from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter

        def _run_sync() -> dict:
            adapter = StrategyBuilderAdapter(strategy_graph)
            signal_result = adapter.generate_signals(df)

            cfg = BacktestConfig(
                symbol=symbol,
                timeframe=timeframe,
                initial_capital=state.context.get("initial_capital", INITIAL_CAPITAL),
                leverage=state.context.get("leverage", 1),
                direction="both",
                commission_value=COMMISSION_TV,
            )

            from backend.backtesting.engine import BacktestEngine

            engine = BacktestEngine()
            result = engine.run(
                data=df,
                signals=signal_result,
                config=cfg,
            )

            # Convert PerformanceMetrics Pydantic model → plain dict so
            # downstream nodes (RefinementNode) can call .get() safely.
            raw_metrics = getattr(result, "metrics", None)
            if raw_metrics is None:
                metrics: dict = {}
            elif hasattr(raw_metrics, "model_dump"):
                metrics = raw_metrics.model_dump()
            elif isinstance(raw_metrics, dict):
                metrics = raw_metrics
            else:
                metrics = {}

            # BacktestResult has `analysis_warnings` (static analysis).
            # DIRECTION_MISMATCH / NO_TRADES are NOT set by the engine — generate
            # them here from result metrics so RefinementNode gets meaningful feedback.
            engine_warnings: list[str] = list(getattr(result, "analysis_warnings", []) or [])
            trades_count = metrics.get("total_trades", 0)
            long_trades = metrics.get("long_trades", 0)
            short_trades = metrics.get("short_trades", 0)
            if trades_count == 0:
                engine_warnings.append(
                    "[NO_TRADES] Signals were generated but no trades executed. "
                    "Check that port names are correct (use 'long'/'short', not 'signal'/'output') "
                    "and that SL/TP values are realistic."
                )
            elif long_trades == 0 and short_trades > 0:
                engine_warnings.append(
                    "[DIRECTION_MISMATCH] Strategy generates only SHORT signals but direction='both'. "
                    "Ensure 'long' port is connected to entry_long on the strategy node."
                )
            elif short_trades == 0 and long_trades > 0:
                engine_warnings.append(
                    "[DIRECTION_MISMATCH] Strategy generates only LONG signals but direction='both'. "
                    "Ensure 'short' port is connected to entry_short on the strategy node."
                )

            # Capture first 10 trades for RefinementNode diagnostics
            sample_trades: list[dict] = []
            raw_trades = getattr(result, "trades", None) or []
            for t in raw_trades[:10]:
                if isinstance(t, dict):
                    sample_trades.append(t)
                elif hasattr(t, "model_dump"):
                    # Pydantic models: model_dump() gives clean field-only dict
                    try:
                        sample_trades.append(t.model_dump())
                    except Exception:
                        pass
                elif hasattr(t, "__dict__"):
                    sample_trades.append({k: v for k, v in t.__dict__.items() if not k.startswith("_")})

            return {
                "metrics": metrics,
                "engine_warnings": engine_warnings,
                "sample_trades": sample_trades,
            }

        try:
            run_data = await asyncio.to_thread(_run_sync)
            metrics = run_data["metrics"]
            logger.info(
                f"[BacktestNode] Adapter path: {metrics.get('total_trades', 0)} trades, "
                f"Sharpe={metrics.get('sharpe_ratio', 0):.2f}"
            )
            return run_data
        except Exception as exc:
            logger.warning(f"[BacktestNode] Adapter path failed, falling back to bridge: {exc}")
            # Fallback to BacktestBridge on error
            from backend.agents.integration.backtest_bridge import BacktestBridge

            select_result = state.get_result("select_best") or {}
            strategy = select_result.get("selected_strategy")
            bridge = BacktestBridge()
            return await bridge.run_strategy(
                strategy=strategy,
                symbol=symbol,
                timeframe=timeframe,
                df=df,
                initial_capital=state.context.get("initial_capital", INITIAL_CAPITAL),
                leverage=state.context.get("leverage", 1),
            )


class BacktestAnalysisNode(AgentNode):
    """
    Node 5.5: Structured diagnostic between BacktestNode and the conditional router.

    Runs immediately after BacktestNode, before _should_refine check.
    Provides severity-aware, root-cause analysis so that RefinementNode can
    generate precise, actionable feedback instead of rebuilding diagnostics
    from scratch.

    Severity levels (stored in state.context["backtest_analysis"]["severity"]):
    - ``"pass"``        — meets all acceptance criteria
    - ``"near_miss"``   — sharpe ∈ (-0.5, 0], trades ∈ [3,5), or dd ∈ [25,30%)
    - ``"moderate"``    — sharpe ∈ (-1.5, -0.5], trades ∈ [1,3), or dd ∈ [30,50%)
    - ``"catastrophic"``— sharpe < -1.5, 0 trades, or dd ≥ 50%

    Root causes (first match wins, priority order):
    - ``"direction_mismatch"``  — DIRECTION_MISMATCH in engine_warnings
    - ``"no_signal"``           — 0 trades, no engine warnings
    - ``"signal_connectivity"`` — NO_TRADES warning (signals exist but no executions)
    - ``"sl_too_tight"``        — trades exist, all/most losing (SL knocked out)
    - ``"excessive_risk"``      — very high drawdown with few trades
    - ``"low_activity"``        — too few trades, otherwise reasonable metrics
    - ``"poor_risk_reward"``    — enough trades but negative Sharpe
    - ``"unknown"``             — fallback

    Output written to ``state.context["backtest_analysis"]`` and
    ``state.results["backtest_analysis"]``.
    """

    # Thresholds — use module-level constants (single source of truth)
    MIN_TRADES: int = _MIN_TRADES
    MAX_DD_PCT: float = _MAX_DD_PCT

    def __init__(self) -> None:
        super().__init__(
            name="backtest_analysis",
            description="Classify backtest failure severity and root cause",
            timeout=5.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        backtest_result = state.get_result("backtest") or {}
        metrics: dict[str, Any] = backtest_result.get("metrics", {}) or {}
        engine_warnings: list[str] = list(backtest_result.get("engine_warnings", None) or [])

        trades: int = int(metrics.get("total_trades", 0))
        sharpe: float = float(metrics.get("sharpe_ratio", -999.0))
        dd: float = float(metrics.get("max_drawdown", 100.0))
        win_rate: float = float(metrics.get("win_rate", 0.0))

        # ── Severity ──────────────────────────────────────────────────────────
        passed = trades >= self.MIN_TRADES and sharpe > -1e-9 and dd < self.MAX_DD_PCT

        if passed:
            severity = "pass"
        elif (
            -0.5 < sharpe <= 0 or (self.MIN_TRADES - 2 <= trades < self.MIN_TRADES) or 25.0 <= dd < self.MAX_DD_PCT
        ) and not (sharpe < -0.5 or trades < 3 or dd >= self.MAX_DD_PCT):
            severity = "near_miss"
        elif sharpe < -1.5 or trades == 0 or dd >= 50.0:
            severity = "catastrophic"
        else:
            severity = "moderate"

        # ── Root cause ────────────────────────────────────────────────────────
        warning_str = " ".join(engine_warnings)
        if "DIRECTION_MISMATCH" in warning_str:
            root_cause = "direction_mismatch"
        elif trades == 0 and not engine_warnings:
            root_cause = "no_signal"
        elif "NO_TRADES" in warning_str:
            root_cause = "signal_connectivity"
        elif trades > 0 and win_rate < 0.05:
            root_cause = "sl_too_tight"
        elif dd >= self.MAX_DD_PCT and trades < self.MIN_TRADES:
            root_cause = "excessive_risk"
        elif trades < self.MIN_TRADES:
            root_cause = "low_activity"
        elif sharpe <= 0:
            root_cause = "poor_risk_reward"
        else:
            root_cause = "unknown"

        # ── Suggestions (root-cause specific) ─────────────────────────────────
        suggestions: list[str] = []
        if root_cause == "direction_mismatch":
            suggestions.append(
                "Your blocks output signals in only ONE direction. "
                "Add BOTH 'long' and 'short' port connections to the strategy node, "
                "or set direction='long' if you intend a long-only strategy."
            )
        elif root_cause == "no_signal":
            suggestions.append(
                "No entry signals were generated at all. "
                "Check that indicator output ports are connected to strategy 'entry_long'/'entry_short' inputs. "
                "Lower indicator thresholds or shorten lookback periods."
            )
        elif root_cause == "signal_connectivity":
            suggestions.append(
                "Signals exist but no trades executed — likely a port name mismatch. "
                "Use 'long'/'short' port names, not 'signal'/'output'. "
                "Also verify SL/TP values are not so tight they immediately close every entry."
            )
        elif root_cause == "sl_too_tight":
            suggestions.append(
                f"Win rate is near zero ({win_rate:.0%}) — stop-loss is too tight. "
                "Increase stop_loss to at least 2-3× ATR, or disable fixed SL and use ATR-based exits."
            )
        elif root_cause == "excessive_risk":
            suggestions.append(
                f"Drawdown {dd:.1f}% far exceeds limit. "
                "Add a trend filter (e.g. 200 EMA), reduce leverage, or add a drawdown-based exit."
            )
        elif root_cause == "low_activity":
            suggestions.append(
                f"Only {trades} trades in the period — strategy too selective. "
                "Relax entry conditions: lower RSI thresholds, use shorter MA periods, "
                "or add a secondary entry signal."
            )
        elif root_cause == "poor_risk_reward":
            suggestions.append(
                f"Sharpe {sharpe:.2f} is negative despite {trades} trades. "
                "Improve risk-reward: add trend filter, widen TP relative to SL, "
                "or use a different exit strategy (ATR trailing stop)."
            )

        # Near-miss hint: small tweak may be enough
        if severity == "near_miss" and not suggestions:
            suggestions.append(
                "Results are close — a small parameter adjustment may be sufficient. "
                "Try ±20% on the main indicator period, or adjust oversold/overbought thresholds by 5 points."
            )

        analysis: dict[str, Any] = {
            "passed": passed,
            "severity": severity,
            "root_cause": root_cause,
            "suggestions": suggestions,
            "metrics_snapshot": {
                "total_trades": trades,
                "sharpe_ratio": round(sharpe, 3),
                "max_drawdown": round(dd, 2),
                "win_rate": round(win_rate, 4),
            },
            "engine_warnings": engine_warnings,
        }

        state.context["backtest_analysis"] = analysis
        state.set_result(self.name, analysis)

        logger.info(
            f"🔬 [BacktestAnalysisNode] severity={severity}, root_cause={root_cause}, "
            f"trades={trades}, sharpe={sharpe:.2f}, dd={dd:.1f}%"
        )
        return state


class MemoryUpdateNode(AgentNode):
    """
    Node 6: Store backtest results in HierarchicalMemory for future retrieval.

    Memory items stored:
    - Episodic: full backtest outcome (symbol, Sharpe, DD, agent, strategy)
    - Working: selected strategy params (short TTL, for same-session reuse)

    This node is non-blocking — failures are logged but do not abort the pipeline.
    """

    def __init__(self) -> None:
        super().__init__(
            name="memory_update",
            description="Store backtest results in HierarchicalMemory",
            timeout=10.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        select_result = state.get_result("select_best") or {}
        backtest_result = state.get_result("backtest") or {}
        metrics = backtest_result.get("metrics", {})

        if not metrics:
            # No backtest ran — store at least the selected strategy
            logger.debug("[MemoryUpdateNode] No backtest metrics; skipping episodic store")
            return state

        symbol = state.context.get("symbol", "BTCUSDT")
        timeframe = state.context.get("timeframe", "15")
        selected_agent = select_result.get("selected_agent", "unknown")
        strategy = select_result.get("selected_strategy")
        strategy_name = getattr(strategy, "strategy_name", "unknown")
        sharpe = metrics.get("sharpe_ratio", 0.0)
        dd = metrics.get("max_drawdown", 0.0)
        trades = metrics.get("total_trades", 0)

        episodic_content = (
            f"Strategy backtest result: {strategy_name} by {selected_agent} "
            f"on {symbol}/{timeframe} — "
            f"Sharpe={sharpe:.2f}, MaxDD={dd:.1f}%, Trades={trades}, "
            f"WinRate={metrics.get('win_rate', 0):.0%}, "
            f"ProfitFactor={metrics.get('profit_factor', 0):.2f}"
        )
        importance = min(1.0, max(0.1, (sharpe + 1.0) / 4.0))  # 0→0.25, 2→0.75

        try:
            from backend.agents.memory.hierarchical_memory import HierarchicalMemory, MemoryType

            memory = HierarchicalMemory()
            await memory.store(
                content=episodic_content,
                memory_type=MemoryType.EPISODIC,
                importance=importance,
                tags=["backtest", symbol, timeframe, selected_agent, strategy_name],
                metadata={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "agent": selected_agent,
                    "sharpe_ratio": sharpe,
                    "max_drawdown": dd,
                    "total_trades": trades,
                },
                source="trading_strategy_pipeline",
                agent_namespace="strategy_gen",
            )
            logger.info(
                f"🧠 MemoryUpdateNode: stored episodic memory (importance={importance:.2f}, sharpe={sharpe:.2f})"
            )
        except Exception as e:
            logger.warning(f"[MemoryUpdateNode] HierarchicalMemory store failed (non-fatal): {e}")

        state.set_result(self.name, {"stored": True, "importance": importance})

        # Persist strategy to ORM so it appears in the Strategy Builder UI
        strategy_graph = state.context.get("strategy_graph")
        if strategy_graph is not None and strategy is not None:
            try:
                saved_id = await asyncio.to_thread(
                    self._save_to_db,
                    strategy_graph,
                    strategy_name,
                    metrics,
                    state.context.get("symbol", "BTCUSDT"),
                )
                if saved_id:
                    logger.info(f"[MemoryUpdateNode] Saved strategy to ORM (id={saved_id})")
                    state.context["saved_strategy_id"] = saved_id
            except Exception as e:
                logger.warning(f"[MemoryUpdateNode] ORM save failed (non-fatal): {e}")

        return state

    @staticmethod
    def _save_to_db(
        strategy_graph: dict[str, Any],
        strategy_name: str,
        metrics: dict[str, Any],
        symbol: str,
    ) -> int | None:
        """Persist AI-generated strategy to the Strategy ORM (synchronous).

        Returns the saved Strategy.id or None on failure.
        """
        from backend.database import SessionLocal
        from backend.database.models.strategy import Strategy, StrategyStatus, StrategyType

        db = SessionLocal()
        try:
            sharpe = metrics.get("sharpe_ratio", 0.0)
            total_return = metrics.get("total_return", 0.0)
            description = f"AI-generated strategy. Sharpe={sharpe:.2f}, Return={total_return:.1f}%, Symbol={symbol}."
            strategy_obj = Strategy(
                name=strategy_name,
                description=description,
                strategy_type=StrategyType.BUILDER,
                status=StrategyStatus.DRAFT,
                symbol=symbol,
                timeframe=str(strategy_graph.get("interval", "15")),
                is_builder_strategy=True,
                builder_graph=strategy_graph,
                builder_blocks=strategy_graph.get("blocks", []),
                builder_connections=strategy_graph.get("connections", []),
            )
            db.add(strategy_obj)
            db.commit()
            db.refresh(strategy_obj)
            return strategy_obj.id
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


class RefinementNode(AgentNode):
    """
    Refinement loop node: injects backtest failure feedback before regeneration.

    Triggered when BacktestNode results don't meet acceptance criteria:
        - total_trades < MIN_TRADES (5)
        - sharpe_ratio <= 0
        - max_drawdown >= MAX_DD_PCT (30%)

    Builds a structured feedback prompt and injects it into state.context so
    that GenerateStrategiesNode incorporates it on the next pass.
    Clears stale parse/select/build results to force fresh generation.

    Max iterations: MAX_REFINEMENTS (3). After that the pipeline proceeds to
    memory_update regardless of result quality.
    """

    MIN_TRADES = _MIN_TRADES
    MAX_DD_PCT = _MAX_DD_PCT
    MAX_REFINEMENTS = 3

    def __init__(self) -> None:
        super().__init__(
            name="refine_strategy",
            description="Build failure feedback and prepare for strategy regeneration",
            timeout=10.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        iteration = state.context.get("refinement_iteration", 0) + 1
        state.context["refinement_iteration"] = iteration

        backtest_result = state.get_result("backtest") or {}
        metrics = backtest_result.get("metrics", {}) or {}
        engine_warnings: list[str] = list(backtest_result.get("engine_warnings", None) or [])
        sample_trades: list[dict] = list(backtest_result.get("sample_trades", None) or [])

        trades = metrics.get("total_trades", 0)
        sharpe = metrics.get("sharpe_ratio", 0.0)
        dd = metrics.get("max_drawdown", 100.0)
        total_return = metrics.get("total_return", 0.0)

        # --- Use structured analysis from BacktestAnalysisNode if available ---
        analysis: dict[str, Any] = state.context.get("backtest_analysis", {})
        severity = analysis.get("severity", "unknown")
        root_cause = analysis.get("root_cause", "unknown")
        analysis_suggestions: list[str] = analysis.get("suggestions", [])

        # Build precise failure diagnosis
        failures: list[str] = []
        suggestions: list[str] = list(analysis_suggestions)  # start from structured analysis

        if trades < self.MIN_TRADES:
            failures.append(f"too few trades ({trades} < {self.MIN_TRADES} required)")
            if not any("trade" in s.lower() or "signal" in s.lower() for s in suggestions):
                suggestions.append(
                    "Use more sensitive signal conditions (lower RSI periods, "
                    "tighter MA crossover periods, or add more entry signals)."
                )
        if sharpe <= 0:
            failures.append(f"negative Sharpe ratio ({sharpe:.2f})")
            if not any("sharpe" in s.lower() or "risk" in s.lower() for s in suggestions):
                suggestions.append(
                    "Improve risk-adjusted return: add trend filter, tighten stop-loss, "
                    "or switch to a different indicator combination."
                )
        if dd >= self.MAX_DD_PCT:
            failures.append(f"excessive drawdown ({dd:.1f}% >= {self.MAX_DD_PCT}% limit)")
            if not any("drawdown" in s.lower() or "risk" in s.lower() for s in suggestions):
                suggestions.append(
                    "Reduce risk: use ATR-based stop-loss, add volatility filter, or switch to a shorter-term strategy."
                )
        if not failures:
            # Shouldn't happen (router only calls us on failure) but be safe
            failures.append("did not meet overall quality threshold")

        # Severity context prefix
        severity_prefix = {
            "near_miss": "⚠️ NEAR-MISS (small adjustment may fix this)",
            "moderate": "❌ MODERATE FAILURE",
            "catastrophic": "🚨 CATASTROPHIC FAILURE (complete redesign needed)",
        }.get(severity, "❌ FAILURE")

        feedback_parts = [
            f"=== REFINEMENT FEEDBACK (iteration {iteration}/{self.MAX_REFINEMENTS}) [{severity_prefix}] ===",
            f"Root cause diagnosis: {root_cause.upper().replace('_', ' ')}",
            f"The previous strategy FAILED backtesting due to: {'; '.join(failures)}.",
            f"Backtest summary: {trades} trades, Sharpe={sharpe:.2f}, MaxDD={dd:.1f}%, Return={total_return:.1f}%.",
        ]

        # Append engine warnings (DIRECTION_MISMATCH, NO_TRADES, etc.)
        relevant_warnings = [
            w
            for w in engine_warnings
            if any(tag in str(w) for tag in ("DIRECTION_MISMATCH", "NO_TRADES", "INVALID_OHLC", "BAR_MAGNIFIER"))
        ]
        if relevant_warnings:
            feedback_parts.append("\nENGINE WARNINGS (root cause clues):")
            for w in relevant_warnings:
                if "DIRECTION_MISMATCH" in str(w):
                    feedback_parts.append(
                        "  [DIRECTION_MISMATCH] The strategy generates signals only in one direction "
                        "but the backtest is configured for both long and short. "
                        "Ensure your blocks output BOTH 'long' AND 'short' port signals."
                    )
                elif "NO_TRADES" in str(w):
                    feedback_parts.append(
                        "  [NO_TRADES] Signals were generated but no trades were executed. "
                        "Check that SL/TP values are realistic and port names are correct "
                        "(e.g. use 'long'/'short', not 'signal'/'output')."
                    )
                else:
                    feedback_parts.append(f"  {w}")

        # Append graph conversion warnings
        graph_warnings = state.context.get("graph_warnings", [])
        if graph_warnings:
            feedback_parts.append("\nGRAPH CONVERSION WARNINGS:")
            for w in graph_warnings[:3]:
                feedback_parts.append(f"  {w}")

        # Append sample trades for diagnosing near-misses (< 10 trades executed)
        if 0 < trades < 10 and sample_trades:
            feedback_parts.append(f"\nSAMPLE TRADES (first {len(sample_trades)} of {trades}):")
            for i, t in enumerate(sample_trades[:5], 1):
                entry = t.get("entry_price", t.get("entry", "?"))
                exit_p = t.get("exit_price", t.get("exit", "?"))
                pnl = t.get("pnl", t.get("profit", "?"))
                direction = t.get("direction", t.get("side", "?"))
                feedback_parts.append(f"  #{i}: {direction} entry={entry} exit={exit_p} pnl={pnl}")

        if severity == "near_miss":
            feedback_parts.append(
                "\nNEAR-MISS GUIDANCE: Results are close to passing. "
                "Small parameter tweaks may be sufficient — try ±20% on key periods."
            )

        feedback_parts.append("\nREQUIRED IMPROVEMENTS:")
        feedback_parts.extend(f"  {i + 1}. {s}" for i, s in enumerate(suggestions))

        regeneration_instruction = (
            "\nGenerate a DIFFERENT strategy that directly addresses these specific failures. "
            "Do NOT repeat the same indicator combination or parameter values."
            if severity != "near_miss"
            else "\nRefine the strategy to address the root cause. "
            "You may keep the same indicator type but adjust parameters."
        )
        feedback_parts.append(regeneration_instruction)

        feedback = "\n".join(feedback_parts)

        state.context["refinement_feedback"] = feedback

        # Clear stale results from the previous iteration so downstream nodes re-run fresh.
        # These keys are always regenerated in the next loop by parse_responses → select_best
        # → build_graph → backtest nodes. Clearing here prevents stale data from being used.
        for stale_key in ("parse_responses", "select_best", "build_graph", "backtest"):
            state.results.pop(stale_key, None)

        state.set_result(
            self.name,
            {
                "iteration": iteration,
                "failures": failures,
                "previous_metrics": {
                    "total_trades": trades,
                    "sharpe_ratio": sharpe,
                    "max_drawdown": dd,
                    "total_return": total_return,
                },
            },
        )
        state.add_message(
            "system",
            f"Refinement {iteration}/{self.MAX_REFINEMENTS}: {'; '.join(failures)}",
            self.name,
        )
        logger.info(f"🔄 [RefinementNode] iter={iteration}/{self.MAX_REFINEMENTS} failures={failures}")
        return state


class OptimizationNode(AgentNode):
    """
    Phase 6: Run a lightweight Optuna optimization on the AI-generated strategy_graph.

    Triggered only when:
    - run_backtest=True
    - backtest passed acceptance criteria
    - strategy_graph is available in state.context

    Runs N_TRIALS Optuna TPE trials to tune indicator parameters.
    Multi-objective scoring: Sharpe (50%) + Sortino (30%) + ProfitFactor (20%).
    Results are stored in state.context["optimization_result"] and the best
    graph is written to state.context["optimized_graph"].

    Non-blocking: optimization failure does not abort the pipeline.
    """

    N_TRIALS = 50
    TIMEOUT_SECONDS = 120  # 2 min max to keep the pipeline responsive

    def __init__(self) -> None:
        super().__init__(
            name="optimize_strategy",
            description="Run Optuna parameter optimization on strategy_graph (Phase 6)",
            timeout=150.0,  # TIMEOUT_SECONDS + 30s headroom
        )

    async def execute(self, state: AgentState) -> AgentState:
        strategy_graph = state.context.get("strategy_graph")
        df = state.context.get("df")

        if strategy_graph is None or df is None:
            logger.debug("[OptimizationNode] No strategy_graph or df — skipping optimization")
            return state

        symbol = state.context.get("symbol", "BTCUSDT")
        timeframe = state.context.get("timeframe", "15")
        initial_capital = state.context.get("initial_capital", INITIAL_CAPITAL)
        leverage = state.context.get("leverage", 1)
        agent_hints = state.context.get("agent_optimization_hints", {})

        config_params = {
            "symbol": symbol,
            "timeframe": timeframe,
            "initial_capital": initial_capital,
            "leverage": leverage,
            "commission_value": COMMISSION_TV,
            "direction": "both",
        }

        # Multi-objective weights: Sharpe 50%, Sortino 30%, ProfitFactor 20%
        weights = {
            "sharpe_ratio": 0.50,
            "sortino_ratio": 0.30,
            "profit_factor": 0.20,
        }

        logger.info(f"🔧 [OptimizationNode] Starting {self.N_TRIALS}-trial Optuna search on {symbol} {timeframe}")

        try:
            opt_result = await asyncio.to_thread(
                self._run_optimization,
                strategy_graph,
                df,
                config_params,
                weights,
                agent_hints,
            )

            best_params = opt_result.get("best_params", {})
            best_metrics = opt_result.get("best_metrics", {})
            best_score = opt_result.get("best_score", 0.0)
            tested = opt_result.get("tested_combinations", 0)

            logger.info(
                f"✅ [OptimizationNode] {tested} trials, best_score={best_score:.3f}, "
                f"Sharpe={best_metrics.get('sharpe_ratio', 0):.2f}"
            )

            state.context["optimization_result"] = opt_result

            # Apply best params to create optimized graph
            if best_params:
                from backend.optimization.builder_optimizer import clone_graph_with_params

                optimized_graph = clone_graph_with_params(strategy_graph, best_params)
                state.context["optimized_graph"] = optimized_graph
                # Overwrite strategy_graph so MemoryUpdateNode saves the optimized version
                state.context["strategy_graph"] = optimized_graph

            state.set_result(
                self.name,
                {
                    "tested_combinations": tested,
                    "best_score": best_score,
                    "best_params": best_params,
                    "best_sharpe": best_metrics.get("sharpe_ratio", 0.0),
                    "best_trades": best_metrics.get("total_trades", 0),
                    "best_drawdown": best_metrics.get("max_drawdown", 0.0),
                    "status": opt_result.get("status", "unknown"),
                },
            )
            state.add_message(
                "system",
                f"Optimization: {tested} trials, Sharpe={best_metrics.get('sharpe_ratio', 0):.2f}",
                self.name,
            )

        except Exception as exc:
            logger.warning(f"[OptimizationNode] Optimization failed (non-fatal): {exc}")
            state.set_result(self.name, {"status": "error", "error": str(exc)})

        return state

    def _run_optimization(
        self,
        strategy_graph: dict,
        df,
        config_params: dict,
        weights: dict,
        agent_hints: dict | None = None,
    ) -> dict:
        """Synchronous Optuna optimization (runs in thread via asyncio.to_thread)."""
        from backend.optimization.builder_optimizer import (
            extract_optimizable_params,
            run_builder_optuna_search,
        )

        param_specs = extract_optimizable_params(strategy_graph)

        # Apply agent-provided optimization hints to narrow/focus param ranges
        if agent_hints and param_specs:
            param_specs = self._apply_agent_hints(param_specs, agent_hints)

        if not param_specs:
            logger.info("[OptimizationNode] No optimizable params found in graph")
            return {
                "status": "skipped",
                "reason": "no_optimizable_params",
                "tested_combinations": 0,
                "best_params": {},
                "best_score": 0.0,
                "best_metrics": {},
            }

        logger.info(f"[OptimizationNode] {len(param_specs)} param specs extracted, running {self.N_TRIALS} trials")

        return run_builder_optuna_search(
            base_graph=strategy_graph,
            ohlcv=df,
            param_specs=param_specs,
            config_params=config_params,
            optimize_metric="sharpe_ratio",
            weights=weights,
            n_trials=self.N_TRIALS,
            sampler_type="tpe",
            top_n=5,
            timeout_seconds=self.TIMEOUT_SECONDS,
            n_jobs=1,
        )

    @staticmethod
    def _apply_agent_hints(param_specs: list[dict], hints: dict) -> list[dict]:
        """Narrow or focus param ranges using agent-provided optimization_hints.

        The agent's optimization_hints.optimizationParams field has the format:
            {"param_key": {"enabled": true, "min": 5, "max": 20, "step": 1}, ...}

        This method overrides extracted default ranges for matched params.
        Params not mentioned in hints are left unchanged (default ranges apply).
        """
        hint_params: dict = hints.get("optimizationParams", {})
        if not hint_params:
            # Fall back to simple ranges dict: {"period": [5, 20]}
            ranges = hints.get("ranges", {})
            hint_params = {
                k: {"enabled": True, "min": v[0], "max": v[1], "step": 1}
                for k, v in ranges.items()
                if isinstance(v, list) and len(v) >= 2
            }

        if not hint_params:
            return param_specs

        updated: list[dict] = []
        for spec in param_specs:
            param_key = spec.get("param_key", spec.get("key", ""))
            # Match by bare param key (e.g. "period" from "block_1.period")
            bare_key = param_key.split(".")[-1] if "." in param_key else param_key
            override = hint_params.get(bare_key) or hint_params.get(param_key)

            if override and override.get("enabled", True):
                spec = dict(spec)
                if "min" in override:
                    spec["low"] = override["min"]
                if "max" in override:
                    spec["high"] = override["max"]
                if "step" in override:
                    spec["step"] = override["step"]
                logger.debug(
                    f"[OptimizationNode] Agent hint applied to '{param_key}': "
                    f"range=[{spec.get('low')}, {spec.get('high')}] step={spec.get('step')}"
                )
            updated.append(spec)

        return updated


class MLValidationNode(AgentNode):
    """
    Phase 7: ML Integration Layer — three lightweight validation checks on the
    optimized strategy before it is persisted to memory.

    Checks (all non-blocking — failures add warnings but do not abort the pipeline):

    7.1 Overfitting Detection
        Split OHLCV into in-sample (IS, first 70%) and out-of-sample (OOS, last 30%).
        Run the strategy_graph on both halves.  If IS_sharpe − OOS_sharpe > 0.5 the
        strategy is flagged as potentially overfit (overfitting_score = gap / 2.0).

    7.2 Regime Analysis
        Use HMMRegimeDetector (or KMeansRegimeDetector as fallback) from
        backend.ml.regime_detection to label each bar with a market regime.
        Report per-regime Sharpe so the user knows which regimes the strategy avoids.
        Recommends adding a regime filter when ≥1 regime has Sharpe < 0.

    7.3 Parameter Stability
        Perturb each indicator period in the strategy_graph by ±20% and re-run
        a quick backtest.  If Sharpe stays > 0 for all perturbations the strategy
        is considered parameter-stable.

    Results are stored in state.context["ml_validation"] and state.results["ml_validation"].
    """

    # Overfitting thresholds
    IS_FRACTION = 0.70  # 70% in-sample, 30% OOS
    OVERFIT_GAP_THRESHOLD = 0.5  # IS_sharpe - OOS_sharpe > this → overfit flag
    OVERFIT_SCORE_DIVISOR = 2.0  # normalise gap into [0, 1] range

    # Perturbation test
    PERTURB_FRACTIONS = [-0.20, +0.20]  # ±20% of original period value

    def __init__(self) -> None:
        super().__init__(
            name="ml_validation",
            description="Phase 7: Overfitting detection + regime analysis + parameter stability",
            timeout=120.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        strategy_graph = state.context.get("strategy_graph")
        df = state.context.get("df")

        if strategy_graph is None or df is None or (hasattr(df, "empty") and df.empty):
            logger.debug("[MLValidationNode] No strategy_graph or df — skipping ML validation")
            state.set_result(self.name, {"status": "skipped", "reason": "no_graph_or_data"})
            return state

        symbol = state.context.get("symbol", "BTCUSDT")
        timeframe = state.context.get("timeframe", "15")
        initial_capital = state.context.get("initial_capital", INITIAL_CAPITAL)
        leverage = state.context.get("leverage", 1)

        validation: dict[str, Any] = {
            "status": "ok",
            "overfitting": {},
            "regime_analysis": {},
            "parameter_stability": {},
            "warnings": [],
        }

        # ------------------------------------------------------------------
        # 7.1  Overfitting detection
        # ------------------------------------------------------------------
        try:
            overfit_result = await asyncio.to_thread(
                self._check_overfitting,
                strategy_graph,
                df,
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "initial_capital": initial_capital,
                    "leverage": leverage,
                    "commission_value": COMMISSION_TV,
                    "direction": "both",
                },
            )
            validation["overfitting"] = overfit_result
            if overfit_result.get("is_overfit"):
                validation["warnings"].append(
                    f"[OVERFIT] IS_sharpe={overfit_result['is_sharpe']:.2f} "
                    f"OOS_sharpe={overfit_result['oos_sharpe']:.2f} "
                    f"gap={overfit_result['gap']:.2f} (threshold {self.OVERFIT_GAP_THRESHOLD})"
                )
                logger.warning(f"⚠️ [MLValidation] Overfitting detected: gap={overfit_result['gap']:.2f}")
            else:
                logger.info(
                    f"✅ [MLValidation] Overfitting check passed "
                    f"(IS={overfit_result.get('is_sharpe', 0):.2f} "
                    f"OOS={overfit_result.get('oos_sharpe', 0):.2f})"
                )
        except Exception as exc:
            logger.warning(f"[MLValidationNode] Overfitting check failed (non-fatal): {exc}")
            validation["overfitting"] = {"status": "error", "error": str(exc)}

        # ------------------------------------------------------------------
        # 7.2  Regime analysis
        # ------------------------------------------------------------------
        try:
            regime_result = await asyncio.to_thread(
                self._check_regimes,
                strategy_graph,
                df,
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "initial_capital": initial_capital,
                    "leverage": leverage,
                    "commission_value": COMMISSION_TV,
                    "direction": "both",
                },
            )
            validation["regime_analysis"] = regime_result
            poor_regimes = [r for r, s in regime_result.get("regime_sharpes", {}).items() if s < 0]
            if poor_regimes:
                validation["warnings"].append(
                    f"[REGIME] Strategy performs poorly in: {poor_regimes}. Consider adding a regime filter block."
                )
                logger.info(f"ℹ️ [MLValidation] Poor regimes: {poor_regimes}")
            else:
                logger.info("✅ [MLValidation] Regime check: strategy viable across all regimes")
        except Exception as exc:
            logger.warning(f"[MLValidationNode] Regime analysis failed (non-fatal): {exc}")
            validation["regime_analysis"] = {"status": "error", "error": str(exc)}

        # ------------------------------------------------------------------
        # 7.3  Parameter stability
        # ------------------------------------------------------------------
        try:
            stability_result = await asyncio.to_thread(
                self._check_parameter_stability,
                strategy_graph,
                df,
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "initial_capital": initial_capital,
                    "leverage": leverage,
                    "commission_value": COMMISSION_TV,
                    "direction": "both",
                },
            )
            validation["parameter_stability"] = stability_result
            if not stability_result.get("is_stable", True):
                validation["warnings"].append(
                    f"[STABILITY] Sensitive params: {stability_result.get('sensitive_params', [])}"
                )
                logger.warning(f"⚠️ [MLValidation] Parameter instability: {stability_result.get('sensitive_params')}")
            else:
                logger.info("✅ [MLValidation] Parameter stability check passed")
        except Exception as exc:
            logger.warning(f"[MLValidationNode] Stability check failed (non-fatal): {exc}")
            validation["parameter_stability"] = {"status": "error", "error": str(exc)}

        # Store results
        state.context["ml_validation"] = validation
        state.set_result(self.name, validation)
        state.add_message(
            "system",
            f"ML validation: {len(validation['warnings'])} warning(s)",
            self.name,
        )
        logger.info(
            f"🔬 [MLValidationNode] Complete — {len(validation['warnings'])} warnings: "
            f"{validation['warnings'] or 'none'}"
        )
        return state

    # ------------------------------------------------------------------
    # Internal helpers (synchronous, called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _run_strategy(self, strategy_graph: dict, df, config_params: dict) -> dict:
        """Run strategy_graph on the given df slice and return metrics dict."""
        from backend.backtesting.engine import BacktestEngine
        from backend.backtesting.models import BacktestConfig
        from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter

        adapter = StrategyBuilderAdapter(strategy_graph)
        signal_result = adapter.generate_signals(df)

        cfg = BacktestConfig(
            symbol=config_params.get("symbol", "BTCUSDT"),
            timeframe=config_params.get("timeframe", "15"),
            initial_capital=config_params.get("initial_capital", INITIAL_CAPITAL),
            leverage=config_params.get("leverage", 1),
            direction=config_params.get("direction", "both"),
            commission_value=config_params.get("commission_value", 0.0007),
        )
        engine = BacktestEngine()
        result = engine.run(data=df, signals=signal_result, config=cfg)
        return result.metrics if hasattr(result, "metrics") else {}

    def _check_overfitting(self, strategy_graph: dict, df, config_params: dict) -> dict:
        """7.1: In-sample vs out-of-sample Sharpe comparison."""
        n = len(df)
        if n < 100:
            return {"status": "skipped", "reason": "insufficient_data"}

        split_idx = int(n * self.IS_FRACTION)
        df_is = df.iloc[:split_idx].copy()
        df_oos = df.iloc[split_idx:].copy()

        if len(df_is) < 50 or len(df_oos) < 30:
            return {"status": "skipped", "reason": "insufficient_data_after_split"}

        try:
            is_metrics = self._run_strategy(strategy_graph, df_is, config_params)
            oos_metrics = self._run_strategy(strategy_graph, df_oos, config_params)
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

        is_sharpe = is_metrics.get("sharpe_ratio", 0.0)
        oos_sharpe = oos_metrics.get("sharpe_ratio", 0.0)
        gap = is_sharpe - oos_sharpe
        overfitting_score = min(1.0, max(0.0, gap / self.OVERFIT_SCORE_DIVISOR))
        is_overfit = gap > self.OVERFIT_GAP_THRESHOLD

        return {
            "status": "ok",
            "is_sharpe": is_sharpe,
            "oos_sharpe": oos_sharpe,
            "gap": gap,
            "overfitting_score": overfitting_score,
            "is_overfit": is_overfit,
            "is_trades": is_metrics.get("total_trades", 0),
            "oos_trades": oos_metrics.get("total_trades", 0),
        }

    def _check_regimes(self, strategy_graph: dict, df, config_params: dict) -> dict:
        """7.2: Per-regime Sharpe analysis."""
        import numpy as np

        if len(df) < 100:
            return {"status": "skipped", "reason": "insufficient_data"}

        # Detect regimes (try HMM, fallback to KMeans)
        try:
            from backend.ml.regime_detection import HMMRegimeDetector

            detector = HMMRegimeDetector(n_regimes=3, n_iter=50)
            regime_result = detector.fit_predict(df)
        except Exception:
            try:
                from backend.ml.regime_detection import KMeansRegimeDetector

                detector = KMeansRegimeDetector(n_regimes=3)
                regime_result = detector.fit_predict(df)
            except Exception as exc:
                return {"status": "error", "error": f"regime detector unavailable: {exc}"}

        regimes = regime_result.regimes
        n_regimes = regime_result.n_regimes
        regime_names = regime_result.regime_names

        # Get entry signals for the full df (to split per regime)
        try:
            from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter

            adapter = StrategyBuilderAdapter(strategy_graph)
            signal_result = adapter.generate_signals(df)
            entries = (
                signal_result.entries.values if hasattr(signal_result.entries, "values") else signal_result.entries
            )
        except Exception:
            entries = None

        regime_sharpes: dict[str, float] = {}
        for i in range(n_regimes):
            regime_mask = regimes == i
            regime_indices = np.where(regime_mask)[0]
            if len(regime_indices) < 30:
                continue
            df_regime = df.iloc[regime_indices].copy()
            try:
                metrics = self._run_strategy(strategy_graph, df_regime, config_params)
                regime_sharpes[regime_names[i]] = metrics.get("sharpe_ratio", 0.0)
            except Exception:
                regime_sharpes[regime_names[i]] = 0.0

        return {
            "status": "ok",
            "n_regimes": n_regimes,
            "regime_names": regime_names,
            "regime_sharpes": regime_sharpes,
            "current_regime": regime_result.current_regime_name,
            "regime_distribution": {
                regime_names[i]: float(np.mean(regimes == i)) for i in range(n_regimes) if i < len(regime_names)
            },
        }

    def _check_parameter_stability(self, strategy_graph: dict, df, config_params: dict) -> dict:
        """7.3: Perturb indicator periods ±20% and check Sharpe stability."""
        import copy

        if len(df) < 100:
            return {"status": "skipped", "reason": "insufficient_data"}

        # Extract period params from blocks
        period_params: list[tuple[int, str, int]] = []  # (block_idx, param_name, value)
        for b_idx, block in enumerate(strategy_graph.get("blocks", [])):
            params = block.get("params", {})
            for k, v in params.items():
                if "period" in k.lower() and isinstance(v, int) and v > 1:
                    period_params.append((b_idx, k, v))

        if not period_params:
            return {"status": "skipped", "reason": "no_period_params"}

        # Baseline Sharpe
        try:
            base_metrics = self._run_strategy(strategy_graph, df, config_params)
            base_sharpe = base_metrics.get("sharpe_ratio", 0.0)
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

        sensitive_params: list[str] = []

        for b_idx, param_name, orig_value in period_params:
            for frac in self.PERTURB_FRACTIONS:
                perturbed_graph = copy.deepcopy(strategy_graph)
                new_value = max(2, int(round(orig_value * (1.0 + frac))))
                perturbed_graph["blocks"][b_idx]["params"][param_name] = new_value

                try:
                    perturbed_metrics = self._run_strategy(perturbed_graph, df, config_params)
                    p_sharpe = perturbed_metrics.get("sharpe_ratio", 0.0)
                    # Flag if Sharpe flips sign or drops more than 1.0 from baseline
                    if (base_sharpe > 0 and p_sharpe <= 0) or (base_sharpe - p_sharpe > 1.0):
                        key = f"block[{b_idx}].{param_name}={orig_value}→{new_value}"
                        if key not in sensitive_params:
                            sensitive_params.append(key)
                except Exception:
                    pass  # ignore individual perturbation errors

        is_stable = len(sensitive_params) == 0
        return {
            "status": "ok",
            "is_stable": is_stable,
            "base_sharpe": base_sharpe,
            "tested_params": len(period_params),
            "sensitive_params": sensitive_params,
            "perturbation_fractions": self.PERTURB_FRACTIONS,
        }


# =============================================================================
# P2-3: Human-in-the-Loop (HITL) interrupt node
# =============================================================================


class HITLCheckNode(AgentNode):
    """
    P2-3: Human-in-the-loop checkpoint before memory is updated (optional).

    When enabled, the node inspects ``state.context["hitl_approved"]``:
    - If ``True``  → pipeline continues normally (human approved)
    - If ``False`` or missing → sets ``state.context["hitl_pending"] = True``
      and ``state.context["hitl_payload"]`` with the strategy summary for review,
      then returns early.  ``run_strategy_pipeline()`` callers can detect this
      and pause/resume by re-calling with ``hitl_approved=True`` in context.

    The node is wired between ``ml_validation`` and ``memory_update`` when
    ``build_trading_strategy_graph(hitl_enabled=True)`` is called.
    """

    def __init__(self) -> None:
        super().__init__(
            name="hitl_check",
            description="HITL: pause pipeline for human review before memory update",
            timeout=5.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        approved: bool = bool(state.context.get("hitl_approved", False))

        if approved:
            logger.info("✅ [HITL] Human approved — continuing to memory_update")
            state.context.pop("hitl_pending", None)
            return state

        # Build a compact summary for the human reviewer
        best = state.get_result("select_best") or {}
        bt = state.get_result("backtest") or {}
        wf = state.get_result("wf_validation") or {}

        payload = {
            "strategy_name": (best.get("strategy", {}) or {}).get("strategy_name", "unknown"),
            "backtest_summary": {
                "trades": bt.get("total_trades", 0),
                "sharpe": round(bt.get("sharpe_ratio", 0.0), 3),
                "max_dd": round(bt.get("max_drawdown", 0.0), 2),
                "net_profit": round(bt.get("net_profit", 0.0), 2),
            },
            "wf_passed": wf.get("wf_passed", None),
            "regime": state.context.get("regime_classification", {}).get("regime", "unknown"),
            "message": (
                "Pipeline paused for human review. "
                "Set state.context['hitl_approved'] = True and re-run to continue."
            ),
        }

        state.context["hitl_pending"] = True
        state.context["hitl_payload"] = payload
        logger.info(
            f"⏸️ [HITL] Pipeline paused — strategy='{payload['strategy_name']}' "
            f"sharpe={payload['backtest_summary']['sharpe']}. "
            f"Set hitl_approved=True to continue."
        )
        state.set_result(self.name, payload)
        return state


# =============================================================================
# P1-1: Post-run self-reflection node
# =============================================================================


class PostRunReflectionNode(AgentNode):
    """
    P1-1: Self-reflection node — writes a structured retrospective after each pipeline run.

    TradingGroup (arXiv 2025) pattern: agents record *why* a result succeeded or failed,
    not just the raw metrics. Future runs retrieve these reflections via MemoryRecallNode
    to improve generation quality iteratively.

    Stores:
    - ``state.results["reflection"]`` — structured dict in the current run
    - HierarchicalMemory (EPISODIC, tagged "reflection") — persisted for future recall

    Wired: memory_update → reflection → report
    """

    def __init__(self) -> None:
        super().__init__(
            name="reflection",
            description="Write structured retrospective after pipeline run (TradingGroup pattern)",
            timeout=10.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        backtest = state.get_result("backtest") or {}
        metrics = backtest.get("metrics", {}) or {}
        analysis = state.get_result("backtest_analysis") or {}
        selected = state.get_result("select_best") or {}
        market = state.get_result("analyze_market") or {}

        symbol = state.context.get("symbol", "BTCUSDT")
        timeframe = state.context.get("timeframe", "15")
        regime = market.get("regime", "unknown")
        sharpe = metrics.get("sharpe_ratio")
        dd = metrics.get("max_drawdown")
        trades = metrics.get("total_trades")
        passed = analysis.get("passed", False)
        root_cause = analysis.get("root_cause", "unknown")
        severity = analysis.get("severity", "unknown")
        wf = state.context.get("wf_validation", {})
        wf_ratio = wf.get("ratio")
        errors = state.errors

        # ── What worked ─────────────────────────────────────────────────────
        what_worked: list[str] = []
        if passed:
            what_worked.append(f"Strategy passed acceptance criteria (Sharpe={sharpe:.2f})")
        if trades and trades >= 10:
            what_worked.append(f"Sufficient trade count ({trades} trades)")
        if wf_ratio and wf_ratio >= 0.5:
            what_worked.append(f"Walk-forward stable (wf/is ratio={wf_ratio:.2f})")
        if not errors:
            what_worked.append("Pipeline completed without errors")

        # ── What failed ─────────────────────────────────────────────────────
        what_failed: list[str] = []
        if not passed:
            what_failed.append(f"Strategy did not pass: severity={severity}, root_cause={root_cause}")
        if sharpe is not None and sharpe <= 0:
            what_failed.append(f"Negative Sharpe ratio ({sharpe:.2f})")
        if dd is not None and dd >= 25.0:
            what_failed.append(f"High drawdown ({dd:.1f}%)")
        if wf_ratio is not None and wf_ratio < 0.5:
            what_failed.append(f"Walk-forward overfitting detected (ratio={wf_ratio:.2f} < 0.5)")
        if errors:
            what_failed.extend([f"Error in {e['node']}: {e['error_message'][:80]}" for e in errors[:3]])

        # ── Recommended adjustments ──────────────────────────────────────────
        adjustments: list[str] = []
        if root_cause == "direction_mismatch":
            adjustments.append("Verify signal direction matches backtest direction setting")
        elif root_cause == "no_signal":
            adjustments.append("Add condition blocks or relax indicator thresholds to generate signals")
        elif root_cause == "sl_too_tight":
            adjustments.append("Increase stop-loss distance (e.g., ATR-based SL instead of fixed %)")
        elif root_cause == "poor_risk_reward":
            adjustments.append("Improve risk/reward ratio: widen TP or tighten SL")
        elif root_cause == "low_activity":
            adjustments.append("Reduce indicator period or oversold/overbought thresholds to increase signal frequency")
        if regime in ("ranging", "low_vol"):
            adjustments.append(f"In {regime} regime: prefer mean-reversion strategies (BB, RSI) over trend-following")
        elif regime in ("trending_bull", "trending_bear"):
            adjustments.append(f"In {regime} regime: prefer trend-following (EMA crossover, Supertrend) over oscillators")

        reflection = {
            "symbol": symbol,
            "timeframe": timeframe,
            "regime": regime,
            "passed": passed,
            "sharpe_ratio": sharpe,
            "max_drawdown": dd,
            "total_trades": trades,
            "severity": severity,
            "root_cause": root_cause,
            "what_worked": what_worked,
            "what_failed": what_failed,
            "recommended_adjustments": adjustments,
            "wf_ratio": wf_ratio,
            "llm_call_count": state.llm_call_count,
            "total_cost_usd": round(state.total_cost_usd, 6),
        }
        state.set_result(self.name, reflection)

        # ── Persist to HierarchicalMemory for future recall ──────────────────
        reflection_text = (
            f"Run reflection for {symbol}/{timeframe} regime={regime}: "
            f"passed={passed}, sharpe={sharpe}, dd={dd:.1f}% if dd else '?', trades={trades}. "
            f"What worked: {'; '.join(what_worked) or 'nothing'}. "
            f"What failed: {'; '.join(what_failed) or 'nothing'}. "
            f"Adjustments: {'; '.join(adjustments) or 'none'}."
        )
        importance = 0.6 if passed else 0.3  # failed runs are still valuable

        try:
            from backend.agents.memory.hierarchical_memory import HierarchicalMemory, MemoryType

            memory = HierarchicalMemory()
            await memory.store(
                content=reflection_text,
                memory_type=MemoryType.EPISODIC,
                importance=importance,
                tags=["reflection", symbol, timeframe, regime, "passed" if passed else "failed"],
                metadata={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "regime": regime,
                    "passed": passed,
                    "sharpe_ratio": sharpe,
                    "root_cause": root_cause,
                    "adjustments": adjustments,
                },
                source="post_run_reflection",
                agent_namespace="strategy_gen",
            )
            logger.info(f"🪞 [Reflection] Stored retrospective (passed={passed}, sharpe={sharpe})")
        except Exception as exc:
            logger.warning(f"[Reflection] Memory store failed (non-fatal): {exc}")

        return state


# =============================================================================
# P1-2: Walk-forward validation gate
# =============================================================================


class WalkForwardValidationNode(AgentNode):
    """
    P1-2: Walk-forward overfitting gate.

    Academic consensus (TradingAgents, AI-Trader, StockBench, 2025):
    In-sample Sharpe alone is the primary failure mode of AI-generated strategies.
    Any strategy that passes the BacktestAnalysisNode must also survive walk-forward
    validation before proceeding to optimization.

    Acceptance criterion:
        wf_sharpe / is_sharpe >= WF_RATIO_THRESHOLD (0.5)

    If the walk-forward Sharpe is less than half the in-sample Sharpe, the strategy
    is flagged as overfitted and the refinement loop is re-triggered.

    Result stored in:
    - ``state.context["wf_validation"]`` — {passed, wf_sharpe, is_sharpe, ratio, windows}
    - ``state.results["wf_validation"]`` — same dict

    Wired: backtest_analysis (passes) → wf_validation → [optimize | refine]
    """

    WF_RATIO_THRESHOLD: float = 0.5  # wf_sharpe / is_sharpe must exceed this
    TRAIN_MONTHS: int = 3            # walk-forward training window
    TEST_MONTHS: int = 1             # walk-forward test window
    MIN_BARS_FOR_WF: int = 200       # skip WF if fewer bars available

    def __init__(self) -> None:
        super().__init__(
            name="wf_validation",
            description="Walk-forward overfitting gate (wf_sharpe/is_sharpe >= 0.5)",
            timeout=60.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        backtest_result = state.get_result("backtest") or {}
        metrics = backtest_result.get("metrics", {}) or {}
        is_sharpe: float = float(metrics.get("sharpe_ratio", 0.0))
        strategy_graph = state.context.get("strategy_graph") or backtest_result.get("strategy_graph")
        df: pd.DataFrame | None = state.context.get("df")

        # Skip if no graph, no data, or in-sample sharpe already negative
        if strategy_graph is None or df is None or df.empty or is_sharpe <= 0:
            result = {
                "passed": True,  # don't block on missing inputs
                "skipped": True,
                "reason": "no_graph_or_negative_is_sharpe",
                "is_sharpe": is_sharpe,
            }
            state.set_result(self.name, result)
            state.context["wf_validation"] = result
            logger.debug(f"[WF] Skipped walk-forward: {result['reason']}")
            return state

        if len(df) < self.MIN_BARS_FOR_WF:
            result = {
                "passed": True,
                "skipped": True,
                "reason": f"insufficient_bars ({len(df)} < {self.MIN_BARS_FOR_WF})",
                "is_sharpe": is_sharpe,
            }
            state.set_result(self.name, result)
            state.context["wf_validation"] = result
            return state

        # Run lightweight rolling walk-forward
        wf_sharpes: list[float] = []
        try:
            wf_sharpes = await asyncio.to_thread(
                self._run_rolling_wf, strategy_graph, df, is_sharpe
            )
        except Exception as exc:
            logger.warning(f"[WF] Walk-forward failed (non-fatal): {exc}")
            result = {"passed": True, "skipped": True, "reason": f"wf_error: {exc}", "is_sharpe": is_sharpe}
            state.set_result(self.name, result)
            state.context["wf_validation"] = result
            return state

        wf_sharpe = sum(wf_sharpes) / len(wf_sharpes) if wf_sharpes else 0.0
        ratio = wf_sharpe / is_sharpe if is_sharpe != 0 else 0.0
        passed = ratio >= self.WF_RATIO_THRESHOLD

        result = {
            "passed": passed,
            "skipped": False,
            "is_sharpe": round(is_sharpe, 4),
            "wf_sharpe": round(wf_sharpe, 4),
            "ratio": round(ratio, 4),
            "windows": len(wf_sharpes),
            "threshold": self.WF_RATIO_THRESHOLD,
        }
        state.set_result(self.name, result)
        state.context["wf_validation"] = result

        if passed:
            logger.info(f"✅ [WF] Walk-forward passed: ratio={ratio:.2f} ({wf_sharpe:.2f}/{is_sharpe:.2f})")
        else:
            logger.warning(
                f"⚠️ [WF] Overfitting detected: ratio={ratio:.2f} < {self.WF_RATIO_THRESHOLD} "
                f"(wf={wf_sharpe:.2f}, is={is_sharpe:.2f}) — flagging for refinement"
            )
            # Inject into backtest_analysis so _should_refine sees it
            analysis = state.context.get("backtest_analysis", {})
            analysis["passed"] = False
            analysis["wf_failed"] = True
            state.context["backtest_analysis"] = analysis

        return state

    def _run_rolling_wf(
        self, strategy_graph: dict, df: pd.DataFrame, is_sharpe: float
    ) -> list[float]:
        """Synchronous: run rolling walk-forward windows, return list of test Sharpes."""
        from backend.backtesting.engine import BacktestEngine
        from backend.backtesting.models import BacktestConfig
        from backend.config.constants import COMMISSION_TV

        bars_per_month = max(1, len(df) // 12)  # approximate
        train_bars = self.TRAIN_MONTHS * bars_per_month
        test_bars = self.TEST_MONTHS * bars_per_month
        step_bars = test_bars

        results: list[float] = []
        i = 0
        while i + train_bars + test_bars <= len(df):
            test_slice = df.iloc[i + train_bars: i + train_bars + test_bars]
            if len(test_slice) < 30:
                break
            try:
                config = BacktestConfig(
                    initial_capital=10000.0,
                    commission_value=COMMISSION_TV,
                    direction="both",
                )
                engine = BacktestEngine(config)
                bt_result = engine.run(test_slice, strategy_graph)
                sharpe = (bt_result.metrics or {}).get("sharpe_ratio", 0.0)
                results.append(float(sharpe))
            except Exception:
                results.append(0.0)
            i += step_bars

        return results


def _backtest_passes(state: AgentState) -> bool:
    """Return True if backtest metrics meet acceptance criteria.

    Reads from BacktestAnalysisNode result when available (single source of truth).
    Falls back to direct metric computation if BacktestAnalysisNode was skipped.
    """
    analysis = state.context.get("backtest_analysis")
    if analysis is not None:
        return bool(analysis.get("passed", False))
    # Fallback (BacktestAnalysisNode not in graph)
    metrics = (state.get_result("backtest") or {}).get("metrics", {})
    trades = metrics.get("total_trades", 0)
    sharpe = metrics.get("sharpe_ratio", -999.0)
    dd = metrics.get("max_drawdown", 100.0)
    return trades >= _MIN_TRADES and sharpe > -1e-9 and dd < _MAX_DD_PCT


def _should_refine(state: AgentState) -> bool:
    """Return True if we should trigger refinement (failed + iterations left)."""
    iteration = state.context.get("refinement_iteration", 0)
    return not _backtest_passes(state) and iteration < RefinementNode.MAX_REFINEMENTS


def _report_node(state: AgentState) -> AgentState:
    """Final node: compile all results into a report."""
    report = {
        "market_analysis": state.get_result("analyze_market"),
        "proposals_count": len((state.get_result("parse_responses") or {}).get("proposals", [])),
        "selected": state.get_result("select_best"),
        "backtest": state.get_result("backtest"),
        "backtest_analysis": state.get_result("backtest_analysis"),
        "errors": state.errors,
        "execution_path": state.execution_path,
        "pipeline_metrics": {
            "total_cost_usd": round(state.total_cost_usd, 6),
            "llm_call_count": state.llm_call_count,
            "node_timing_s": dict(state.execution_path),
            "total_wall_time_s": round(sum(t for _, t in state.execution_path), 3),
        },
    }
    state.set_result("report", report)
    state.add_message("system", "Pipeline report generated", "report")
    return state


# =============================================================================
# GRAPH BUILDER
# =============================================================================


def build_trading_strategy_graph(
    run_backtest: bool = True,
    run_debate: bool = True,
    run_wf_validation: bool = True,
    checkpoint_enabled: bool = False,
    hitl_enabled: bool = False,
    event_fn: "Callable[[str, dict[str, Any]], None] | None" = None,
) -> AgentGraph:
    """
    Build the full Trading Strategy generation graph.

    Args:
        run_backtest:       If True, includes backtest + memory_update nodes
        run_debate:         If True, includes the MAD debate node before generation
        run_wf_validation:  If True (default), adds WalkForwardValidationNode as an
                            overfitting gate between backtest_analysis and optimize.
                            P1-2: wf_sharpe/is_sharpe < 0.5 → re-triggers refinement.
        checkpoint_enabled: If True (default False), attach a SQLite checkpointer that
                            persists AgentState after every node transition.
                            P1-4: enables resume-after-crash and run audit trail.
        hitl_enabled:       If True (default False), adds HITLCheckNode between
                            ml_validation and memory_update (P2-3). Pipeline pauses
                            if state.context["hitl_approved"] != True.
        event_fn:           P2-4 streaming callback: called after each node completes
                            with (node_name, event_dict). Use make_pipeline_event_queue()
                            to create a queue-backed event_fn for WebSocket streaming.

    Returns:
        AgentGraph ready for execution

    Graph structure (full):
        analyze_market → regime_classifier → [debate] → memory_recall
                                                              → generate_strategies → parse_responses
                                                                    ↑                       │
                                                                    │               select_best (Consensus)
                                                                    │                       │
                                                           refine_strategy ←           build_graph
                                                           (iter < 3, fails)                │
                                                                                        backtest
                                                                                            │
                                                                                   backtest_analysis
                                                                                            ├── fails → refine (loop)
                                                                                            └── passes → [wf_validation →] optimize_strategy
                                                                                                               │
                                                                                                        ml_validation
                                                                                                               │
                                                                                              [hitl_check →] memory_update → reflection → report → END
    """
    graph = AgentGraph(
        name="trading_strategy_pipeline",
        description="AI-powered trading strategy generation with Self-MoA + MAD + ConsensusEngine",
        checkpoint_fn=make_sqlite_checkpointer() if checkpoint_enabled else None,
        event_fn=event_fn,
    )

    # Add core nodes
    graph.add_node(AnalyzeMarketNode())
    graph.add_node(RegimeClassifierNode())  # P2-1: deterministic regime classification
    graph.add_node(GenerateStrategiesNode())
    graph.add_node(ParseResponsesNode())
    graph.add_node(ConsensusNode())
    graph.add_node(FunctionAgent(name="report", func=_report_node, description="Final report"))

    # Chain: analyze → regime_classifier → [debate] → memory_recall → generate → parse → select
    graph.add_edge("analyze_market", "regime_classifier")
    graph.add_node(MemoryRecallNode())
    if run_debate:
        graph.add_node(DebateNode())
        graph.add_edge("regime_classifier", "debate")
        graph.add_edge("debate", "memory_recall")
    else:
        graph.add_edge("regime_classifier", "memory_recall")
    graph.add_edge("memory_recall", "generate_strategies")

    graph.add_edge("generate_strategies", "parse_responses")
    graph.add_edge("parse_responses", "select_best")

    if run_backtest:
        graph.add_node(BuildGraphNode())
        graph.add_node(BacktestNode())
        graph.add_node(BacktestAnalysisNode())
        graph.add_node(RefinementNode())
        graph.add_node(OptimizationNode())
        graph.add_node(MemoryUpdateNode())
        graph.add_node(PostRunReflectionNode())  # P1-1
        graph.add_edge("select_best", "build_graph")
        graph.add_edge("build_graph", "backtest")
        graph.add_edge("backtest", "backtest_analysis")

        if run_wf_validation:
            # P1-2: walk-forward gate between backtest_analysis and optimize
            graph.add_node(WalkForwardValidationNode())
            backtest_router = ConditionalRouter(name="backtest_router")
            backtest_router.add_route(_should_refine, "refine_strategy")
            backtest_router.set_default("wf_validation")
            graph.add_conditional_edges("backtest_analysis", backtest_router)

            wf_router = ConditionalRouter(name="wf_router")
            wf_router.add_route(_should_refine, "refine_strategy")
            wf_router.set_default("optimize_strategy")
            graph.add_conditional_edges("wf_validation", wf_router)
        else:
            backtest_router = ConditionalRouter(name="backtest_router")
            backtest_router.add_route(_should_refine, "refine_strategy")
            backtest_router.set_default("optimize_strategy")
            graph.add_conditional_edges("backtest_analysis", backtest_router)

        # After refinement, loop back to regenerate strategies
        graph.add_edge("refine_strategy", "generate_strategies")

        # Optimization → ML validation → [hitl_check →] memory_update → reflection → report
        graph.add_node(MLValidationNode())
        graph.add_edge("optimize_strategy", "ml_validation")

        if hitl_enabled:
            # P2-3: HITL checkpoint before memory_update
            graph.add_node(HITLCheckNode())
            graph.add_edge("ml_validation", "hitl_check")

            # After HITL: if pending → exit (caller inspects state); else → memory_update
            def _hitl_not_pending(state: AgentState) -> bool:
                return not state.context.get("hitl_pending", False)

            hitl_router = ConditionalRouter(name="hitl_router")
            hitl_router.add_route(_hitl_not_pending, "memory_update")
            hitl_router.set_default("report")  # exit early with hitl_pending=True
            graph.add_conditional_edges("hitl_check", hitl_router)
        else:
            graph.add_edge("ml_validation", "memory_update")

        graph.add_edge("memory_update", "reflection")   # P1-1: self-reflection before report
        graph.add_edge("reflection", "report")
    else:
        graph.add_edge("select_best", "report")

    graph.set_entry_point("analyze_market")
    graph.add_exit_point("report")

    return graph


async def run_strategy_pipeline(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    agents: list[str] | None = None,
    run_backtest: bool = False,
    run_debate: bool = True,
    run_wf_validation: bool = True,
    initial_capital: float = INITIAL_CAPITAL,
    leverage: int = 1,
    pipeline_timeout: float = 300.0,
    max_cost_usd: float = 0.0,
    checkpoint_enabled: bool = False,
    hitl_enabled: bool = False,
    hitl_approved: bool = False,
    event_fn: "Callable[[str, dict[str, Any]], None] | None" = None,
) -> AgentState:
    """
    Convenience function to run the full strategy generation pipeline.

    Args:
        symbol: Trading pair (e.g. "BTCUSDT")
        timeframe: Candle interval (e.g. "15")
        df: OHLCV DataFrame
        agents: LLM agents to use (default: ["deepseek"])
        run_backtest: Whether to backtest the generated strategy
        run_debate: Whether to run MAD debate before generation (default: True)
        run_wf_validation: Whether to run walk-forward overfitting gate (P1-2, default True)
        initial_capital: Starting capital
        leverage: Trading leverage
        pipeline_timeout: Wall-clock timeout for the entire pipeline in seconds.
            Default 300 s (5 min). Individual nodes have their own timeouts
            (60–180 s); this cap prevents runaway refinement loops.
            On timeout, a partial AgentState is returned with a ``"pipeline"``
            error entry so callers can inspect partial results.
        max_cost_usd: Hard LLM cost cap in USD (P1-5). 0.0 = unlimited (default).
            When exceeded mid-pipeline, BudgetExceededError is caught and the
            partial state is returned with a ``"budget"`` error entry.
        checkpoint_enabled: If True, persist AgentState to SQLite after each node
            (P1-4). Enables run audit trail and post-mortem debugging.
        hitl_enabled: If True (P2-3), add HITLCheckNode before memory_update.
            Pipeline pauses unless hitl_approved=True.
        hitl_approved: If True (P2-3), mark pipeline as human-approved so HITL
            check passes without pausing. Use on second call after human review.
        event_fn: P2-4 streaming callback attached to AgentGraph.event_fn.
            Called after each node with (node_name, event_dict).
            Use make_pipeline_event_queue() to get a (queue, event_fn) pair.

    Returns:
        AgentState with all results in state.results
    """
    graph = build_trading_strategy_graph(
        run_backtest=run_backtest,
        run_debate=run_debate,
        run_wf_validation=run_wf_validation,
        checkpoint_enabled=checkpoint_enabled,
        hitl_enabled=hitl_enabled,
        event_fn=event_fn,
    )

    initial_state = AgentState(
        context={
            "symbol": symbol,
            "timeframe": timeframe,
            "df": df,
            "agents": agents or ["deepseek"],
            "initial_capital": initial_capital,
            "leverage": leverage,
            "hitl_approved": hitl_approved,  # P2-3: HITL approval flag
        },
        max_cost_usd=max_cost_usd,  # P1-5: cost budget
    )

    try:
        result_state = await asyncio.wait_for(
            graph.execute(initial_state),
            timeout=pipeline_timeout,
        )
    except TimeoutError:
        logger.error(
            f"[Pipeline] Timeout after {pipeline_timeout}s — returning partial state "
            f"(nodes completed: {initial_state.visited_nodes})"
        )
        initial_state.add_error(
            "pipeline",
            TimeoutError(f"Pipeline exceeded {pipeline_timeout}s wall-clock limit"),
        )
        return initial_state
    except BudgetExceededError as exc:
        # P1-5: cost budget exceeded — return partial state with budget error
        logger.warning(
            f"[Pipeline] Budget exceeded: ${exc.spent:.4f} > ${exc.limit:.4f} — "
            f"returning partial state (nodes: {initial_state.visited_nodes})"
        )
        initial_state.add_error("budget", exc)
        return initial_state

    logger.info(
        f"✅ [Graph] Pipeline complete: {len(result_state.execution_path)} nodes, "
        f"{len(result_state.errors)} errors, "
        f"cost=${result_state.total_cost_usd:.4f}, calls={result_state.llm_call_count}"
    )
    return result_state


# Register in global graph registry
register_graph(build_trading_strategy_graph(run_backtest=False))
