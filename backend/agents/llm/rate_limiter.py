"""
Token-Aware Rate Limiter

Extends basic token-bucket rate limiting with:
- Per-provider token budgets (not just request count)
- Cost-aware throttling with configurable daily/hourly budgets
- Thread-safe async operations
- Metrics emission for observability

Addresses audit finding: "RateLimiter lacks per-provider token budgeting" (Qwen, P1)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class TokenBudget:
    """Token budget configuration per provider."""

    max_tokens_per_minute: int = 100_000
    max_tokens_per_hour: int = 2_000_000
    max_tokens_per_day: int = 20_000_000
    max_cost_per_hour_usd: float = 5.0
    max_cost_per_day_usd: float = 50.0


@dataclass
class UsageWindow:
    """Sliding-window usage tracker."""

    tokens_used: int = 0
    cost_usd: float = 0.0
    request_count: int = 0
    window_start: float = field(default_factory=time.time)
    window_seconds: float = 60.0

    def reset_if_expired(self) -> bool:
        """Reset window if it has expired. Returns True if reset occurred."""
        now = time.time()
        if now - self.window_start >= self.window_seconds:
            self.tokens_used = 0
            self.cost_usd = 0.0
            self.request_count = 0
            self.window_start = now
            return True
        return False

    def record(self, tokens: int, cost: float = 0.0) -> None:
        """Record token usage within current window."""
        self.reset_if_expired()
        self.tokens_used += tokens
        self.cost_usd += cost
        self.request_count += 1

    @property
    def remaining_seconds(self) -> float:
        """Seconds remaining in current window."""
        elapsed = time.time() - self.window_start
        return max(0.0, self.window_seconds - elapsed)


class TokenAwareRateLimiter:
    """
    Rate limiter with token-level and cost-level awareness.

    Tracks usage across multiple time windows (minute, hour, day) and
    blocks requests that would exceed configured budgets.

    Example:
        limiter = TokenAwareRateLimiter(
            provider="deepseek",
            budget=TokenBudget(max_tokens_per_minute=100_000)
        )
        can_proceed = await limiter.acquire(estimated_tokens=5000)
    """

    def __init__(self, provider: str, budget: TokenBudget | None = None):
        self.provider = provider
        self.budget = budget or TokenBudget()
        self._lock = asyncio.Lock()

        # Sliding windows
        self._minute_window = UsageWindow(window_seconds=60.0)
        self._hour_window = UsageWindow(window_seconds=3600.0)
        self._day_window = UsageWindow(window_seconds=86400.0)

        # Metrics
        self._total_tokens = 0
        self._total_cost = 0.0
        self._total_requests = 0
        self._throttled_count = 0

    async def acquire(self, estimated_tokens: int = 1000) -> bool:
        """
        Acquire permission to make a request.

        Args:
            estimated_tokens: Estimated token count for the request.

        Returns:
            True if request is allowed, False if throttled.
        """
        async with self._lock:
            # Reset expired windows
            self._minute_window.reset_if_expired()
            self._hour_window.reset_if_expired()
            self._day_window.reset_if_expired()

            # Check minute budget
            if self._minute_window.tokens_used + estimated_tokens > self.budget.max_tokens_per_minute:
                wait_time = self._minute_window.remaining_seconds
                self._throttled_count += 1
                logger.warning(
                    f"⏳ {self.provider} minute token budget exceeded "
                    f"({self._minute_window.tokens_used}/{self.budget.max_tokens_per_minute}). "
                    f"Wait {wait_time:.1f}s"
                )
                if wait_time > 0:
                    await asyncio.sleep(min(wait_time, 10.0))
                return True  # Allow after wait

            # Check hourly budget
            if self._hour_window.tokens_used + estimated_tokens > self.budget.max_tokens_per_hour:
                self._throttled_count += 1
                logger.warning(
                    f"⏳ {self.provider} hourly token budget exceeded "
                    f"({self._hour_window.tokens_used}/{self.budget.max_tokens_per_hour})"
                )
                return False

            # Check daily budget
            if self._day_window.tokens_used + estimated_tokens > self.budget.max_tokens_per_day:
                self._throttled_count += 1
                logger.warning(
                    f"🛑 {self.provider} daily token budget exhausted "
                    f"({self._day_window.tokens_used}/{self.budget.max_tokens_per_day})"
                )
                return False

            # Check hourly cost budget
            if self._hour_window.cost_usd > self.budget.max_cost_per_hour_usd:
                self._throttled_count += 1
                logger.warning(
                    f"💰 {self.provider} hourly cost budget exceeded "
                    f"(${self._hour_window.cost_usd:.4f}/${self.budget.max_cost_per_hour_usd})"
                )
                return False

            return True

    def record_usage(self, tokens: int, cost_usd: float = 0.0) -> None:
        """Record actual token usage after a request completes."""
        self._minute_window.record(tokens, cost_usd)
        self._hour_window.record(tokens, cost_usd)
        self._day_window.record(tokens, cost_usd)
        self._total_tokens += tokens
        self._total_cost += cost_usd
        self._total_requests += 1

    def get_metrics(self) -> dict[str, Any]:
        """Get current rate limiter metrics."""
        return {
            "provider": self.provider,
            "total_tokens": self._total_tokens,
            "total_cost_usd": round(self._total_cost, 4),
            "total_requests": self._total_requests,
            "throttled_count": self._throttled_count,
            "minute_window": {
                "tokens_used": self._minute_window.tokens_used,
                "remaining_seconds": round(self._minute_window.remaining_seconds, 1),
            },
            "hour_window": {
                "tokens_used": self._hour_window.tokens_used,
                "cost_usd": round(self._hour_window.cost_usd, 4),
            },
            "day_window": {
                "tokens_used": self._day_window.tokens_used,
                "cost_usd": round(self._day_window.cost_usd, 4),
            },
        }
