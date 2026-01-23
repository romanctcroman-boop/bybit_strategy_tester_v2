"""
Rate Limiter Middleware
Provides rate limiting for API endpoints using Token Bucket algorithm.
Production-ready implementation with configurable limits per endpoint.
"""

import asyncio
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: int  # Maximum tokens
    refill_rate: float  # Tokens per second
    tokens: float = field(default=0.0)
    last_refill: float = field(default_factory=time.time)

    def __post_init__(self):
        self.tokens = float(self.capacity)

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if successful."""
        now = time.time()
        # Refill tokens based on time elapsed
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def get_remaining(self) -> int:
        """Get remaining tokens."""
        return max(0, int(self.tokens))

    def get_reset_time(self) -> int:
        """Get seconds until bucket is full again."""
        if self.tokens >= self.capacity:
            return 0
        tokens_needed = self.capacity - self.tokens
        return int(tokens_needed / self.refill_rate) + 1


class RateLimitConfig:
    """Configuration for rate limiting."""

    def __init__(self):
        # Default limits - can be overridden via environment variables
        self.default_calls = int(os.getenv("RATE_LIMIT_DEFAULT_CALLS", "100"))
        self.default_period = int(os.getenv("RATE_LIMIT_DEFAULT_PERIOD", "60"))

        # Agent endpoints - more restrictive (expensive API calls)
        self.agent_calls = int(os.getenv("RATE_LIMIT_AGENT_CALLS", "30"))
        self.agent_period = int(os.getenv("RATE_LIMIT_AGENT_PERIOD", "60"))

        # Health/status endpoints - more permissive
        self.health_calls = int(os.getenv("RATE_LIMIT_HEALTH_CALLS", "300"))
        self.health_period = int(os.getenv("RATE_LIMIT_HEALTH_PERIOD", "60"))

        # Enabled flag
        self.enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in (
            "true",
            "1",
            "yes",
        )

        # Whitelist IPs (comma-separated)
        whitelist_str = os.getenv("RATE_LIMIT_WHITELIST_IPS", "127.0.0.1,::1,localhost")
        self.whitelist_ips = set(
            ip.strip() for ip in whitelist_str.split(",") if ip.strip()
        )

        # Market data limits (high - charts need frequent updates)
        self.market_calls = int(os.getenv("RATE_LIMIT_MARKET_CALLS", "500"))
        self.market_period = int(os.getenv("RATE_LIMIT_MARKET_PERIOD", "60"))

        # Endpoint-specific limits
        self.endpoint_limits: Dict[str, tuple] = {
            "/healthz": (self.health_calls, self.health_period),
            "/health": (self.health_calls, self.health_period),
            "/api/v1/agents/stats": (self.health_calls, self.health_period),
            "/api/v1/agents/query/deepseek": (self.agent_calls, self.agent_period),
            "/api/v1/agents/query/perplexity": (self.agent_calls, self.agent_period),
            "/api/v1/agents/consensus": (self.agent_calls, self.agent_period),
            # Market data endpoints - charts need high throughput
            "/api/v1/marketdata/bybit/klines/smart": (
                self.market_calls,
                self.market_period,
            ),
            "/api/v1/marketdata/bybit/klines/smart-history": (
                self.market_calls,
                self.market_period,
            ),
            "/api/v1/marketdata/bybit/klines/fetch": (
                self.market_calls,
                self.market_period,
            ),
        }

    def get_limit_for_path(self, path: str) -> tuple:
        """Get rate limit for specific path."""
        # Check exact match first
        if path in self.endpoint_limits:
            return self.endpoint_limits[path]

        # Check prefix matches
        for endpoint, limits in self.endpoint_limits.items():
            if path.startswith(endpoint):
                return limits

        # Default limits
        return (self.default_calls, self.default_period)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Production-ready rate limiting middleware.
    Uses Token Bucket algorithm with per-IP tracking.
    """

    def __init__(self, app, **kwargs):
        """
        Initialize rate limiter.

        Args:
            app: FastAPI application
            **kwargs: Additional keyword arguments (ignored, uses env vars)
        """
        super().__init__(app)
        self.config = RateLimitConfig()
        self.buckets: Dict[str, Dict[str, TokenBucket]] = defaultdict(dict)
        self._cleanup_lock = asyncio.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes

        logger.info(
            f"Rate limiter initialized: "
            f"enabled={self.config.enabled}, "
            f"default={self.config.default_calls}/{self.config.default_period}s, "
            f"agent={self.config.agent_calls}/{self.config.agent_period}s"
        )

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check X-Forwarded-For header (for reverse proxy)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        # Fallback to direct client
        if request.client:
            return request.client.host

        return "unknown"

    def _get_bucket_key(self, path: str) -> str:
        """Get bucket key for path (group similar endpoints)."""
        # Group market data endpoints (charts need high throughput)
        if "/marketdata/" in path:
            return "marketdata"
        # Group agent query endpoints
        if "/agents/query/" in path:
            return "agents_query"
        if "/agents/" in path:
            return "agents"
        if path in ("/healthz", "/health"):
            return "health"
        return "default"

    def _get_or_create_bucket(self, client_ip: str, path: str) -> TokenBucket:
        """Get or create token bucket for client and path."""
        bucket_key = self._get_bucket_key(path)

        if bucket_key not in self.buckets[client_ip]:
            calls, period = self.config.get_limit_for_path(path)
            refill_rate = calls / period  # tokens per second
            self.buckets[client_ip][bucket_key] = TokenBucket(
                capacity=calls, refill_rate=refill_rate
            )

        return self.buckets[client_ip][bucket_key]

    async def _cleanup_old_buckets(self):
        """Remove stale buckets to prevent memory leaks."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        async with self._cleanup_lock:
            if now - self._last_cleanup < self._cleanup_interval:
                return

            stale_threshold = now - 3600  # 1 hour
            stale_clients = []

            for client_ip, buckets in self.buckets.items():
                all_stale = all(
                    bucket.last_refill < stale_threshold for bucket in buckets.values()
                )
                if all_stale:
                    stale_clients.append(client_ip)

            for client_ip in stale_clients:
                del self.buckets[client_ip]

            if stale_clients:
                logger.debug(
                    f"Cleaned up {len(stale_clients)} stale rate limit buckets"
                )

            self._last_cleanup = now

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with rate limiting.
        """
        # Skip if disabled
        if not self.config.enabled:
            response = await call_next(request)
            return response

        client_ip = self._get_client_ip(request)
        path = request.url.path

        # Skip whitelist IPs (normalize localhost variants)
        normalized_ip = client_ip.lower().strip()
        is_localhost = (
            normalized_ip in self.config.whitelist_ips
            or normalized_ip == "127.0.0.1"
            or normalized_ip == "::1"
            or normalized_ip == "localhost"
            or normalized_ip.startswith("127.")
            or normalized_ip.startswith("::ffff:127.")
        )

        if is_localhost:
            response = await call_next(request)
            return response

        # Cleanup old buckets periodically
        await self._cleanup_old_buckets()

        # Get or create bucket
        bucket = self._get_or_create_bucket(client_ip, path)
        calls, period = self.config.get_limit_for_path(path)

        # Try to consume token
        if bucket.consume():
            # Request allowed
            response = await call_next(request)

            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(calls)
            response.headers["X-RateLimit-Remaining"] = str(bucket.get_remaining())
            response.headers["X-RateLimit-Reset"] = str(bucket.get_reset_time())

            return response
        else:
            # Rate limited
            logger.warning(
                f"Rate limit exceeded for {client_ip} on {path} "
                f"(limit: {calls}/{period}s)"
            )

            reset_time = bucket.get_reset_time()

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Try again in {reset_time} seconds.",
                    "retry_after": reset_time,
                },
                headers={
                    "X-RateLimit-Limit": str(calls),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time),
                },
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        stats = {
            "enabled": self.config.enabled,
            "active_clients": len(self.buckets),
            "buckets_by_client": {},
        }

        for client_ip, buckets in self.buckets.items():
            stats["buckets_by_client"][client_ip] = {
                key: {
                    "remaining": bucket.get_remaining(),
                    "capacity": bucket.capacity,
                    "reset_in": bucket.get_reset_time(),
                }
                for key, bucket in buckets.items()
            }

        return stats


# Global rate limiter instance
_rate_limiter: Optional[RateLimitMiddleware] = None


def get_rate_limiter() -> Dict[str, Any]:
    """
    Get rate limiter configuration.

    Returns:
        Rate limiter configuration dict
    """
    config = RateLimitConfig()
    return {
        "enabled": config.enabled,
        "calls": config.default_calls,
        "period": config.default_period,
        "agent_calls": config.agent_calls,
        "agent_period": config.agent_period,
    }


def get_rate_limiter_stats() -> Dict[str, Any]:
    """Get statistics from the global rate limiter."""
    if _rate_limiter:
        return _rate_limiter.get_stats()
    return {"error": "Rate limiter not initialized"}


__all__ = [
    "RateLimitMiddleware",
    "get_rate_limiter",
    "get_rate_limiter_stats",
    "RateLimitConfig",
]
