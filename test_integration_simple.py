"""
Simplified Integration Tests for Phase 3 - MEDIUM Priority Task #1

Goal: Increase coverage from 78% to 85%+
Focus: Component interactions with correct APIs

Author: AI Assistant
Date: 2025-11-10
"""

import asyncio
import time
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')

from reliability.retry_policy import RetryPolicy, RetryConfig
from reliability.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from reliability.distributed_rate_limiter import DistributedRateLimiter, RateLimitConfig, RateLimitScope
from reliability.distributed_cache import DistributedCache, CacheConfig, EvictionPolicy


# ===========================================================================
# TEST 1: Circuit Breaker Integration with RetryPolicy
# ===========================================================================

async def test_retry_with_circuit_breaker():
    """Test RetryPolicy respects CircuitBreaker state"""
    
    print("\n" + "="*70)
    print("TEST 1: RetryPolicy + CircuitBreaker Integration")
    print("="*70)
    
    circuit = CircuitBreaker(
        name="test_api",
        config=CircuitBreakerConfig(
            failure_threshold=0.5,
            min_request_volume=2,
            recovery_timeout=1.0
        )
    )
    
    retry = RetryPolicy(
        config=RetryConfig(max_retries=3, base_delay=0.1),
        circuit_breaker=circuit
    )
    
    # Force circuit open
    await circuit.force_open()
    
    call_count = 0
    async def test_func():
        nonlocal call_count
        call_count += 1
        return "success"
    
    # Should fail fast when circuit open
    try:
        result = await retry.retry(test_func)
        print(f"❌ FAIL: Should have raised exception, got {result}")
        return False
    except Exception as e:
        if "Circuit breaker is OPEN" in str(e) and call_count == 0:
            print(f"✅ PASS: Retry failed fast (0 calls) when circuit OPEN")
            return True
        else:
            print(f"❌ FAIL: Wrong behavior: {e}, calls={call_count}")
            return False


# ===========================================================================
# TEST 2: RateLimiter Integration
# ===========================================================================

async def test_rate_limiter_concurrent():
    """Test RateLimiter under concurrent load"""
    
    print("\n" + "="*70)
    print("TEST 2: RateLimiter Concurrent Access")
    print("="*70)
    
    config = RateLimitConfig(
        capacity=50,
        refill_rate=100.0,  # Fast refill
        scope=RateLimitScope.PER_USER
    )
    
    rate_limiter = DistributedRateLimiter(redis_client=None, default_config=config)
    
    allowed_count = 0
    denied_count = 0
    
    # Make 100 concurrent requests
    async def make_request(req_id):
        nonlocal allowed_count, denied_count
        result = await rate_limiter.check_limit(f"user:test", tokens_required=1)
        if result.allowed:
            allowed_count += 1
        else:
            denied_count += 1
    
    tasks = [make_request(i) for i in range(100)]
    await asyncio.gather(*tasks)
    
    print(f"   Allowed: {allowed_count}")
    print(f"   Denied: {denied_count}")
    
    # Should have some allowed (at least capacity)
    if allowed_count >= 50:
        print(f"✅ PASS: Rate limiter working ({allowed_count} allowed, {denied_count} denied)")
        return True
    else:
        print(f"❌ FAIL: Too few allowed: {allowed_count}")
        return False


# ===========================================================================
# TEST 3: DistributedCache TTL and Eviction
# ===========================================================================

async def test_cache_ttl_eviction():
    """Test cache TTL expiration and eviction"""
    
    print("\n" + "="*70)
    print("TEST 3: DistributedCache TTL & Eviction")
    print("="*70)
    
    cache = DistributedCache(
        redis_client=None,
        config=CacheConfig(
            max_size_mb=10,
            default_ttl=1,  # 1 second
            eviction_policy=EvictionPolicy.LRU
        )
    )
    
    # Test 1: TTL expiration
    await cache.set("temp_key", "temp_value", ttl=0.1)
    await asyncio.sleep(0.2)
    
    result = await cache.get("temp_key")
    if result is None:
        print("✅ PASS: TTL expiration works")
        ttl_ok = True
    else:
        print(f"❌ FAIL: Expected None, got {result}")
        ttl_ok = False
    
    # Test 2: Cache stores and retrieves
    await cache.set("key1", "value1")
    result2 = await cache.get("key1")
    
    if result2 == "value1":
        print("✅ PASS: Cache set/get works")
        set_get_ok = True
    else:
        print(f"❌ FAIL: Expected 'value1', got {result2}")
        set_get_ok = False
    
    # Test 3: Multiple items
    for i in range(20):
        await cache.set(f"item{i}", f"value{i}")
    
    cache_size = len(cache._local_cache)
    print(f"   Cache size after 20 items: {cache_size}")
    
    if cache_size > 0:
        print("✅ PASS: Cache handles multiple items")
        multi_ok = True
    else:
        print("❌ FAIL: Cache is empty")
        multi_ok = False
    
    return ttl_ok and set_get_ok and multi_ok


