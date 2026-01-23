"""
Comprehensive tests for backend/api/deepseek_client.py

Coverage Target: 100%
Tests: DeepSeek API client for health checks
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from backend.api.deepseek_client import DeepSeekClient


# ==================== INITIALIZATION TESTS ====================


class TestDeepSeekClientInit:
    """Test DeepSeekClient initialization"""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key"""
        client = DeepSeekClient(api_key="test_key_123")
        assert client.api_key == "test_key_123"
        assert client.base_url == "https://api.deepseek.com/v1"
        assert client.timeout == 10.0

    def test_init_without_api_key_uses_env(self):
        """Test initialization falls back to environment variable"""
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "env_key_456"}):
            client = DeepSeekClient()
            assert client.api_key == "env_key_456"

    def test_init_without_api_key_no_env(self):
        """Test initialization with no key and no environment variable"""
        with patch.dict("os.environ", {}, clear=True):
            client = DeepSeekClient()
            assert client.api_key == ""

    def test_init_none_api_key_uses_env(self):
        """Test explicit None uses environment variable"""
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "env_override"}):
            client = DeepSeekClient(api_key=None)
            assert client.api_key == "env_override"

    def test_base_url_is_correct(self):
        """Test base URL is set correctly"""
        client = DeepSeekClient(api_key="key")
        assert client.base_url == "https://api.deepseek.com/v1"

    def test_timeout_default_value(self):
        """Test timeout has correct default value"""
        client = DeepSeekClient(api_key="key")
        assert client.timeout == 10.0


# ==================== TEST_CONNECTION TESTS ====================


class TestConnectionMethod:
    """Test test_connection method"""

    @pytest.mark.asyncio
    async def test_connection_success(self):
        """Test successful connection to API"""
        client = DeepSeekClient(api_key="valid_key")

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            result = await client.test_connection()

            assert result is True
            mock_client.get.assert_called_once_with(
                "https://api.deepseek.com/v1/models",
                headers={"Authorization": "Bearer valid_key"}
            )

    @pytest.mark.asyncio
    async def test_connection_no_api_key(self):
        """Test connection fails without API key"""
        with patch.dict("os.environ", {}, clear=True):
            client = DeepSeekClient(api_key="")
            result = await client.test_connection()
            assert result is False

    @pytest.mark.asyncio
    async def test_connection_none_api_key(self):
        """Test connection fails with None API key"""
        with patch.dict("os.environ", {}, clear=True):
            client = DeepSeekClient()
            result = await client.test_connection()
            assert result is False

    @pytest.mark.asyncio
    async def test_connection_failure_status_code(self):
        """Test connection fails with non-200 status code"""
        client = DeepSeekClient(api_key="valid_key")

        # Mock 401 Unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            result = await client.test_connection()

            assert result is False

    @pytest.mark.asyncio
    async def test_connection_exception_httpx_error(self):
        """Test connection fails on httpx exception"""
        client = DeepSeekClient(api_key="valid_key")

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.RequestError("Network error")

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            result = await client.test_connection()

            assert result is False

    @pytest.mark.asyncio
    async def test_connection_exception_timeout(self):
        """Test connection fails on timeout"""
        client = DeepSeekClient(api_key="valid_key")

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Request timeout")

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            result = await client.test_connection()

            assert result is False

    @pytest.mark.asyncio
    async def test_connection_exception_generic(self):
        """Test connection fails on generic exception"""
        client = DeepSeekClient(api_key="valid_key")

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Unexpected error")

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            result = await client.test_connection()

            assert result is False

    @pytest.mark.asyncio
    async def test_connection_uses_correct_timeout(self):
        """Test connection uses correct timeout value"""
        client = DeepSeekClient(api_key="test_key")

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            await client.test_connection()

            # Verify AsyncClient was created with correct timeout
            mock_async_client.assert_called_once_with(timeout=10.0)


# ==================== CHECK_HEALTH TESTS ====================


class TestCheckHealthMethod:
    """Test check_health method"""

    @pytest.mark.asyncio
    async def test_check_health_healthy(self):
        """Test health check when API is healthy"""
        client = DeepSeekClient(api_key="valid_key")

        # Mock successful connection
        with patch.object(client, "test_connection", return_value=True):
            result = await client.check_health()

            assert result["status"] == "healthy"
            assert result["service"] == "DeepSeek API"
            assert result["available"] is True
            assert "failure_count" in result
            assert "circuit_breaker_state" in result

    @pytest.mark.asyncio
    async def test_check_health_unhealthy(self):
        """Test health check when API is unhealthy"""
        client = DeepSeekClient(api_key="")

        # Mock failed connection
        with patch.object(client, "test_connection", return_value=False):
            result = await client.check_health()

            assert result["status"] == "unhealthy"
            assert result["service"] == "DeepSeek API"
            assert result["available"] is False
            assert "failure_count" in result
            assert "circuit_breaker_state" in result

    @pytest.mark.asyncio
    async def test_check_health_calls_test_connection(self):
        """Test that check_health calls test_connection"""
        client = DeepSeekClient(api_key="test_key")

        mock_test_connection = AsyncMock(return_value=True)

        with patch.object(client, "test_connection", mock_test_connection):
            await client.check_health()

            mock_test_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_health_structure(self):
        """Test health check response structure"""
        client = DeepSeekClient(api_key="key")

        with patch.object(client, "test_connection", return_value=True):
            result = await client.check_health()

            # Verify all required keys
            assert "status" in result
            assert "service" in result
            assert "available" in result

            # Verify types
            assert isinstance(result["status"], str)
            assert isinstance(result["service"], str)
            assert isinstance(result["available"], bool)


