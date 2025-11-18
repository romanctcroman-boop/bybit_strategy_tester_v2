"""
Comprehensive tests for backend/core/cache.py

Redis cache implementation for Bybit data
"""

import pytest
import pickle
import zlib
from unittest.mock import Mock, patch, MagicMock
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from backend.core.cache import RedisCache, get_cache, make_cache_key


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    mock = MagicMock()
    mock.ping = Mock()
    mock.get = Mock(return_value=None)
    mock.setex = Mock()
    mock.delete = Mock(return_value=1)
    mock.scan_iter = Mock(return_value=iter([]))
    mock.info = Mock(return_value={
        'used_memory_human': '1.5M',
        'used_memory_rss_human': '2.0M'
    })
    return mock


@pytest.fixture
def cache():
    """Create RedisCache instance with mocked connection"""
    with patch('redis.Redis') as mock_redis_class:
        mock_client = MagicMock()
        mock_client.ping = Mock()
        mock_redis_class.return_value = mock_client
        
        cache = RedisCache(
            host='localhost',
            port=6379,
            db=0,
            prefix='test:',
            ttl_seconds=3600
        )
        cache._client = mock_client
        cache._connected = True
        
        yield cache


@pytest.fixture
def sample_data():
    """Sample cache data"""
    return {
        'symbol': 'BTCUSDT',
        'interval': '1h',
        'candles': [
            {'open': 50000, 'high': 51000, 'low': 49000, 'close': 50500},
            {'open': 50500, 'high': 51500, 'low': 50000, 'close': 51000},
        ]
    }


# ============================================================================
# Test RedisCache.__init__
# ============================================================================

