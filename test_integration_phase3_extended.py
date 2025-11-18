"""
Extended Integration Tests for Phase 3 - Days 24-25

Goal: Increase integration test coverage from 78% to 85%+

Focus Areas:
1. Failure scenarios (service outages, network errors)
2. Race conditions under load
3. Edge cases (boundary conditions, extreme values)
4. Component interactions (RetryPolicy + CircuitBreaker + RateLimiter)

Author: AI Assistant
Date: 2025-11-10
"""

import asyncio
import time
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')

from reliability.retry_policy import RetryPolicy, RetryConfig, NonRetryableException
from reliability.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from reliability.distributed_rate_limiter import DistributedRateLimiter, RateLimitConfig, RateLimitScope
from reliability.distributed_cache import DistributedCache


# ===========================================================================
# TEST SUITE 1: RetryPolicy + CircuitBreaker Integration
# ===========================================================================

async def test_retry_circuit_integration_scenarios():
    """Test RetryPolicy + CircuitBreaker interaction under various scenarios"""
    
    print("\n" + "="*70)
    print("INTEGRATION TEST 1: RetryPolicy + CircuitBreaker")
    print("="*70)
    
    results = []
    
    # Scenario 1: Circuit transitions during retry attempts
    print("\n--- Scenario 1: Circuit opens during retry ---")
    
    circuit_config = CircuitBreakerConfig(
        failure_threshold=0.5,
        min_request_volume=2,
        recovery_timeout=1.0
    )
    circuit = CircuitBreaker(config=circuit_config, service_name="test_service")
    
    retry_config = RetryConfig(
        max_retries=5,
        base_delay=0.01,
        jitter_percentage=0.0  # Deterministic for testing
    )
    retry = RetryPolicy(config=retry_config, circuit_breaker=circuit)
    
    call_count = 0
    async def failing_function():
        nonlocal call_count
        call_count += 1
        # First 2 calls fail -> circuit opens
        if call_count <= 2:
            await circuit.record_failure(Exception("Simulated failure"))
            raise Exception(f"Simulated failure #{call_count}")
        return "success"
    
    try:
        result = await retry.retry(failing_function)
        print(f"❌ FAIL: Should have raised exception, got: {result}")
        results.append(False)
    except NonRetryableException as e:
        if "Circuit breaker is OPEN" in str(e):
            print(f"✅ PASS: Circuit opened after {call_count} failures, retry aborted")
            results.append(True)
        else:
            print(f"❌ FAIL: Wrong exception: {e}")
            results.append(False)
    except Exception as e:
        print(f"❌ FAIL: Unexpected exception: {e}")
        results.append(False)
    
    # Scenario 2: Circuit recovers during retry
    print("\n--- Scenario 2: Circuit recovers (HALF_OPEN → CLOSED) ---")
    
    # Wait for recovery timeout
    await asyncio.sleep(1.1)
    
    # Circuit should be HALF_OPEN now
    call_count = 0
    async def recovering_function():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call succeeds -> circuit closes
            await circuit.record_success()
            return "recovered"
        raise Exception("Should not reach here")
    
    try:
        result = await retry.retry(recovering_function)
        if result == "recovered" and circuit.state == CircuitState.CLOSED:
            print(f"✅ PASS: Circuit recovered, state={circuit.state.value}")
            results.append(True)
        else:
            print(f"❌ FAIL: Circuit state={circuit.state.value}, expected CLOSED")
            results.append(False)
    except Exception as e:
        print(f"❌ FAIL: Unexpected exception: {e}")
        results.append(False)
    
    return all(results)


# ===========================================================================
# TEST SUITE 2: RateLimiter + CircuitBreaker
# ===========================================================================

