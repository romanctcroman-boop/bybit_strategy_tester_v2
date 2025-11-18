"""
Comprehensive tests for backend/api/perplexity_client.py

Coverage Target: 100%
Tests: Perplexity API client with caching and circuit breaker
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
import time
from datetime import datetime, timedelta
from backend.api.perplexity_client import PerplexityClient, SimpleCache


# ==================== SIMPLE CACHE TESTS ====================


class TestSimpleCache:
    """Test SimpleCache implementation"""

    def test_cache_init(self):
        """Test cache initialization"""
        cache = SimpleCache(max_size=5, ttl_seconds=30)
        assert cache.max_size == 5
        assert cache.ttl_seconds == 30
        assert len(cache.cache) == 0
        assert cache.stats == {"hits": 0, "misses": 0}

    def test_cache_default_params(self):
        """Test cache with default parameters"""
        cache = SimpleCache()
        assert cache.max_size == 10
        assert cache.ttl_seconds == 60

    def test_compute_key_basic(self):
        """Test cache key computation"""
        cache = SimpleCache()
        key1 = cache._compute_key("test query")
        key2 = cache._compute_key("test query")
        assert key1 == key2  # Same input = same key

    def test_compute_key_case_insensitive(self):
        """Test cache key is case insensitive"""
        cache = SimpleCache()
        key1 = cache._compute_key("TEST Query")
        key2 = cache._compute_key("test query")
        assert key1 == key2

    def test_compute_key_strips_whitespace(self):
        """Test cache key strips whitespace"""
        cache = SimpleCache()
        key1 = cache._compute_key("  test query  ")
        key2 = cache._compute_key("test query")
        assert key1 == key2

    def test_compute_key_with_kwargs(self):
        """Test cache key with additional parameters"""
        cache = SimpleCache()
        key1 = cache._compute_key("query", model="sonar")
        key2 = cache._compute_key("query", model="sonar")
        key3 = cache._compute_key("query", model="different")
        
        assert key1 == key2
        assert key1 != key3

    def test_set_and_get(self):
        """Test basic set and get operations"""
        cache = SimpleCache()
        cache.set("test", {"result": "data"})
        
        result = cache.get("test")
        assert result == {"result": "data"}
        assert cache.stats["hits"] == 1
        assert cache.stats["misses"] == 0

    def test_get_miss(self):
        """Test cache miss"""
        cache = SimpleCache()
        result = cache.get("nonexistent")
        
        assert result is None
        assert cache.stats["hits"] == 0
        assert cache.stats["misses"] == 1

    def test_get_with_kwargs(self):
        """Test get with additional parameters"""
        cache = SimpleCache()
        cache.set("query", {"data": "value"}, model="sonar")
        
        # Same kwargs should hit
        result = cache.get("query", model="sonar")
        assert result == {"data": "value"}
        assert cache.stats["hits"] == 1
        
        # Different kwargs should miss
        result = cache.get("query", model="different")
        assert result is None
        assert cache.stats["misses"] == 1

    def test_lru_eviction(self):
        """Test LRU eviction when cache is full"""
        cache = SimpleCache(max_size=3)
        
        cache.set("key1", {"data": "value1"})
        cache.set("key2", {"data": "value2"})
        cache.set("key3", {"data": "value3"})
        
        assert len(cache.cache) == 3
        
        # Adding 4th item should evict oldest (key1)
        cache.set("key4", {"data": "value4"})
        
        assert len(cache.cache) == 3
        assert cache.get("key1") is None  # Evicted
        assert cache.get("key4") is not None

    def test_lru_update_on_access(self):
        """Test that accessing an item updates its position in LRU"""
        cache = SimpleCache(max_size=3)
        
        cache.set("key1", {"data": "value1"})
        cache.set("key2", {"data": "value2"})
        cache.set("key3", {"data": "value3"})
        
        # Access key1 to make it most recent
        cache.get("key1")
        
        # Add key4, should evict key2 (oldest)
        cache.set("key4", {"data": "value4"})
        
        assert cache.get("key1") is not None  # Still exists
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key4") is not None

    def test_ttl_expiration(self):
        """Test that expired entries are removed"""
        cache = SimpleCache(ttl_seconds=0.1)  # 100ms TTL
        
        cache.set("key", {"data": "value"})
        
        # Immediate access should work
        result = cache.get("key")
        assert result == {"data": "value"}
        
        # Wait for expiration
        time.sleep(0.15)
        
        # Should be expired
        result = cache.get("key")
        assert result is None

    def test_get_stats_empty(self):
        """Test stats for empty cache"""
        cache = SimpleCache()
        stats = cache.get_stats()
        
        assert stats == {
            "size": 0,
            "max_size": 10,
            "hits": 0,
            "misses": 0,
            "hit_rate": 0
        }

    def test_get_stats_with_data(self):
        """Test stats with cache activity"""
        cache = SimpleCache(max_size=5)
        
        cache.set("key1", {"data": "value1"})
        cache.set("key2", {"data": "value2"})
        
        cache.get("key1")  # Hit
        cache.get("key1")  # Hit
        cache.get("key3")  # Miss
        
        stats = cache.get_stats()
        
        assert stats["size"] == 2
        assert stats["max_size"] == 5
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 66.7  # 2/3 * 100


# ==================== PERPLEXITY CLIENT INIT TESTS ====================


class TestPerplexityClientInit:
    """Test PerplexityClient initialization"""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key"""
        client = PerplexityClient(api_key="test_key_123")
        assert client.api_key == "test_key_123"
        assert client.base_url == "https://api.perplexity.ai"
        assert client.timeout == 5.0

    def test_init_without_api_key_uses_env(self):
        """Test initialization falls back to environment variable"""
        with patch.dict("os.environ", {"PERPLEXITY_API_KEY": "env_key_456"}):
            client = PerplexityClient()
            assert client.api_key == "env_key_456"

    def test_init_without_api_key_no_env(self):
        """Test initialization with no key and no environment variable"""
        with patch.dict("os.environ", {}, clear=True):
            client = PerplexityClient()
            assert client.api_key == ""

    def test_init_cache_created(self):
        """Test that cache is initialized"""
        client = PerplexityClient(api_key="key")
        assert isinstance(client.cache, SimpleCache)
        assert client.cache.max_size == 10
        assert client.cache.ttl_seconds == 60

    def test_init_circuit_breaker_state(self):
        """Test circuit breaker is initialized"""
        client = PerplexityClient(api_key="key")
        assert client.failure_count == 0
        assert client.last_failure_time == 0


