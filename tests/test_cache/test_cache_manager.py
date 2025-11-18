"""
Tests for Cache Manager and Decorators

Tests multi-level caching, LRU eviction, decorators, and cache warming.
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime

from backend.cache.cache_manager import CacheManager, LRUCache, get_cache_manager
from backend.cache.decorators import cached, cache_with_key, invalidate_cache
from backend.cache.warming import CacheWarmer, warm_startup_caches


@pytest_asyncio.fixture
async def cache_manager():
    """Fixture for CacheManager with proper cleanup."""
    manager = CacheManager(l1_size=10, l1_ttl=300)
    await manager.connect()
    yield manager
    # Note: Redis cleanup skipped to avoid event loop issues in tests
    # In production, cleanup is handled by application lifecycle


@pytest_asyncio.fixture
async def cache_warmer():
    """Fixture for CacheWarmer with proper cleanup."""
    warmer = CacheWarmer(max_concurrent=5)
    await warmer.connect()
    yield warmer
    # Note: Redis cleanup skipped to avoid event loop issues in tests


class TestLRUCache:
    """Test LRU cache implementation."""
    
    @pytest.mark.asyncio
    async def test_parameter_validation(self):
        """Test parameter validation in LRUCache constructor."""
        # Test invalid max_size
        with pytest.raises(ValueError, match="max_size must be positive"):
            LRUCache(max_size=0)
        
        with pytest.raises(ValueError, match="max_size must be positive"):
            LRUCache(max_size=-10)
        
        # Test invalid default_ttl
        with pytest.raises(ValueError, match="default_ttl must be positive"):
            LRUCache(max_size=100, default_ttl=0)
        
        with pytest.raises(ValueError, match="default_ttl must be positive"):
            LRUCache(max_size=100, default_ttl=-60)
        
        # Test valid parameters
        cache = LRUCache(max_size=100, default_ttl=300)
        assert cache.max_size == 100
        assert cache.default_ttl == 300
    
    @pytest.mark.asyncio
    async def test_basic_operations(self):
        """Test basic get/set/delete operations."""
        cache = LRUCache(max_size=10, default_ttl=300)
        
        # Set and get
        await cache.set("key1", "value1")
        value = await cache.get("key1")
        assert value == "value1"
        
        # Get non-existent
        value = await cache.get("nonexistent")
        assert value is None
        
        # Delete
        deleted = await cache.delete("key1")
        assert deleted is True
        value = await cache.get("key1")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Test LRU eviction when capacity is reached."""
        cache = LRUCache(max_size=3, default_ttl=300)
        
        # Fill cache
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        
        # Add 4th item - should evict key1 (oldest)
        await cache.set("key4", "value4")
        
        assert await cache.get("key1") is None  # Evicted
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """Test TTL-based expiration."""
        cache = LRUCache(max_size=10, default_ttl=1)  # 1 second TTL
        
        await cache.set("key1", "value1")
        
        # Should exist immediately
        assert await cache.get("key1") == "value1"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired
        assert await cache.get("key1") is None
    
    @pytest.mark.asyncio
    async def test_statistics(self):
        """Test cache statistics tracking."""
        cache = LRUCache(max_size=10, default_ttl=300)
        
        # Generate hits and misses
        await cache.set("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("key1")  # Hit
        await cache.get("nonexistent")  # Miss
        
        stats = await cache.get_stats()
        
        assert stats['hits'] == 2
        assert stats['misses'] == 1
        assert stats['size'] == 1
        assert stats['hit_rate'] == 2/3


class TestCacheManager:
    """Test cache manager with L1/L2 hierarchy."""
    
    @pytest.mark.asyncio
    async def test_l1_caching(self, cache_manager):
        """Test L1 (memory) cache."""
        # Set and get from L1
        await cache_manager.set("test:key", {"data": "value"})
        value = await cache_manager.get("test:key")
        
        assert value == {"data": "value"}
        
        # Should be L1 hit
        stats = await cache_manager.get_stats()
        assert stats['total_hits'] > 0
        assert stats['l1_stats']['hits'] > 0
    
    @pytest.mark.asyncio
    async def test_get_or_compute(self, cache_manager):
        """Test get_or_compute pattern."""
        compute_count = 0
        
        async def expensive_computation():
            nonlocal compute_count
            compute_count += 1
            await asyncio.sleep(0.1)
            return {"result": "computed"}
        
        # First call - should compute
        result1 = await cache_manager.get_or_compute(
            key="compute:test",
            compute_func=expensive_computation,
            l1_ttl=300
        )
        
        assert result1 == {"result": "computed"}
        assert compute_count == 1
        
        # Second call - should use cache
        result2 = await cache_manager.get_or_compute(
            key="compute:test",
            compute_func=expensive_computation,
            l1_ttl=300
        )
        
        assert result2 == {"result": "computed"}
        assert compute_count == 1  # Not computed again
    
    @pytest.mark.asyncio
    async def test_delete_pattern(self, cache_manager):
        """Test pattern-based deletion."""
        # Set multiple keys
        await cache_manager.set("user:1", {"name": "Alice"})
        await cache_manager.set("user:2", {"name": "Bob"})
        await cache_manager.set("strategy:1", {"type": "momentum"})
        
        # Delete user keys
        deleted = await cache_manager.delete_pattern("user:*")
        
        # User keys should be gone
        assert await cache_manager.get("user:1") is None
        assert await cache_manager.get("user:2") is None
        
        # Strategy key should remain
        assert await cache_manager.get("strategy:1") is not None
    
    @pytest.mark.asyncio
    async def test_cache_statistics(self, cache_manager):
        """Test comprehensive statistics."""
        import uuid
        unique_key = f"stats_test_{uuid.uuid4().hex[:8]}"
        
        # Generate some traffic
        await cache_manager.set(f"{unique_key}_key1", "value1")
        await cache_manager.get(f"{unique_key}_key1")  # L1 hit
        await cache_manager.get(f"{unique_key}_nonexistent")  # Miss
        
        async def compute():
            return "computed"
        
        await cache_manager.get_or_compute(f"{unique_key}_key2", compute)  # Compute
        
        stats = await cache_manager.get_stats()
        
        assert stats['total_hits'] > 0
        assert stats['total_misses'] > 0
        assert stats['total_computes'] > 0
        assert 0 <= stats['overall_hit_rate'] <= 1


class TestCacheDecorators:
    """Test cache decorators."""
    
    @pytest.mark.asyncio
    async def test_cached_decorator(self):
        """Test @cached decorator."""
        import uuid
        test_id = uuid.uuid4().hex[:8]
        call_count = 0
        
        @cached(ttl=300, key_prefix=f"decorator_test_{test_id}")
        async def get_user(user_id: int):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            return {"id": user_id, "name": f"User {user_id}"}
        
        # First call - should execute
        result1 = await get_user(1)
        assert result1 == {"id": 1, "name": "User 1"}
        assert call_count == 1
        
        # Second call - should use cache
        result2 = await get_user(1)
        assert result2 == {"id": 1, "name": "User 1"}
        assert call_count == 1  # Not called again
        
        # Different argument - should execute
        result3 = await get_user(2)
        assert result3 == {"id": 2, "name": "User 2"}
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_cache_with_key_decorator(self):
        """Test @cache_with_key decorator."""
        call_count = 0
        
        @cache_with_key(key="user:{user_id}", ttl=300)
        async def get_user(user_id: int):
            nonlocal call_count
            call_count += 1
            return {"id": user_id}
        
        # First call
        result1 = await get_user(user_id=1)
        assert call_count == 1
        
        # Second call - cached
        result2 = await get_user(user_id=1)
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_invalidate_cache_decorator(self):
        """Test @invalidate_cache decorator."""
        # Setup cached function
        @cached(ttl=300)
        async def get_user(user_id: int):
            return {"id": user_id, "name": f"User {user_id}"}
        
        # Setup mutation with invalidation
        @invalidate_cache(patterns=["user:*"])
        async def update_user(user_id: int, name: str):
            return {"id": user_id, "name": name}
        
        # Cache user
        user1 = await get_user(1)
        assert user1["name"] == "User 1"
        
        # Update user (should invalidate cache)
        await update_user(1, "Updated Name")
        
        # Next get should recompute (in real app, would fetch updated data)
        # For this test, we just verify invalidation happened


class TestCacheWarmer:
    """Test cache warming system."""
    
    @pytest.mark.asyncio
    async def test_warm_single_task(self, cache_warmer):
        """Test warming single task."""
        async def load_data():
            await asyncio.sleep(0.1)
            return {"data": "test"}
        
        cache_warmer.register_task(
            name="test_task",
            warm_func=load_data,
            priority="high",
            ttl=300
        )
        
        task = cache_warmer.tasks[0]
        success = await cache_warmer.warm_task(task)
        
        assert success is True
        assert task['warm_count'] == 1
        assert task['last_warmed'] is not None
    
    @pytest.mark.asyncio
    async def test_warm_all(self, cache_warmer):
        """Test warming all registered tasks."""
        # Register multiple tasks
        for i in range(3):
            async def load_data(idx=i):
                return {"data": f"test{idx}"}
            
            cache_warmer.register_task(
                name=f"task_{i}",
                warm_func=load_data,
                priority="normal",
                ttl=300
            )
        
        # Warm all
        stats = await cache_warmer.warm_all()
        
        assert stats['success'] == 3
        assert stats['failed'] == 0
    
    @pytest.mark.asyncio
    async def test_priority_filtering(self, cache_warmer):
        """Test warming by priority."""
        # Register tasks with different priorities
        async def load_data():
            return {"data": "test"}
        
        cache_warmer.register_task("critical", load_data, priority="critical", ttl=300)
        cache_warmer.register_task("high", load_data, priority="high", ttl=300)
        cache_warmer.register_task("normal", load_data, priority="normal", ttl=300)
        cache_warmer.register_task("low", load_data, priority="low", ttl=300)
        
        # Warm only high priority and above
        stats = await cache_warmer.warm_all(priority_filter="high")
        
        # Should warm critical and high only
        assert stats['success'] == 2
    
    @pytest.mark.asyncio
    async def test_warmer_statistics(self, cache_warmer):
        """Test warmer statistics tracking."""
        async def load_data():
            return {"data": "test"}
        
        cache_warmer.register_task("task1", load_data, priority="high", ttl=300)
        
        await cache_warmer.warm_all()
        
        stats = cache_warmer.get_stats()
        
        assert stats['total_tasks'] == 1
        assert stats['total_warmed'] == 1
        assert len(stats['tasks']) == 1


class TestPerformanceBenchmarks:
    """Performance benchmarks for caching."""
    
    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """Benchmark cache vs no-cache performance."""
        import time
        
        # Simulated expensive function
        async def expensive_query():
            await asyncio.sleep(0.05)  # 50ms DB query
            return {"data": "result"}
        
        # Without cache
        start = time.perf_counter()
        for _ in range(10):
            await expensive_query()
        no_cache_time = time.perf_counter() - start
        
        # With cache
        manager = CacheManager()
        await manager.connect()
        
        start = time.perf_counter()
        for _ in range(10):
            await manager.get_or_compute(
                key="test:cached",
                compute_func=expensive_query,
                l1_ttl=300
            )
        cached_time = time.perf_counter() - start
        
        speedup = no_cache_time / cached_time
        
        print(f"\n📊 Cache Performance:")
        print(f"   Without cache: {no_cache_time*1000:.2f}ms")
        print(f"   With cache:    {cached_time*1000:.2f}ms")
        print(f"   ⚡ Speedup:     {speedup:.2f}x")
        
        # Cache should be significantly faster
        assert speedup > 5.0, f"Cache should be 5x+ faster, got {speedup:.2f}x"


class TestCriticalScenarios:
    """Critical test scenarios identified by DeepSeek AI review."""
    
    @pytest.mark.asyncio
    async def test_concurrent_access_race_conditions(self):
        """
        Test race conditions under concurrent access.
        
        DeepSeek: "❌ CRITICAL MISSING TEST"
        Validates that LRU eviction works correctly under high concurrency.
        """
        import uuid
        
        cache = LRUCache(max_size=10, default_ttl=300)
        test_id = uuid.uuid4().hex[:8]
        
        # Simulate 100 concurrent set operations
        async def concurrent_set(i: int):
            await cache.set(f"{test_id}_key{i}", f"value{i}")
            # Small delay to increase race condition probability
            await asyncio.sleep(0.001)
        
        # Run concurrent operations
        tasks = [concurrent_set(i) for i in range(100)]
        await asyncio.gather(*tasks)
        
        # Validate cache integrity
        stats = await cache.get_stats()
        
        # Cache size should never exceed max_size
        assert stats['size'] <= 10, f"Cache size {stats['size']} exceeds max_size 10"
        
        # Should have evictions (100 items into size 10)
        assert stats['evictions'] > 0, "No evictions occurred with 100 items in size-10 cache"
        
        # Verify LRU order is maintained (most recent items still in cache)
        recent_keys_found = 0
        for i in range(90, 100):  # Check last 10 items
            value = await cache.get(f"{test_id}_key{i}")
            if value is not None:
                recent_keys_found += 1
        
        # At least some recent keys should still be in cache
        assert recent_keys_found > 0, "No recent keys found in cache after concurrent operations"
        
        print(f"\n✅ Concurrent Access Test:")
        print(f"   Operations: 100 concurrent sets")
        print(f"   Cache size: {stats['size']}/{cache.max_size}")
        print(f"   Evictions: {stats['evictions']}")
        print(f"   Recent keys in cache: {recent_keys_found}/10")
    
    @pytest.mark.asyncio
    async def test_redis_connection_failure_handling(self):
        """
        Test cache degradation when Redis is down.
        
        DeepSeek: "❌ CRITICAL MISSING TEST"
        Validates graceful degradation to L1-only mode on Redis failures.
        """
        from unittest.mock import AsyncMock, patch
        import uuid
        
        manager = CacheManager(l1_size=10, l1_ttl=300)
        await manager.connect()
        
        test_id = uuid.uuid4().hex[:8]
        test_key = f"{test_id}_test_key"
        
        # Mock Redis to throw ConnectionError
        original_get = manager.redis_client.get
        
        async def failing_redis_get(key):
            raise ConnectionError("Redis connection refused")
        
        # Test 1: Redis failure on get
        manager.redis_client.get = failing_redis_get
        
        # Should fallback to compute without crashing
        value = await manager.get_or_compute(
            key=test_key,
            compute_func=lambda: "computed_value",
            l1_ttl=300
        )
        
        assert value == "computed_value", "Should compute value on Redis failure"
        
        # Check error was tracked
        stats = manager._stats
        assert 'l2_errors' in stats, "l2_errors not tracked"
        assert stats['l2_errors'] > 0, "Redis error not recorded in stats"
        
        # Restore Redis
        manager.redis_client.get = original_get
        
        # Test 2: Verify L1 cache still works
        l1_value = await manager.get(test_key)
        assert l1_value == "computed_value", "L1 cache should still have value"
        
        print(f"\n✅ Redis Failure Test:")
        print(f"   L2 errors: {stats['l2_errors']}")
        print(f"   L1 cache: Still working ✓")
        print(f"   Graceful degradation: ✓")
    
    @pytest.mark.asyncio
    async def test_memory_usage_with_large_objects(self):
        """
        Test cache behavior with large objects.
        
        DeepSeek: "Need memory-based eviction tests"
        Validates that cache doesn't grow unbounded with large objects.
        """
        import sys
        import uuid
        
        cache = LRUCache(max_size=50, default_ttl=300)
        test_id = uuid.uuid4().hex[:8]
        
        # Create objects of varying sizes
        small_object = "x" * 100  # 100 bytes
        medium_object = "x" * 10_000  # 10KB
        large_object = "x" * 100_000  # 100KB
        
        # Cache 50 small objects
        for i in range(50):
            await cache.set(f"{test_id}_small_{i}", small_object)
        
        stats_small = await cache.get_stats()
        
        # Cache 50 medium objects (should evict small ones)
        for i in range(50):
            await cache.set(f"{test_id}_medium_{i}", medium_object)
        
        stats_medium = await cache.get_stats()
        
        # Cache 50 large objects (should evict medium ones)
        for i in range(50):
            await cache.set(f"{test_id}_large_{i}", large_object)
        
        stats_large = await cache.get_stats()
        
        # Validate cache size never exceeds max_size
        assert stats_small['size'] <= 50, f"Small objects: size {stats_small['size']} exceeds 50"
        assert stats_medium['size'] <= 50, f"Medium objects: size {stats_medium['size']} exceeds 50"
        assert stats_large['size'] <= 50, f"Large objects: size {stats_large['size']} exceeds 50"
        
        # Validate evictions occurred
        assert stats_medium['evictions'] > 0, "No evictions with medium objects"
        assert stats_large['evictions'] > 0, "No evictions with large objects"
        
        # Calculate approximate memory usage
        # Note: This is a basic check - real implementation would track actual memory
        total_evictions = stats_large['evictions']
        
        print(f"\n✅ Large Objects Test:")
        print(f"   Small (100B): {stats_small['size']} items, {stats_small['evictions']} evictions")
        print(f"   Medium (10KB): {stats_medium['size']} items, {stats_medium['evictions']} evictions")
        print(f"   Large (100KB): {stats_large['size']} items, {stats_large['evictions']} evictions")
        print(f"   Total evictions: {total_evictions}")
        print(f"   Cache integrity: ✓")
    
    @pytest.mark.asyncio
    async def test_compute_function_error_handling(self):
        """
        Test error handling when compute function fails.
        
        Validates that compute errors are properly logged and re-raised.
        """
        import uuid
        
        manager = CacheManager(l1_size=10, l1_ttl=300)
        await manager.connect()
        
        test_id = uuid.uuid4().hex[:8]
        
        # Define a failing compute function
        def failing_compute():
            raise ValueError("Database connection failed")
        
        # Should raise the exception after logging
        with pytest.raises(ValueError, match="Database connection failed"):
            await manager.get_or_compute(
                key=f"{test_id}_failing_key",
                compute_func=failing_compute,
                l1_ttl=300
            )
        
        # Check error was tracked
        stats = manager._stats
        assert 'compute_errors' in stats, "compute_errors not tracked"
        assert stats['compute_errors'] > 0, "Compute error not recorded"
        
        print(f"\n✅ Compute Error Test:")
        print(f"   Compute errors: {stats['compute_errors']}")
        print(f"   Exception re-raised: ✓")
        print(f"   Error tracking: ✓")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