# ==================== INTEGRATION TESTS ====================


class TestDeepSeekClientIntegration:
    """Integration tests for DeepSeekClient"""

    @pytest.mark.asyncio
    async def test_full_workflow_success(self):
        """Test full workflow with successful connection"""
        client = DeepSeekClient(api_key="integration_key")

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            # Test connection
            connection_ok = await client.test_connection()
            assert connection_ok is True

            # Test health check
            health = await client.check_health()
            assert health["status"] == "healthy"
            assert health["available"] is True

    @pytest.mark.asyncio
    async def test_full_workflow_failure(self):
        """Test full workflow with failed connection"""
        # Clear environment to ensure empty key
        with patch.dict("os.environ", {}, clear=True):
            client = DeepSeekClient(api_key="")

            # Test connection fails without key
            connection_ok = await client.test_connection()
            assert connection_ok is False

            # Health check reflects failure
            health = await client.check_health()
            assert health["status"] == "unhealthy"
            assert health["available"] is False

    @pytest.mark.asyncio
    async def test_multiple_health_checks(self):
        """Test multiple consecutive health checks"""
        client = DeepSeekClient(api_key="test_key")

        with patch.object(client, "test_connection") as mock_test:
            # Simulate alternating success/failure
            mock_test.side_effect = [True, False, True]

            result1 = await client.check_health()
            result2 = await client.check_health()
            result3 = await client.check_health()

            assert result1["status"] == "healthy"
            assert result2["status"] == "unhealthy"
            assert result3["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_client_reuse(self):
        """Test that client can be reused for multiple calls"""
        client = DeepSeekClient(api_key="reuse_key")

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_http_client = AsyncMock()
        mock_http_client.get.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_http_client

            # Multiple calls
            result1 = await client.test_connection()
            result2 = await client.test_connection()

            assert result1 is True
            assert result2 is True
            assert mock_http_client.get.call_count == 2


# ==================== EDGE CASE TESTS ====================


class TestDeepSeekClientEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_string_api_key(self):
        """Test client with empty string API key"""
        # Clear environment to test empty string explicitly
        with patch.dict("os.environ", {}, clear=True):
            client = DeepSeekClient(api_key="")
            assert client.api_key == ""

    def test_whitespace_api_key(self):
        """Test client with whitespace API key"""
        client = DeepSeekClient(api_key="   ")
        assert client.api_key == "   "

    @pytest.mark.asyncio
    async def test_connection_with_special_characters_in_key(self):
        """Test connection with special characters in API key"""
        client = DeepSeekClient(api_key="sk-!@#$%^&*()")

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            result = await client.test_connection()

            # Should work with special characters
            assert result is True
            mock_client.get.assert_called_once()
            call_headers = mock_client.get.call_args[1]["headers"]
            assert call_headers["Authorization"] == "Bearer sk-!@#$%^&*()"

    @pytest.mark.asyncio
    async def test_connection_status_codes(self):
        """Test various HTTP status codes"""
        client = DeepSeekClient(api_key="test_key")

        status_codes = [200, 201, 401, 403, 404, 500, 502, 503]

        for status_code in status_codes:
            mock_response = MagicMock()
            mock_response.status_code = status_code

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response

            with patch("httpx.AsyncClient") as mock_async_client:
                mock_async_client.return_value.__aenter__.return_value = mock_client

                result = await client.test_connection()

                # Only 200 is success
                assert result == (status_code == 200)

    @pytest.mark.asyncio
    async def test_health_check_exception_propagation(self):
        """Test that exceptions in test_connection are handled"""
        client = DeepSeekClient(api_key="test_key")

        # Mock test_connection to raise exception
        async def failing_connection():
            raise Exception("Simulated failure")

        with patch.object(client, "test_connection", side_effect=Exception("Error")):
            # Should raise exception (not caught in check_health)
            with pytest.raises(Exception):
                await client.check_health()

    @pytest.mark.asyncio
    async def test_long_api_key(self):
        """Test client with very long API key"""
        long_key = "sk-" + "x" * 1000
        client = DeepSeekClient(api_key=long_key)

        assert client.api_key == long_key

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            result = await client.test_connection()
            assert result is True
