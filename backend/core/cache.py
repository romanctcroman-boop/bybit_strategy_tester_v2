"""
Redis cache implementation for Bybit adapter.

Provides caching layer for:
- Kline/candle data
- Symbol metadata
- Rate limit state

Features:
- Automatic serialization/deserialization
- TTL support
- Compression for large datasets
- Metrics integration
"""

import json
import pickle
import zlib
from datetime import datetime, timedelta
from typing import Any, Optional
import redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from backend.core.config import get_config
from backend.core.logging_config import get_logger
from backend.core.metrics import (
    record_cache_hit,
    record_cache_miss,
    record_cache_set,
    bybit_cache_size_bytes,
    bybit_cache_items_total
)

config = get_config()
logger = get_logger(__name__)


class RedisCache:
    """Redis-based cache for Bybit data."""
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        prefix: str = 'bybit:',
        ttl_seconds: int = 3600,
        compress: bool = True,
        compression_threshold: int = 1024
    ):
        """
        Initialize Redis cache.
        
        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number
            password: Redis password (if required)
            prefix: Key prefix for all cache entries
            ttl_seconds: Default TTL in seconds
            compress: Enable compression for large values
            compression_threshold: Min size in bytes to trigger compression
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.prefix = prefix
        self.ttl_seconds = ttl_seconds
        self.compress = compress
        self.compression_threshold = compression_threshold
        
        self._client: Optional[redis.Redis] = None
        self._connected = False
        
        # Try to connect
        try:
            self._connect()
        except RedisConnectionError as e:
            logger.warning(f"Redis connection failed: {e}. Cache disabled.")
    
    def _connect(self):
        """Establish Redis connection."""
        try:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=False,  # We handle encoding ourselves
                socket_timeout=2,
                socket_connect_timeout=2,
                health_check_interval=30
            )
            # Test connection
            self._client.ping()
            self._connected = True
            logger.info(f"Redis cache connected: {self.host}:{self.port}/{self.db}")
        except RedisError as e:
            self._connected = False
            logger.warning(f"Redis connection failed: {e}")
            raise
    
    def _make_key(self, key: str) -> str:
        """Generate full cache key with prefix."""
        return f"{self.prefix}{key}"
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value to bytes with optional compression."""
        # Use pickle for Python objects
        data = pickle.dumps(value)
        
        # Compress if enabled and data is large enough
        if self.compress and len(data) > self.compression_threshold:
            compressed = zlib.compress(data, level=6)
            # Only use compressed if it's actually smaller
            if len(compressed) < len(data):
                # Add marker byte to indicate compression
                return b'\x01' + compressed
        
        # No compression marker
        return b'\x00' + data
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to Python object."""
        if not data:
            return None
        
        # Check compression marker
        is_compressed = data[0] == 1
        payload = data[1:]
        
        if is_compressed:
            payload = zlib.decompress(payload)
        
        return pickle.loads(payload)
    
    def get(self, key: str, symbol: str = '', interval: str = '') -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            symbol: Symbol for metrics (optional)
            interval: Interval for metrics (optional)
            
        Returns:
            Cached value or None if not found
        """
        if not self._connected or not self._client:
            return None
        
        try:
            full_key = self._make_key(key)
            data = self._client.get(full_key)
            
            if data is None:
                if symbol and interval:
                    record_cache_miss(symbol, interval)
                return None
            
            value = self._deserialize(data)
            
            # Record metrics
            if symbol and interval:
                count = len(value) if isinstance(value, list) else 1
                record_cache_hit(symbol, interval, count)
            
            logger.debug(f"Cache hit: {key}")
            return value
            
        except RedisError as e:
            logger.warning(f"Cache get failed for {key}: {e}")
            return None
    
    def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        symbol: str = '',
        interval: str = ''
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default if None)
            symbol: Symbol for metrics (optional)
            interval: Interval for metrics (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connected or not self._client:
            return False
        
        try:
            full_key = self._make_key(key)
            data = self._serialize(value)
            ttl = ttl or self.ttl_seconds
            
            self._client.setex(full_key, ttl, data)
            
            # Record metrics
            if symbol and interval:
                count = len(value) if isinstance(value, list) else 1
                record_cache_set(symbol, interval, count)
            
            # Update cache size metrics
            bybit_cache_size_bytes.labels(cache_type='redis').set(len(data))
            
            logger.debug(f"Cache set: {key} (TTL: {ttl}s, size: {len(data)} bytes)")
            return True
            
        except RedisError as e:
            logger.warning(f"Cache set failed for {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self._connected or not self._client:
            return False
        
        try:
            full_key = self._make_key(key)
            self._client.delete(full_key)
            logger.debug(f"Cache delete: {key}")
            return True
        except RedisError as e:
            logger.warning(f"Cache delete failed for {key}: {e}")
            return False
    
    def clear(self, pattern: str = '*') -> int:
        """
        Clear cache entries matching pattern.
        
        Args:
            pattern: Key pattern to match (default: all keys with prefix)
            
        Returns:
            Number of keys deleted
        """
        if not self._connected or not self._client:
            return 0
        
        try:
            full_pattern = self._make_key(pattern)
            keys = list(self._client.scan_iter(match=full_pattern, count=100))
            
            if keys:
                deleted = self._client.delete(*keys)
                logger.info(f"Cleared {deleted} cache entries matching {pattern}")
                return deleted
            
            return 0
        except RedisError as e:
            logger.warning(f"Cache clear failed for pattern {pattern}: {e}")
            return 0
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        if not self._connected or not self._client:
            return {'connected': False}
        
        try:
            info = self._client.info('memory')
            keyspace = self._client.info('keyspace')
            
            # Count keys with our prefix
            pattern = self._make_key('*')
            keys = list(self._client.scan_iter(match=pattern, count=100))
            
            # Update metrics
            bybit_cache_items_total.labels(cache_type='redis').set(len(keys))
            
            return {
                'connected': True,
                'total_keys': len(keys),
                'used_memory': info.get('used_memory_human', 'N/A'),
                'used_memory_rss': info.get('used_memory_rss_human', 'N/A'),
                'db_keys': keyspace.get(f'db{self.db}', {}).get('keys', 0)
            }
        except RedisError as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {'connected': False, 'error': str(e)}
    
    def health_check(self) -> dict:
        """Check cache health."""
        try:
            if not self._connected or not self._client:
                return {'status': 'unavailable', 'message': 'Not connected'}
            
            # Test with ping
            latency_start = datetime.now()
            self._client.ping()
            latency = (datetime.now() - latency_start).total_seconds() * 1000
            
            return {
                'status': 'healthy',
                'latency_ms': round(latency, 2),
                'host': self.host,
                'port': self.port,
                'db': self.db
            }
        except RedisError as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }


# Global cache instance
_cache: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """Get or create global cache instance."""
    global _cache
    
    if _cache is None:
        try:
            _cache = RedisCache(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                password=config.REDIS_PASSWORD,
                prefix='bybit:',
                ttl_seconds=config.CACHE_TTL_DAYS * 86400,
                compress=True,
                compression_threshold=1024
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Redis cache: {e}")
            # Return dummy cache that does nothing
            _cache = RedisCache(host='invalid', port=0)
    
    return _cache


def make_cache_key(symbol: str, interval: str, limit: int = 0) -> str:
    """
    Generate cache key for kline data.
    
    Args:
        symbol: Trading symbol
        interval: Time interval
        limit: Number of candles (optional)
    
    Returns:
        Cache key string
    """
    if limit:
        return f"klines:{symbol}:{interval}:{limit}"
    return f"klines:{symbol}:{interval}"
