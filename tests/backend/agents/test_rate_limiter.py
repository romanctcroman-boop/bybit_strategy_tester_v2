"""
Tests for llm/rate_limiter.py — TokenAwareRateLimiter.

Tests cover:
- TokenBudget defaults and configuration
- UsageWindow sliding reset
- TokenAwareRateLimiter acquire/record/metrics
- Budget enforcement (minute, hour, day, cost)
"""

import time

import pytest

from backend.agents.llm.rate_limiter import (
    TokenAwareRateLimiter,
    TokenBudget,
    UsageWindow,
)


class TestTokenBudget:
    """Test TokenBudget configuration."""

    def test_defaults(self):
        """Default budget values are sane."""
        budget = TokenBudget()
        assert budget.max_tokens_per_minute == 100_000
        assert budget.max_tokens_per_hour == 2_000_000
        assert budget.max_tokens_per_day == 20_000_000
        assert budget.max_cost_per_hour_usd == 5.0
        assert budget.max_cost_per_day_usd == 50.0

    def test_custom_values(self):
        """Custom budget values are accepted."""
        budget = TokenBudget(
            max_tokens_per_minute=50_000,
            max_cost_per_hour_usd=1.0,
        )
        assert budget.max_tokens_per_minute == 50_000
        assert budget.max_cost_per_hour_usd == 1.0


class TestUsageWindow:
    """Test UsageWindow sliding tracker."""

    def test_record_increments(self):
        """record() increments counters."""
        window = UsageWindow(window_seconds=60.0)
        window.record(tokens=100, cost=0.01)
        assert window.tokens_used == 100
        assert window.cost_usd == 0.01
        assert window.request_count == 1

    def test_multiple_records(self):
        """Multiple record() calls accumulate."""
        window = UsageWindow(window_seconds=60.0)
        window.record(tokens=100)
        window.record(tokens=200)
        window.record(tokens=300)
        assert window.tokens_used == 600
        assert window.request_count == 3

    def test_reset_if_expired_fresh(self):
        """Fresh window does not reset."""
        window = UsageWindow(window_seconds=60.0)
        window.record(tokens=100)
        reset = window.reset_if_expired()
        assert reset is False
        assert window.tokens_used == 100

    def test_reset_if_expired_stale(self):
        """Expired window resets counters."""
        window = UsageWindow(window_seconds=0.01)
        window.record(tokens=100)
        time.sleep(0.02)
        reset = window.reset_if_expired()
        assert reset is True
        assert window.tokens_used == 0
        assert window.request_count == 0

    def test_remaining_seconds(self):
        """remaining_seconds returns positive value for fresh window."""
        window = UsageWindow(window_seconds=60.0)
        assert 0 < window.remaining_seconds <= 60.0