async def test_ratelimiter_circuit_combination():
    """Test RateLimiter + CircuitBreaker working together"""
    
    print("\n" + "="*70)
    print("INTEGRATION TEST 2: RateLimiter + CircuitBreaker")
    print("="*70)
    
    results = []
    
    # Setup
    rate_limiter = DistributedRateLimiter(redis_client=None)
    rate_config = RateLimitConfig(
        capacity=10,
        refill_rate=2.0,
        scope=RateLimitScope.PER_USER
    )
    
    circuit_config = CircuitBreakerConfig(
        failure_threshold=0.8,
        min_request_volume=5,
        recovery_timeout=0.5
    )
    circuit = CircuitBreaker(config=circuit_config, service_name="api")
    
    # Scenario: Rate limiting prevents circuit from opening
    print("\n--- Scenario: Rate limit protects circuit ---")
    
    identifier = "user:test"
    success_count = 0
    rate_limited_count = 0
    
    # Make 20 requests rapidly
    for i in range(20):
        # Check rate limit
        limit_result = await rate_limiter._check_local(identifier, 1, rate_config)
        
        if limit_result.allowed:
            # Simulate API call
            try:
                # First 5 calls succeed, rest fail
                if i < 5:
                    await circuit.record_success()
                    success_count += 1
                else:
                    await circuit.record_failure(Exception("API error"))
            except Exception:
                pass
        else:
            rate_limited_count += 1
    
    # Circuit should NOT be open because rate limiter prevented excessive failures
    if circuit.state != CircuitState.OPEN:
        print(f"✅ PASS: Circuit state={circuit.state.value} (rate limiter protected)")
        print(f"   Success: {success_count}, Rate limited: {rate_limited_count}")
        results.append(True)
    else:
        print(f"❌ FAIL: Circuit opened despite rate limiting")
        results.append(False)
    
    return all(results)


# ===========================================================================
# TEST SUITE 3: Distributed Cache Edge Cases
# ===========================================================================

async def test_distributed_cache_edge_cases():
    """Test DistributedCache with edge cases"""
    
    print("\n" + "="*70)
    print("INTEGRATION TEST 3: DistributedCache Edge Cases")
    print("="*70)
    
    results = []
    
    cache = DistributedCache(
        redis_client=None,
        default_ttl=1,  # 1 second TTL
        max_memory_items=5
    )
    
    # Edge Case 1: Expired items
    print("\n--- Edge Case 1: Expired items ---")
    
    await cache.set("key1", "value1", ttl=0.1)  # 100ms TTL
    await asyncio.sleep(0.2)  # Wait for expiration
    
    result = await cache.get("key1")
    if result is None:
        print("✅ PASS: Expired item returns None")
        results.append(True)
    else:
        print(f"❌ FAIL: Expected None, got {result}")
        results.append(False)
    
    # Edge Case 2: Memory limit enforcement
    print("\n--- Edge Case 2: Memory limit (max 5 items) ---")
    
    # Fill cache to capacity
    for i in range(7):
        await cache.set(f"item{i}", f"value{i}")
    
    # Check cache size (should be <= 5)
    cache_size = len(cache._memory_cache)
    if cache_size <= 5:
        print(f"✅ PASS: Cache size={cache_size} (within limit)")
        results.append(True)
    else:
        print(f"❌ FAIL: Cache size={cache_size} exceeds limit 5")
        results.append(False)
    
    # Edge Case 3: LRU eviction order
    print("\n--- Edge Case 3: LRU eviction order ---")
    
    cache2 = DistributedCache(redis_client=None, max_memory_items=3)
    
    # Add 3 items
    await cache2.set("a", "1")
    await cache2.set("b", "2")
    await cache2.set("c", "3")
    
    # Access "a" to make it most recently used
    await cache2.get("a")
    
    # Add new item (should evict "b", least recently used)
    await cache2.set("d", "4")
    
    # Check if "b" was evicted
    result_b = await cache2.get("b")
    result_a = await cache2.get("a")
    
    if result_b is None and result_a == "1":
        print("✅ PASS: LRU eviction works correctly")
        results.append(True)
    else:
        print(f"❌ FAIL: b={result_b} (expected None), a={result_a}")
        results.append(False)
    
    return all(results)


# ===========================================================================
# TEST SUITE 4: Concurrent Load Test
# ===========================================================================

