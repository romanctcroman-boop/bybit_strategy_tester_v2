"""
Trading Strategy LangGraph Pipeline.

Builds an AgentGraph that implements the full AI strategy generation cycle:

    analyze_market ──► regime_classifier ──► memory_recall ──► generate_strategies ──► parse_responses
                                                                                                  │
                                                                                            select_best
                                                                                                  │
                                                                                            build_graph
                                                                                                  │
                                                                                             backtest
                                                                                                  │
                                                                                  backtest_analysis ──► refine_strategy ──┐
                                                                                                  │                       │
                                                                                  (passes/max iter)            (back to generate)
                                                                                                  │
                                                                                        optimize_strategy
                                                                                                  │
                                                                                      [wf_validation]  (optional, run_wf_validation=True)
                                                                                                  │
                                                                                         ml_validation
                                                                                                  │
                                                                                    [hitl]  (optional, hitl_enabled=True)
                                                                                                  │
                                                                                        memory_update ──► reflection ──► report ──► END

Uses StrategyController components but in a graph-based execution model
for better observability, retry logic, and conditional routing.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
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

# SQLite DB used by all three memory nodes so memories survive across runs
_PIPELINE_MEMORY_DB: str = "data/pipeline_strategy_memory.db"

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

    _ADX_TREND_THRESHOLD = 20.0  # above → trending
    _ATR_HIGH_THRESHOLD = 2.5  # % → high volatility
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
        adx_proxy = strength_map.get(trend_strength)
        if adx_proxy is None:
            logger.warning(f"[RegimeClassifier] Unknown trend_strength '{trend_strength}' — defaulting to weak (10.0)")
            adx_proxy = 10.0

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
    MIN_WIN_IMPORTANCE = 0.35  # importance ≥ 0.35 = optimized Sharpe ≥ 0.4 (was 0.5 → Sharpe > 1, too strict)
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
            from backend.agents.memory.backend_interface import SQLiteBackendAdapter
            from backend.agents.memory.hierarchical_memory import HierarchicalMemory

            memory = HierarchicalMemory(backend=SQLiteBackendAdapter(db_path=_PIPELINE_MEMORY_DB))
            # Event loop is already running inside execute() → must async_load explicitly
            loaded_count = await memory.async_load()
            logger.debug(f"[MemoryRecallNode] async_load loaded {loaded_count} memories from SQLite")

            # SELF-RAG: skip all recall queries if memory is empty
            if loaded_count == 0:
                logger.debug("[MemoryRecallNode] Memory is empty — skipping recall queries")
                wins, failures, regime_memories = [], [], []
            else:
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

                # Deduplicate across all 3 lists by item id: the same memory can
                # score high in multiple queries, inflating the LLM context block.
                _seen_ids: set[str] = set()

                def _dedup(items: list) -> list:
                    result = []
                    for m in items:
                        mid = str(getattr(m, "id", id(m)))
                        if mid not in _seen_ids:
                            _seen_ids.add(mid)
                            result.append(m)
                    return result

                wins = _dedup(wins)
                failures = _dedup(failures)
                regime_memories = _dedup(regime_memories)

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
                few_shot_examples.append(f"EXAMPLE (Sharpe={sharpe}, agent={agent}): {snippet}")

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


# Module-level TTL cache for GroundingNode: (symbol, timeframe) → (grounding_context, timestamp)
_GROUNDING_CACHE: dict[tuple[str, str], tuple[str, float]] = {}
_GROUNDING_CACHE_TTL = 900.0  # 15 minutes


class GroundingNode(AgentNode):
    """
    Grounding Node: Perplexity sonar-pro provides real-time market context.

    Fetches current price levels, recent news, sentiment and key technical levels
    for the target symbol. This grounds strategy generation in current reality,
    not just historical patterns — reducing hallucinated price levels.

    Runs after MemoryRecallNode, before GenerateStrategiesNode.
    Skips gracefully if PERPLEXITY_API_KEY is not configured.
    """

    def __init__(self) -> None:
        super().__init__(
            name="grounding",
            description="Fetch real-time market context via Perplexity sonar-pro",
            timeout=20.0,
            retry_count=1,
            retry_delay=2.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        from backend.security.key_manager import get_key_manager

        symbol = state.context.get("symbol", "BTCUSDT")
        timeframe = state.context.get("timeframe", "15")
        clf = state.context.get("regime_classification", {})
        _am = state.get_result("analyze_market") or {}
        regime = clf.get("regime") or _am.get("regime", "unknown")

        km = get_key_manager()
        api_key = km.get_decrypted_key("PERPLEXITY_API_KEY")
        if not api_key:
            logger.info("[Grounding] PERPLEXITY_API_KEY not set — skipping grounding")
            state.set_result(self.name, {"grounding_context": "", "skipped": True})
            return state

        # TTL cache check — avoid repeated Perplexity calls for same symbol+timeframe
        cache_key = (symbol, timeframe)
        cached = _GROUNDING_CACHE.get(cache_key)
        if cached is not None:
            cached_text, cached_at = cached
            if time.time() - cached_at < _GROUNDING_CACHE_TTL:
                logger.info(
                    f"[Grounding] Cache hit for {symbol}/{timeframe}tf "
                    f"(age {int(time.time() - cached_at)}s < {int(_GROUNDING_CACHE_TTL)}s) — skipping API call"
                )
                state.set_result(self.name, {"grounding_context": cached_text, "skipped": False, "cached": True})
                state.context["grounding_context"] = cached_text
                return state

        query = (
            f"{symbol} cryptocurrency current price, key support and resistance levels, "
            f"recent significant news or events, market sentiment, {timeframe}min timeframe. "
            f"Current detected regime: {regime}. "
            f"Provide specific price levels and actionable context for a trading strategy."
        )

        # Escalate to sonar-reasoning-pro for regimes that need deeper CoT analysis
        deep_analysis = regime in ("unknown", "extreme_volatile")

        try:
            grounding_text = await self._call_llm(
                "perplexity",
                query,
                system_msg="Provide concise factual market data with specific price levels and sources.",
                state=state,
                deep_analysis=deep_analysis,
            )

            grounding_context = f"## Real-Time Market Grounding ({symbol})\n{grounding_text or ''}\n"
            # Store in TTL cache
            _GROUNDING_CACHE[cache_key] = (grounding_context, time.time())
            state.set_result(self.name, {"grounding_context": grounding_context, "skipped": False, "cached": False})
            # Inject into state context so GenerateStrategiesNode can read it
            state.context["grounding_context"] = grounding_context
            logger.info(f"[Grounding] {symbol} real-time context fetched ({len(grounding_context)} chars)")
        except Exception as e:
            logger.warning(f"[Grounding] Perplexity call failed: {e} — continuing without grounding")
            state.set_result(self.name, {"grounding_context": "", "error": str(e)})

        return state

    async def _call_llm(
        self,
        agent_name: str,
        query: str,
        system_msg: str,
        state: AgentState | None = None,
        **kwargs: Any,
    ) -> str | None:
        """Minimal _call_llm for GroundingNode — Perplexity only.

        Model routing:
          sonar-pro             — standard queries (default)
          sonar-reasoning-pro   — deep CoT analysis for extreme/unknown regimes
                                  (escalated via kwargs["deep_analysis"]=True)
        Search quality defaults: search_context_size="medium", CRYPTO_SEARCH_DOMAINS filter.
        """
        from backend.agents.llm.base_client import (
            LLMClientFactory,
            LLMConfig,
            LLMMessage,
            LLMProvider,
        )
        from backend.agents.llm.clients.perplexity import CRYPTO_SEARCH_DOMAINS
        from backend.security.key_manager import get_key_manager

        km = get_key_manager()
        api_key = km.get_decrypted_key("PERPLEXITY_API_KEY")
        if not api_key:
            return None

        deep_analysis = kwargs.pop("deep_analysis", False)
        model = "sonar-reasoning-pro" if deep_analysis else "sonar-pro"
        config = LLMConfig(
            provider=LLMProvider.PERPLEXITY,
            api_key=api_key,
            model=model,
            temperature=0.3,
            max_tokens=1024,
        )
        client = LLMClientFactory.create(config)
        try:
            messages = [
                LLMMessage(role="system", content=system_msg),
                LLMMessage(role="user", content=query),
            ]
            response = await client.chat(
                messages,
                search_context_size="medium",
                search_domain_filter=CRYPTO_SEARCH_DOMAINS,
            )
            if state is not None:
                state.record_llm_cost(response.estimated_cost)
            return response.content
        finally:
            await client.close()


class GenerateStrategiesNode(AgentNode):
    """
    Node 2: Generate strategy proposals from LLM agents.

    Claude Sonnet is used for standard strategy generation; Opus is escalated
    for novel/unknown regimes or when force_escalate is set in context.
    Perplexity real-time grounding context is injected by GroundingNode upstream.
    """

    # Kept for backward compatibility with existing tests that reference this attribute
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
        # seed_mode: existing strategy graph provided — skip LLM generation
        if state.context.get("seed_mode"):
            logger.info("[GenerateStrategies] seed_mode — skipping LLM generation")
            state.set_result(self.name, {"responses": [], "seed_mode": True})
            return state

        market_result = state.get_result("analyze_market")
        if not market_result:
            state.add_error(self.name, ValueError("No market analysis result"))
            return state

        market_context = market_result["market_context"]
        agents: list[str] = state.context.get("agents", ["claude"])
        if not agents:
            state.add_error(self.name, ValueError("agents list is empty — cannot generate strategies"))
            return state
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
                "Use them as inspiration — adapt, don't copy verbatim:\n\n" + "\n\n".join(few_shot_examples) + "\n"
            )
            logger.info(f"🎯 [GenerateStrategies] Injecting {len(few_shot_examples)} few-shot examples")

        # --- Phase 4: Optimizer analysis feedback (AnalysisDebateNode consensus) ---
        # Inject post-optimization insights so the next generation iteration can
        # learn from which param regions / designs produced positive Sharpe.
        optimizer_analysis = state.context.get("optimizer_analysis")
        optimizer_insights_block = ""
        if optimizer_analysis and optimizer_analysis.get("consensus"):
            n_pos = optimizer_analysis.get("n_positive_sharpe", 0)
            n_trials = optimizer_analysis.get("n_trials", 0)
            best_sh = optimizer_analysis.get("best_sharpe", 0.0)
            optimizer_insights_block = (
                "## Optimizer Evidence (previous run)\n"
                f"Ran {n_trials} optimizer trials — {n_pos} had positive Sharpe "
                f"(best Sharpe={best_sh:.3f}).\n"
                f"Agent analysis consensus:\n{optimizer_analysis['consensus']}\n\n"
                "IMPORTANT: Use these insights to design a better strategy. "
                "Avoid parameter regions that the optimizer identified as consistently negative.\n"
            )
            logger.info(
                f"📊 [GenerateStrategies] Injecting optimizer insights "
                f"(n_pos={n_pos}/{n_trials}, best_sharpe={best_sh:.2f})"
            )

        responses: list[dict[str, Any]] = []
        failed_agents: list[str] = []

        # --- Strategy generation: A2A parallel (Claude Sonnet + Perplexity market validation) ---
        # Claude Sonnet generates the StrategyDefinition JSON.
        # Perplexity validates current market conditions for the symbol.
        # Claude Haiku synthesizes both into the final strategy.
        # Fallback chain: if Perplexity unavailable → single Claude; if Haiku fails → use Claude directly.

        clf = state.context.get("regime_classification", {})
        _am = state.get_result("analyze_market") or {}
        regime = clf.get("regime") or _am.get("regime", "unknown")
        is_novel_regime = regime in ("unknown", "extreme_volatile") or state.context.get("force_escalate")
        agent_name = "claude-opus" if is_novel_regime else "claude-sonnet"

        # Read grounding context injected by GroundingNode (if present)
        grounding_context = state.context.get("grounding_context", "")
        if grounding_context:
            market_context_text = getattr(market_context, "summary", str(market_context))
            state.context["_enriched_market_context"] = f"{grounding_context}\n\n{market_context_text}"

        # Build Claude strategy prompt (unchanged from before)
        prompt = self._prompt_engineer.create_strategy_prompt(
            context=market_context,
            platform_config=platform_config,
            agent_name=agent_name,
            include_examples=True,
        )
        if grounding_context:
            prompt = f"{grounding_context}\n\n{prompt}"
        if few_shot_block:
            prompt = f"{few_shot_block}\n\n{prompt}"
        if memory_context:
            prompt = f"{memory_context}\n\n{prompt}"
        if optimizer_insights_block:
            prompt = f"{prompt}\n\n{optimizer_insights_block}"
        if refinement_feedback:
            prompt = f"{prompt}\n\n{refinement_feedback}"
        system_msg = self._prompt_engineer.get_system_message(agent_name)

        if is_novel_regime:
            logger.info(f"[GenerateStrategy] A2A — escalating to Opus (regime={regime})")
        else:
            logger.info(f"[GenerateStrategy] A2A — Claude Sonnet + Perplexity (regime={regime})")

        # ── Parallel A2A calls ────────────────────────────────────────────────
        symbol: str = state.context.get("symbol", "")
        timeframe: str = state.context.get("timeframe", "15")
        perplexity_prompt = self._build_perplexity_market_prompt(symbol, timeframe, regime, market_context)

        claude_response: str | None = None
        perplexity_response: str | None = None

        async def _call_claude() -> str | None:
            try:
                return await self._call_llm(agent_name, prompt, system_msg, state=state)
            except Exception as exc:
                logger.error(f"[GenerateStrategy] Claude call failed: {exc}")
                return None

        async def _call_perplexity() -> str | None:
            try:
                return await self._call_llm(
                    "perplexity",
                    perplexity_prompt,
                    "You are a financial market analyst. Provide a concise, factual market analysis.",
                    temperature=0.3,
                    state=state,
                )
            except Exception as exc:
                logger.debug(f"[GenerateStrategy] Perplexity call failed (non-fatal): {exc}")
                return None

        # Check if Perplexity key is available AND perplexity is in the requested agents list
        from backend.security.key_manager import get_key_manager as _get_km

        _has_perplexity = bool(_get_km().get_decrypted_key("PERPLEXITY_API_KEY")) and "perplexity" in agents

        if _has_perplexity:
            logger.info("[GenerateStrategy] Running Claude + Perplexity in parallel")
            claude_response, perplexity_response = await asyncio.gather(_call_claude(), _call_perplexity())
        else:
            logger.info("[GenerateStrategy] No Perplexity key — single Claude call")
            claude_response = await _call_claude()

        # ── Synthesis ─────────────────────────────────────────────────────────
        final_response: str | None = None
        synthesis_used = False

        if claude_response and perplexity_response:
            logger.info("[GenerateStrategy] Synthesising Claude strategy + Perplexity market insight via Haiku")
            synthesized = await self._synthesis_critic(
                [claude_response],
                market_context,
                state=state,
                perplexity_market_analysis=perplexity_response,
            )
            if synthesized:
                final_response = synthesized
                synthesis_used = True
                logger.info("[GenerateStrategy] A2A synthesis succeeded")
            else:
                # Synthesis failed → fall through to raw Claude response
                logger.warning("[GenerateStrategy] Synthesis failed — using raw Claude response")
                final_response = claude_response
        elif claude_response:
            final_response = claude_response
        else:
            failed_agents.append("claude")

        if final_response:
            source = "claude+perplexity" if synthesis_used else "claude"
            responses.append({"agent": source, "response": final_response})
            logger.info(f"[GenerateStrategy] Generation complete (source={source})")

        if failed_agents:
            state.context["partial_generation"] = True
            state.context["failed_agents"] = failed_agents
            logger.warning(f"[Graph] Partial generation: {len(failed_agents)} agent(s) failed: {failed_agents}")

        state.set_result(self.name, {"responses": responses})
        state.add_message(
            "system",
            f"Generated {len(responses)} responses (A2A: Claude Sonnet/Opus + Perplexity)",
            self.name,
        )
        return state

    def _build_perplexity_market_prompt(
        self,
        symbol: str,
        timeframe: str,
        regime: str,
        market_context: Any,
    ) -> str:
        """Build a concise market research prompt for Perplexity.

        Perplexity's role: validate / enrich the market context with real-time data.
        We do NOT ask it to generate a strategy JSON — that's Claude's job.
        """
        tf_label = f"{timeframe}m" if timeframe.isdigit() else timeframe
        context_summary = getattr(market_context, "summary", "")[:300] if market_context else ""
        return (
            f"Provide a brief technical market analysis for {symbol} ({tf_label} timeframe).\n\n"
            f"Current regime (from local indicators): {regime}\n"
            f"{('Local context: ' + context_summary) if context_summary else ''}\n\n"
            "Answer these questions concisely (3-5 sentences total):\n"
            "1. Is the current regime confirmed by recent price action?\n"
            "2. What are the key support/resistance levels or price zones to watch?\n"
            "3. Any recent news or macro events that could affect this asset?\n"
            "4. What technical approach (trend-following, mean-reversion, breakout) "
            "fits the current conditions?\n\n"
            "Be factual and concise. No trading advice — this is for strategy parameter tuning."
        )

    async def _synthesis_critic(
        self,
        moa_texts: list[str],
        market_context: Any,
        state: AgentState | None = None,
        perplexity_market_analysis: str | None = None,
    ) -> str | None:
        """Claude Haiku synthesis critic.

        When ``perplexity_market_analysis`` is provided (A2A mode), the prompt
        instructs Haiku to incorporate the real-time market insight into the
        strategy — e.g. adjusting parameters for current volatility / regime.
        Falls back to the legacy multi-variant merge when called without it.
        """
        variants_block = "\n\n".join(f"--- VARIANT {i + 1} ---\n{text}" for i, text in enumerate(moa_texts))

        if perplexity_market_analysis:
            # A2A synthesis: Claude strategy + Perplexity market insight → final strategy
            critic_prompt = (
                "You are a precision trading strategy synthesiser.\n\n"
                "## Claude's strategy proposal\n"
                f"{variants_block}\n\n"
                "## Real-time market analysis (from Perplexity)\n"
                f"{perplexity_market_analysis}\n\n"
                "Your task:\n"
                "1. Keep Claude's strategy structure and JSON format intact\n"
                "2. Adjust parameters, filters, or conditions where the market analysis "
                "suggests a better fit (e.g. wider stops in volatile conditions, "
                "shorter periods in ranging markets)\n"
                "3. Do NOT change the fundamental strategy logic — only tune it\n"
                "4. Output the SAME structured JSON format as Claude's proposal\n\n"
                "Output only the final strategy JSON, no explanation."
            )
        else:
            # Legacy multi-variant merge (backward compatibility)
            critic_prompt = (
                "You are a quantitative trading strategy critic.\n\n"
                "Below are multiple strategy proposals for the same market context.\n\n"
                f"{variants_block}\n\n"
                "Your task:\n"
                "1. Identify the strongest elements from each variant\n"
                "2. Synthesise ONE final strategy that combines the best ideas\n"
                "3. Ensure the strategy is concrete, implementable, and risk-controlled\n"
                "4. Output in the SAME structured JSON format as the variants\n\n"
                "Output only the synthesised strategy JSON, no explanation."
            )

        system_msg = "You are a precision strategy synthesiser. Output valid JSON only."
        try:
            result = await self._call_llm("claude-haiku", critic_prompt, system_msg, temperature=0.3, state=state)
            if result:
                logger.debug("Claude Haiku synthesis critic succeeded")
                return result
        except Exception as e:
            logger.debug(f"Claude Haiku synthesis critic failed: {e}")
        return None

    async def _call_llm(
        self,
        agent_name: str,
        prompt: str,
        system_msg: str,
        temperature: float | None = None,
        state: AgentState | None = None,
        json_mode: bool = False,
    ) -> str | None:
        """Call LLM using the connections module (temperature override supported).

        Args:
            state:     If provided, LLM cost and call count are recorded on the state
                       for pipeline-level observability via ``state.total_cost_usd``.
            json_mode: If True, passes ``response_format={"type":"json_object"}`` to
                       OpenAI-compatible providers (deepseek, qwen).  The system_msg
                       MUST contain the word "JSON" (API requirement).  Eliminates
                       regex-based extraction in ResponseParser.  Not set for
                       Perplexity (unsupported by sonar-pro model).
        """
        from backend.agents.llm.base_client import (
            LLMClientFactory,
            LLMConfig,
            LLMMessage,
            LLMProvider,
        )
        from backend.agents.llm.model_router import ModelRouter
        from backend.security.key_manager import get_key_manager

        km = get_key_manager()

        # Map task/agent names to Claude model tiers + Perplexity
        # Legacy agent names (deepseek, qwen) are silently routed to Claude equivalents
        _AGENT_TO_CLAUDE_MODEL = {
            "claude-haiku": "claude-haiku-4-5-20251001",
            "claude-sonnet": "claude-sonnet-4-6",
            "claude-opus": "claude-opus-4-6",
            # Legacy aliases → Claude equivalents
            "claude": "claude-haiku-4-5-20251001",
            "deepseek": "claude-sonnet-4-6",  # was main generator → Sonnet
            "qwen": "claude-haiku-4-5-20251001",  # was critic → Haiku
        }

        # Perplexity stays as-is (real-time grounding only)
        if agent_name == "perplexity":
            provider = LLMProvider.PERPLEXITY
            key_name = "PERPLEXITY_API_KEY"
            model = "sonar-pro"
            default_temp = 0.7
        elif agent_name in _AGENT_TO_CLAUDE_MODEL:
            provider = LLMProvider.ANTHROPIC
            key_name = "ANTHROPIC_API_KEY"
            model = _AGENT_TO_CLAUDE_MODEL[agent_name]
            default_temp = 0.7
        else:
            # Unknown agent → try as Claude model name directly
            provider = LLMProvider.ANTHROPIC
            key_name = "ANTHROPIC_API_KEY"
            model = ModelRouter.get_model(agent_name)
            default_temp = 0.7

        api_key = km.get_decrypted_key(key_name)
        if not api_key:
            return None

        effective_temp = temperature if temperature is not None else default_temp
        # Claude Sonnet/Opus support up to 64K output tokens; 8192 gives room for
        # large strategy JSONs without truncation (Haiku stays at 4096 — smaller role)
        _is_large_claude = provider == LLMProvider.ANTHROPIC and "haiku" not in model.lower()
        max_tokens = 8192 if _is_large_claude else 4096
        config = LLMConfig(
            provider=provider,
            api_key=api_key,
            model=model,
            temperature=effective_temp,
            max_tokens=max_tokens,
        )
        client = LLMClientFactory.create(config)
        # Claude handles json_mode via prompt engineering (no response_format field)
        # Perplexity does not support json_mode at all
        _supports_json_mode = False  # Claude: handled internally; Perplexity: unsupported
        try:
            messages = [
                LLMMessage(role="system", content=system_msg),
                LLMMessage(role="user", content=prompt),
            ]
            response = await client.chat(
                messages,
                json_mode=(json_mode and _supports_json_mode),
            )
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
        # seed_mode: skip parse — no LLM responses to parse
        if state.context.get("seed_mode"):
            logger.info("[ParseResponses] seed_mode — skipping parse")
            state.set_result(self.name, {"proposals": [], "seed_mode": True})
            return state

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
        # seed_mode: create a synthetic select_best result from the seeded strategy_graph
        if state.context.get("seed_mode"):
            seed_name = state.context.get("seed_strategy_name", "Existing Strategy")
            logger.info(f"[ConsensusNode] seed_mode — using seeded graph '{seed_name}'")
            state.set_result(
                self.name,
                {
                    "selected_strategy": {"name": seed_name, "seed_mode": True},
                    "selected_agent": "seed",
                    "candidates_count": 1,
                    "agreement_score": 1.0,
                    "seed_mode": True,
                },
            )
            state.context["selected_strategy"] = {"name": seed_name, "seed_mode": True}
            return state

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

        # seed_mode: strategy_graph already in context — skip LLM conversion
        if state.context.get("seed_mode"):
            graph = state.context.get("strategy_graph")
            if graph:
                logger.info("[BuildGraphNode] seed_mode — using existing strategy_graph")
                state.set_result(
                    self.name,
                    {
                        "blocks": len(graph.get("blocks", [])),
                        "connections": len(graph.get("connections", [])),
                        "warnings": [],
                        "seed_mode": True,
                    },
                )
            return state

        select_result = state.get_result("select_best")
        if not select_result:
            logger.debug("[BuildGraphNode] No select_best result — skipping graph conversion")
            return state

        strategy = select_result.get("selected_strategy")
        if strategy is None:
            return state

        timeframe = state.context.get("timeframe", "15")

        # Log the StrategyDefinition for debugging signal/filter counts
        n_signals = len(strategy.signals) if hasattr(strategy, "signals") else 0
        n_filters = len(strategy.filters) if hasattr(strategy, "filters") else 0
        sig_types = [s.type for s in strategy.signals] if hasattr(strategy, "signals") else []
        logger.info(
            f"[BuildGraphNode] Converting '{getattr(strategy, 'strategy_name', '?')}': "
            f"{n_signals} signals={sig_types}, {n_filters} filters"
        )

        try:
            converter = StrategyDefToGraphConverter()
            graph, warnings = converter.convert(strategy, interval=timeframe)

            # Count non-strategy indicator blocks
            indicator_blocks = [b for b in graph.get("blocks", []) if b.get("type") != "strategy"]
            skipped_warnings = [w for w in warnings if "skipped" in w.lower()]
            if skipped_warnings:
                logger.warning(f"[BuildGraphNode] Signals dropped during conversion: {skipped_warnings}")

            # Hard guard: if graph has 0 indicator blocks, it will overtrade or do nothing
            if len(indicator_blocks) == 0:
                msg = (
                    f"Graph conversion produced 0 indicator blocks "
                    f"(strategy_name='{getattr(strategy, 'strategy_name', '?')}', "
                    f"signals={sig_types}, skipped={skipped_warnings}). "
                    f"All signals were unrecognised or filtered out."
                )
                logger.error(f"[BuildGraphNode] {msg}")
                state.add_error(self.name, ValueError(msg))
                state.context["strategy_graph"] = None
                state.context["graph_warnings"] = [*warnings, msg]
                return state

            # Soft guard: if >50% of original signals+filters were dropped, refinement is needed.
            # A strategy missing most of its logic cannot validate the LLM's hypothesis.
            n_original = n_signals + n_filters
            n_dropped = len(skipped_warnings)
            if n_original > 1 and n_dropped > n_original // 2:
                msg = (
                    f"Graph conversion dropped {n_dropped}/{n_original} signals/filters "
                    f"({skipped_warnings}). Only {len(indicator_blocks)} indicator block(s) remain. "
                    f"Regenerate with ONLY supported types: "
                    f"RSI, MACD, EMA_Crossover, SMA_Crossover, EMA, SMA, Bollinger, SuperTrend, "
                    f"Stochastic, CCI, ATR, ADX, Williams_R, VWAP, OBV. "
                    f"Filters: Volatility, Volume, Trend, ADX."
                )
                logger.warning(f"[BuildGraphNode] {msg}")
                state.add_error(self.name, ValueError(msg))
                state.context["strategy_graph"] = None
                state.context["graph_warnings"] = [*warnings, msg]
                return state

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
                {
                    "blocks": len(graph["blocks"]),
                    "connections": len(graph["connections"]),
                    "indicator_blocks": len(indicator_blocks),
                    "warnings": warnings,
                },
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
        df = state.context.get("df")
        symbol = state.context.get("symbol", "BTCUSDT")
        timeframe = state.context.get("timeframe", "15")
        strategy_graph = state.context.get("strategy_graph")

        # seed_mode: run directly via adapter — no LLM-generated select_best needed
        if state.context.get("seed_mode"):
            if not strategy_graph:
                state.add_error(self.name, ValueError("seed_mode but no strategy_graph in context"))
                return state
            logger.info(f"[BacktestNode] seed_mode — backtesting '{state.context.get('seed_strategy_name')}'")
        else:
            select_result = state.get_result("select_best")
            if not select_result:
                state.add_error(self.name, ValueError("No selected strategy"))
                return state

        # Prefer StrategyBuilderAdapter path (full 40+ block universe)
        engine_warnings: list[str] = []
        sample_trades: list[dict] = []
        sig_long_count: int = -1
        sig_short_count: int = -1
        if strategy_graph is not None:
            run_data = await self._run_via_adapter(strategy_graph, df, symbol, timeframe, state)
            metrics = run_data.get("metrics", {})
            engine_warnings = run_data.get("engine_warnings", [])
            sample_trades = run_data.get("sample_trades", [])
            sig_long_count = run_data.get("signal_long_count", -1)
            sig_short_count = run_data.get("signal_short_count", -1)
        else:
            # Fallback: legacy BacktestBridge (6 strategy types only)
            logger.debug("[BacktestNode] No strategy_graph — using BacktestBridge fallback")
            from backend.agents.integration.backtest_bridge import BacktestBridge

            bridge = BacktestBridge()
            # strategy is only available in non-seed_mode (select_result was retrieved above)
            bridge_strategy = (state.get_result("select_best") or {}).get("selected_strategy")
            metrics = await bridge.run_strategy(
                strategy=bridge_strategy,
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
                "signal_long_count": sig_long_count,
                "signal_short_count": sig_short_count,
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
            strategy_type = getattr(bridge_strategy, "strategy_type", "unknown")
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
            from datetime import UTC

            adapter = StrategyBuilderAdapter(strategy_graph)
            signal_result = adapter.generate_signals(df)

            # Capture raw signal counts before the engine runs — used by
            # BacktestAnalysisNode and RefinementNode for better diagnostics.
            _sig_long = int(signal_result.entries.sum()) if signal_result.entries is not None else 0
            _sig_short = int(signal_result.short_entries.sum()) if signal_result.short_entries is not None else 0

            # Derive start/end dates from the OHLCV DataFrame index
            # (BacktestConfig requires interval, start_date, end_date as mandatory fields)
            df_start = df.index[0]
            df_end = df.index[-1]
            if hasattr(df_start, "to_pydatetime"):
                df_start = df_start.to_pydatetime()
            if hasattr(df_end, "to_pydatetime"):
                df_end = df_end.to_pydatetime()
            # Ensure timezone-aware datetimes
            if df_start.tzinfo is None:
                df_start = df_start.replace(tzinfo=UTC)
            if df_end.tzinfo is None:
                df_end = df_end.replace(tzinfo=UTC)

            # Extract SL/TP from StrategyDefinition so positions actually close.
            # Without SL/TP and no exit signals, positions stay open → total_trades=0.
            _sl: float = 0.02  # default 2%
            _tp: float = 0.03  # default 3%
            _selected = (state.get_result("select_best") or {}).get("selected_strategy")
            if _selected is not None and not isinstance(_selected, dict):
                try:
                    ec = getattr(_selected, "exit_conditions", None)
                    if ec:
                        if getattr(ec, "stop_loss", None):
                            v = float(ec.stop_loss.value)
                            _sl = v / 100 if v > 1 else v
                        if getattr(ec, "take_profit", None):
                            v = float(ec.take_profit.value)
                            _tp = v / 100 if v > 1 else v
                except Exception:
                    pass
            # Clamp to realistic intraday ranges (15m–1h strategies):
            # SL > 7% means BTC must move $7k+ before stopping out → position held forever.
            # TP > 15% means BTC must move $15k+ → equally unrealistic for short-term.
            # These caps protect against LLM hallucinating values like SL=20%, TP=90%.
            _sl = max(0.005, min(_sl, 0.07))
            _tp = max(0.005, min(_tp, 0.15))
            # Enforce TP ≥ SL: inverted R:R (TP < SL) requires >67% win rate just to break even —
            # most LLM-generated strategies can't sustain that. Fall back to TP = SL * 1.5.
            if _tp < _sl:
                logger.warning(f"[BacktestNode] Inverted R:R: TP={_tp:.3f} < SL={_sl:.3f} — correcting TP to SL*1.5")
                _tp = min(_sl * 1.5, 0.15)
            logger.info(f"[BacktestNode] SL={_sl:.4f} ({_sl * 100:.2f}%)  TP={_tp:.4f} ({_tp * 100:.2f}%)")
            # Store for OptimizationNode so it uses the same SL/TP in Numba trials
            state.context["backtest_sl"] = _sl
            state.context["backtest_tp"] = _tp

            cfg = BacktestConfig(
                symbol=symbol,
                interval=timeframe,  # BacktestConfig field is 'interval', not 'timeframe'
                start_date=df_start,
                end_date=df_end,
                initial_capital=state.context.get("initial_capital", INITIAL_CAPITAL),
                leverage=state.context.get("leverage", 1),
                direction="both",
                commission_value=COMMISSION_TV,
                stop_loss=_sl,
                take_profit=_tp,
            )

            from backend.backtesting.engine import BacktestEngine
            from backend.backtesting.strategies import BaseStrategy

            # Wrap the pre-computed SignalResult so BacktestEngine can consume it
            # via the `custom_strategy` parameter (signature: run(config, ohlcv, ..., custom_strategy))
            _precomputed = signal_result

            class _PrecomputedStrategy(BaseStrategy):
                """Thin wrapper that returns already-generated signals to BacktestEngine."""

                def _validate_params(self) -> None:
                    pass

                def generate_signals(self, ohlcv):
                    return _precomputed

            engine = BacktestEngine()
            result = engine.run(
                config=cfg,
                ohlcv=df,
                custom_strategy=_PrecomputedStrategy(),
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
            open_count = metrics.get("open_trades", 0)
            # effective count: closed + end-of-backtest positions (is_open=True, TV parity)
            effective_count = trades_count + open_count
            if effective_count == 0:
                engine_warnings.append(
                    "[NO_TRADES] Signals were generated but no trades executed. "
                    "Check that port names are correct (use 'long'/'short', not 'signal'/'output') "
                    "and that SL/TP values are realistic."
                )
            # Only fire DIRECTION_MISMATCH when the SIGNALS themselves are one-directional.
            # If signals exist in both directions (e.g. 28 long + 18 short) but trades end up
            # one-directional due to clustering / pyramiding-1 blocking, that is NOT a mismatch
            # — firing this warning causes the LLM to add restrictive AND gates trying to "fix"
            # something that isn't broken, which reduces signals to zero on the next iteration.
            elif _sig_long == 0 and _sig_short > 0:
                engine_warnings.append(
                    "[DIRECTION_MISMATCH] Strategy generates only SHORT signals but direction='both'. "
                    "Ensure 'long' port is connected to entry_long on the strategy node."
                )
            elif _sig_short == 0 and _sig_long > 0:
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
                    with contextlib.suppress(Exception):
                        sample_trades.append(t.model_dump())
                elif hasattr(t, "__dict__"):
                    sample_trades.append({k: v for k, v in t.__dict__.items() if not k.startswith("_")})

            return {
                "metrics": metrics,
                "engine_warnings": engine_warnings,
                "sample_trades": sample_trades,
                "signal_long_count": _sig_long,
                "signal_short_count": _sig_short,
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
        # Raw signal counts from generate_signals (before engine execution)
        sig_long: int = int(backtest_result.get("signal_long_count", -1))
        sig_short: int = int(backtest_result.get("signal_short_count", -1))

        trades: int = int(metrics.get("total_trades", 0))
        # Include open (end-of-backtest) positions in the activity count — a position
        # closed at EOB is counted as is_open=True by the engine (TV parity) and
        # therefore excluded from closed-trade metrics.  For the purpose of deciding
        # whether the strategy generated *any* market activity, count them together.
        open_trades: int = int(metrics.get("open_trades", 0))
        effective_trades: int = trades + open_trades
        sharpe: float = float(metrics.get("sharpe_ratio", -999.0))
        dd: float = float(metrics.get("max_drawdown", 100.0))
        win_rate: float = float(metrics.get("win_rate", 0.0))

        # ── Severity ──────────────────────────────────────────────────────────
        # sharpe > 0: strictly positive required — sharpe=0 means no alpha generated
        # Use effective_trades (closed + open/EOB) for activity check so that
        # a position closed at end-of-backtest (is_open=True, TV parity) is not
        # wrongly treated as "no activity".
        passed = effective_trades >= self.MIN_TRADES and sharpe > 0.0 and dd < self.MAX_DD_PCT

        if passed:
            severity = "pass"
        elif (
            -0.5 < sharpe <= 0
            or (self.MIN_TRADES - 2 <= effective_trades < self.MIN_TRADES)
            or 25.0 <= dd < self.MAX_DD_PCT
        ) and not (sharpe < -0.5 or effective_trades < 3 or dd >= self.MAX_DD_PCT):
            severity = "near_miss"
        elif sharpe < -1.5 or effective_trades == 0 or dd >= 50.0:
            severity = "catastrophic"
        else:
            severity = "moderate"

        # ── Root cause ────────────────────────────────────────────────────────
        warning_str = " ".join(engine_warnings)
        # sparse_signals: AND-gate chaining reduced raw signals to near-zero before
        # the engine even runs.  Check before direction_mismatch so the LLM gets
        # the right corrective feedback (simplify gates, not "add both directions").
        _signals_known = sig_long >= 0 and sig_short >= 0
        if _signals_known and sig_long + sig_short < 10:
            root_cause = "sparse_signals"
        elif "DIRECTION_MISMATCH" in warning_str:
            root_cause = "direction_mismatch"
        elif effective_trades == 0 and not engine_warnings:
            root_cause = "no_signal"
        elif "NO_TRADES" in warning_str:
            root_cause = "signal_connectivity"
        elif trades == 0 and open_trades > 0 and sharpe < 0:
            # Position opened but never hit SL or TP for the entire period →
            # SL/TP too wide (e.g. SL=20%, TP=90% for a 15m BTC strategy).
            root_cause = "sl_tp_too_wide"
        elif effective_trades > 0 and win_rate < 0.05:
            root_cause = "sl_too_tight"
        elif dd >= self.MAX_DD_PCT and effective_trades < self.MIN_TRADES:
            root_cause = "excessive_risk"
        elif effective_trades < self.MIN_TRADES:
            root_cause = "low_activity"
        elif sharpe <= 0:
            root_cause = "poor_risk_reward"
        else:
            root_cause = "unknown"

        # ── Suggestions (root-cause specific) ─────────────────────────────────
        suggestions: list[str] = []
        if root_cause == "sparse_signals":
            _sl = f"{sig_long}" if _signals_known else "?"
            _ss = f"{sig_short}" if _signals_known else "?"
            suggestions.append(
                f"⚠️ CRITICAL: AND-gate filters reduced signals to {_sl} long + {_ss} short "
                f"over the entire 6-month period — far too few to backtest. "
                "AND(gate_A, RSI_cross) = max(RSI_cross_count) which may be 0-2. "
                "Fix: (1) Replace RSI 'cross' mode with 'range' mode. "
                "(2) Remove deeply nested AND gates. "
                "(3) Each indicator in an AND chain must independently produce ≥50 signals "
                "per year. Check each block's signal count before combining."
            )
        elif root_cause == "direction_mismatch":
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
        elif root_cause == "sl_tp_too_wide":
            suggestions.append(
                "Position opened but NEVER closed (held entire 6-month period). "
                "Your SL/TP values are unrealistically large for a 15m strategy. "
                "Use SL=1-3% and TP=2-5% for intraday mean reversion. "
                "Do NOT use SL > 5% or TP > 10% — price must actually reach these levels within 1-5 bars."
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
                "open_trades": open_trades,
                "effective_trades": effective_trades,
                "sharpe_ratio": round(sharpe, 3),
                "max_drawdown": round(dd, 2),
                "win_rate": round(win_rate, 4),
                "signal_long_count": sig_long if _signals_known else None,
                "signal_short_count": sig_short if _signals_known else None,
            },
            "engine_warnings": engine_warnings,
        }

        state.context["backtest_analysis"] = analysis
        state.set_result(self.name, analysis)

        _sig_info = f", signals={sig_long}L+{sig_short}S" if _signals_known else ""
        logger.info(
            f"🔬 [BacktestAnalysisNode] severity={severity}, root_cause={root_cause}, "
            f"trades={trades}+{open_trades}open={effective_trades}eff, sharpe={sharpe:.2f}, dd={dd:.1f}%"
            f"{_sig_info}"
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

        # Prefer optimized Sharpe when WF validation passed — the optimizer found better params.
        # Raw IS Sharpe may be negative while optimized IS Sharpe is strongly positive.
        wf_ctx = state.context.get("wf_validation", {})
        opt_result = state.get_result("optimize_strategy") or {}
        if wf_ctx.get("passed") and opt_result.get("best_sharpe") is not None:
            sharpe = float(opt_result["best_sharpe"])
            logger.debug(
                f"[MemoryUpdateNode] Using optimized sharpe={sharpe:.3f} (raw IS was {metrics.get('sharpe_ratio', 0):.3f})"
            )

        importance = min(1.0, max(0.1, (sharpe + 1.0) / 4.0))  # 0→0.25, 2→0.75
        # Outcome label helps BM25 recall: MemoryRecallNode queries "successful strategy … high sharpe profit"
        # and "failed strategy … low sharpe no trades". Without matching keywords, BM25 returns 0 hits.
        outcome_label = "successful profitable high sharpe" if sharpe >= 0.4 else "failed poor low sharpe"
        episodic_content = (
            f"{outcome_label} strategy backtest result: {strategy_name} by {selected_agent} "
            f"on {symbol}/{timeframe} — "
            f"Sharpe={sharpe:.2f}, MaxDD={dd:.1f}%, Trades={trades}, "
            f"WinRate={metrics.get('win_rate', 0):.0%}, "
            f"ProfitFactor={metrics.get('profit_factor', 0):.2f}"
        )
        outcome_tag = "successful" if sharpe >= 0.4 else "failed"

        try:
            from backend.agents.memory.backend_interface import SQLiteBackendAdapter
            from backend.agents.memory.hierarchical_memory import HierarchicalMemory, MemoryType

            memory = HierarchicalMemory(backend=SQLiteBackendAdapter(db_path=_PIPELINE_MEMORY_DB))
            await memory.store(
                content=episodic_content,
                memory_type=MemoryType.EPISODIC,
                importance=importance,
                tags=["backtest", outcome_tag, symbol, timeframe, selected_agent, strategy_name],
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

        # Phase 6: save best optimization params to "optimization_params" namespace
        # so A2AParamRangeNode can recall them in future runs for the same symbol/regime
        opt_result = state.get_result("optimize_strategy") or {}
        best_params = opt_result.get("best_params", {})
        regime = (state.context.get("regime_classification") or {}).get("regime", "unknown")
        if best_params and sharpe >= 0.4:
            try:
                from backend.agents.memory.backend_interface import SQLiteBackendAdapter
                from backend.agents.memory.hierarchical_memory import HierarchicalMemory, MemoryType

                memory2 = HierarchicalMemory(backend=SQLiteBackendAdapter(db_path=_PIPELINE_MEMORY_DB))
                await memory2.store(
                    content=(
                        f"successful optimization {symbol} {regime} best params sharpe "
                        f"symbol={symbol} regime={regime} sharpe={sharpe:.3f} params={best_params}"
                    ),
                    memory_type=MemoryType.EPISODIC,
                    importance=importance,
                    tags=["optimization", "best_params", symbol, regime],
                    metadata={
                        "symbol": symbol,
                        "regime": regime,
                        "best_params": best_params,
                        "sharpe_ratio": sharpe,
                    },
                    source="trading_strategy_pipeline",
                    agent_namespace="optimization_params",
                )
                logger.debug("[MemoryUpdateNode] Saved opt params to 'optimization_params' namespace")
            except Exception as e:
                logger.debug(f"[MemoryUpdateNode] opt_params namespace save failed (non-fatal): {e}")

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

        # Iteration 3 (final attempt) → escalate to Opus in GenerateStrategiesNode
        if iteration >= self.MAX_REFINEMENTS:
            state.context["force_escalate"] = True
            logger.info("[Refinement] Iteration 3 — escalating to Claude Opus for final attempt")

        backtest_result = state.get_result("backtest") or {}
        metrics = backtest_result.get("metrics", {}) or {}
        engine_warnings: list[str] = list(backtest_result.get("engine_warnings", None) or [])
        sample_trades: list[dict] = list(backtest_result.get("sample_trades", None) or [])
        sig_long: int = int(backtest_result.get("signal_long_count", -1))
        sig_short: int = int(backtest_result.get("signal_short_count", -1))
        _signals_known = sig_long >= 0 and sig_short >= 0

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
        # Signal counts from generate_signals — critical context for the LLM to
        # understand WHY trades=0 or direction imbalance occurred.
        if _signals_known:
            feedback_parts.append(
                f"\nRAW SIGNAL COUNTS (before engine): long_entries={sig_long}, short_entries={sig_short}. "
                + (
                    "⚠️ NEAR-ZERO SIGNALS: AND-gate chains are killing all signals. "
                    "AND(A, B) produces at most min(count_A, count_B) signals. "
                    "If RSI 'cross' mode produces 0-2 signals in 6 months, AND(RSI, anything) = 0-2. "
                    "Fix: use RSI 'range' mode (oversold/overbought zones), use OR gates, "
                    "or remove deep AND chains. Each indicator block must produce ≥50 signals independently."
                    if sig_long + sig_short < 10
                    else (
                        "Signals exist in both directions — execution imbalance is due to "
                        "trade clustering (pyramiding=1 blocks new entries while position is open). "
                        "DO NOT add more conditions to 'fix' direction balance — it will reduce signals further."
                        if sig_long > 5 and sig_short > 5
                        else "One direction has very few signals — ensure both 'long' and 'short' ports are well-connected."
                    )
                )
            )

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

        # Always remind about SL/TP hard limits — the most common source of trades=0
        feedback_parts.append(
            "\n⚠️ HARD LIMITS (ALWAYS APPLY):\n"
            "  stop_loss value: 0.5% – 5.0%  (NEVER exceed 5% — BTC 15m bars move ~0.3% avg)\n"
            "  take_profit value: 1.0% – 10.0% (NEVER exceed 10%)\n"
            "  take_profit MUST be >= stop_loss (positive R:R)\n"
            "  Violating these limits causes trades=0 because price never reaches your SL/TP."
        )

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

    N_TRIALS = 100  # P3-3: n_jobs=2 → ~2× throughput; 100 trials fills the 120s budget
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

        # Use IS-backtest SL/TP so optimization trials share the same exit mechanics.
        # builder_optimizer._run_standard_block_backtest reads "stop_loss_pct" (percent, e.g. 2.0)
        # and converts to decimal internally.
        opt_sl = state.context.get("backtest_sl", 0.02)
        opt_tp = state.context.get("backtest_tp", 0.03)
        config_params = {
            "symbol": symbol,
            "interval": timeframe,  # build_backtest_input expects 'interval', not 'timeframe'
            "initial_capital": initial_capital,
            "leverage": leverage,
            "commission": COMMISSION_TV,  # build_backtest_input key is 'commission'
            "direction": "both",
            "stop_loss_pct": opt_sl * 100.0,  # decimal → percent (e.g. 0.02 → 2.0)
            "take_profit_pct": opt_tp * 100.0,  # decimal → percent (e.g. 0.03 → 3.0)
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

            # Build condensed top_trials array (up to 20 entries)
            raw_top = opt_result.get("top_results", [])
            top_trials: list[dict] = []
            for r in raw_top[:20]:
                top_trials.append(
                    {
                        "params": r.get("params", {}),
                        "sharpe": round(float(r.get("sharpe_ratio", 0.0)), 4),
                        "trades": int(r.get("total_trades", 0)),
                        "drawdown": round(float(r.get("max_drawdown", 0.0)), 2),
                        "profit_factor": round(float(r.get("profit_factor", 0.0)), 3),
                        "score": round(float(r.get("score", 0.0)), 4),
                    }
                )

            # Spearman rank correlation: each param → sharpe_ratio
            param_sensitivity: dict[str, float] = {}
            if len(top_trials) >= 3:
                param_sensitivity = self._compute_param_sensitivity(top_trials)

            n_positive_sharpe = sum(1 for t in top_trials if t["sharpe"] > 0)

            logger.info(
                f"✅ [OptimizationNode] {tested} trials, best_score={best_score:.3f}, "
                f"Sharpe={best_metrics.get('sharpe_ratio', 0):.2f}, "
                f"top_trials={len(top_trials)}, n_positive_sharpe={n_positive_sharpe}"
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
                    # --- Phase 1: optimizer array for agent analysis ---
                    "top_trials": top_trials,
                    "param_sensitivity": param_sensitivity,
                    "n_positive_sharpe": n_positive_sharpe,
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
            top_n=20,  # Re-run top-20 for full metrics (was 5) — needed for param_sensitivity
            timeout_seconds=self.TIMEOUT_SECONDS,
            n_jobs=2,  # P3-3: 2 parallel Optuna workers → ~2x trials within same 120s budget
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

    @staticmethod
    def _compute_param_sensitivity(top_trials: list[dict]) -> dict[str, float]:
        """Spearman rank correlation: each numeric param → sharpe_ratio across top_trials.

        Returns {param_key: rho} where rho ∈ [-1, 1].
        Positive rho → higher param value correlates with higher Sharpe.
        Only params that vary (≥2 unique values) and are fully numeric are included.
        """

        def rank_list(vals: list[float]) -> list[float]:
            order = sorted(range(len(vals)), key=lambda i: vals[i])
            ranks = [0.0] * len(vals)
            for rank, idx in enumerate(order, 1):
                ranks[idx] = float(rank)
            return ranks

        sharpe_vals = [t["sharpe"] for t in top_trials]
        sharpe_ranks = rank_list(sharpe_vals)
        n = len(top_trials)

        all_keys: set[str] = set()
        for t in top_trials:
            all_keys.update(t.get("params", {}).keys())

        result: dict[str, float] = {}
        for key in sorted(all_keys):
            values = [t.get("params", {}).get(key) for t in top_trials]
            if any(v is None or not isinstance(v, (int, float)) for v in values):
                continue
            float_vals = [float(v) for v in values]  # type: ignore[arg-type]
            if len(set(float_vals)) < 2:
                continue  # constant param — sensitivity undefined
            param_ranks = rank_list(float_vals)
            d2 = sum((pr - sr) ** 2 for pr, sr in zip(param_ranks, sharpe_ranks, strict=True))
            rho = 1.0 - 6.0 * d2 / (n * (n * n - 1)) if n > 1 else 0.0
            result[key] = round(rho, 3)

        return result


# =============================================================================
# Phase 5: AnalysisDebateNode — structured Optimist vs Risk-Manager debate
# =============================================================================


class AnalysisDebateNode(AgentNode):
    """Two-agent structured debate before Walk-Forward / ML validation.

    Round 1 (parallel):
      - Claude Sonnet  "Optimist"      — arguments FOR deploying the strategy
      - Claude Haiku   "Risk Manager"  — arguments AGAINST (drawdown, overfitting)
    Round 2 (sequential):
      - Claude Haiku   "Synthesiser"   — weighs both sides, produces final verdict

    Outcome stored in ``state.debate_outcome``:
        {
            "decision":   "proceed" | "reject" | "conditional",
            "risk_score": 0–10  (0 = no risk, 10 = very high risk),
            "conditions": ["...", ...]  (only meaningful for "conditional"),
            "rationale":  "..."
        }

    Timeout: 45 s (not 150 s like the heavyweight DebateNode).
    """

    _OPTIMIST_SYS = (
        "You are an experienced quantitative trader who is OPTIMISTIC about this strategy. "
        "Provide 2-3 concise, data-backed arguments FOR deploying it. "
        "Focus on positive metrics. Be brief."
    )
    _RISK_SYS = (
        "You are a risk manager who is SCEPTICAL about this strategy. "
        "Provide 2-3 concise arguments AGAINST deploying it, focusing on drawdown, "
        "overfitting risk, and regime sensitivity. Be brief."
    )
    _SYNTH_SYS = (
        "You are an impartial quantitative analyst. "
        "Given the optimist and risk-manager arguments below, produce a final verdict. "
        "Reply ONLY with a JSON object. No prose, no markdown fences."
    )

    def __init__(self) -> None:
        super().__init__(
            name="analysis_debate",
            description="Optimist vs Risk-Manager debate to gate strategy deployment",
            timeout=45.0,
            retry_count=1,
            retry_delay=2.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        # Gather inputs
        backtest_result = state.get_result("backtest") or {}
        opt_result = state.get_result("optimize_strategy") or {}
        opt_analysis = state.get_result("optimization_analysis") or {}

        metrics_summary = self._build_metrics_summary(backtest_result, opt_result, opt_analysis)
        iter_summary = self._build_iter_summary(state.opt_iterations)

        optimist_prompt = (
            f"Strategy performance summary:\n{metrics_summary}\n"
            f"Optimisation history:\n{iter_summary}\n"
            "Provide your arguments FOR deploying this strategy."
        )
        risk_prompt = (
            f"Strategy performance summary:\n{metrics_summary}\n"
            f"Optimisation history:\n{iter_summary}\n"
            "Provide your arguments AGAINST deploying this strategy."
        )

        optimist_view: str | None = None
        risk_view: str | None = None
        try:
            optimist_view, risk_view = await asyncio.gather(
                self._call_llm("claude-sonnet", optimist_prompt, self._OPTIMIST_SYS, temperature=0.4, state=state),
                self._call_llm("claude-haiku", risk_prompt, self._RISK_SYS, temperature=0.3, state=state),
                return_exceptions=False,
            )
        except Exception as exc:
            logger.warning(f"[AnalysisDebate] Parallel calls failed: {exc} — using safe default")

        outcome = await self._synthesise(optimist_view, risk_view, metrics_summary, state)
        state.debate_outcome = outcome
        state.set_result(self.name, outcome)

        logger.info(f"[AnalysisDebate] decision={outcome['decision']} risk_score={outcome['risk_score']}")
        return state

    async def _synthesise(
        self,
        optimist_view: str | None,
        risk_view: str | None,
        metrics_summary: str,
        state: AgentState,
    ) -> dict:
        synth_prompt = (
            f"Metrics:\n{metrics_summary}\n\n"
            f"Optimist arguments:\n{optimist_view or '(unavailable)'}\n\n"
            f"Risk Manager arguments:\n{risk_view or '(unavailable)'}\n\n"
            "Produce a final verdict as JSON with keys:\n"
            '  "decision": "proceed" | "reject" | "conditional"\n'
            '  "risk_score": integer 0-10\n'
            '  "conditions": list of strings (empty if not conditional)\n'
            '  "rationale": one-sentence summary\n'
        )
        try:
            raw = await self._call_llm(
                "claude-haiku",
                synth_prompt,
                self._SYNTH_SYS,
                temperature=0.1,
                state=state,
                json_mode=True,
            )
            parsed = self._parse_outcome(raw)
            if parsed:
                return parsed
        except Exception as exc:
            logger.warning(f"[AnalysisDebate] Synthesis call failed: {exc}")
        # Safe default: proceed with moderate risk
        return {
            "decision": "proceed",
            "risk_score": 5,
            "conditions": [],
            "rationale": "Synthesis unavailable — defaulting to proceed.",
        }

    @staticmethod
    def _build_metrics_summary(backtest: dict, opt: dict, opt_analysis: dict) -> str:
        sharpe = opt.get("best_sharpe") or backtest.get("sharpe_ratio", 0.0)
        dd = opt.get("best_drawdown") or backtest.get("max_drawdown", 0.0)
        trades = opt.get("best_trades") or backtest.get("total_trades", 0)
        n_pos = opt.get("n_positive_sharpe", 0)
        risks = opt_analysis.get("risks", [])
        return (
            f"Sharpe: {sharpe:.3f} | Max Drawdown: {dd:.1f}% | Trades: {trades} | "
            f"Positive-Sharpe trials: {n_pos} | Risk flags: {len(risks)}"
        )

    @staticmethod
    def _build_iter_summary(iterations: list) -> str:
        if not iterations:
            return "(no iteration history)"
        lines = [
            f"  Iter {it['iteration']}: Sharpe={it['best_sharpe']:.3f} params={it.get('best_params', {})}"
            for it in iterations
        ]
        return "\n".join(lines)

    @staticmethod
    def _parse_outcome(raw: str | None) -> dict | None:
        if not raw:
            return None
        import json as _json
        import re as _re

        text = raw.strip()
        match = _re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()
        try:
            data = _json.loads(text)
            if isinstance(data, dict) and "decision" in data:
                # Normalise decision field
                decision = str(data.get("decision", "proceed")).lower()
                if decision not in {"proceed", "reject", "conditional"}:
                    decision = "proceed"
                return {
                    "decision": decision,
                    "risk_score": int(data.get("risk_score", 5)),
                    "conditions": list(data.get("conditions", [])),
                    "rationale": str(data.get("rationale", "")),
                }
        except (_json.JSONDecodeError, ValueError, TypeError):
            pass
        return None


def _is_debate_rejected(state: AgentState) -> bool:
    """Return True if AnalysisDebateNode decided to reject the strategy."""
    outcome = getattr(state, "debate_outcome", None)
    if not outcome:
        return False
    return str(outcome.get("decision", "")).lower() == "reject"


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
            timeout=180.0,
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
        # 7.1-7.3  Overfitting / Regime / Stability — run in parallel (P3-2)
        # All three sub-checks are independent: same inputs, different slices/logic.
        # ------------------------------------------------------------------
        _cfg = {
            "symbol": symbol,
            "timeframe": timeframe,
            "initial_capital": initial_capital,
            "leverage": leverage,
            "commission_value": COMMISSION_TV,
            "direction": "both",
        }
        overfit_raw, regime_raw, stability_raw = await asyncio.gather(
            asyncio.to_thread(self._check_overfitting, strategy_graph, df, _cfg),
            asyncio.to_thread(self._check_regimes, strategy_graph, df, _cfg),
            asyncio.to_thread(self._check_parameter_stability, strategy_graph, df, _cfg),
            return_exceptions=True,
        )

        # 7.1 process overfitting result
        if isinstance(overfit_raw, Exception):
            logger.warning(f"[MLValidationNode] Overfitting check failed (non-fatal): {overfit_raw}")
            validation["overfitting"] = {"status": "error", "error": str(overfit_raw)}
        else:
            overfit_result = overfit_raw
            validation["overfitting"] = overfit_result
            if overfit_result.get("is_overfit"):
                validation["warnings"].append(
                    f"[OVERFIT] IS_sharpe={overfit_result['is_sharpe']:.2f} "
                    f"OOS_sharpe={overfit_result['oos_sharpe']:.2f} "
                    f"gap={overfit_result['gap']:.2f} (threshold {self.OVERFIT_GAP_THRESHOLD})"
                )
                logger.warning(f"⚠️ [MLValidation] Overfitting detected: gap={overfit_result['gap']:.2f}")
            elif overfit_result.get("status") == "ok":
                logger.info(
                    f"✅ [MLValidation] Overfitting check passed "
                    f"(IS={overfit_result.get('is_sharpe', 0):.2f} "
                    f"OOS={overfit_result.get('oos_sharpe', 0):.2f})"
                )
            else:
                logger.warning(
                    f"⚠️ [MLValidation] Overfitting check skipped/errored: "
                    f"status={overfit_result.get('status')} reason={overfit_result.get('reason') or overfit_result.get('error', '')}"
                )

        # 7.2 process regime result
        if isinstance(regime_raw, Exception):
            logger.warning(f"[MLValidationNode] Regime analysis failed (non-fatal): {regime_raw}")
            validation["regime_analysis"] = {"status": "error", "error": str(regime_raw)}
        else:
            regime_result = regime_raw
            validation["regime_analysis"] = regime_result
            poor_regimes = [r for r, s in regime_result.get("regime_sharpes", {}).items() if s < 0]
            if poor_regimes:
                validation["warnings"].append(
                    f"[REGIME] Strategy performs poorly in: {poor_regimes}. Consider adding a regime filter block."
                )
                logger.info(f"ℹ️ [MLValidation] Poor regimes: {poor_regimes}")
            else:
                logger.info("✅ [MLValidation] Regime check: strategy viable across all regimes")

        # 7.3 process stability result
        if isinstance(stability_raw, Exception):
            logger.warning(f"[MLValidationNode] Stability check failed (non-fatal): {stability_raw}")
            validation["parameter_stability"] = {"status": "error", "error": str(stability_raw)}
        else:
            stability_result = stability_raw
            validation["parameter_stability"] = stability_result
            if not stability_result.get("is_stable", True):
                validation["warnings"].append(
                    f"[STABILITY] Sensitive params: {stability_result.get('sensitive_params', [])}"
                )
                logger.warning(f"⚠️ [MLValidation] Parameter instability: {stability_result.get('sensitive_params')}")
            else:
                logger.info("✅ [MLValidation] Parameter stability check passed")

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

        # Derive start/end from the df slice (BacktestConfig requires these fields)
        idx = df.index
        _start = idx[0]
        _end = idx[-1]
        start_date = _start.to_pydatetime() if hasattr(_start, "to_pydatetime") else _start
        end_date = _end.to_pydatetime() if hasattr(_end, "to_pydatetime") else _end

        cfg = BacktestConfig(
            symbol=config_params.get("symbol", "BTCUSDT"),
            interval=config_params.get("timeframe", "15"),  # BacktestConfig uses interval=
            start_date=start_date,
            end_date=end_date,
            initial_capital=config_params.get("initial_capital", INITIAL_CAPITAL),
            leverage=config_params.get("leverage", 1),
            direction=config_params.get("direction", "both"),
            commission_value=config_params.get("commission_value", 0.0007),
            # Disable bar magnifier: ML validation runs many quick comparative backtests;
            # intrabar SL/TP precision is unnecessary and loading 200K 1m candles per
            # backtest would cause timeout (17 perturbation backtests × ~19s > 120s).
            use_bar_magnifier=False,
        )
        engine = BacktestEngine()
        # Pass adapter as custom_strategy so the engine calls adapter.generate_signals()
        result = engine.run(cfg, df, silent=True, custom_strategy=adapter)
        if not result.metrics:
            return {}
        # Return as plain dict so downstream .get() calls work correctly
        return result.metrics.model_dump()

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
            _ = signal_result.entries.values if hasattr(signal_result.entries, "values") else signal_result.entries
        except Exception:
            pass

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
                new_value = max(2, round(orig_value * (1.0 + frac)))
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
                "Pipeline paused for human review. Set state.context['hitl_approved'] = True and re-run to continue."
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

        # When WF passed, the run ultimately succeeded — override passed/sharpe with
        # the optimized values so memory stores an accurate, high-quality entry.
        if wf.get("passed"):
            passed = True
            opt_result = state.get_result("optimize_strategy") or {}
            if opt_result.get("best_sharpe") is not None:
                sharpe = float(opt_result["best_sharpe"])

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
            adjustments.append(
                f"In {regime} regime: prefer trend-following (EMA crossover, Supertrend) over oscillators"
            )

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
            from backend.agents.memory.backend_interface import SQLiteBackendAdapter
            from backend.agents.memory.hierarchical_memory import HierarchicalMemory, MemoryType

            memory = HierarchicalMemory(backend=SQLiteBackendAdapter(db_path=_PIPELINE_MEMORY_DB))
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
# Phase 3: Optimization Analysis Node — Claude analyses top-20 Optuna trials
# =============================================================================


class OptimizationAnalysisNode(AgentNode):
    """Reads OptimizationNode's top_trials and asks Claude Haiku to identify:
    - param_clusters: which param values appear in the top-5 results
    - winning_zones: param ranges where Sharpe > 0.8
    - risks: configs with good Sharpe but high drawdown (overfitting warning)
    - next_ranges: tighter param ranges for the next sweep

    Writes results to state.opt_insights and state.set_result("optimization_analysis", ...).
    Skips gracefully when top_trials is empty or optimization was not run.
    """

    _SYSTEM = (
        "You are a quantitative analyst reviewing optimization results. "
        "Reply ONLY with a JSON object. No prose, no markdown fences."
    )

    def __init__(self) -> None:
        super().__init__(
            name="optimization_analysis",
            description="Claude analyses top-20 Optuna trials to extract winning parameter zones",
            timeout=30.0,
            retry_count=1,
            retry_delay=2.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        opt_result = state.get_result("optimize_strategy") or {}
        top_trials: list[dict] = opt_result.get("top_trials", [])

        if not top_trials:
            logger.info("[OptimizationAnalysis] No top_trials — skipping")
            state.set_result(self.name, {"skipped": True, "reason": "no_top_trials"})
            return state

        symbol = state.context.get("symbol", "BTCUSDT")
        regime = (state.context.get("regime_classification") or {}).get("regime", "unknown")

        prompt = self._build_analysis_prompt(symbol, regime, top_trials)
        try:
            raw = await self._call_llm(
                "claude-haiku",
                prompt,
                self._SYSTEM,
                temperature=0.2,
                state=state,
                json_mode=True,
            )
            insights = self._parse_insights(raw)
            logger.info(
                f"[OptimizationAnalysis] Analysis complete — "
                f"{len(insights.get('param_clusters', {}))} clusters, "
                f"{len(insights.get('winning_zones', {}))} winning zones"
            )
        except Exception as exc:
            logger.warning(f"[OptimizationAnalysis] Claude call failed (non-fatal): {exc}")
            insights = {}

        state.opt_insights = insights
        state.set_result(
            self.name,
            {
                "param_clusters": insights.get("param_clusters", {}),
                "winning_zones": insights.get("winning_zones", {}),
                "risks": insights.get("risks", []),
                "next_ranges": insights.get("next_ranges", {}),
                "n_trials_analysed": len(top_trials),
            },
        )
        # Phase 4: record this sweep in opt_iterations for the loop router
        state.opt_iterations.append(
            {
                "iteration": len(state.opt_iterations) + 1,
                "best_sharpe": opt_result.get("best_sharpe", 0.0),
                "best_params": opt_result.get("best_params", {}),
                "n_trials": opt_result.get("tested_combinations", 0),
            }
        )
        return state

    @staticmethod
    def _build_analysis_prompt(symbol: str, regime: str, top_trials: list[dict]) -> str:
        """Build a compact JSON prompt with trial data for Claude to analyse."""
        # Summarise each trial: only the fields Claude needs
        trial_rows = []
        for i, t in enumerate(top_trials[:20], 1):
            params = t.get("params", {})
            row = {
                "rank": i,
                "sharpe": round(t.get("sharpe", 0.0), 3),
                "drawdown_pct": round(t.get("max_drawdown", 0.0), 1),
                "trades": t.get("trades", 0),
                "params": {k: round(v, 4) if isinstance(v, float) else v for k, v in params.items()},
            }
            trial_rows.append(row)

        import json as _json

        trials_json = _json.dumps(trial_rows, separators=(",", ":"))

        return (
            f"Symbol: {symbol} | Market regime: {regime}\n"
            f"Top-{len(trial_rows)} Optuna optimisation results:\n"
            f"{trials_json}\n\n"
            "Analyse these results and return a JSON object with EXACTLY these keys:\n"
            '  "param_clusters": {{"<param_name>": [<most_common_values_in_top5>], ...}}\n'
            '  "winning_zones": {{"<param_name>": {{"min": <v>, "max": <v>}}, ...}}  '
            "(ranges where Sharpe > 0.8)\n"
            '  "risks": [  // configs that look good but are risky\n'
            '    {{"rank": <n>, "issue": "<description>"}},\n'
            "    ...\n"
            "  ]\n"
            '  "next_ranges": {{"<param_name>": {{"min": <v>, "max": <v>}}, ...}}  '
            "(tighter ranges for next sweep)\n"
        )

    @staticmethod
    def _parse_insights(raw: str | None) -> dict:
        """Parse JSON from Claude response. Returns empty dict on failure."""
        if not raw:
            return {}
        import json as _json
        import re as _re

        text = raw.strip()
        # Strip markdown code fences if present
        match = _re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()
        try:
            data = _json.loads(text)
            if isinstance(data, dict):
                return data
        except (_json.JSONDecodeError, ValueError):
            pass
        return {}


# =============================================================================
# Phase 4: Iterative Optimization Loop helpers + A2AParamRangeNode
# =============================================================================

_MAX_OPT_ITERATIONS = 3


def _should_continue_opt(state: AgentState) -> bool:
    """Return True if the optimization loop should run another iteration.

    Conditions to CONTINUE:
    - Fewer than _MAX_OPT_ITERATIONS completed so far  AND
    - Not yet converged (top-1 params changed > 5% vs previous iteration)

    Convergence is checked only once ≥ 2 iterations have been recorded.
    """
    iterations = state.opt_iterations
    if len(iterations) >= _MAX_OPT_ITERATIONS:
        return False
    if len(iterations) < 2:
        return True  # need at least 2 data points for convergence check

    last = iterations[-1].get("best_params", {})
    prev = iterations[-2].get("best_params", {})
    diffs = [
        abs(last[k] - prev[k]) / max(abs(float(prev[k])), 1e-9)
        for k in last
        if k in prev and isinstance(last[k], (int, float)) and isinstance(prev[k], (int, float))
    ]
    # Converged if all params moved by ≤ 5%
    return not diffs or max(diffs) > 0.05


class A2AParamRangeNode(AgentNode):
    """Phase 4: Uses opt_insights (from OptimizationAnalysisNode) to propose
    tighter parameter ranges for the next Optuna sweep.

    Claude Haiku reads the winning_zones, next_ranges, and param_clusters from
    the previous analysis and produces a refined ``{"ranges": {...}}`` dict that
    is stored in ``state.context["agent_optimization_hints"]``.

    If the LLM call fails, falls back to using opt_insights.next_ranges directly
    so the optimisation loop can still proceed.
    """

    _SYSTEM = (
        "You are a quantitative parameter optimiser. "
        "Reply ONLY with a JSON object containing a single key 'ranges'. "
        "No prose, no markdown fences."
    )

    def __init__(self) -> None:
        super().__init__(
            name="param_range",
            description="Propose tighter param ranges for the next optimisation sweep",
            timeout=20.0,
            retry_count=1,
            retry_delay=2.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        insights = state.opt_insights
        if not insights:
            logger.info("[A2AParamRange] No opt_insights — skipping range refinement")
            return state

        iteration = len(state.opt_iterations)
        symbol = state.context.get("symbol", "BTCUSDT")
        regime = (state.context.get("regime_classification") or {}).get("regime", "unknown")

        # Phase 6: memory recall — historical successful params for this symbol/regime
        try:
            memory_records = await self._recall_opt_params(symbol, regime)
        except Exception:
            memory_records = []
        memory_context = self._format_memory_context(memory_records)

        prompt = self._build_range_prompt(symbol, regime, iteration, insights, memory_context)
        new_hints: dict = {}
        try:
            raw = await self._call_llm(
                "claude-haiku",
                prompt,
                self._SYSTEM,
                temperature=0.1,
                state=state,
                json_mode=True,
            )
            parsed = self._parse_ranges(raw)
            if parsed:
                new_hints = parsed
                logger.info(
                    f"[A2AParamRange] iter={iteration} — "
                    f"Claude proposed ranges for {len(parsed.get('ranges', {}))} params"
                )
        except Exception as exc:
            logger.warning(f"[A2AParamRange] LLM call failed (non-fatal): {exc}")

        # Fallback: use next_ranges from OptimizationAnalysisNode directly
        if not new_hints:
            next_ranges = insights.get("next_ranges", {})
            if next_ranges:
                new_hints = {
                    "ranges": {k: [v["min"], v["max"]] for k, v in next_ranges.items() if "min" in v and "max" in v}
                }
                logger.info(f"[A2AParamRange] Fallback to direct next_ranges ({len(new_hints['ranges'])} params)")

        if new_hints:
            state.context["agent_optimization_hints"] = new_hints

        state.set_result(
            self.name,
            {
                "iteration": iteration,
                "hints_applied": bool(new_hints),
                "n_params_refined": len(new_hints.get("ranges") or {}),
            },
        )
        return state

    @staticmethod
    def _build_range_prompt(
        symbol: str,
        regime: str,
        iteration: int,
        insights: dict,
        memory_context: str = "",
    ) -> str:
        import json as _json

        data = {
            "symbol": symbol,
            "regime": regime,
            "iteration": iteration,
            "param_clusters": insights.get("param_clusters", {}),
            "winning_zones": insights.get("winning_zones", {}),
            "next_ranges": insights.get("next_ranges", {}),
            "risks": insights.get("risks", []),
        }
        memory_section = f"\nHistorical optimization memory:\n{memory_context}\n" if memory_context else ""
        return (
            f"Iteration {iteration} optimisation analysis:\n"
            f"{_json.dumps(data, separators=(',', ':'))}\n"
            f"{memory_section}\n"
            "Based on the winning_zones, next_ranges, and historical memory above, "
            "propose the tightest possible parameter ranges for the next sweep.\n"
            'Return ONLY: {"ranges": {"<param_name>": [<min>, <max>], ...}}'
        )

    async def _recall_opt_params(self, symbol: str, regime: str) -> list:
        """Query optimization_params namespace for historical best params.

        Non-blocking — returns empty list on any error.
        """
        try:
            from backend.agents.memory.backend_interface import SQLiteBackendAdapter
            from backend.agents.memory.hierarchical_memory import HierarchicalMemory

            memory = HierarchicalMemory(backend=SQLiteBackendAdapter(db_path=_PIPELINE_MEMORY_DB))
            await memory.async_load()
            results = await memory.recall(
                query=f"successful optimization {symbol} {regime} best params sharpe",
                top_k=3,
                agent_namespace="optimization_params",
            )
            return results
        except Exception as exc:
            logger.debug(f"[A2AParamRange] Memory recall failed (non-fatal): {exc}")
            return []

    @staticmethod
    def _format_memory_context(records: list) -> str:
        """Format memory recall results into a short text block for the LLM prompt."""
        if not records:
            return ""
        lines = []
        for rec in records[:3]:
            content = getattr(rec, "content", None) or (rec.get("content") if isinstance(rec, dict) else "")
            if content:
                lines.append(f"  - {str(content)[:200]}")
        return "\n".join(lines)

    @staticmethod
    def _parse_ranges(raw: str | None) -> dict:
        if not raw:
            return {}
        import json as _json
        import re as _re

        text = raw.strip()
        match = _re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()
        try:
            data = _json.loads(text)
            if isinstance(data, dict) and "ranges" in data:
                return data
        except (_json.JSONDecodeError, ValueError):
            pass
        return {}


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

    Acceptance criterion (either condition passes):
        1. wf_sharpe / is_sharpe >= WF_RATIO_THRESHOLD (0.5)  — ratio check
        2. wf_sharpe >= WF_MIN_ABS_SHARPE (0.5)               — absolute OOS floor

    The absolute floor handles high-IS optimized strategies: if optimizer finds
    IS Sharpe=1.8 but OOS Sharpe=0.51, ratio=0.28 fails the ratio check, but the
    strategy is genuinely tradeable (positive OOS edge) and should not be rejected.

    Result stored in:
    - ``state.context["wf_validation"]`` — {passed, wf_sharpe, is_sharpe, ratio, windows}
    - ``state.results["wf_validation"]`` — same dict

    Wired: optimize_strategy → wf_validation → [analysis_debate | refine]
    is_sharpe is taken from the optimizer's best_sharpe when available (optimized params),
    falling back to the raw IS backtest Sharpe.
    """

    WF_RATIO_THRESHOLD: float = 0.5  # wf_sharpe / is_sharpe must exceed this
    WF_MIN_ABS_SHARPE: float = 0.5  # OR: absolute OOS Sharpe floor (passes even if ratio < threshold)
    TRAIN_MONTHS: int = 3  # walk-forward training window
    TEST_MONTHS: int = 1  # walk-forward test window
    MIN_BARS_FOR_WF: int = 200  # skip WF if fewer bars available

    def __init__(self) -> None:
        super().__init__(
            name="wf_validation",
            description="Walk-forward overfitting gate (wf_sharpe/is_sharpe >= 0.5)",
            timeout=60.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        backtest_result = state.get_result("backtest") or {}
        metrics = backtest_result.get("metrics", {}) or {}
        raw_is_sharpe: float = float(metrics.get("sharpe_ratio", 0.0))

        # Prefer optimizer best_sharpe — WF now runs AFTER optimization so it validates
        # optimized params, not the raw LLM-generated strategy with default values.
        # OptimizationNode also sets state.context["strategy_graph"] to the optimized graph.
        opt_result = state.get_result("optimize_strategy") or {}
        opt_best_sharpe = opt_result.get("best_sharpe")
        if opt_best_sharpe is not None and float(opt_best_sharpe) > raw_is_sharpe:
            is_sharpe = float(opt_best_sharpe)
            logger.info(f"[WF] Using optimizer best_sharpe={is_sharpe:.3f} (raw IS={raw_is_sharpe:.3f})")
        else:
            is_sharpe = raw_is_sharpe

        strategy_graph = state.context.get("strategy_graph") or backtest_result.get("strategy_graph")
        df: pd.DataFrame | None = state.context.get("df")

        # Skip if missing inputs (graph or data not available)
        if strategy_graph is None or df is None or df.empty:
            result = {
                "passed": True,
                "skipped": True,
                "reason": "no_graph_or_data",
                "is_sharpe": is_sharpe,
            }
            state.set_result(self.name, result)
            state.context["wf_validation"] = result
            logger.debug(f"[WF] Skipped walk-forward: {result['reason']}")
            return state

        # Hard quality gate: negative IS Sharpe means strategy is unprofitable regardless of overfitting
        if is_sharpe <= 0:
            result = {
                "passed": False,
                "skipped": False,
                "reason": "negative_is_sharpe",
                "is_sharpe": round(is_sharpe, 4),
                "wf_sharpe": None,
                "ratio": None,
            }
            state.set_result(self.name, result)
            state.context["wf_validation"] = result
            # Flag backtest_analysis so _should_refine sees it
            analysis = state.context.get("backtest_analysis", {})
            analysis["passed"] = False
            analysis["wf_failed"] = True
            state.context["backtest_analysis"] = analysis
            logger.warning(f"⚠️ [WF] Hard reject: IS Sharpe={is_sharpe:.3f} ≤ 0 — strategy is unprofitable")
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
            symbol = state.context.get("symbol", "BTCUSDT")
            wf_sharpes = await asyncio.to_thread(self._run_rolling_wf, strategy_graph, df, is_sharpe, symbol)
        except Exception as exc:
            logger.warning(f"[WF] Walk-forward failed (non-fatal): {exc}")
            result = {"passed": True, "skipped": True, "reason": f"wf_error: {exc}", "is_sharpe": is_sharpe}
            state.set_result(self.name, result)
            state.context["wf_validation"] = result
            return state

        wf_sharpe = sum(wf_sharpes) / len(wf_sharpes) if wf_sharpes else 0.0
        # Ratio only meaningful when IS Sharpe is positive (already guaranteed above).
        # wf_sharpe must also be positive to pass; two-negative ratio is a false positive.
        ratio = wf_sharpe / is_sharpe if is_sharpe > 0 else 0.0
        # Pass if ratio >= threshold (OOS is at least 50% of IS),
        # OR if absolute OOS Sharpe is strong enough (≥ WF_MIN_ABS_SHARPE).
        # The second clause handles high-IS optimized strategies where ratio is low
        # but OOS Sharpe is genuinely good (e.g. IS=1.8, OOS=0.51 → ratio=0.28 but tradeable).
        ratio_passes = ratio >= self.WF_RATIO_THRESHOLD
        abs_passes = wf_sharpe >= self.WF_MIN_ABS_SHARPE
        passed = is_sharpe > 0 and wf_sharpe > 0 and (ratio_passes or abs_passes)

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
            how = "ratio" if ratio_passes else f"abs_sharpe≥{self.WF_MIN_ABS_SHARPE}"
            logger.info(f"✅ [WF] Walk-forward passed [{how}]: ratio={ratio:.2f} ({wf_sharpe:.2f}/{is_sharpe:.2f})")
        else:
            logger.warning(
                f"⚠️ [WF] Overfitting detected: ratio={ratio:.2f} < {self.WF_RATIO_THRESHOLD} "
                f"AND wf_sharpe={wf_sharpe:.2f} < {self.WF_MIN_ABS_SHARPE} "
                f"(is={is_sharpe:.2f}) — flagging for refinement"
            )
            # Inject into backtest_analysis so _should_refine sees it
            analysis = state.context.get("backtest_analysis", {})
            analysis["passed"] = False
            analysis["wf_failed"] = True
            state.context["backtest_analysis"] = analysis

        return state

    def _run_rolling_wf(
        self, strategy_graph: dict, df: pd.DataFrame, is_sharpe: float, symbol: str = "BTCUSDT"
    ) -> list[float]:
        """Synchronous: run rolling walk-forward windows, return list of test Sharpes."""
        from datetime import UTC

        from backend.backtesting.engine import BacktestEngine
        from backend.backtesting.models import BacktestConfig
        from backend.backtesting.strategies import BaseStrategy
        from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter
        from backend.config.constants import COMMISSION_TV

        bars_per_month = max(1, len(df) // 12)  # approximate
        train_bars = self.TRAIN_MONTHS * bars_per_month
        test_bars = self.TEST_MONTHS * bars_per_month
        step_bars = test_bars

        # Pre-compute signals once over the full dataset to avoid repeated adapter init
        try:
            adapter = StrategyBuilderAdapter(strategy_graph)
            full_signals = adapter.generate_signals(df)
        except Exception as e:
            logger.warning(f"[WF] Failed to generate signals for WF windows: {e}")
            return []

        results: list[float] = []
        i = 0
        while i + train_bars + test_bars <= len(df):
            test_slice = df.iloc[i + train_bars : i + train_bars + test_bars]
            if len(test_slice) < 30:
                break
            try:
                # Derive timezone-aware start/end from this window's index
                t_start = test_slice.index[0]
                t_end = test_slice.index[-1]
                if hasattr(t_start, "to_pydatetime"):
                    t_start = t_start.to_pydatetime()
                if hasattr(t_end, "to_pydatetime"):
                    t_end = t_end.to_pydatetime()
                if t_start.tzinfo is None:
                    t_start = t_start.replace(tzinfo=UTC)
                if t_end.tzinfo is None:
                    t_end = t_end.replace(tzinfo=UTC)

                # Slice pre-computed signals to this window
                window_entries = full_signals.entries.iloc[i + train_bars : i + train_bars + test_bars]
                window_exits = full_signals.exits.iloc[i + train_bars : i + train_bars + test_bars]
                window_short_entries = (
                    full_signals.short_entries.iloc[i + train_bars : i + train_bars + test_bars]
                    if full_signals.short_entries is not None
                    else None
                )
                window_short_exits = (
                    full_signals.short_exits.iloc[i + train_bars : i + train_bars + test_bars]
                    if full_signals.short_exits is not None
                    else None
                )

                from backend.backtesting.strategies import SignalResult as _SR

                window_signals = _SR(
                    entries=window_entries,
                    exits=window_exits,
                    short_entries=window_short_entries,
                    short_exits=window_short_exits,
                    entry_sizes=None,
                    short_entry_sizes=None,
                    extra_data=None,
                )

                class _WindowStrategy(BaseStrategy):
                    def _validate_params(self) -> None:
                        pass

                    def generate_signals(self, ohlcv, _sig=window_signals):
                        return _sig

                # Detect timeframe from graph interval; fall back to "15"
                tf = str(strategy_graph.get("interval", "15"))

                cfg = BacktestConfig(
                    symbol=symbol,
                    interval=tf,
                    start_date=t_start,
                    end_date=t_end,
                    initial_capital=10000.0,
                    commission_value=COMMISSION_TV,
                    direction="both",
                    stop_loss=0.02,
                    take_profit=0.03,
                )

                engine = BacktestEngine()
                bt_result = engine.run(
                    config=cfg,
                    ohlcv=test_slice,
                    silent=True,
                    custom_strategy=_WindowStrategy(),
                )
                raw_m = bt_result.metrics
                if raw_m is None:
                    sharpe = 0.0
                elif hasattr(raw_m, "model_dump"):
                    sharpe = raw_m.model_dump().get("sharpe_ratio", 0.0)
                elif isinstance(raw_m, dict):
                    sharpe = raw_m.get("sharpe_ratio", 0.0)
                else:
                    sharpe = getattr(raw_m, "sharpe_ratio", 0.0)
                results.append(float(sharpe or 0.0))
            except Exception as exc:
                logger.debug(f"[WF] Window {i}: error — {exc}")
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
    # sharpe > 0: strictly positive required — sharpe=0 means no alpha generated
    return trades >= _MIN_TRADES and sharpe > 0.0 and dd < _MAX_DD_PCT


def _should_refine(state: AgentState) -> bool:
    """Return True if we should trigger refinement (failed + iterations left).

    Skips refinement when root_cause is ``poor_risk_reward`` AND the strategy has
    adequate signal coverage (≥50 raw signals, ≥5 trades).  In this case LLM
    refinement rarely helps because signal generation is fine — only parameter
    tuning is needed, which the OptimizationNode handles far more efficiently.
    """
    if _backtest_passes(state):
        return False
    iteration = state.context.get("refinement_iteration", 0)
    if iteration >= RefinementNode.MAX_REFINEMENTS:
        return False

    # Skip refinement for poor_risk_reward with good signal coverage — the
    # optimizer will tune SL/TP/periods far more effectively than LLM rewriting.
    analysis = state.context.get("backtest_analysis", {})
    if analysis.get("root_cause") == "poor_risk_reward":
        backtest = state.get_result("backtest") or {}
        sig_long = int(backtest.get("signal_long_count", -1))
        sig_short = int(backtest.get("signal_short_count", -1))
        trades = int((backtest.get("metrics", {}) or {}).get("total_trades", 0))
        if sig_long >= 0 and sig_short >= 0 and sig_long + sig_short >= 50 and trades >= RefinementNode.MIN_TRADES:
            logger.info(
                f"[_should_refine] Skipping refinement: root_cause=poor_risk_reward "
                f"with {sig_long}L+{sig_short}S signals, {trades} trades — "
                f"sending to optimizer instead"
            )
            return False

    return True


def _report_node(state: AgentState) -> AgentState:
    """Final node: compile all results into a report.

    Phase 8 additions:
    - top_trials_table  — top-20 Optuna trials with Sharpe/DD/trades/params
    - iteration_history — per-iteration Sharpe + params from opt_iterations
    - opt_insights      — param_clusters, winning_zones, risks from OptimizationAnalysisNode
    - debate_outcome    — AnalysisDebateNode decision + risk_score + rationale
    - comparison        — initial vs final Sharpe/DD (OPTIMIZE mode)
    """
    opt_result = state.get_result("optimize_strategy") or {}
    backtest_result = state.get_result("backtest") or {}

    # ── Top-20 Optuna trials table ──────────────────────────────────────────
    top_trials = opt_result.get("top_trials", [])
    top_trials_table = [
        {
            "rank": t.get("rank", i + 1),
            "sharpe": round(float(t.get("sharpe", 0)), 4),
            "max_drawdown": round(float(t.get("max_drawdown", 0)), 2),
            "trades": int(t.get("trades", 0)),
            "params": t.get("params", {}),
        }
        for i, t in enumerate(top_trials[:20])
    ]

    # ── Iteration history ───────────────────────────────────────────────────
    iteration_history = [
        {
            "iteration": entry.get("iteration", i + 1),
            "sharpe": round(float(entry.get("best_sharpe", 0)), 4),
            "params": entry.get("best_params", {}),
        }
        for i, entry in enumerate(state.opt_iterations)
    ]

    # ── Initial vs final comparison (useful in OPTIMIZE mode) ───────────────
    initial_sharpe = float(backtest_result.get("sharpe_ratio", 0) or 0)
    final_sharpe = float(opt_result.get("best_sharpe", initial_sharpe) or initial_sharpe)
    initial_dd = float(backtest_result.get("max_drawdown", 0) or 0)
    final_dd = float(opt_result.get("best_drawdown", initial_dd) or initial_dd)
    comparison = {
        "initial_sharpe": round(initial_sharpe, 4),
        "final_sharpe": round(final_sharpe, 4),
        "sharpe_improvement": round(final_sharpe - initial_sharpe, 4),
        "initial_drawdown": round(initial_dd, 2),
        "final_drawdown": round(final_dd, 2),
    }

    report = {
        # ── Existing fields ────────────────────────────────────────────────
        "market_analysis": state.get_result("analyze_market"),
        "proposals_count": len((state.get_result("parse_responses") or {}).get("proposals", [])),
        "selected": state.get_result("select_best"),
        "backtest": backtest_result,
        "backtest_analysis": state.get_result("backtest_analysis"),
        "errors": state.errors,
        "execution_path": state.execution_path,
        "pipeline_metrics": {
            "total_cost_usd": round(state.total_cost_usd, 6),
            "llm_call_count": state.llm_call_count,
            "node_timing_s": dict(state.execution_path),
            "total_wall_time_s": round(sum(t for _, t in state.execution_path), 3),
        },
        # ── Phase 8: Enhanced report fields ───────────────────────────────
        "top_trials_table": top_trials_table,
        "iteration_history": iteration_history,
        "opt_insights": state.opt_insights,
        "debate_outcome": state.debate_outcome,
        "comparison": comparison,
        "pipeline_mode": state.pipeline_mode,
    }
    state.set_result("report", report)
    state.add_message("system", "Pipeline report generated", "report")
    return state


# =============================================================================
# GRAPH BUILDER
# =============================================================================


def build_trading_strategy_graph(
    run_backtest: bool = True,
    run_wf_validation: bool = True,
    checkpoint_enabled: bool = False,
    hitl_enabled: bool = False,
    event_fn: Callable[[str, dict[str, Any]], None] | None = None,
    **_kwargs: Any,
) -> AgentGraph:
    """
    Build the full Trading Strategy generation graph.

    Args:
        run_backtest:       If True, includes backtest + memory_update nodes
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
        analyze_market → regime_classifier → memory_recall → grounding → generate_strategies → parse_responses
                                                                                ↑                       │
                                                                                │               select_best (Consensus)
                                                                                │                       │
                                                                       refine_strategy ←           build_graph
                                                                       (iter < 3, fails)                │
                                                                                                    backtest
                                                                                                        │
                                                                                               backtest_analysis
                                                                                                        ├── fails → refine (loop)
                                                                                                        └── passes → optimize_strategy → [wf_validation →] ml_validation
                                                                                                                                                  ↕ refine if fails
                                                                                                                  ml_validation
                                                                                                                        │
                                                                                                      [hitl_check →] memory_update → reflection → report → END
    """
    graph = AgentGraph(
        name="trading_strategy_pipeline",
        description="AI-powered trading strategy generation with Self-MoA + ConsensusEngine",
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

    # Chain: analyze → regime_classifier → memory_recall → grounding → generate → parse → select
    graph.add_edge("analyze_market", "regime_classifier")
    graph.add_node(MemoryRecallNode())
    graph.add_node(GroundingNode())
    graph.add_edge("regime_classifier", "memory_recall")
    graph.add_edge("memory_recall", "grounding")
    graph.add_edge("grounding", "generate_strategies")

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

        # backtest_analysis → [refine | optimize_strategy]
        backtest_router = ConditionalRouter(name="backtest_router")
        backtest_router.add_route(_should_refine, "refine_strategy")
        backtest_router.set_default("optimize_strategy")
        graph.add_conditional_edges("backtest_analysis", backtest_router)

        # After refinement, loop back to regenerate strategies
        graph.add_edge("refine_strategy", "generate_strategies")

        graph.add_node(MLValidationNode())
        # Phase 3: OptimizationAnalysisNode sits between optimizer and WF/ML validation
        # Phase 4: A2AParamRangeNode feeds refined ranges back into OptimizationNode
        graph.add_node(OptimizationAnalysisNode())
        graph.add_node(A2AParamRangeNode())
        graph.add_edge("optimize_strategy", "optimization_analysis")
        # Loop: param_range → optimize_strategy (cycles back)
        graph.add_edge("param_range", "optimize_strategy")

        # Phase 5: AnalysisDebateNode — wired between opt loop exit and WF/ML
        graph.add_node(AnalysisDebateNode())
        # debate_router: reject → reflection (skip save), else → WF/ML
        debate_router = ConditionalRouter(name="debate_router")
        debate_router.add_route(_is_debate_rejected, "reflection")

        # opt_iter_router: continue loop or exit to analysis_debate
        opt_iter_router = ConditionalRouter(name="opt_iter_router")
        opt_iter_router.add_route(_should_continue_opt, "param_range")
        opt_iter_router.set_default("analysis_debate")
        graph.add_conditional_edges("optimization_analysis", opt_iter_router)

        if run_wf_validation:
            # P1-2: walk-forward gate AFTER optimization — WF validates optimized params,
            # not raw IS params.  OptimizationNode stores best_params in state.context
            # ["strategy_graph"] so WalkForwardValidationNode uses the optimized graph.
            graph.add_node(WalkForwardValidationNode())
            wf_router = ConditionalRouter(name="wf_router")
            wf_router.add_route(_should_refine, "refine_strategy")
            wf_router.set_default("ml_validation")
            graph.add_conditional_edges("wf_validation", wf_router)
            debate_router.set_default("wf_validation")
        else:
            debate_router.set_default("ml_validation")

        graph.add_conditional_edges("analysis_debate", debate_router)

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

        graph.add_edge("memory_update", "reflection")  # P1-1: self-reflection before report
        graph.add_edge("reflection", "report")
    else:
        graph.add_edge("select_best", "report")

    graph.set_entry_point("analyze_market")
    graph.add_exit_point("report")

    return graph


async def _load_strategy_graph_from_db(strategy_id: str) -> dict[str, Any] | None:
    """Load a strategy graph (blocks + connections) from the DB by strategy_id.

    Returns a seed_graph dict on success, or None on any error.
    Uses the same builder_get_strategy helper as BuilderWorkflow.
    """
    try:
        from backend.agents.mcp.tools.strategy_builder import builder_get_strategy

        existing = await builder_get_strategy(strategy_id)
        if not isinstance(existing, dict) or "error" in existing:
            logger.warning(f"[Pipeline] Could not load strategy {strategy_id}: {existing}")
            return None

        # Prefer top-level blocks; fall back to builder_graph.blocks (richer params)
        raw_blocks = existing.get("blocks", [])
        raw_connections = existing.get("connections", [])
        graph = existing.get("builder_graph") or {}

        if not raw_blocks or not any(b.get("params") for b in raw_blocks):
            graph_blocks = graph.get("blocks", [])
            if graph_blocks and any(b.get("params") for b in graph_blocks):
                raw_blocks = graph_blocks

        if not raw_connections:
            raw_connections = graph.get("connections", [])

        return {
            "blocks": raw_blocks,
            "connections": raw_connections,
            "name": existing.get("name", f"Strategy {strategy_id[:8]}"),
            "id": strategy_id,
        }
    except Exception as exc:
        logger.warning(f"[Pipeline] _load_strategy_graph_from_db({strategy_id}) error: {exc}")
        return None


async def run_strategy_pipeline(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    agents: list[str] | None = None,
    run_backtest: bool = False,
    run_wf_validation: bool = True,
    initial_capital: float = INITIAL_CAPITAL,
    leverage: int = 1,
    pipeline_timeout: float = 300.0,
    max_cost_usd: float = 0.0,
    checkpoint_enabled: bool = False,
    hitl_enabled: bool = False,
    hitl_approved: bool = False,
    event_fn: Callable[[str, dict[str, Any]], None] | None = None,
    seed_graph: dict[str, Any] | None = None,
    existing_strategy_id: str | None = None,
    **_kwargs: Any,
) -> AgentState:
    """
    Convenience function to run the full strategy generation pipeline.

    Args:
        symbol: Trading pair (e.g. "BTCUSDT")
        timeframe: Candle interval (e.g. "15")
        df: OHLCV DataFrame
        agents: LLM agents to use (default: ["claude"])
        run_backtest: Whether to backtest the generated strategy
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
        seed_graph: Existing Strategy Builder graph dict (blocks + connections).
            When provided, skips LLM generation and runs the pipeline in
            "analysis mode": analyze_market → regime → backtest the existing
            graph → analyze → refine/optimize → report.
            Useful for: "I have a strategy — let agents analyse and improve it."
        existing_strategy_id: Strategy UUID to load from DB as seed_graph.
            When set, the pipeline runs in ``pipeline_mode="optimize"``:
            blocks + connections are fetched from the DB, injected as seed_graph,
            and all LLM generation nodes are skipped.
            Takes precedence over an explicitly passed seed_graph.

    Returns:
        AgentState with all results in state.results
    """
    graph = build_trading_strategy_graph(
        run_backtest=run_backtest,
        run_wf_validation=run_wf_validation,
        checkpoint_enabled=checkpoint_enabled,
        hitl_enabled=hitl_enabled,
        event_fn=event_fn,
    )

    # Pre-flight health check (non-blocking — just warns, never raises)
    from backend.agents.monitoring.provider_health import get_health_monitor

    try:
        await get_health_monitor().preflight_check()
    except Exception as _e:
        logger.debug(f"Preflight check error (non-fatal): {_e}")

    # ── Determine pipeline_mode ──────────────────────────────────────────────
    # existing_strategy_id → load graph from DB → optimize mode
    # seed_graph passed explicitly → optimize mode (caller already loaded it)
    # neither → create mode
    pipeline_mode = "create"
    if existing_strategy_id:
        logger.info(f"[Pipeline] OPTIMIZE mode — loading strategy {existing_strategy_id} from DB")
        loaded = await _load_strategy_graph_from_db(existing_strategy_id)
        if loaded is not None:
            seed_graph = loaded
            pipeline_mode = "optimize"
            logger.info(
                f"[Pipeline] Loaded '{loaded['name']}': "
                f"{len(loaded['blocks'])} blocks, {len(loaded['connections'])} connections"
            )
        else:
            logger.warning(f"[Pipeline] Could not load strategy {existing_strategy_id} — falling back to CREATE mode")
    elif seed_graph is not None:
        pipeline_mode = "optimize"

    context: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "df": df,
        "agents": agents or ["claude"],
        "initial_capital": initial_capital,
        "leverage": leverage,
        "hitl_approved": hitl_approved,  # P2-3: HITL approval flag
        "existing_strategy_id": existing_strategy_id,
    }

    # seed_graph mode: inject existing strategy graph, skip LLM generation nodes
    if seed_graph is not None:
        context["strategy_graph"] = seed_graph
        context["seed_mode"] = True
        context["seed_strategy_name"] = seed_graph.get("name", "Existing Strategy")
        logger.info(
            f"[Pipeline] seed_mode active — strategy='{context['seed_strategy_name']}', "
            f"blocks={len(seed_graph.get('blocks', []))}, "
            f"connections={len(seed_graph.get('connections', []))}"
        )

    initial_state = AgentState(
        context=context,
        max_cost_usd=max_cost_usd,  # P1-5: cost budget
        pipeline_mode=pipeline_mode,
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
