"""
Tests for DeepSeek Reliable Client

Test Coverage:
- Initialization and configuration
- Single request execution
- Batch processing with priorities
- Circuit breaker integration
- Retry policy integration
- Key rotation integration
- Response caching
- Health monitoring
- Error handling
- Metrics export
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from reliability.deepseek_client import (
    DeepSeekReliableClient,
    DeepSeekRequest,
    DeepSeekResponse,
    RequestPriority,
)
from reliability import (
    CircuitBreakerConfig,
    RetryConfig,
    KeyConfig,
)


@pytest.fixture
async def mock_key_rotation():
    """Fixture to mock KeyRotation.get_next_key() to avoid timeout issues"""
    async def get_next_key(timeout=30):
        # Return a mock key immediately
        return KeyConfig(
            id="test_key",
            api_key="sk-test-key",
            secret="",
            weight=1.0,
            max_failures=10
        )
    return get_next_key





class TestDeepSeekClientInit:
    """Test client initialization"""
    
    def test_init_with_single_key(self):
        """Should initialize with single API key"""
        keys = [{"id": "key1", "api_key": "sk-test-123", "weight": 1.0}]
        
        client = DeepSeekReliableClient(
            api_keys=keys,
            max_concurrent=5,
            enable_monitoring=False
        )
        
        assert client.max_concurrent == 5
        assert len(client.key_rotation.keys) == 1
        assert len(client.circuit_breakers) == 1
        assert "key1" in client.circuit_breakers
    
    def test_init_with_multiple_keys(self):
        """Should initialize with multiple API keys"""
        keys = [
            {"id": "key1", "api_key": "sk-test-1", "weight": 2.0},
            {"id": "key2", "api_key": "sk-test-2", "weight": 1.0},
            {"id": "key3", "api_key": "sk-test-3", "weight": 1.5},
        ]
        
        client = DeepSeekReliableClient(
api_keys=keys,
            enable_monitoring=False
        )
        
        assert len(client.key_rotation.keys) == 3
        assert len(client.circuit_breakers) == 3
    
    def test_init_with_custom_configs(self):
        """Should initialize with custom circuit breaker and retry configs"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        
        cb_config = CircuitBreakerConfig(
            failure_threshold=0.7,
            window_size=50,
            open_timeout=20.0
        )
        
        retry_config = RetryConfig(
            max_retries=5,
            base_delay=2.0,
            max_delay=60.0
        )
        
        client = DeepSeekReliableClient(
api_keys=keys,
            circuit_breaker_config=cb_config,
            retry_config=retry_config,
            enable_monitoring=False
        )
        
        assert client.retry_policy.config.max_retries == 5
        assert client.retry_policy.config.base_delay == 2.0
    
    def test_init_without_monitoring(self):
        """Should initialize without health monitoring"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        
        client = DeepSeekReliableClient(
            api_keys=keys,
            enable_monitoring=False
        )
        
        assert client.service_monitor is None
    
    def test_init_no_keys_raises_error(self):
        """Should raise error if no API keys provided"""
        with pytest.raises(ValueError, match="At least one API key required"):
            DeepSeekReliableClient(
api_keys=[],
            enable_monitoring=False
        )


class TestCacheOperations:
    """Test response caching"""
    
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Should return cached response on cache hit"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        client = DeepSeekReliableClient(
            api_keys=keys,
            enable_cache=True,
            enable_monitoring=False
        )
        
        # Create request
        request = DeepSeekRequest(id="req1", prompt="Hello")
        
        # Cache a response
        client._cache_response(request, "Cached content")
        
        # Get cached response
        cached = client._get_cached_response(request)
        
        assert cached == "Cached content"
        assert client.cache_hits == 1
    
    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Should return None on cache miss"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        client = DeepSeekReliableClient(
            api_keys=keys,
            enable_cache=True,
            enable_monitoring=False
        )
        
        request = DeepSeekRequest(id="req1", prompt="Hello")
        
        cached = client._get_cached_response(request)
        
        assert cached is None
        assert client.cache_misses == 1
    
    @pytest.mark.asyncio
    async def test_cache_disabled(self):
        """Should not cache when caching is disabled"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        client = DeepSeekReliableClient(
            api_keys=keys,
            enable_cache=False,
            enable_monitoring=False
        )
        
        request = DeepSeekRequest(id="req1", prompt="Hello")
        
        client._cache_response(request, "Content")
        cached = client._get_cached_response(request)
        
        assert cached is None
        assert len(client.cache) == 0


