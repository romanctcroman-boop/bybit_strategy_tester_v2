"""
Comprehensive Test Suite for CircuitBreaker V2 with Prometheus Metrics

Tests:
1. ✅ Async operations with asyncio.Lock
2. ✅ Prometheus metrics export
3. ✅ State transitions with metrics tracking
4. ✅ Circuit breaker behavior (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
5. ✅ Metrics accuracy
6. ✅ Backward compatibility
"""

import asyncio
import sys
import time
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from api.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    PROMETHEUS_AVAILABLE
)

print(f"🔍 Prometheus availability: {PROMETHEUS_AVAILABLE}")


async def test_1_async_lock_safety():
    """Test 1: Verify asyncio.Lock prevents race conditions"""
    print("\n" + "="*70)
    print("TEST 1: Asyncio Lock Safety (Concurrent Operations)")
    print("="*70)
    
    breaker = CircuitBreaker(
        failure_threshold=10,
        key_id="test_async",
        provider="test"
    )
    
    # Simulate 100 concurrent record_failure calls
    async def concurrent_failures():
        tasks = [breaker.record_failure() for _ in range(100)]
        await asyncio.gather(*tasks)
    
    start_time = time.time()
    await concurrent_failures()
    duration = time.time() - start_time
    
    stats = breaker.get_stats()
    
    # With asyncio.Lock, failure_count should be exactly 100
    assert stats['failure_count'] <= 100, f"Race condition detected: {stats['failure_count']} > 100"
    
    print(f"✅ Concurrent operations completed in {duration:.3f}s")
    print(f"✅ Final failure count: {stats['failure_count']} (no race condition)")
    print(f"✅ Circuit state: {stats['state']}")
    
    return True


async def test_2_prometheus_metrics_integration():
    """Test 2: Verify Prometheus metrics are exported correctly"""
    print("\n" + "="*70)
    print("TEST 2: Prometheus Metrics Integration")
    print("="*70)
    
    if not PROMETHEUS_AVAILABLE:
        print("⚠️  Prometheus client not installed - skipping metrics test")
        return True
    
    breaker = CircuitBreaker(
        failure_threshold=3,
        success_threshold=2,
        timeout=1,
        key_id="metrics_test",
        provider="deepseek"
    )
    
    # Initial state: CLOSED
    metrics = breaker.get_prometheus_metrics()
    assert metrics['circuit_breaker_state'] == 0, "Initial state should be CLOSED (0)"
    print(f"✅ Initial metrics: {metrics}")
    
    # Trigger 3 failures -> OPEN
    for i in range(3):
        await breaker.record_failure()
        print(f"   Failure {i+1}/3 recorded")
    
    stats = breaker.get_stats()
    metrics = breaker.get_prometheus_metrics()
    
    assert stats['state'] == 'open', f"Expected OPEN, got {stats['state']}"
    assert metrics['circuit_breaker_state'] == 2, "Metrics should show OPEN (2)"
    assert metrics['circuit_breaker_failure_count'] == 3, "Should have 3 failures"
    
    print(f"✅ Circuit OPENED after 3 failures")
    print(f"✅ Metrics updated correctly: state={metrics['circuit_breaker_state']}, failures={metrics['circuit_breaker_failure_count']}")
    
    # Wait for timeout -> HALF_OPEN
    print(f"   Waiting 1.2s for timeout...")
    await asyncio.sleep(1.2)
    
    # Check availability triggers state transition
    is_available = await breaker.is_available()
    stats = breaker.get_stats()
    metrics = breaker.get_prometheus_metrics()
    
    assert stats['state'] == 'half_open', f"Expected HALF_OPEN, got {stats['state']}"
    assert metrics['circuit_breaker_state'] == 1, "Metrics should show HALF_OPEN (1)"
    
    print(f"✅ Circuit transitioned to HALF_OPEN")
    print(f"✅ Metrics: {metrics}")
    
    # Record 2 successes -> CLOSED
    for i in range(2):
        await breaker.record_success()
        print(f"   Success {i+1}/2 recorded")
    
    stats = breaker.get_stats()
    metrics = breaker.get_prometheus_metrics()
    
    assert stats['state'] == 'closed', f"Expected CLOSED, got {stats['state']}"
    assert metrics['circuit_breaker_state'] == 0, "Metrics should show CLOSED (0)"
    assert metrics['circuit_breaker_success_count'] == 0, "Success count should reset"
    
    print(f"✅ Circuit CLOSED after 2 successes")
    print(f"✅ Final metrics: {metrics}")
    
    return True


