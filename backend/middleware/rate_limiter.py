"""
Rate Limiter Middleware (ACTIVE).

This is the PRIMARY rate limiting implementation for the application.
Uses Token Bucket algorithm with per-IP tracking.

Storage backends:
- Redis (recommended for multi-worker): Set REDIS_URL env variable
- In-memory (single worker only): Default fallback if Redis unavailable

Configuration via environment variables:
- RATE_LIMIT_ENABLED: Enable/disable rate limiting (default: true)
- RATE_LIMIT_DEFAULT_CALLS: Default requests per period (default: 100)
- RATE_LIMIT_DEFAULT_PERIOD: Default period in seconds (default: 60)
- RATE_LIMIT_AGENT_CALLS: AI agent endpoint limit (default: 30)
- RATE_LIMIT_AGENT_PERIOD: AI agent period (default: 60)
- RATE_LIMIT_HEALTH_CALLS: Health endpoint limit (default: 300)
- RATE_LIMIT_HEALTH_PERIOD: Health period (default: 60)
- RATE_LIMIT_MARKET_CALLS: Market data limit (default: 500)
- RATE_LIMIT_MARKET_PERIOD: Market data period (default: 60)
- RATE_LIMIT_WHITELIST_IPS: Comma-separated IPs to skip (default: 127.0.0.1,::1,localhost)
- REDIS_URL: Redis connection URL for distributed rate limiting

Endpoint categories:
- /healthz, /health: High limit (300/min) for monitoring
- /api/v1/agents/query/*: Restricted (30/min) - expensive AI calls
- /api/v1/marketdata/*: High limit (500/min) - chart data
- Everything else: Default (100/min)

See also:
- backend/api/middleware_setup.py: Where this middleware is configured
- backend/services/rate_limiter.py: Service for REST API management
- backend/api/routers/rate_limiting.py: REST API for rate limit rules
"""

import asyncio
import logging
import os
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.info("Redis not available - rate limiter will use in-memory storage")


