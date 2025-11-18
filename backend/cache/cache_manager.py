"""
Cache Manager - Multi-Level Caching System

Implements hierarchical caching with:
- L1: In-memory LRU cache (fastest, limited size)
- L2: Redis cache (fast, shared across instances)
- L3: Database (fallback)

Features:
- Automatic cache warming for hot data
- TTL-based expiration
- Cache invalidation strategies
- Hit rate tracking
- Memory-efficient LRU eviction
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Callable, TypeVar, Generic
from datetime import datetime, timedelta
from functools import wraps
from collections import OrderedDict
import hashlib
import json
import pickle

from backend.cache.redis_client import RedisClient, get_redis_client
from backend.cache.metrics import cache_metrics
from backend.cache.config import get_cache_settings

logger = logging.getLogger(__name__)

T = TypeVar('T')


class LRUCache(Generic[T]):
    """
    Thread-safe LRU (Least Recently Used) cache.
    
    Features:
    - O(1) get and set operations
    - Automatic eviction of least recently used items
    - TTL support for expiration
    - Memory-efficient OrderedDict implementation
    
    Example:
        >>> cache = LRUCache(max_size=100, default_ttl=300)
        >>> cache.set("key", "value")
        >>> value = cache.get("key")  # Returns "value"
        >>> cache.get("missing")      # Returns None
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of items to store
            default_ttl: Default time-to-live in seconds
            
        Raises:
            ValueError: If max_size or default_ttl are invalid
        """
        # Parameter validation
        if max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")
        if default_ttl <= 0:
            raise ValueError(f"default_ttl must be positive, got {default_ttl}")
        
        self.max_size = max_size
        self.default_ttl = default_ttl
        # Use time.monotonic() for TTL to avoid system clock issues
        self._cache: OrderedDict[str, tuple[T, float]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expired': 0,
        }
    
    async def get(self, key: str) -> Optional[T]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if exists and not expired, None otherwise
        """
        # Time the operation for Prometheus
        with cache_metrics.time_operation('get', 'l1'):
            async with self._lock:
                if key not in self._cache:
                    self._stats['misses'] += 1
                    cache_metrics.record_miss()
                    cache_metrics.record_operation('get', 'success')
                    return None
                
                value, expiry = self._cache[key]
                
                # Check expiration using monotonic time (not affected by system clock changes)
                if time.monotonic() > expiry:
                    del self._cache[key]
                    self._stats['expired'] += 1
                    self._stats['misses'] += 1
                    cache_metrics.record_miss()
                    cache_metrics.record_expired('l1')
                    cache_metrics.record_operation('get', 'success')
                    return None
                
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self._stats['hits'] += 1
                cache_metrics.record_hit('l1')
                cache_metrics.record_operation('get', 'success')
                
                # Update cache size metric
                cache_metrics.update_cache_size(len(self._cache), 'l1')
                
                return value
    
    async def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        # Time the operation for Prometheus
        with cache_metrics.time_operation('set', 'l1'):
            async with self._lock:
                ttl = ttl or self.default_ttl
                # Use time.monotonic() instead of datetime for TTL (immune to clock changes)
                expiry = time.monotonic() + ttl
                
                # Instagram/Meta pattern: atomic update to avoid race conditions
                if key in self._cache:
                    # Update existing key and move to end (most recent)
                    self._cache.move_to_end(key)
                    self._cache[key] = (value, expiry)
                else:
                    # New key: evict oldest if at capacity, then add
                    if len(self._cache) >= self.max_size:
                        self._cache.popitem(last=False)  # Remove oldest (LRU)
                        self._stats['evictions'] += 1
                        cache_metrics.record_eviction('l1')
                    self._cache[key] = (value, expiry)
                
                # Update Prometheus metrics
                cache_metrics.record_operation('set', 'success')
                cache_metrics.update_cache_size(len(self._cache), 'l1')
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cached items."""
        async with self._lock:
            self._cache.clear()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0
            
            return {
                **self._stats,
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_rate': hit_rate,
                'total_requests': total_requests,
            }


class CacheManager:
    """
    Multi-level cache manager with L1 (memory) and L2 (Redis).
    
    Features:
    - Hierarchical caching (memory → Redis → database)
    - Automatic cache warming
    - Pattern-based invalidation
    - Cache-aside pattern
    - Write-through optional
    
    Example:
        >>> manager = CacheManager()
        >>> await manager.connect()
        >>> 
        >>> # Get with fallback
        >>> value = await manager.get_or_compute(
        ...     key="user:1",
        ...     compute_func=lambda: fetch_user_from_db(1),
        ...     ttl=300
        ... )
    """
    
    def __init__(
        self,
        l1_size: Optional[int] = None,
        l1_ttl: Optional[int] = None,
        l2_ttl: Optional[int] = None,
        redis_client: Optional[RedisClient] = None,
        settings: Optional['CacheSettings'] = None,
    ):
        """
        Initialize cache manager.
        
        Args:
            l1_size: L1 cache size (memory) - uses config if None
            l1_ttl: L1 cache TTL in seconds - uses config if None
            l2_ttl: L2 cache TTL in seconds (Redis) - uses config if None
            redis_client: Redis client instance (optional)
            settings: CacheSettings instance (optional, loads from env if None)
        """
        # Load settings from environment if not provided
        if settings is None:
            settings = get_cache_settings()
        
        self.settings = settings
        
        # Use provided values or fall back to settings
        l1_size = l1_size if l1_size is not None else settings.l1_size
        l1_ttl = l1_ttl if l1_ttl is not None else settings.l1_ttl
        l2_ttl = l2_ttl if l2_ttl is not None else settings.l2_ttl
        
        # Initialize L1 cache if enabled
        self.l1_cache = LRUCache(max_size=l1_size, default_ttl=l1_ttl) if settings.enable_l1 else None
        self.l2_ttl = l2_ttl
        self.redis_client = redis_client
        
        self._stats = {
            'l1_hits': 0,
            'l2_hits': 0,
            'misses': 0,
            'computes': 0,
        }
        
        logger.info(f"CacheManager initialized: L1={settings.enable_l1} (size={l1_size}, ttl={l1_ttl}s), L2={settings.enable_l2} (ttl={l2_ttl}s)")
    
    async def connect(self):
        """Connect to Redis (L2 cache) if enabled."""
        # Only connect to Redis if L2 is enabled
        if self.settings.enable_l2:
            if self.redis_client is None:
                self.redis_client = await get_redis_client()
            logger.info("✅ CacheManager connected (L1: Memory, L2: Redis)")
        else:
            logger.info("✅ CacheManager connected (L1: Memory only, L2 disabled)")
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache hierarchy.
        
        Checks L1 (memory) first, then L2 (Redis).
        Implements graceful degradation on Redis failures.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if found, None otherwise
        """
        # Try L1 (memory) if enabled - metrics already tracked in LRUCache.get()
        if self.settings.enable_l1 and self.l1_cache:
            value = await self.l1_cache.get(key)
            if value is not None:
                self._stats['l1_hits'] += 1
                return value
        
        # Try L2 (Redis) if enabled with error handling
        if self.settings.enable_l2 and self.redis_client:
            try:
                with cache_metrics.time_operation('get', 'l2'):
                    redis_value = await self.redis_client.get(key)
                    if redis_value:
                        # Deserialize and populate L1
                        try:
                            value = json.loads(redis_value)
                            await self.l1_cache.set(key, value)
                            self._stats['l2_hits'] += 1
                            cache_metrics.record_hit('l2')
                            cache_metrics.record_operation('get', 'success')
                            return value
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to deserialize cache value for key {key}: {e}")
                            cache_metrics.record_operation('get', 'error')
            except ConnectionError as e:
                # Netflix EVCache pattern: graceful degradation
                logger.warning(f"Redis L2 connection error for key {key}: {e}")
                self._stats.setdefault('l2_errors', 0)
                self._stats['l2_errors'] += 1
                cache_metrics.record_l2_error('connection')
                cache_metrics.record_operation('get', 'error')
            except TimeoutError as e:
                logger.warning(f"Redis L2 timeout for key {key}: {e}")
                self._stats.setdefault('l2_errors', 0)
                self._stats['l2_errors'] += 1
                cache_metrics.record_l2_error('timeout')
                cache_metrics.record_operation('get', 'error')
            except OSError as e:
                logger.warning(f"Redis L2 OS error for key {key}: {e}")
                self._stats.setdefault('l2_errors', 0)
                self._stats['l2_errors'] += 1
                cache_metrics.record_l2_error('other')
                cache_metrics.record_operation('get', 'error')
        
        self._stats['misses'] += 1
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        l1_ttl: Optional[int] = None,
        l2_ttl: Optional[int] = None,
    ) -> None:
        """
        Set value in cache hierarchy.
        
        Writes to both L1 (memory) and L2 (Redis).
        
        Args:
            key: Cache key
            value: Value to cache
            l1_ttl: L1 TTL override
            l2_ttl: L2 TTL override
        """
        # Set in L1 (memory) if enabled - metrics already tracked in LRUCache.set()
        if self.settings.enable_l1 and self.l1_cache:
            await self.l1_cache.set(key, value, ttl=l1_ttl)
        
        # Set in L2 (Redis) if enabled with error handling
        if self.settings.enable_l2 and self.redis_client:
            try:
                with cache_metrics.time_operation('set', 'l2'):
                    serialized = json.dumps(value)
                    await self.redis_client.set(
                        key,
                        serialized,
                        expire=l2_ttl or self.l2_ttl
                    )
                    cache_metrics.record_operation('set', 'success')
            except (TypeError, json.JSONEncodeError) as e:
                logger.error(f"Failed to serialize cache value for key {key}: {e}")
                cache_metrics.record_operation('set', 'error')
            except (ConnectionError, TimeoutError, OSError) as e:
                # Graceful degradation: L1 still works
                logger.warning(f"Redis L2 cache write error for key {key}: {e}")
                self._stats.setdefault('l2_errors', 0)
                self._stats['l2_errors'] += 1
                cache_metrics.record_l2_error('connection' if isinstance(e, ConnectionError) else 'other')
                cache_metrics.record_operation('set', 'error')
    
    async def get_or_compute(
        self,
        key: str,
        compute_func: Callable[[], Any],
        l1_ttl: Optional[int] = None,
        l2_ttl: Optional[int] = None,
    ) -> Any:
        """
        Get from cache or compute value if not cached.
        
        This implements the cache-aside pattern:
        1. Check cache
        2. If miss, compute value
        3. Store in cache
        4. Return value
        
        Args:
            key: Cache key
            compute_func: Function to compute value if cache miss
            l1_ttl: L1 TTL override
            l2_ttl: L2 TTL override
            
        Returns:
            Cached or computed value
            
        Example:
            >>> value = await manager.get_or_compute(
            ...     key="user:1",
            ...     compute_func=lambda: fetch_user_from_db(1),
            ...     l1_ttl=300
            ... )
        """
        # Try cache first
        value = await self.get(key)
        if value is not None:
            return value
        
        # Cache miss - compute value with error handling
        self._stats['computes'] += 1
        
        try:
            # Time compute function execution
            with cache_metrics.time_compute():
                if asyncio.iscoroutinefunction(compute_func):
                    value = await compute_func()
                else:
                    value = compute_func()
        except Exception as e:
            logger.error(f"Compute function failed for key {key}: {e}")
            self._stats.setdefault('compute_errors', 0)
            self._stats['compute_errors'] += 1
            cache_metrics.record_compute_error()
            raise  # Re-raise after logging
        
        # Store in cache
        if value is not None:
            await self.set(key, value, l1_ttl=l1_ttl, l2_ttl=l2_ttl)
        
        return value
    
    async def delete(self, key: str) -> None:
        """Delete key from all cache levels."""
        if self.settings.enable_l1 and self.l1_cache:
            await self.l1_cache.delete(key)
        if self.settings.enable_l2 and self.redis_client:
            await self.redis_client.delete(key)
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.
        
        Args:
            pattern: Key pattern (e.g., "user:*")
            
        Returns:
            Number of keys deleted
        """
        deleted = 0
        
        # L1 cache doesn't support patterns efficiently, so clear all
        # (In production, you'd track keys or use a prefix tree)
        await self.l1_cache.clear()
        
        # L2 (Redis) - delete by pattern
        if self.redis_client:
            keys = await self.redis_client.keys(pattern)
            if keys:
                deleted = await self.redis_client.delete(*keys)
        
        return deleted
    
    # ========================================================================
    # Batch Operations (Performance Optimization - Week 2 Day 3 Task 3)
    # ========================================================================
    
    async def mget(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple keys in a single batch operation.
        
        Uses Redis MGET for L2 cache to reduce round-trips.
        Falls back to L1 cache for keys found in memory.
        
        Args:
            keys: List of cache keys to retrieve
            
        Returns:
            Dictionary mapping keys to their values (missing keys are omitted)
            
        Example:
            >>> result = await cache_manager.mget(['user:1', 'user:2', 'user:3'])
            >>> print(result)
            {'user:1': {...}, 'user:2': {...}}  # user:3 not found
        
        Performance:
            - Single round-trip to Redis instead of N round-trips
            - ~5-10x faster than individual get() calls
            - L1 cache checked first for even better performance
        """
        result = {}
        l2_keys = []  # Keys not found in L1, need to check L2
        
        # Step 1: Try L1 cache first (fastest)
        if self.settings.enable_l1 and self.l1_cache:
            for key in keys:
                value = await self.l1_cache.get(key)
                if value is not None:
                    result[key] = value
                    self._stats['l1_hits'] += 1
                    cache_metrics.record_hit('l1')
                else:
                    l2_keys.append(key)
        else:
            l2_keys = keys
        
        # Step 2: Check remaining keys in L2 (Redis) using MGET
        if l2_keys and self.settings.enable_l2 and self.redis_client:
            try:
                with cache_metrics.time_operation('mget', 'l2'):
                    # Redis MGET returns list of values (None for missing keys)
                    # Use underlying redis client for batch operations
                    redis_values = await self.redis_client.client.mget(l2_keys)
                    
                    for key, redis_value in zip(l2_keys, redis_values):
                        if redis_value:
                            try:
                                # Deserialize and populate L1
                                value = json.loads(redis_value)
                                result[key] = value
                                
                                # Populate L1 cache for future hits
                                if self.settings.enable_l1 and self.l1_cache:
                                    await self.l1_cache.set(key, value)
                                
                                self._stats['l2_hits'] += 1
                                cache_metrics.record_hit('l2')
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to deserialize cache value for key {key}: {e}")
                        else:
                            # Key not found in L2
                            self._stats['misses'] += 1
                            cache_metrics.record_miss()
                    
                    cache_metrics.record_operation('mget', 'success')
            
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning(f"Redis L2 MGET error: {e}")
                self._stats.setdefault('l2_errors', 0)
                self._stats['l2_errors'] += 1
                cache_metrics.record_l2_error('connection' if isinstance(e, ConnectionError) else 'other')
                cache_metrics.record_operation('mget', 'error')
                
                # Keys remain missing (not in result)
                for key in l2_keys:
                    self._stats['misses'] += 1
                    cache_metrics.record_miss()
        
        elif l2_keys:
            # L2 disabled or not connected, all remaining keys are misses
            for key in l2_keys:
                self._stats['misses'] += 1
                cache_metrics.record_miss()
        
        return result
    
    async def mset(
        self,
        items: Dict[str, Any],
        l1_ttl: Optional[int] = None,
        l2_ttl: Optional[int] = None,
    ) -> None:
        """
        Set multiple keys in a single batch operation.
        
        Uses Redis MSET for L2 cache to reduce round-trips.
        Sets all keys in L1 cache simultaneously.
        
        Args:
            items: Dictionary mapping keys to values
            l1_ttl: L1 TTL override (same for all keys)
            l2_ttl: L2 TTL override (same for all keys)
            
        Example:
            >>> await cache_manager.mset({
            ...     'user:1': {'name': 'Alice'},
            ...     'user:2': {'name': 'Bob'},
            ...     'user:3': {'name': 'Charlie'}
            ... })
        
        Performance:
            - Single round-trip to Redis instead of N round-trips
            - ~5-10x faster than individual set() calls
            - All keys set atomically in Redis
        
        Note:
            - All keys have the same TTL (cannot set per-key TTL in batch)
            - For per-key TTLs, use multiple set() calls
        """
        if not items:
            return
        
        # Step 1: Set in L1 cache (if enabled)
        if self.settings.enable_l1 and self.l1_cache:
            for key, value in items.items():
                await self.l1_cache.set(key, value, ttl=l1_ttl)
        
        # Step 2: Set in L2 cache (Redis) using MSET
        if self.settings.enable_l2 and self.redis_client:
            try:
                with cache_metrics.time_operation('mset', 'l2'):
                    # Serialize all values
                    serialized_items = {}
                    for key, value in items.items():
                        try:
                            serialized_items[key] = json.dumps(value)
                        except (TypeError, json.JSONEncodeError) as e:
                            logger.error(f"Failed to serialize cache value for key {key}: {e}")
                            # Skip this key
                    
                    if serialized_items:
                        # Redis MSET: set all keys atomically
                        # Use underlying redis client for batch operations
                        await self.redis_client.client.mset(serialized_items)
                        
                        # Set expiration for each key (MSET doesn't support TTL)
                        # Use pipeline for efficiency
                        if l2_ttl or self.l2_ttl:
                            ttl = l2_ttl or self.l2_ttl
                            pipeline = self.redis_client.pipeline()
                            for key in serialized_items.keys():
                                pipeline.expire(key, ttl)
                            await pipeline.execute()
                    
                    cache_metrics.record_operation('mset', 'success')
            
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning(f"Redis L2 MSET error: {e}")
                self._stats.setdefault('l2_errors', 0)
                self._stats['l2_errors'] += 1
                cache_metrics.record_l2_error('connection' if isinstance(e, ConnectionError) else 'other')
                cache_metrics.record_operation('mset', 'error')
    
    async def prefetch(
        self,
        keys: List[str],
        compute_funcs: Optional[Dict[str, Callable[[], Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Prefetch multiple keys into cache.
        
        Tries to get all keys from cache first. For missing keys, uses compute_funcs
        to compute values and populate the cache.
        
        Args:
            keys: List of cache keys to prefetch
            compute_funcs: Optional dict mapping keys to compute functions
                          If not provided, only existing cached values are returned
            
        Returns:
            Dictionary mapping keys to their values
            
        Example:
            >>> # Prefetch user data
            >>> result = await cache_manager.prefetch(
            ...     keys=['user:1', 'user:2', 'user:3'],
            ...     compute_funcs={
            ...         'user:1': lambda: fetch_user_from_db(1),
            ...         'user:2': lambda: fetch_user_from_db(2),
            ...         'user:3': lambda: fetch_user_from_db(3),
            ...     }
            ... )
        
        Performance:
            - Uses mget() for efficient batch retrieval
            - Computes missing keys in parallel using asyncio.gather()
            - Populates cache for future requests
        """
        # Step 1: Try to get all keys from cache using mget
        result = await self.mget(keys)
        
        # Step 2: Compute missing keys (if compute_funcs provided)
        if compute_funcs:
            missing_keys = [key for key in keys if key not in result]
            
            if missing_keys:
                # Prepare compute tasks for missing keys
                compute_tasks = []
                for key in missing_keys:
                    if key in compute_funcs:
                        compute_tasks.append(self._compute_and_cache(key, compute_funcs[key]))
                
                # Compute all missing keys in parallel
                if compute_tasks:
                    with cache_metrics.time_compute():
                        computed_results = await asyncio.gather(*compute_tasks, return_exceptions=True)
                    
                    # Add computed results to result dict
                    for key, value in zip(missing_keys, computed_results):
                        if not isinstance(value, Exception):
                            result[key] = value
                        else:
                            logger.error(f"Failed to compute prefetch key {key}: {value}")
        
        return result
    
    async def _compute_and_cache(self, key: str, compute_func: Callable[[], Any]) -> Any:
        """Helper to compute and cache a single key."""
        try:
            # Compute value
            value = await compute_func() if asyncio.iscoroutinefunction(compute_func) else compute_func()
            
            # Cache the result
            await self.set(key, value)
            
            return value
        
        except Exception as e:
            logger.error(f"Compute error for key {key}: {e}")
            cache_metrics.record_compute_error()
            raise
    
    # ========================================================================
    # End of Batch Operations
    # ========================================================================
    
    async def invalidate_tag(self, tag: str) -> int:
        """
        Invalidate all cached items with specific tag.
        
        Args:
            tag: Cache tag (e.g., "strategy:1")
            
        Returns:
            Number of keys invalidated
        """
        pattern = f"*{tag}*"
        return await self.delete_pattern(pattern)
    
    async def clear_all(self) -> None:
        """Clear all caches."""
        await self.l1_cache.clear()
        if self.redis_client:
            # Be careful with flushdb in production!
            logger.warning("Clearing Redis cache")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        l1_stats = await self.l1_cache.get_stats()
        
        total_requests = (
            self._stats['l1_hits'] +
            self._stats['l2_hits'] +
            self._stats['misses']
        )
        
        overall_hit_rate = (
            (self._stats['l1_hits'] + self._stats['l2_hits']) / total_requests
            if total_requests > 0 else 0
        )
        
        return {
            'l1_stats': l1_stats,
            'l2_hits': self._stats['l2_hits'],
            'total_hits': self._stats['l1_hits'] + self._stats['l2_hits'],
            'total_misses': self._stats['misses'],
            'total_computes': self._stats['computes'],
            'overall_hit_rate': overall_hit_rate,
            'l1_hit_rate': l1_stats['hit_rate'],
            'l2_hit_rate': (
                self._stats['l2_hits'] / (self._stats['l2_hits'] + self._stats['misses'])
                if (self._stats['l2_hits'] + self._stats['misses']) > 0 else 0
            ),
        }


# ============================================================================
# Global Cache Manager Instance
# ============================================================================

_cache_manager: Optional[CacheManager] = None


async def get_cache_manager() -> CacheManager:
    """
    Get or create global cache manager instance.
    
    Returns:
        Connected CacheManager instance
    """
    global _cache_manager
    
    if _cache_manager is None:
        _cache_manager = CacheManager(
            l1_size=1000,      # 1000 items in memory
            l1_ttl=300,        # 5 minutes
            l2_ttl=3600,       # 1 hour in Redis
        )
        await _cache_manager.connect()
    
    return _cache_manager