# ==================== TEST_CONNECTION TESTS ====================


class TestPerplexityConnectionMethod:
    """Test test_connection method"""

    @pytest.mark.asyncio
    async def test_connection_no_api_key(self):
        """Test connection fails without API key"""
        with patch.dict("os.environ", {}, clear=True):
            client = PerplexityClient(api_key="")
            result = await client.test_connection()
            assert result is False

    @pytest.mark.asyncio
    async def test_connection_success_status_200(self):
        """Test successful connection with 200 status"""
        client = PerplexityClient(api_key="valid_key")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client
            
            result = await client.test_connection()
            
            assert result is True
            assert client.failure_count == 0
            
            # Verify API call
            mock_http_client.post.assert_called_once()
            call_args = mock_http_client.post.call_args
            assert "chat/completions" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_connection_accepts_400_status(self):
        """Test connection accepts 400 as healthy (API reachable)"""
        client = PerplexityClient(api_key="valid_key")
        
        mock_response = MagicMock()
        mock_response.status_code = 400
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client
            
            result = await client.test_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_connection_accepts_401_status(self):
        """Test connection accepts 401 as healthy (API reachable)"""
        client = PerplexityClient(api_key="invalid_key")
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client
            
            result = await client.test_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_connection_accepts_403_status(self):
        """Test connection accepts 403 as healthy (API reachable)"""
        client = PerplexityClient(api_key="limited_key")
        
        mock_response = MagicMock()
        mock_response.status_code = 403
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client
            
            result = await client.test_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_connection_fails_on_500_status(self):
        """Test connection fails on 500 server error"""
        client = PerplexityClient(api_key="valid_key")
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client
            
            result = await client.test_connection()
            assert result is False
            assert client.failure_count == 0  # Not an exception failure

    @pytest.mark.asyncio
    async def test_connection_timeout_exception(self):
        """Test connection fails on timeout"""
        client = PerplexityClient(api_key="valid_key")
        
        mock_http_client = AsyncMock()
        mock_http_client.post.side_effect = httpx.TimeoutException("Request timeout")
        
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client
            
            result = await client.test_connection()
            
            assert result is False
            assert client.failure_count == 1
            assert client.last_failure_time > 0

    @pytest.mark.asyncio
    async def test_connection_generic_exception(self):
        """Test connection fails on generic exception"""
        client = PerplexityClient(api_key="valid_key")
        
        mock_http_client = AsyncMock()
        mock_http_client.post.side_effect = Exception("Network error")
        
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client
            
            result = await client.test_connection()
            
            assert result is False
            assert client.failure_count == 1

    @pytest.mark.asyncio
    async def test_connection_uses_cache(self):
        """Test that successful connection is cached"""
        client = PerplexityClient(api_key="valid_key")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client
            
            # First call
            result1 = await client.test_connection()
            assert result1 is True
            assert mock_http_client.post.call_count == 1
            
            # Second call should use cache
            result2 = await client.test_connection()
            assert result2 is True
            assert mock_http_client.post.call_count == 1  # No additional call

    @pytest.mark.asyncio
    async def test_connection_caches_failure(self):
        """Test that failures are also cached"""
        client = PerplexityClient(api_key="valid_key")
        
        mock_http_client = AsyncMock()
        mock_http_client.post.side_effect = httpx.TimeoutException("Timeout")
        
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client
            
            # First call
            result1 = await client.test_connection()
            assert result1 is False
            assert mock_http_client.post.call_count == 1
            
            # Second call should use cached failure
            result2 = await client.test_connection()
            assert result2 is False
            assert mock_http_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_connection_resets_failure_count_on_success(self):
        """Test failure count is reset on successful connection"""
        client = PerplexityClient(api_key="valid_key")
        client.failure_count = 3  # Simulate previous failures
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client
            
            result = await client.test_connection()
            
            assert result is True
            assert client.failure_count == 0  # Reset