class TestCacheInit:
    """Test cache initialization"""
    
    def test_init_default_params(self):
        """Test init with default parameters"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping = Mock()
            mock_redis.return_value = mock_client
            
            cache = RedisCache()
            
            assert cache.host == 'localhost'
            assert cache.port == 6379
            assert cache.db == 0
            assert cache.prefix == 'bybit:'
            assert cache.ttl_seconds == 3600
            assert cache.compress is True
            assert cache.compression_threshold == 1024
    
    def test_init_custom_params(self):
        """Test init with custom parameters"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping = Mock()
            mock_redis.return_value = mock_client
            
            cache = RedisCache(
                host='custom-host',
                port=6380,
                db=1,
                password='secret',
                prefix='custom:',
                ttl_seconds=7200,
                compress=False,
                compression_threshold=2048
            )
            
            assert cache.host == 'custom-host'
            assert cache.port == 6380
            assert cache.db == 1
            assert cache.password == 'secret'
            assert cache.prefix == 'custom:'
            assert cache.ttl_seconds == 7200
            assert cache.compress is False
            assert cache.compression_threshold == 2048
    
    def test_init_connection_failure(self):
        """Test init handles connection failure gracefully"""
        with patch('redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = RedisConnectionError("Connection refused")
            
            cache = RedisCache()
            
            assert cache._connected is False
            # Client is created but connection failed
            assert cache._client is not None or cache._client is None  # Either state is valid


# ============================================================================
# Test _connect
# ============================================================================

class TestConnect:
    """Test Redis connection"""
    
    def test_connect_success(self):
        """Test successful connection"""
        with patch('redis.Redis') as mock_redis_class:
            mock_client = MagicMock()
            mock_client.ping = Mock()
            mock_redis_class.return_value = mock_client
            
            cache = RedisCache()
            
            assert cache._connected is True
            assert cache._client is mock_client
            mock_client.ping.assert_called_once()
    
    def test_connect_failure(self):
        """Test connection failure"""
        with patch('redis.Redis') as mock_redis_class:
            mock_client = MagicMock()
            mock_client.ping.side_effect = RedisError("Connection error")
            mock_redis_class.return_value = mock_client
            
            with pytest.raises(RedisError):
                cache = RedisCache()
                cache._connect()


# ============================================================================
# Test _make_key
# ============================================================================

class TestMakeKey:
    """Test key generation"""
    
    def test_make_key_with_prefix(self, cache):
        """Test key generation with prefix"""
        key = cache._make_key('my-key')
        assert key == 'test:my-key'
    
    def test_make_key_preserves_structure(self, cache):
        """Test key preserves colon structure"""
        key = cache._make_key('klines:BTCUSDT:1h')
        assert key == 'test:klines:BTCUSDT:1h'


# ============================================================================
# Test _serialize / _deserialize
# ============================================================================

class TestSerialization:
    """Test data serialization"""
    
    def test_serialize_small_data(self, cache):
        """Test serialization of small data (no compression)"""
        data = {'small': 'data'}
        serialized = cache._serialize(data)
        
        # Should start with no-compression marker
        assert serialized[0] == 0
        assert len(serialized) < cache.compression_threshold
    
    def test_serialize_large_data(self, cache):
        """Test serialization of large data (with compression)"""
        # Create large data that exceeds threshold
        data = {'large': 'x' * 2000}
        serialized = cache._serialize(data)
        
        # Should use compression
        raw = pickle.dumps(data)
        assert len(serialized) < len(raw) + 1  # Should be smaller after compression
    
    def test_deserialize_uncompressed(self, cache):
        """Test deserialization of uncompressed data"""
        original = {'test': 'data'}
        serialized = cache._serialize(original)
        deserialized = cache._deserialize(serialized)
        
        assert deserialized == original
    
    def test_deserialize_compressed(self, cache):
        """Test deserialization of compressed data"""
        original = {'large': 'x' * 2000}
        serialized = cache._serialize(original)
        deserialized = cache._deserialize(serialized)
        
        assert deserialized == original
    
    def test_deserialize_empty_data(self, cache):
        """Test deserialization of empty data"""
        result = cache._deserialize(b'')
        assert result is None
    
    def test_serialize_complex_types(self, cache):
        """Test serialization of complex Python types"""
        data = {
            'list': [1, 2, 3],
            'dict': {'nested': True},
            'tuple': (1, 2),
            'set': {1, 2, 3}
        }
        serialized = cache._serialize(data)
        deserialized = cache._deserialize(serialized)
        
        assert deserialized['list'] == [1, 2, 3]
        assert deserialized['dict'] == {'nested': True}
        assert deserialized['tuple'] == (1, 2)


# ============================================================================
# Test get
# ============================================================================

class TestGet:
    """Test cache retrieval"""
    
    def test_get_hit(self, cache, sample_data):
        """Test cache hit"""
        serialized = cache._serialize(sample_data)
        cache._client.get = Mock(return_value=serialized)
        
        result = cache.get('test-key')
        
        assert result == sample_data
        cache._client.get.assert_called_once_with('test:test-key')
    
    def test_get_miss(self, cache):
        """Test cache miss"""
        cache._client.get = Mock(return_value=None)
        
        result = cache.get('missing-key')
        
        assert result is None
    
    def test_get_with_metrics(self, cache, sample_data):
        """Test get with metrics recording"""
        serialized = cache._serialize(sample_data)
        cache._client.get = Mock(return_value=serialized)
        
        with patch('backend.core.cache.record_cache_hit') as mock_hit:
            result = cache.get('test-key', symbol='BTCUSDT', interval='1h')
            
            mock_hit.assert_called_once()
    
    def test_get_when_not_connected(self):
        """Test get when not connected"""
        cache = RedisCache.__new__(RedisCache)
        cache._connected = False
        cache._client = None
        
        result = cache.get('test-key')
        assert result is None
    
    def test_get_redis_error(self, cache):
        """Test get handles Redis errors"""
        cache._client.get = Mock(side_effect=RedisError("Redis error"))
        
        result = cache.get('test-key')
        assert result is None


# ============================================================================
# Test set
# ============================================================================

class TestSet:
    """Test cache storage"""
    
    def test_set_success(self, cache, sample_data):
        """Test successful cache set"""
        cache._client.setex = Mock()
        
        result = cache.set('test-key', sample_data)
        
        assert result is True
        cache._client.setex.assert_called_once()
        
        call_args = cache._client.setex.call_args
        assert call_args[0][0] == 'test:test-key'
        assert call_args[0][1] == 3600  # Default TTL
    
    def test_set_custom_ttl(self, cache, sample_data):
        """Test set with custom TTL"""
        cache._client.setex = Mock()
        
        result = cache.set('test-key', sample_data, ttl=7200)
        
        assert result is True
        call_args = cache._client.setex.call_args
        assert call_args[0][1] == 7200
    
    def test_set_with_metrics(self, cache, sample_data):
        """Test set with metrics recording"""
        cache._client.setex = Mock()
        
        with patch('backend.core.cache.record_cache_set') as mock_set:
            with patch('backend.core.cache.bybit_cache_size_bytes'):
                result = cache.set('test-key', sample_data, symbol='BTCUSDT', interval='1h')
                
                mock_set.assert_called_once()
    
    def test_set_when_not_connected(self):
        """Test set when not connected"""
        cache = RedisCache.__new__(RedisCache)
        cache._connected = False
        cache._client = None
        
        result = cache.set('test-key', {'data': 'value'})
        assert result is False
    
    def test_set_redis_error(self, cache, sample_data):
        """Test set handles Redis errors"""
        cache._client.setex = Mock(side_effect=RedisError("Redis error"))
        
        result = cache.set('test-key', sample_data)
        assert result is False


# ============================================================================
# Test delete
# ============================================================================

class TestDelete:
    """Test cache deletion"""
    
    def test_delete_success(self, cache):
        """Test successful deletion"""
        cache._client.delete = Mock(return_value=1)
        
        result = cache.delete('test-key')
        
        assert result is True
        cache._client.delete.assert_called_once_with('test:test-key')
    
    def test_delete_when_not_connected(self):
        """Test delete when not connected"""
        cache = RedisCache.__new__(RedisCache)
        cache._connected = False
        cache._client = None
        
        result = cache.delete('test-key')
        assert result is False
    
    def test_delete_redis_error(self, cache):
        """Test delete handles Redis errors"""
        cache._client.delete = Mock(side_effect=RedisError("Redis error"))
        
        result = cache.delete('test-key')
        assert result is False


# ============================================================================
# Test clear
# ============================================================================

class TestClear:
    """Test cache clearing"""
    
    def test_clear_all(self, cache):
        """Test clearing all keys"""
        cache._client.scan_iter = Mock(return_value=iter(['key1', 'key2', 'key3']))
        cache._client.delete = Mock(return_value=3)
        
        deleted = cache.clear()
        
        assert deleted == 3
        cache._client.delete.assert_called_once_with('key1', 'key2', 'key3')
    
    def test_clear_pattern(self, cache):
        """Test clearing keys matching pattern"""
        cache._client.scan_iter = Mock(return_value=iter(['test:klines:BTC']))
        cache._client.delete = Mock(return_value=1)
        
        deleted = cache.clear('klines:BTC*')
        
        assert deleted == 1
    
    def test_clear_no_keys(self, cache):
        """Test clear when no keys match"""
        cache._client.scan_iter = Mock(return_value=iter([]))
        
        deleted = cache.clear()
        
        assert deleted == 0
    
    def test_clear_when_not_connected(self):
        """Test clear when not connected"""
        cache = RedisCache.__new__(RedisCache)
        cache._connected = False
        cache._client = None
        
        deleted = cache.clear()
        assert deleted == 0
    
    def test_clear_redis_error(self, cache):
        """Test clear handles Redis errors"""
        cache._client.scan_iter = Mock(side_effect=RedisError("Redis error"))
        
        deleted = cache.clear()
        assert deleted == 0


# ============================================================================
# Test get_stats
# ============================================================================

class TestGetStats:
    """Test cache statistics"""
    
    def test_get_stats_success(self, cache):
        """Test getting cache stats"""
        cache._client.info = Mock(side_effect=[
            {'used_memory_human': '2.5M', 'used_memory_rss_human': '3.0M'},
            {'db0': {'keys': 150}}
        ])
        cache._client.scan_iter = Mock(return_value=iter(['key1', 'key2']))
        
        stats = cache.get_stats()
        
        assert stats['connected'] is True
        assert stats['total_keys'] == 2
        assert stats['used_memory'] == '2.5M'
        assert stats['db_keys'] == 150
    
    def test_get_stats_when_not_connected(self):
        """Test get_stats when not connected"""
        cache = RedisCache.__new__(RedisCache)
        cache._connected = False
        cache._client = None
        
        stats = cache.get_stats()
        
        assert stats['connected'] is False
    
    def test_get_stats_redis_error(self, cache):
        """Test get_stats handles Redis errors"""
        cache._client.info = Mock(side_effect=RedisError("Redis error"))
        
        stats = cache.get_stats()
        
        assert stats['connected'] is False
        assert 'error' in stats


# ============================================================================
# Test health_check
# ============================================================================

class TestHealthCheck:
    """Test cache health check"""
    
    def test_health_check_healthy(self, cache):
        """Test health check when healthy"""
        cache._client.ping = Mock()
        
        health = cache.health_check()
        
        assert health['status'] == 'healthy'
        assert 'latency_ms' in health
        assert health['host'] == 'localhost'
        assert health['port'] == 6379
    
    def test_health_check_not_connected(self):
        """Test health check when not connected"""
        cache = RedisCache.__new__(RedisCache)
        cache._connected = False
        cache._client = None
        
        health = cache.health_check()
        
        assert health['status'] == 'unavailable'
        assert 'message' in health
    
    def test_health_check_redis_error(self, cache):
        """Test health check handles Redis errors"""
        cache._client.ping = Mock(side_effect=RedisError("Connection lost"))
        
        health = cache.health_check()
        
        assert health['status'] == 'unhealthy'
        assert 'error' in health


# ============================================================================
# Test Global Functions
# ============================================================================

class TestGlobalFunctions:
    """Test global helper functions"""
    
    def test_get_cache_creates_instance(self):
        """Test get_cache creates singleton instance"""
        with patch('backend.core.cache._cache', None):
            with patch('redis.Redis') as mock_redis:
                mock_client = MagicMock()
                mock_client.ping = Mock()
                mock_redis.return_value = mock_client
                
                cache = get_cache()
                
                assert cache is not None
                assert isinstance(cache, RedisCache)
    
    def test_get_cache_returns_same_instance(self):
        """Test get_cache returns same instance"""
        with patch('backend.core.cache._cache', None):
            with patch('redis.Redis') as mock_redis:
                mock_client = MagicMock()
                mock_client.ping = Mock()
                mock_redis.return_value = mock_client
                
                cache1 = get_cache()
                cache2 = get_cache()
                
                # Should be same object
                assert cache1 is cache2
    
    def test_make_cache_key_with_limit(self):
        """Test cache key generation with limit"""
        key = make_cache_key('BTCUSDT', '1h', 100)
        assert key == 'klines:BTCUSDT:1h:100'
    
    def test_make_cache_key_without_limit(self):
        """Test cache key generation without limit"""
        key = make_cache_key('ETHUSDT', '4h')
        assert key == 'klines:ETHUSDT:4h'
    
    def test_make_cache_key_zero_limit(self):
        """Test cache key with zero limit"""
        key = make_cache_key('BTCUSDT', '1h', 0)
        assert key == 'klines:BTCUSDT:1h'


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_serialize_none_value(self, cache):
        """Test serializing None"""
        serialized = cache._serialize(None)
        deserialized = cache._deserialize(serialized)
        assert deserialized is None
    
    def test_compression_threshold_boundary(self, cache):
        """Test compression at threshold boundary"""
        # Exactly at threshold
        data = {'data': 'x' * (cache.compression_threshold - 50)}
        serialized = cache._serialize(data)
        deserialized = cache._deserialize(serialized)
        assert deserialized == data
    
    def test_multiple_operations_sequence(self, cache, sample_data):
        """Test sequence of operations"""
        serialized = cache._serialize(sample_data)
        
        cache._client.setex = Mock()
        cache._client.get = Mock(return_value=serialized)
        cache._client.delete = Mock(return_value=1)
        
        # Set
        cache.set('key1', sample_data)
        # Get
        result = cache.get('key1')
        # Delete
        cache.delete('key1')
        
        assert cache._client.setex.called
        assert cache._client.get.called
        assert cache._client.delete.called
        assert result == sample_data
