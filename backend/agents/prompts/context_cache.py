"""
Context Cache for AI Agent Prompts

Caches market contexts and generated prompts to:
- Reduce redundant API calls
- Speed up repeated requests
- Track prompt usage patterns
- Reduce costs

Supports:
- In-memory LRU cache (default)
- Redis-backed distributed cache (optional)

Usage:
    cache = ContextCache()
    cache_key = cache.set(context_data, ttl=300)
    cached = cache.get(cache_key)
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

# Optional Redis support
try:
    from backend.monitoring.redis_cache import RedisCacheConfig, RedisContextCache

    REDIS_AVAILABLE = True
except ImportError:
    RedisContextCache = None  # type: ignore
    RedisCacheConfig = None  # type: ignore
    REDIS_AVAILABLE = False


@dataclass
class CacheEntry:
    """Cache entry with metadata."""

    key: str
    value: Any
    created_at: float
    ttl: int  # Time to live in seconds
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        return time.time() > (self.created_at + self.ttl)

    def touch(self) -> None:
        """Update last accessed time and access count."""
        self.access_count += 1
        self.last_accessed = time.time()


class ContextCache:
    """
    LRU cache for market contexts and prompts.

    Features:
    - TTL-based expiration
    - LRU eviction
    - Hit/miss statistics
    - Key generation from data
    - Redis backend support (optional)

    Example:
        cache = ContextCache(max_size=1000, default_ttl=300)
        key = cache.set({"symbol": "BTCUSDT", "regime": "trending"})
        data = cache.get(key)
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 300,
        enable_stats: bool = True,
        use_redis: bool = False,
        redis_config: dict[str, Any] | None = None,
    ):
        """
        Initialize context cache.

        Args:
            max_size: Maximum cache entries (default: 1000)
            default_ttl: Default TTL in seconds (default: 300 = 5 min)
            enable_stats: Enable statistics tracking (default: True)
            use_redis: Use Redis backend (default: False)
            redis_config: Redis configuration dict (optional)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.enable_stats = enable_stats
        self.use_redis = use_redis and REDIS_AVAILABLE

        # Redis backend
        if self.use_redis and RedisContextCache:
            config = None
            if redis_config:
                config = RedisCacheConfig(**redis_config)
            self._redis_cache = RedisContextCache(config)
            logger.info("✅ ContextCache using Redis backend")
        else:
            self._redis_cache = None

        # In-memory backend
        self._cache: dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0

        logger.info(
            f"💾 ContextCache initialized (max_size={max_size}, default_ttl={default_ttl}s, redis={self.use_redis})"
        )

    def set(
        self,
        data: dict[str, Any],
        ttl: int | None = None,
        key: str | None = None,
    ) -> str:
        """
        Store data in cache.

        Args:
            data: Data to cache
            ttl: Time to live in seconds (default: default_ttl)
            key: Custom key (default: auto-generated from data hash)

        Returns:
            Cache key
        """
        if key is None:
            key = self._generate_key(data)

        ttl = ttl if ttl is not None else self.default_ttl

        # Try Redis first
        if self._redis_cache:
            try:
                self._redis_cache.set(key, data, ttl)
                logger.debug(f"💾 Redis set: {key[:16]}... (ttl={ttl}s)")
                return key
            except Exception as e:
                logger.error(f"Redis set error, falling back to memory: {e}")

        # In-memory fallback
        entry = CacheEntry(
            key=key,
            value=data,
            created_at=time.time(),
            ttl=ttl,
        )

        # Evict if at capacity
        if len(self._cache) >= self.max_size:
            self._evict_lru()

        self._cache[key] = entry

        logger.debug(f"💾 Memory set: {key[:16]}... (ttl={ttl}s)")

        return key

    def get(self, key: str) -> Any | None:
        """
        Retrieve data from cache.

        Args:
            key: Cache key

        Returns:
            Cached data or None if not found/expired
        """
        # Try Redis first
        if self._redis_cache:
            try:
                value = self._redis_cache.get(key)
                if value is not None:
                    self._hits += 1
                    logger.debug(f"💾 Redis hit: {key[:16]}...")
                    return value
            except Exception as e:
                logger.error(f"Redis get error, falling back to memory: {e}")

        # In-memory fallback
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            logger.debug(f"💾 Memory miss: {key[:16]}...")
            return None

        if entry.is_expired():
            del self._cache[key]
            self._misses += 1
            logger.debug(f"💾 Memory expired: {key[:16]}...")
            return None

        entry.touch()
        self._hits += 1
        logger.debug(f"💾 Memory hit: {key[:16]}... (accesses={entry.access_count})")

        return entry.value

    def get_or_set(
        self,
        key: str,
        factory: callable,
        ttl: int | None = None,
    ) -> Any:
        """
        Get from cache or set using factory function.

        Args:
            key: Cache key
            factory: Function to generate value if not cached
            ttl: Time to live in seconds

        Returns:
            Cached or newly generated value
        """
        value = self.get(key)

        if value is None:
            value = factory()
            self.set(value, ttl=ttl, key=key)

        return value

    def delete(self, key: str) -> bool:
        """
        Delete entry from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"🗑️ Cache delete: {key[:16]}...")
            return True
        return False

    def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"🗑️ Cache cleared ({count} entries)")
        return count

    def cleanup_expired(self) -> int:
        """
        Remove expired entries.

        Returns:
            Number of entries removed
        """
        expired_keys = [key for key, entry in self._cache.items() if entry.is_expired()]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"🧹 Cleaned up {len(expired_keys)} expired entries")

        return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        # If using Redis, get Redis stats
        if self._redis_cache:
            redis_stats = self._redis_cache.get_stats()
            return {
                **redis_stats,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0.0,
            }

        # In-memory stats
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        # Size distribution by TTL
        now = time.time()
        expiring_soon = sum(1 for entry in self._cache.values() if (entry.created_at + entry.ttl) - now < 60)

        return {
            "backend": "memory",
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "expiring_soon": expiring_soon,
            "default_ttl": self.default_ttl,
        }

    def _generate_key(self, data: dict[str, Any]) -> str:
        """Generate cache key from data."""
        # Sort keys for consistent hashing
        normalized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Find entry with oldest last_accessed
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)

        del self._cache[lru_key]
        logger.debug(f"🗑️ Evicted LRU: {lru_key[:16]}...")

    def keys(self) -> list[str]:
        """Get all cache keys."""
        return list(self._cache.keys())

    def values(self) -> list[Any]:
        """Get all cached values."""
        return [entry.value for entry in self._cache.values()]

    def items(self) -> list[tuple[str, Any]]:
        """Get all cache items."""
        return [(key, entry.value) for key, entry in self._cache.items()]

    def __len__(self) -> int:
        """Get cache size."""
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if key is in cache."""
        return key in self._cache and not self._cache[key].is_expired()


class MarketContextCache(ContextCache):
    """
    Specialized cache for market contexts.

    Provides convenient methods for caching market analysis
    and strategy generation results.
    """

    def cache_market_context(
        self,
        symbol: str,
        timeframe: str,
        context_data: dict[str, Any],
        ttl: int = 300,
    ) -> str:
        """
        Cache market context for symbol/timeframe.

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe
            context_data: Market context data
            ttl: Time to live in seconds

        Returns:
            Cache key
        """
        key = f"market:{symbol}:{timeframe}"
        self.set(context_data, ttl=ttl, key=key)
        logger.debug(f"💾 Cached market context: {key}")
        return key

    def get_market_context(
        self,
        symbol: str,
        timeframe: str,
    ) -> dict[str, Any] | None:
        """
        Get cached market context.

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe

        Returns:
            Market context or None
        """
        key = f"market:{symbol}:{timeframe}"
        return self.get(key)

    def cache_strategy_prompt(
        self,
        symbol: str,
        timeframe: str,
        agent_type: str,
        prompt: str,
        ttl: int = 600,
    ) -> str:
        """
        Cache generated strategy prompt.

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe
            agent_type: Agent type
            prompt: Generated prompt
            ttl: Time to live in seconds

        Returns:
            Cache key
        """
        key = f"prompt:{symbol}:{timeframe}:{agent_type}"
        self.set({"prompt": prompt}, ttl=ttl, key=key)
        logger.debug(f"💾 Cached strategy prompt: {key}")
        return key

    def get_strategy_prompt(
        self,
        symbol: str,
        timeframe: str,
        agent_type: str,
    ) -> str | None:
        """
        Get cached strategy prompt.

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe
            agent_type: Agent type

        Returns:
            Prompt or None
        """
        key = f"prompt:{symbol}:{timeframe}:{agent_type}"
        entry = self.get(key)
        return entry.get("prompt") if entry else None