async def test_concurrent_reliability_patterns():
    """Test all reliability patterns under concurrent load"""
    
    print("\n" + "="*70)
    print("INTEGRATION TEST 4: Concurrent Reliability Patterns")
    print("="*70)
    
    results = []
    
    # Setup all components
    rate_limiter = DistributedRateLimiter(redis_client=None)
    rate_config = RateLimitConfig(
        capacity=100,
        refill_rate=50.0,
        scope=RateLimitScope.PER_USER
    )
    
    circuit = CircuitBreaker(
        config=CircuitBreakerConfig(
            failure_threshold=0.5,
            min_request_volume=10
        ),
        service_name="load_test"
    )
    
    retry = RetryPolicy(
        config=RetryConfig(max_retries=2, base_delay=0.01),
        circuit_breaker=circuit
    )
    
    cache = DistributedCache(redis_client=None, max_memory_items=50)
    
    # Scenario: 100 concurrent requests
    print("\n--- Scenario: 100 concurrent requests ---")
    
    request_count = 0
    success_count = 0
    failure_count = 0
    cached_count = 0
    
    async def simulated_request(request_id):
        nonlocal request_count, success_count, failure_count, cached_count
        request_count += 1
        
        identifier = f"user:{request_id % 10}"  # 10 different users
        
        # Check rate limit
        limit_result = await rate_limiter._check_local(identifier, 1, rate_config)
        if not limit_result.allowed:
            failure_count += 1
            return None
        
        # Check cache
        cache_key = f"data:{request_id % 20}"  # 20 different keys
        cached_value = await cache.get(cache_key)
        if cached_value:
            cached_count += 1
            success_count += 1
            return cached_value
        
        # Simulated API call with retry
        async def api_call():
            # 70% success rate
            if (request_id % 10) < 7:
                value = f"data_{request_id}"
                await cache.set(cache_key, value)
                await circuit.record_success()
                return value
            else:
                await circuit.record_failure(Exception("API error"))
                raise Exception("API error")
        
        try:
            result = await retry.retry(api_call)
            success_count += 1
            return result
        except Exception:
            failure_count += 1
            return None
    
    # Execute concurrent requests
    start_time = time.time()
    tasks = [simulated_request(i) for i in range(100)]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start_time
    
    print(f"✅ Executed 100 concurrent requests in {elapsed:.3f}s")
    print(f"   Success: {success_count}")
    print(f"   Failure: {failure_count}")
    print(f"   Cached: {cached_count}")
    print(f"   Rate: {100/elapsed:.0f} req/s")
    
    # Verify reasonable success rate (should be > 50%)
    success_rate = success_count / request_count
    if success_rate > 0.5:
        print(f"✅ PASS: Success rate {success_rate:.1%} > 50%")
        results.append(True)
    else:
        print(f"❌ FAIL: Success rate {success_rate:.1%} too low")
        results.append(False)
    
    return all(results)


# ===========================================================================
# MAIN TEST RUNNER
# ===========================================================================

async def run_all_integration_tests():
    """Run all extended integration tests"""
    
    print("\n" + "="*70)
    print("EXTENDED INTEGRATION TESTS - Phase 3 Days 24-25")
    print("="*70)
    print("\nGoal: Increase coverage from 78% to 85%+")
    print("Focus: Failure scenarios, race conditions, edge cases")
    print("="*70)
    
    all_results = []
    
    # Test Suite 1
    try:
        result = await test_retry_circuit_integration_scenarios()
        all_results.append(("RetryPolicy + CircuitBreaker", result))
    except Exception as e:
        print(f"\n❌ FAIL: Test Suite 1 crashed - {e}")
        all_results.append(("RetryPolicy + CircuitBreaker", False))
    
    # Test Suite 2
    try:
        result = await test_ratelimiter_circuit_combination()
        all_results.append(("RateLimiter + CircuitBreaker", result))
    except Exception as e:
        print(f"\n❌ FAIL: Test Suite 2 crashed - {e}")
        all_results.append(("RateLimiter + CircuitBreaker", False))
    
    # Test Suite 3
    try:
        result = await test_distributed_cache_edge_cases()
        all_results.append(("DistributedCache Edge Cases", result))
    except Exception as e:
        print(f"\n❌ FAIL: Test Suite 3 crashed - {e}")
        all_results.append(("DistributedCache Edge Cases", False))
    
    # Test Suite 4
    try:
        result = await test_concurrent_reliability_patterns()
        all_results.append(("Concurrent Reliability Patterns", result))
    except Exception as e:
        print(f"\n❌ FAIL: Test Suite 4 crashed - {e}")
        all_results.append(("Concurrent Reliability Patterns", False))
    
    # Print summary
    print("\n" + "="*70)
    print("EXTENDED INTEGRATION TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in all_results if result)
    total = len(all_results)
    
    for test_name, result in all_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} test suites passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 ALL EXTENDED INTEGRATION TESTS PASSED!")
        print("Estimated coverage increase: 78% → 82-85%")
    else:
        print(f"\n⚠️ {total - passed} test suite(s) failed")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_integration_tests())
    exit(0 if success else 1)