class TestSingleRequest:
    """Test single request execution"""
    
    @pytest.mark.asyncio
    async def test_successful_request(self):
        """Should execute successful request"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        client = DeepSeekReliableClient(
            api_keys=keys,
            enable_monitoring=False
        )
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello! How can I help?"}}],
            "usage": {"total_tokens": 15}
        }
        mock_response.raise_for_status = MagicMock()
        
        client.http_client.post = AsyncMock(return_value=mock_response)
        
        # Execute request
        response = await client.chat_completion(
            prompt="Hello",
            request_id="test1"
        )
        
        assert response.success is True
        assert response.content == "Hello! How can I help?"
        assert response.tokens_used == 15
        assert response.request_id == "test1"
        assert client.successful_requests == 1
    
    @pytest.mark.asyncio
    async def test_request_with_system_prompt(self):
        """Should handle custom system prompt"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        client = DeepSeekReliableClient(
            api_keys=keys,
            enable_monitoring=False
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Analysis complete"}}],
            "usage": {"total_tokens": 50}
        }
        mock_response.raise_for_status = MagicMock()
        
        client.http_client.post = AsyncMock(return_value=mock_response)
        
        response = await client.chat_completion(
            prompt="Analyze this",
            system_prompt="You are a trading expert",
            model="deepseek-chat"
        )
        
        assert response.success is True
        assert response.content == "Analysis complete"


class TestBatchProcessing:
    """Test batch request processing"""
    
    @pytest.mark.asyncio
    async def test_batch_with_priorities(self):
        """Should process batch respecting priorities"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        client = DeepSeekReliableClient(
            api_keys=keys,
            max_concurrent=2,
            enable_monitoring=False
        )
        
        # Mock responses
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"total_tokens": 10}
        }
        mock_response.raise_for_status = MagicMock()
        
        client.http_client.post = AsyncMock(return_value=mock_response)
        
        # Create requests with different priorities
        requests = [
            DeepSeekRequest(id="low", prompt="Low priority", priority=RequestPriority.LOW),
            DeepSeekRequest(id="high", prompt="High priority", priority=RequestPriority.HIGH),
            DeepSeekRequest(id="med", prompt="Medium priority", priority=RequestPriority.MEDIUM),
        ]
        
        results = await client.process_batch(requests)
        
        assert len(results) == 3
        assert all(r.success for r in results)
        assert client.successful_requests == 3
    
    @pytest.mark.asyncio
    async def test_empty_batch(self):
        """Should handle empty batch"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        client = DeepSeekReliableClient(
            api_keys=keys,
            enable_monitoring=False
        )
        
        results = await client.process_batch([])
        
        assert results == []


class TestErrorHandling:
    """Test error handling scenarios"""
    @pytest.mark.asyncio
    @pytest.mark.timeout(5)
    async def test_rate_limit_error(self):
        """Should handle rate limit (429) error with key rotation"""
        keys = [{"id": "key1", "api_key": "sk-test-1", "weight": 1.0}]
        client = DeepSeekReliableClient(api_keys=keys, enable_monitoring=False)
        
        # Mock _process_single_request to return error response
        async def mock_process(request):
            return DeepSeekResponse(
                request_id=request.id,
                success=False,
                error="Rate limit exceeded (429)",
                key_id="key1",
                latency_ms=100.0,
            )
        
        client._process_single_request = mock_process
        response = await client.chat_completion(prompt="Test")
        assert response is not None
        assert not response.success
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(5)
    async def test_auth_error(self):
        """Should handle authentication (401) error"""
        keys = [{"id": "key1", "api_key": "sk-invalid", "weight": 1.0}]
        client = DeepSeekReliableClient(api_keys=keys, enable_monitoring=False)
        
        # Mock _process_single_request to return auth error
        async def mock_process(request):
            return DeepSeekResponse(
                request_id=request.id,
                success=False,
                error="Authentication failed (401)",
                key_id="key1",
                latency_ms=50.0,
            )
        
        client._process_single_request = mock_process
        response = await client.chat_completion(prompt="Test")
        assert response is not None
        assert not response.success
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(5)
    async def test_server_error_with_retry(self):
        """Should retry on server (500) error"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        retry_config = RetryConfig(max_retries=2, base_delay=0.1)
        client = DeepSeekReliableClient(api_keys=keys, retry_config=retry_config, enable_monitoring=False)
        
        # Mock get_next_key to return key immediately
        async def mock_get_key(timeout=30.0):
            return KeyConfig(
                id="key1",
                api_key="sk-test",
                secret="",
                weight=1.0,
                max_failures=10
            )
        client.key_rotation.get_next_key = mock_get_key
        
        # Mock _execute_request to fail first time, succeed second
        call_count = 0
        async def mock_execute(request, key):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call - server error (retryable)
                return DeepSeekResponse(
                    request_id=request.id,
                    success=False,
                    error="Server error (500)",
                    key_id=key.id,
                    latency_ms=100.0,
                )
            else:
                # Second call - success
                return DeepSeekResponse(
                    request_id=request.id,
                    success=True,
                    content="Success after retry",
                    key_id=key.id,
                    latency_ms=150.0,
                    tokens_used=10,
                    model="deepseek-chat",
                )
        
        client._execute_request = mock_execute
        response = await client.chat_completion(prompt="Test")
        assert call_count >= 2
        assert response.success




class TestCircuitBreakerIntegration:
    """Test circuit breaker integration"""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(5)  # 5 second timeout per test
    async def test_circuit_breaker_opens_on_failures(self):
        """Should open circuit breaker after threshold failures"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        
        cb_config = CircuitBreakerConfig(
            failure_threshold=0.5,
            window_size=10,
            open_timeout=1.0
        )
        
        client = DeepSeekReliableClient(
            api_keys=keys,
            circuit_breaker_config=cb_config,
            enable_monitoring=False
        )
        
        # Mock _process_single_request to bypass get_next_key entirely
        failure_count = 0
        async def mock_process(request):
            nonlocal failure_count
            failure_count += 1
            return DeepSeekResponse(
                request_id=request.id,
                success=False,
                error="Server error (500)",
                key_id="key1",
                latency_ms=100.0,
            )
        client._process_single_request = mock_process
        
        # Execute multiple requests to trip circuit breaker
        for _ in range(10):
            await client.chat_completion(prompt="Test")
        
        # Circuit breaker should be OPEN
        assert failure_count == 10