# ==================== CHECK_HEALTH TESTS ====================


class TestCheckHealthMethod:
    """Test check_health method"""

    @pytest.mark.asyncio
    async def test_check_health_healthy(self):
        """Test health check when API is healthy"""
        client = PerplexityClient(api_key="valid_key")
        
        with patch.object(client, "test_connection", return_value=True):
            result = await client.check_health()
            
            assert result["status"] == "healthy"
            assert result["service"] == "Perplexity API"
            assert result["available"] is True
            assert "latency_ms" in result
            assert "cache_stats" in result
            assert "circuit_breaker" in result

    @pytest.mark.asyncio
    async def test_check_health_unhealthy(self):
        """Test health check when API is unhealthy"""
        client = PerplexityClient(api_key="")
        
        with patch.object(client, "test_connection", return_value=False):
            result = await client.check_health()
            
            assert result["status"] == "unhealthy"
            assert result["available"] is False

    @pytest.mark.asyncio
    async def test_check_health_includes_latency(self):
        """Test that health check includes latency measurement"""
        client = PerplexityClient(api_key="key")
        
        async def slow_connection():
            await asyncio.sleep(0.01)  # 10ms delay
            return True
        
        import asyncio
        with patch.object(client, "test_connection", slow_connection):
            result = await client.check_health()
            
            assert "latency_ms" in result
            assert result["latency_ms"] > 0
            assert isinstance(result["latency_ms"], float)

    @pytest.mark.asyncio
    async def test_check_health_includes_cache_stats(self):
        """Test health check includes cache statistics"""
        client = PerplexityClient(api_key="key")
        
        with patch.object(client, "test_connection", return_value=True):
            result = await client.check_health()
            
            cache_stats = result["cache_stats"]
            assert "size" in cache_stats
            assert "max_size" in cache_stats
            assert "hits" in cache_stats
            assert "misses" in cache_stats
            assert "hit_rate" in cache_stats

    @pytest.mark.asyncio
    async def test_check_health_circuit_breaker_closed(self):
        """Test circuit breaker shows closed when healthy"""
        client = PerplexityClient(api_key="key")
        
        with patch.object(client, "test_connection", return_value=True):
            result = await client.check_health()
            
            cb = result["circuit_breaker"]
            assert cb["failure_count"] == 0
            assert cb["state"] == "closed"

    @pytest.mark.asyncio
    async def test_check_health_circuit_breaker_open(self):
        """Test circuit breaker shows open after failures"""
        client = PerplexityClient(api_key="key")
        client.failure_count = 5  # Threshold
        
        with patch.object(client, "test_connection", return_value=False):
            result = await client.check_health()
            
            cb = result["circuit_breaker"]
            assert cb["failure_count"] == 5
            assert cb["state"] == "open"

    @pytest.mark.asyncio
    async def test_check_health_circuit_breaker_last_failure(self):
        """Test circuit breaker tracks last failure time"""
        client = PerplexityClient(api_key="key")
        client.failure_count = 3
        client.last_failure_time = 12345.67
        
        with patch.object(client, "test_connection", return_value=False):
            result = await client.check_health()
            
            cb = result["circuit_breaker"]
            assert cb["last_failure_time"] == 12345.67


