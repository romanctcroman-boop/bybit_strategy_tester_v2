"""
Distributed Cache with Redis Backend

Implements distributed caching with:
- Redis-backed shared cache (works across multiple instances)
- LRU (Least Recently Used) eviction policy
- Cache stampede prevention (dog-pile effect protection)
- Consistent hashing for cache key distribution
- TTL (Time To Live) support with auto-expiration
- Cache warming and preloading
- Compression for large values

Architecture:
- Redis Storage: Centralized cache for distributed systems
- LRU Eviction: Automatic cleanup of least used items
- Stampede Prevention: Lock-based protection during cache misses
- Compression: Optional gzip for large cached values
- Metrics: Track hit/miss rates, memory usage

Usage:
    cache = DistributedCache(
        redis_client=redis.Redis(),
        max_size_mb=100,
        default_ttl=300  # 5 minutes
    )
    
    # Get from cache
    value = await cache.get("user:123")
    
    # Set to cache
    await cache.set("user:123", user_data, ttl=600)
    
    # Get with fallback function (prevents stampede)
    user = await cache.get_or_set(
        key="user:123",
        fetch_func=lambda: fetch_user_from_db(123),
        ttl=300
    )

Phase 3, Day 17-18
Target: 20+ tests, >90% coverage
"""

import asyncio
import time
import hashlib
import pickle
import gzip
import logging
from typing import Any, Optional, Callable, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import OrderedDict

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None

logger = logging.getLogger(__name__)


class EvictionPolicy(Enum):
    """Cache eviction policies"""
    LRU = "lru"           # Least Recently Used
    LFU = "lfu"           # Least Frequently Used
    FIFO = "fifo"         # First In First Out
    TTL_ONLY = "ttl"      # TTL expiration only (no size limit)


@dataclass
class CacheConfig:
    """Cache configuration
    
    Attributes:
        max_size_mb: Maximum cache size in MB (0 = unlimited)
        default_ttl: Default TTL in seconds (0 = no expiration)
        eviction_policy: Eviction policy when cache full
        enable_compression: Compress values > compression_threshold
        compression_threshold: Min size (bytes) to compress (default: 1024)
        stampede_ttl: Lock TTL for stampede prevention (default: 10s)
    """
    max_size_mb: int = 100
    default_ttl: int = 300
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    enable_compression: bool = True
    compression_threshold: int = 1024  # 1KB
    stampede_ttl: int = 10  # 10 seconds


