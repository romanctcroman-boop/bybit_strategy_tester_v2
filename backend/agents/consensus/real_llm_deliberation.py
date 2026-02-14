"""
Real LLM Deliberation Integration

Connects MultiAgentDeliberation with real LLM APIs (DeepSeek, Qwen, Perplexity).
This module creates an enhanced deliberation system that uses actual AI responses
from 3 specialized agents for robust multi-agent consensus.

Agent Specializations:
- DeepSeek: Quantitative analyst — conservative, data-driven strategies
- Qwen: Technical analyst — momentum, pattern recognition, indicator optimization
- Perplexity: Market researcher — real-time sentiment, macro trends, web-sourced insights

P2 Fix (2026-01-28): Now uses KeyManager for secure API key access instead of os.environ.
P2 Update (2026-02-09): Full 3-agent Qwen integration with specialized system prompts.
P2 Update (2026-02-11): Deep Perplexity integration — context enrichment,
    cross-validation, structured data exchange between agents.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

# Use KeyManager for secure API key access
try:
    from backend.security.key_manager import get_key_manager

    _key_manager = get_key_manager()
except ImportError:
    logger.warning("KeyManager not available, falling back to environment variables")
    _key_manager = None

import os


def _get_api_key(key_name: str) -> str | None:
    """
    Get API key securely via KeyManager, fallback to env.

    Args:
        key_name: Name of the key (e.g., "DEEPSEEK_API_KEY")

    Returns:
        Decrypted API key or None
    """
    if _key_manager:
        try:
            return _key_manager.get_decrypted_key(key_name)
        except Exception as e:
            logger.debug(f"KeyManager failed for {key_name}: {e}")

    # Fallback to environment
    return os.environ.get(key_name)


from backend.agents.consensus.deliberation import (
    DeliberationResult,
    MultiAgentDeliberation,
    VotingStrategy,
)
from backend.agents.consensus.perplexity_integration import (
    AgentSignal,
    get_perplexity_integration,
)
from backend.agents.llm.connections import (
    DeepSeekClient,
    LLMConfig,
    LLMMessage,
    LLMProvider,
    PerplexityClient,
    QwenClient,
)


class RealLLMDeliberation(MultiAgentDeliberation):
    """
    Multi-Agent Deliberation with real LLM API calls and deep Perplexity integration.

    Extends MultiAgentDeliberation to use actual DeepSeek/Qwen/Perplexity APIs
    instead of simulated responses. Each agent has a specialized system prompt
    matching its domain expertise.

    Deep Perplexity Integration (v2):
        - **Context Enrichment**: Perplexity is called first to gather real-time
          market data, then DeepSeek/Qwen receive enriched prompts.
        - **Structured Signals**: Agents exchange structured AgentSignal objects
          instead of raw text, enabling cross-validation.
        - **Cross-Validation**: After all agents respond, signals are cross-validated
          to detect conflicts and calculate agreement scores.
        - **Adaptive Routing**: Perplexity is only consulted when the task benefits
          from web-search context (saves costs for pure backtest tasks).

    Agent Roles:
        - **deepseek**: Quantitative analyst — risk metrics, statistical validation,
          conservative approach to strategy design.
        - **qwen**: Technical analyst — momentum analysis, indicator optimization,
          pattern recognition, moderate risk tolerance.
        - **perplexity**: Market researcher — real-time sentiment, macro context,
          news-driven insights with web search capability.

    Example:
        deliberation = RealLLMDeliberation()

        result = await deliberation.deliberate(
            question="Should I use RSI or MACD for BTC entry signals?",
            agents=["deepseek", "qwen", "perplexity"],
            max_rounds=2,
        )

        print(f"Decision: {result.decision}")
        print(f"Confidence: {result.confidence:.2%}")
    """

    # Agent-specific system prompts with trading domain specialization
    AGENT_SYSTEM_PROMPTS: dict[str, str] = {
        "deepseek": (
            "You are a quantitative trading analyst participating in a multi-agent deliberation. "
            "Your expertise: statistical analysis, risk management, Sharpe ratio optimization, "
            "drawdown control, and evidence-based decision making. "
            "You prefer conservative, data-validated strategies with strong risk-adjusted returns. "
            "Always consider commission impact (0.07%) and realistic slippage. "
            "Follow the exact format specified in the prompt."
        ),
        "qwen": (
            "You are a technical analysis expert participating in a multi-agent deliberation. "
            "Your expertise: momentum indicators (RSI, MACD, Stochastic), moving average systems, "
            "Bollinger Bands, pattern recognition, and indicator parameter optimization. "
            "You balance signal quality with trade frequency, preferring robust indicator combinations. "
            "Consider timeframe alignment and multi-timeframe confirmation. "
            "Follow the exact format specified in the prompt."
        ),
        "perplexity": (
            "You are a market research analyst participating in a multi-agent deliberation. "
            "Your expertise: market regime analysis, sentiment indicators, macro trends, "
            "volatility cycles, and event-driven strategy adjustments. "
            "You bring real-time market context and broader economic perspective. "
            "Consider market conditions, correlation shifts, and regime changes. "
            "When providing signals, always include current market regime and sentiment direction. "
            "Follow the exact format specified in the prompt."
        ),
    }

    # Default system prompt for unknown agents
    DEFAULT_SYSTEM_PROMPT = (
        "You are an expert AI agent participating in a multi-agent deliberation. "
        "You must analyze the question carefully and provide a well-reasoned response. "
        "Follow the exact format specified in the prompt."
    )

    def __init__(self, enable_perplexity_enrichment: bool = True):
        """
        Initialize with real LLM clients and Perplexity integration.

        Args:
            enable_perplexity_enrichment: If True, Perplexity is called first
                to enrich context before DeepSeek/Qwen analyze. Adaptive routing
                still applies (skips pure backtest tasks).
        """
        super().__init__()

        self._clients: dict[str, Any] = {}
        self._initialize_clients()

        # Perplexity deep integration
        self._perplexity_integration = get_perplexity_integration()
        self._enable_enrichment = enable_perplexity_enrichment
        self._last_market_context: dict[str, Any] | None = None
        self._last_cross_validation: dict[str, Any] | None = None
        self._agent_signals: list[AgentSignal] = []

        # Override ask_fn to use real LLM
        self.ask_fn = self._real_ask

        logger.info(
            "🤖 RealLLMDeliberation initialized with actual LLM APIs "
            f"(perplexity_enrichment={enable_perplexity_enrichment})"
        )

    def _initialize_clients(self) -> None:
        """Initialize LLM clients using KeyManager for secure key access"""
        # DeepSeek - use KeyManager
        deepseek_key = _get_api_key("DEEPSEEK_API_KEY")
        if deepseek_key:
            config = LLMConfig(
                provider=LLMProvider.DEEPSEEK,
                api_key=deepseek_key,
                model="deepseek-chat",
                temperature=0.7,
                max_tokens=2048,
            )
            self._clients["deepseek"] = DeepSeekClient(config)
            logger.info("✅ DeepSeek client ready (via KeyManager)")
        else:
            logger.warning("⚠️ DEEPSEEK_API_KEY not found in KeyManager or environment")

        # Perplexity - use KeyManager, upgraded model for deeper analysis
        perplexity_key = _get_api_key("PERPLEXITY_API_KEY")
        if perplexity_key:
            perplexity_model = os.getenv("PERPLEXITY_MODEL", "sonar-pro")
            config = LLMConfig(
                provider=LLMProvider.PERPLEXITY,
                api_key=perplexity_key,
                model=perplexity_model,
                temperature=0.4,
                max_tokens=2048,
            )
            self._clients["perplexity"] = PerplexityClient(config)
            logger.info(f"✅ Perplexity client ready (model={perplexity_model}, via KeyManager)")
        else:
            logger.warning("⚠️ PERPLEXITY_API_KEY not found in KeyManager or environment")

        # Qwen - use KeyManager
        qwen_key = _get_api_key("QWEN_API_KEY")
        if qwen_key:
            config = LLMConfig(
                provider=LLMProvider.QWEN,
                api_key=qwen_key,
                model="qwen-plus",
                temperature=0.4,
                max_tokens=2048,
            )
            self._clients["qwen"] = QwenClient(config)
            logger.info("✅ Qwen client ready (via KeyManager)")
        else:
            logger.warning("⚠️ QWEN_API_KEY not found in KeyManager or environment")

    async def _real_ask(self, agent_type: str, prompt: str) -> str:
        """
        Ask real LLM for response with agent-specific system prompt.

        Enhanced with Perplexity context enrichment: if market context is
        available from a prior enrich_for_deliberation() call, DeepSeek and
        Qwen receive enriched prompts automatically.

        Args:
            agent_type: Agent name — "deepseek", "qwen", or "perplexity"
            prompt: The deliberation prompt to send

        Returns:
            LLM response text
        """
        client = self._clients.get(agent_type.lower())

        if not client:
            logger.warning(f"No client for {agent_type}, using fallback")
            return self._simulate_response(agent_type, prompt)

        try:
            # Use agent-specific system prompt for domain specialization
            system_prompt = self.AGENT_SYSTEM_PROMPTS.get(agent_type.lower(), self.DEFAULT_SYSTEM_PROMPT)

            # Enrich prompt for DeepSeek/Qwen with Perplexity market context
            enriched_prompt = prompt
            if agent_type.lower() in ("deepseek", "qwen") and self._last_market_context:
                enriched_prompt = self._perplexity_integration.build_enriched_prompt(
                    agent_type=agent_type.lower(),
                    base_prompt=prompt,
                    market_context=self._last_market_context,
                    peer_signals=self._agent_signals if self._agent_signals else None,
                )

            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=enriched_prompt),
            ]

            response = await client.chat(messages)

            logger.debug(
                f"🤖 {agent_type} response: {len(response.content)} chars, "
                f"{response.total_tokens} tokens, {response.latency_ms:.0f}ms"
                f"{' [enriched]' if enriched_prompt != prompt else ''}"
            )

            return response.content

        except Exception as e:
            logger.error(f"LLM request failed for {agent_type}: {e}")
            return self._simulate_response(agent_type, prompt)

    async def enrich_for_deliberation(
        self,
        question: str,
        symbol: str = "BTCUSDT",
        strategy_type: str = "general",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Pre-enrich context with Perplexity before starting deliberation.

        Call this BEFORE deliberate() to give DeepSeek/Qwen real-time
        market context. The enriched context is stored internally and
        automatically injected into agent prompts.

        Args:
            question: The deliberation question (used to determine relevance)
            symbol: Trading symbol for market context
            strategy_type: Strategy type for context
            context: Additional context dict

        Returns:
            Market context dict if enrichment occurred, None if skipped
        """
        if not self._enable_enrichment:
            logger.debug("Perplexity enrichment disabled")
            return None

        # Check if Perplexity should be consulted for this task
        if not self._perplexity_integration.should_consult_perplexity(question):
            logger.debug(f"Perplexity skipped (task doesn't need web context): {question[:60]}")
            return None

        try:
            enriched = await self._perplexity_integration.enrich_context(
                symbol=symbol,
                strategy_type=strategy_type,
                base_context=context or {},
            )

            self._last_market_context = enriched.get("market_context")

            logger.info(
                f"🟣 Deliberation enriched with Perplexity context for {symbol} "
                f"(regime={self._last_market_context.get('regime', '?') if self._last_market_context else '?'})"
            )

            return self._last_market_context

        except Exception as e:
            logger.warning(f"Perplexity enrichment failed (non-fatal): {e}")
            return None

    def record_agent_signal(
        self,
        agent: str,
        signal_type: str,
        direction: str,
        confidence: float,
        reasoning: str,
        data: dict[str, Any] | None = None,
    ) -> AgentSignal:
        """
        Record a structured signal from an agent for cross-validation.

        Call this after each agent responds during deliberation to build
        a structured signal log. Signals are automatically cross-validated
        and shared with subsequent agents.

        Args:
            agent: Agent name (e.g., "deepseek")
            signal_type: Signal domain ("quantitative", "technical", "sentiment")
            direction: Signal direction ("bullish", "bearish", "neutral")
            confidence: Confidence level (0.0 - 1.0)
            reasoning: Brief reasoning string
            data: Optional additional data dict

        Returns:
            Created AgentSignal
        """
        signal = AgentSignal(
            agent=agent,
            signal_type=signal_type,
            direction=direction,
            confidence=confidence,
            reasoning=reasoning,
            data=data or {},
        )
        self._agent_signals.append(signal)

        logger.debug(f"📊 Signal recorded: {agent} → {direction} (conf={confidence:.0%}, type={signal_type})")

        return signal

    def cross_validate(self) -> dict[str, Any] | None:
        """
        Cross-validate all recorded agent signals.

        Detects conflicts between agents and provides resolution
        recommendations. Call after all agents have responded.

        Returns:
            Cross-validation result dict, or None if < 2 signals
        """
        if len(self._agent_signals) < 2:
            logger.debug("Not enough signals for cross-validation")
            return None

        result = self._perplexity_integration.cross_validate_signals(self._agent_signals)
        self._last_cross_validation = result.to_dict()

        if not result.agents_agree:
            logger.warning(
                f"⚠️ Agent conflict detected! Agreement score: {result.agreement_score:.0%}. "
                f"Conflicts: {len(result.conflicts)}"
            )
        else:
            logger.info(f"✅ Agents agree (score={result.agreement_score:.0%})")

        return self._last_cross_validation

    def get_integration_stats(self) -> dict[str, Any]:
        """
        Get combined stats from deliberation and Perplexity integration.

        Returns:
            Dict with deliberation stats + Perplexity integration stats
        """
        return {
            "deliberation": dict(self.stats),
            "perplexity_integration": self._perplexity_integration.get_stats(),
            "signals_recorded": len(self._agent_signals),
            "last_cross_validation": self._last_cross_validation,
            "market_context_available": self._last_market_context is not None,
        }

    def clear_session(self) -> None:
        """Clear session-specific state (signals, context) for a new deliberation."""
        self._agent_signals.clear()
        self._last_market_context = None
        self._last_cross_validation = None
        logger.debug("🔄 Deliberation session cleared")

    async def close(self) -> None:
        """Close all LLM clients and Perplexity integration"""
        for name, client in self._clients.items():
            try:
                await client.close()
                logger.info(f"Closed {name} client")
            except Exception as e:
                logger.warning(f"Error closing {name}: {e}")

        self._clients.clear()

        # Close Perplexity integration
        try:
            await self._perplexity_integration.close()
        except Exception as e:
            logger.warning(f"Error closing Perplexity integration: {e}")