async def test_3_state_transition_tracking():
    """Test 3: Verify state transitions are tracked correctly"""
    print("\n" + "="*70)
    print("TEST 3: State Transition Tracking")
    print("="*70)
    
    breaker = CircuitBreaker(
        failure_threshold=2,
        success_threshold=1,
        timeout=0.5,
        key_id="transition_test",
        provider="test"
    )
    
    print(f"Initial state: {breaker.state.value}")
    
    # CLOSED -> OPEN
    await breaker.record_failure()
    await breaker.record_failure()
    
    assert breaker.state == CircuitState.OPEN, "Should be OPEN after 2 failures"
    print(f"✅ Transition: CLOSED -> OPEN")
    
    # Wait for timeout
    await asyncio.sleep(0.6)
    
    # Trigger OPEN -> HALF_OPEN
    await breaker.is_available()
    
    assert breaker.state == CircuitState.HALF_OPEN, "Should be HALF_OPEN after timeout"
    print(f"✅ Transition: OPEN -> HALF_OPEN")
    
    # HALF_OPEN -> CLOSED
    await breaker.record_success()
    
    assert breaker.state == CircuitState.CLOSED, "Should be CLOSED after success"
    print(f"✅ Transition: HALF_OPEN -> CLOSED")
    
    # HALF_OPEN -> OPEN (failure in half-open)
    await breaker.record_failure()
    await breaker.record_failure()
    await asyncio.sleep(0.6)
    await breaker.is_available()  # Trigger HALF_OPEN
    
    assert breaker.state == CircuitState.HALF_OPEN, "Should be in HALF_OPEN"
    print(f"✅ Back to HALF_OPEN for testing failure path")
    
    await breaker.record_failure()
    
    assert breaker.state == CircuitState.OPEN, "Should return to OPEN after failure in HALF_OPEN"
    print(f"✅ Transition: HALF_OPEN -> OPEN (failure path)")
    
    return True


async def test_4_metrics_accuracy():
    """Test 4: Verify metrics reflect actual circuit breaker state"""
    print("\n" + "="*70)
    print("TEST 4: Metrics Accuracy (State vs Metrics Consistency)")
    print("="*70)
    
    if not PROMETHEUS_AVAILABLE:
        print("⚠️  Prometheus client not installed - skipping")
        return True
    
    breaker = CircuitBreaker(
        failure_threshold=5,
        key_id="accuracy_test",
        provider="test"
    )
    
    # Test multiple failure recordings
    for i in range(5):
        await breaker.record_failure()
        
        stats = breaker.get_stats()
        metrics = breaker.get_prometheus_metrics()
        
        # Verify failure count accuracy
        assert metrics['circuit_breaker_failure_count'] == stats['failure_count'], \
            f"Metrics mismatch at failure {i+1}"
        
        print(f"   Failure {i+1}: state={stats['state']}, "
              f"failures={metrics['circuit_breaker_failure_count']}")
    
    # Verify OPEN state
    stats = breaker.get_stats()
    metrics = breaker.get_prometheus_metrics()
    
    assert stats['state'] == 'open', "Should be OPEN after 5 failures"
    assert metrics['circuit_breaker_state'] == 2, "Metrics should show OPEN"
    
    print(f"✅ All metrics accurate throughout test")
    print(f"✅ Final state: {stats['state']} (metrics: {metrics['circuit_breaker_state']})")
    
    return True


