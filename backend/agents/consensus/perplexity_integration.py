"""
Enhanced Perplexity Integration for Multi-Agent Deliberation

Provides deep integration between Perplexity (web-search agent) and
DeepSeek/Qwen through:

1. **Context Enrichment**: Perplexity enriches prompts with real-time market context
   before DeepSeek/Qwen analyze strategies.
2. **Structured Data Exchange**: JSON protocol for inter-agent communication
   instead of raw text.
3. **Cross-Validation**: Agents can challenge each other's findings with
   structured disagreement resolution.
4. **Adaptive Routing**: Perplexity is called selectively based on task relevance
   (saves costs when web context isn't needed).

Created per agent infrastructure analysis recommendations (2026-02-11).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from backend.agents.llm.connections import PerplexityClient


class PerplexityRelevance(Enum):
    """When to invoke Perplexity in the pipeline."""

    ALWAYS = "always"  # Every deliberation
    HIGH_VOLATILITY = "high_volatility"  # Only when market is volatile
    NEWS_SENSITIVE = "news_sensitive"  # Strategy depends on macro events
    NEVER = "never"  # Skip Perplexity entirely (backtest-only mode)
    AUTO = "auto"  # Decide based on task keywords


# Keywords indicating Perplexity should be consulted
PERPLEXITY_TRIGGER_KEYWORDS: set[str] = {
    "sentiment",
    "news",
    "macro",
    "fed",
    "fomc",
    "regulation",
    "halving",
    "etf",
    "whale",
    "liquidation",
    "crash",
    "pump",
    "dump",
    "black swan",
    "event",
    "breaking",
    "announcement",
    "ban",
    "sec",
    "exchange",
    "hack",
    "exploit",
    "live",
    "current",
    "today",
    "real-time",
    "market conditions",
    "volatility regime",
}

# Keywords where Perplexity adds little value
PERPLEXITY_SKIP_KEYWORDS: set[str] = {
    "backtest",
    "historical",
    "calculate",
    "rsi",
    "macd",
    "optimize parameters",
    "sharpe ratio",
    "drawdown",
    "commission",
}


@dataclass
class AgentSignal:
    """Structured signal from an agent for cross-validation."""

    agent: str
    signal_type: str  # "technical", "quantitative", "sentiment"
    direction: str  # "bullish", "bearish", "neutral"
    confidence: float  # 0.0 - 1.0
    reasoning: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "signal_type": self.signal_type,
            "direction": self.direction,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "data": self.data,
            "timestamp": self.timestamp,
        }

    def to_compact(self) -> str:
        """Compact representation for inter-agent prompts."""
        return f"[{self.agent}] {self.direction.upper()} (conf={self.confidence:.0%}): {self.reasoning[:120]}"


@dataclass
class CrossValidationResult:
    """Result of cross-validating signals between agents."""

    agents_agree: bool
    agreement_score: float  # 0.0 (total disagreement) to 1.0 (full agreement)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    resolution: str = ""
    signals: list[AgentSignal] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agents_agree": self.agents_agree,
            "agreement_score": self.agreement_score,
            "conflicts": self.conflicts,
            "resolution": self.resolution,
            "signals": [s.to_dict() for s in self.signals],
        }


class PerplexityIntegration:
    """
    Deep integration layer for Perplexity with DeepSeek and Qwen.

    Usage:
        integration = PerplexityIntegration()

        # Determine if Perplexity should be called
        should_call = integration.should_consult_perplexity(
            "analyze BTC momentum with current market context"
        )

        # Enrich context before sending to DeepSeek/Qwen
        enriched = await integration.enrich_context(
            symbol="BTCUSDT",
            strategy_type="rsi",  # Universal RSI block type
            base_context={"timeframe": "15m", "direction": "long"}
        )

        # Cross-validate signals from all agents
        result = integration.cross_validate_signals([
            AgentSignal("deepseek", "quantitative", "bearish", 0.8, "High VaR"),
            AgentSignal("qwen", "technical", "bullish", 0.7, "RSI oversold bounce"),
            AgentSignal("perplexity", "sentiment", "bearish", 0.6, "FED hawkish tone"),
        ])
    """

    # Enhanced system prompts with structured output format
    ENRICHMENT_PROMPT_TEMPLATE = """You are a market research analyst providing real-time context.

Symbol: {symbol}
Strategy Type: {strategy_type}
Timeframe: {timeframe}

Provide a structured market context update:

