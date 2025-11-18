"""
🎯 Priority 1.5: Unit-тесты Multi-Key Rotation (без реальных API вызовов)

Тестирует:
1. Загрузку 4 API ключей
2. Round-robin rotation
3. Per-key statistics tracking
4. Rate limit handling (429) с автоматическим failover
5. Shared cache across keys
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

# Add mcp-server to path
mcp_server_path = Path(__file__).parent / "mcp-server"
sys.path.insert(0, str(mcp_server_path))

from api.providers.perplexity import PerplexityProvider


async def test_multi_key_loading():
    """
    Тест 1: Загрузка нескольких API ключей
    """
    print("\n" + "="*80)
    print("🧪 TEST 1: Multi-Key Loading")
    print("="*80)
    
    # Set test keys
    os.environ["PERPLEXITY_API_KEY_1"] = "test-key-1"
    os.environ["PERPLEXITY_API_KEY_2"] = "test-key-2"
    os.environ["PERPLEXITY_API_KEY_3"] = "test-key-3"
    os.environ["PERPLEXITY_API_KEY_4"] = "test-key-4"
    
    provider = PerplexityProvider()
    
    print(f"✅ Loaded {len(provider.api_keys)} API keys")
    print(f"📊 Key stats initialized: {len(provider._key_stats)} keys")
    
    for i, key in enumerate(provider.api_keys, 1):
        print(f"   Key {i}: {key}")
        assert key in provider._key_stats, f"Key {key} should have stats"
    
    assert len(provider.api_keys) == 4, "Should load 4 keys"
    assert provider.current_key_index == 0, "Should start at index 0"
    
    print("\n✅ TEST 1 PASSED")
    return provider


async def test_key_rotation(provider: PerplexityProvider):
    """
    Тест 2: Round-robin rotation между ключами
    """
    print("\n" + "="*80)
    print("🧪 TEST 2: Round-Robin Key Rotation")
    print("="*80)
    
    keys_used = []
    for i in range(12):  # 12 requests = 3 full rotations
        key = provider._get_next_key()
        keys_used.append(key)
        print(f"Request {i+1}: Key {key}")
    
    # Check pattern
    unique_keys = set(keys_used)
    print(f"\n📊 Unique keys used: {len(unique_keys)}")
    print(f"✅ Rotation pattern (first 4): {keys_used[:4]}")
    print(f"✅ Rotation pattern (second 4): {keys_used[4:8]}")
    print(f"✅ Rotation pattern (third 4): {keys_used[8:12]}")
    
    assert len(unique_keys) == 4, "All 4 keys should be used"
    assert keys_used[0] == keys_used[4] == keys_used[8], "First key should repeat every 4 requests"
    assert keys_used[1] == keys_used[5] == keys_used[9], "Second key should repeat every 4 requests"
    
    print("\n✅ TEST 2 PASSED")


async def test_key_stats_tracking():
    """
    Тест 3: Per-key statistics tracking
    """
    print("\n" + "="*80)
    print("🧪 TEST 3: Per-Key Statistics Tracking")
    print("="*80)
    
    provider = PerplexityProvider(
        api_keys=["key1", "key2", "key3", "key4"]
    )
    
    # Simulate requests with different outcomes
    provider._update_key_stats("key1", success=True, is_rate_limit=False)
    provider._update_key_stats("key1", success=True, is_rate_limit=False)
    provider._update_key_stats("key2", success=False, is_rate_limit=True)
    provider._update_key_stats("key3", success=False, is_rate_limit=False)
    provider._update_key_stats("key4", success=True, is_rate_limit=False)
    
    stats = provider.get_key_stats()
    
    print(f"📊 Key Statistics:")
    for key, data in stats.items():
        print(f"   {key}:")
        print(f"      Requests: {data['requests']}")
        print(f"      Failures: {data['failures']}")
        print(f"      Rate Limits: {data['rate_limits']}")
    
    assert stats["key1"]["requests"] == 2, "key1 should have 2 requests"
    assert stats["key1"]["failures"] == 0, "key1 should have 0 failures"
    assert stats["key2"]["rate_limits"] == 1, "key2 should have 1 rate limit"
    assert stats["key3"]["failures"] == 1, "key3 should have 1 failure"
    
    print("\n✅ TEST 3 PASSED")


async def test_rate_limit_handling():
    """
    Тест 4: Rate limit (429) handling с failover
    """
    print("\n" + "="*80)
    print("🧪 TEST 4: Rate Limit Handling with Failover")
    print("="*80)
    
    provider = PerplexityProvider(
        api_keys=["key1", "key2", "key3", "key4"]
    )
    
    # Simulate rate limit on key1
    import time
    current_time = time.time()
    provider._update_key_stats("key1", success=False, is_rate_limit=True)
    
    # Get next key should skip key1 (rate limited)
    next_key = provider._get_next_key()
    
    print(f"✅ Key1 rate limited, next key: {next_key}")
    assert next_key != "key1", "Should skip rate-limited key1"
    
    # Wait and check if key1 becomes available
    provider._key_stats["key1"]["last_rate_limit"] = current_time - 61  # 61 seconds ago
    
    # Reset rotation index to test key1 availability
    provider.current_key_index = 0
    next_key_after_cooldown = provider._get_next_key()
    
    print(f"✅ After cooldown (60s), key available: {next_key_after_cooldown}")
    assert next_key_after_cooldown == "key1", "Key1 should be available after cooldown"
    
    print("\n✅ TEST 4 PASSED")


async def test_make_request_with_failover():
    """
    Тест 5: _make_request с автоматическим failover при 429
    """
    print("\n" + "="*80)
    print("🧪 TEST 5: _make_request with Automatic Failover")
    print("="*80)
    
    provider = PerplexityProvider(
        api_keys=["key1", "key2", "key3", "key4"]
    )
    
    # Mock responses: key1 = 429, key2 = 200 OK
    mock_response_429 = MagicMock()
    mock_response_429.status_code = 429
    mock_response_429.text = "Rate limit exceeded"
    
    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {
        "choices": [{"message": {"content": "Test response"}}],
        "usage": {"total_tokens": 10},
        "model": "sonar"
    }
    
    call_count = 0
    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        # First call (key1) returns 429
        if call_count == 1:
            return mock_response_429
        # Second call (key2) returns 200
        else:
            return mock_response_200
    
    # Patch httpx.AsyncClient
    with patch('httpx.AsyncClient') as mock_client:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.post = mock_post
        mock_client.return_value = mock_context
        
        # Make request
        payload = {"model": "sonar", "messages": [{"role": "user", "content": "test"}]}
        
        try:
            result = await provider._make_request(payload, timeout=10.0)
            
            print(f"✅ Request succeeded after {call_count} attempts")
            print(f"📊 Response: {result.get('choices', [{}])[0].get('message', {}).get('content', '')}")
            
            # Check that key1 was rate limited and key2 succeeded
            key1_stats = provider._key_stats["key1"]
            key2_stats = provider._key_stats["key2"]
            
            print(f"\n📊 Key1 stats: requests={key1_stats['requests']}, rate_limits={key1_stats['rate_limits']}")
            print(f"📊 Key2 stats: requests={key2_stats['requests']}, failures={key2_stats['failures']}")
            
            assert key1_stats["rate_limits"] == 1, "Key1 should have 1 rate limit"
            assert key2_stats["requests"] == 1, "Key2 should have 1 successful request"
            assert call_count == 2, "Should take 2 attempts (key1 fails, key2 succeeds)"
            
            print("\n✅ TEST 5 PASSED")
            
        except Exception as e:
            print(f"❌ TEST 5 FAILED: {e}")
            raise


async def test_cache_integration():
    """
    Тест 6: Shared cache across all keys
    """
    print("\n" + "="*80)
    print("🧪 TEST 6: Shared Cache Across Multi-Key")
    print("="*80)
    
    provider = PerplexityProvider(
        api_keys=["key1", "key2", "key3", "key4"],
        enable_cache=True
    )
    
    # Manually populate cache
    query = "test query"
    model = "sonar"
    response_data = {
        "answer": "cached answer",
        "success": True
    }
    
    provider.cache.set(query, model, response_data)
    
    # Check cache hit
    cached = provider.cache.get(query, model)
    
    print(f"✅ Cache populated")
    print(f"✅ Cache hit: {cached is not None}")
    print(f"📊 Cache stats: {provider.cache.get_stats()}")
    
    assert cached is not None, "Should get cached response"
    assert cached["answer"] == "cached answer", "Should return correct cached data"
    
    # Check that cache is shared (same for all keys)
    key_before = provider._get_next_key()
    cached2 = provider.cache.get(query, model)
    key_after = provider._get_next_key()
    
    print(f"✅ Key before: {key_before}, Key after: {key_after}")
    print(f"✅ Cache shared: {cached2 is not None}")
    
    assert cached2 is not None, "Cache should be shared across keys"
    
    print("\n✅ TEST 6 PASSED")


async def test_health_check_with_multi_key():
    """
    Тест 7: Health check включает статистику всех ключей
    """
    print("\n" + "="*80)
    print("🧪 TEST 7: Health Check with Multi-Key Stats")
    print("="*80)
    
    provider = PerplexityProvider(
        api_keys=["key1", "key2", "key3", "key4"]
    )
    
    # Simulate some activity
    provider._update_key_stats("key1", success=True)
    provider._update_key_stats("key2", success=False, is_rate_limit=True)
    provider._update_key_stats("key3", success=True)
    
    # Mock health check response
    with patch.object(provider, 'generate_response', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {"success": True}
        
        health = await provider.health_check(timeout=5.0)
        
        print(f"✅ Health check: {health['success']}")
        print(f"📊 Service: {health['service']}")
        
        if 'key_stats' in health:
            print(f"\n📊 Multi-Key Stats:")
            for key, stats in health['key_stats'].items():
                print(f"   {key}:")
                print(f"      Requests: {stats['requests']}")
                print(f"      Failures: {stats['failures']}")
                print(f"      Rate Limits: {stats['rate_limits']}")
        
        assert 'key_stats' in health, "Health check should include key_stats"
        assert health['key_stats']["key1"]["requests"] == 1, "Key1 should have 1 request"
        assert health['key_stats']["key2"]["rate_limits"] == 1, "Key2 should have 1 rate limit"
        
        print("\n✅ TEST 7 PASSED")


async def main():
    """
    Запуск всех unit-тестов
    """
    print("\n" + "="*80)
    print("🎯 Priority 1.5: Multi-Key Rotation Unit Testing")
    print("="*80)
    
    try:
        # Test 1: Load keys
        provider = await test_multi_key_loading()
        
        # Test 2: Rotation
        await test_key_rotation(provider)
        
        # Test 3: Stats tracking
        await test_key_stats_tracking()
        
        # Test 4: Rate limit handling
        await test_rate_limit_handling()
        
        # Test 5: Failover in _make_request
        await test_make_request_with_failover()
        
        # Test 6: Shared cache
        await test_cache_integration()
        
        # Test 7: Health check
        await test_health_check_with_multi_key()
        
        print("\n" + "="*80)
        print("✅ ALL UNIT TESTS PASSED")
        print("="*80)
        print("\n📊 Multi-Key Rotation Implementation:")
        print("   ✅ 4-key support")
        print("   ✅ Round-robin rotation")
        print("   ✅ Per-key statistics tracking")
        print("   ✅ Automatic failover on 429 (rate limit)")
        print("   ✅ 60-second cooldown after rate limit")
        print("   ✅ Shared cache across all keys")
        print("   ✅ Health check with multi-key stats")
        
    except Exception as e:
        print("\n" + "="*80)
        print(f"❌ TEST SUITE FAILED: {e}")
        print("="*80)
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
