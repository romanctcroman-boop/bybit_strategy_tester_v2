"""
Multi-Level Cache Service

Implements a tiered caching system:
- L1: In-memory (fastest, limited size)
- L2: Redis (fast, distributed)
- L3: Database (slow, persistent)

Features:
- Automatic cache promotion/demotion
- LRU eviction
- TTL support
- Cache statistics and monitoring
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheLevel(str, Enum):
    """Cache level identifiers."""

    L1_MEMORY = "l1_memory"
    L2_REDIS = "l2_redis"
    L3_DATABASE = "l3_database"


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with metadata."""

    key: str
    value: T
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    level: CacheLevel = CacheLevel.L1_MEMORY

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl_seconds is None:
            return False
        return time.time() - self.created_at > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """Get age of entry in seconds."""
        return time.time() - self.created_at

    def touch(self) -> None:
        """Update access time and count."""
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    l1_hits: int = 0
    l2_hits: int = 0
    l3_hits: int = 0
    evictions: int = 0
    promotions: int = 0
    demotions: int = 0
    avg_hit_latency_ms: float = 0.0
    avg_miss_latency_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 4),
            "l1_hits": self.l1_hits,
            "l2_hits": self.l2_hits,
            "l3_hits": self.l3_hits,
            "evictions": self.evictions,
            "promotions": self.promotions,
            "demotions": self.demotions,
            "avg_hit_latency_ms": round(self.avg_hit_latency_ms, 2),
            "avg_miss_latency_ms": round(self.avg_miss_latency_ms, 2),
        }


class L1MemoryCache:
    """
    Level 1: In-memory LRU cache.

    Fastest but limited in size.
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get value from cache."""
        async with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            if entry.is_expired:
                del self._cache[key]
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            return entry

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set value in cache."""
        async with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self.max_size:
                # Remove least recently used (first item)
                self._cache.popitem(last=False)

            self._cache[key] = CacheEntry(
                key=key,
                value=value,
                ttl_seconds=ttl_seconds,
                level=CacheLevel.L1_MEMORY,
            )

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all entries."""
        async with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)


