"""
Redis-based Distributed Lock for Pipeline Jobs (P5.1b).

Prevents concurrent execution of the same pipeline job across
multiple workers/processes. Uses Redis SET NX EX pattern (simple,
no Redlock complexity needed for single-Redis deployment).

Features:
- Async-native via redis.asyncio
- Auto-expiring locks (configurable TTL)
- Graceful fallback to in-process asyncio.Lock when Redis is unavailable
- Context manager interface for clean acquire/release

Usage::

    from backend.services.distributed_lock import DistributedLock

    lock = DistributedLock()
    async with lock.acquire("pipeline:BTCUSDT:15", ttl=300):
        # Only one worker executes this at a time
        result = await run_pipeline(...)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Default lock TTL: 5 minutes (pipeline jobs should complete within this)
_DEFAULT_TTL_SECONDS = 300

# Redis key prefix for pipeline locks
_LOCK_PREFIX = "bybit:lock:"


class DistributedLock:
    """
    Redis-based distributed lock with async context manager interface.

    Falls back to a local asyncio.Lock when Redis is unavailable,
    ensuring the application still works in single-process mode.
    """

    def __init__(self, redis_url: str | None = None):
        """
        Initialize the distributed lock.

        Args:
            redis_url: Redis connection URL. Defaults to REDIS_URL env var
                       or ``redis://localhost:6379``.
        """
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._redis = None
        self._local_locks: dict[str, asyncio.Lock] = {}
        self._lock_id = str(uuid.uuid4())[:8]  # Instance identifier

    async def _get_redis(self):
        """Lazy-connect to Redis."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis

                self._redis = await aioredis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=3,
                )
                # Verify connection
                await self._redis.ping()
                logger.info("DistributedLock connected to Redis: %s", self._redis_url)
            except Exception as e:
                logger.warning(
                    "DistributedLock Redis unavailable (%s), using local locks", e
                )
                self._redis = None
        return self._redis

    def _get_local_lock(self, key: str) -> asyncio.Lock:
        """Get or create a local asyncio.Lock for fallback."""
        if key not in self._local_locks:
            self._local_locks[key] = asyncio.Lock()
        return self._local_locks[key]

    @asynccontextmanager
    async def acquire(
        self,
        resource: str,
        *,
        ttl: int = _DEFAULT_TTL_SECONDS,
        retry_interval: float = 0.5,
        max_retries: int = 10,
    ) -> AsyncIterator[bool]:
        """
        Acquire a distributed lock on the given resource.

        Args:
            resource: Lock key name (e.g. "pipeline:BTCUSDT:15").
            ttl: Lock TTL in seconds (auto-expires to prevent deadlocks).
            retry_interval: Seconds between acquire retries.
            max_retries: Maximum number of acquire attempts.

        Yields:
            True if Redis lock acquired, False if using local fallback.

        Raises:
            TimeoutError: If lock cannot be acquired within max_retries.
        """
        redis_client = await self._get_redis()
        lock_key = f"{_LOCK_PREFIX}{resource}"
        lock_value = f"{self._lock_id}:{uuid.uuid4().hex[:8]}"

        use_redis = redis_client is not None
        if use_redis:
            # Redis-based locking (SET NX EX)
            acquired = False
            redis_error = False
            for attempt in range(max_retries):
                try:
                    result = await redis_client.set(
                        lock_key, lock_value, nx=True, ex=ttl
                    )
                    if result:
                        acquired = True
                        logger.debug("Lock acquired: %s (attempt %d)", lock_key, attempt + 1)
                        break
                except Exception as e:
                    logger.warning("Redis lock error on attempt %d: %s", attempt + 1, e)
                    redis_error = True
                    break  # Fall through to local lock

                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_interval)

            if acquired:
                try:
                    yield True
                finally:
                    # Release: only delete if WE still hold the lock (compare-and-delete)
                    try:
                        current = await redis_client.get(lock_key)
                        if current == lock_value:
                            await redis_client.delete(lock_key)
                            logger.debug("Lock released: %s", lock_key)
                    except Exception as e:
                        logger.warning("Lock release error: %s", e)
                return

            if not redis_error:
                # Genuine contention (another worker holds the lock)
                raise TimeoutError(
                    f"Could not acquire distributed lock '{resource}' "
                    f"after {max_retries} attempts ({max_retries * retry_interval:.1f}s)"
                )
            # Redis error — fall through to local lock
            logger.info("Falling back to local lock for '%s'", resource)

        # Fallback: local asyncio.Lock (single-process safety)
        local_lock = self._get_local_lock(resource)
        try:
            await asyncio.wait_for(local_lock.acquire(), timeout=max_retries * retry_interval)
        except TimeoutError:
            raise TimeoutError(
                f"Could not acquire local lock '{resource}' "
                f"after {max_retries * retry_interval:.1f}s"
            )
        try:
            yield False
        finally:
            local_lock.release()

    async def is_locked(self, resource: str) -> bool:
        """Check if a resource is currently locked."""
        redis_client = await self._get_redis()
        lock_key = f"{_LOCK_PREFIX}{resource}"

        if redis_client is not None:
            try:
                return await redis_client.exists(lock_key) > 0
            except Exception:
                pass

        # Fallback: check local lock
        local = self._local_locks.get(resource)
        return local is not None and local.locked()

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis is not None:
            with contextlib.suppress(Exception):
                await self._redis.close()
            self._redis = None


# Module-level singleton
_distributed_lock: DistributedLock | None = None


def get_distributed_lock() -> DistributedLock:
    """Get or create the global DistributedLock instance."""
    global _distributed_lock
    if _distributed_lock is None:
        _distributed_lock = DistributedLock()
    return _distributed_lock