# Global instance
_real_deliberation: RealLLMDeliberation | None = None


def get_real_deliberation() -> RealLLMDeliberation:
    """Get or create RealLLMDeliberation singleton"""
    global _real_deliberation
    if _real_deliberation is None:
        _real_deliberation = RealLLMDeliberation()
    return _real_deliberation


async def deliberate_with_llm(
    question: str,
    agents: list[str] | None = None,
    max_rounds: int = 2,
    min_confidence: float = 0.7,
    voting_strategy: VotingStrategy = VotingStrategy.WEIGHTED,
    symbol: str = "BTCUSDT",
    strategy_type: str = "general",
    enrich_with_perplexity: bool = True,
) -> DeliberationResult:
    """
    Convenience function for real LLM deliberation with Perplexity enrichment.

    Automatically:
    1. Uses all available agents (up to 3: deepseek, qwen, perplexity)
    2. Enriches context with Perplexity web-search (if relevant to the task)
    3. Cross-validates signals after deliberation

    Falls back to deepseek-only if no agents have API keys configured.

    Args:
        question: Question to deliberate
        agents: List of agent types (default: all available agents)
        max_rounds: Max deliberation rounds
        min_confidence: Min confidence for consensus
        voting_strategy: Voting strategy to use
        symbol: Trading symbol for Perplexity context
        strategy_type: Strategy type for context enrichment
        enrich_with_perplexity: Whether to pre-enrich with Perplexity

    Returns:
        DeliberationResult with real AI responses
    """
    deliberation = get_real_deliberation()

    # Clear previous session state
    deliberation.clear_session()

    # Default to all available agents (up to 3)
    if agents is None:
        available = list(deliberation._clients.keys())
        agents = available if available else ["deepseek"]

    # Pre-enrich context with Perplexity (adaptive — may skip for backtest tasks)
    if enrich_with_perplexity and "perplexity" in agents:
        await deliberation.enrich_for_deliberation(
            question=question,
            symbol=symbol,
            strategy_type=strategy_type,
        )

    result = await deliberation.deliberate(
        question=question,
        agents=agents,
        max_rounds=max_rounds,
        min_confidence=min_confidence,
        voting_strategy=voting_strategy,
    )

    # Post-deliberation cross-validation
    cross_val = deliberation.cross_validate()
    if cross_val:
        result.metadata["cross_validation"] = cross_val

    return result


__all__ = [
    "AgentSignal",
    "RealLLMDeliberation",
    "deliberate_with_llm",
    "get_real_deliberation",
]
