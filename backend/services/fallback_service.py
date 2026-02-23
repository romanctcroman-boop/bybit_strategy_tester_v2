"""
Fallback Service - Graceful Degradation for AI Agents

Provides fallback mechanisms when primary AI services are unavailable:
1. Cached responses for common queries
2. Degraded mode with simpler responses
3. Static fallback data for critical operations
4. Service health aggregation

Phase 5: Reliability & Resilience
"""

import hashlib
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, TypeVar


def _utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(UTC)


logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceHealth(str, Enum):
    """Service health states"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class FallbackType(str, Enum):
    """Types of fallback responses"""

    CACHED = "cached"  # Previously cached response
    STATIC = "static"  # Pre-defined static response
    DEGRADED = "degraded"  # Simplified response
    ERROR = "error"  # Error response (last resort)


@dataclass
class FallbackResponse:
    """Fallback response wrapper"""

    content: str
    fallback_type: FallbackType
    original_prompt: str
    cached_at: datetime | None = None
    ttl_seconds: int = 3600
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if not self.cached_at:
            return True
        return _utc_now() > self.cached_at + timedelta(seconds=self.ttl_seconds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "fallback_type": self.fallback_type.value,
            "original_prompt": self.original_prompt,
            "cached_at": self.cached_at.isoformat() if self.cached_at else None,
            "ttl_seconds": self.ttl_seconds,
            "metadata": self.metadata,
        }


@dataclass
class ServiceStatus:
    """Status of a monitored service"""

    name: str
    health: ServiceHealth
    last_check: datetime
    failure_count: int = 0
    success_count: int = 0
    circuit_state: str = "closed"
    latency_p95_ms: float = 0.0
    error_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "health": self.health.value,
            "last_check": self.last_check.isoformat(),
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "circuit_state": self.circuit_state,
            "latency_p95_ms": self.latency_p95_ms,
            "error_rate": self.error_rate,
        }


class ResponseCache:
    """LRU cache for AI responses with TTL"""

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: dict[str, FallbackResponse] = {}
        self._access_order: list[str] = []

    def _hash_prompt(self, prompt: str, agent_type: str) -> str:
        """Create cache key from prompt"""
        normalized = prompt.strip().lower()
        content = f"{agent_type}:{normalized}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def get(self, prompt: str, agent_type: str) -> FallbackResponse | None:
        """Get cached response if available and not expired"""
        key = self._hash_prompt(prompt, agent_type)

        if key not in self._cache:
            return None

        response = self._cache[key]
        if response.is_expired:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return None

        # Update access order (LRU)
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

        return response

    def set(
        self,
        prompt: str,
        agent_type: str,
        content: str,
        ttl: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Cache a response"""
        key = self._hash_prompt(prompt, agent_type)

        # Evict oldest if at capacity
        while len(self._cache) >= self.max_size and self._access_order:
            oldest_key = self._access_order.pop(0)
            if oldest_key in self._cache:
                del self._cache[oldest_key]

        self._cache[key] = FallbackResponse(
            content=content,
            fallback_type=FallbackType.CACHED,
            original_prompt=prompt,
            cached_at=_utc_now(),
            ttl_seconds=ttl or self.default_ttl,
            metadata=metadata or {"agent_type": agent_type},
        )
        self._access_order.append(key)

    def clear(self) -> int:
        """Clear all cached responses"""
        count = len(self._cache)
        self._cache.clear()
        self._access_order.clear()
        return count

    def stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        expired = sum(1 for r in self._cache.values() if r.is_expired)
        return {
            "total_entries": len(self._cache),
            "expired_entries": expired,
            "valid_entries": len(self._cache) - expired,
            "max_size": self.max_size,
            "utilization_pct": round(len(self._cache) / self.max_size * 100, 2),
        }