class TestTokenAwareRateLimiter:
    """Test TokenAwareRateLimiter."""

    @pytest.mark.asyncio
    async def test_acquire_within_budget(self):
        """acquire() returns True when within budget."""
        budget = TokenBudget(max_tokens_per_minute=10_000)
        limiter = TokenAwareRateLimiter("deepseek", budget)
        result = await limiter.acquire(estimated_tokens=1000)
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_exceeds_hourly_budget(self):
        """acquire() returns False when hourly budget exceeded."""
        budget = TokenBudget(max_tokens_per_hour=1000)
        limiter = TokenAwareRateLimiter("deepseek", budget)
        limiter.record_usage(tokens=900)
        result = await limiter.acquire(estimated_tokens=200)
        assert result is False

    @pytest.mark.asyncio
    async def test_acquire_exceeds_daily_budget(self):
        """acquire() returns False when daily budget exceeded."""
        budget = TokenBudget(max_tokens_per_day=500)
        limiter = TokenAwareRateLimiter("deepseek", budget)
        limiter.record_usage(tokens=400)
        result = await limiter.acquire(estimated_tokens=200)
        assert result is False

    @pytest.mark.asyncio
    async def test_acquire_exceeds_cost_budget(self):
        """acquire() returns False when hourly cost exceeded."""
        budget = TokenBudget(max_cost_per_hour_usd=0.01)
        limiter = TokenAwareRateLimiter("deepseek", budget)
        limiter.record_usage(tokens=1000, cost_usd=0.02)
        result = await limiter.acquire(estimated_tokens=100)
        assert result is False

    def test_record_usage_accumulates(self):
        """record_usage() accumulates totals."""
        limiter = TokenAwareRateLimiter("deepseek")
        limiter.record_usage(tokens=1000, cost_usd=0.01)
        limiter.record_usage(tokens=2000, cost_usd=0.02)
        assert limiter._total_tokens == 3000
        assert limiter._total_cost == pytest.approx(0.03)
        assert limiter._total_requests == 2

    def test_get_metrics(self):
        """get_metrics() returns structured dict."""
        limiter = TokenAwareRateLimiter("deepseek")
        limiter.record_usage(tokens=5000, cost_usd=0.05)
        metrics = limiter.get_metrics()
        assert metrics["provider"] == "deepseek"
        assert metrics["total_tokens"] == 5000
        assert metrics["total_cost_usd"] == 0.05
        assert metrics["total_requests"] == 1
        assert metrics["throttled_count"] == 0
        assert "minute_window" in metrics
        assert "hour_window" in metrics
        assert "day_window" in metrics

    def test_default_budget(self):
        """Default budget is used when none provided."""
        limiter = TokenAwareRateLimiter("test")
        assert limiter.budget.max_tokens_per_minute == 100_000

    @pytest.mark.asyncio
    async def test_acquire_waits_then_succeeds_after_minute_reset(self):
        """acquire() sleeps when minute budget is exceeded, then succeeds after window expires.

        Verifies the critical recovery path: minute exhaustion → asyncio.sleep() →
        window reset → acquire() returns True (not False). Addresses audit finding
        that recovery behavior was untested (Qwen, HIGH severity).
        """
        # Tiny window so it expires fast
        budget = TokenBudget(max_tokens_per_minute=500)
        limiter = TokenAwareRateLimiter("deepseek", budget)

        # Exhaust minute budget
        limiter.record_usage(tokens=500)

        # Force minute window to almost-expired state so sleep is minimal
        limiter._minute_window.window_start = time.time() - 59.95

        # acquire() should detect minute overflow, sleep briefly, then return True
        result = await limiter.acquire(estimated_tokens=100)
        assert result is True, "acquire() must succeed after minute window expires"
        assert limiter._throttled_count == 1, "throttle counter should increment once"

    @pytest.mark.asyncio
    async def test_acquire_minute_reset_clears_usage(self):
        """After minute window expires, token counters are reset and new requests proceed.

        End-to-end: exhaust → expire → record new → verify isolated window.
        """
        budget = TokenBudget(max_tokens_per_minute=1000)
        limiter = TokenAwareRateLimiter("deepseek", budget)

        # Exhaust minute budget
        limiter.record_usage(tokens=1000)
        assert limiter._minute_window.tokens_used == 1000

        # Force window expiry
        limiter._minute_window.window_start = time.time() - 61.0
        limiter._minute_window.reset_if_expired()
        assert limiter._minute_window.tokens_used == 0

        # Should be able to acquire again
        result = await limiter.acquire(estimated_tokens=500)
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_concurrent_does_not_deadlock(self):
        """Multiple concurrent acquire() calls don't deadlock on the internal lock.

        Runs 10 concurrent acquires with a tight budget to verify the lock
        is correctly released even when throttling occurs.
        """
        import asyncio

        budget = TokenBudget(max_tokens_per_minute=10_000)
        limiter = TokenAwareRateLimiter("deepseek", budget)

        async def do_acquire():
            return await limiter.acquire(estimated_tokens=500)

        tasks = [asyncio.create_task(do_acquire()) for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed (within budget) and no exceptions
        for r in results:
            assert isinstance(r, bool), f"Expected bool, got {type(r)}: {r}"
            assert r is True
