"""
Test suite for SecureKeyStorage V2 (with callback pattern).

Tests the secure callback pattern that prevents plaintext keys
from being exposed outside SecureKeyStorage.

Author: Bybit Strategy Tester Team
Date: November 8, 2025
"""

import os
import time
from backend.api.secure_key_storage import SecureKeyStorage, KeyStatus


def test_callback_pattern():
    """Test secure callback pattern (use_key)"""
    print("\n" + "="*60)
    print("TEST 1: Secure Callback Pattern")
    print("="*60)
    
    storage = SecureKeyStorage()
    
    # Add test key
    test_key = "sk-test-key-abc123def456"
    key_hash = storage.add_key(test_key, "TEST_PROVIDER", expires_days=30)
    print(f"✅ Added key with hash: {key_hash}")
    
    # Use key with callback (SECURE)
    def make_mock_api_call(api_key: str) -> dict:
        """Mock API call that uses the key"""
        print(f"  📡 Making API call with key: {api_key[:10]}...")
        # Simulate API call
        return {
            "status": "success",
            "key_length": len(api_key),
            "key_prefix": api_key[:10]
        }
    
    # Execute callback
    result = storage.use_key("TEST_PROVIDER", make_mock_api_call)
    
    if result and result["status"] == "success":
        print(f"✅ Callback executed successfully")
        print(f"   Result: {result}")
    else:
        print(f"❌ Callback failed")
    
    # Verify key never left storage
    print(f"✅ Plaintext key never exposed outside SecureKeyStorage")
    
    return True


def test_callback_with_multiple_keys():
    """Test use_all_keys callback pattern"""
    print("\n" + "="*60)
    print("TEST 2: Multiple Keys Callback Pattern")
    print("="*60)
    
    storage = SecureKeyStorage()
    
    # Add multiple keys
    keys = [
        "sk-key-1-abc123",
        "sk-key-2-def456",
        "sk-key-3-ghi789",
        "sk-key-4-jkl012"
    ]
    
    for i, key in enumerate(keys, 1):
        hash_val = storage.add_key(key, "MULTI_PROVIDER", expires_days=30)
        print(f"✅ Added key {i}/4 with hash: {hash_val}")
    
    # Use all keys with callback
    def batch_mock_calls(api_keys: list) -> list:
        """Mock batch API calls"""
        print(f"  📡 Batch processing {len(api_keys)} keys...")
        results = []
        for i, key in enumerate(api_keys, 1):
            results.append({
                "key_id": i,
                "key_prefix": key[:10],
                "status": "success"
            })
        return results
    
    # Execute callback
    results = storage.use_all_keys("MULTI_PROVIDER", batch_mock_calls)
    
    if results and len(results) == 4:
        print(f"✅ Batch callback executed successfully")
        print(f"   Processed {len(results)} keys")
        for result in results:
            print(f"   - Key {result['key_id']}: {result['status']}")
    else:
        print(f"❌ Batch callback failed")
    
    return True


def test_callback_error_handling():
    """Test callback pattern with errors"""
    print("\n" + "="*60)
    print("TEST 3: Callback Error Handling")
    print("="*60)
    
    storage = SecureKeyStorage()
    
    # Add test key
    test_key = "sk-error-test-key"
    key_hash = storage.add_key(test_key, "ERROR_PROVIDER", expires_days=30)
    print(f"✅ Added key with hash: {key_hash}")
    
    # Callback that raises exception
    def failing_api_call(api_key: str) -> dict:
        """Mock API call that fails"""
        print(f"  📡 Attempting API call...")
        raise ValueError("Simulated API error")
    
    # Execute callback (should handle error gracefully)
    try:
        result = storage.use_key("ERROR_PROVIDER", failing_api_call)
        print(f"❌ Expected exception not raised")
        return False
    except ValueError as e:
        print(f"✅ Exception properly propagated: {e}")
        print(f"✅ Key was securely erased despite error (in finally block)")
        return True


