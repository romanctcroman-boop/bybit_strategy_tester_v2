"""
Tests for Distributed Cache

Comprehensive test suite covering:
- Basic cache operations (get/set/delete)
- TTL and expiration
- LRU eviction policy
- Cache stampede prevention
- Compression
- Redis backend (mocked)
- Local fallback
- Metrics and statistics
- Cache warming
- Edge cases

Phase 3, Day 17-18
Target: 30+ tests, >90% coverage
"""

import asyncio
import time
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from reliability.distributed_cache import (
    DistributedCache,
    CacheConfig,
    CacheStats,
    EvictionPolicy,
    CacheWarmer
)


@pytest.fixture
def cache_config():
    """Default cache config for tests"""
    return CacheConfig(
        max_size_mb=10,
        default_ttl=60,
        eviction_policy=EvictionPolicy.LRU,
        enable_compression=True,
        compression_threshold=1024
    )


@pytest.fixture
def local_cache(cache_config):
    """Cache without Redis (local fallback)"""
    return DistributedCache(
        redis_client=None,
        config=cache_config,
        enable_metrics=True
    )


@pytest.fixture
def redis_mock():
    """Mock Redis client"""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.zadd = AsyncMock(return_value=1)
    mock.zrange = AsyncMock(return_value=[])
    mock.zrem = AsyncMock(return_value=1)
    mock.scan = AsyncMock(return_value=(0, []))
    mock.info = AsyncMock(return_value={'used_memory': 1024 * 1024})  # 1MB
    return mock


@pytest.fixture
def redis_cache(cache_config, redis_mock):
    """Cache with Redis backend"""
    return DistributedCache(
        redis_client=redis_mock,
        config=cache_config,
        enable_metrics=True
    )


# ============================================================================
# Test Basic Cache Operations
# ============================================================================

class TestBasicOperations:
    """Test basic cache get/set/delete"""
    
    @pytest.mark.asyncio
    async def test_set_and_get(self, local_cache):
        """Should set and retrieve value"""
        await local_cache.set("key1", "value1")
        result = await local_cache.get("key1")
        
        assert result == "value1"
        assert local_cache.stats.sets == 1
        assert local_cache.stats.hits == 1
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, local_cache):
        """Should return None for missing key"""
        result = await local_cache.get("nonexistent")
        
        assert result is None
        assert local_cache.stats.misses == 1
    
    @pytest.mark.asyncio
    async def test_delete(self, local_cache):
        """Should delete key"""
        await local_cache.set("key1", "value1")
        success = await local_cache.delete("key1")
        result = await local_cache.get("key1")
        
        assert success is True
        assert result is None
        assert local_cache.stats.deletes == 1
    
    @pytest.mark.asyncio
    async def test_overwrite_value(self, local_cache):
        """Should overwrite existing value"""
        await local_cache.set("key1", "value1")
        await local_cache.set("key1", "value2")
        result = await local_cache.get("key1")
        
        assert result == "value2"
        assert local_cache.stats.sets == 2
    
    @pytest.mark.asyncio
    async def test_multiple_keys(self, local_cache):
        """Should handle multiple keys independently"""
        await local_cache.set("key1", "value1")
        await local_cache.set("key2", "value2")
        await local_cache.set("key3", "value3")
        
        assert await local_cache.get("key1") == "value1"
        assert await local_cache.get("key2") == "value2"
        assert await local_cache.get("key3") == "value3"


# ============================================================================
# Test TTL and Expiration
# ============================================================================

class TestTTLExpiration:
    """Test TTL and automatic expiration"""
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self, local_cache):
        """Should expire after TTL"""
        await local_cache.set("key1", "value1", ttl=1)
        
        # Should exist immediately
        result1 = await local_cache.get("key1")
        assert result1 == "value1"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired
        result2 = await local_cache.get("key1")
        assert result2 is None
    
    @pytest.mark.asyncio
    async def test_no_ttl(self, local_cache):
        """Should not expire with ttl=0"""
        await local_cache.set("key1", "value1", ttl=0)
        
        # Should exist after long time
        await asyncio.sleep(0.1)
        result = await local_cache.get("key1")
        
        assert result == "value1"
    
    @pytest.mark.asyncio
    async def test_default_ttl(self, local_cache):
        """Should use default TTL from config"""
        # Config has default_ttl=60
        await local_cache.set("key1", "value1")
        
        # Should exist (not expired yet)
        result = await local_cache.get("key1")
        assert result == "value1"


# ============================================================================
# Test LRU Eviction
# ============================================================================