# ==================== INVALIDATE CACHE TESTS ====================


class TestInvalidateCache:
    """Test invalidate_health_cache method"""

    def test_invalidate_clears_cache(self):
        """Test that invalidate clears all cache entries"""
        client = PerplexityClient(api_key="key")
        
        # Add some cache entries
        client.cache.set("query1", {"data": "value1"})
        client.cache.set("query2", {"data": "value2"})
        
        assert len(client.cache.cache) == 2
        
        # Invalidate
        client.invalidate_health_cache()
        
        assert len(client.cache.cache) == 0

    def test_invalidate_resets_stats(self):
        """Test that invalidate resets cache statistics"""
        client = PerplexityClient(api_key="key")
        
        # Generate some stats
        client.cache.set("key", {"data": "value"})
        client.cache.get("key")  # Hit
        client.cache.get("missing")  # Miss
        
        assert client.cache.stats["hits"] == 1
        assert client.cache.stats["misses"] == 1
        
        # Invalidate
        client.invalidate_health_cache()
        
        assert client.cache.stats == {"hits": 0, "misses": 0}


# ==================== INTEGRATION TESTS ====================


class TestPerplexityClientIntegration:
    """Integration tests for PerplexityClient"""

    @pytest.mark.asyncio
    async def test_full_workflow_success(self):
        """Test full workflow with successful connection"""
        client = PerplexityClient(api_key="integration_key")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client
            
            # Test connection
            connection_ok = await client.test_connection()
            assert connection_ok is True
            
            # Test health check
            health = await client.check_health()
            assert health["status"] == "healthy"
            assert health["available"] is True
            assert health["circuit_breaker"]["state"] == "closed"

    @pytest.mark.asyncio
    async def test_multiple_failures_open_circuit(self):
        """Test multiple failures open circuit breaker"""
        client = PerplexityClient(api_key="key")
        
        mock_http_client = AsyncMock()
        mock_http_client.post.side_effect = httpx.TimeoutException("Timeout")
        
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client
            
            # Simulate 5 failures
            for _ in range(5):
                client.cache.cache.clear()  # Clear cache each time
                await client.test_connection()
            
            # Check circuit breaker state
            health = await client.check_health()
            assert health["circuit_breaker"]["state"] == "open"
            assert health["circuit_breaker"]["failure_count"] == 5

    @pytest.mark.asyncio
    async def test_cache_improves_performance(self):
        """Test that caching improves performance"""
        client = PerplexityClient(api_key="key")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client
            
            # First call - should make API request
            start1 = time.time()
            result1 = await client.test_connection()
            time1 = time.time() - start1
            
            # Second call - should use cache (faster)
            start2 = time.time()
            result2 = await client.test_connection()
            time2 = time.time() - start2
            
            assert result1 is True
            assert result2 is True
            assert mock_http_client.post.call_count == 1  # Only one API call
            
            # Get cache stats
            health = await client.check_health()
            assert health["cache_stats"]["hit_rate"] > 0

    @pytest.mark.asyncio
    async def test_invalidate_forces_new_request(self):
        """Test that cache invalidation forces new API request"""
        client = PerplexityClient(api_key="key")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client
            
            # First call
            await client.test_connection()
            assert mock_http_client.post.call_count == 1
            
            # Second call uses cache
            await client.test_connection()
            assert mock_http_client.post.call_count == 1
            
            # Invalidate cache
            client.invalidate_health_cache()
            
            # Third call should make new request
            await client.test_connection()
            assert mock_http_client.post.call_count == 2
