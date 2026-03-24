"""
Cost Circuit Breaker

Hard spending limits that BLOCK agent API calls before they are sent.
Unlike CostTracker (which only logs alerts), this module raises
CostLimitExceededError when budget thresholds are breached.

Motivation: ZenML incident — runaway agent loop cost $47K in one session.
Reference: "Cost Circuit Breaker" pattern from production ML systems.

Limits (configurable via env vars):
    AGENT_COST_LIMIT_PER_CALL=2.00     # single Perplexity/DeepSeek call
    AGENT_COST_LIMIT_PER_HOUR=20.00    # rolling 60-minute window
    AGENT_COST_LIMIT_PER_DAY=50.00     # rolling 24-hour window

Usage::

    breaker = get_cost_circuit_breaker()
    breaker.check_before_call(agent="perplexity", estimated_tokens=2000)
    # ... make API call ...
    breaker.record_actual(agent="perplexity", cost_usd=0.0015)
"""

from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


class CostLimitExceededError(RuntimeError):
    """Raised when a hard cost budget limit would be exceeded."""

    def __init__(self, message: str, limit_type: str, limit_usd: float, current_usd: float) -> None:
        super().__init__(message)
        self.limit_type = limit_type
        self.limit_usd = limit_usd
        self.current_usd = current_usd


@dataclass
class _SpendRecord:
    cost_usd: float
    agent: str
    timestamp: float = field(default_factory=time.time)


def _env_float(var: str, default: float) -> float:
    try:
        return float(os.environ.get(var, default))
    except ValueError:
        return default


class CostCircuitBreaker:
    """
    Hard spending limiter for AI agent API calls.

    Maintains a rolling deque of spend records and enforces three limits:
    - Per-call estimate check (before request)
    - Per-hour rolling window
    - Per-day rolling window

    Thread-safety: uses a single deque + Python GIL for single-threaded
    async workloads; sufficient for FastAPI single-process deployment.
    """

    def __init__(
        self,
        limit_per_call_usd: float | None = None,
        limit_per_hour_usd: float | None = None,
        limit_per_day_usd: float | None = None,
    ) -> None:
        self.limit_per_call = limit_per_call_usd or _env_float("AGENT_COST_LIMIT_PER_CALL", 2.00)
        self.limit_per_hour = limit_per_hour_usd or _env_float("AGENT_COST_LIMIT_PER_HOUR", 20.00)
        self.limit_per_day = limit_per_day_usd or _env_float("AGENT_COST_LIMIT_PER_DAY", 50.00)

        # Rolling spend records (kept ≤ 24h)
        self._records: deque[_SpendRecord] = deque()

        # Approximate per-token costs for pre-call estimation (USD/token)
        self._token_costs: dict[str, float] = {
            "perplexity": 0.60 / 1_000_000,   # sonar output rate
            "deepseek":   0.28 / 1_000_000,   # deepseek-chat output rate
            "qwen":       1.20 / 1_000_000,   # qwen3-max output rate
        }

        logger.info(
            f"🛡️ CostCircuitBreaker initialized — "
            f"per_call=${self.limit_per_call:.2f}, "
            f"per_hour=${self.limit_per_hour:.2f}, "
            f"per_day=${self.limit_per_day:.2f}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_before_call(
        self,
        agent: str,
        estimated_tokens: int = 2000,
        estimated_cost_usd: float | None = None,
    ) -> None:
        """
        Check spending limits BEFORE making an API call.

        Raises CostLimitExceededError if any limit would be breached.
        estimated_cost_usd takes priority; falls back to token estimate.
        """
        self._prune_old_records()

        # Estimate call cost
        if estimated_cost_usd is None:
            rate = self._token_costs.get(agent.lower(), 0.30 / 1_000_000)
            estimated_cost_usd = estimated_tokens * rate

        # 1. Per-call limit
        if estimated_cost_usd > self.limit_per_call:
            msg = (
                f"🛡️ COST BLOCKED: Estimated call cost ${estimated_cost_usd:.4f} "
                f"exceeds per-call limit ${self.limit_per_call:.2f} for {agent}"
            )
            logger.error(msg)
            raise CostLimitExceededError(msg, "per_call", self.limit_per_call, estimated_cost_usd)

        # 2. Per-hour rolling window
        hourly = self._sum_since(3600)
        if hourly + estimated_cost_usd > self.limit_per_hour:
            msg = (
                f"🛡️ COST BLOCKED: Hourly spend ${hourly:.4f} + estimated "
                f"${estimated_cost_usd:.4f} would exceed limit ${self.limit_per_hour:.2f}"
            )
            logger.error(msg)
            raise CostLimitExceededError(msg, "per_hour", self.limit_per_hour, hourly)

        # 3. Per-day rolling window
        daily = self._sum_since(86400)
        if daily + estimated_cost_usd > self.limit_per_day:
            msg = (
                f"🛡️ COST BLOCKED: Daily spend ${daily:.4f} + estimated "
                f"${estimated_cost_usd:.4f} would exceed limit ${self.limit_per_day:.2f}"
            )
            logger.error(msg)
            raise CostLimitExceededError(msg, "per_day", self.limit_per_day, daily)

        logger.debug(
            f"🛡️ Cost check OK: {agent} ~${estimated_cost_usd:.4f} "
            f"(hour=${hourly:.4f}/{self.limit_per_hour}, day=${daily:.4f}/{self.limit_per_day})"
        )

    def record_actual(self, agent: str, cost_usd: float) -> None:
        """Record the actual cost of a completed call."""
        self._records.append(_SpendRecord(cost_usd=cost_usd, agent=agent))
        logger.debug(f"🛡️ Cost recorded: {agent} ${cost_usd:.6f}")

    def get_spend_summary(self) -> dict[str, Any]:
        """Return current spend totals for monitoring."""
        self._prune_old_records()
        return {
            "hourly_spend_usd": round(self._sum_since(3600), 6),
            "daily_spend_usd": round(self._sum_since(86400), 6),
            "limits": {
                "per_call_usd": self.limit_per_call,
                "per_hour_usd": self.limit_per_hour,
                "per_day_usd": self.limit_per_day,
            },
            "record_count": len(self._records),
        }

    def reset(self) -> None:
        """Clear all records (e.g., for testing)."""
        self._records.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sum_since(self, seconds: float) -> float:
        cutoff = time.time() - seconds
        return sum(r.cost_usd for r in self._records if r.timestamp >= cutoff)

    def _prune_old_records(self) -> None:
        """Remove records older than 24 hours to bound memory usage."""
        cutoff = time.time() - 86400
        while self._records and self._records[0].timestamp < cutoff:
            self._records.popleft()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_breaker: CostCircuitBreaker | None = None


def get_cost_circuit_breaker() -> CostCircuitBreaker:
    """Return the process-level singleton CostCircuitBreaker."""
    global _breaker
    if _breaker is None:
        _breaker = CostCircuitBreaker()
    return _breaker