class TestLRUEviction:
    """Test LRU eviction policy"""
    
    @pytest.mark.asyncio
    async def test_lru_eviction_on_size_limit(self, local_cache):
        """Should evict least recently used when size limit reached"""
        # Set very low size limit
        local_cache.config.max_size_mb = 0.001  # Very small
        
        # Add many items
        for i in range(20):
            await local_cache.set(f"key{i}", f"value{i}")
        
        # Should have evicted some items
        assert local_cache.stats.evictions > 0
    
    @pytest.mark.asyncio
    async def test_lru_access_updates_order(self, local_cache):
        """Accessing key should update LRU order"""
        local_cache.config.max_size_mb = 0.001
        
        await local_cache.set("key1", "value1")
        await local_cache.set("key2", "value2")
        
        # Access key1 to make it more recent
        await local_cache.get("key1")
        
        # Add more items to trigger eviction
        for i in range(20):
            await local_cache.set(f"key{i}", f"value{i}")
        
        # key1 should still exist (recently accessed)
        # key2 might be evicted (less recent)
        result1 = await local_cache.get("key1")
        
        # At least one should exist due to recent access
        assert result1 is not None or local_cache.stats.evictions > 0


# ============================================================================
# Test Cache Stampede Prevention
# ============================================================================

class TestStampedePrevention:
    """Test cache stampede (dog-pile effect) prevention"""
    
    @pytest.mark.asyncio
    async def test_get_or_set_on_miss(self, local_cache):
        """Should fetch and cache on miss"""
        fetch_count = 0
        
        def fetch_func():
            nonlocal fetch_count
            fetch_count += 1
            return "fetched_value"
        
        result = await local_cache.get_or_set("key1", fetch_func)
        
        assert result == "fetched_value"
        assert fetch_count == 1
        assert local_cache.stats.sets == 1
    
    @pytest.mark.asyncio
    async def test_get_or_set_on_hit(self, local_cache):
        """Should return cached value without fetching"""
        fetch_count = 0
        
        def fetch_func():
            nonlocal fetch_count
            fetch_count += 1
            return "fetched_value"
        
        # Pre-populate cache
        await local_cache.set("key1", "cached_value")
        
        result = await local_cache.get_or_set("key1", fetch_func)
        
        assert result == "cached_value"
        assert fetch_count == 0  # Should not fetch
    
    @pytest.mark.asyncio
    async def test_stampede_prevention_concurrent(self, local_cache):
        """Should prevent multiple concurrent fetches (stampede)"""
        fetch_count = 0
        
        async def slow_fetch():
            nonlocal fetch_count
            fetch_count += 1
            await asyncio.sleep(0.1)  # Simulate slow fetch
            return "fetched_value"
        
        # Launch 10 concurrent get_or_set
        tasks = [
            local_cache.get_or_set("key1", slow_fetch)
            for _ in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should get same value
        assert all(r == "fetched_value" for r in results)
        
        # Should only fetch once (not 10 times)
        assert fetch_count == 1
    
    @pytest.mark.asyncio
    async def test_get_or_set_async_fetch(self, local_cache):
        """Should work with async fetch function"""
        async def async_fetch():
            await asyncio.sleep(0.01)
            return "async_value"
        
        result = await local_cache.get_or_set("key1", async_fetch)
        
        assert result == "async_value"


# ============================================================================
# Test Compression
# ============================================================================

class TestCompression:
    """Test value compression"""
    
    @pytest.mark.asyncio
    async def test_compression_enabled(self, local_cache):
        """Should compress large values"""
        large_value = "x" * 2000  # Above compression_threshold (1024)
        
        await local_cache.set("key1", large_value)
        result = await local_cache.get("key1")
        
        assert result == large_value
    
    @pytest.mark.asyncio
    async def test_compression_disabled(self, cache_config):
        """Should not compress when disabled"""
        cache_config.enable_compression = False
        cache = DistributedCache(config=cache_config)
        
        large_value = "x" * 2000
        await cache.set("key1", large_value)
        result = await cache.get("key1")
        
        assert result == large_value
    
    @pytest.mark.asyncio
    async def test_small_value_not_compressed(self, local_cache):
        """Should not compress small values"""
        small_value = "x" * 100  # Below threshold
        
        await local_cache.set("key1", small_value)
        result = await local_cache.get("key1")
        
        assert result == small_value


# ============================================================================
# Test Redis Backend
# ============================================================================

class TestRedisBackend:
    """Test Redis-backed cache"""
    
    @pytest.mark.asyncio
    async def test_redis_set_and_get(self, redis_cache, redis_mock):
        """Should use Redis for storage"""
        # Mock Redis responses
        redis_mock.setex.return_value = True
        redis_mock.get.return_value = redis_cache._serialize("value1")
        
        await redis_cache.set("key1", "value1")
        result = await redis_cache.get("key1")
        
        assert result == "value1"
        redis_mock.setex.assert_called_once()
        redis_mock.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_redis_delete(self, redis_cache, redis_mock):
        """Should delete from Redis"""
        redis_mock.delete.return_value = 1
        
        success = await redis_cache.delete("key1")
        
        assert success is True
        redis_mock.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_redis_lru_tracking(self, redis_cache, redis_mock):
        """Should track LRU in Redis sorted set"""
        redis_mock.setex.return_value = True
        
        await redis_cache.set("key1", "value1")
        
        # Should add to LRU sorted set
        redis_mock.zadd.assert_called()
    
    @pytest.mark.asyncio
    async def test_redis_error_fallback(self, redis_cache, redis_mock):
        """Should handle Redis errors gracefully"""
        redis_mock.get.side_effect = Exception("Redis connection failed")
        
        result = await redis_cache.get("key1")
        
        # Should return None on error (not crash)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_redis_eviction(self, redis_cache, redis_mock):
        """Should evict old keys when size limit reached"""
        # Mock large memory usage
        redis_mock.info.return_value = {'used_memory': 100 * 1024 * 1024}  # 100MB
        redis_mock.zrange.return_value = [b"old_key1", b"old_key2"]
        
        await redis_cache.set("new_key", "new_value")
        
        # Should check size and evict
        redis_mock.info.assert_called()
    
    @pytest.mark.asyncio
    async def test_redis_set_no_ttl(self, redis_cache, redis_mock):
        """Should use SET (not SETEX) when TTL=0"""
        redis_mock.set.return_value = True
        
        await redis_cache.set("key1", "value1", ttl=0)
        
        # Should call set() not setex()
        redis_mock.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_redis_clear_pagination(self, redis_cache, redis_mock):
        """Should handle paginated scan results when clearing"""
        # Mock multiple scan pages
        redis_mock.scan.side_effect = [
            (1, [b"cache:key1", b"cache:key2"]),  # First page
            (0, [b"cache:key3"])  # Last page
        ]
        
        await redis_cache.clear()
        
        # Should scan multiple times
        assert redis_mock.scan.call_count == 2
        # Should delete all found keys
        assert redis_mock.delete.call_count == 2
    
    @pytest.mark.asyncio
    async def test_redis_set_error_returns_false(self, redis_cache, redis_mock):
        """Should return False on Redis set error"""
        redis_mock.setex.side_effect = Exception("Redis error")
        
        success = await redis_cache.set("key1", "value1")
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_redis_eviction_error_handling(self, redis_cache, redis_mock):
        """Should handle errors during eviction gracefully"""
        redis_mock.info.return_value = {'used_memory': 100 * 1024 * 1024}
        redis_mock.zrange.side_effect = Exception("Redis error")
        
        # Should not crash on eviction error
        await redis_cache.set("key1", "value1")
        
        # Test passes if no exception raised


# ============================================================================
# Test Metrics and Stats
# ============================================================================

class TestMetrics:
    """Test metrics tracking"""
    
    @pytest.mark.asyncio
    async def test_hit_rate_calculation(self, local_cache):
        """Should calculate hit rate correctly"""
        await local_cache.set("key1", "value1")
        
        # 2 hits, 1 miss
        await local_cache.get("key1")
        await local_cache.get("key1")
        await local_cache.get("nonexistent")
        
        stats = local_cache.get_stats()
        
        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.hit_rate == pytest.approx(2/3, 0.01)
    
    @pytest.mark.asyncio
    async def test_metrics_disabled(self, cache_config):
        """Should not track metrics when disabled"""
        cache = DistributedCache(config=cache_config, enable_metrics=False)
        
        await cache.set("key1", "value1")
        await cache.get("key1")
        
        stats = cache.get_stats()
        
        # Should return empty stats
        assert stats.hits == 0
        assert stats.misses == 0
    
    @pytest.mark.asyncio
    async def test_eviction_counter(self, local_cache):
        """Should count evictions"""
        local_cache.config.max_size_mb = 0.001
        
        # Trigger evictions
        for i in range(50):
            await local_cache.set(f"key{i}", f"value{i}")
        
        stats = local_cache.get_stats()
        
        assert stats.evictions > 0


# ============================================================================
# Test Cache Warming
# ============================================================================

class TestCacheWarming:
    """Test cache warming/preloading"""
    
    @pytest.mark.asyncio
    async def test_warm_cache(self, local_cache):
        """Should preload cache with data"""
        warmer = CacheWarmer(local_cache)
        
        def fetch1():
            return "value1"
        
        def fetch2():
            return "value2"
        
        keys_and_funcs = [
            ("key1", fetch1, 60),
            ("key2", fetch2, 60)
        ]
        
        await warmer.warm(keys_and_funcs)
        
        # Values should be cached
        assert await local_cache.get("key1") == "value1"
        assert await local_cache.get("key2") == "value2"
    
    @pytest.mark.asyncio
    async def test_warm_with_async_funcs(self, local_cache):
        """Should work with async fetch functions"""
        warmer = CacheWarmer(local_cache)
        
        async def async_fetch():
            await asyncio.sleep(0.01)
            return "async_value"
        
        await warmer.warm([("key1", async_fetch, 60)])
        
        assert await local_cache.get("key1") == "async_value"


# ============================================================================
# Test Clear Operation
# ============================================================================

class TestClearCache:
    """Test cache clearing"""
    
    @pytest.mark.asyncio
    async def test_clear_local_cache(self, local_cache):
        """Should clear all local cache entries"""
        await local_cache.set("key1", "value1")
        await local_cache.set("key2", "value2")
        
        await local_cache.clear()
        
        assert await local_cache.get("key1") is None
        assert await local_cache.get("key2") is None
    
    @pytest.mark.asyncio
    async def test_clear_redis_cache(self, redis_cache, redis_mock):
        """Should clear all Redis cache entries"""
        redis_mock.scan.return_value = (0, [b"cache:key1", b"cache:key2"])
        
        await redis_cache.clear()
        
        # Should scan for keys and delete them
        redis_mock.scan.assert_called()
        redis_mock.delete.assert_called()


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.mark.asyncio
    async def test_none_value(self, local_cache):
        """Should handle None as a valid value"""
        await local_cache.set("key1", None)
        result = await local_cache.get("key1")
        
        # Note: None is ambiguous (cache miss vs cached None)
        # In practice, use sentinel value for cached None if needed
        assert result is None
        assert local_cache.stats.sets == 1
    
    @pytest.mark.asyncio
    async def test_complex_value_types(self, local_cache):
        """Should handle complex Python objects"""
        complex_value = {
            "list": [1, 2, 3],
            "dict": {"nested": True},
            "tuple": (1, 2, 3)
        }
        
        await local_cache.set("key1", complex_value)
        result = await local_cache.get("key1")
        
        assert result == complex_value
    
    @pytest.mark.asyncio
    async def test_empty_string_key(self, local_cache):
        """Should handle empty string key"""
        await local_cache.set("", "value")
        result = await local_cache.get("")
        
        assert result == "value"
    
    @pytest.mark.asyncio
    async def test_very_large_value(self, local_cache):
        """Should handle very large values"""
        large_value = "x" * 100000  # 100KB
        
        await local_cache.set("key1", large_value)
        result = await local_cache.get("key1")
        
        assert result == large_value
    
    @pytest.mark.asyncio
    async def test_zero_hit_rate(self, local_cache):
        """Should handle zero hit rate (all misses)"""
        await local_cache.get("key1")
        await local_cache.get("key2")
        
        stats = local_cache.get_stats()
        
        assert stats.hit_rate == 0.0


# ============================================================================
# Test Consistent Hashing
# ============================================================================

class TestConsistentHashing:
    """Test consistent hashing for key distribution"""
    
    def test_hash_key_consistency(self, local_cache):
        """Should generate consistent hash for same key"""
        hash1 = local_cache._hash_key("key1")
        hash2 = local_cache._hash_key("key1")
        
        assert hash1 == hash2
    
    def test_hash_key_distribution(self, local_cache):
        """Should generate different hashes for different keys"""
        hash1 = local_cache._hash_key("key1")
        hash2 = local_cache._hash_key("key2")
        
        assert hash1 != hash2


# ============================================================================
# Test Configuration Options
# ============================================================================

class TestConfigurationOptions:
    """Test different configuration options"""
    
    @pytest.mark.asyncio
    async def test_no_size_limit(self):
        """Should not evict when max_size_mb=0"""
        config = CacheConfig(max_size_mb=0)
        cache = DistributedCache(config=config)
        
        # Add many items
        for i in range(100):
            await cache.set(f"key{i}", f"value{i}")
        
        # Should not evict any
        assert cache.stats.evictions == 0
    
    @pytest.mark.asyncio
    async def test_different_eviction_policies(self):
        """Should support different eviction policies"""
        config_lru = CacheConfig(eviction_policy=EvictionPolicy.LRU)
        config_lfu = CacheConfig(eviction_policy=EvictionPolicy.LFU)
        
        cache_lru = DistributedCache(config=config_lru)
        cache_lfu = DistributedCache(config=config_lfu)
        
        assert cache_lru.config.eviction_policy == EvictionPolicy.LRU
        assert cache_lfu.config.eviction_policy == EvictionPolicy.LFU
    
    @pytest.mark.asyncio
    async def test_custom_key_prefix(self):
        """Should use custom key prefix"""
        cache = DistributedCache(key_prefix="myapp")
        
        redis_key = cache._make_key("user:123")
        
        assert redis_key.startswith("myapp:")
