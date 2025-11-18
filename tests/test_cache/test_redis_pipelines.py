"""
Tests for Redis Pipeline Operations

Tests batch operations and performance improvements from pipelining.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List

from backend.cache.redis_client import RedisClient, get_redis_client
from backend.cache.pipeline_manager import PipelineManager, get_pipeline_manager


@pytest.fixture
async def redis_client():
    """Create Redis client for testing."""
    client = RedisClient(db=15)  # Use test database
    await client.connect()
    
    # Clear test database
    await client.flushdb()
    
    yield client
    
    # Cleanup
    await client.flushdb()
    await client.disconnect()


@pytest.fixture
async def pipeline_manager(redis_client):
    """Create pipeline manager for testing."""
    manager = PipelineManager(redis_client=redis_client)
    yield manager


class TestRedisClient:
    """Test Redis client basic operations."""
    
    @pytest.mark.asyncio
    async def test_connection(self, redis_client):
        """Test Redis connection."""
        assert redis_client._connected
        assert await redis_client.ping()
    
    @pytest.mark.asyncio
    async def test_set_get(self, redis_client):
        """Test basic SET/GET operations."""
        # Set value
        success = await redis_client.set("test:key", "test_value")
        assert success
        
        # Get value
        value = await redis_client.get("test:key")
        assert value == "test_value"
    
    @pytest.mark.asyncio
    async def test_set_with_expiration(self, redis_client):
        """Test SET with expiration."""
        # Set with 1 second TTL
        await redis_client.set("test:expire", "value", expire=1)
        
        # Verify exists
        assert await redis_client.get("test:expire") == "value"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Verify expired
        assert await redis_client.get("test:expire") is None
    
    @pytest.mark.asyncio
    async def test_delete(self, redis_client):
        """Test DELETE operation."""
        # Set values
        await redis_client.set("test:del1", "value1")
        await redis_client.set("test:del2", "value2")
        
        # Delete
        deleted = await redis_client.delete("test:del1", "test:del2")
        assert deleted == 2
        
        # Verify deleted
        assert await redis_client.get("test:del1") is None
        assert await redis_client.get("test:del2") is None
    
    @pytest.mark.asyncio
    async def test_exists(self, redis_client):
        """Test EXISTS operation."""
        await redis_client.set("test:exists", "value")
        
        # Check existence
        assert await redis_client.exists("test:exists") == 1
        assert await redis_client.exists("test:notexists") == 0
    
    @pytest.mark.asyncio
    async def test_ttl(self, redis_client):
        """Test TTL operation."""
        # Set with expiration
        await redis_client.set("test:ttl", "value", expire=3600)
        
        # Check TTL
        ttl = await redis_client.ttl("test:ttl")
        assert 3590 < ttl <= 3600  # Allow some time variance
    
    @pytest.mark.asyncio
    async def test_hash_operations(self, redis_client):
        """Test hash operations."""
        # HSET
        await redis_client.hset("test:hash", "field1", "value1")
        await redis_client.hset("test:hash", "field2", "value2")
        
        # HGET
        value = await redis_client.hget("test:hash", "field1")
        assert value == "value1"
        
        # HGETALL
        all_fields = await redis_client.hgetall("test:hash")
        assert all_fields == {"field1": "value1", "field2": "value2"}
        
        # HDEL
        deleted = await redis_client.hdel("test:hash", "field1")
        assert deleted == 1


class TestRedisPipeline:
    """Test Redis pipeline operations."""
    
    @pytest.mark.asyncio
    async def test_pipeline_basic(self, redis_client):
        """Test basic pipeline usage."""
        async with redis_client.pipeline() as pipe:
            pipe.set("pipe:1", "value1")
            pipe.set("pipe:2", "value2")
            pipe.get("pipe:1")
            
            results = await pipe.execute()
        
        # Verify results
        assert results[0] is not None  # SET result
        assert results[1] is not None  # SET result
        assert results[2] == "value1"  # GET result
    
    @pytest.mark.asyncio
    async def test_pipeline_performance(self, redis_client):
        """Test pipeline performance improvement."""
        import time
        
        # Individual operations
        start = time.perf_counter()
        for i in range(100):
            await redis_client.set(f"perf:individual:{i}", f"value{i}")
        individual_time = time.perf_counter() - start
        
        # Pipeline operations
        start = time.perf_counter()
        async with redis_client.pipeline() as pipe:
            for i in range(100):
                pipe.set(f"perf:pipeline:{i}", f"value{i}")
            await pipe.execute()
        pipeline_time = time.perf_counter() - start
        
        # Pipeline should be significantly faster (at least 2x)
        speedup = individual_time / pipeline_time
        print(f"\n⚡ Pipeline speedup: {speedup:.2f}x")
        assert speedup >= 2.0, f"Pipeline not fast enough: {speedup:.2f}x"


class TestPipelineManager:
    """Test Pipeline Manager batch operations."""
    
    @pytest.mark.asyncio
    async def test_mset(self, pipeline_manager):
        """Test batch SET operation."""
        data = {
            "batch:1": "value1",
            "batch:2": "value2",
            "batch:3": "value3",
        }
        
        results = await pipeline_manager.mset(data)
        
        # Verify all successful
        assert all(results.values())
        assert len(results) == 3
    
    @pytest.mark.asyncio
    async def test_mset_with_expiration(self, pipeline_manager):
        """Test batch SET with expiration."""
        data = {"expire:1": "value1", "expire:2": "value2"}
        
        await pipeline_manager.mset(data, expire=1)
        
        # Verify exists
        client = await get_redis_client()
        assert await client.get("expire:1") == "value1"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Verify expired
        assert await client.get("expire:1") is None
    
    @pytest.mark.asyncio
    async def test_mget(self, pipeline_manager):
        """Test batch GET operation."""
        # Setup data
        data = {"get:1": "value1", "get:2": "value2", "get:3": "value3"}
        await pipeline_manager.mset(data)
        
        # Batch get
        keys = ["get:1", "get:2", "get:3", "get:notexist"]
        results = await pipeline_manager.mget(keys)
        
        # Verify results
        assert results["get:1"] == "value1"
        assert results["get:2"] == "value2"
        assert results["get:3"] == "value3"
        assert results["get:notexist"] is None
    
    @pytest.mark.asyncio
    async def test_mdelete(self, pipeline_manager):
        """Test batch DELETE operation."""
        # Setup data
        data = {"del:1": "value1", "del:2": "value2", "del:3": "value3"}
        await pipeline_manager.mset(data)
        
        # Batch delete
        keys = ["del:1", "del:2", "del:3"]
        deleted = await pipeline_manager.mdelete(keys)
        
        # Verify deleted
        assert deleted == 3
        
        # Verify not exists
        results = await pipeline_manager.mget(keys)
        assert all(v is None for v in results.values())
    
    @pytest.mark.asyncio
    async def test_mexists(self, pipeline_manager):
        """Test batch EXISTS operation."""
        # Setup data
        data = {"exists:1": "value1", "exists:2": "value2"}
        await pipeline_manager.mset(data)
        
        # Batch exists check
        keys = ["exists:1", "exists:2", "exists:notexist"]
        results = await pipeline_manager.mexists(keys)
        
        # Verify results
        assert results["exists:1"] is True
        assert results["exists:2"] is True
        assert results["exists:notexist"] is False
    
    @pytest.mark.asyncio
    async def test_mexpire(self, pipeline_manager):
        """Test batch EXPIRE operation."""
        # Setup data
        data = {"ttl:1": "value1", "ttl:2": "value2"}
        await pipeline_manager.mset(data)
        
        # Batch set expiration
        keys = ["ttl:1", "ttl:2"]
        results = await pipeline_manager.mexpire(keys, seconds=3600)
        
        # Verify all successful
        assert all(results.values())
        
        # Verify TTL set
        client = await get_redis_client()
        ttl1 = await client.ttl("ttl:1")
        assert 3590 < ttl1 <= 3600
    
    @pytest.mark.asyncio
    async def test_large_batch(self, pipeline_manager):
        """Test large batch operation with chunking."""
        # Create 500 items (5 chunks of 100)
        data = {f"large:{i}": f"value{i}" for i in range(500)}
        
        # Batch set
        results = await pipeline_manager.mset(data, chunk_size=100)
        
        # Verify all successful
        assert len(results) == 500
        assert all(results.values())
        
        # Batch get
        keys = list(data.keys())
        get_results = await pipeline_manager.mget(keys, chunk_size=100)
        
        # Verify all retrieved
        assert len(get_results) == 500
        assert all(v is not None for v in get_results.values())
    
    @pytest.mark.asyncio
    async def test_statistics(self, pipeline_manager):
        """Test pipeline statistics tracking."""
        # Reset stats
        pipeline_manager.reset_stats()
        
        # Perform operations
        data = {f"stats:{i}": f"value{i}" for i in range(50)}
        await pipeline_manager.mset(data)
        await pipeline_manager.mget(list(data.keys()))
        
        # Check stats
        stats = pipeline_manager.get_stats()
        assert stats["total_operations"] == 100  # 50 set + 50 get
        assert stats["total_batches"] == 2  # 1 mset batch + 1 mget batch
        assert stats["error_rate"] == 0
        assert stats["last_operation"] is not None


class TestPerformanceBenchmarks:
    """Performance benchmarks for pipeline operations."""
    
    @pytest.mark.asyncio
    async def test_benchmark_mset_vs_individual(self, pipeline_manager, redis_client):
        """Benchmark MSET vs individual SET operations."""
        import time
        
        count = 100
        
        # Individual SET
        start = time.perf_counter()
        for i in range(count):
            await redis_client.set(f"bench:individual:{i}", f"value{i}")
        individual_time = time.perf_counter() - start
        
        # Batch MSET
        data = {f"bench:batch:{i}": f"value{i}" for i in range(count)}
        start = time.perf_counter()
        await pipeline_manager.mset(data)
        batch_time = time.perf_counter() - start
        
        # Calculate speedup
        speedup = individual_time / batch_time
        
        print(f"\n📊 MSET Performance Benchmark:")
        print(f"   Individual SET: {individual_time*1000:.2f}ms ({count} operations)")
        print(f"   Batch MSET: {batch_time*1000:.2f}ms ({count} operations)")
        print(f"   ⚡ Speedup: {speedup:.2f}x")
        
        # Assert significant improvement
        assert speedup >= 2.0, f"MSET should be 2x+ faster, got {speedup:.2f}x"
    
    @pytest.mark.asyncio
    async def test_benchmark_mget_vs_individual(self, pipeline_manager, redis_client):
        """Benchmark MGET vs individual GET operations."""
        import time
        
        count = 100
        
        # Setup data
        data = {f"bench:get:{i}": f"value{i}" for i in range(count)}
        await pipeline_manager.mset(data)
        
        keys = list(data.keys())
        
        # Individual GET
        start = time.perf_counter()
        for key in keys:
            await redis_client.get(key)
        individual_time = time.perf_counter() - start
        
        # Batch MGET
        start = time.perf_counter()
        await pipeline_manager.mget(keys)
        batch_time = time.perf_counter() - start
        
        # Calculate speedup
        speedup = individual_time / batch_time
        
        print(f"\n📊 MGET Performance Benchmark:")
        print(f"   Individual GET: {individual_time*1000:.2f}ms ({count} operations)")
        print(f"   Batch MGET: {batch_time*1000:.2f}ms ({count} operations)")
        print(f"   ⚡ Speedup: {speedup:.2f}x")
        
        # Assert significant improvement
        assert speedup >= 2.0, f"MGET should be 2x+ faster, got {speedup:.2f}x"
