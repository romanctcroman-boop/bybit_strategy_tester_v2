"""
🚀 Optimization Cache - Memoization for Strategy Results

По рекомендации Perplexity: кэширование результатов подстратегий
для ускорения повторных оптимизаций (2-5x speedup, низкая сложность).

Особенности:
- LRU-кэш для сигналов стратегий
- Disk-персистентность для результатов оптимизации
- Умная инвалидация при изменении данных
"""

import hashlib
import json
import pickle
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger


class OptimizationCache:
    """
    Multi-level cache for optimization results.

    Level 1: LRU memory cache for signals (fastest)
    Level 2: Disk cache for optimization results (persistent)
    """

    # Dynamic path resolution - works on any system
    CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache"
    MAX_MEMORY_ITEMS = 1000
    MAX_DISK_SIZE_MB = 500
    EXPIRY_DAYS = 7

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._memory_cache: dict[str, Any] = {}
        self._memory_cache_order = []  # LRU order

        # Create cache directory
        if enabled:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self._cleanup_expired()

        self.stats = {
            "memory_hits": 0,
            "memory_misses": 0,
            "disk_hits": 0,
            "disk_misses": 0,
        }

        logger.info(f"📦 OptimizationCache initialized: enabled={enabled}")

    # =========================================================
    # KEY GENERATION
    # =========================================================

    def _make_key(self, *args, **kwargs) -> str:
        """Create a unique hash key from arguments using SHA256."""
        key_data = {
            "args": [self._serialize_arg(a) for a in args],
            "kwargs": {k: self._serialize_arg(v) for k, v in sorted(kwargs.items())},
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def _serialize_arg(self, arg) -> Any:
        """Serialize argument for hashing."""
        if isinstance(arg, pd.DataFrame):
            # Hash DataFrame by shape and first/last values
            return {
                "type": "DataFrame",
                "shape": arg.shape,
                "first": arg.iloc[0].to_dict() if len(arg) > 0 else None,
                "last": arg.iloc[-1].to_dict() if len(arg) > 0 else None,
                "hash": hashlib.sha256(pd.util.hash_pandas_object(arg).values.tobytes()).hexdigest()[:8],
            }
        elif isinstance(arg, pd.Series):
            return {
                "type": "Series",
                "len": len(arg),
                "hash": hashlib.sha256(arg.values.tobytes()).hexdigest()[:8],
            }
        elif isinstance(arg, np.ndarray):
            return {
                "type": "ndarray",
                "shape": arg.shape,
                "hash": hashlib.sha256(arg.tobytes()).hexdigest()[:8],
            }
        elif isinstance(arg, (dict, list, tuple, str, int, float, bool, type(None))):
            return arg
        else:
            return str(arg)

    # =========================================================
    # MEMORY CACHE (Level 1)
    # =========================================================

    def get_memory(self, key: str) -> tuple[bool, Any]:
        """Get from memory cache."""
        if not self.enabled:
            return False, None

        if key in self._memory_cache:
            # Move to end (most recently used)
            self._memory_cache_order.remove(key)
            self._memory_cache_order.append(key)
            self.stats["memory_hits"] += 1
            return True, self._memory_cache[key]

        self.stats["memory_misses"] += 1
        return False, None

    def set_memory(self, key: str, value: Any):
        """Set in memory cache with LRU eviction."""
        if not self.enabled:
            return

        # Evict if at capacity
        while len(self._memory_cache) >= self.MAX_MEMORY_ITEMS:
            oldest = self._memory_cache_order.pop(0)
            del self._memory_cache[oldest]

        self._memory_cache[key] = value
        self._memory_cache_order.append(key)

    # =========================================================
    # DISK CACHE (Level 2)
    # =========================================================

    def _get_disk_path(self, key: str) -> Path:
        """Get disk path for cache key."""
        return self.CACHE_DIR / f"{key}.pkl"

    def get_disk(self, key: str) -> tuple[bool, Any]:
        """Get from disk cache."""
        if not self.enabled:
            return False, None

        path = self._get_disk_path(key)

        if path.exists():
            try:
                with open(path, "rb") as f:
                    data = pickle.load(f)

                # Check expiry
                if data.get("expires_at") and datetime.fromisoformat(data["expires_at"]) < datetime.now():
                    path.unlink()
                    return False, None

                self.stats["disk_hits"] += 1
                return True, data["value"]
            except Exception as e:
                logger.warning(f"Disk cache read error: {e}")
                return False, None

        self.stats["disk_misses"] += 1
        return False, None

    def set_disk(self, key: str, value: Any, expires_days: int = None):
        """Set in disk cache."""
        if not self.enabled:
            return

        expires_days = expires_days or self.EXPIRY_DAYS
        expires_at = datetime.now() + timedelta(days=expires_days)

        data = {
            "value": value,
            "created_at": datetime.now().isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        path = self._get_disk_path(key)

        try:
            with open(path, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.warning(f"Disk cache write error: {e}")

    def _cleanup_expired(self):
        """Remove expired cache files."""
        if not self.CACHE_DIR.exists():
            return

        removed = 0
        for path in self.CACHE_DIR.glob("*.pkl"):
            try:
                with open(path, "rb") as f:
                    data = pickle.load(f)

                if data.get("expires_at") and datetime.fromisoformat(data["expires_at"]) < datetime.now():
                    path.unlink()
                    removed += 1
            except Exception:
                path.unlink()
                removed += 1

        if removed:
            logger.info(f"🧹 Cleaned up {removed} expired cache files")

    # =========================================================
    # HIGH-LEVEL API
    # =========================================================

    def get(self, key: str) -> tuple[bool, Any]:
        """Get from cache (checks memory first, then disk)."""
        # Try memory
        hit, value = self.get_memory(key)
        if hit:
            return True, value

        # Try disk
        hit, value = self.get_disk(key)
        if hit:
            # Promote to memory
            self.set_memory(key, value)
            return True, value

        return False, None

    def set(self, key: str, value: Any, disk: bool = False):
        """Set in cache."""
        self.set_memory(key, value)
        if disk:
            self.set_disk(key, value)

    def clear(self):
        """Clear all caches."""
        self._memory_cache.clear()
        self._memory_cache_order.clear()

        if self.CACHE_DIR.exists():
            for path in self.CACHE_DIR.glob("*.pkl"):
                path.unlink()

        self.stats = dict.fromkeys(self.stats, 0)
        logger.info("🗑️ Cache cleared")

    def print_stats(self):
        """Print cache statistics."""
        total_hits = self.stats["memory_hits"] + self.stats["disk_hits"]
        total_misses = self.stats["memory_misses"] + self.stats["disk_misses"]
        total = total_hits + total_misses
        hit_rate = total_hits / total if total > 0 else 0

        disk_size_mb = 0.0
        if self.CACHE_DIR.exists():
            disk_size_mb = sum(f.stat().st_size for f in self.CACHE_DIR.glob("*.pkl")) / 1024 / 1024

        logger.info(
            "Cache statistics",
            memory_hits=self.stats["memory_hits"],
            memory_misses=self.stats["memory_misses"],
            disk_hits=self.stats["disk_hits"],
            disk_misses=self.stats["disk_misses"],
            hit_rate=f"{hit_rate:.1%}",
            memory_items=len(self._memory_cache),
            disk_size_mb=f"{disk_size_mb:.2f}",
        )


# =========================================================
# CACHED DECORATORS
# =========================================================

# Global cache instance
_cache = OptimizationCache(enabled=True)


def cached_signals(func):
    """Decorator to cache signal generation results."""

    def wrapper(*args, **kwargs):
        key = f"signals_{_cache._make_key(*args, **kwargs)}"

        hit, result = _cache.get(key)
        if hit:
            return result

        result = func(*args, **kwargs)
        _cache.set(key, result, disk=False)  # Memory only for signals
        return result

    return wrapper


def cached_optimization(func):
    """Decorator to cache optimization results (with disk persistence)."""

    def wrapper(*args, **kwargs):
        key = f"opt_{_cache._make_key(*args, **kwargs)}"

        hit, result = _cache.get(key)
        if hit:
            logger.info("📦 Cache HIT for optimization")
            return result

        result = func(*args, **kwargs)
        _cache.set(key, result, disk=True)  # Persist to disk
        return result

    return wrapper


def get_cache() -> OptimizationCache:
    """Get the global cache instance."""
    return _cache


# =========================================================
# CACHED RSI CALCULATION
# =========================================================


@lru_cache(maxsize=100)
def calculate_rsi_cached(close_hash: str, period: int) -> np.ndarray:
    """
    LRU-cached RSI calculation.

    Note: close_hash is used as cache key to avoid hashing large arrays.
    Actual close data should be stored elsewhere and looked up by hash.
    """
    # This is a placeholder - actual implementation would look up close data
    pass


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 OPTIMIZATION CACHE TEST")
    print("=" * 70)

    cache = OptimizationCache(enabled=True)

    # Test memory cache
    print("\n📝 Testing memory cache...")
    cache.set("test_key", {"value": 123, "data": [1, 2, 3]})

    hit, value = cache.get("test_key")
    print(f"Hit: {hit}, Value: {value}")

    # Test disk cache
    print("\n💾 Testing disk cache...")
    cache.set("disk_key", {"large": "data" * 100}, disk=True)

    hit, value = cache.get("disk_key")
    print(f"Hit: {hit}, Value type: {type(value)}")

    # Test key generation
    print("\n🔑 Testing key generation...")
    import pandas as pd

    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    key1 = cache._make_key(df, period=14, overbought=70)
    key2 = cache._make_key(df, period=14, overbought=70)
    key3 = cache._make_key(df, period=21, overbought=70)

    print(f"Same args, same key: {key1 == key2}")
    print(f"Diff args, diff key: {key1 != key3}")

    # Stats
    cache.print_stats()

    print("\n✅ Cache test complete!")