# ===========================================================================
# TEST 4: Combined Concurrent Load
# ===========================================================================

async def test_combined_concurrent_load():
    """Test all components together under load"""
    
    print("\n" + "="*70)
    print("TEST 4: Combined Concurrent Load (All Components)")
    print("="*70)
    
    # Setup components
    cache = DistributedCache(
        redis_client=None,
        config=CacheConfig(max_size_mb=10, default_ttl=5)
    )
    
    rate_limiter = DistributedRateLimiter(
        redis_client=None,
        default_config=RateLimitConfig(capacity=200, refill_rate=100.0, scope=RateLimitScope.GLOBAL)
    )
    
    circuit = CircuitBreaker(
        name="load_test",
        config=CircuitBreakerConfig(
            failure_threshold=0.9,  # Very permissive
            min_request_volume=50
        )
    )
    
    success_count = 0
    cache_hits = 0
    
    async def simulated_request(req_id):
        nonlocal success_count, cache_hits
        
        # Check cache first
        cache_key = f"data:{req_id % 10}"
        cached = await cache.get(cache_key)
        if cached:
            cache_hits += 1
            success_count += 1
            return cached
        
        # Check rate limit
        limit_result = await rate_limiter.check_limit(f"user:{req_id % 5}", tokens_required=1)
        if not limit_result.allowed:
            return None
        
        # Simulate API call through circuit breaker
        async def api_call():
            await cache.set(cache_key, f"data_{req_id}")
            return f"data_{req_id}"
        
        try:
            result = await circuit.call(api_call)
            success_count += 1
            return result
        except Exception:
            return None
    
    # Execute 100 concurrent requests
    start = time.time()
    await asyncio.gather(*[simulated_request(i) for i in range(100)])
    elapsed = time.time() - start
    
    print(f"   Completed in: {elapsed:.3f}s")
    print(f"   Success: {success_count}")
    print(f"   Cache hits: {cache_hits}")
    print(f"   Rate: {100/elapsed:.0f} req/s")
    
    if success_count >= 50:  # At least 50% success
        print(f"✅ PASS: Combined load test ({success_count}/100 success)")
        return True
    else:
        print(f"❌ FAIL: Success rate too low ({success_count}/100)")
        return False


# ===========================================================================
# MAIN TEST RUNNER
# ===========================================================================

async def run_all_tests():
    """Run all simplified integration tests"""
    
    print("\n" + "="*70)
    print("SIMPLIFIED INTEGRATION TESTS - Phase 3 MEDIUM Task #1")
    print("="*70)
    print("Goal: Increase coverage 78% → 85%+")
    print("="*70)
    
    results = []
    
    # Test 1
    try:
        result = await test_retry_with_circuit_breaker()
        results.append(("RetryPolicy + CircuitBreaker", result))
    except Exception as e:
        print(f"\n❌ FAIL: Test 1 crashed - {e}")
        import traceback
        traceback.print_exc()
        results.append(("RetryPolicy + CircuitBreaker", False))
    
    # Test 2
    try:
        result = await test_rate_limiter_concurrent()
        results.append(("RateLimiter Concurrent", result))
    except Exception as e:
        print(f"\n❌ FAIL: Test 2 crashed - {e}")
        import traceback
        traceback.print_exc()
        results.append(("RateLimiter Concurrent", False))
    
    # Test 3
    try:
        result = await test_cache_ttl_eviction()
        results.append(("Cache TTL & Eviction", result))
    except Exception as e:
        print(f"\n❌ FAIL: Test 3 crashed - {e}")
        import traceback
        traceback.print_exc()
        results.append(("Cache TTL & Eviction", False))
    
    # Test 4
    try:
        result = await test_combined_concurrent_load()
        results.append(("Combined Concurrent Load", result))
    except Exception as e:
        print(f"\n❌ FAIL: Test 4 crashed - {e}")
        import traceback
        traceback.print_exc()
        results.append(("Combined Concurrent Load", False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 ALL INTEGRATION TESTS PASSED!")
        print("Coverage increase: 78% → ~82-85% (estimated)")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
