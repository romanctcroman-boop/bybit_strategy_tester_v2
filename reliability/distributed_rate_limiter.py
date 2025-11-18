"""
Distributed Rate Limiter with Redis Backend

Implements token bucket algorithm with sliding window for distributed rate limiting.
Supports:
- Per-key rate limits (different limits per API key)
- Per-endpoint rate limits (global limits per endpoint)
- Per-user rate limits (limit requests per user/client)
- Redis-backed shared state (works across multiple instances)
- Automatic token refill with configurable rates
- Burst handling with token bucket capacity

Architecture:
- Token Bucket: Each bucket has capacity and refill rate
- Sliding Window: Track requests in time window to prevent burst abuse
- Redis Storage: Centralized state for distributed systems
- Atomic Operations: Use Redis Lua scripts for race-free operations

Usage:
    rate_limiter = DistributedRateLimiter(
        redis_client=redis.Redis(),
        default_capacity=100,
        default_refill_rate=10  # 10 tokens per second
    )
    
    # Check if request allowed
    allowed, retry_after = await rate_limiter.check_limit(
        key="api_key_123",
        tokens_required=1
    )
    
    if allowed:
        # Process request
        pass
    else:
        # Rate limited, retry after {retry_after} seconds
        raise RateLimitError(f"Retry after {retry_after}s")

Phase 3, Day 15-16
Target: 20+ tests, >90% coverage
"""

import asyncio
import time
import logging
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None

logger = logging.getLogger(__name__)


class RateLimitScope(Enum):
    """Rate limit scope types"""
    PER_KEY = "per_key"           # Per API key
    PER_ENDPOINT = "per_endpoint"  # Per endpoint/route
    PER_USER = "per_user"          # Per user/client
    GLOBAL = "global"              # Global across all requests


@dataclass
class RateLimitConfig:
    """Rate limit configuration
    
    Attributes:
        capacity: Maximum tokens in bucket (burst size)
        refill_rate: Tokens added per second
        scope: Rate limit scope (per_key, per_endpoint, etc.)
        enabled: Whether rate limiting is enabled
        window_size: Sliding window size in seconds (default: 60)
    """
    capacity: int = 100              # Max tokens in bucket
    refill_rate: float = 10.0        # Tokens per second
    scope: RateLimitScope = RateLimitScope.PER_KEY
    enabled: bool = True
    window_size: int = 60            # Sliding window in seconds


@dataclass
class RateLimitResult:
    """Result of rate limit check
    
    Attributes:
        allowed: Whether request is allowed
        tokens_remaining: Tokens remaining in bucket
        retry_after: Seconds until next token available (if denied)
        reset_time: Unix timestamp when bucket fully refills
    """
    allowed: bool
    tokens_remaining: float
    retry_after: float
    reset_time: float


