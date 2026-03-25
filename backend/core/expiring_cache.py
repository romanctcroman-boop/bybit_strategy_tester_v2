"""Expiring data structures for caching and deduplication.

These structures automatically expire old entries to prevent memory growth.
"""

import threading
import time
from collections import OrderedDict
from typing import Any


class ExpiringSet:
    """
    A set that automatically expires entries after a TTL.

    Thread-safe and memory-efficient for deduplication of streaming data.

    Example:
        seen = ExpiringSet(ttl_seconds=60, max_size=100000)

        if trade_id in seen:
            # Duplicate trade, skip
            continue

        seen.add(trade_id)
        process_trade(trade)
    """

    def __init__(self, ttl_seconds: float = 60.0, max_size: int = 100000):
        """
        Initialize ExpiringSet.

        Args:
            ttl_seconds: Time to live for each entry
            max_size: Maximum entries to keep (oldest evicted first)
        """
        self.ttl = ttl_seconds
        self.max_size = max_size

        # OrderedDict to maintain insertion order for efficient eviction
        self._data: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()

        # Stats
        self._stats = {
            "adds": 0,
            "hits": 0,
            "evictions_ttl": 0,
            "evictions_size": 0,
        }

    def add(self, item: str) -> bool:
        """
        Add item to set.

        Returns:
            True if item was new, False if already existed
        """
        now = time.time()

        with self._lock:
            # Check if already exists
            if item in self._data:
                # Update timestamp (refresh TTL)
                self._data.move_to_end(item)
                self._data[item] = now
                self._stats["hits"] += 1
                return False

            # Evict expired entries (lazy cleanup)
            self._cleanup_expired(now)

            # Evict oldest if at max size
            while len(self._data) >= self.max_size:
                self._data.popitem(last=False)
                self._stats["evictions_size"] += 1

            # Add new entry
            self._data[item] = now
            self._stats["adds"] += 1
            return True

    def __contains__(self, item: str) -> bool:
        """Check if item is in set (and not expired)."""
        now = time.time()

        with self._lock:
            if item not in self._data:
                return False

            # Check if expired
            if now - self._data[item] > self.ttl:
                del self._data[item]
                self._stats["evictions_ttl"] += 1
                return False

            return True

    def _cleanup_expired(self, now: float):
        """Remove expired entries from the front of the OrderedDict."""
        # Only clean first 100 entries per call to avoid blocking
        cleaned = 0
        max_clean = 100

        while self._data and cleaned < max_clean:
            key, timestamp = next(iter(self._data.items()))
            if now - timestamp > self.ttl:
                del self._data[key]
                self._stats["evictions_ttl"] += 1
                cleaned += 1
            else:
                break  # Entries are ordered, so remaining are fresh

    def clear(self):
        """Clear all entries."""
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        """Return current size (may include expired entries)."""
        return len(self._data)

    def get_stats(self) -> dict:
        """Get statistics."""
        return {
            **self._stats,
            "current_size": len(self._data),
            "ttl_seconds": self.ttl,
            "max_size": self.max_size,
        }


class ExpiringDict:
    """
    A dictionary that automatically expires entries after a TTL.

    Thread-safe and memory-efficient.

    Example:
        cache = ExpiringDict(ttl_seconds=300, max_size=10000)
        cache.set("key", expensive_value)
        value = cache.get("key")  # Returns None if expired
    """

    def __init__(self, ttl_seconds: float = 300.0, max_size: int = 10000):
        """
        Initialize ExpiringDict.

        Args:
            ttl_seconds: Time to live for each entry
            max_size: Maximum entries to keep (oldest evicted first)
        """
        self.ttl = ttl_seconds
        self.max_size = max_size

        # Entry format: (value, timestamp)
        self._data: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    def set(self, key: str, value: Any) -> None:
        """Set value with automatic TTL."""
        now = time.time()

        with self._lock:
            # Remove if exists (to update order)
            if key in self._data:
                del self._data[key]

            # Evict oldest if at max
            while len(self._data) >= self.max_size:
                self._data.popitem(last=False)

            self._data[key] = (value, now)

    def get(self, key: str, default: Any = None) -> Any:
        """Get value if exists and not expired."""
        now = time.time()

        with self._lock:
            if key not in self._data:
                return default

            value, timestamp = self._data[key]

            if now - timestamp > self.ttl:
                del self._data[key]
                return default

            return value

    def __contains__(self, key: str) -> bool:
        """Check if key exists and not expired."""
        return self.get(key) is not None

    def delete(self, key: str) -> bool:
        """Delete key. Returns True if existed."""
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    def clear(self):
        """Clear all entries."""
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        return len(self._data)
