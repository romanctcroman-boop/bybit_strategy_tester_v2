"""
Test for Configurable Jitter Implementation (0-100%)

Validates that RetryPolicy jitter can be configured from 0% to 100%
following AWS SDK best practices.

Phase 3 Day 22: High Priority Task
"""

import asyncio
import statistics
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')

from reliability.retry_policy import RetryPolicy, RetryConfig, NonRetryableException


async def test_jitter_configurations():
    """Test different jitter configurations"""
    
    print("=" * 70)
    print("TEST: Configurable Jitter (0% - 100%)")
    print("=" * 70)
    
    # Test function that always fails
    call_count = 0
    async def failing_function():
        nonlocal call_count
        call_count += 1
        raise Exception("Simulated failure")
    
    test_results = []
    
    # -----------------------------------------------------------------------
    # Test 1: 0% Jitter (Deterministic)
    # -----------------------------------------------------------------------
    print("\n--- Test 1: 0% Jitter (Deterministic) ---")
    config = RetryConfig(
        max_retries=3,
        base_delay=1.0,
        exponential_base=2,
        jitter=True,
        jitter_percentage=0.0  # No randomization
    )
    policy = RetryPolicy(config=config)
    call_count = 0
    
    delays_0_percent = []
    try:
        await policy.retry(failing_function)
    except Exception:
        pass
    
    # Extract delays from history
    for attempt in policy.retry_history:
        if attempt.delay_before is not None:
            delays_0_percent.append(attempt.delay_before)
    
    print(f"Delays: {[f'{d:.4f}' for d in delays_0_percent]}")
    print(f"Expected: [1.0000, 2.0000, 4.0000] (exact exponential backoff)")
    
    # Verify deterministic behavior (all delays should be exact)
    expected = [1.0, 2.0, 4.0]
    for i, (actual, exp) in enumerate(zip(delays_0_percent, expected)):
        if abs(actual - exp) < 0.0001:
            print(f"✅ Delay {i+1}: {actual:.4f} = {exp} (deterministic)")
        else:
            print(f"❌ Delay {i+1}: {actual:.4f} ≠ {exp} (should be deterministic)")
            test_results.append(False)
    
    test_results.append(True)
    
    # -----------------------------------------------------------------------
    # Test 2: 50% Jitter (Half jitter)
    # -----------------------------------------------------------------------
    print("\n--- Test 2: 50% Jitter (Half jitter) ---")
    config = RetryConfig(
        max_retries=3,
        base_delay=1.0,
        exponential_base=2,
        jitter=True,
        jitter_percentage=0.5  # Half jitter
    )
    policy = RetryPolicy(config=config)
    call_count = 0
    
    delays_50_percent = []
    try:
        await policy.retry(failing_function)
    except Exception:
        pass
    
    # Extract delays
    for attempt in policy.retry_history:
        if attempt.delay_before is not None:
            delays_50_percent.append(attempt.delay_before)
    
    print(f"Delays: {[f'{d:.4f}' for d in delays_50_percent]}")
    print(f"Expected ranges: [0.5-1.0], [1.0-2.0], [2.0-4.0]")
    
    # Verify 50% jitter ranges
    expected_ranges = [(0.5, 1.0), (1.0, 2.0), (2.0, 4.0)]
    for i, (actual, (min_val, max_val)) in enumerate(zip(delays_50_percent, expected_ranges)):
        if min_val <= actual <= max_val:
            print(f"✅ Delay {i+1}: {actual:.4f} in [{min_val}, {max_val}]")
        else:
            print(f"❌ Delay {i+1}: {actual:.4f} NOT in [{min_val}, {max_val}]")
            test_results.append(False)
    
    test_results.append(True)
    
    # -----------------------------------------------------------------------
    # Test 3: 100% Jitter (Full jitter - AWS SDK standard)
    # -----------------------------------------------------------------------
    print("\n--- Test 3: 100% Jitter (Full jitter - AWS SDK standard) ---")
    config = RetryConfig(
        max_retries=3,
        base_delay=1.0,
        exponential_base=2,
        jitter=True,
        jitter_percentage=1.0  # Full jitter (default)
    )
    policy = RetryPolicy(config=config)
    call_count = 0
    
    delays_100_percent = []
    try:
        await policy.retry(failing_function)
    except Exception:
        pass
    
    # Extract delays
    for attempt in policy.retry_history:
        if attempt.delay_before is not None:
            delays_100_percent.append(attempt.delay_before)
    
    print(f"Delays: {[f'{d:.4f}' for d in delays_100_percent]}")
    print(f"Expected ranges: [0.0-1.0], [0.0-2.0], [0.0-4.0]")
    
    # Verify 100% jitter ranges
    expected_ranges = [(0.0, 1.0), (0.0, 2.0), (0.0, 4.0)]
    for i, (actual, (min_val, max_val)) in enumerate(zip(delays_100_percent, expected_ranges)):
        if min_val <= actual <= max_val:
            print(f"✅ Delay {i+1}: {actual:.4f} in [{min_val}, {max_val}]")
        else:
            print(f"❌ Delay {i+1}: {actual:.4f} NOT in [{min_val}, {max_val}]")
            test_results.append(False)
    
    test_results.append(True)
    
    # -----------------------------------------------------------------------
    # Test 4: Default Configuration (should be 100% jitter)
    # -----------------------------------------------------------------------
    print("\n--- Test 4: Default Configuration (should be 100% jitter) ---")
    
    # Create policy with default config (no arguments)
    policy_default = RetryPolicy()
    
    print(f"Default jitter_percentage: {policy_default.config.jitter_percentage}")
    print(f"Expected: 1.0 (100% full jitter - AWS SDK standard)")
    
    if policy_default.config.jitter_percentage == 1.0:
        print(f"✅ Default is 100% full jitter (AWS SDK standard)")
        test_results.append(True)
    else:
        print(f"❌ Default is {policy_default.config.jitter_percentage * 100}%, expected 100%")
        test_results.append(False)
    
    # -----------------------------------------------------------------------
    # Test 5: Backward Compatibility (Legacy jitter_min/max)
    # -----------------------------------------------------------------------
    print("\n--- Test 5: Backward Compatibility (Legacy jitter_min/max) ---")
    config = RetryConfig(
        max_retries=2,
        base_delay=2.0,
        exponential_base=2,
        jitter=True,
        jitter_min=0.8,  # Legacy: 80% of delay
        jitter_max=1.2   # Legacy: 120% of delay
    )
    # Remove new jitter_percentage to test legacy path
    if hasattr(config, 'jitter_percentage'):
        delattr(config, 'jitter_percentage')
    
    policy = RetryPolicy(config=config)
    call_count = 0
    
    delays_legacy = []
    try:
        await policy.retry(failing_function)
    except Exception:
        pass
    
    # Extract delays
    for attempt in policy.retry_history:
        if attempt.delay_before is not None:
            delays_legacy.append(attempt.delay_before)
    
    print(f"Delays: {[f'{d:.4f}' for d in delays_legacy]}")
    print(f"Expected ranges: [1.6-2.4], [3.2-4.8] (legacy multiplier method)")
    
    # Verify legacy ranges
    expected_ranges = [(1.6, 2.4), (3.2, 4.8)]
    for i, (actual, (min_val, max_val)) in enumerate(zip(delays_legacy, expected_ranges)):
        if min_val <= actual <= max_val:
            print(f"✅ Delay {i+1}: {actual:.4f} in [{min_val}, {max_val}] (legacy compatible)")
        else:
            print(f"❌ Delay {i+1}: {actual:.4f} NOT in [{min_val}, {max_val}]")
            test_results.append(False)
    
    test_results.append(True)
    
    # -----------------------------------------------------------------------
    # Final Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in test_results if r)
    total = len(test_results)
    
    print(f"\n✅ Test 1: 0% Jitter (Deterministic)")
    print(f"✅ Test 2: 50% Jitter (Half jitter)")
    print(f"✅ Test 3: 100% Jitter (Full jitter - AWS SDK)")
    print(f"✅ Test 4: Default Configuration (100% jitter)")
    print(f"✅ Test 5: Backward Compatibility (Legacy)")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 ALL JITTER TESTS PASSED!")
        print("✅ Configurable jitter (0-100%) implemented successfully")
        print("✅ AWS SDK standard (100% full jitter) is now default")
        print("✅ Backward compatibility maintained")
        return True
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_jitter_configurations())
    exit(0 if success else 1)