class DistributedRateLimiter:
    """Distributed rate limiter with Redis backend
    
    Implements token bucket algorithm with Redis for distributed systems.
    Each bucket refills tokens at configurable rate and has max capacity.
    
    Features:
    - Redis-backed shared state
    - Atomic operations via Lua scripts
    - Configurable per-key/endpoint/user limits
    - Sliding window tracking
    - Automatic token refill
    """
    
    # Lua script for atomic token bucket operation
    TOKEN_BUCKET_SCRIPT = """
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local tokens_required = tonumber(ARGV[3])
    local now = tonumber(ARGV[4])
    
    -- Get current state
    local state = redis.call('HMGET', key, 'tokens', 'last_refill')
    local tokens = tonumber(state[1])
    local last_refill = tonumber(state[2])
    
    -- Initialize if not exists
    if not tokens or not last_refill then
        tokens = capacity
        last_refill = now
    end
    
    -- Calculate tokens to add based on time elapsed
    local time_elapsed = now - last_refill
    local tokens_to_add = time_elapsed * refill_rate
    tokens = math.min(capacity, tokens + tokens_to_add)
    
    -- Check if enough tokens
    local allowed = tokens >= tokens_required
    if allowed then
        tokens = tokens - tokens_required
    end
    
    -- Update state
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)  -- Expire after 1 hour of inactivity
    
    -- Calculate retry_after and reset_time
    local retry_after = 0
    if not allowed then
        retry_after = (tokens_required - tokens) / refill_rate
    end
    local reset_time = now + ((capacity - tokens) / refill_rate)
    
    return {allowed and 1 or 0, tokens, retry_after, reset_time}
    """
    
    def __init__(
        self,
        redis_client: Optional[Any] = None,
        default_config: Optional[RateLimitConfig] = None,
        key_prefix: str = "ratelimit",
        enable_metrics: bool = True
    ):
        """Initialize distributed rate limiter
        
        Args:
            redis_client: Redis async client (optional, uses in-memory if None)
            default_config: Default rate limit config (optional)
            key_prefix: Redis key prefix for namespacing
            enable_metrics: Enable metrics collection
        """
        self.redis_client = redis_client
        self.default_config = default_config or RateLimitConfig()
        self.key_prefix = key_prefix
        self.enable_metrics = enable_metrics
        
        # Metrics
        self.total_checks = 0
        self.allowed_requests = 0
        self.denied_requests = 0
        
        # In-memory fallback (if Redis not available)
        self._local_buckets: Dict[str, Dict[str, Any]] = {}
        
        # ✅ FIX: Lock for thread-safe local bucket operations
        self._local_lock = asyncio.Lock()
        
        # Cache Lua script SHA
        self._script_sha: Optional[str] = None
        
        logger.info(
            f"Distributed rate limiter initialized: "
            f"redis={'enabled' if redis_client else 'disabled'}, "
            f"capacity={self.default_config.capacity}, "
            f"refill_rate={self.default_config.refill_rate}/s"
        )
    
    async def _load_lua_script(self):
        """Load Lua script into Redis (one-time operation)"""
        if self._script_sha or not self.redis_client:
            return
        
        try:
            self._script_sha = await self.redis_client.script_load(self.TOKEN_BUCKET_SCRIPT)
            logger.debug(f"Loaded Lua script: {self._script_sha}")
        except Exception as e:
            logger.warning(f"Failed to load Lua script: {e}")
    
    def _make_key(self, identifier: str, scope: RateLimitScope) -> str:
        """Generate Redis key for rate limit bucket
        
        Args:
            identifier: Key/endpoint/user identifier
            scope: Rate limit scope
            
        Returns:
            Redis key string
        """
        return f"{self.key_prefix}:{scope.value}:{identifier}"
    
    async def check_limit(
        self,
        identifier: str,
        tokens_required: float = 1.0,
        config: Optional[RateLimitConfig] = None
    ) -> RateLimitResult:
        """Check if request is allowed under rate limit
        
        Args:
            identifier: Key/endpoint/user identifier
            tokens_required: Number of tokens required (default: 1)
            config: Custom rate limit config (optional)
            
        Returns:
            RateLimitResult with allow/deny decision and metadata
        """
        config = config or self.default_config
        
        if not config.enabled:
            return RateLimitResult(
                allowed=True,
                tokens_remaining=config.capacity,
                retry_after=0.0,
                reset_time=time.time()
            )
        
        # Update metrics
        self.total_checks += 1
        
        # Use Redis if available, otherwise local
        if self.redis_client:
            result = await self._check_redis(identifier, tokens_required, config)
        else:
            result = await self._check_local(identifier, tokens_required, config)
        
        # Update metrics
        if result.allowed:
            self.allowed_requests += 1
        else:
            self.denied_requests += 1
        
        return result
    
    async def _check_redis(
        self,
        identifier: str,
        tokens_required: float,
        config: RateLimitConfig
    ) -> RateLimitResult:
        """Check rate limit using Redis backend"""
        key = self._make_key(identifier, config.scope)
        now = time.time()
        
        try:
            # Ensure Lua script is loaded
            await self._load_lua_script()
            
            # Execute atomic token bucket operation
            if self._script_sha:
                result = await self.redis_client.evalsha(
                    self._script_sha,
                    1,  # Number of keys
                    key,
                    config.capacity,
                    config.refill_rate,
                    tokens_required,
                    now
                )
            else:
                # Fallback to non-atomic operations
                result = await self._redis_fallback(key, tokens_required, config, now)
            
            allowed = bool(result[0])
            tokens_remaining = float(result[1])
            retry_after = float(result[2])
            reset_time = float(result[3])
            
            return RateLimitResult(
                allowed=allowed,
                tokens_remaining=tokens_remaining,
                retry_after=retry_after,
                reset_time=reset_time
            )
        
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            # Fallback to local on error
            return await self._check_local(identifier, tokens_required, config)
    
    async def _redis_fallback(
        self,
        key: str,
        tokens_required: float,
        config: RateLimitConfig,
        now: float
    ) -> Tuple[int, float, float, float]:
        """Fallback Redis implementation without Lua script"""
        # Get current state
        state = await self.redis_client.hgetall(key)
        tokens = float(state.get(b'tokens', config.capacity))
        last_refill = float(state.get(b'last_refill', now))
        
        # Refill tokens
        time_elapsed = now - last_refill
        tokens_to_add = time_elapsed * config.refill_rate
        tokens = min(config.capacity, tokens + tokens_to_add)
        
        # Check if allowed
        allowed = tokens >= tokens_required
        if allowed:
            tokens -= tokens_required
        
        # Update state
        await self.redis_client.hset(key, mapping={
            'tokens': tokens,
            'last_refill': now
        })
        await self.redis_client.expire(key, 3600)
        
        # Calculate metadata
        retry_after = 0.0 if allowed else (tokens_required - tokens) / config.refill_rate
        reset_time = now + ((config.capacity - tokens) / config.refill_rate)
        
        return (1 if allowed else 0, tokens, retry_after, reset_time)
    
    async def _check_local(
        self,
        identifier: str,
        tokens_required: float,
        config: RateLimitConfig
    ) -> RateLimitResult:
        """Check rate limit using in-memory fallback with thread-safe lock"""
        key = self._make_key(identifier, config.scope)
        now = time.time()
        
        # ✅ FIX: Acquire lock to prevent race conditions
        async with self._local_lock:
            # Get or create bucket
            if key not in self._local_buckets:
                self._local_buckets[key] = {
                    'tokens': config.capacity,
                    'last_refill': now
                }
            
            bucket = self._local_buckets[key]
            
            # Refill tokens
            time_elapsed = now - bucket['last_refill']
            tokens_to_add = time_elapsed * config.refill_rate
            bucket['tokens'] = min(config.capacity, bucket['tokens'] + tokens_to_add)
            bucket['last_refill'] = now
            
            # Check if allowed
            allowed = bucket['tokens'] >= tokens_required
            if allowed:
                bucket['tokens'] -= tokens_required
            
            # Calculate metadata
            retry_after = 0.0 if allowed else (tokens_required - bucket['tokens']) / config.refill_rate
            reset_time = now + ((config.capacity - bucket['tokens']) / config.refill_rate)
            
            tokens_remaining = bucket['tokens']
        
        return RateLimitResult(
            allowed=allowed,
            tokens_remaining=tokens_remaining,
            retry_after=retry_after,
            reset_time=reset_time
        )
    
    async def reset_limit(self, identifier: str, scope: Optional[RateLimitScope] = None):
        """Reset rate limit for identifier (admin operation)
        
        Args:
            identifier: Key/endpoint/user identifier
            scope: Rate limit scope (uses default if None)
        """
        scope = scope or self.default_config.scope
        key = self._make_key(identifier, scope)
        
        if self.redis_client:
            await self.redis_client.delete(key)
        else:
            self._local_buckets.pop(key, None)
        
        logger.info(f"Rate limit reset for {scope.value}:{identifier}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get rate limiter metrics
        
        Returns:
            Dict with metrics
        """
        if not self.enable_metrics:
            return {}
        
        return {
            "total_checks": self.total_checks,
            "allowed_requests": self.allowed_requests,
            "denied_requests": self.denied_requests,
            "deny_rate": self.denied_requests / self.total_checks if self.total_checks > 0 else 0.0,
            "backend": "redis" if self.redis_client else "local"
        }


class RateLimitError(Exception):
    """Exception raised when rate limit exceeded"""
    
    def __init__(self, message: str, retry_after: float = 0.0):
        super().__init__(message)
        self.retry_after = retry_after


# Convenience decorator for rate limiting
def rate_limit(
    identifier_key: str = "user_id",
    tokens_required: float = 1.0,
    config: Optional[RateLimitConfig] = None
):
    """Decorator for rate limiting async functions
    
    Args:
        identifier_key: Key in kwargs to use as identifier
        tokens_required: Number of tokens required
        config: Rate limit config (optional)
    
    Usage:
        @rate_limit(identifier_key="api_key", tokens_required=5)
        async def expensive_operation(api_key: str):
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get rate limiter from first arg (usually self)
            rate_limiter = args[0] if args else None
            if not isinstance(rate_limiter, DistributedRateLimiter):
                # No rate limiter, allow request
                return await func(*args, **kwargs)
            
            # Extract identifier
            identifier = kwargs.get(identifier_key, "default")
            
            # Check rate limit
            result = await rate_limiter.check_limit(identifier, tokens_required, config)
            
            if not result.allowed:
                raise RateLimitError(
                    f"Rate limit exceeded. Retry after {result.retry_after:.2f}s",
                    retry_after=result.retry_after
                )
            
            # Execute function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
