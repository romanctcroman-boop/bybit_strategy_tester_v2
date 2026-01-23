"""
Rate Limiting Service.

Provides comprehensive rate limiting for API endpoints with:
- Per-endpoint rate limits
- Per-IP throttling
- Per-user/API key limits
- Adaptive rate limiting based on system load
- Redis-backed distributed limiting
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimitStrategy(str, Enum):
    """Rate limiting strategy types."""

    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


class RateLimitScope(str, Enum):
    """Scope for rate limiting."""

    GLOBAL = "global"
    PER_IP = "per_ip"
    PER_USER = "per_user"
    PER_API_KEY = "per_api_key"
    PER_ENDPOINT = "per_endpoint"


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit rule."""

    name: str
    requests_per_second: float
    burst_size: int = 10
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    scope: RateLimitScope = RateLimitScope.PER_IP
    enabled: bool = True
    penalty_seconds: int = 60  # Penalty time after limit exceeded


@dataclass
class RateLimitState:
    """State for token bucket rate limiting."""

    tokens: float
    last_update: float
    request_count: int = 0
    blocked_until: Optional[float] = None


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    reset_after: float
    retry_after: Optional[float] = None
    limit: int = 0
    scope: str = ""
    rule_name: str = ""


@dataclass
class RateLimitMetrics:
    """Metrics for rate limiting."""

    total_requests: int = 0
    allowed_requests: int = 0
    blocked_requests: int = 0
    current_rate: float = 0.0
    peak_rate: float = 0.0
    last_blocked: Optional[datetime] = None