class FallbackService:
    """
    Central fallback service for graceful degradation.

    Features:
    - Response caching with TTL
    - Static fallback responses for common queries
    - Degraded mode with simplified responses
    - Service health aggregation
    """

    def __init__(self):
        self.cache = ResponseCache(
            max_size=int(os.getenv("FALLBACK_CACHE_SIZE", "1000")),
            default_ttl=int(os.getenv("FALLBACK_CACHE_TTL", "3600")),
        )

        self._services: dict[str, ServiceStatus] = {}
        self._static_responses: dict[str, str] = {}
        self._degraded_handlers: dict[str, Callable] = {}

        # Initialize static responses
        self._init_static_responses()

        logger.info("FallbackService initialized")

    def _init_static_responses(self) -> None:
        """Initialize static fallback responses"""
        self._static_responses = {
            # DeepSeek strategy generation fallbacks
            "strategy:momentum": """
## Momentum Strategy (Fallback Response)

This is a cached fallback response. The AI service is temporarily unavailable.

**Basic Momentum Strategy:**
1. Calculate 20-period RSI
2. Buy when RSI crosses above 30 (oversold)
3. Sell when RSI crosses below 70 (overbought)
4. Use 2% stop-loss per trade

**Recommended Parameters:**
- RSI Period: 14-20
- Entry Threshold: 30
- Exit Threshold: 70
- Position Size: 2-5% of portfolio

Please retry when services are restored for AI-optimized parameters.
""",
            "strategy:mean_reversion": """
## Mean Reversion Strategy (Fallback Response)

This is a cached fallback response. The AI service is temporarily unavailable.

**Basic Mean Reversion Strategy:**
1. Calculate 20-period Bollinger Bands
2. Buy when price touches lower band
3. Sell when price returns to middle band
4. Use 1.5% stop-loss per trade

**Recommended Parameters:**
- BB Period: 20
- BB Std Dev: 2.0
- Stop Loss: 1.5%
- Take Profit: At middle band

Please retry when services are restored for AI-optimized parameters.
""",
            # Perplexity market research fallbacks
            "research:market_overview": """
## Market Overview (Fallback Response)

This is a cached fallback response. The AI service is temporarily unavailable.

**General Market Guidance:**
- Always check current BTC dominance
- Monitor major support/resistance levels
- Watch for high-impact news events
- Consider overall market sentiment

**Risk Considerations:**
- Crypto markets are highly volatile
- Use proper position sizing
- Never risk more than 2% per trade

Please retry when services are restored for real-time market analysis.
""",
            # Health check fallbacks
            "health_check": "OK - Fallback response (service degraded)",
            # Risk analysis fallbacks
            "risk:portfolio": """
## Portfolio Risk Analysis (Fallback Response)

This is a cached fallback response. The AI service is temporarily unavailable.

**General Risk Guidelines:**
- Diversify across uncorrelated assets
- Limit single position to 10% of portfolio
- Maintain stop-losses on all positions
- Consider correlation risk in crypto

**Standard Risk Metrics:**
- Max Drawdown Target: < 20%
- Sharpe Ratio Target: > 1.0
- Position Sizing: 1-5% per trade

Please retry when services are restored for personalized risk analysis.
""",
        }

    def register_service(self, name: str) -> None:
        """Register a service for health monitoring"""
        if name not in self._services:
            self._services[name] = ServiceStatus(
                name=name,
                health=ServiceHealth.UNKNOWN,
                last_check=_utc_now(),
            )
            logger.debug(f"Registered service for monitoring: {name}")

    def update_service_health(
        self,
        name: str,
        health: ServiceHealth,
        circuit_state: str = "closed",
        latency_p95: float = 0.0,
        error_rate: float = 0.0,
    ) -> None:
        """Update service health status"""
        if name not in self._services:
            self.register_service(name)

        service = self._services[name]
        prev_health = service.health

        service.health = health
        service.last_check = _utc_now()
        service.circuit_state = circuit_state
        service.latency_p95_ms = latency_p95
        service.error_rate = error_rate

        if health == ServiceHealth.HEALTHY:
            service.success_count += 1
        else:
            service.failure_count += 1

        if prev_health != health:
            logger.info(f"Service {name} health changed: {prev_health} → {health}")

    def get_service_health(self, name: str) -> ServiceStatus:
        """Get health status for a service"""
        if name not in self._services:
            self.register_service(name)
        return self._services[name]

    def get_all_services_health(self) -> dict[str, ServiceStatus]:
        """Get health status for all services"""
        return self._services.copy()

    def get_overall_health(self) -> ServiceHealth:
        """Get aggregated health across all services"""
        if not self._services:
            return ServiceHealth.UNKNOWN

        healths = [s.health for s in self._services.values()]

        if all(h == ServiceHealth.HEALTHY for h in healths):
            return ServiceHealth.HEALTHY
        elif any(h == ServiceHealth.UNHEALTHY for h in healths):
            return ServiceHealth.UNHEALTHY
        elif any(h == ServiceHealth.DEGRADED for h in healths):
            return ServiceHealth.DEGRADED
        return ServiceHealth.UNKNOWN

    def register_degraded_handler(
        self, pattern: str, handler: Callable[[str], str]
    ) -> None:
        """Register a degraded mode handler for a pattern"""
        self._degraded_handlers[pattern] = handler
        logger.debug(f"Registered degraded handler for pattern: {pattern}")

    def get_fallback(
        self,
        prompt: str,
        agent_type: str,
        task_type: str | None = None,
    ) -> FallbackResponse | None:
        """
        Get fallback response with priority:
        1. Cached response (if valid)
        2. Static response (if matching pattern)
        3. Degraded handler (if registered)
        4. None (caller should handle)
        """
        # 1. Try cache first
        cached = self.cache.get(prompt, agent_type)
        if cached:
            logger.info(f"Returning cached fallback for {agent_type}")
            return cached

        # 2. Try static responses
        static_key = self._match_static_key(prompt, agent_type, task_type)
        if static_key and static_key in self._static_responses:
            logger.info(f"Returning static fallback: {static_key}")
            return FallbackResponse(
                content=self._static_responses[static_key],
                fallback_type=FallbackType.STATIC,
                original_prompt=prompt,
                metadata={"static_key": static_key, "agent_type": agent_type},
            )

        # 3. Try degraded handlers
        for pattern, handler in self._degraded_handlers.items():
            if pattern in prompt.lower() or (task_type and pattern in task_type):
                try:
                    content = handler(prompt)
                    logger.info(f"Returning degraded fallback for pattern: {pattern}")
                    return FallbackResponse(
                        content=content,
                        fallback_type=FallbackType.DEGRADED,
                        original_prompt=prompt,
                        metadata={"pattern": pattern, "agent_type": agent_type},
                    )
                except Exception as e:
                    logger.error(f"Degraded handler failed: {e}")

        return None

    def _match_static_key(
        self, prompt: str, agent_type: str, task_type: str | None
    ) -> str | None:
        """Match prompt to static response key"""
        prompt_lower = prompt.lower()

        # Health check
        if task_type == "health_check" or "health" in prompt_lower:
            return "health_check"

        # Strategy generation patterns
        if agent_type == "deepseek":
            if "momentum" in prompt_lower:
                return "strategy:momentum"
            if "mean reversion" in prompt_lower or "bollinger" in prompt_lower:
                return "strategy:mean_reversion"

        # Market research patterns
        if agent_type == "perplexity" and "market" in prompt_lower and (
            "overview" in prompt_lower or "analysis" in prompt_lower
        ):
            return "research:market_overview"

        # Risk analysis patterns
        if "risk" in prompt_lower and "portfolio" in prompt_lower:
            return "risk:portfolio"

        return None

    def cache_response(
        self,
        prompt: str,
        agent_type: str,
        content: str,
        ttl: int | None = None,
    ) -> None:
        """Cache a successful response for future fallback use"""
        self.cache.set(prompt, agent_type, content, ttl)
        logger.debug(f"Cached response for {agent_type} (TTL: {ttl or 'default'}s)")

    def get_degraded_response(
        self, prompt: str, agent_type: str, error: str | None = None
    ) -> FallbackResponse:
        """
        Generate a degraded mode response when all else fails.
        This is the last resort before returning an error.
        """
        content = f"""
## Service Temporarily Unavailable

The AI service ({agent_type}) is currently experiencing issues and cannot process your request.

**Your Request:**
{prompt[:200]}{"..." if len(prompt) > 200 else ""}

**What You Can Do:**
1. Wait a few minutes and try again
2. Check the system health dashboard
3. Try a different agent type if available

**Error Details:**
{error or "Service circuit breaker is open"}

This is a degraded response. The system will automatically recover when the service is restored.
"""

        return FallbackResponse(
            content=content,
            fallback_type=FallbackType.DEGRADED,
            original_prompt=prompt,
            metadata={"agent_type": agent_type, "error": error},
        )

    def stats(self) -> dict[str, Any]:
        """Get fallback service statistics"""
        return {
            "cache": self.cache.stats(),
            "services": {
                name: status.to_dict() for name, status in self._services.items()
            },
            "overall_health": self.get_overall_health().value,
            "static_responses_count": len(self._static_responses),
            "degraded_handlers_count": len(self._degraded_handlers),
        }


