"""
Rate Limiting Middleware для FastAPI (DEPRECATED)
=================================================

.. deprecated:: 2.9.4
    This module is NOT used in production. The active rate limiting middleware is
    ``backend.middleware.rate_limiter.RateLimitMiddleware`` which uses Token Bucket
    algorithm with in-memory storage.

    This Redis-based sliding window implementation is kept for potential future use
    in distributed deployments where Redis-backed rate limiting is needed.

For current rate limiting configuration, see:
- backend/middleware/rate_limiter.py - Active Token Bucket implementation
- backend/api/middleware_setup.py - Where middleware is configured

Original description:
---------------------
Защищает API от DDoS и злоупотреблений
Использует Redis для distributed rate limiting
"""

import hashlib
import logging
import time
from collections.abc import Callable

import redis
from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using sliding window algorithm

    Features:
    - Per-IP rate limiting
    - Per-API-key rate limiting
    - Different limits for different endpoint groups
    - Distributed rate limiting via Redis
    """

    def __init__(
        self,
        app: ASGIApp,
        redis_client: redis.Redis | None = None,
        default_limit: int = 100,  # requests per window
        window_seconds: int = 60,  # time window
        enabled: bool = True,
    ):
        super().__init__(app)
        self.redis = redis_client
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.enabled = enabled

        # Endpoint-specific limits
        self.endpoint_limits = {
            "/api/v1/agents/": (10, 60),  # 10 requests per minute
            "/api/v1/backtest/": (30, 60),  # 30 requests per minute
            "/api/v1/strategies/": (50, 60),  # 50 requests per minute
            "/api/v1/trading/": (20, 60),  # 20 requests per minute (critical)
        }

        logger.info(f"RateLimitMiddleware initialized (enabled={enabled})")

    def _get_client_identifier(self, request: Request) -> str:
        """Get unique client identifier (IP + API key if present)"""
        # Try to get API key from header
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization")
        if api_key:
            # Use hash of API key for privacy
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
            return f"api_key:{key_hash}"

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return f"ip:{client_ip}"

    def _get_rate_limit(self, path: str) -> tuple[int, int]:
        """Get rate limit for specific endpoint"""
        # Check if path matches any endpoint pattern
        for pattern, limits in self.endpoint_limits.items():
            if path.startswith(pattern):
                return limits

        # Default limit
        return (self.default_limit, self.window_seconds)

    async def _check_rate_limit(self, client_id: str, path: str) -> tuple[bool, dict]:
        """
        Check if request should be rate limited

        Returns:
            (allowed, info) where info contains limit details
        """
        limit, window = self._get_rate_limit(path)

        if not self.redis:
            # If Redis not available, allow request but log warning
            logger.warning("Rate limiting disabled: Redis not configured")
            return True, {"limit": limit, "remaining": limit, "reset": 0}

        try:
            # Redis key for this client and endpoint
            key = f"rate_limit:{client_id}:{path}"
            current_time = int(time.time())
            window_start = current_time - window

            # Use Redis sorted set for sliding window
            pipe = self.redis.pipeline()

            # Remove old entries outside window
            pipe.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(current_time): current_time})

            # Set expiry
            pipe.expire(key, window)

            results = pipe.execute()
            request_count = results[1]

            # Check if limit exceeded
            allowed = request_count < limit
            remaining = max(0, limit - request_count - 1)
            reset = current_time + window

            info = {
                "limit": limit,
                "remaining": remaining,
                "reset": reset,
                "retry_after": window if not allowed else 0,
            }

            return allowed, info

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}", exc_info=True)
            # On error, allow request (fail open)
            return True, {"limit": limit, "remaining": limit, "reset": 0}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting"""
        if not self.enabled:
            return await call_next(request)

        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/health", "/metrics", "/monitoring/metrics"]:
            return await call_next(request)

        # Get client identifier
        client_id = self._get_client_identifier(request)

        # Check rate limit
        allowed, info = await self._check_rate_limit(client_id, request.url.path)

        # Add rate limit headers to response
        async def add_headers(response: Response) -> Response:
            response.headers["X-RateLimit-Limit"] = str(info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
            response.headers["X-RateLimit-Reset"] = str(info["reset"])
            return response

        if not allowed:
            # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded for {client_id} on {request.url.path}",
                extra={"client_id": client_id, "path": request.url.path},
            )

            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": info["limit"],
                    "retry_after": info["retry_after"],
                },
                headers={
                    "Retry-After": str(info["retry_after"]),
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset"]),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        return await add_headers(response)


# Helper function to get Redis client
def get_redis_client() -> redis.Redis | None:
    """Get Redis client for rate limiting"""
    try:
        from backend.core.config import settings

        if not settings.REDIS_HOST:
            return None

        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=False,
        )

        # Test connection
        client.ping()
        return client

    except Exception as e:
        logger.error(f"Failed to connect to Redis for rate limiting: {e}")
        return None
