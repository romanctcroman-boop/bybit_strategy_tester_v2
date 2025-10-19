"""
Тест интеграции Redis

Проверяет работу Redis manager и cache service.
"""

import pytest
from backend.services.redis_manager import redis_manager
from backend.services.cache_service import CacheService


def test_redis_connection():
    """Тест подключения к Redis"""
    assert redis_manager.is_available, "Redis should be available"
    
    # Проверка PING
    assert redis_manager.client.ping(), "Redis should respond to PING"
    
    print("✅ Redis connection test passed")


def test_redis_basic_operations():
    """Тест базовых операций Redis"""
    # SET/GET
    assert redis_manager.set("test_key", "test_value", ttl=60)
    assert redis_manager.get("test_key") == "test_value"
    
    # JSON serialization
    test_data = {"symbol": "BTCUSDT", "price": 50000, "volume": 123.45}
    assert redis_manager.set("test_json", test_data, ttl=60)
    cached_data = redis_manager.get("test_json")
    assert cached_data == test_data
    
    # DELETE
    assert redis_manager.delete("test_key")
    assert redis_manager.get("test_key") is None
    
    # EXISTS
    redis_manager.set("test_exists", "value")
    assert redis_manager.exists("test_exists")
    redis_manager.delete("test_exists")
    assert not redis_manager.exists("test_exists")
    
    print("✅ Redis basic operations test passed")


def test_cache_service():
    """Тест CacheService"""
    cache = CacheService()
    
    assert cache.is_available(), "CacheService should be available"
    
    # Кэширование с namespace
    test_data = {"strategy_id": 1, "result": {"sharpe": 1.5, "return": 0.25}}
    assert cache.set(
        key="strategy_1",
        value=test_data,
        ttl=300,
        namespace=CacheService.NS_BACKTEST
    )
    
    cached = cache.get("strategy_1", namespace=CacheService.NS_BACKTEST)
    assert cached == test_data
    
    # Удаление
    cache.delete("strategy_1", namespace=CacheService.NS_BACKTEST)
    assert cache.get("strategy_1", namespace=CacheService.NS_BACKTEST) is None
    
    print("✅ CacheService test passed")


def test_redis_pattern_operations():
    """Тест операций с паттернами"""
    # Создать несколько ключей
    redis_manager.set("candles:BTCUSDT:1h", {"data": "test1"})
    redis_manager.set("candles:ETHUSDT:1h", {"data": "test2"})
    redis_manager.set("candles:SOLUSDT:1h", {"data": "test3"})
    
    # Очистить по паттерну
    deleted = redis_manager.clear_pattern("candles:*")
    assert deleted >= 3, f"Should delete at least 3 keys, deleted {deleted}"
    
    # Проверить что ключи удалены
    assert redis_manager.get("candles:BTCUSDT:1h") is None
    
    print("✅ Redis pattern operations test passed")


def test_redis_stats():
    """Тест получения статистики Redis"""
    stats = redis_manager.get_stats()
    
    assert stats["available"] is True
    assert "used_memory" in stats
    assert "connected_clients" in stats
    
    print(f"📊 Redis stats: {stats}")
    print("✅ Redis stats test passed")


if __name__ == "__main__":
    print("\n" + "="*50)
    print("REDIS INTEGRATION TESTS")
    print("="*50 + "\n")
    
    try:
        test_redis_connection()
        test_redis_basic_operations()
        test_cache_service()
        test_redis_pattern_operations()
        test_redis_stats()
        
        print("\n" + "="*50)
        print("✅ ALL TESTS PASSED!")
        print("="*50 + "\n")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        raise
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        raise