# Global singleton
_fallback_service: FallbackService | None = None


def get_fallback_service() -> FallbackService:
    """Get or create the global fallback service instance"""
    global _fallback_service
    if _fallback_service is None:
        _fallback_service = FallbackService()
    return _fallback_service


# =============================================================================
# Graceful Degradation Decorators
# =============================================================================


def with_fallback(
    agent_type: str,
    cache_successful: bool = True,
    cache_ttl: int = 3600,
):
    """
    Decorator for graceful degradation with fallback support.

    Usage:
        @with_fallback("deepseek", cache_successful=True)
        async def generate_strategy(prompt: str) -> str:
            # Call AI service
            ...
    """

    def decorator(func: Callable):
        async def wrapper(prompt: str, *args, **kwargs) -> str:
            fallback_svc = get_fallback_service()

            try:
                # Try the main function
                result = await func(prompt, *args, **kwargs)

                # Cache successful response
                if cache_successful and result:
                    fallback_svc.cache_response(
                        prompt, agent_type, result, ttl=cache_ttl
                    )

                return result

            except Exception as e:
                logger.warning(f"Primary call failed, trying fallback: {e}")

                # Try to get fallback
                fallback = fallback_svc.get_fallback(prompt, agent_type)
                if fallback:
                    logger.info(f"Using {fallback.fallback_type.value} fallback")
                    return fallback.content

                # Last resort: degraded response
                degraded = fallback_svc.get_degraded_response(
                    prompt, agent_type, str(e)
                )
                return degraded.content

        return wrapper

    return decorator


def graceful_degradation[T](
    fallback_value: T,
    log_level: str = "warning",
):
    """
    Simple decorator for graceful degradation with a default value.

    Usage:
        @graceful_degradation(fallback_value={"status": "degraded"})
        async def get_metrics() -> dict:
            ...
    """

    def decorator(func: Callable[..., T]):
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                log_func = getattr(logger, log_level, logger.warning)
                log_func(f"Graceful degradation activated for {func.__name__}: {e}")
                return fallback_value

        return wrapper

    return decorator