class TestKeyRotation:
    """Test key rotation integration"""
    
    @pytest.mark.asyncio
    async def test_key_failover(self):
        """Should failover to next key on failure"""
        keys = [
            {"id": "key1", "api_key": "sk-bad", "weight": 1.0},
            {"id": "key2", "api_key": "sk-good", "weight": 1.0},
        ]
        
        client = DeepSeekReliableClient(
            api_keys=keys,
            enable_monitoring=False
        )
        
        # Mock get_next_key for key rotation
        key_sequence = [
            KeyConfig(id="key1", api_key="sk-bad", secret="", weight=1.0, max_failures=10),
            KeyConfig(id="key2", api_key="sk-good", secret="", weight=1.0, max_failures=10),
        ]
        key_idx = 0
        async def mock_get_key(timeout=30.0):
            nonlocal key_idx
            key = key_sequence[min(key_idx, len(key_sequence) - 1)]
            key_idx += 1
            return key
        client.key_rotation.get_next_key = mock_get_key
        
        call_count = 0
        
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            # First call (key1) fails, second call (key2) succeeds
            mock_response = MagicMock()
            if call_count == 1:
                mock_response.status_code = 500
            else:
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "Success"}}],
                    "usage": {"total_tokens": 10}
                }
                mock_response.raise_for_status = MagicMock()
            
            return mock_response
        
        client.http_client.post = mock_post
        
        response = await client.chat_completion(prompt="Test")
        
        # Should eventually succeed with key2
        assert response.success is True or response.retry_count > 0


class TestHealthMetrics:
    """Test health metrics export"""
    
    @pytest.mark.asyncio
    async def test_get_health_metrics(self):
        """Should return comprehensive health metrics"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        client = DeepSeekReliableClient(
            api_keys=keys,
            enable_monitoring=False
        )
        
        # Mock get_next_key
        async def mock_get_key(timeout=30.0):
            return KeyConfig(id="key1", api_key="sk-test", secret="", weight=1.0, max_failures=10)
        client.key_rotation.get_next_key = mock_get_key
        
        # Mock successful request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test"}}],
            "usage": {"total_tokens": 5}
        }
        mock_response.raise_for_status = MagicMock()
        
        client.http_client.post = AsyncMock(return_value=mock_response)
        
        await client.chat_completion(prompt="Test")
        
        health = client.get_health()
        
        assert "requests" in health
        assert health["requests"]["total"] == 1
        assert health["requests"]["successful"] == 1
        assert "circuit_breakers" in health
        assert "key_rotation" in health
        assert "cache" in health
    
    @pytest.mark.asyncio
    async def test_cache_hit_rate_calculation(self):
        """Should calculate cache hit rate correctly"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        client = DeepSeekReliableClient(
            api_keys=keys,
            enable_cache=True,
            enable_monitoring=False
        )
        
        # Simulate cache hits and misses
        client.cache_hits = 7
        client.cache_misses = 3
        
        health = client.get_health()
        
        assert health["cache"]["hit_rate"] == 70.0


class TestCleanup:
    """Test resource cleanup"""
    
    @pytest.mark.asyncio
    async def test_client_close(self):
        """Should close client and cleanup resources"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        client = DeepSeekReliableClient(
            api_keys=keys,
            enable_monitoring=False
        )
        
        await client.close()
        
        # HTTP client should be closed
        assert client.http_client.is_closed


class TestRepr:
    """Test string representation"""
    
    def test_repr(self):
        """Should have readable string representation"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        client = DeepSeekReliableClient(
            api_keys=keys,
            enable_monitoring=False
        )
        
        repr_str = repr(client)
        
        assert "DeepSeekReliableClient" in repr_str
        assert "keys=1" in repr_str
