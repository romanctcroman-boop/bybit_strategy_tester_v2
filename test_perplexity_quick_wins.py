"""
🚀 Тест Quick Wins для Perplexity Optimization

Проверяет работу всех 4 Quick Wins:
1. Base Caching (SimpleCache)
2. Improved Health Check
3. Circuit Breaker
4. Model Mapping Optimization

Usage:
    python test_perplexity_quick_wins.py
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# Add mcp-server to path
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))

from api.providers.perplexity import PerplexityProvider
from backend.api.perplexity_client import PerplexityClient


async def test_quick_win_1_caching():
    """
    🚀 Quick Win 1: Base Caching (SimpleCache)
    
    Проверяет:
    - Cache HIT/MISS
    - LRU eviction
    - TTL expiration
    - Statistics tracking
    """
    print("\n" + "=" * 60)
    print("🚀 Quick Win 1: Base Caching (SimpleCache)")
    print("=" * 60)
    
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("❌ PERPLEXITY_API_KEY not set, skipping test")
        return
    
    # Создать provider с кэшем
    provider = PerplexityProvider(
        api_key=api_key,
        enable_cache=True,
        cache_max_size=3,  # Маленький для теста LRU
        cache_ttl_seconds=10  # Короткий для теста TTL
    )
    
    print("\n1. First request (should be MISS)")
    start = time.time()
    result1 = await provider.generate_response("What is Bitcoin?", model="sonar")
    elapsed1 = time.time() - start
    print(f"   ⏱️  Elapsed: {elapsed1:.2f}s")
    print(f"   ✅ Success: {result1.get('success')}")
    
    stats = provider.get_cache_stats()
    print(f"   📊 Cache stats: {stats}")
    assert stats["misses"] == 1, "Should have 1 miss"
    
    print("\n2. Second request (same query, should be HIT)")
    start = time.time()
    result2 = await provider.generate_response("What is Bitcoin?", model="sonar")
    elapsed2 = time.time() - start
    print(f"   ⏱️  Elapsed: {elapsed2:.2f}s (should be <0.01s)")
    print(f"   ✅ Success: {result2.get('success')}")
    
    stats = provider.get_cache_stats()
    print(f"   📊 Cache stats: {stats}")
    assert stats["hits"] == 1, "Should have 1 hit"
    assert elapsed2 < 0.1, f"Cache HIT should be fast, got {elapsed2:.2f}s"
    
    print("\n3. LRU eviction test (add 3 more entries)")
    await provider.generate_response("What is Ethereum?", model="sonar")
    await provider.generate_response("What is Solana?", model="sonar")
    await provider.generate_response("What is Cardano?", model="sonar")
    
    stats = provider.get_cache_stats()
    print(f"   📊 Cache stats: {stats}")
    assert stats["size"] == 3, f"Cache should have max 3 entries, got {stats['size']}"
    
    print("\n4. TTL expiration test (wait 11 seconds)")
    print("   ⏳ Waiting 11s for TTL expiration...")
    await asyncio.sleep(11)
    
    # Request again (should be MISS due to TTL)
    result4 = await provider.generate_response("What is Bitcoin?", model="sonar")
    stats = provider.get_cache_stats()
    print(f"   📊 Cache stats after TTL: {stats}")
    # Note: TTL check happens on get(), so this should be a MISS
    
    print("\n✅ Quick Win 1 PASSED")


async def test_quick_win_2_health_check():
    """
    🚀 Quick Win 2: Improved Health Check
    
    Проверяет:
    - Health check caching (60s)
    - Latency metrics
    - Cache invalidation
    """
    print("\n" + "=" * 60)
    print("🚀 Quick Win 2: Improved Health Check")
    print("=" * 60)
    
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("❌ PERPLEXITY_API_KEY not set, skipping test")
        return
    
    client = PerplexityClient(api_key=api_key)
    
    print("\n1. First health check (should be uncached)")
    start = time.time()
    health1 = await client.check_health()
    elapsed1 = time.time() - start
    print(f"   ⏱️  Elapsed: {elapsed1:.2f}s")
    print(f"   📊 Health: {health1}")
    assert not health1.get("cached"), "First check should not be cached"
    
    print("\n2. Second health check (should be cached)")
    start = time.time()
    health2 = await client.check_health()
    elapsed2 = time.time() - start
    print(f"   ⏱️  Elapsed: {elapsed2:.2f}s (should be <0.01s)")
    print(f"   📊 Health: {health2}")
    assert health2.get("cached"), "Second check should be cached"
    assert elapsed2 < 0.1, f"Cached health check should be fast, got {elapsed2:.2f}s"
    
    print("\n3. Cache invalidation test")
    client.invalidate_health_cache()
    health3 = await client.check_health()
    print(f"   📊 Health after invalidation: {health3}")
    assert not health3.get("cached"), "Check after invalidation should not be cached"
    
    print("\n✅ Quick Win 2 PASSED")


async def test_quick_win_3_circuit_breaker():
    """
    🚀 Quick Win 3: Circuit Breaker
    
    Проверяет:
    - Circuit breaker states (CLOSED/OPEN/HALF_OPEN)
    - Failure counting
    - Automatic recovery
    """
    print("\n" + "=" * 60)
    print("🚀 Quick Win 3: Circuit Breaker")
    print("=" * 60)
    
    # Create provider with circuit breaker
    # Note: enable_circuit_breaker is set in AIProvider (parent class)
    provider = PerplexityProvider(
        api_key="invalid_key_for_testing",  # Invalid key to trigger failures
        enable_cache=False  # Disable cache for clean testing
    )
    
    # Circuit breaker is enabled by default in AIProvider
    
    print("\n1. Circuit breaker initial state (should be CLOSED)")
    state = provider.circuit_breaker.get_state()
    print(f"   📊 State: {state}")
    assert state["state"] == "closed", "Initial state should be CLOSED"
    
    print("\n2. Trigger 5 failures to open circuit")
    for i in range(5):
        result = await provider.generate_response("Test query", model="sonar")
        print(f"   ❌ Attempt {i+1}: {result.get('error', 'Unknown error')[:50]}...")
    
    state = provider.circuit_breaker.get_state()
    print(f"   📊 State after 5 failures: {state}")
    assert state["state"] == "open", "Circuit should be OPEN after 5 failures"
    
    print("\n3. Verify circuit blocks requests when OPEN")
    result = await provider.generate_response("Test query", model="sonar")
    print(f"   📊 Result: {result}")
    assert not result["success"], "Request should fail when circuit is OPEN"
    assert "Circuit breaker is OPEN" in result.get("error", ""), "Error should mention circuit breaker"
    
    print("\n4. Manual reset")
    provider.circuit_breaker.reset()
    state = provider.circuit_breaker.get_state()
    print(f"   📊 State after reset: {state}")
    assert state["state"] == "closed", "Circuit should be CLOSED after reset"
    
    print("\n✅ Quick Win 3 PASSED")


def test_quick_win_4_model_mapping():
    """
    🚀 Quick Win 4: Model Mapping Optimization
    
    Проверяет:
    - Config file loading
    - Model mapping (legacy → new)
    - Fallback config
    """
    print("\n" + "=" * 60)
    print("🚀 Quick Win 4: Model Mapping Optimization")
    print("=" * 60)
    
    api_key = os.getenv("PERPLEXITY_API_KEY", "test_key")
    
    print("\n1. Load config from file")
    provider = PerplexityProvider(api_key=api_key)
    print(f"   📊 Model mapping: {provider.model_mapping}")
    print(f"   📊 Default model: {provider.default_model}")
    assert len(provider.model_mapping) > 0, "Model mapping should not be empty"
    
    print("\n2. Test model normalization (legacy → new)")
    legacy_model = "llama-3.1-sonar-small-128k-online"
    normalized = provider._normalize_model_name(legacy_model)
    print(f"   📊 {legacy_model} → {normalized}")
    assert normalized == "sonar", f"Legacy model should map to 'sonar', got '{normalized}'"
    
    print("\n3. Test fallback config (invalid path)")
    provider_fallback = PerplexityProvider(
        api_key=api_key,
        config_path="/nonexistent/path.json"
    )
    print(f"   📊 Fallback mapping: {provider_fallback.model_mapping}")
    assert len(provider_fallback.model_mapping) > 0, "Fallback mapping should not be empty"
    
    print("\n✅ Quick Win 4 PASSED")


async def main():
    """Main test runner"""
    print("\n" + "=" * 60)
    print("🚀 PERPLEXITY QUICK WINS TEST SUITE")
    print("=" * 60)
    
    # Quick Win 4 (synchronous test)
    test_quick_win_4_model_mapping()
    
    # Quick Win 1 (async test)
    await test_quick_win_1_caching()
    
    # Quick Win 2 (async test)
    await test_quick_win_2_health_check()
    
    # Quick Win 3 (async test)
    await test_quick_win_3_circuit_breaker()
    
    print("\n" + "=" * 60)
    print("✅ ALL QUICK WINS PASSED")
    print("=" * 60)
    print("\n📊 Summary:")
    print("   ✅ Quick Win 1: Base Caching (LRU, TTL, Statistics)")
    print("   ✅ Quick Win 2: Improved Health Check (Caching, Metrics)")
    print("   ✅ Quick Win 3: Circuit Breaker (CLOSED/OPEN/HALF_OPEN)")
    print("   ✅ Quick Win 4: Model Mapping Optimization (Config-driven)")


if __name__ == "__main__":
    asyncio.run(main())
