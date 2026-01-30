"""
API Rate Limiting Middleware using slowapi (DEPRECATED).

.. deprecated:: 2.9.4
    This module is NOT used in production. The active rate limiting middleware is
    ``backend.middleware.rate_limiter.RateLimitMiddleware`` which uses Token Bucket
    algorithm configured via environment variables.

    This slowapi-based implementation is kept for potential decorator-based
    per-endpoint rate limiting use cases.

For current rate limiting configuration, see:
- backend/middleware/rate_limiter.py - Active Token Bucket implementation
- backend/api/middleware_setup.py - Where middleware is configured

Original description:
---------------------
Provides configurable rate limiting to protect the API from abuse.
Uses Redis as backend for distributed rate limiting (falls back to memory).

Usage (if re-enabled):
    from backend.api.middleware.rate_limiter import limiter, rate_limit_exceeded_handler

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @app.get("/api/endpoint")
    @limiter.limit("10/minute")
    async def my_endpoint(request: Request):
        ...
"""

import logging
import os
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Try to import slowapi, provide fallback if not installed
try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address  # noqa: F401

    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    logger.warning("slowapi not installed. Rate limiting disabled. Install with: pip install slowapi")


def get_client_identifier(request: Request) -> str:
    """
    Get unique identifier for rate limiting.

    Priority:
    1. X-Forwarded-For header (for proxied requests)
    2. X-Real-IP header
    3. Client host from request
    """
    # Check for proxy headers
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take first IP in chain (original client)
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to direct client
    if request.client:
        return request.client.host

    return "unknown"


# Rate limit configuration from environment
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "100/minute")
RATE_LIMIT_BURST = os.getenv("RATE_LIMIT_BURST", "200/minute")
REDIS_URL = os.getenv("REDIS_URL", "")


def create_limiter() -> "Limiter | None":
    """Create and configure the rate limiter."""
    if not SLOWAPI_AVAILABLE:
        return None

    if not RATE_LIMIT_ENABLED:
        logger.info("Rate limiting is disabled via RATE_LIMIT_ENABLED=false")
        return None

    # Try Redis backend for distributed limiting
    storage_uri = None
    if REDIS_URL:
        try:
            storage_uri = REDIS_URL
            logger.info("Rate limiter using Redis backend")
        except Exception as e:
            logger.warning(f"Failed to configure Redis for rate limiting: {e}")

    limiter = Limiter(
        key_func=get_client_identifier,
        default_limits=[RATE_LIMIT_DEFAULT],
        storage_uri=storage_uri,
        strategy="fixed-window",  # or "moving-window" for stricter limiting
        headers_enabled=True,  # Add X-RateLimit-* headers to responses
    )

    logger.info(f"Rate limiter initialized: default={RATE_LIMIT_DEFAULT}, burst={RATE_LIMIT_BURST}")
    return limiter


# Create global limiter instance
limiter = create_limiter()


async def rate_limit_exceeded_handler(request: Request, exc: "RateLimitExceeded") -> Response:
    """
    Custom handler for rate limit exceeded errors.

    Returns a JSON response with:
    - 429 status code
    - Retry-After header
    - Detailed error message
    """
    retry_after = getattr(exc, "retry_after", 60)

    logger.warning(f"Rate limit exceeded for {get_client_identifier(request)}: {request.method} {request.url.path}")

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please slow down.",
            "detail": str(exc.detail) if hasattr(exc, "detail") else "Rate limit exceeded",
            "retry_after": retry_after,
        },
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": RATE_LIMIT_DEFAULT,
        },
    )


# Pre-configured rate limit decorators for common use cases
def rate_limit_standard(func: Callable) -> Callable:
    """Standard rate limit: 100 requests/minute."""
    if limiter:
        return limiter.limit(RATE_LIMIT_DEFAULT)(func)
    return func


def rate_limit_strict(func: Callable) -> Callable:
    """Strict rate limit: 10 requests/minute (for expensive operations)."""
    if limiter:
        return limiter.limit("10/minute")(func)
    return func


def rate_limit_relaxed(func: Callable) -> Callable:
    """Relaxed rate limit: 200 requests/minute (for lightweight endpoints)."""
    if limiter:
        return limiter.limit(RATE_LIMIT_BURST)(func)
    return func


def rate_limit_auth(func: Callable) -> Callable:
    """Auth rate limit: 5 requests/minute (for login/register)."""
    if limiter:
        return limiter.limit("5/minute")(func)
    return func


# Export RateLimitExceeded for exception handler registration
if SLOWAPI_AVAILABLE:
    from slowapi.errors import RateLimitExceeded as RateLimitExceededException
else:
    # Dummy exception class when slowapi is not available
    class RateLimitExceededException(Exception):
        """Placeholder when slowapi is not installed."""

        pass
