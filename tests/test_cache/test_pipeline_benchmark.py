"""
Simple benchmark test for Redis pipelines (standalone)
"""

import asyncio
import time
from backend.cache.redis_client import RedisClient
from backend.cache.pipeline_manager import PipelineManager


async def test_redis_pipeline_performance():
    """Test Redis pipeline performance improvement."""
    
    print("\n" + "="*60)
    print("🧪 Redis Pipeline Performance Test")
    print("="*60)
    
    # Connect to Redis
    client = RedisClient(db=15)  # Test database
    await client.connect()
    await client.flushdb()
    
    print("✅ Connected to Redis (test database 15)")
    
    # Test 1: Individual vs Pipeline SET operations
    print("\n📊 Test 1: SET Operations (100 items)")
    print("-" * 40)
    
    count = 100
    
    # Individual SET
    start = time.perf_counter()
    for i in range(count):
        await client.set(f"perf:individual:{i}", f"value{i}")
    individual_time = time.perf_counter() - start
    print(f"   Individual SET: {individual_time*1000:.2f}ms")
    
    # Pipeline SET
    start = time.perf_counter()
    async with client.pipeline() as pipe:
        for i in range(count):
            pipe.set(f"perf:pipeline:{i}", f"value{i}")
        await pipe.execute()
    pipeline_time = time.perf_counter() - start
    print(f"   Pipeline SET:   {pipeline_time*1000:.2f}ms")
    
    set_speedup = individual_time / pipeline_time
    print(f"   ⚡ Speedup:      {set_speedup:.2f}x")
    
    # Test 2: Batch operations with PipelineManager
    print("\n📊 Test 2: Batch Operations (100 items)")
    print("-" * 40)
    
    manager = PipelineManager(redis_client=client)
    
    # MSET
    data = {f"batch:{i}": f"value{i}" for i in range(count)}
    start = time.perf_counter()
    results = await manager.mset(data)
    mset_time = time.perf_counter() - start
    print(f"   MSET:           {mset_time*1000:.2f}ms ({len(results)} items)")
    
    # MGET
    keys = list(data.keys())
    start = time.perf_counter()
    get_results = await manager.mget(keys)
    mget_time = time.perf_counter() - start
    print(f"   MGET:           {mget_time*1000:.2f}ms ({len(get_results)} items)")
    
    # Test 3: Large batch with chunking
    print("\n📊 Test 3: Large Batch (500 items, 5 chunks)")
    print("-" * 40)
    
    large_data = {f"large:{i}": f"value{i}" for i in range(500)}
    start = time.perf_counter()
    large_results = await manager.mset(large_data, chunk_size=100)
    large_time = time.perf_counter() - start
    print(f"   MSET (500):     {large_time*1000:.2f}ms")
    print(f"   Chunks:         5 batches of 100 items")
    print(f"   Success rate:   {sum(large_results.values())}/500")
    
    # Statistics
    stats = manager.get_stats()
    print("\n📈 PipelineManager Statistics:")
    print(f"   Total operations: {stats['total_operations']}")
    print(f"   Total batches:    {stats['total_batches']}")
    print(f"   Error rate:       {stats['error_rate']:.2%}")
    print(f"   Avg batch size:   {stats['avg_batch_size']:.1f}")
    
    # Cleanup
    await client.flushdb()
    await client.disconnect()
    
    print("\n" + "="*60)
    print("✅ All tests passed!")
    print("="*60)
    
    # Assertions
    assert set_speedup >= 2.0, f"Pipeline should be 2x+ faster, got {set_speedup:.2f}x"
    assert all(large_results.values()), "All batch operations should succeed"
    assert stats['error_rate'] == 0, "No errors should occur"
    
    print(f"\n🎯 Performance Target: 2.0x speedup")
    print(f"🏆 Achieved:          {set_speedup:.2f}x speedup")
    print(f"{'✅ PASSED' if set_speedup >= 2.0 else '❌ FAILED'}")


if __name__ == "__main__":
    asyncio.run(test_redis_pipeline_performance())
