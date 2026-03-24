"""
Tests for Redis Context Cache

Run: pytest tests/monitoring/test_redis_cache.py -v

Note: Requires Redis server running on localhost:6379
      Or set REDIS_HOST environment variable
"""

import os
import socket
import sys
import time

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import pytest

from backend.monitoring.redis_cache import (
    REDIS_AVAILABLE,
    RedisCacheConfig,
    RedisContextCache,
    get_redis_cache,
)


def _redis_reachable() -> bool:
    """Quick TCP check — returns False in < 0.5 s when Redis is down."""
    if not REDIS_AVAILABLE:
        return False
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


_REDIS_RUNNING = _redis_reachable()

# Skip all tests if redis package not installed OR Redis not reachable
pytestmark = pytest.mark.skipif(
    not _REDIS_RUNNING,
    reason="Redis not reachable — start Redis to run these tests",
)


class TestRedisContextCache:
    """Tests for RedisContextCache."""

    @pytest.fixture
    def redis_config(self):
        """Get Redis config from environment or use defaults."""
        return RedisCacheConfig(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=1,  # Use DB 1 for tests
            password=os.getenv("REDIS_PASSWORD"),
            default_ttl=300,
            prefix="test:prompts:",
        )

    @pytest.fixture
    def cache(self, redis_config):
        """Create Redis cache instance."""
        return RedisContextCache(redis_config)

    @pytest.fixture(autouse=True)
    def cleanup(self, cache):
        """Clean up after each test."""
        yield
        cache.clear()

    def test_redis_connection(self, cache):
        """Test Redis connection."""
        stats = cache.get_stats()

        # Should have backend info
        assert "backend" in stats

        # If connected, should be redis
        if not cache.is_using_fallback():
            assert stats["backend"] == "redis"
            assert stats["connected"] is True

    def test_set_and_get(self, cache):
        """Test basic set and get."""
        data = {"symbol": "BTCUSDT", "regime": "trending"}

        # Set
        success = cache.set("test_key", data, ttl=60)
        assert success is True

        # Get
        result = cache.get("test_key")
        assert result == data

    def test_get_nonexistent(self, cache):
        """Test getting nonexistent key."""
        result = cache.get("nonexistent_key_12345")
        assert result is None

    def test_ttl_expiration(self, cache):
        """Test TTL-based expiration."""
        data = {"test": "data"}

        # Set with short TTL
        cache.set("ttl_key", data, ttl=1)

        # Should exist immediately
        assert cache.get("ttl_key") == data

        # Wait for expiration
        time.sleep(1.5)

        # Should be expired
        assert cache.get("ttl_key") is None

    def test_delete(self, cache):
        """Test deleting key."""
        data = {"test": "data"}

        # Set
        cache.set("delete_key", data)

        # Verify exists
        assert cache.get("delete_key") == data

        # Delete
        success = cache.delete("delete_key")
        assert success is True

        # Verify deleted
        assert cache.get("delete_key") is None

    def test_exists(self, cache):
        """Test key existence check."""
        data = {"test": "data"}

        # Should not exist
        assert cache.exists("exists_key") is False

        # Set
        cache.set("exists_key", data)

        # Should exist
        assert cache.exists("exists_key") is True

    def test_clear(self, cache):
        """Test clearing cache."""
        # Set multiple keys
        cache.set("key1", {"data": 1})
        cache.set("key2", {"data": 2})
        cache.set("key3", {"data": 3})

        # Clear
        deleted = cache.clear()

        # Should delete at least 3 keys
        assert deleted >= 3

        # Verify cleared
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is None

    def test_stats(self, cache):
        """Test cache statistics."""
        stats = cache.get_stats()

        assert isinstance(stats, dict)
        assert "backend" in stats
        assert "size" in stats or "connected" in stats

    def test_fallback_to_memory(self):
        """Test fallback to in-memory cache."""
        # Create config with disabled Redis
        config = RedisCacheConfig(
            enabled=False,
            fallback_to_memory=True,
        )

        cache = RedisContextCache(config)

        # Should use fallback
        assert cache.is_using_fallback() is True

        # Should still work (in-memory)
        data = {"test": "data"}
        cache.set("fallback_key", data)
        result = cache.get("fallback_key")
        assert result == data

    def test_reconnect(self, cache):
        """Test reconnection."""
        # Disconnect by setting flag
        cache._using_fallback = True

        # Try to reconnect
        success = cache.reconnect()

        # May succeed or fail depending on Redis availability
        assert isinstance(success, bool)

    def test_json_serialization(self, cache):
        """Test JSON serialization of complex data."""
        data = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "float": 3.14159,
            "bool": True,
            "null": None,
        }

        # Set
        cache.set("complex_key", data)

        # Get
        result = cache.get("complex_key")

        # Should match
        assert result == data

    def test_unicode_data(self, cache):
        """Test Unicode data handling."""
        data = {
            "emoji": "🚀",
            "chinese": "中文",
            "russian": "Привет",
            "arabic": "مرحبا",
        }

        # Set
        cache.set("unicode_key", data)

        # Get
        result = cache.get("unicode_key")

        # Should match
        assert result == data


class TestRedisCacheConfig:
    """Tests for RedisCacheConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = RedisCacheConfig()

        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.default_ttl == 300
        assert config.enabled is True
        assert config.fallback_to_memory is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = RedisCacheConfig(
            host="redis.example.com",
            port=6380,
            db=2,
            password="secret",
            default_ttl=600,
            prefix="custom:",
        )

        assert config.host == "redis.example.com"
        assert config.port == 6380
        assert config.db == 2
        assert config.password == "secret"
        assert config.default_ttl == 600
        assert config.prefix == "custom:"


class TestGlobalCache:
    """Tests for global cache functions."""

    def test_get_redis_cache_singleton(self):
        """Test singleton pattern."""
        cache1 = get_redis_cache()
        cache2 = get_redis_cache()

        # Should be same instance
        assert cache1 is cache2

    def test_init_from_env(self):
        """Test initialization from environment."""
        # Set env vars
        os.environ["REDIS_HOST"] = "localhost"
        os.environ["REDIS_PORT"] = "6379"
        os.environ["REDIS_DB"] = "0"

        from backend.monitoring.redis_cache import init_redis_cache_from_env

        cache = init_redis_cache_from_env()

        # Should create cache instance
        assert cache is not None

        # Cleanup
        del os.environ["REDIS_HOST"]
        del os.environ["REDIS_PORT"]
        del os.environ["REDIS_DB"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