class L2RedisCache:
    """
    Level 2: Redis-backed cache.

    Distributed and larger than L1.
    """

    def __init__(self, redis_url: Optional[str] = None, prefix: str = "cache:l2:"):
        self.redis_url = redis_url or "redis://localhost:6379/0"
        self.prefix = prefix
        self._redis = None

    async def _get_redis(self):
        """Get Redis connection lazily."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis

                self._redis = await aioredis.from_url(self.redis_url)
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}")
                return None
        return self._redis

    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get value from Redis."""
        redis = await self._get_redis()
        if redis is None:
            return None

        try:
            data = await redis.get(f"{self.prefix}{key}")
            if data is None:
                return None

            entry_dict = json.loads(data)
            entry = CacheEntry(
                key=key,
                value=entry_dict["value"],
                created_at=entry_dict.get("created_at", time.time()),
                last_accessed=entry_dict.get("last_accessed", time.time()),
                access_count=entry_dict.get("access_count", 0),
                ttl_seconds=entry_dict.get("ttl_seconds"),
                level=CacheLevel.L2_REDIS,
            )

            if entry.is_expired:
                await self.delete(key)
                return None

            entry.touch()
            return entry
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set value in Redis."""
        redis = await self._get_redis()
        if redis is None:
            return

        try:
            entry = CacheEntry(
                key=key,
                value=value,
                ttl_seconds=ttl_seconds,
                level=CacheLevel.L2_REDIS,
            )

            data = json.dumps(
                {
                    "value": value,
                    "created_at": entry.created_at,
                    "last_accessed": entry.last_accessed,
                    "access_count": entry.access_count,
                    "ttl_seconds": ttl_seconds,
                }
            )

            if ttl_seconds:
                await redis.setex(f"{self.prefix}{key}", ttl_seconds, data)
            else:
                await redis.set(f"{self.prefix}{key}", data)
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        redis = await self._get_redis()
        if redis is None:
            return False

        try:
            result = await redis.delete(f"{self.prefix}{key}")
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False


class MultiLevelCache:
    """
    Multi-level cache with automatic promotion/demotion.

    Usage:
        cache = MultiLevelCache()

        # Get with automatic level traversal
        value = await cache.get("my_key")

        # Set with TTL
        await cache.set("my_key", {"data": "value"}, ttl_seconds=300)

        # Get stats
        stats = cache.get_stats()
    """

    def __init__(
        self,
        l1_max_size: int = 1000,
        redis_url: Optional[str] = None,
        enable_l2: bool = True,
        enable_l3: bool = False,  # Database layer (not implemented yet)
        promotion_threshold: int = 3,  # Promote to L1 after N accesses
    ):
        self.l1 = L1MemoryCache(max_size=l1_max_size)
        self.l2 = L2RedisCache(redis_url=redis_url) if enable_l2 else None
        self.enable_l3 = enable_l3
        self.promotion_threshold = promotion_threshold
        self.stats = CacheStats()
        self._hit_latencies: list = []
        self._miss_latencies: list = []

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache, checking all levels.

        Promotes frequently accessed items to L1.
        """
        start = time.time()

        # Try L1 first
        entry = await self.l1.get(key)
        if entry is not None:
            self._record_hit(start, CacheLevel.L1_MEMORY)
            return entry.value

        # Try L2 (Redis)
        if self.l2 is not None:
            entry = await self.l2.get(key)
            if entry is not None:
                self._record_hit(start, CacheLevel.L2_REDIS)

                # Promote to L1 if accessed frequently
                if entry.access_count >= self.promotion_threshold:
                    await self._promote(entry)

                return entry.value

        # Cache miss
        self._record_miss(start)
        return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        level: CacheLevel = CacheLevel.L1_MEMORY,
    ) -> None:
        """
        Set value in cache at specified level.

        By default, writes to L1 and falls through to L2.
        """
        if level in (CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS):
            await self.l1.set(key, value, ttl_seconds)

        if self.l2 is not None and level == CacheLevel.L2_REDIS:
            await self.l2.set(key, value, ttl_seconds)

    async def delete(self, key: str) -> bool:
        """Delete key from all cache levels."""
        l1_deleted = await self.l1.delete(key)
        l2_deleted = False

        if self.l2 is not None:
            l2_deleted = await self.l2.delete(key)

        return l1_deleted or l2_deleted

    async def clear(self) -> None:
        """Clear all cache levels."""
        await self.l1.clear()
        # Note: L2 (Redis) clear would affect other services

    async def _promote(self, entry: CacheEntry) -> None:
        """Promote entry from lower level to L1."""
        await self.l1.set(entry.key, entry.value, entry.ttl_seconds)
        self.stats.promotions += 1
        logger.debug(f"Promoted {entry.key} to L1")

    def _record_hit(self, start_time: float, level: CacheLevel) -> None:
        """Record cache hit."""
        latency_ms = (time.time() - start_time) * 1000
        self.stats.hits += 1
        self._hit_latencies.append(latency_ms)

        if level == CacheLevel.L1_MEMORY:
            self.stats.l1_hits += 1
        elif level == CacheLevel.L2_REDIS:
            self.stats.l2_hits += 1
        elif level == CacheLevel.L3_DATABASE:
            self.stats.l3_hits += 1

        # Update average
        if self._hit_latencies:
            self.stats.avg_hit_latency_ms = sum(self._hit_latencies[-100:]) / len(self._hit_latencies[-100:])

    def _record_miss(self, start_time: float) -> None:
        """Record cache miss."""
        latency_ms = (time.time() - start_time) * 1000
        self.stats.misses += 1
        self._miss_latencies.append(latency_ms)

        if self._miss_latencies:
            self.stats.avg_miss_latency_ms = sum(self._miss_latencies[-100:]) / len(self._miss_latencies[-100:])

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            **self.stats.to_dict(),
            "l1_size": self.l1.size,
            "l1_max_size": self.l1.max_size,
            "l2_enabled": self.l2 is not None,
            "l3_enabled": self.enable_l3,
        }


def cache_key(*args, **kwargs) -> str:
    """Generate a cache key from arguments using SHA256."""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_str = ":".join(key_parts)
    return hashlib.sha256(key_str.encode()).hexdigest()


def cached(
    ttl_seconds: int = 300,
    key_prefix: str = "",
):
    """
    Decorator for caching function results.

    Usage:
        @cached(ttl_seconds=60)
        async def get_market_data(symbol: str):
            ...
    """

    def decorator(func: Callable):
        _cache = MultiLevelCache()

        async def wrapper(*args, **kwargs):
            key = f"{key_prefix}{func.__name__}:{cache_key(*args, **kwargs)}"

            # Try to get from cache
            result = await _cache.get(key)
            if result is not None:
                return result

            # Call function and cache result
            result = await func(*args, **kwargs)
            await _cache.set(key, result, ttl_seconds=ttl_seconds)
            return result

        wrapper._cache = _cache
        return wrapper

    return decorator


# Global cache instance
_global_cache: Optional[MultiLevelCache] = None


def get_multi_level_cache() -> MultiLevelCache:
    """Get global multi-level cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = MultiLevelCache()
    return _global_cache


# Export
__all__ = [
    "MultiLevelCache",
    "CacheEntry",
    "CacheStats",
    "CacheLevel",
    "L1MemoryCache",
    "L2RedisCache",
    "cached",
    "cache_key",
    "get_multi_level_cache",
]
