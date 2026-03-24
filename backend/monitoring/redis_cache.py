"""
Redis-backed Context Cache

Distributed cache for AI prompt system using Redis:
- LRU eviction
- TTL-based expiration
- Automatic serialization
- Connection pooling
- Fallback to in-memory cache

Usage:
    from backend.monitoring.redis_cache import RedisContextCache
    cache = RedisContextCache()
    cache.set("key", {"data": "value"}, ttl=300)
    data = cache.get("key")
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from loguru import logger

# Try to import redis, fallback to None if not available
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False


@dataclass
class RedisCacheConfig:
    """Redis cache configuration."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    max_connections: int = 10
    decode_responses: bool = True
    prefix: str = "prompts:"
    default_ttl: int = 300
    enabled: bool = True
    fallback_to_memory: bool = True


class RedisContextCache:
    """
    Redis-backed context cache with in-memory fallback.

    Features:
    - Distributed caching
    - LRU eviction (Redis native)
    - TTL-based expiration
    - Automatic serialization
    - Connection pooling
    - Graceful fallback to in-memory cache

    Example:
        cache = RedisContextCache()
        cache.set("market:BTCUSDT:15m", {"regime": "trending"})
        data = cache.get("market:BTCUSDT:15m")
    """

    def __init__(self, config: RedisCacheConfig | None = None):
        """
        Initialize Redis cache.

        Args:
            config: Redis configuration
        """
        self.config = config or RedisCacheConfig()
        self._redis: redis.Redis | None = None
        self._memory_cache: dict[str, Any] = {}
        self._memory_cache_ttl: dict[str, float] = {}
        self._using_fallback = False

        # Check if Redis is enabled
        if not self.config.enabled:
            logger.info("📝 Redis cache disabled, using in-memory fallback")
            self._using_fallback = True
            return

        # Try to connect to Redis
        self._connect()

    def _connect(self) -> bool:
        """Connect to Redis server."""
        if not REDIS_AVAILABLE:
            logger.warning("⚠️ Redis package not installed, using in-memory fallback")
            logger.warning("Install with: pip install redis")
            self._using_fallback = True
            return False

        try:
            # Create connection pool
            pool = redis.ConnectionPool(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                max_connections=self.config.max_connections,
                decode_responses=self.config.decode_responses,
            )

            # Create Redis client
            self._redis = redis.Redis(connection_pool=pool)

            # Test connection
            self._redis.ping()

            logger.info(f"✅ Redis connected: {self.config.host}:{self.config.port}/{self.config.db}")

            self._using_fallback = False
            return True

        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}")

            if self.config.fallback_to_memory:
                logger.info("📝 Falling back to in-memory cache")
                self._using_fallback = True
            else:
                logger.error("❌ Redis connection failed and fallback disabled")
                raise

            return False

    def get(self, key: str) -> Any | None:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        if self._using_fallback:
            return self._get_memory(key)

        try:
            if self._redis is None:
                return self._get_memory(key)

            full_key = f"{self.config.prefix}{key}"
            value = self._redis.get(full_key)

            if value is None:
                return None

            # Deserialize JSON
            return json.loads(value)

        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return self._get_memory(key)

    def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: config.default_ttl)

        Returns:
            True if successful
        """
        if self._using_fallback:
            return self._set_memory(key, value, ttl)

        try:
            if self._redis is None:
                return self._set_memory(key, value, ttl)

            full_key = f"{self.config.prefix}{key}"
            ttl = ttl if ttl is not None else self.config.default_ttl

            # Serialize to JSON
            serialized = json.dumps(value, ensure_ascii=False)

            # Set with TTL
            success = self._redis.setex(full_key, ttl, serialized)

            logger.debug(f"✅ Redis set: {key} (ttl={ttl}s)")

            return bool(success)

        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return self._set_memory(key, value, ttl)

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        if self._using_fallback:
            return self._delete_memory(key)

        try:
            if self._redis is None:
                return self._delete_memory(key)

            full_key = f"{self.config.prefix}{key}"
            result = self._redis.delete(full_key)

            logger.debug(f"🗑️ Redis delete: {key}")

            return result > 0

        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return self._delete_memory(key)

    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if exists
        """
        if self._using_fallback:
            return self._exists_memory(key)

        try:
            if self._redis is None:
                return self._exists_memory(key)

            full_key = f"{self.config.prefix}{key}"
            return bool(self._redis.exists(full_key))

        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return self._exists_memory(key)

    def clear(self) -> int:
        """
        Clear all keys with prefix from cache.

        Returns:
            Number of keys deleted
        """
        if self._using_fallback:
            return self._clear_memory()

        try:
            if self._redis is None:
                return self._clear_memory()

            # Find all keys with prefix
            pattern = f"{self.config.prefix}*"
            keys = self._redis.keys(pattern)

            if keys:
                deleted = self._redis.delete(*keys)
                logger.info(f"🗑️ Redis cleared: {deleted} keys")
                return deleted

            return 0

        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return self._clear_memory()

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Statistics dict
        """
        if self._using_fallback:
            return self._get_memory_stats()

        try:
            if self._redis is None:
                return self._get_memory_stats()

            # Get Redis info
            info = self._redis.info("memory")

            # Count keys with our prefix
            pattern = f"{self.config.prefix}*"
            keys = self._redis.keys(pattern)

            return {
                "backend": "redis",
                "connected": True,
                "size": len(keys),
                "used_memory_mb": info.get("used_memory", 0) / (1024 * 1024),
                "used_memory_peak_mb": info.get("used_memory_peak", 0) / (1024 * 1024),
                "connected_clients": info.get("connected_clients", 0),
                "prefix": self.config.prefix,
                "default_ttl": self.config.default_ttl,
            }

        except Exception as e:
            logger.error(f"Redis stats error: {e}")
            return self._get_memory_stats()

    def is_using_fallback(self) -> bool:
        """Check if using in-memory fallback."""
        return self._using_fallback

    def reconnect(self) -> bool:
        """
        Attempt to reconnect to Redis.

        Returns:
            True if reconnected
        """
        self._using_fallback = False
        return self._connect()

    # In-memory fallback methods

    def _get_memory(self, key: str) -> Any | None:
        """Get from in-memory cache."""
        # Check TTL
        if key in self._memory_cache_ttl:
            if time.time() > self._memory_cache_ttl[key]:
                # Expired
                del self._memory_cache[key]
                del self._memory_cache_ttl[key]
                return None

        return self._memory_cache.get(key)

    def _set_memory(self, key: str, value: Any, ttl: int | None) -> bool:
        """Set in in-memory cache."""
        self._memory_cache[key] = value

        if ttl is not None:
            self._memory_cache_ttl[key] = time.time() + ttl

        return True

    def _delete_memory(self, key: str) -> bool:
        """Delete from in-memory cache."""
        if key in self._memory_cache:
            del self._memory_cache[key]
            if key in self._memory_cache_ttl:
                del self._memory_cache_ttl[key]
            return True
        return False

    def _exists_memory(self, key: str) -> bool:
        """Check if key exists in in-memory cache."""
        # Check TTL first
        if key in self._memory_cache_ttl:
            if time.time() > self._memory_cache_ttl[key]:
                del self._memory_cache[key]
                del self._memory_cache_ttl[key]
                return False

        return key in self._memory_cache

    def _clear_memory(self) -> int:
        """Clear in-memory cache."""
        count = len(self._memory_cache)
        self._memory_cache.clear()
        self._memory_cache_ttl.clear()
        return count

    def _get_memory_stats(self) -> dict[str, Any]:
        """Get in-memory cache stats."""
        # Clean expired
        now = time.time()
        expired = [k for k, ttl in self._memory_cache_ttl.items() if now > ttl]
        for key in expired:
            del self._memory_cache[key]
            del self._memory_cache_ttl[key]

        return {
            "backend": "memory",
            "connected": True,
            "size": len(self._memory_cache),
            "prefix": self.config.prefix,
            "default_ttl": self.config.default_ttl,
            "fallback": self._using_fallback,
        }


# Global cache instance
_cache: RedisContextCache | None = None


def get_redis_cache(config: RedisCacheConfig | None = None) -> RedisContextCache:
    """
    Get or create Redis cache instance (singleton).

    Args:
        config: Optional configuration

    Returns:
        RedisContextCache instance
    """
    global _cache
    if _cache is None:
        _cache = RedisContextCache(config)
    return _cache


def init_redis_cache_from_env() -> RedisContextCache:
    """
    Initialize Redis cache from environment variables.

    Environment variables:
        REDIS_HOST: Redis host (default: localhost)
        REDIS_PORT: Redis port (default: 6379)
        REDIS_DB: Redis database (default: 0)
        REDIS_PASSWORD: Redis password (default: None)
        REDIS_ENABLED: Enable Redis (default: true)
        REDIS_FALLBACK: Fallback to memory (default: true)

    Returns:
        RedisContextCache instance
    """
    config = RedisCacheConfig(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD"),
        enabled=os.getenv("REDIS_ENABLED", "true").lower() == "true",
        fallback_to_memory=os.getenv("REDIS_FALLBACK", "true").lower() == "true",
    )

    return get_redis_cache(config)
