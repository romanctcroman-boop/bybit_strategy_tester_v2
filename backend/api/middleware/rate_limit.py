"""
Rate limiting middleware for FastAPI.

Provides protection against:
- Excessive API usage
- DDoS attacks
- Bybit API rate limit violations

Features:
- Per-IP rate limiting
- Per-endpoint rate limiting
- Redis-backed shared state (multi-instance support)
- Sliding window algorithm
- Customizable limits
"""

import time
from typing import Optional, Dict
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
import redis
from redis.exceptions import RedisError

from backend.core.config import get_config
from backend.core.logging_config import get_logger
from backend.core.metrics import record_rate_limit_hit

config = get_config()
logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using sliding window algorithm.
    
    Limits:
    - Per IP: configurable requests per minute
    - Per endpoint: configurable requests per minute
    - Global: configurable total requests per minute
    """
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        redis_client: Optional[redis.Redis] = None,
        enable_per_ip: bool = True,
        enable_per_endpoint: bool = True,
        enable_global: bool = False,
        global_limit: int = 1000,
        excluded_paths: Optional[list] = None
    ):
        """
        Initialize rate limiter.
        
        Args:
            app: FastAPI application
            requests_per_minute: Default limit per IP per minute
            redis_client: Redis client (optional, for multi-instance)
            enable_per_ip: Enable per-IP limiting
            enable_per_endpoint: Enable per-endpoint limiting
            enable_global: Enable global limiting
            global_limit: Global requests per minute
            excluded_paths: Paths to exclude from rate limiting
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.redis_client = redis_client
        self.enable_per_ip = enable_per_ip
        self.enable_per_endpoint = enable_per_endpoint
        self.enable_global = enable_global
        self.global_limit = global_limit
        self.excluded_paths = excluded_paths or [
            '/health',
            '/health/live',
            '/health/ready',
            '/docs',
            '/openapi.json'
        ]
        
        # In-memory fallback (if no Redis)
        self._local_cache: Dict[str, list] = {}
        
        logger.info(
            "Rate limiting middleware initialized",
            extra={
                'per_ip_limit': requests_per_minute,
                'global_limit': global_limit if enable_global else None,
                'redis_enabled': bool(redis_client)
            }
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Try X-Forwarded-For first (for proxies)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        # Fallback to direct client
        if request.client:
            return request.client.host
        
        return 'unknown'
    
    def _make_key(self, identifier: str, endpoint: str = '') -> str:
        """Generate cache key for rate limiting."""
        if endpoint:
            return f"ratelimit:{identifier}:{endpoint}"
        return f"ratelimit:{identifier}"
    
    def _check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60
    ) -> tuple[bool, int]:
        """
        Check if request exceeds rate limit.
        
        Args:
            key: Cache key
            limit: Max requests per window
            window_seconds: Time window in seconds
            
        Returns:
            (allowed: bool, remaining: int)
        """
        now = time.time()
        window_start = now - window_seconds
        
        # Use Redis if available
        if self.redis_client:
            try:
                # Use Redis sorted set for sliding window
                pipe = self.redis_client.pipeline()
                
                # Remove old entries
                pipe.zremrangebyscore(key, 0, window_start)
                
                # Count current entries
                pipe.zcard(key)
                
                # Add current request
                pipe.zadd(key, {str(now): now})
                
                # Set expiry
                pipe.expire(key, window_seconds)
                
                results = pipe.execute()
                current_count = results[1]
                
                allowed = current_count < limit
                remaining = max(0, limit - current_count - 1)
                
                return allowed, remaining
                
            except RedisError as e:
                logger.warning(f"Redis rate limit check failed: {e}, allowing request")
                return True, limit
        
        # Fallback to in-memory cache
        if key not in self._local_cache:
            self._local_cache[key] = []
        
        # Clean old entries
        self._local_cache[key] = [
            t for t in self._local_cache[key]
            if t > window_start
        ]
        
        current_count = len(self._local_cache[key])
        allowed = current_count < limit
        remaining = max(0, limit - current_count - 1)
        
        if allowed:
            self._local_cache[key].append(now)
        
        return allowed, remaining
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        
        # Skip excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        client_ip = self._get_client_ip(request)
        endpoint = request.url.path
        
        # Check per-IP limit
        if self.enable_per_ip:
            key = self._make_key(client_ip)
            allowed, remaining = self._check_rate_limit(key, self.requests_per_minute)
            
            if not allowed:
                logger.warning(
                    f"Rate limit exceeded for IP {client_ip}",
                    extra={'ip': client_ip, 'endpoint': endpoint}
                )
                record_rate_limit_hit(client_ip)
                
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        'error': 'Rate limit exceeded',
                        'message': f'Too many requests. Limit: {self.requests_per_minute} per minute',
                        'retry_after': 60
                    },
                    headers={
                        'X-RateLimit-Limit': str(self.requests_per_minute),
                        'X-RateLimit-Remaining': '0',
                        'X-RateLimit-Reset': str(int(time.time()) + 60),
                        'Retry-After': '60'
                    }
                )
        
        # Check per-endpoint limit
        if self.enable_per_endpoint:
            key = self._make_key(client_ip, endpoint)
            allowed, remaining = self._check_rate_limit(key, self.requests_per_minute)
            
            if not allowed:
                logger.warning(
                    f"Endpoint rate limit exceeded: {endpoint}",
                    extra={'ip': client_ip, 'endpoint': endpoint}
                )
                record_rate_limit_hit(f"{client_ip}:{endpoint}")
                
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        'error': 'Endpoint rate limit exceeded',
                        'message': f'Too many requests to {endpoint}',
                        'retry_after': 60
                    },
                    headers={'Retry-After': '60'}
                )
        
        # Check global limit
        if self.enable_global:
            key = self._make_key('global')
            allowed, remaining = self._check_rate_limit(key, self.global_limit)
            
            if not allowed:
                logger.error("Global rate limit exceeded")
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        'error': 'Service temporarily unavailable',
                        'message': 'Global rate limit exceeded',
                        'retry_after': 60
                    },
                    headers={'Retry-After': '60'}
                )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers['X-RateLimit-Limit'] = str(self.requests_per_minute)
        
        return response


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts limits based on Bybit API responses.
    
    Monitors:
    - 429 responses from Bybit API
    - Response times
    - Error rates
    
    Automatically adjusts:
    - Request rate
    - Concurrent connections
    """
    
    def __init__(
        self,
        initial_rate: float = 0.2,
        min_rate: float = 0.5,
        max_rate: float = 0.05,
        adjustment_factor: float = 1.5
    ):
        """
        Initialize adaptive rate limiter.
        
        Args:
            initial_rate: Initial delay between requests (seconds)
            min_rate: Minimum delay (fastest)
            max_rate: Maximum delay (slowest)
            adjustment_factor: Rate adjustment multiplier
        """
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.adjustment_factor = adjustment_factor
        
        self._consecutive_successes = 0
        self._consecutive_failures = 0
        
        logger.info(f"Adaptive rate limiter initialized: {initial_rate}s")
    
    def on_success(self):
        """Record successful request."""
        self._consecutive_successes += 1
        self._consecutive_failures = 0
        
        # Speed up after 10 consecutive successes
        if self._consecutive_successes >= 10:
            old_rate = self.current_rate
            self.current_rate = max(
                self.max_rate,
                self.current_rate / self.adjustment_factor
            )
            
            if old_rate != self.current_rate:
                logger.info(f"Rate limit increased: {old_rate:.3f}s -> {self.current_rate:.3f}s")
            
            self._consecutive_successes = 0
    
    def on_rate_limit_hit(self):
        """Record rate limit violation."""
        self._consecutive_failures += 1
        self._consecutive_successes = 0
        
        # Slow down immediately
        old_rate = self.current_rate
        self.current_rate = min(
            self.min_rate,
            self.current_rate * self.adjustment_factor
        )
        
        logger.warning(
            f"Rate limit hit! Slowing down: {old_rate:.3f}s -> {self.current_rate:.3f}s"
        )
    
    def get_delay(self) -> float:
        """Get current delay between requests."""
        return self.current_rate
    
    async def wait(self):
        """Async wait with current rate."""
        import asyncio
        await asyncio.sleep(self.current_rate)
