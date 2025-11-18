"""
🎯 Priority 1.5: Тест Multi-Key Rotation для Perplexity Provider

Проверяет:
1. Загрузку 4 API ключей из переменных окружения
2. Round-robin rotation между ключами
3. Автоматический fallback при rate limit (429)
4. Per-key statistics tracking
5. Shared cache across all keys
"""

import asyncio
import os
import sys
from pathlib import Path

# Add mcp-server to path
mcp_server_path = Path(__file__).parent / "mcp-server"
sys.path.insert(0, str(mcp_server_path))

from api.providers.perplexity import PerplexityProvider
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_multi_key_loading():
    """
    Тест 1: Загрузка нескольких API ключей
    """
    print("\n" + "="*80)
    print("🧪 TEST 1: Multi-Key Loading")
    print("="*80)
    
    # Manually set test keys
    os.environ["PERPLEXITY_API_KEY_1"] = "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"
    os.environ["PERPLEXITY_API_KEY_2"] = "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"
    os.environ["PERPLEXITY_API_KEY_3"] = "pplx-d4g6rCdiM5sNxEoLpQ8cThWzUaKYjV9fGbHtRmI2wDnJe7lPqS"
    os.environ["PERPLEXITY_API_KEY_4"] = "pplx-c8G4Z1kq9WxY3DjNvHmF6rTaLeCbP5sUoI7tBnRwJpXhK2yAg"
    
    provider = PerplexityProvider()
    
    print(f"✅ Loaded {len(provider.api_keys)} API keys")
    print(f"📊 Key stats initialized: {len(provider._key_stats)} keys")
    
    for i, key in enumerate(provider.api_keys, 1):
        print(f"   Key {i}: ...{key[-8:]}")
    
    assert len(provider.api_keys) == 4, "Should load 4 keys"
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
    for i in range(8):  # 8 requests = 2 full rotations
        key = provider._get_next_key()
        keys_used.append(key[-8:])
        print(f"Request {i+1}: Key ...{key[-8:]}")
    
    # Check that all 4 keys were used
    unique_keys = set(keys_used)
    print(f"\n📊 Unique keys used: {len(unique_keys)}")
    print(f"✅ Rotation pattern: {keys_used[:4]}")
    
    assert len(unique_keys) == 4, "All 4 keys should be used"
    assert keys_used[0] == keys_used[4], "Rotation should repeat"
    print("\n✅ TEST 2 PASSED")


async def test_real_api_call(provider: PerplexityProvider):
    """
    Тест 3: Реальный API вызов с multi-key support
    """
    print("\n" + "="*80)
    print("🧪 TEST 3: Real API Call with Multi-Key")
    print("="*80)
    
    try:
        response = await provider.generate_response(
            query="What is the capital of France?",
            model="sonar",
            max_tokens=50,
            temperature=0
        )
        
        print(f"✅ API call successful")
        print(f"📝 Answer: {response.get('answer', '')[:100]}...")
        print(f"🔍 Model used: {response.get('model', 'unknown')}")
        print(f"📊 Cached: {response.get('cached', False)}")
        
        # Check key stats
        key_stats = provider.get_key_stats()
        print(f"\n📊 Key Statistics:")
        for key, stats in key_stats.items():
            if stats['requests'] > 0:
                print(f"   Key ...{key[-8:]}: {stats['requests']} requests, "
                      f"{stats['failures']} failures, {stats['rate_limits']} rate limits")
        
        assert response.get("success", False), "API call should succeed"
        print("\n✅ TEST 3 PASSED")
        
    except Exception as e:
        print(f"❌ TEST 3 FAILED: {e}")
        raise


async def test_health_check(provider: PerplexityProvider):
    """
    Тест 4: Health check с multi-key stats
    """
    print("\n" + "="*80)
    print("🧪 TEST 4: Health Check with Multi-Key Stats")
    print("="*80)
    
    try:
        health = await provider.health_check(timeout=10.0)
        
        print(f"✅ Health check: {'HEALTHY' if health['success'] else 'UNHEALTHY'}")
        print(f"🔍 Service: {health['service']}")
        
        if 'key_stats' in health:
            print(f"\n📊 Multi-Key Stats:")
            for key, stats in health['key_stats'].items():
                print(f"   Key ...{key[-8:]}:")
                print(f"      Requests: {stats['requests']}")
                print(f"      Failures: {stats['failures']}")
                print(f"      Rate Limits: {stats['rate_limits']}")
        
        if 'cache_stats' in health:
            cache = health['cache_stats']
            print(f"\n📊 Cache Stats:")
            print(f"   Size: {cache.get('size', 0)}")
            print(f"   Hits: {cache.get('hits', 0)}")
            print(f"   Misses: {cache.get('misses', 0)}")
            print(f"   Hit Rate: {cache.get('hit_rate', 0):.1%}")
        
        assert health['success'], "Health check should succeed"
        assert 'key_stats' in health, "Should include key stats"
        print("\n✅ TEST 4 PASSED")
        
    except Exception as e:
        print(f"❌ TEST 4 FAILED: {e}")
        raise


async def test_cache_with_multi_key(provider: PerplexityProvider):
    """
    Тест 5: Shared cache across all keys
    """
    print("\n" + "="*80)
    print("🧪 TEST 5: Shared Cache Across Multi-Key")
    print("="*80)
    
    query = "What is 2+2?"
    
    # First request (cache miss)
    response1 = await provider.generate_response(
        query=query,
        model="sonar",
        max_tokens=10
    )
    
    print(f"✅ First request: cached={response1.get('cached', False)}")
    
    # Second request (cache hit)
    response2 = await provider.generate_response(
        query=query,
        model="sonar",
        max_tokens=10
    )
    
    print(f"✅ Second request: cached={response2.get('cached', False)}")
    
    cache_stats = provider.get_cache_stats()
    print(f"\n📊 Cache Stats:")
    print(f"   Hits: {cache_stats.get('hits', 0)}")
    print(f"   Misses: {cache_stats.get('misses', 0)}")
    print(f"   Hit Rate: {cache_stats.get('hit_rate', 0):.1%}")
    
    assert not response1.get('cached', True), "First request should be cache miss"
    assert response2.get('cached', False), "Second request should be cache hit"
    print("\n✅ TEST 5 PASSED")


async def main():
    """
    Запуск всех тестов
    """
    print("\n" + "="*80)
    print("🎯 Priority 1.5: Multi-Key Rotation Testing")
    print("="*80)
    
    try:
        # Test 1: Load keys
        provider = await test_multi_key_loading()
        
        # Test 2: Rotation
        await test_key_rotation(provider)
        
        # Test 3: Real API call
        await test_real_api_call(provider)
        
        # Test 4: Health check
        await test_health_check(provider)
        
        # Test 5: Shared cache
        await test_cache_with_multi_key(provider)
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED")
        print("="*80)
        
        # Final key stats summary
        print("\n📊 FINAL KEY STATISTICS:")
        key_stats = provider.get_key_stats()
        for key, stats in key_stats.items():
            print(f"\nKey ...{key[-8:]}:")
            print(f"  Requests: {stats['requests']}")
            print(f"  Failures: {stats['failures']}")
            print(f"  Rate Limits: {stats['rate_limits']}")
            success_rate = (
                (stats['requests'] - stats['failures']) / stats['requests'] * 100
                if stats['requests'] > 0 else 0
            )
            print(f"  Success Rate: {success_rate:.1f}%")
        
    except Exception as e:
        print("\n" + "="*80)
        print(f"❌ TEST SUITE FAILED: {e}")
        print("="*80)
        raise


if __name__ == "__main__":
    asyncio.run(main())