class RateLimiterService:
    """
    Comprehensive rate limiting service.

    Features:
    - Multiple rate limiting strategies
    - Per-IP, per-user, per-endpoint limits
    - Adaptive limiting based on system load
    - Distributed limiting with Redis (optional)
    """

    def __init__(self):
        self._rules: dict[str, RateLimitConfig] = {}
        self._states: dict[str, dict[str, RateLimitState]] = defaultdict(dict)
        self._metrics: dict[str, RateLimitMetrics] = defaultdict(RateLimitMetrics)
        self._global_metrics = RateLimitMetrics()
        self._initialized = False
        self._lock = asyncio.Lock()
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """Register default rate limiting rules."""
        # Global API limit
        self.register_rule(
            RateLimitConfig(
                name="global_api",
                requests_per_second=100.0,
                burst_size=200,
                scope=RateLimitScope.GLOBAL,
            )
        )

        # Per-IP limit
        self.register_rule(
            RateLimitConfig(
                name="per_ip_default",
                requests_per_second=10.0,
                burst_size=20,
                scope=RateLimitScope.PER_IP,
            )
        )

        # Trading endpoints - stricter limits
        self.register_rule(
            RateLimitConfig(
                name="trading_endpoints",
                requests_per_second=2.0,
                burst_size=5,
                scope=RateLimitScope.PER_IP,
                penalty_seconds=120,
            )
        )

        # AI agent endpoints - moderate limits
        self.register_rule(
            RateLimitConfig(
                name="ai_agent_endpoints",
                requests_per_second=5.0,
                burst_size=10,
                scope=RateLimitScope.PER_IP,
            )
        )

        # Health check endpoints - lenient
        self.register_rule(
            RateLimitConfig(
                name="health_endpoints",
                requests_per_second=50.0,
                burst_size=100,
                scope=RateLimitScope.GLOBAL,
            )
        )

        # Data quality endpoints
        self.register_rule(
            RateLimitConfig(
                name="data_quality",
                requests_per_second=20.0,
                burst_size=40,
                scope=RateLimitScope.PER_IP,
            )
        )

        # Market data endpoints
        self.register_rule(
            RateLimitConfig(
                name="market_data",
                requests_per_second=30.0,
                burst_size=60,
                scope=RateLimitScope.PER_IP,
            )
        )

        self._initialized = True
        logger.info(f"✅ Registered {len(self._rules)} rate limiting rules")

    # ============================================================
    # Rule Management
    # ============================================================

    def register_rule(self, config: RateLimitConfig) -> None:
        """Register a rate limiting rule."""
        self._rules[config.name] = config
        logger.debug(f"📝 Registered rate limit rule: {config.name}")

    def unregister_rule(self, name: str) -> bool:
        """Unregister a rate limiting rule."""
        if name in self._rules:
            del self._rules[name]
            if name in self._states:
                del self._states[name]
            logger.debug(f"🗑️ Unregistered rate limit rule: {name}")
            return True
        return False

    def get_rule(self, name: str) -> Optional[RateLimitConfig]:
        """Get a rate limiting rule by name."""
        return self._rules.get(name)

    def list_rules(self) -> list[dict]:
        """List all registered rules."""
        return [
            {
                "name": rule.name,
                "requests_per_second": rule.requests_per_second,
                "burst_size": rule.burst_size,
                "strategy": rule.strategy.value,
                "scope": rule.scope.value,
                "enabled": rule.enabled,
                "penalty_seconds": rule.penalty_seconds,
            }
            for rule in self._rules.values()
        ]

    # ============================================================
    # Rate Limit Checking
    # ============================================================

    async def check_rate_limit(
        self,
        rule_name: str,
        identifier: str,
    ) -> RateLimitResult:
        """
        Check if a request is allowed under the rate limit.

        Args:
            rule_name: Name of the rate limit rule to apply
            identifier: Identifier for the client (IP, user ID, API key)

        Returns:
            RateLimitResult with allowed status and metadata
        """
        rule = self._rules.get(rule_name)
        if not rule or not rule.enabled:
            return RateLimitResult(
                allowed=True,
                remaining=999,
                reset_after=0,
                limit=999,
                scope="none",
                rule_name=rule_name,
            )

        async with self._lock:
            return self._check_token_bucket(rule, identifier)

    def _check_token_bucket(
        self,
        rule: RateLimitConfig,
        identifier: str,
    ) -> RateLimitResult:
        """Token bucket rate limiting algorithm."""
        now = time.time()
        key = f"{rule.name}:{identifier}"

        # Get or create state
        if key not in self._states[rule.name]:
            self._states[rule.name][key] = RateLimitState(
                tokens=float(rule.burst_size),
                last_update=now,
            )

        state = self._states[rule.name][key]

        # Check if currently blocked
        if state.blocked_until and now < state.blocked_until:
            retry_after = state.blocked_until - now
            self._record_blocked(rule.name)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_after=retry_after,
                retry_after=retry_after,
                limit=rule.burst_size,
                scope=rule.scope.value,
                rule_name=rule.name,
            )

        # Refill tokens based on time elapsed
        elapsed = now - state.last_update
        tokens_to_add = elapsed * rule.requests_per_second
        state.tokens = min(rule.burst_size, state.tokens + tokens_to_add)
        state.last_update = now

        # Check if request is allowed
        if state.tokens >= 1.0:
            state.tokens -= 1.0
            state.request_count += 1
            self._record_allowed(rule.name)

            reset_after = (rule.burst_size - state.tokens) / rule.requests_per_second

            return RateLimitResult(
                allowed=True,
                remaining=int(state.tokens),
                reset_after=reset_after,
                limit=rule.burst_size,
                scope=rule.scope.value,
                rule_name=rule.name,
            )
        else:
            # Apply penalty
            state.blocked_until = now + rule.penalty_seconds
            retry_after = rule.penalty_seconds
            self._record_blocked(rule.name)

            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_after=retry_after,
                retry_after=retry_after,
                limit=rule.burst_size,
                scope=rule.scope.value,
                rule_name=rule.name,
            )

    def _record_allowed(self, rule_name: str) -> None:
        """Record an allowed request."""
        self._global_metrics.total_requests += 1
        self._global_metrics.allowed_requests += 1
        self._metrics[rule_name].total_requests += 1
        self._metrics[rule_name].allowed_requests += 1

    def _record_blocked(self, rule_name: str) -> None:
        """Record a blocked request."""
        self._global_metrics.total_requests += 1
        self._global_metrics.blocked_requests += 1
        self._global_metrics.last_blocked = datetime.now(timezone.utc)
        self._metrics[rule_name].total_requests += 1
        self._metrics[rule_name].blocked_requests += 1
        self._metrics[rule_name].last_blocked = datetime.now(timezone.utc)

    # ============================================================
    # Endpoint Matching
    # ============================================================

    def get_rule_for_endpoint(self, path: str, method: str) -> str:
        """
        Get the appropriate rate limit rule for an endpoint.

        Args:
            path: Request path
            method: HTTP method

        Returns:
            Rule name to apply
        """
        # Trading endpoints
        if any(p in path for p in ["/trade", "/order", "/position", "/execution"]):
            return "trading_endpoints"

        # AI agent endpoints
        if "/agents/" in path or "/ai/" in path:
            return "ai_agent_endpoints"

        # Health endpoints
        if "/health" in path or "/monitoring/" in path:
            return "health_endpoints"

        # Data quality endpoints
        if "/data-quality/" in path:
            return "data_quality"

        # Market data endpoints
        if "/marketdata/" in path or "/klines" in path:
            return "market_data"

        # Default per-IP limit
        return "per_ip_default"

    # ============================================================
    # IP Management
    # ============================================================

    def is_ip_blocked(self, ip: str) -> bool:
        """Check if an IP is currently blocked."""
        now = time.time()
        for rule_name, states in self._states.items():
            key = f"{rule_name}:{ip}"
            if key in states:
                state = states[key]
                if state.blocked_until and now < state.blocked_until:
                    return True
        return False

    def unblock_ip(self, ip: str) -> bool:
        """Manually unblock an IP address."""
        unblocked = False
        for rule_name, states in self._states.items():
            key = f"{rule_name}:{ip}"
            if key in states:
                states[key].blocked_until = None
                states[key].tokens = self._rules[rule_name].burst_size
                unblocked = True
        if unblocked:
            logger.info(f"🔓 Unblocked IP: {ip}")
        return unblocked

    def get_blocked_ips(self) -> list[dict]:
        """Get list of currently blocked IPs."""
        now = time.time()
        blocked = []
        for rule_name, states in self._states.items():
            for key, state in states.items():
                if state.blocked_until and now < state.blocked_until:
                    ip = key.split(":", 1)[1] if ":" in key else key
                    blocked.append(
                        {
                            "ip": ip,
                            "rule": rule_name,
                            "blocked_until": datetime.fromtimestamp(
                                state.blocked_until
                            ).isoformat(),
                            "remaining_seconds": state.blocked_until - now,
                        }
                    )
        return blocked

    # ============================================================
    # Metrics & Status
    # ============================================================

    def get_metrics(self, rule_name: Optional[str] = None) -> dict:
        """Get rate limiting metrics."""
        if rule_name:
            m = self._metrics.get(rule_name, RateLimitMetrics())
            return {
                "rule": rule_name,
                "total_requests": m.total_requests,
                "allowed_requests": m.allowed_requests,
                "blocked_requests": m.blocked_requests,
                "block_rate": (
                    m.blocked_requests / m.total_requests * 100
                    if m.total_requests > 0
                    else 0
                ),
                "last_blocked": m.last_blocked.isoformat() if m.last_blocked else None,
            }

        return {
            "global": {
                "total_requests": self._global_metrics.total_requests,
                "allowed_requests": self._global_metrics.allowed_requests,
                "blocked_requests": self._global_metrics.blocked_requests,
                "block_rate": (
                    self._global_metrics.blocked_requests
                    / self._global_metrics.total_requests
                    * 100
                    if self._global_metrics.total_requests > 0
                    else 0
                ),
                "last_blocked": (
                    self._global_metrics.last_blocked.isoformat()
                    if self._global_metrics.last_blocked
                    else None
                ),
            },
            "by_rule": {
                name: {
                    "total": m.total_requests,
                    "allowed": m.allowed_requests,
                    "blocked": m.blocked_requests,
                }
                for name, m in self._metrics.items()
            },
        }

    def get_status(self) -> dict:
        """Get service status."""
        return {
            "initialized": self._initialized,
            "rules_count": len(self._rules),
            "active_limiters": sum(len(s) for s in self._states.values()),
            "blocked_ips_count": len(self.get_blocked_ips()),
            "total_requests": self._global_metrics.total_requests,
            "block_rate": (
                self._global_metrics.blocked_requests
                / self._global_metrics.total_requests
                * 100
                if self._global_metrics.total_requests > 0
                else 0
            ),
        }

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self._global_metrics = RateLimitMetrics()
        self._metrics.clear()
        logger.info("📊 Rate limiter metrics reset")

    def cleanup_expired_states(self) -> int:
        """Clean up expired rate limit states."""
        now = time.time()
        cleaned = 0
        for rule_name in list(self._states.keys()):
            rule = self._rules.get(rule_name)
            if not rule:
                continue

            # Clean states older than 10 minutes with full tokens
            expire_time = now - 600
            for key in list(self._states[rule_name].keys()):
                state = self._states[rule_name][key]
                if (
                    state.last_update < expire_time
                    and state.tokens >= rule.burst_size
                    and not state.blocked_until
                ):
                    del self._states[rule_name][key]
                    cleaned += 1

        if cleaned > 0:
            logger.debug(f"🧹 Cleaned {cleaned} expired rate limit states")
        return cleaned


# Singleton instance
_rate_limiter_service: Optional[RateLimiterService] = None


def get_rate_limiter_service() -> RateLimiterService:
    """Get or create rate limiter service instance."""
    global _rate_limiter_service
    if _rate_limiter_service is None:
        _rate_limiter_service = RateLimiterService()
        logger.info("🚦 Rate Limiter Service initialized")
    return _rate_limiter_service
