"""
Graceful Degradation System

Provides fallback responses and cached data when services are unavailable.
Ensures system stability under failure conditions.

Features:
- Cached response storage with TTL
- Fallback handlers for all critical services
- Degraded mode indicators
- Automatic recovery detection
- Circuit breaker integration
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceStatus(str, Enum):
    """Status of a service."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class FallbackType(str, Enum):
    """Type of fallback strategy."""

    CACHED = "cached"  # Return cached response
    STATIC = "static"  # Return static default
    COMPUTED = "computed"  # Compute fallback
    PASSTHROUGH = "passthrough"  # Pass error through


@dataclass
class CachedResponse:
    """Cached response with metadata."""

    key: str
    value: Any
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    source: str = "unknown"

    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()

    def access(self):
        """Record cache access."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)


@dataclass
class ServiceHealth:
    """Health information for a service."""

    name: str
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_check: Optional[datetime] = None
    last_success: Optional[datetime] = None
    failure_count: int = 0
    success_count: int = 0
    degraded_since: Optional[datetime] = None
    error_message: Optional[str] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.failure_count + self.success_count
        return (self.success_count / total * 100) if total > 0 else 0.0

    def record_success(self):
        """Record successful call."""
        self.success_count += 1
        self.last_success = datetime.now(timezone.utc)
        self.last_check = datetime.now(timezone.utc)
        if self.status != ServiceStatus.HEALTHY:
            self.status = ServiceStatus.HEALTHY
            self.degraded_since = None
            self.error_message = None

    def record_failure(self, error: Optional[str] = None):
        """Record failed call."""
        self.failure_count += 1
        self.last_check = datetime.now(timezone.utc)
        self.error_message = error
        if self.status == ServiceStatus.HEALTHY:
            self.status = ServiceStatus.DEGRADED
            self.degraded_since = datetime.now(timezone.utc)


class FallbackCache:
    """
    In-memory cache for fallback responses.

    Stores last successful responses for use when services are unavailable.
    """

    def __init__(
        self,
        default_ttl: int = 3600,  # 1 hour default
        max_entries: int = 1000,
        cleanup_interval: int = 300,  # 5 minutes
    ):
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self.cleanup_interval = cleanup_interval

        self._cache: Dict[str, CachedResponse] = {}
        self._last_cleanup = time.time()

        # Metrics
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _cleanup_if_needed(self):
        """Remove expired entries if cleanup interval passed."""
        now = time.time()
        if now - self._last_cleanup < self.cleanup_interval:
            return

        expired_keys = [k for k, v in self._cache.items() if v.is_expired]
        for key in expired_keys:
            del self._cache[key]
            self.evictions += 1

        self._last_cleanup = now

    def _ensure_capacity(self):
        """Ensure cache doesn't exceed max entries."""
        if len(self._cache) <= self.max_entries:
            return

        # Remove oldest entries
        sorted_entries = sorted(
            self._cache.items(), key=lambda x: x[1].last_accessed or x[1].created_at
        )

        to_remove = len(self._cache) - self.max_entries + 10  # Remove 10 extra
        for key, _ in sorted_entries[:to_remove]:
            del self._cache[key]
            self.evictions += 1

    def set(
        self, key: str, value: Any, ttl: Optional[int] = None, source: str = "unknown"
    ):
        """Store a value in the cache."""
        self._cleanup_if_needed()
        self._ensure_capacity()

        ttl = ttl or self.default_ttl
        now = datetime.now(timezone.utc)

        self._cache[key] = CachedResponse(
            key=key,
            value=value,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl),
            source=source,
        )

    def get(self, key: str, allow_expired: bool = False) -> Optional[Any]:
        """Get a value from the cache."""
        entry = self._cache.get(key)
        if not entry:
            self.misses += 1
            return None

        if entry.is_expired and not allow_expired:
            self.misses += 1
            return None

        entry.access()
        self.hits += 1
        return entry.value

    def get_with_metadata(self, key: str) -> Optional[CachedResponse]:
        """Get cache entry with full metadata."""
        return self._cache.get(key)

    def invalidate(self, key: str):
        """Remove entry from cache."""
        if key in self._cache:
            del self._cache[key]

    def clear(self):
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hits + self.misses
        return {
            "entries": len(self._cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": (self.hits / total_requests * 100) if total_requests > 0 else 0,
            "evictions": self.evictions,
            "max_entries": self.max_entries,
            "default_ttl": self.default_ttl,
        }


class GracefulDegradationManager:
    """
    Central manager for graceful degradation.

    Coordinates fallback handlers, caching, and service health tracking.
    """

    def __init__(self):
        self.cache = FallbackCache()
        self.services: Dict[str, ServiceHealth] = {}
        self.fallback_handlers: Dict[str, Callable] = {}
        self.static_fallbacks: Dict[str, Any] = {}

        # Default static fallbacks
        self._register_default_fallbacks()

    def _register_default_fallbacks(self):
        """Register default fallback responses."""
        self.static_fallbacks = {
            # AI Agents fallback
            "deepseek_query": {
                "response": "AI analysis is temporarily unavailable. Please try again later.",
                "status": "degraded",
                "cached": False,
            },
            "perplexity_query": {
                "response": "AI research is temporarily unavailable. Please try again later.",
                "status": "degraded",
                "cached": False,
            },
            # Market data fallback
            "market_data": {
                "data": [],
                "status": "degraded",
                "message": "Market data temporarily unavailable",
            },
            # Strategy analysis fallback
            "strategy_analysis": {
                "result": None,
                "status": "degraded",
                "message": "Strategy analysis temporarily unavailable",
            },
            # Health check fallback
            "health": {
                "status": "degraded",
                "services": {},
                "message": "Health check returned degraded status",
            },
        }

    def register_service(self, name: str) -> ServiceHealth:
        """Register a service for health tracking."""
        if name not in self.services:
            self.services[name] = ServiceHealth(name=name)
        return self.services[name]

    def get_service(self, name: str) -> Optional[ServiceHealth]:
        """Get service health information."""
        return self.services.get(name)

    def register_fallback_handler(self, key: str, handler: Callable[..., Any]):
        """Register a custom fallback handler."""
        self.fallback_handlers[key] = handler

    def register_static_fallback(self, key: str, value: Any):
        """Register a static fallback value."""
        self.static_fallbacks[key] = value

    def cache_response(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        service: Optional[str] = None,
    ):
        """Cache a successful response for fallback."""
        self.cache.set(key, value, ttl=ttl, source=service or "unknown")

    def get_fallback(
        self,
        key: str,
        fallback_type: FallbackType = FallbackType.CACHED,
        *args,
        **kwargs,
    ) -> Optional[Any]:
        """
        Get fallback response for a key.

        Args:
            key: The cache/fallback key
            fallback_type: Strategy for fallback
            *args, **kwargs: Arguments for computed fallbacks

        Returns:
            Fallback value or None if not available
        """
        if fallback_type == FallbackType.CACHED:
            # Try cache first
            cached = self.cache.get(key, allow_expired=True)  # Allow stale data
            if cached:
                logger.info(f"Using cached fallback for '{key}'")
                return cached

            # Fall through to static
            fallback_type = FallbackType.STATIC

        if fallback_type == FallbackType.STATIC:
            if key in self.static_fallbacks:
                logger.info(f"Using static fallback for '{key}'")
                return self.static_fallbacks[key]

        if fallback_type == FallbackType.COMPUTED:
            if key in self.fallback_handlers:
                logger.info(f"Using computed fallback for '{key}'")
                return self.fallback_handlers[key](*args, **kwargs)

        return None

    def record_success(
        self, service: str, key: str, response: Any, ttl: Optional[int] = None
    ):
        """Record successful service call and cache response."""
        svc = self.register_service(service)
        svc.record_success()
        self.cache_response(key, response, ttl=ttl, service=service)

    def record_failure(self, service: str, error: Optional[str] = None):
        """Record service failure."""
        svc = self.register_service(service)
        svc.record_failure(error)

    def get_degraded_services(self) -> List[ServiceHealth]:
        """Get list of degraded services."""
        return [s for s in self.services.values() if s.status != ServiceStatus.HEALTHY]

    def get_overall_status(self) -> ServiceStatus:
        """Get overall system status."""
        if not self.services:
            return ServiceStatus.UNKNOWN

        degraded = self.get_degraded_services()
        if not degraded:
            return ServiceStatus.HEALTHY

        unavailable = [s for s in degraded if s.status == ServiceStatus.UNAVAILABLE]
        if len(unavailable) == len(self.services):
            return ServiceStatus.UNAVAILABLE

        return ServiceStatus.DEGRADED

    def get_status_report(self) -> Dict[str, Any]:
        """Get comprehensive status report."""
        return {
            "overall_status": self.get_overall_status().value,
            "services": {
                name: {
                    "status": svc.status.value,
                    "success_rate": round(svc.success_rate, 2),
                    "failure_count": svc.failure_count,
                    "success_count": svc.success_count,
                    "degraded_since": svc.degraded_since.isoformat()
                    if svc.degraded_since
                    else None,
                    "error_message": svc.error_message,
                }
                for name, svc in self.services.items()
            },
            "cache_stats": self.cache.get_stats(),
            "fallback_handlers": list(self.fallback_handlers.keys()),
            "static_fallbacks": list(self.static_fallbacks.keys()),
        }


# Global instance
_degradation_manager: Optional[GracefulDegradationManager] = None


def get_degradation_manager() -> GracefulDegradationManager:
    """Get or create the global degradation manager."""
    global _degradation_manager
    if _degradation_manager is None:
        _degradation_manager = GracefulDegradationManager()
    return _degradation_manager


def with_fallback(
    cache_key: str,
    service_name: str,
    fallback_type: FallbackType = FallbackType.CACHED,
    cache_ttl: int = 3600,
):
    """
    Decorator for graceful degradation with automatic caching and fallback.

    Usage:
        @with_fallback("market_data_btc", "market_data_service")
        async def get_market_data(symbol: str):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            manager = get_degradation_manager()

            try:
                result = await func(*args, **kwargs)
                manager.record_success(service_name, cache_key, result, ttl=cache_ttl)
                return result
            except Exception as e:
                logger.warning(f"Service '{service_name}' failed: {e}")
                manager.record_failure(service_name, str(e))

                fallback = manager.get_fallback(
                    cache_key, fallback_type, *args, **kwargs
                )
                if fallback is not None:
                    logger.info(f"Returning fallback for '{cache_key}'")
                    return fallback

                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            manager = get_degradation_manager()

            try:
                result = func(*args, **kwargs)
                manager.record_success(service_name, cache_key, result, ttl=cache_ttl)
                return result
            except Exception as e:
                logger.warning(f"Service '{service_name}' failed: {e}")
                manager.record_failure(service_name, str(e))

                fallback = manager.get_fallback(
                    cache_key, fallback_type, *args, **kwargs
                )
                if fallback is not None:
                    logger.info(f"Returning fallback for '{cache_key}'")
                    return fallback

                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