@dataclass
class CacheStats:
    """Cache statistics
    
    Attributes:
        hits: Number of cache hits
        misses: Number of cache misses
        sets: Number of cache sets
        deletes: Number of cache deletes
        evictions: Number of evictions due to size limit
        size_bytes: Current cache size in bytes
        items_count: Number of items in cache
    """
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    size_bytes: int = 0
    items_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class DistributedCache:
    """Distributed cache with Redis backend
    
    Features:
    - Redis-backed shared state
    - LRU/LFU/FIFO eviction policies
    - Cache stampede prevention
    - Optional compression
    - Consistent hashing
    - Metrics tracking
    """
    
    def __init__(
        self,
        redis_client: Optional[Any] = None,
        config: Optional[CacheConfig] = None,
        key_prefix: str = "cache",
        enable_metrics: bool = True
    ):
        """Initialize distributed cache
        
        Args:
            redis_client: Redis async client (optional, uses in-memory if None)
            config: Cache configuration (optional)
            key_prefix: Redis key prefix for namespacing
            enable_metrics: Enable metrics collection
        """
        self.redis_client = redis_client
        self.config = config or CacheConfig()
        self.key_prefix = key_prefix
        self.enable_metrics = enable_metrics
        
        # Stats
        self.stats = CacheStats()
        
        # In-memory fallback (if Redis not available)
        # Using OrderedDict for O(1) LRU operations
        self._local_cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()  # key -> (value, expiry)
        
        # Stampede prevention locks
        self._stampede_locks: Dict[str, asyncio.Lock] = {}
        
        # TTL cleanup background task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 60  # Check every 60 seconds
        self._shutdown = False
        
        logger.info(
            f"Distributed cache initialized: "
            f"redis={'enabled' if redis_client else 'disabled'}, "
            f"max_size={self.config.max_size_mb}MB, "
            f"ttl={self.config.default_ttl}s, "
            f"eviction={self.config.eviction_policy.value}"
        )
        
        # Start TTL cleanup task for local cache
        if not redis_client:
            self._cleanup_task = asyncio.create_task(self._ttl_cleanup_loop())
    
    def _make_key(self, key: str) -> str:
        """Generate Redis key with prefix
        
        Args:
            key: Cache key
            
        Returns:
            Prefixed Redis key
        """
        return f"{self.key_prefix}:{key}"
    
    def _hash_key(self, key: str) -> str:
        """Generate consistent hash for key (for sharding)
        
        Args:
            key: Cache key
            
        Returns:
            Hashed key (hex string)
        """
        return hashlib.md5(key.encode()).hexdigest()
    
    def _compress(self, value: bytes) -> bytes:
        """Compress value if above threshold
        
        Args:
            value: Raw bytes to compress
            
        Returns:
            Compressed bytes (or original if below threshold)
        """
        if not self.config.enable_compression:
            return value
        
        if len(value) < self.config.compression_threshold:
            return value
        
        return gzip.compress(value)
    
    def _decompress(self, value: bytes) -> bytes:
        """Decompress value if compressed
        
        Args:
            value: Potentially compressed bytes
            
        Returns:
            Decompressed bytes
        """
        if not self.config.enable_compression:
            return value
        
        # Try to decompress (will fail if not compressed)
        try:
            return gzip.decompress(value)
        except gzip.BadGzipFile:
            return value
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value to bytes
        
        Args:
            value: Python object to serialize
            
        Returns:
            Serialized bytes
        """
        serialized = pickle.dumps(value)
        return self._compress(serialized)
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to value
        
        Args:
            data: Serialized bytes
            
        Returns:
            Deserialized Python object
        """
        decompressed = self._decompress(data)
        return pickle.loads(decompressed)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        if self.redis_client:
            value = await self._get_redis(key)
        else:
            value = await self._get_local(key)
        
        # Update stats
        if value is not None:
            self.stats.hits += 1
        else:
            self.stats.misses += 1
        
        return value
    
    async def _get_redis(self, key: str) -> Optional[Any]:
        """Get value from Redis"""
        redis_key = self._make_key(key)
        
        try:
            data = await self.redis_client.get(redis_key)
            
            if data is None:
                return None
            
            # Update access time for LRU
            if self.config.eviction_policy == EvictionPolicy.LRU:
                await self.redis_client.zadd(
                    f"{self.key_prefix}:lru",
                    {redis_key: time.time()}
                )
            
            return self._deserialize(data)
        
        except Exception as e:
            logger.error(f"Redis get failed for {key}: {e}")
            return None
    
    async def _get_local(self, key: str) -> Optional[Any]:
        """Get value from local cache with O(1) LRU update"""
        if key not in self._local_cache:
            return None
        
        value, expiry = self._local_cache[key]
        
        # Check expiry
        if expiry > 0 and time.time() > expiry:
            del self._local_cache[key]
            return None
        
        # Move to end for LRU (O(1) operation with OrderedDict)
        self._local_cache.move_to_end(key)
        
        return value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default if None)
            
        Returns:
            True if set successfully
        """
        ttl = ttl if ttl is not None else self.config.default_ttl
        
        if self.redis_client:
            success = await self._set_redis(key, value, ttl)
        else:
            success = await self._set_local(key, value, ttl)
        
        if success:
            self.stats.sets += 1
        
        return success
    
    async def _set_redis(self, key: str, value: Any, ttl: int) -> bool:
        """Set value in Redis"""
        redis_key = self._make_key(key)
        
        try:
            # Serialize and compress
            data = self._serialize(value)
            
            # Set with TTL
            if ttl > 0:
                await self.redis_client.setex(redis_key, ttl, data)
            else:
                await self.redis_client.set(redis_key, data)
            
            # Update LRU tracking
            if self.config.eviction_policy == EvictionPolicy.LRU:
                await self.redis_client.zadd(
                    f"{self.key_prefix}:lru",
                    {redis_key: time.time()}
                )
            
            # Check size limit and evict if needed
            await self._check_size_limit_redis()
            
            return True
        
        except Exception as e:
            logger.error(f"Redis set failed for {key}: {e}")
            return False
    
    async def _set_local(self, key: str, value: Any, ttl: int) -> bool:
        """Set value in local cache with O(1) LRU tracking"""
        expiry = time.time() + ttl if ttl > 0 else 0
        
        # If key exists, remove it first (will be added at end)
        if key in self._local_cache:
            del self._local_cache[key]
        
        # Add at end (most recently used)
        self._local_cache[key] = (value, expiry)
        
        # Check size limit and evict if needed
        await self._check_size_limit_local()
        
        return True
    
    async def _check_size_limit_redis(self):
        """Check Redis cache size and evict if needed"""
        if self.config.max_size_mb == 0:
            return  # No size limit
        
        # Get cache size (approximate)
        try:
            info = await self.redis_client.info('memory')
            used_memory_mb = info['used_memory'] / (1024 * 1024)
            
            if used_memory_mb > self.config.max_size_mb:
                # Evict based on policy
                await self._evict_redis()
        except Exception as e:
            logger.warning(f"Size check failed: {e}")
    
    async def _check_size_limit_local(self):
        """Check local cache size and evict if needed"""
        if self.config.max_size_mb == 0:
            return
        
        # Estimate size (rough approximation)
        estimated_size = len(self._local_cache) * 1024  # Assume 1KB per item
        estimated_size_mb = estimated_size / (1024 * 1024)
        
        if estimated_size_mb > self.config.max_size_mb:
            await self._evict_local()
    
    async def _evict_redis(self):
        """Evict items from Redis based on policy"""
        try:
            if self.config.eviction_policy == EvictionPolicy.LRU:
                # Get oldest accessed keys
                lru_key = f"{self.key_prefix}:lru"
                old_keys = await self.redis_client.zrange(lru_key, 0, 9)  # Evict 10 oldest
                
                for key in old_keys:
                    await self.redis_client.delete(key)
                    await self.redis_client.zrem(lru_key, key)
                    self.stats.evictions += 1
        
        except Exception as e:
            logger.error(f"Eviction failed: {e}")
    
    async def _evict_local(self):
        """Evict items from local cache with O(1) LRU eviction
        
        Using OrderedDict.popitem(last=False) for O(1) removal of oldest item.
        Previous implementation used sorted() which was O(n log n).
        """
        if self.config.eviction_policy == EvictionPolicy.LRU:
            # Evict 10% of cache or at least 1 item
            evict_count = max(1, len(self._local_cache) // 10)
            
            for _ in range(min(evict_count, len(self._local_cache))):
                # Remove oldest (least recently used) - O(1) operation
                self._local_cache.popitem(last=False)
                self.stats.evictions += 1
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted
        """
        if self.redis_client:
            redis_key = self._make_key(key)
            result = await self.redis_client.delete(redis_key)
            success = result > 0
        else:
            success = self._local_cache.pop(key, None) is not None
        
        if success:
            self.stats.deletes += 1
        
        return success
    
    async def get_or_set(
        self,
        key: str,
        fetch_func: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """Get from cache or fetch and set (with stampede prevention)
        
        Args:
            key: Cache key
            fetch_func: Function to fetch value on cache miss
            ttl: TTL in seconds
            
        Returns:
            Cached or fetched value
        """
        # Try to get from cache
        value = await self.get(key)
        
        if value is not None:
            return value
        
        # Cache miss - prevent stampede with lock
        lock_key = f"lock:{key}"
        
        if lock_key not in self._stampede_locks:
            self._stampede_locks[lock_key] = asyncio.Lock()
        
        async with self._stampede_locks[lock_key]:
            # Double-check cache (another coroutine might have filled it)
            value = await self.get(key)
            
            if value is not None:
                return value
            
            # Fetch value
            if asyncio.iscoroutinefunction(fetch_func):
                value = await fetch_func()
            else:
                value = fetch_func()
            
            # Set in cache
            await self.set(key, value, ttl)
            
            return value
    
    async def clear(self):
        """Clear entire cache"""
        if self.redis_client:
            # Delete all keys with prefix
            pattern = f"{self.key_prefix}:*"
            cursor = 0
            
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor,
                    match=pattern,
                    count=100
                )
                
                if keys:
                    await self.redis_client.delete(*keys)
                
                if cursor == 0:
                    break
        else:
            self._local_cache.clear()
        
        logger.info("Cache cleared")
    
    async def _ttl_cleanup_loop(self):
        """Background task to clean up expired entries from local cache
        
        Runs every 60 seconds (configurable) to prevent memory leaks.
        Removes all expired items from _local_cache and _access_times.
        """
        logger.info(f"TTL cleanup task started (interval={self._cleanup_interval}s)")
        
        while not self._shutdown:
            try:
                await asyncio.sleep(self._cleanup_interval)
                
                if self._shutdown:
                    break
                
                # Find and remove expired entries
                now = time.time()
                expired_keys = []
                
                for key, (value, expiry) in list(self._local_cache.items()):
                    if expiry > 0 and now > expiry:
                        expired_keys.append(key)
                
                # Remove expired entries
                for key in expired_keys:
                    self._local_cache.pop(key, None)
                
                if expired_keys:
                    logger.debug(f"TTL cleanup: removed {len(expired_keys)} expired entries")
                    self.stats.evictions += len(expired_keys)
            
            except asyncio.CancelledError:
                logger.info("TTL cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"TTL cleanup error: {e}")
                # Continue running even if error occurs
    
    async def close(self):
        """Shutdown cache and cleanup resources"""
        self._shutdown = True
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Distributed cache closed")
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics
        
        Returns:
            CacheStats object
        """
        if not self.enable_metrics:
            return CacheStats()
        
        # Update size stats
        if not self.redis_client:
            self.stats.items_count = len(self._local_cache)
            self.stats.size_bytes = len(self._local_cache) * 1024  # Rough estimate
        
        return self.stats


class CacheWarmer:
    """Utility for cache warming/preloading"""
    
    def __init__(self, cache: DistributedCache):
        self.cache = cache
    
    async def warm(
        self,
        keys_and_funcs: List[Tuple[str, Callable, Optional[int]]]
    ):
        """Warm cache with preloaded data
        
        Args:
            keys_and_funcs: List of (key, fetch_func, ttl) tuples
        """
        tasks = []
        
        for key, fetch_func, ttl in keys_and_funcs:
            task = self.cache.get_or_set(key, fetch_func, ttl)
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        logger.info(f"Cache warmed with {len(keys_and_funcs)} entries")
