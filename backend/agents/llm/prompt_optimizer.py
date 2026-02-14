"""
Prompt Optimizer for LLM Agent Calls

Reduces token consumption by 30-45% through:
1. Agent-specific metric filtering — each agent gets only metrics it needs
2. Float quantization — round numbers to 3 decimal places
3. Request batching — group up to N backtests into a single prompt
4. Response caching — skip identical prompt_hash calls via LRU cache
5. Dynamic thinking mode — enable CoT only for complex tasks

Created per agent infrastructure analysis recommendations (2026-02-11).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import Any

from loguru import logger


class TaskComplexity(Enum):
    """Task complexity levels for dynamic thinking mode control."""

    SIMPLE = "simple"  # Basic calculations, lookups — no thinking needed
    MODERATE = "moderate"  # Standard analysis — thinking optional
    COMPLEX = "complex"  # Multi-step reasoning, pattern recognition — thinking ON


# ═══════════════════════════════════════════════════════════════════════════
# AGENT-SPECIFIC METRIC FILTERS
# ═══════════════════════════════════════════════════════════════════════════

# Each agent only receives metrics relevant to its specialization.
# This eliminates ~31% of input tokens that were previously wasted.

AGENT_REQUIRED_METRICS: dict[str, set[str]] = {
    "deepseek": {
        # Quantitative analyst: risk metrics & statistical validation
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "var_95",
        "cvar_95",
        "max_drawdown",
        "max_drawdown_pct",
        "win_rate",
        "profit_factor",
        "expectancy",
        "ulcer_index",
        "total_trades",
        "net_profit",
        "net_profit_pct",
        "avg_trade_pnl",
        "avg_trade_pnl_pct",
        "risk_reward_ratio",
        "recovery_factor",
        "payoff_ratio",
    },
    "qwen": {
        # Technical analyst: signal quality & indicator performance
        "win_rate",
        "total_trades",
        "avg_trade_pnl",
        "avg_trade_pnl_pct",
        "avg_win",
        "avg_loss",
        "max_consecutive_wins",
        "max_consecutive_losses",
        "profit_factor",
        "net_profit",
        "net_profit_pct",
        "long_trades",
        "short_trades",
        "long_win_rate",
        "short_win_rate",
        "avg_holding_time",
        "max_drawdown_pct",
        "sharpe_ratio",
        "sortino_ratio",
        "expectancy",
    },
    "perplexity": {
        # Market researcher: high-level performance & context
        "net_profit",
        "net_profit_pct",
        "max_drawdown_pct",
        "win_rate",
        "total_trades",
        "sharpe_ratio",
        "profit_factor",
        "calmar_ratio",
        "avg_holding_time",
        "risk_reward_ratio",
    },
}

# Metrics all agents always receive (never filtered)
UNIVERSAL_METRICS: set[str] = {
    "net_profit",
    "net_profit_pct",
    "total_trades",
    "win_rate",
    "max_drawdown_pct",
    "sharpe_ratio",
}

# ═══════════════════════════════════════════════════════════════════════════
# TASK COMPLEXITY CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════

# Keywords that indicate task complexity for thinking mode decisions
COMPLEX_TASK_KEYWORDS: set[str] = {
    "optimize",
    "compare",
    "analyze",
    "multi-timeframe",
    "pattern",
    "regime",
    "correlation",
    "drawdown_analysis",
    "strategy_evolution",
    "portfolio",
    "risk_assessment",
    "backtest_review",
    "deliberation",
    "consensus",
    "cross-validate",
    "monte_carlo",
    "walk_forward",
}

SIMPLE_TASK_KEYWORDS: set[str] = {
    "calculate",
    "get",
    "fetch",
    "lookup",
    "status",
    "health",
    "list",
    "count",
    "summarize",
    "format",
    "validate_basic",
    "rsi",
    "macd",
    "ema",
    "sma",
    "bollinger",
}

# ═══════════════════════════════════════════════════════════════════════════
# FLOAT PRECISION SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

# Default precision for metrics (3 decimal places saves ~14% tokens)
DEFAULT_FLOAT_PRECISION = 3

# Override precision for specific metrics that need more/less
METRIC_PRECISION_OVERRIDES: dict[str, int] = {
    "net_profit": 2,
    "avg_trade_pnl": 2,
    "avg_win": 2,
    "avg_loss": 2,
    "sharpe_ratio": 3,
    "sortino_ratio": 3,
    "calmar_ratio": 3,
    "win_rate": 2,
    "max_drawdown_pct": 2,
    "net_profit_pct": 2,
    "var_95": 2,
    "cvar_95": 2,
}


@dataclass
class OptimizationStats:
    """Track optimization statistics for monitoring."""

    total_calls: int = 0
    tokens_saved_estimate: int = 0
    cache_hits: int = 0
    metrics_filtered: int = 0
    floats_quantized: int = 0
    thinking_mode_skipped: int = 0
    batch_calls_merged: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "tokens_saved_estimate": self.tokens_saved_estimate,
            "cache_hits": self.cache_hits,
            "metrics_filtered": self.metrics_filtered,
            "floats_quantized": self.floats_quantized,
            "thinking_mode_skipped": self.thinking_mode_skipped,
            "batch_calls_merged": self.batch_calls_merged,
        }


class PromptOptimizer:
    """
    Optimizes LLM prompts to reduce token consumption and costs.

    Usage:
        optimizer = PromptOptimizer()

        # Filter metrics for a specific agent
        filtered = optimizer.filter_metrics_for_agent("deepseek", full_metrics)

        # Quantize floats in a dict
        quantized = optimizer.quantize_floats(metrics_dict)

        # Classify task complexity for thinking mode
        complexity = optimizer.classify_task_complexity("analyze RSI divergence pattern")

        # Check if thinking mode should be enabled
        should_think = optimizer.should_enable_thinking("deepseek", "calculate RSI")

        # Full optimization pipeline
        optimized_prompt = optimizer.optimize_prompt("deepseek", prompt, metrics)
    """

    # LRU cache for identical prompts (keyed by prompt hash)
    CACHE_MAX_SIZE = 256
    CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self):
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self.stats = OptimizationStats()

    # ─── Metric Filtering ─────────────────────────────────────────────

    def filter_metrics_for_agent(
        self,
        agent_type: str,
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Filter metrics to only include those relevant to the agent's role.

        Args:
            agent_type: "deepseek", "qwen", or "perplexity"
            metrics: Full metrics dictionary

        Returns:
            Filtered metrics dict containing only agent-relevant keys
        """
        agent_key = agent_type.lower()
        allowed = AGENT_REQUIRED_METRICS.get(agent_key, set()) | UNIVERSAL_METRICS

        filtered = {}
        removed_count = 0

        for key, value in metrics.items():
            if key in allowed:
                filtered[key] = value
            else:
                removed_count += 1

        self.stats.metrics_filtered += removed_count

        if removed_count > 0:
            logger.debug(f"Filtered {removed_count} metrics for {agent_type} ({len(filtered)}/{len(metrics)} kept)")

        return filtered

    # ─── Float Quantization ───────────────────────────────────────────

    def quantize_floats(
        self,
        data: dict[str, Any],
        precision: int | None = None,
    ) -> dict[str, Any]:
        """
        Round all float values to reduce token count.

        Saves ~14% tokens by removing unnecessary decimal places.
        Uses metric-specific precision where configured.

        Args:
            data: Dictionary with float values
            precision: Override precision (uses per-metric defaults if None)

        Returns:
            Dictionary with quantized float values
        """
        quantized = {}
        for key, value in data.items():
            if isinstance(value, float):
                p = precision or METRIC_PRECISION_OVERRIDES.get(key, DEFAULT_FLOAT_PRECISION)
                quantized[key] = round(value, p)
                self.stats.floats_quantized += 1
            elif isinstance(value, dict):
                quantized[key] = self.quantize_floats(value, precision)
            elif isinstance(value, list):
                quantized[key] = [
                    round(v, precision or DEFAULT_FLOAT_PRECISION) if isinstance(v, float) else v for v in value
                ]
            else:
                quantized[key] = value
        return quantized

    # ─── Task Complexity Classification ───────────────────────────────

    def classify_task_complexity(self, task_description: str) -> TaskComplexity:
        """
        Classify task complexity to decide whether thinking mode is warranted.

        Args:
            task_description: Description of the task (task_type + prompt snippet)

        Returns:
            TaskComplexity enum value
        """
        text_lower = task_description.lower()

        # Check for complex indicators
        complex_matches = sum(1 for kw in COMPLEX_TASK_KEYWORDS if kw in text_lower)
        simple_matches = sum(1 for kw in SIMPLE_TASK_KEYWORDS if kw in text_lower)

        # Heuristics based on prompt length and structure
        has_multiple_questions = text_lower.count("?") > 1
        has_comparison = any(w in text_lower for w in ["vs", "versus", "compare", "better"])
        prompt_length = len(task_description)

        if complex_matches >= 2 or has_comparison or has_multiple_questions:
            return TaskComplexity.COMPLEX
        elif complex_matches == 1 and simple_matches == 0:
            return TaskComplexity.MODERATE
        elif simple_matches >= 1 or prompt_length < 100:
            return TaskComplexity.SIMPLE
        elif prompt_length > 500:
            return TaskComplexity.COMPLEX
        else:
            return TaskComplexity.MODERATE

    def should_enable_thinking(
        self,
        agent_type: str,
        task_description: str,
    ) -> bool:
        """
        Decide whether to enable thinking mode for a Qwen request.

        Thinking mode adds 40-60% token overhead. Only enable for complex tasks
        where multi-step reasoning provides clear value.
        Blocked by default unless QWEN_ENABLE_THINKING=true.

        Args:
            agent_type: "deepseek", "qwen", or "perplexity"
            task_description: Combined task_type + prompt

        Returns:
            True if thinking mode should be enabled
        """
        import os

        # Only Qwen supports dynamic thinking mode toggle
        if agent_type.lower() != "qwen":
            return False

        # Cost guard: respect env var override
        allow_thinking = os.getenv("QWEN_ENABLE_THINKING", "false").lower() == "true"
        if not allow_thinking:
            self.stats.thinking_mode_skipped += 1
            logger.debug(f"Thinking mode BLOCKED by QWEN_ENABLE_THINKING=false: {task_description[:60]}...")
            return False

        complexity = self.classify_task_complexity(task_description)

        if complexity == TaskComplexity.SIMPLE:
            self.stats.thinking_mode_skipped += 1
            logger.debug(f"Thinking mode SKIPPED for simple task: {task_description[:60]}...")
            return False
        elif complexity == TaskComplexity.COMPLEX:
            return True
        else:
            # Moderate: enable thinking only if prompt is substantial
            return len(task_description) > 300

    # ─── Compact JSON Serialization ───────────────────────────────────

    def compact_json(self, data: dict[str, Any]) -> str:
        """
        Serialize to minimal JSON (no extra whitespace).

        Saves ~18-22% tokens compared to pretty-printed JSON.
        """
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    # ─── Prompt Caching ───────────────────────────────────────────────

    def _prompt_hash(self, agent_type: str, prompt: str) -> str:
        """Generate hash for prompt deduplication."""
        raw = f"{agent_type}:{prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get_cached_response(self, agent_type: str, prompt: str) -> str | None:
        """
        Check if an identical prompt was recently answered.

        Returns cached response if found and not expired.
        """
        key = self._prompt_hash(agent_type, prompt)
        if key in self._cache:
            response, timestamp = self._cache[key]
            if time.time() - timestamp < self.CACHE_TTL_SECONDS:
                self.stats.cache_hits += 1
                # Move to end (LRU)
                self._cache.move_to_end(key)
                logger.debug(f"Cache HIT for {agent_type} prompt (hash={key})")
                return response
            else:
                # Expired
                del self._cache[key]
        return None

    def cache_response(self, agent_type: str, prompt: str, response: str) -> None:
        """Cache a prompt-response pair."""
        key = self._prompt_hash(agent_type, prompt)
        self._cache[key] = (response, time.time())
        # Evict oldest if over limit
        while len(self._cache) > self.CACHE_MAX_SIZE:
            self._cache.popitem(last=False)

    # ─── Batch Optimization ───────────────────────────────────────────

    def batch_metrics_prompt(
        self,
        agent_type: str,
        backtests: list[dict[str, Any]],
        max_batch_size: int = 5,
    ) -> list[str]:
        """
        Batch multiple backtest metrics into fewer prompts.

        Instead of N separate API calls, group up to max_batch_size
        backtests into a single prompt with indexed results.

        Args:
            agent_type: Agent type for metric filtering
            backtests: List of backtest result dicts with metrics
            max_batch_size: Max backtests per batch prompt

        Returns:
            List of batch prompt strings
        """
        prompts = []

        for i in range(0, len(backtests), max_batch_size):
            batch = backtests[i : i + max_batch_size]
            merged = i > 0
            if merged:
                self.stats.batch_calls_merged += len(batch) - 1

            parts = []
            for idx, bt in enumerate(batch):
                metrics = bt.get("metrics", bt)
                filtered = self.filter_metrics_for_agent(agent_type, metrics)
                quantized = self.quantize_floats(filtered)

                parts.append(
                    f"[Backtest #{i + idx + 1}] "
                    f"Symbol: {bt.get('symbol', 'N/A')}, "
                    f"Strategy: {bt.get('strategy_type', 'N/A')}\n"
                    f"Metrics: {self.compact_json(quantized)}"
                )

            prompt = (
                f"Analyze the following {len(batch)} backtest(s) and provide "
                f"your assessment for each:\n\n"
                + "\n\n".join(parts)
                + "\n\nProvide a structured response for each backtest."
            )
            prompts.append(prompt)

        return prompts

    # ─── Full Optimization Pipeline ───────────────────────────────────

    def optimize_prompt(
        self,
        agent_type: str,
        prompt: str,
        metrics: dict[str, Any] | None = None,
    ) -> str:
        """
        Full optimization pipeline for a prompt.

        1. Filter metrics for agent
        2. Quantize floats
        3. Compact JSON serialization
        4. Inject optimized metrics into prompt

        Args:
            agent_type: "deepseek", "qwen", or "perplexity"
            prompt: Original prompt text
            metrics: Optional metrics dict to optimize and inject

        Returns:
            Optimized prompt string
        """
        self.stats.total_calls += 1

        if metrics:
            filtered = self.filter_metrics_for_agent(agent_type, metrics)
            quantized = self.quantize_floats(filtered)
            compact = self.compact_json(quantized)

            # Replace any existing JSON metrics block in prompt
            # Look for patterns like {...} with metric keys
            json_pattern = re.compile(
                r'\{[^{}]*"(?:sharpe_ratio|net_profit|win_rate|total_trades)[^{}]*\}',
                re.DOTALL,
            )
            if json_pattern.search(prompt):
                prompt = json_pattern.sub(compact, prompt, count=1)
            else:
                # Append metrics at end
                prompt = f"{prompt}\n\nMetrics:\n{compact}"

        return prompt

    def get_stats(self) -> dict[str, Any]:
        """Get optimization statistics."""
        return self.stats.to_dict()

    def reset_stats(self) -> None:
        """Reset optimization statistics."""
        self.stats = OptimizationStats()


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

_optimizer: PromptOptimizer | None = None


def get_prompt_optimizer() -> PromptOptimizer:
    """Get or create the global PromptOptimizer instance."""
    global _optimizer
    if _optimizer is None:
        _optimizer = PromptOptimizer()
        logger.info("📊 PromptOptimizer initialized")
    return _optimizer


__all__ = [
    "AGENT_REQUIRED_METRICS",
    "PromptOptimizer",
    "TaskComplexity",
    "get_prompt_optimizer",
]
