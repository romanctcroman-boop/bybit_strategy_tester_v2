"""
Tests for Redis distributed lock (P5.1b).

Tests the DistributedLock with local asyncio.Lock fallback
(no Redis required for unit tests).
"""

from __future__ import annotations

import asyncio

import pytest

from backend.services.distributed_lock import DistributedLock


@pytest.fixture
def lock() -> DistributedLock:
    """Create a DistributedLock that will fall back to local locks
    (Redis unavailable in CI)."""
    return DistributedLock(redis_url="redis://localhost:1")  # intentionally bad port


@pytest.mark.asyncio
class TestDistributedLockFallback:
    """Tests using local asyncio.Lock fallback (no Redis needed)."""

    async def test_acquire_and_release(self, lock: DistributedLock):
        """Lock can be acquired and released via context manager."""
        async with lock.acquire("test:resource", ttl=10, max_retries=1) as is_redis:
            assert is_redis is False  # local fallback
            # Inside lock — should be locked
            assert await lock.is_locked("test:resource")

        # After release — should not be locked
        assert not await lock.is_locked("test:resource")

    async def test_lock_prevents_concurrent_access(self, lock: DistributedLock):
        """Two tasks cannot hold the same lock simultaneously."""
        order: list[str] = []

        async def task(name: str, delay: float):
            async with lock.acquire("shared:resource", ttl=10, max_retries=20, retry_interval=0.05):
                order.append(f"{name}:start")
                await asyncio.sleep(delay)
                order.append(f"{name}:end")

        await asyncio.gather(task("A", 0.1), task("B", 0.1))

        # One task must complete before the other starts
        assert order[0].endswith(":start")
        assert order[1].endswith(":end")
        assert order[2].endswith(":start")
        assert order[3].endswith(":end")

    async def test_different_resources_no_contention(self, lock: DistributedLock):
        """Different resource keys do not block each other."""
        results: list[str] = []

        async def task(resource: str):
            async with lock.acquire(resource, ttl=10, max_retries=1):
                results.append(resource)
                await asyncio.sleep(0.01)

        await asyncio.gather(task("res:A"), task("res:B"))
        assert set(results) == {"res:A", "res:B"}

    async def test_timeout_raises(self, lock: DistributedLock):
        """TimeoutError is raised when lock cannot be acquired in time."""
        # Hold the lock
        async with lock.acquire("timeout:test", ttl=10, max_retries=1):
            # Try to acquire same lock with very short timeout
            with pytest.raises(TimeoutError, match="Could not acquire"):
                async with lock.acquire(
                    "timeout:test", ttl=10, max_retries=1, retry_interval=0.01
                ):
                    pass  # Should never reach here

    async def test_is_locked_false_when_not_acquired(self, lock: DistributedLock):
        """is_locked returns False for resources never acquired."""
        assert not await lock.is_locked("never:acquired")

    async def test_reentrant_different_keys(self, lock: DistributedLock):
        """Nesting locks on different keys works."""
        async with lock.acquire("outer:key", ttl=10, max_retries=1):  # noqa: SIM117
            async with lock.acquire("inner:key", ttl=10, max_retries=1):
                assert await lock.is_locked("outer:key")
                assert await lock.is_locked("inner:key")

    async def test_close_is_idempotent(self, lock: DistributedLock):
        """close() can be called multiple times without error."""
        await lock.close()
        await lock.close()


@pytest.mark.asyncio
class TestDistributedLockSingleton:
    """Test the module-level singleton."""

    async def test_get_distributed_lock_returns_same_instance(self):
        """get_distributed_lock() returns the same object."""
        from backend.services.distributed_lock import get_distributed_lock

        a = get_distributed_lock()
        b = get_distributed_lock()
        assert a is b
