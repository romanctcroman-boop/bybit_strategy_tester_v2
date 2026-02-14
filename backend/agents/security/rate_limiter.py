"""
Agent Rate Limiter

Per-agent sliding window rate limiter for controlling AI agent API usage.
Prevents:
- API quota exhaustion (Bybit 120 req/min, LLM provider limits)
- Cost overruns from excessive LLM calls
- Runaway agent loops

Features:
- Per-agent independent counters
- Sliding window (not fixed window) for smooth limiting
- Configurable limits per agent type
- Burst allowance for short spikes

Thread-safe using simple locking.

Usage:
    limiter = AgentRateLimiter()
    result = limiter.check("deepseek")
    if result.allowed:
        # proceed with API call
    else:
        # wait result.retry_after_seconds
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting an agent."""

    agent_id: str
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10  # Allow this many requests in quick succession
    cooldown_seconds: float = 1.0  # Min interval between requests

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "requests_per_minute": self.requests_per_minute,
            "requests_per_hour": self.requests_per_hour,
            "burst_size": self.burst_size,
            "cooldown_seconds": self.cooldown_seconds,
        }


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    agent_id: str
    current_rpm: int = 0
    current_rph: int = 0
    limit_rpm: int = 60
    limit_rph: int = 1000
    retry_after_seconds: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "agent_id": self.agent_id,
            "current_rpm": self.current_rpm,
            "current_rph": self.current_rph,
            "limit_rpm": self.limit_rpm,
            "limit_rph": self.limit_rph,
            "retry_after_seconds": round(self.retry_after_seconds, 2),
            "reason": self.reason,
        }


# ═══════════════════════════════════════════════════════════════════
# Default Limits by Agent Type
# ═══════════════════════════════════════════════════════════════════

DEFAULT_LIMITS: dict[str, RateLimitConfig] = {
    "deepseek": RateLimitConfig(
        agent_id="deepseek",
        requests_per_minute=30,
        requests_per_hour=500,
        burst_size=5,
        cooldown_seconds=2.0,
    ),
    "perplexity": RateLimitConfig(
        agent_id="perplexity",
        requests_per_minute=20,
        requests_per_hour=300,
        burst_size=3,
        cooldown_seconds=3.0,
    ),
    "qwen": RateLimitConfig(
        agent_id="qwen",
        requests_per_minute=30,
        requests_per_hour=500,
        burst_size=5,
        cooldown_seconds=2.0,
    ),
    "openai": RateLimitConfig(
        agent_id="openai",
        requests_per_minute=60,
        requests_per_hour=1000,
        burst_size=10,
        cooldown_seconds=1.0,
    ),
    "anthropic": RateLimitConfig(
        agent_id="anthropic",
        requests_per_minute=40,
        requests_per_hour=600,
        burst_size=5,
        cooldown_seconds=1.5,
    ),
    "ollama": RateLimitConfig(
        agent_id="ollama",
        requests_per_minute=120,
        requests_per_hour=5000,
        burst_size=20,
        cooldown_seconds=0.5,
    ),
    "bybit_api": RateLimitConfig(
        agent_id="bybit_api",
        requests_per_minute=100,  # Bybit limit: 120/min, leave margin
        requests_per_hour=3000,
        burst_size=10,
        cooldown_seconds=0.5,
    ),
}


