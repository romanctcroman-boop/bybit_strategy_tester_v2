"""
Persistent Feature Store with Redis Backend

This module extends the FeatureStore with Redis persistence to solve
the P0 issue of data loss on restart.

Audit Reference: docs/ML_SYSTEM_AUDIT_2026_01_28.md - P0 Issue #1
"""

from __future__ import annotations

import logging
import pickle
from datetime import UTC, datetime
from typing import Any

import numpy as np

from backend.ml.enhanced.feature_store import (
    FeatureStore,
)

logger = logging.getLogger(__name__)


class PersistentFeatureStore(FeatureStore):
    """
    Feature Store with Redis persistence for computed features.

    Solves the P0 issue where features are lost on restart.

    Features:
        - Redis backend for feature caching
        - TTL support for cache entries
        - Fallback to file system if Redis unavailable
        - Async and sync API support

    Example:
        # Initialize with Redis
        store = PersistentFeatureStore(
            storage_path="./feature_store",
            redis_url="redis://localhost:6379",
            default_ttl=3600
        )

        # Compute and cache features
        features = await store.compute(data, group="momentum_indicators")

        # Features persist across restarts!
    """

    def __init__(
        self,
        storage_path: str = "./feature_store",
        redis_url: str | None = None,
        default_ttl: int = 3600,  # 1 hour default TTL
        key_prefix: str = "feature_store:",
        fallback_to_memory: bool = True,
    ):
        """
        Initialize persistent feature store.

        Args:
            storage_path: Path for file-based storage
            redis_url: Redis connection URL (e.g., "redis://localhost:6379")
            default_ttl: Default TTL in seconds for cached features
            key_prefix: Prefix for Redis keys
            fallback_to_memory: Use memory cache if Redis unavailable
        """
        # Initialize parent class
        super().__init__(storage_path)

        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self.fallback_to_memory = fallback_to_memory

        # Redis connection
        self._redis: Any | None = None
        self._redis_available = False

        # Initialize Redis connection
        if redis_url:
            self._init_redis()

    def _init_redis(self) -> None:
        """Initialize Redis connection."""
        try:
            import redis

            self._redis = redis.from_url(
                self.redis_url,
                decode_responses=False,  # We'll handle bytes
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            # Test connection
            self._redis.ping()
            self._redis_available = True
            logger.info(f"Connected to Redis at {self.redis_url}")
        except ImportError:
            logger.warning("redis package not installed, using memory cache")
            self._redis_available = False
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, using memory cache")
            self._redis_available = False

    def _make_redis_key(self, key: str) -> str:
        """Create a Redis key with prefix."""
        return f"{self.key_prefix}{key}"

    def store_features(
        self,
        name: str,
        features: np.ndarray,
        ttl_seconds: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Store computed features with persistence.

        Args:
            name: Feature name/identifier
            features: Computed feature values
            ttl_seconds: Time-to-live in seconds (None = default TTL)
            metadata: Optional metadata to store with features

        Returns:
            True if stored successfully
        """
        ttl = ttl_seconds or self.default_ttl
        key = self._make_redis_key(name)

        # Prepare data for storage
        data = {
            "features": features.tobytes(),
            "dtype": str(features.dtype),
            "shape": features.shape,
            "metadata": metadata or {},
            "stored_at": datetime.now(UTC).isoformat(),
        }

        if self._redis_available and self._redis:
            try:
                serialized = pickle.dumps(data)
                self._redis.setex(key, ttl, serialized)
                logger.debug(f"Stored features '{name}' in Redis with TTL {ttl}s")
                return True
            except Exception as e:
                logger.warning(f"Redis store failed: {e}")
                if self.fallback_to_memory:
                    return self._store_in_memory(name, features, metadata)
                return False
        elif self.fallback_to_memory:
            return self._store_in_memory(name, features, metadata)

        return False

    def _store_in_memory(
        self,
        name: str,
        features: np.ndarray,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Store features in memory cache (fallback)."""
        self.feature_cache[name] = features
        self.cache_timestamps[name] = datetime.now(UTC)
        logger.debug(f"Stored features '{name}' in memory cache")
        return True

    def get_features(
        self,
        name: str,
        default: np.ndarray | None = None,
    ) -> np.ndarray | None:
        """
        Retrieve stored features.

        Args:
            name: Feature name/identifier
            default: Default value if not found

        Returns:
            Feature array or default
        """
        key = self._make_redis_key(name)

        if self._redis_available and self._redis:
            try:
                serialized = self._redis.get(key)
                if serialized:
                    data = pickle.loads(serialized)
                    features = np.frombuffer(data["features"], dtype=data["dtype"]).reshape(data["shape"])
                    logger.debug(f"Retrieved features '{name}' from Redis")
                    return features
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")

        # Check memory cache
        if name in self.feature_cache:
            logger.debug(f"Retrieved features '{name}' from memory cache")
            return self.feature_cache[name]

        return default

    def delete_features(self, name: str) -> bool:
        """
        Delete stored features.

        Args:
            name: Feature name/identifier

        Returns:
            True if deleted
        """
        deleted = False
        key = self._make_redis_key(name)

        if self._redis_available and self._redis:
            try:
                deleted = self._redis.delete(key) > 0
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")

        # Also clean memory cache
        if name in self.feature_cache:
            del self.feature_cache[name]
            if name in self.cache_timestamps:
                del self.cache_timestamps[name]
            deleted = True

        return deleted

    def exists(self, name: str) -> bool:
        """Check if features exist in store."""
        key = self._make_redis_key(name)

        if self._redis_available and self._redis:
            try:
                if self._redis.exists(key):
                    return True
            except Exception as e:
                logger.warning(f"Redis exists check failed: {e}")

        return name in self.feature_cache

    def get_ttl(self, name: str) -> int | None:
        """Get remaining TTL for stored features."""
        if self._redis_available and self._redis:
            key = self._make_redis_key(name)
            try:
                ttl = self._redis.ttl(key)
                return ttl if ttl > 0 else None
            except Exception as e:
                logger.warning(f"Redis TTL check failed: {e}")
        return None

    def refresh_ttl(self, name: str, ttl_seconds: int | None = None) -> bool:
        """Refresh TTL for stored features."""
        if self._redis_available and self._redis:
            key = self._make_redis_key(name)
            ttl = ttl_seconds or self.default_ttl
            try:
                return self._redis.expire(key, ttl)
            except Exception as e:
                logger.warning(f"Redis TTL refresh failed: {e}")
        return False

    def list_stored_features(self, pattern: str = "*") -> list[str]:
        """
        List all stored feature names matching pattern.

        Args:
            pattern: Glob pattern (e.g., "rsi_*")

        Returns:
            List of feature names
        """
        features = []
        full_pattern = self._make_redis_key(pattern)

        if self._redis_available and self._redis:
            try:
                keys = self._redis.keys(full_pattern)
                features.extend([k.decode().replace(self.key_prefix, "") for k in keys])
            except Exception as e:
                logger.warning(f"Redis list failed: {e}")

        # Add memory cache keys
        for key in self.feature_cache:
            if (pattern == "*" or key.startswith(pattern.replace("*", ""))) and key not in features:
                features.append(key)

        return features

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        stats = {
            "redis_available": self._redis_available,
            "memory_cache_size": len(self.feature_cache),
            "redis_keys": 0,
            "total_redis_memory": 0,
        }

        if self._redis_available and self._redis:
            try:
                full_pattern = self._make_redis_key("*")
                keys = self._redis.keys(full_pattern)
                stats["redis_keys"] = len(keys)

                # Get memory usage
                info = self._redis.info("memory")
                stats["total_redis_memory"] = info.get("used_memory", 0)
            except Exception as e:
                logger.warning(f"Redis stats failed: {e}")

        return stats

    async def compute(
        self,
        data: dict[str, np.ndarray],
        features: list[str] | None = None,
        group: str | None = None,
        use_cache: bool = True,
        persist: bool = True,
        ttl_seconds: int | None = None,
    ) -> dict[str, np.ndarray]:
        """
        Compute features with persistent caching.

        Extends parent compute() with Redis persistence.

        Args:
            data: Input data dict
            features: List of feature names to compute
            group: Name of feature group to compute
            use_cache: Whether to use cached values
            persist: Whether to persist computed features
            ttl_seconds: TTL for cached features

        Returns:
            Dict of feature_name -> computed values
        """
        # Get feature list
        if group:
            if group not in self.groups:
                raise ValueError(f"Group {group} not found")
            feature_list = self.groups[group].features
        elif features:
            feature_list = features
        else:
            feature_list = list(self.features.keys())

        results = {}

        for feat_name in feature_list:
            feat_def = self.features.get(feat_name)
            if feat_def is None:
                logger.warning(f"Feature {feat_name} not found, skipping")
                continue

            # Generate cache key based on data hash
            cache_key = self._get_cache_key(feat_name, data)

            # Check persistent cache first
            if use_cache:
                cached = self.get_features(cache_key)
                if cached is not None:
                    results[feat_name] = cached
                    continue

            # Compute feature
            try:
                computed = await self._compute_single(feat_def, data, results)
                results[feat_name] = computed

                # Persist to Redis
                if persist:
                    self.store_features(
                        cache_key,
                        computed,
                        ttl_seconds=ttl_seconds,
                        metadata={
                            "feature_name": feat_name,
                            "computation_fn": feat_def.computation_fn,
                            "parameters": feat_def.parameters,
                        },
                    )

            except Exception as e:
                logger.error(f"Failed to compute {feat_name}: {e}")
                if feat_def.default_value is not None:
                    n_samples = len(next(iter(data.values())))
                    results[feat_name] = np.full(n_samples, feat_def.default_value)

        return results

    def clear_cache(
        self,
        feature_name: str | None = None,
        older_than: datetime | None = None,
    ) -> int:
        """
        Clear feature cache from both Redis and memory.

        Args:
            feature_name: Clear only this feature's cache
            older_than: Not used for Redis (use TTL)

        Returns:
            Number of entries cleared
        """
        cleared = 0

        # Clear memory cache (via parent method)
        cleared += super().clear_cache(feature_name, older_than)

        # Clear Redis cache
        if self._redis_available and self._redis:
            try:
                pattern = self._make_redis_key(f"{feature_name}*") if feature_name else self._make_redis_key("*")

                keys = self._redis.keys(pattern)
                if keys:
                    cleared += self._redis.delete(*keys)
                    logger.info(f"Cleared {len(keys)} entries from Redis")
            except Exception as e:
                logger.warning(f"Redis clear failed: {e}")

        return cleared

    def health_check(self) -> dict[str, Any]:
        """Check health of feature store."""
        health = {
            "status": "healthy",
            "redis_connected": self._redis_available,
            "feature_definitions": len(self.features),
            "feature_groups": len(self.groups),
            "memory_cache_entries": len(self.feature_cache),
        }

        if self._redis_available and self._redis:
            try:
                self._redis.ping()
                health["redis_ping"] = "ok"
            except Exception as e:
                health["status"] = "degraded"
                health["redis_ping"] = str(e)
        elif self.redis_url:
            health["status"] = "degraded"
            health["redis_error"] = "Connection not available"

        return health

    def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            try:
                self._redis.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.warning(f"Error closing Redis: {e}")


# Convenience function to create feature store with best available backend
def create_feature_store(
    storage_path: str = "./feature_store",
    redis_url: str | None = None,
    auto_detect_redis: bool = True,
) -> FeatureStore:
    """
    Create a feature store with the best available backend.

    Args:
        storage_path: Path for file storage
        redis_url: Redis URL (optional)
        auto_detect_redis: Try to connect to localhost Redis if no URL provided

    Returns:
        FeatureStore instance (Persistent if Redis available)
    """
    # Auto-detect Redis
    if auto_detect_redis and not redis_url:
        default_urls = [
            "redis://localhost:6379",
            "redis://127.0.0.1:6379",
            "redis://redis:6379",  # Docker
        ]
        for url in default_urls:
            try:
                import redis

                r = redis.from_url(url, socket_timeout=1.0)
                r.ping()
                redis_url = url
                logger.info(f"Auto-detected Redis at {url}")
                break
            except Exception:
                continue

    if redis_url:
        return PersistentFeatureStore(
            storage_path=storage_path,
            redis_url=redis_url,
        )

    logger.warning("No Redis available, using file-based FeatureStore")
    return FeatureStore(storage_path=storage_path)