1. CURRENT MARKET REGIME: Is the market trending, ranging, or volatile?
2. KEY NEWS: Any significant events affecting {symbol} in the last 24-72 hours?
3. SENTIMENT: Overall market sentiment (bullish/bearish/neutral) with confidence.
4. RISK FACTORS: Active risk factors that could affect the strategy.
5. MACRO CONTEXT: Relevant macro events (FED, regulations, etc.)

Format your response as JSON:
{{
    "regime": "trending|ranging|volatile",
    "trend_direction": "up|down|sideways",
    "key_news": ["headline1", "headline2"],
    "sentiment": {{"direction": "bullish|bearish|neutral", "score": 0.0-1.0}},
    "risk_factors": ["factor1", "factor2"],
    "macro_events": ["event1", "event2"],
    "volatility_assessment": "low|normal|high|extreme",
    "confidence": 0.0-1.0
}}
"""

    CROSS_VALIDATION_PROMPT = """You are mediating between AI agents that disagree.

The following agents have provided conflicting signals:

{signals_text}

Analyze the conflict and determine:
1. Which signal is most reliable given current conditions?
2. How should the conflict be resolved?
3. What additional data would help resolve the disagreement?

Format your response as JSON:
{{
    "preferred_signal": "agent_name",
    "resolution_reasoning": "explanation",
    "adjusted_confidence": 0.0-1.0,
    "recommended_action": "proceed|defer|reduce_position|skip",
    "additional_data_needed": ["data1", "data2"]
}}
"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._perplexity_client: PerplexityClient | None = None  # Fixed type annotation
        self._context_cache: dict[str, tuple[float, dict[str, Any]]] = {}  # Fixed to accept (timestamp, data) tuples
        self.cache_ttl_seconds: int = int(config.get("perplexity_cache_ttl", 300))  # Ensuring it's an int
        self.trigger_keywords = PERPLEXITY_TRIGGER_KEYWORDS

        # Initialize relevance setting
        relevance_str = config.get("perplexity_relevance", "auto").upper()
        self.relevance_mode = PerplexityRelevance[relevance_str]

        # Stats tracking
        self._stats = {
            "consultations": 0,
            "cache_hits": 0,
            "avg_response_time": 0.0,
            "errors": 0,
            "calls_skipped": 0,
            "calls_made": 0,
            "enrichments": 0,
            "cross_validations": 0,
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
        }

    def get_client(self) -> PerplexityClient | None:
        """Lazy initialization of Perplexity client."""
        if self._perplexity_client is None:
            try:
                # Try primary config first
                api_key: str | None = self.config.get("perplexity_api_key") or os.getenv("PERPLEXITY_API_KEY")
                if api_key and not api_key.startswith("pplx-YOUR-KEY"):
                    from backend.agents.llm.connections import LLMConfig, LLMProvider
                    from backend.agents.llm.connections import PerplexityClient as PClient

                    config = LLMConfig(
                        provider=LLMProvider.PERPLEXITY,
                        api_key=api_key,
                        model="sonar-pro",
                        temperature=0.2,
                        max_tokens=2048,
                        timeout_seconds=30,
                    )
                    self._perplexity_client = PClient(config)
                    logger.info("🟣 Perplexity integration client initialized")
                else:
                    logger.warning("No valid Perplexity API key found")
            except Exception as e:
                logger.warning(f"Failed to initialize Perplexity client: {e}")
                # Try fallback to env
                fallback_key: str | None = os.getenv("PERPLEXITY_API_KEY")
                if fallback_key and not fallback_key.startswith("pplx-YOUR-KEY"):
                    from backend.agents.llm.connections import LLMConfig, LLMProvider
                    from backend.agents.llm.connections import PerplexityClient as PClient

                    config = LLMConfig(
                        provider=LLMProvider.PERPLEXITY,
                        api_key=fallback_key,
                        model="sonar-pro",
                        temperature=0.2,
                        max_tokens=2048,
                    )
                    self._perplexity_client = PClient(config)
        return self._perplexity_client

    # ─── Adaptive Routing ─────────────────────────────────────────────

    def should_consult_perplexity(self, task_description: str) -> bool:
        """
        Decide whether Perplexity should be consulted for this task.

        Saves costs by skipping Perplexity for pure historical/calculation tasks.

        Args:
            task_description: Full task description or prompt

        Returns:
            True if Perplexity should be consulted
        """
        if self.relevance_mode == PerplexityRelevance.ALWAYS:
            return True
        if self.relevance_mode == PerplexityRelevance.NEVER:
            return False

        text_lower = task_description.lower()

        # Check skip keywords first (more specific)
        skip_score = sum(1 for kw in PERPLEXITY_SKIP_KEYWORDS if kw in text_lower)
        trigger_score = sum(1 for kw in PERPLEXITY_TRIGGER_KEYWORDS if kw in text_lower)

        # If clearly a backtest/calculation, skip
        if skip_score >= 2 and trigger_score == 0:
            self._stats["calls_skipped"] += 1
            logger.debug(f"Perplexity SKIPPED (skip={skip_score}, trigger={trigger_score})")
            return False

        # If any trigger keyword found, consult
        if trigger_score >= 1:
            return True

        # Default: skip for AUTO mode (conservative to save costs)
        self._stats["calls_skipped"] += 1
        return False

    # ─── Context Enrichment ───────────────────────────────────────────

    async def enrich_context(
        self,
        symbol: str,
        strategy_type: str,
        base_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Enrich analysis context with Perplexity's real-time market data.

        Called BEFORE sending prompts to DeepSeek/Qwen so they can
        incorporate market context into their analysis.

        Uses a TTL cache (default 5 minutes) to avoid duplicate API calls
        for the same symbol+strategy_type within the cache window.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            strategy_type: Strategy being analyzed
            base_context: Existing context to enrich

        Returns:
            Enriched context dict with market_context field
        """
        context = dict(base_context or {})

        # ── TTL Cache Check ──
        cache_key = f"{symbol}:{strategy_type}"  # Using string as key instead of tuple
        cached = self._context_cache.get(cache_key)
        if cached is not None:
            cached_ts, cached_data = cached
            age = time.time() - cached_ts
            if age < self.cache_ttl_seconds:
                self._stats["cache_hits"] += 1
                context["market_context"] = cached_data
                context["perplexity_cache_hit"] = True
                context["perplexity_cache_age_s"] = round(age, 1)
                logger.debug(
                    f"🟣 Perplexity cache HIT for {symbol}/{strategy_type} "
                    f"(age={age:.0f}s, TTL={self.cache_ttl_seconds}s)"
                )
                return context

        client = self.get_client()

        if not client:
            logger.warning("Perplexity client not available, returning base context")
            context["market_context"] = {
                "status": "unavailable",
                "reason": "Perplexity client not initialized",
            }
            return context

        try:
            from backend.agents.llm.connections import LLMMessage

            prompt = self.ENRICHMENT_PROMPT_TEMPLATE.format(
                symbol=symbol,
                strategy_type=strategy_type,
                timeframe=context.get("timeframe", "15m"),
            )

            messages = [
                LLMMessage(
                    role="system",
                    content=(
                        "You are a crypto market research analyst. Always respond with valid JSON only, no extra text."
                    ),
                ),
                LLMMessage(role="user", content=prompt),
            ]

            try:
                response = await asyncio.wait_for(client.chat(messages), timeout=30.0)
            except TimeoutError:
                logger.error(f"🟣 Perplexity enrichment timeout for {symbol}/{strategy_type}")
                context["market_context"] = {"status": "timeout", "error": "Perplexity request timed out"}
                return context
            self._stats["calls_made"] += 1
            self._stats["enrichments"] += 1

            # Parse JSON from response
            try:
                market_data = json.loads(response.content)
            except json.JSONDecodeError:
                # Try extracting JSON from markdown code block
                import re

                json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response.content, re.DOTALL)
                if json_match:
                    market_data = json.loads(json_match.group(1))
                else:
                    market_data = {"raw_response": response.content, "parse_error": True}

            context["market_context"] = market_data
            context["perplexity_latency_ms"] = response.latency_ms
            context["perplexity_tokens"] = response.total_tokens
            context["perplexity_cache_hit"] = False

            # Store in TTL cache (only valid responses, not parse errors)
            if not market_data.get("parse_error"):
                self._context_cache[cache_key] = (time.time(), market_data)
                self._evict_expired_cache()

            logger.info(
                f"🟣 Context enriched for {symbol}: "
                f"regime={market_data.get('regime', '?')}, "
                f"sentiment={market_data.get('sentiment', {}).get('direction', '?')}"
            )

        except Exception as e:
            logger.error(f"Context enrichment failed: {e}")
            context["market_context"] = {"status": "error", "error": str(e)}

        return context

    # ─── Cross-Validation ─────────────────────────────────────────────

    def cross_validate_signals(
        self,
        signals: list[AgentSignal],
    ) -> CrossValidationResult:
        """
        Cross-validate signals from multiple agents.

        Detects conflicts between agents and calculates agreement score.
        Does NOT make API calls — this is pure logic.

        Args:
            signals: List of signals from different agents

        Returns:
            CrossValidationResult with agreement analysis
        """
        if len(signals) < 2:
            return CrossValidationResult(
                agents_agree=True,
                agreement_score=1.0,
                signals=signals,
                resolution="Only one signal provided",
            )

        self._stats["cross_validations"] += 1

        # Check direction agreement
        directions = [s.direction for s in signals]
        unique_directions = set(directions)
        all_agree = len(unique_directions) == 1

        # Calculate agreement score
        if all_agree:
            # All same direction — score based on confidence spread
            confidences = [s.confidence for s in signals]
            avg_conf = sum(confidences) / len(confidences)
            conf_spread = max(confidences) - min(confidences)
            agreement_score = avg_conf * (1 - conf_spread * 0.5)
        else:
            # Direction conflict — penalize based on how split they are
            direction_counts: dict[str, int] = {}
            for d in directions:
                direction_counts[d] = direction_counts.get(d, 0) + 1

            majority_count = max(direction_counts.values())
            agreement_score = majority_count / len(signals) * 0.6  # Cap at 0.6 for conflicts

        # Detect specific conflicts
        conflicts = []
        for i, s1 in enumerate(signals):
            for s2 in signals[i + 1 :]:
                if s1.direction != s2.direction:
                    conflict = {
                        "agents": [s1.agent, s2.agent],
                        "directions": [s1.direction, s2.direction],
                        "confidences": [s1.confidence, s2.confidence],
                        "type": self._classify_conflict(s1, s2),
                    }
                    conflicts.append(conflict)
                    self._stats["conflicts_detected"] += 1

        # Generate resolution based on conflicts
        resolution = self._resolve_conflicts(signals, conflicts)

        return CrossValidationResult(
            agents_agree=all_agree,
            agreement_score=round(agreement_score, 3),
            conflicts=conflicts,
            resolution=resolution,
            signals=signals,
        )

    def _classify_conflict(self, s1: AgentSignal, s2: AgentSignal) -> str:
        """Classify the type of conflict between two signals."""
        if s1.signal_type == s2.signal_type:
            return "same_domain_disagreement"
        elif {s1.signal_type, s2.signal_type} == {"technical", "sentiment"}:
            return "technical_vs_sentiment"
        elif {s1.signal_type, s2.signal_type} == {"quantitative", "sentiment"}:
            return "quantitative_vs_sentiment"
        elif {s1.signal_type, s2.signal_type} == {"quantitative", "technical"}:
            return "quantitative_vs_technical"
        return "general_disagreement"

    def _resolve_conflicts(
        self,
        signals: list[AgentSignal],
        conflicts: list[dict[str, Any]],
    ) -> str:
        """
        Generate conflict resolution based on priority rules.

        Priority: quantitative > technical > sentiment (for backtesting)
        For live trading, sentiment would be weighted higher.
        """
        if not conflicts:
            return "No conflicts detected — agents agree"

        self._stats["conflicts_resolved"] += 1

        # Find the signal with highest priority
        priority_order = {"quantitative": 3, "technical": 2, "sentiment": 1}
        best_signal = max(
            signals,
            key=lambda s: (
                priority_order.get(s.signal_type, 0),
                s.confidence,
            ),
        )

        # Check if majority agrees
        direction_counts: dict[str, int] = {}
        for s in signals:
            direction_counts[s.direction] = direction_counts.get(s.direction, 0) + 1

        majority_direction = max(direction_counts, key=direction_counts.get)  # type: ignore[arg-type]
        majority_count = direction_counts[majority_direction]

        if majority_count > len(signals) / 2:
            return (
                f"Majority ({majority_count}/{len(signals)}) favors {majority_direction}. "
                f"Primary signal from {best_signal.agent} ({best_signal.signal_type}). "
                f"Recommended: follow majority with adjusted position size."
            )
        else:
            return (
                f"No clear majority. Highest-priority signal from {best_signal.agent} "
                f"({best_signal.signal_type}, conf={best_signal.confidence:.0%}) "
                f"suggests {best_signal.direction}. "
                f"Recommended: reduce position size due to agent disagreement."
            )

    # ─── Structured Inter-Agent Communication ─────────────────────────

    def build_enriched_prompt(
        self,
        agent_type: str,
        base_prompt: str,
        market_context: dict[str, Any] | None = None,
        peer_signals: list[AgentSignal] | None = None,
    ) -> str:
        """
        Build an enriched prompt that includes Perplexity context
        and peer agent signals.

        Args:
            agent_type: Target agent ("deepseek", "qwen")
            base_prompt: Original prompt
            market_context: Perplexity market context (from enrich_context)
            peer_signals: Signals from other agents for cross-reference

        Returns:
            Enriched prompt string
        """
        parts = [base_prompt]

        # Add market context from Perplexity
        if market_context and market_context.get("status") != "unavailable":
            ctx_summary = self._format_market_context(market_context)
            parts.append(f"\n\n--- Real-Time Market Context (from Perplexity) ---\n{ctx_summary}")

        # Add peer signals for cross-reference
        if peer_signals:
            signals_text = "\n".join(s.to_compact() for s in peer_signals)
            parts.append(
                f"\n\n--- Peer Agent Signals (for cross-reference) ---\n{signals_text}\n"
                f"Consider these signals in your analysis but form your own independent assessment."
            )

        return "\n".join(parts)

    def _format_market_context(self, context: dict[str, Any]) -> str:
        """Format market context for injection into agent prompts."""
        parts = []

        regime = context.get("regime", "unknown")
        direction = context.get("trend_direction", "unknown")
        parts.append(f"Market Regime: {regime} ({direction})")

        sentiment = context.get("sentiment", {})
        if sentiment:
            parts.append(f"Sentiment: {sentiment.get('direction', '?')} (score: {sentiment.get('score', 0):.0%})")

        volatility = context.get("volatility_assessment", "unknown")
        parts.append(f"Volatility: {volatility}")

        news = context.get("key_news", [])
        if news:
            parts.append(f"Key News: {'; '.join(news[:3])}")

        risk_factors = context.get("risk_factors", [])
        if risk_factors:
            parts.append(f"Risk Factors: {'; '.join(risk_factors[:3])}")

        macro = context.get("macro_events", [])
        if macro:
            parts.append(f"Macro Events: {'; '.join(macro[:3])}")

        return "\n".join(parts)

    # ─── Stats & Monitoring ───────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get integration statistics including cache metrics."""
        stats = dict(self._stats)
        stats["cache_size"] = len(self._context_cache)
        stats["cache_ttl_seconds"] = self.cache_ttl_seconds
        return stats

    # ─── Cache Management ─────────────────────────────────────────────

    def _evict_expired_cache(self) -> None:
        """Remove expired entries from the context cache."""
        now = time.time()
        expired_keys = [key for key, (ts, _) in self._context_cache.items() if now - ts >= self.cache_ttl_seconds]
        for key in expired_keys:
            del self._context_cache[key]

    def invalidate_cache(self, symbol: str | None = None) -> int:
        """
        Invalidate cached context data.

        Args:
            symbol: If provided, only invalidate entries for this symbol.
                    If None, clear the entire cache.

        Returns:
            Number of entries removed
        """
        if symbol is None:
            count = len(self._context_cache)
            self._context_cache.clear()
            logger.info(f"🟣 Perplexity cache cleared ({count} entries)")
            return count

        keys_to_remove = [
            key
            for key in self._context_cache
            if (isinstance(key, str) and key.startswith(f"{symbol}:"))
            or (isinstance(key, tuple) and len(key) >= 1 and key[0] == symbol)
        ]
        for key in keys_to_remove:
            del self._context_cache[key]
        if keys_to_remove:
            logger.info(f"🟣 Perplexity cache invalidated for {symbol} ({len(keys_to_remove)} entries)")
        return len(keys_to_remove)

    async def close(self) -> None:
        """Close Perplexity client and clear cache."""
        self._context_cache.clear()
        if self._perplexity_client:
            await self._perplexity_client.close()
            self._perplexity_client = None


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════

_integration: PerplexityIntegration | None = None


def get_perplexity_integration(
    config: dict[str, Any] | None = None,
) -> PerplexityIntegration:
    """Get or create the global PerplexityIntegration instance."""
    global _integration
    if _integration is None:
        _integration = PerplexityIntegration(config or {})
        logger.info("🟣 PerplexityIntegration initialized")
    return _integration


__all__ = [
    "AgentSignal",
    "CrossValidationResult",
    "PerplexityIntegration",
    "PerplexityRelevance",
    "get_perplexity_integration",
]