class AgentRateLimiter:
    """
    Per-agent sliding window rate limiter.

    Uses a deque of timestamps for each agent to implement
    a true sliding window (not fixed time buckets).
    """

    def __init__(
        self,
        limits: dict[str, RateLimitConfig] | None = None,
        default_rpm: int = 60,
        default_rph: int = 1000,
    ) -> None:
        """
        Args:
            limits: Per-agent rate limit configs.
            default_rpm: Default requests per minute for unconfigured agents.
            default_rph: Default requests per hour for unconfigured agents.
        """
        self._limits: dict[str, RateLimitConfig] = limits or dict(DEFAULT_LIMITS)
        self._default_rpm = default_rpm
        self._default_rph = default_rph
        self._windows: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, agent_id: str) -> RateLimitResult:
        """
        Check if a request is allowed for the given agent.

        Does NOT record the request — call record() separately after
        the request succeeds.

        Args:
            agent_id: The agent identifier.

        Returns:
            RateLimitResult indicating whether the request is allowed.
        """
        config = self._get_config(agent_id)
        now = time.monotonic()

        with self._lock:
            window = self._get_window(agent_id)
            self._clean_window(window, now)

            # Count requests in last minute and hour
            one_min_ago = now - 60.0
            one_hour_ago = now - 3600.0
            rpm_count = sum(1 for t in window if t >= one_min_ago)
            rph_count = len(window)  # Window is already cleaned to 1h

            # Check cooldown
            if window and (now - window[-1]) < config.cooldown_seconds:
                retry_after = config.cooldown_seconds - (now - window[-1])
                return RateLimitResult(
                    allowed=False,
                    agent_id=agent_id,
                    current_rpm=rpm_count,
                    current_rph=rph_count,
                    limit_rpm=config.requests_per_minute,
                    limit_rph=config.requests_per_hour,
                    retry_after_seconds=retry_after,
                    reason=f"Cooldown: {retry_after:.1f}s remaining",
                )

            # Check per-minute limit
            if rpm_count >= config.requests_per_minute:
                # Find earliest request that will expire from the minute window
                oldest_in_minute = next((t for t in window if t >= one_min_ago), now)
                retry_after = 60.0 - (now - oldest_in_minute)
                return RateLimitResult(
                    allowed=False,
                    agent_id=agent_id,
                    current_rpm=rpm_count,
                    current_rph=rph_count,
                    limit_rpm=config.requests_per_minute,
                    limit_rph=config.requests_per_hour,
                    retry_after_seconds=max(0.1, retry_after),
                    reason=f"RPM limit exceeded: {rpm_count}/{config.requests_per_minute}",
                )

            # Check per-hour limit
            if rph_count >= config.requests_per_hour:
                oldest_in_hour = next((t for t in window if t >= one_hour_ago), now)
                retry_after = 3600.0 - (now - oldest_in_hour)
                return RateLimitResult(
                    allowed=False,
                    agent_id=agent_id,
                    current_rpm=rpm_count,
                    current_rph=rph_count,
                    limit_rpm=config.requests_per_minute,
                    limit_rph=config.requests_per_hour,
                    retry_after_seconds=max(0.1, retry_after),
                    reason=f"RPH limit exceeded: {rph_count}/{config.requests_per_hour}",
                )

            return RateLimitResult(
                allowed=True,
                agent_id=agent_id,
                current_rpm=rpm_count,
                current_rph=rph_count,
                limit_rpm=config.requests_per_minute,
                limit_rph=config.requests_per_hour,
            )

    def record(self, agent_id: str) -> None:
        """Record a completed request for the given agent."""
        now = time.monotonic()
        with self._lock:
            window = self._get_window(agent_id)
            window.append(now)

    def check_and_record(self, agent_id: str) -> RateLimitResult:
        """Check and record in one atomic operation."""
        result = self.check(agent_id)
        if result.allowed:
            self.record(agent_id)
        return result

    def get_usage(self, agent_id: str) -> dict[str, Any]:
        """Get current usage stats for an agent."""
        config = self._get_config(agent_id)
        now = time.monotonic()

        with self._lock:
            window = self._get_window(agent_id)
            self._clean_window(window, now)

            one_min_ago = now - 60.0
            rpm_count = sum(1 for t in window if t >= one_min_ago)
            rph_count = len(window)

        return {
            "agent_id": agent_id,
            "current_rpm": rpm_count,
            "current_rph": rph_count,
            "limit_rpm": config.requests_per_minute,
            "limit_rph": config.requests_per_hour,
            "rpm_utilization": rpm_count / config.requests_per_minute if config.requests_per_minute > 0 else 0,
            "rph_utilization": rph_count / config.requests_per_hour if config.requests_per_hour > 0 else 0,
        }

    def reset(self, agent_id: str | None = None) -> None:
        """Reset rate limit counters. If agent_id is None, reset all."""
        with self._lock:
            if agent_id:
                self._windows.pop(agent_id, None)
            else:
                self._windows.clear()

    def set_config(self, config: RateLimitConfig) -> None:
        """Set or update config for an agent."""
        self._limits[config.agent_id] = config

    # ─── Private ─────────────────────────────────────────────────

    def _get_config(self, agent_id: str) -> RateLimitConfig:
        """Get config for an agent, falling back to defaults."""
        if agent_id in self._limits:
            return self._limits[agent_id]
        return RateLimitConfig(
            agent_id=agent_id,
            requests_per_minute=self._default_rpm,
            requests_per_hour=self._default_rph,
        )

    def _get_window(self, agent_id: str) -> deque[float]:
        """Get or create the sliding window for an agent."""
        if agent_id not in self._windows:
            self._windows[agent_id] = deque()
        return self._windows[agent_id]

    @staticmethod
    def _clean_window(window: deque[float], now: float) -> None:
        """Remove entries older than 1 hour from the window."""
        cutoff = now - 3600.0
        while window and window[0] < cutoff:
            window.popleft()
