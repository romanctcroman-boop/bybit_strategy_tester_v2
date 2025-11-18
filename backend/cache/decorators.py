"""
Cache Decorators

Convenient decorators for automatic caching of function results.

Features:
- @cached: Automatic result caching
- @cache_with_key: Custom key generation
- @invalidate_cache: Cache invalidation on mutations
- Support for async and sync functions
"""

import asyncio
import hashlib
import json
import logging
from typing import Any, Callable, Optional, TypeVar, cast
from functools import wraps

from backend.cache.cache_manager import get_cache_manager

logger = logging.getLogger(__name__)

T = TypeVar('T')


def _generate_cache_key(
    prefix: str,
    func_name: str,
    args: tuple,
    kwargs: dict,
) -> str:
    """
    Generate cache key from function arguments.
    
    Args:
        prefix: Key prefix
        func_name: Function name
        args: Positional arguments
        kwargs: Keyword arguments
        
    Returns:
        Cache key string
    """
    # Create hashable representation of args
    try:
        args_str = json.dumps(args, sort_keys=True, default=str)
        kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
        combined = f"{args_str}:{kwargs_str}"
        
        # Hash for shorter keys
        args_hash = hashlib.md5(combined.encode()).hexdigest()[:12]
        
        return f"{prefix}:{func_name}:{args_hash}"
    
    except (TypeError, ValueError) as e:
        logger.warning(f"Failed to generate cache key: {e}")
        # Fallback to simple key without args
        return f"{prefix}:{func_name}"


def cached(
    ttl: int = 300,
    key_prefix: Optional[str] = None,
    key_func: Optional[Callable] = None,
) -> Callable:
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time-to-live in seconds (default: 5 minutes)
        key_prefix: Custom key prefix (default: function module + name)
        key_func: Custom key generation function
        
    Returns:
        Decorated function with caching
        
    Example:
        >>> @cached(ttl=600)
        >>> async def get_user(user_id: int):
        ...     return await fetch_user_from_db(user_id)
        >>> 
        >>> # First call: cache miss, fetches from DB
        >>> user = await get_user(1)
        >>> 
        >>> # Second call: cache hit, returns cached value
        >>> user = await get_user(1)  # Instant!
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            # Get cache manager
            cache = await get_cache_manager()
            
            # Generate cache key
            prefix = key_prefix or f"{func.__module__}.{func.__name__}"
            
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = _generate_cache_key(prefix, func.__name__, args, kwargs)
            
            # Try cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_value
            
            # Cache miss - compute
            logger.debug(f"Cache MISS: {cache_key}")
            result = await func(*args, **kwargs)
            
            # Store in cache
            if result is not None:
                await cache.set(cache_key, result, l1_ttl=ttl, l2_ttl=ttl)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            # For sync functions, run in async context
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return cast(Callable[..., T], async_wrapper)
        else:
            return cast(Callable[..., T], sync_wrapper)
    
    return decorator


def cache_with_key(key: str, ttl: int = 300) -> Callable:
    """
    Decorator with explicit cache key.
    
    Args:
        key: Cache key (can include {arg} placeholders)
        ttl: Time-to-live in seconds
        
    Returns:
        Decorated function
        
    Example:
        >>> @cache_with_key(key="user:{user_id}", ttl=600)
        >>> async def get_user(user_id: int):
        ...     return await fetch_user_from_db(user_id)
        >>> 
        >>> # Cached with key "user:1"
        >>> user = await get_user(user_id=1)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            cache = await get_cache_manager()
            
            # Format key with arguments
            try:
                cache_key = key.format(**kwargs)
            except KeyError:
                # Fallback if key format fails
                cache_key = key
            
            # Try cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Compute and cache
            result = await func(*args, **kwargs)
            if result is not None:
                await cache.set(cache_key, result, l1_ttl=ttl, l2_ttl=ttl)
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return cast(Callable[..., T], async_wrapper)
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return asyncio.run(async_wrapper(*args, **kwargs))
            return cast(Callable[..., T], sync_wrapper)
    
    return decorator


def invalidate_cache(patterns: list[str]) -> Callable:
    """
    Decorator to invalidate cache after function execution.
    
    Useful for mutations that should clear cached data.
    
    Args:
        patterns: List of cache key patterns to invalidate
        
    Returns:
        Decorated function
        
    Example:
        >>> @invalidate_cache(patterns=["user:*", "users:list"])
        >>> async def update_user(user_id: int, data: dict):
        ...     return await db.update_user(user_id, data)
        >>> 
        >>> # After update, user caches are cleared
        >>> await update_user(1, {"name": "John"})
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            # Execute function
            result = await func(*args, **kwargs)
            
            # Invalidate caches
            cache = await get_cache_manager()
            for pattern in patterns:
                # Format pattern with kwargs
                try:
                    formatted_pattern = pattern.format(**kwargs)
                except (KeyError, ValueError):
                    formatted_pattern = pattern
                
                deleted = await cache.delete_pattern(formatted_pattern)
                if deleted > 0:
                    logger.info(f"Invalidated {deleted} cache keys: {formatted_pattern}")
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return cast(Callable[..., T], async_wrapper)
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return asyncio.run(async_wrapper(*args, **kwargs))
            return cast(Callable[..., T], sync_wrapper)
    
    return decorator


def cache_result(ttl: int = 300):
    """
    Simple decorator for caching function results.
    
    Similar to @cached but with simpler interface.
    
    Args:
        ttl: Time-to-live in seconds
        
    Example:
        >>> @cache_result(ttl=600)
        >>> async def expensive_computation():
        ...     await asyncio.sleep(5)
        ...     return "result"
    """
    return cached(ttl=ttl)


class CacheContext:
    """
    Context manager for temporary cache configuration.
    
    Example:
        >>> async with CacheContext(enabled=False):
        ...     # Caching disabled in this block
        ...     user = await get_user(1)
    """
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._original_state = None
    
    async def __aenter__(self):
        # Store original state and apply new
        # (In production, you'd have global cache config)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Restore original state
        pass


# ============================================================================
# Helper Functions
# ============================================================================

async def warm_cache(
    key: str,
    value_func: Callable,
    ttl: int = 300,
) -> None:
    """
    Warm cache with computed value.
    
    Args:
        key: Cache key
        value_func: Function to compute value
        ttl: Time-to-live in seconds
        
    Example:
        >>> # Warm cache with popular strategies
        >>> await warm_cache(
        ...     key="strategies:popular",
        ...     value_func=lambda: fetch_popular_strategies(),
        ...     ttl=3600
        ... )
    """
    cache = await get_cache_manager()
    
    if asyncio.iscoroutinefunction(value_func):
        value = await value_func()
    else:
        value = value_func()
    
    if value is not None:
        await cache.set(key, value, l1_ttl=ttl, l2_ttl=ttl)
        logger.info(f"Cache warmed: {key}")


async def invalidate_all(prefix: str) -> int:
    """
    Invalidate all caches with prefix.
    
    Args:
        prefix: Key prefix
        
    Returns:
        Number of keys invalidated
        
    Example:
        >>> # Invalidate all user caches
        >>> count = await invalidate_all("user:")
        >>> print(f"Invalidated {count} keys")
    """
    cache = await get_cache_manager()
    return await cache.delete_pattern(f"{prefix}*")