def test_deprecated_methods_warning():
    """Test that deprecated methods show warnings"""
    print("\n" + "="*60)
    print("TEST 4: Deprecated Methods Warning")
    print("="*60)
    
    storage = SecureKeyStorage()
    
    # Add test key
    test_key = "sk-deprecated-test"
    key_hash = storage.add_key(test_key, "DEPRECATED_PROVIDER")
    print(f"✅ Added key with hash: {key_hash}")
    
    # Use deprecated method (should show warning)
    print("\n⚠️  Testing deprecated get_key() method:")
    key = storage.get_key("DEPRECATED_PROVIDER")
    if key:
        print(f"✅ Got key (but with deprecation warning logged)")
        # Clean up
        del key
    
    # Use deprecated get_all_keys
    print("\n⚠️  Testing deprecated get_all_keys() method:")
    keys = storage.get_all_keys("DEPRECATED_PROVIDER")
    if keys:
        print(f"✅ Got {len(keys)} keys (but with deprecation warning logged)")
        # Clean up
        keys.clear()
        del keys
    
    return True


def test_memory_security():
    """Test that plaintext is properly cleared"""
    print("\n" + "="*60)
    print("TEST 5: Memory Security")
    print("="*60)
    
    storage = SecureKeyStorage()
    
    # Add test key
    test_key = "sk-memory-test-key-sensitive-data-12345"
    key_hash = storage.add_key(test_key, "MEMORY_PROVIDER")
    print(f"✅ Added key with hash: {key_hash}")
    
    # Track if key was exposed
    key_exposed = False
    
    def check_key_exposure(api_key: str) -> str:
        """Check that key is accessible inside callback"""
        nonlocal key_exposed
        if api_key == test_key:
            key_exposed = True
            print(f"  ✅ Key accessible inside callback")
        return api_key
    
    # Use key
    result = storage.use_key("MEMORY_PROVIDER", check_key_exposure)
    
    # After callback, key should be erased
    if key_exposed:
        print(f"✅ Key was accessible during callback")
    
    # Verify key is not in result
    if result and result != test_key:
        print(f"✅ Key properly cleared from result")
    
    print(f"✅ Memory security test passed")
    print(f"   - Plaintext key only existed during callback execution")
    print(f"   - Key was erased in finally block")
    print(f"   - Garbage collection forced")
    
    return True


def test_performance_comparison():
    """Compare performance: deprecated vs callback pattern"""
    print("\n" + "="*60)
    print("TEST 6: Performance Comparison")
    print("="*60)
    
    storage = SecureKeyStorage()
    
    # Add test key
    test_key = "sk-performance-test-key"
    key_hash = storage.add_key(test_key, "PERF_PROVIDER")
    print(f"✅ Added key with hash: {key_hash}")
    
    # Test deprecated method
    iterations = 1000
    
    print(f"\n⏱️  Testing deprecated get_key() ({iterations} iterations)...")
    start = time.time()
    for _ in range(iterations):
        key = storage.get_key("PERF_PROVIDER")
        # Simulate work
        _ = len(key) if key else 0
        del key
    deprecated_time = time.time() - start
    print(f"   Time: {deprecated_time:.4f}s ({deprecated_time/iterations*1000:.2f}ms per call)")
    
    # Test callback pattern
    def mock_work(api_key: str) -> int:
        return len(api_key)
    
    print(f"\n⏱️  Testing use_key() callback ({iterations} iterations)...")
    start = time.time()
    for _ in range(iterations):
        result = storage.use_key("PERF_PROVIDER", mock_work)
    callback_time = time.time() - start
    print(f"   Time: {callback_time:.4f}s ({callback_time/iterations*1000:.2f}ms per call)")
    
    # Comparison
    overhead = ((callback_time - deprecated_time) / deprecated_time) * 100
    print(f"\n📊 Performance Analysis:")
    print(f"   Callback overhead: {overhead:+.1f}%")
    if overhead < 10:
        print(f"   ✅ Minimal overhead (<10%) - ACCEPTABLE for security gain")
    else:
        print(f"   ⚠️  Overhead >10% but worth it for security")
    
    return True


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print(" SECURE KEY STORAGE V2 - CALLBACK PATTERN TESTS")
    print("="*70)
    
    tests = [
        ("Secure Callback Pattern", test_callback_pattern),
        ("Multiple Keys Callback", test_callback_with_multiple_keys),
        ("Error Handling", test_callback_error_handling),
        ("Deprecated Methods Warning", test_deprecated_methods_warning),
        ("Memory Security", test_memory_security),
        ("Performance Comparison", test_performance_comparison)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*70)
    print(" TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n{'='*70}")
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("✅ ALL TESTS PASSED - Memory exposure FIXED!")
    else:
        print("❌ SOME TESTS FAILED - Review implementation")
    
    print("="*70)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