class RedisRateLimiter:
    """
    Redis-backed rate limiter for multi-worker deployments.
    Uses Lua script for atomic check-and-increment.
    """

    # Lua script for atomic rate limiting (sliding window algorithm)
    _LUA_SCRIPT = """
    local key = KEYS[1]
    local limit = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])

    -- Clean old entries
    redis.call('ZREMRANGEBYSCORE', key, 0, now - window * 1000)

    -- Count current requests
    local count = redis.call('ZCARD', key)

    if count < limit then
        -- Add new request with timestamp as score
        redis.call('ZADD', key, now, now .. '-' .. math.random(1000000))
        redis.call('PEXPIRE', key, window * 1000)
        return {1, limit - count - 1, window}
    else
        -- Get oldest entry for reset time calculation
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local reset = window
        if #oldest > 1 then
            reset = math.ceil((tonumber(oldest[2]) + window * 1000 - now) / 1000)
            if reset < 0 then reset = 0 end
        end
        return {0, 0, reset}
    end
    """

    def __init__(self, redis_url: str, prefix: str = "rate_limit:"):
        """Initialize Redis rate limiter."""
        self.redis_url = redis_url
        self.prefix = prefix
        self._client = None
        self._script_sha = None
        self._connected = False

    def _get_client(self):
        """Get or create Redis client."""
        if self._client is None:
            try:
                self._client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_timeout=1.0,
                    socket_connect_timeout=1.0,
                )
                # Load Lua script
                self._script_sha = self._client.script_load(self._LUA_SCRIPT)
                self._client.ping()
                self._connected = True
                logger.info(f"Redis rate limiter connected: {self.redis_url}")
            except Exception as e:
                logger.warning(f"Redis rate limiter connection failed: {e}")
                self._client = None
                self._connected = False
        return self._client

    def check_rate_limit(self, client_ip: str, bucket_key: str, limit: int, period: int) -> tuple[bool, int, int]:
        """
        Check rate limit using Redis.

        Returns:
            (allowed, remaining, reset_seconds)
        """
        client = self._get_client()
        if not client:
            # Fallback: allow request if Redis unavailable
            return (True, limit, period)

        key = f"{self.prefix}{client_ip}:{bucket_key}"
        now = int(time.time() * 1000)  # Milliseconds for precision

        try:
            result = client.evalsha(
                self._script_sha,
                1,  # number of keys
                key,  # KEYS[1]
                limit,  # ARGV[1]
                period,  # ARGV[2]
                now,  # ARGV[3]
            )
            allowed = result[0] == 1
            remaining = int(result[1])
            reset_seconds = int(result[2])
            return (allowed, remaining, reset_seconds)
        except redis.RedisError as e:
            logger.warning(f"Redis rate limit check failed: {e}")
            # Fallback: allow request on Redis error
            return (True, limit, period)

    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._connected

    def get_stats(self) -> dict[str, Any]:
        """Get Redis rate limiter stats."""
        client = self._get_client()
        if not client:
            return {"connected": False, "error": "Not connected"}

        try:
            # Count rate limit keys
            keys = client.keys(f"{self.prefix}*")
            return {
                "connected": True,
                "backend": "redis",
                "active_keys": len(keys),
                "redis_url": self.redis_url.split("@")[-1] if "@" in self.redis_url else self.redis_url,
            }
        except redis.RedisError as e:
            return {"connected": False, "error": str(e)}


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
        self.whitelist_ips = {ip.strip() for ip in whitelist_str.split(",") if ip.strip()}

        # Market data limits (high - charts need frequent updates)
        self.market_calls = int(os.getenv("RATE_LIMIT_MARKET_CALLS", "500"))
        self.market_period = int(os.getenv("RATE_LIMIT_MARKET_PERIOD", "60"))

        # Endpoint-specific limits
        self.endpoint_limits: dict[str, tuple] = {
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

    Supports two backends:
    - Redis (recommended for multi-worker): Atomic, distributed rate limiting
    - In-memory (fallback): Single worker only, not shared across processes
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

        # In-memory fallback storage
        self.buckets: dict[str, dict[str, TokenBucket]] = defaultdict(dict)
        self._cleanup_lock = asyncio.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes

        # Try to initialize Redis backend
        self._redis_limiter: RedisRateLimiter | None = None
        redis_url = os.getenv("REDIS_URL", "")

        if redis_url and REDIS_AVAILABLE:
            try:
                self._redis_limiter = RedisRateLimiter(redis_url)
                if self._redis_limiter.is_connected():
                    logger.info("Rate limiter using Redis backend")
                else:
                    logger.warning("Redis rate limiter failed to connect - using in-memory")
                    self._redis_limiter = None
            except Exception as e:
                logger.warning(f"Failed to init Redis rate limiter: {e} - using in-memory")
                self._redis_limiter = None
        elif not REDIS_AVAILABLE and redis_url:
            logger.warning("REDIS_URL set but redis package not installed - using in-memory")

        backend = "redis" if self._redis_limiter else "in-memory"
        logger.info(
            f"Rate limiter initialized: "
            f"enabled={self.config.enabled}, "
            f"backend={backend}, "
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
            self.buckets[client_ip][bucket_key] = TokenBucket(capacity=calls, refill_rate=refill_rate)

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
                all_stale = all(bucket.last_refill < stale_threshold for bucket in buckets.values())
                if all_stale:
                    stale_clients.append(client_ip)

            for client_ip in stale_clients:
                del self.buckets[client_ip]

            if stale_clients:
                logger.debug(f"Cleaned up {len(stale_clients)} stale rate limit buckets")

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

        # Get limit config
        calls, period = self.config.get_limit_for_path(path)
        bucket_key = self._get_bucket_key(path)

        # Try Redis backend first (if available)
        if self._redis_limiter:
            allowed, remaining, reset_time = self._redis_limiter.check_rate_limit(client_ip, bucket_key, calls, period)

            if allowed:
                response = await call_next(request)
                response.headers["X-RateLimit-Limit"] = str(calls)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Reset"] = str(reset_time)
                response.headers["X-RateLimit-Backend"] = "redis"
                return response
            else:
                logger.warning(f"Rate limit exceeded for {client_ip} on {path} (limit: {calls}/{period}s) [redis]")
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
                        "X-RateLimit-Backend": "redis",
                    },
                )

        # Fallback to in-memory rate limiting
        # Cleanup old buckets periodically
        await self._cleanup_old_buckets()

        # Get or create bucket
        bucket = self._get_or_create_bucket(client_ip, path)

        # Try to consume token
        if bucket.consume():
            # Request allowed
            response = await call_next(request)

            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(calls)
            response.headers["X-RateLimit-Remaining"] = str(bucket.get_remaining())
            response.headers["X-RateLimit-Reset"] = str(bucket.get_reset_time())
            response.headers["X-RateLimit-Backend"] = "memory"

            return response
        else:
            # Rate limited
            logger.warning(f"Rate limit exceeded for {client_ip} on {path} (limit: {calls}/{period}s) [memory]")

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
                    "X-RateLimit-Backend": "memory",
                },
            )

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        # Get Redis stats if available
        if self._redis_limiter:
            redis_stats = self._redis_limiter.get_stats()
            return {
                "enabled": self.config.enabled,
                "backend": "redis",
                "redis": redis_stats,
                "fallback_clients": len(self.buckets),
            }

        # In-memory stats
        stats = {
            "enabled": self.config.enabled,
            "backend": "memory",
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
_rate_limiter: RateLimitMiddleware | None = None


def get_rate_limiter() -> dict[str, Any]:
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


def get_rate_limiter_stats() -> dict[str, Any]:
    """Get statistics from the global rate limiter."""
    if _rate_limiter:
        return _rate_limiter.get_stats()
    return {"error": "Rate limiter not initialized"}


__all__ = [
    "RateLimitConfig",
    "RateLimitMiddleware",
    "get_rate_limiter",
    "get_rate_limiter_stats",
]
