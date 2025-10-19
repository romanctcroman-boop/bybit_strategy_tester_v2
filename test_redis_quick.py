"""
Simple Redis Integration Test Script

Run this directly with Python to test Redis connectivity.
"""

import sys
sys.path.insert(0, 'D:\\bybit_strategy_tester_v2')

from backend.services.redis_manager import redis_manager
from backend.services.cache_service import CacheService

print("\n" + "="*60)
print("REDIS INTEGRATION TEST")
print("="*60 + "\n")

# Test 1: Redis Connection
print("[Test 1] Testing Redis connection...")
try:
    if redis_manager.is_available:
        print("✅ PASS: Redis is available")
        ping_result = redis_manager.client.ping()
        if ping_result:
            print("✅ PASS: Redis responds to PING")
        else:
            print("❌ FAIL: Redis not responding to PING")
    else:
        print("❌ FAIL: Redis is not available")
        sys.exit(1)
except Exception as e:
    print(f"❌ FAIL: {e}")
    sys.exit(1)

# Test 2: Basic Operations
print("\n[Test 2] Testing basic operations...")
try:
    # SET/GET
    redis_manager.set("test_key", "test_value", ttl=60)
    value = redis_manager.get("test_key")
    assert value == "test_value", f"Expected 'test_value', got {value}"
    print("✅ PASS: SET/GET works")
    
    # JSON serialization
    test_data = {"symbol": "BTCUSDT", "price": 50000, "volume": 123.45}
    redis_manager.set("test_json", test_data, ttl=60)
    cached_data = redis_manager.get("test_json")
    assert cached_data == test_data, f"Expected {test_data}, got {cached_data}"
    print("✅ PASS: JSON serialization works")
    
    # DELETE
    redis_manager.delete("test_key")
    value = redis_manager.get("test_key")
    assert value is None, f"Expected None after delete, got {value}"
    print("✅ PASS: DELETE works")
    
    # EXISTS
    redis_manager.set("test_exists", "value")
    assert redis_manager.exists("test_exists"), "Key should exist"
    redis_manager.delete("test_exists")
    assert not redis_manager.exists("test_exists"), "Key should not exist"
    print("✅ PASS: EXISTS works")
    
except Exception as e:
    print(f"❌ FAIL: {e}")
    sys.exit(1)

# Test 3: CacheService
print("\n[Test 3] Testing CacheService...")
try:
    cache = CacheService()
    
    assert cache.is_available(), "CacheService should be available"
    print("✅ PASS: CacheService is available")
    
    # Кэширование с namespace
    test_data = {"strategy_id": 1, "result": {"sharpe": 1.5, "return": 0.25}}
    cache.set(
        key="strategy_1",
        value=test_data,
        ttl=300,
        namespace=CacheService.NS_BACKTEST
    )
    
    cached = cache.get("strategy_1", namespace=CacheService.NS_BACKTEST)
    assert cached == test_data, f"Expected {test_data}, got {cached}"
    print("✅ PASS: CacheService SET/GET with namespace works")
    
    # Удаление
    cache.delete("strategy_1", namespace=CacheService.NS_BACKTEST)
    cached = cache.get("strategy_1", namespace=CacheService.NS_BACKTEST)
    assert cached is None, f"Expected None after delete, got {cached}"
    print("✅ PASS: CacheService DELETE works")
    
except Exception as e:
    print(f"❌ FAIL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Pattern Operations
print("\n[Test 4] Testing pattern operations...")
try:
    # Создать несколько ключей
    redis_manager.set("candles:BTCUSDT:1h", {"data": "test1"})
    redis_manager.set("candles:ETHUSDT:1h", {"data": "test2"})
    redis_manager.set("candles:SOLUSDT:1h", {"data": "test3"})
    
    # Очистить по паттерну
    deleted = redis_manager.clear_pattern("candles:*")
    assert deleted >= 3, f"Should delete at least 3 keys, deleted {deleted}"
    print(f"✅ PASS: Deleted {deleted} keys by pattern")
    
    # Проверить что ключи удалены
    assert redis_manager.get("candles:BTCUSDT:1h") is None
    print("✅ PASS: Pattern deletion verified")
    
except Exception as e:
    print(f"❌ FAIL: {e}")
    sys.exit(1)

# Test 5: Redis Stats
print("\n[Test 5] Testing Redis stats...")
try:
    stats = redis_manager.get_stats()
    
    assert stats["available"] is True, "Redis should be available"
    assert "used_memory" in stats, "Stats should include used_memory"
    assert "connected_clients" in stats, "Stats should include connected_clients"
    
    print("✅ PASS: Stats retrieved successfully")
    print(f"   Used Memory: {stats.get('used_memory')}")
    print(f"   Connected Clients: {stats.get('connected_clients')}")
    print(f"   Total Commands: {stats.get('total_commands')}")
    
except Exception as e:
    print(f"❌ FAIL: {e}")
    sys.exit(1)

# Final Summary
print("\n" + "="*60)
print("✅ ALL TESTS PASSED!")
print("="*60)
print("\nRedis integration is working correctly.")
print("You can now use Redis for caching in your application.")
print("\nNext steps:")
print("1. Install RabbitMQ for Celery message broker")
print("2. Install Celery: .venv\\Scripts\\python.exe -m pip install celery==5.3.4")
print("3. Start Celery worker: celery -A backend.celery_app worker -Q backtest -P solo")
print("")