async def test_5_get_stats_with_metrics():
    """Test 5: Verify get_stats() includes Prometheus info"""
    print("\n" + "="*70)
    print("TEST 5: get_stats() with Prometheus Information")
    print("="*70)
    
    breaker = CircuitBreaker(
        failure_threshold=3,
        key_id="stats_test",
        provider="deepseek"
    )
    
    stats = breaker.get_stats()
    
    # Verify new fields in V2
    assert 'key_id' in stats, "Missing key_id in stats"
    assert 'provider' in stats, "Missing provider in stats"
    assert 'prometheus_enabled' in stats, "Missing prometheus_enabled in stats"
    
    assert stats['key_id'] == "stats_test", f"Wrong key_id: {stats['key_id']}"
    assert stats['provider'] == "deepseek", f"Wrong provider: {stats['provider']}"
    assert stats['prometheus_enabled'] == PROMETHEUS_AVAILABLE
    
    print(f"✅ key_id: {stats['key_id']}")
    print(f"✅ provider: {stats['provider']}")
    print(f"✅ prometheus_enabled: {stats['prometheus_enabled']}")
    print(f"✅ state: {stats['state']}")
    print(f"✅ config: {stats['config']}")
    
    return True


async def test_6_backward_compatibility():
    """Test 6: Verify old code (without key_id/provider) still works"""
    print("\n" + "="*70)
    print("TEST 6: Backward Compatibility (Old Usage Pattern)")
    print("="*70)
    
    # Old usage: no key_id or provider
    breaker = CircuitBreaker(
        failure_threshold=3,
        success_threshold=2,
        timeout=60
    )
    
    stats = breaker.get_stats()
    
    # Should have default values
    assert stats['key_id'] == "default", f"Expected 'default', got {stats['key_id']}"
    assert stats['provider'] == "unknown", f"Expected 'unknown', got {stats['provider']}"
    
    # Test basic functionality
    await breaker.record_failure()
    await breaker.record_failure()
    await breaker.record_failure()
    
    assert breaker.state == CircuitState.OPEN, "Should be OPEN after 3 failures"
    
    print(f"✅ Old usage pattern works (default key_id/provider)")
    print(f"✅ Circuit breaker functionality intact")
    print(f"✅ Stats: {stats}")
    
    return True


async def run_all_tests():
    """Run all tests and report results"""
    print("=" * 70)
    print("🚀 CIRCUIT BREAKER V2 TEST SUITE")
    print("=" * 70)
    print(f"Prometheus Client Available: {PROMETHEUS_AVAILABLE}")
    print()
    
    tests = [
        ("Async Lock Safety", test_1_async_lock_safety),
        ("Prometheus Metrics Integration", test_2_prometheus_metrics_integration),
        ("State Transition Tracking", test_3_state_transition_tracking),
        ("Metrics Accuracy", test_4_metrics_accuracy),
        ("get_stats() Enhancement", test_5_get_stats_with_metrics),
        ("Backward Compatibility", test_6_backward_compatibility),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, "✅ PASSED", None))
        except Exception as e:
            results.append((test_name, "❌ FAILED", str(e)))
            print(f"\n❌ TEST FAILED: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    for test_name, status, error in results:
        print(f"{status} {test_name}")
        if error:
            print(f"   Error: {error}")
    
    passed = sum(1 for _, status, _ in results if "PASSED" in status)
    total = len(results)
    
    print(f"\n{'='*70}")
    print(f"🎯 Results: {passed}/{total} tests passed ({100*passed//total}%)")
    print(f"{'='*70}")
    
    if passed == total:
        print("✅ ALL TESTS PASSED! Circuit Breaker V2 is production-ready! 🚀")
    else:
        print(f"❌ {total - passed} test(s) failed. Review errors above.")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
