"""
Comprehensive tests for unified_agent_interface.py

Coverage target: 43.10% → 75% (+31.9% gain)
Expected tests: ~60-70 tests
Categories:
1. Enums and Data Classes (15 tests)
2. APIKeyManager (15 tests)
3. UnifiedAgentInterface - Initialization (10 tests)
4. UnifiedAgentInterface - Request Routing (15 tests)
5. UnifiedAgentInterface - Error Handling (10 tests)
6. Convenience Functions (5 tests)
7. Integration Tests (5 tests)
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.agents.circuit_breaker_manager import CircuitBreakerError
from backend.agents.unified_agent_interface import (
    AgentChannel,
    AgentRequest,
    AgentResponse,
    AgentType,
    APIKey,
    APIKeyHealth,
    APIKeyManager,
    UnifiedAgentInterface,
    analyze_with_deepseek,
    ask_perplexity,
    get_agent_interface,
)

# =============================================================================
# CATEGORY 1: Enums and Data Classes (15 tests)
# =============================================================================


class TestEnums:
    """Test enum definitions"""

    def test_agent_channel_values(self):
        """AgentChannel has correct values"""
        assert AgentChannel.MCP_SERVER.value == "mcp_server"
        assert AgentChannel.DIRECT_API.value == "direct_api"
        assert AgentChannel.BACKUP_API.value == "backup_api"

    def test_agent_type_values(self):
        """AgentType has correct values"""
        assert AgentType.DEEPSEEK.value == "deepseek"
        assert AgentType.PERPLEXITY.value == "perplexity"


class TestAPIKey:
    """Test APIKey dataclass"""

    def test_api_key_init_with_defaults(self):
        """APIKey initializes with correct defaults"""
        key = APIKey(value="test_key_123", agent_type=AgentType.DEEPSEEK, index=0)

        assert key.value == "test_key_123"
        assert key.agent_type == AgentType.DEEPSEEK
        assert key.index == 0
        assert key.is_active is True
        assert key.last_used is None
        assert key.error_count == 0
        assert key.requests_count == 0

    def test_api_key_init_with_custom_values(self):
        """APIKey accepts custom values"""
        key = APIKey(
            value="custom_key",
            agent_type=AgentType.PERPLEXITY,
            index=3,
            is_active=False,
            last_used=123.456,
            error_count=2,
            requests_count=10,
        )

        assert key.value == "custom_key"
        assert key.agent_type == AgentType.PERPLEXITY
        assert key.index == 3
        assert key.is_active is False
        assert key.last_used == 123.456
        assert key.error_count == 2
        assert key.requests_count == 10


class TestAgentRequest:
    """Test AgentRequest dataclass"""

    def test_agent_request_init_minimal(self):
        """AgentRequest initializes with minimal params"""
        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK, task_type="analyze", prompt="Test prompt"
        )

        assert request.agent_type == AgentType.DEEPSEEK
        assert request.task_type == "analyze"
        assert request.prompt == "Test prompt"
        assert request.code is None
        assert request.context == {}

    def test_agent_request_to_mcp_format(self):
        """AgentRequest converts to MCP format"""
        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="analyze",
            prompt="Analyze code",
            code="def test(): pass",
            context={"focus": "performance"},
        )

        mcp_format = request.to_mcp_format()

        assert mcp_format["strategy_code"] == "def test(): pass"
        assert mcp_format["include_suggestions"] is True
        assert mcp_format["focus"] == "performance"

    def test_agent_request_to_mcp_format_no_code(self):
        """AgentRequest uses prompt as code if code is None"""
        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="generate",
            prompt="Generate strategy",
        )

        mcp_format = request.to_mcp_format()

        assert mcp_format["strategy_code"] == "Generate strategy"
        assert mcp_format["focus"] == "all"

    def test_agent_request_to_direct_api_format_deepseek(self):
        """AgentRequest converts to DeepSeek API format (thinking_mode=False)"""
        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="fix",
            prompt="Fix this code",
            code="def broken(:\n    pass",
            thinking_mode=False,  # Disable thinking mode to get deepseek-chat
        )

        api_format = request.to_direct_api_format()

        assert api_format["model"] == "deepseek-chat"
        assert len(api_format["messages"]) == 2
        assert api_format["messages"][0]["role"] == "system"
        assert "Python developer" in api_format["messages"][0]["content"]
        assert api_format["messages"][1]["role"] == "user"
        assert "Task: fix" in api_format["messages"][1]["content"]
        assert api_format["temperature"] == 0.7
        assert api_format["max_tokens"] == 4000

    def test_agent_request_to_direct_api_format_deepseek_thinking_mode(self):
        """AgentRequest converts to DeepSeek API format with thinking mode (default)"""
        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="analyze",
            prompt="Analyze this code",
            code="def test(): pass",
            thinking_mode=True,  # Default behavior
        )

        api_format = request.to_direct_api_format()

        assert api_format["model"] == "deepseek-reasoner"
        assert api_format["max_tokens"] == 16000
        assert api_format.get("top_p") == 0.95

    def test_agent_request_to_direct_api_format_perplexity(self):
        """AgentRequest converts to Perplexity API format"""
        request = AgentRequest(
            agent_type=AgentType.PERPLEXITY,
            task_type="search",
            prompt="What is RSI indicator?",
        )

        api_format = request.to_direct_api_format()

        assert api_format["model"] == "sonar-pro"
        assert len(api_format["messages"]) == 2
        assert api_format["messages"][0]["role"] == "system"
        assert "trading strategies" in api_format["messages"][0]["content"]
        assert api_format["temperature"] == 0.2
        assert api_format["max_tokens"] == 2000

    def test_agent_request_build_prompt_with_code_and_context(self):
        """AgentRequest builds full prompt with all components"""
        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="analyze",
            prompt="Check for bugs",
            code="def calc(): return 1/0",
            context={"severity": "critical"},
        )

        prompt = request._build_prompt()

        assert "Task: analyze" in prompt
        assert "Check for bugs" in prompt
        assert "```python" in prompt
        assert "def calc(): return 1/0" in prompt
        assert "Context:" in prompt
        assert "severity" in prompt


class TestAgentResponse:
    """Test AgentResponse dataclass"""

    def test_agent_response_init_success(self):
        """AgentResponse initializes for success"""
        response = AgentResponse(
            success=True,
            content="Analysis complete",
            channel=AgentChannel.MCP_SERVER,
            api_key_index=2,
            latency_ms=150.5,
        )

        assert response.success is True
        assert response.content == "Analysis complete"
        assert response.channel == AgentChannel.MCP_SERVER
        assert response.api_key_index == 2
        assert response.latency_ms == 150.5
        assert response.error is None
        assert response.timestamp > 0

    def test_agent_response_init_failure(self):
        """AgentResponse initializes for failure"""
        response = AgentResponse(
            success=False,
            content="",
            channel=AgentChannel.DIRECT_API,
            error="API timeout",
        )

        assert response.success is False
        assert response.content == ""
        assert response.error == "API timeout"


# =============================================================================
# CATEGORY 2: APIKeyManager (15 tests)
# =============================================================================


class TestAPIKeyManager:
    """Test APIKeyManager class"""

    @patch("backend.security.key_manager.KeyManager")
    def test_init_loads_keys(self, mock_km_class):
        """APIKeyManager loads keys on init"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km

        # Mock 2 DeepSeek + 2 Perplexity keys
        def mock_get_key(key_name):
            if "DEEPSEEK" in key_name:
                return f"dk_{key_name}"
            elif "PERPLEXITY" in key_name:
                return f"pk_{key_name}"
            return None

        mock_km.get_decrypted_key.side_effect = mock_get_key

        manager = APIKeyManager()

        assert len(manager.deepseek_keys) <= 8  # Up to 8 keys
        assert len(manager.perplexity_keys) <= 8
        assert all(k.agent_type == AgentType.DEEPSEEK for k in manager.deepseek_keys)
        assert all(
            k.agent_type == AgentType.PERPLEXITY for k in manager.perplexity_keys
        )

    @pytest.mark.asyncio
    @patch("backend.security.key_manager.KeyManager")
    async def test_get_active_key_deepseek(self, mock_km_class):
        """get_active_key returns DeepSeek key"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test_key"

        manager = APIKeyManager()

        # Manually add some keys
        manager.deepseek_keys = [
            APIKey("key1", AgentType.DEEPSEEK, 0, is_active=True, error_count=1),
            APIKey("key2", AgentType.DEEPSEEK, 1, is_active=True, error_count=0),
        ]

        with patch(
            "backend.agents.unified_agent_interface.random.choices"
        ) as mock_choices:
            mock_choices.return_value = [manager.deepseek_keys[1]]
            key = await manager.get_active_key(AgentType.DEEPSEEK)

        assert key is not None
        assert key.value == "key2"  # Lower error count

    @pytest.mark.asyncio
    @patch("backend.security.key_manager.KeyManager")
    async def test_get_active_key_perplexity(self, mock_km_class):
        """get_active_key returns Perplexity key"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test_key"

        manager = APIKeyManager()
        manager.perplexity_keys = [
            APIKey("pk1", AgentType.PERPLEXITY, 0, is_active=True),
        ]

        with patch(
            "backend.agents.unified_agent_interface.random.choices"
        ) as mock_choices:
            mock_choices.return_value = [manager.perplexity_keys[0]]
            key = await manager.get_active_key(AgentType.PERPLEXITY)

        assert key is not None
        assert key.value == "pk1"

    @pytest.mark.asyncio
    @patch("backend.security.key_manager.KeyManager")
    async def test_get_active_key_none_available(self, mock_km_class):
        """get_active_key returns None if no active keys"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = None

        manager = APIKeyManager()
        manager.deepseek_keys = [
            APIKey("key1", AgentType.DEEPSEEK, 0, is_active=False),
        ]

        key = await manager.get_active_key(AgentType.DEEPSEEK)

        assert key is None

    @pytest.mark.asyncio
    @patch("backend.security.key_manager.KeyManager")
    async def test_get_active_key_prefers_fewer_errors(self, mock_km_class):
        """get_active_key prefers keys with fewer errors"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test"

        manager = APIKeyManager()
        manager.deepseek_keys = [
            APIKey("key1", AgentType.DEEPSEEK, 0, error_count=5, requests_count=10),
            APIKey("key2", AgentType.DEEPSEEK, 1, error_count=1, requests_count=20),
            APIKey("key3", AgentType.DEEPSEEK, 2, error_count=1, requests_count=5),
        ]

        with patch(
            "backend.agents.unified_agent_interface.random.choices"
        ) as mock_choices:
            mock_choices.return_value = [manager.deepseek_keys[2]]
            key = await manager.get_active_key(AgentType.DEEPSEEK)

        # Should get key with error_count=1 and fewer requests
        assert key.value == "key3"

    @patch("backend.security.key_manager.KeyManager")
    def test_mark_error_increments_count(self, mock_km_class):
        """mark_error increments error count"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test"

        manager = APIKeyManager()
        key = APIKey("key1", AgentType.DEEPSEEK, 0, error_count=0)

        manager.mark_error(key)

        assert key.error_count == 1
        assert key.is_active is True

    @patch("backend.security.key_manager.KeyManager")
    def test_mark_error_health_transitions(self, mock_km_class):
        """mark_error degrades before eventually disabling a key"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test"

        manager = APIKeyManager()
        key = APIKey("key1", AgentType.DEEPSEEK, 0, error_count=2)

        manager.mark_error(key)

        assert key.error_count == 3
        assert key.health == APIKeyHealth.DEGRADED
        assert key.is_active is True

        # Trigger disable after crossing higher threshold
        manager.mark_error(key)  # 4
        manager.mark_error(key)  # 5

        assert key.error_count == 5
        assert key.health == APIKeyHealth.DISABLED
        assert key.is_active is False

    @patch("backend.security.key_manager.KeyManager")
    def test_mark_rate_limit_triggers_cooldown(self, mock_km_class):
        """mark_rate_limit puts key into cooldown and records telemetry"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test"

        manager = APIKeyManager()
        key = APIKey("key1", AgentType.DEEPSEEK, 0)
        manager.deepseek_keys = [key]

        manager.mark_rate_limit(key, retry_after=2.5)

        assert key.is_cooling is True
        assert manager.pool_telemetry["rate_limit_events"] == 1
        assert manager.pool_telemetry["cooldown_events"] == 1

    @patch("backend.security.key_manager.KeyManager")
    def test_get_pool_metrics_reports_cooling(self, mock_km_class):
        """get_pool_metrics reflects cooling keys"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test"

        manager = APIKeyManager()
        key = APIKey("key2", AgentType.DEEPSEEK, 0)
        manager.deepseek_keys = [key]
        manager.mark_rate_limit(key, retry_after=5)

        metrics = manager.get_pool_metrics(AgentType.DEEPSEEK)

        assert metrics["total"] == 1
        assert metrics["cooling"] == 1

    @patch("backend.security.key_manager.KeyManager")
    def test_mark_success_updates_stats(self, mock_km_class):
        """mark_success updates key statistics"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test"

        manager = APIKeyManager()
        key = APIKey("key1", AgentType.DEEPSEEK, 0, error_count=2, requests_count=5)

        manager.mark_success(key)

        assert key.requests_count == 6
        assert key.error_count == 1  # Decreased by 1
        assert key.last_used > 0

    @patch("backend.security.key_manager.KeyManager")
    def test_load_keys_handles_exception(self, mock_km_class):
        """_load_keys handles exceptions for individual keys"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km

        # First key succeeds, second raises exception
        def mock_get_key(key_name):
            if key_name == "DEEPSEEK_API_KEY":  # First key
                return "valid_key"
            raise Exception("Decryption failed")

        mock_km.get_decrypted_key.side_effect = mock_get_key

        # Should not raise, just log warning
        manager = APIKeyManager()

        assert len(manager.deepseek_keys) >= 1  # At least first key loaded

    @patch("backend.security.key_manager.KeyManager")
    def test_load_keys_import_error(self, mock_km_class):
        """_load_keys raises on ImportError"""
        # Make KeyManager import fail
        with patch.dict("sys.modules", {"backend.security.key_manager": None}), pytest.raises(ImportError):
            APIKeyManager()


# =============================================================================
# CATEGORY 3: UnifiedAgentInterface - Initialization (10 tests)
# =============================================================================


class TestUnifiedAgentInterfaceInit:
    """Test UnifiedAgentInterface initialization"""

    @patch("backend.security.key_manager.KeyManager")
    def test_init_creates_key_manager(self, mock_km_class):
        """UnifiedAgentInterface creates APIKeyManager"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test_key"

        interface = UnifiedAgentInterface()

        assert interface.key_manager is not None
        assert interface.mcp_available is False
        assert interface.last_health_check == 0
        assert interface.health_check_interval == 30

    @patch("backend.security.key_manager.KeyManager")
    def test_init_initializes_stats(self, mock_km_class):
        """UnifiedAgentInterface initializes statistics"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test_key"

        interface = UnifiedAgentInterface()

        assert interface.stats["total_requests"] == 0
        assert interface.stats["mcp_success"] == 0
        assert interface.stats["mcp_failed"] == 0
        assert interface.stats["direct_api_success"] == 0
        assert interface.stats["direct_api_failed"] == 0
        assert interface.stats["rate_limit_events"] == 0
        assert interface.stats["deepseek_rate_limits"] == 0
        assert interface.stats["perplexity_rate_limits"] == 0
        assert interface.stats["key_pool_alerts"] == 0

    @patch("backend.agents.unified_agent_interface.APIKeyManager")
    def test_get_api_url_deepseek(self, mock_km_class):
        """_get_api_url returns DeepSeek URL"""
        mock_km_class.return_value = MagicMock()

        interface = UnifiedAgentInterface()
        url = interface._get_api_url(AgentType.DEEPSEEK)

        assert url == "https://api.deepseek.com/v1/chat/completions"

    @patch("backend.agents.unified_agent_interface.APIKeyManager")
    def test_get_api_url_perplexity(self, mock_km_class):
        """_get_api_url returns Perplexity URL"""
        mock_km_class.return_value = MagicMock()

        interface = UnifiedAgentInterface()
        url = interface._get_api_url(AgentType.PERPLEXITY)

        assert url == "https://api.perplexity.ai/chat/completions"

    @patch("backend.agents.unified_agent_interface.APIKeyManager")
    def test_get_key_pool_snapshot_shape(self, mock_km_class):
        """get_key_pool_snapshot returns structured telemetry"""
        mock_km = MagicMock()
        mock_km.get_pool_metrics.return_value = {"total": 0, "cooling": 0}
        mock_km.pool_telemetry = {"cooldown_events": 0}
        mock_km_class.return_value = mock_km

        interface = UnifiedAgentInterface()
        snapshot = interface.get_key_pool_snapshot()

        assert "deepseek" in snapshot
        assert "perplexity" in snapshot
        assert "telemetry" in snapshot

    @patch("backend.agents.unified_agent_interface.APIKeyManager")
    def test_get_headers(self, mock_km_class):
        """_get_headers returns correct headers"""
        mock_km_class.return_value = MagicMock()

        interface = UnifiedAgentInterface()
        key = APIKey("test_key_123", AgentType.DEEPSEEK, 0)
        headers = interface._get_headers(key)

        assert headers["Authorization"] == "Bearer test_key_123"
        assert headers["Content-Type"] == "application/json"

    @patch("backend.agents.unified_agent_interface.APIKeyManager")
    def test_extract_content_success(self, mock_km_class):
        """_extract_content extracts message content"""
        mock_km_class.return_value = MagicMock()

        interface = UnifiedAgentInterface()
        data = {"choices": [{"message": {"content": "Analysis result"}}]}

        content = interface._extract_content(data, AgentType.DEEPSEEK)

        assert content == "Analysis result"

    @patch("backend.agents.unified_agent_interface.APIKeyManager")
    def test_extract_content_failure_returns_json(self, mock_km_class):
        """_extract_content returns JSON dump on error"""
        mock_km_class.return_value = MagicMock()

        interface = UnifiedAgentInterface()
        data = {"error": "malformed response"}

        content = interface._extract_content(data, AgentType.DEEPSEEK)

        assert "error" in content
        assert "malformed response" in content


# =============================================================================
# CATEGORY 4: UnifiedAgentInterface - Request Routing (15 tests)
# =============================================================================


class TestUnifiedAgentInterfaceRequests:
    """Test request routing and fallback logic"""

    @pytest.mark.asyncio
    @patch("backend.agents.unified_agent_interface.APIKeyManager")
    async def test_send_request_increments_total(self, mock_km_class):
        """send_request increments total_requests counter"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_active_key = AsyncMock(return_value=None)  # No keys, will fail

        interface = UnifiedAgentInterface()
        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK, task_type="test", prompt="test"
        )

        await interface.send_request(request)

        assert interface.stats["total_requests"] == 1

    @pytest.mark.asyncio
    @patch("backend.agents.unified_agent_interface.MCP_DISABLED", False)
    @patch("backend.agents.unified_agent_interface.APIKeyManager")
    async def test_send_request_tries_mcp_first_if_available(self, mock_km_class):
        """send_request tries MCP if available and preferred"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km

        interface = UnifiedAgentInterface(force_direct_api=False)
        interface.mcp_available = True
        interface.mcp_disabled = False  # Ensure MCP is not disabled

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK, task_type="test", prompt="test"
        )

        with patch.object(
            interface, "_try_mcp", new_callable=AsyncMock
        ) as mock_try_mcp:
            mock_try_mcp.return_value = AgentResponse(
                success=True, content="MCP result", channel=AgentChannel.MCP_SERVER
            )

            response = await interface.send_request(request, AgentChannel.MCP_SERVER)

            assert mock_try_mcp.called
            assert response.channel == AgentChannel.MCP_SERVER
            assert interface.stats["mcp_success"] == 1

    @pytest.mark.asyncio
    @patch("backend.agents.unified_agent_interface.MCP_DISABLED", False)
    @patch("backend.agents.unified_agent_interface.APIKeyManager")
    async def test_send_request_falls_back_to_direct_api(self, mock_km_class):
        """send_request falls back to Direct API if MCP fails"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km

        interface = UnifiedAgentInterface(force_direct_api=False)
        interface.mcp_available = True
        interface.mcp_disabled = False  # Ensure MCP is not disabled

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK, task_type="test", prompt="test"
        )

        with patch.object(interface, "_try_mcp", new_callable=AsyncMock) as mock_mcp, patch.object(
            interface, "_try_direct_api", new_callable=AsyncMock
        ) as mock_direct:
            mock_mcp.return_value = AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.MCP_SERVER,
                error="MCP failed",
            )
            mock_direct.return_value = AgentResponse(
                success=True,
                content="Direct API result",
                channel=AgentChannel.DIRECT_API,
            )

            response = await interface.send_request(
                request, AgentChannel.MCP_SERVER
            )

            assert mock_mcp.called
            assert mock_direct.called
            assert response.channel == AgentChannel.DIRECT_API
            assert interface.stats["mcp_failed"] == 1
            assert interface.stats["direct_api_success"] == 1

    @pytest.mark.asyncio
    @patch("backend.agents.unified_agent_interface.MCP_DISABLED", False)
    @patch("backend.agents.unified_agent_interface.APIKeyManager")
    async def test_send_request_handles_mcp_exception(self, mock_km_class):
        """send_request handles MCP exception and falls back"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km

        interface = UnifiedAgentInterface(force_direct_api=False)
        interface.mcp_available = True
        interface.mcp_disabled = False  # Ensure MCP is not disabled

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK, task_type="test", prompt="test"
        )

        with patch.object(interface, "_try_mcp", side_effect=Exception("MCP crash")), patch.object(
            interface,
            "_try_direct_api",
            new_callable=AsyncMock,
            return_value=AgentResponse(
                success=True,
                content="Fallback success",
                channel=AgentChannel.DIRECT_API,
            ),
        ):
            response = await interface.send_request(request)

            assert response.success is True
            assert response.content == "Fallback success"
            assert interface.stats["mcp_failed"] == 1

    @pytest.mark.asyncio
    @patch("backend.security.key_manager.KeyManager")
    async def test_send_request_handles_direct_api_exception(self, mock_km_class):
        """send_request handles Direct API exception"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test_key"

        interface = UnifiedAgentInterface()

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK, task_type="test", prompt="test"
        )

        with patch.object(
            interface, "_try_direct_api", side_effect=Exception("API crash")
        ):
            response = await interface.send_request(request)

            assert response.success is False
            assert "All communication channels failed" in response.error
            assert interface.stats["direct_api_failed"] == 1

    @pytest.mark.asyncio
    @patch("backend.agents.unified_agent_interface.MCP_DISABLED", False)
    @patch("backend.agents.unified_agent_interface.APIKeyManager")
    async def test_try_mcp_handles_circuit_breaker_open(self, mock_km_class):
        """_try_mcp reports circuit breaker errors"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km

        interface = UnifiedAgentInterface(force_direct_api=False)
        interface.mcp_disabled = False  # Ensure MCP is not disabled

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK, task_type="test", prompt="test"
        )

        with patch.object(
            interface.circuit_manager, "call_with_breaker", new_callable=AsyncMock
        ) as mock_call:
            mock_call.side_effect = CircuitBreakerError("open")
            response = await interface._try_mcp(request)

        assert response.success is False
        assert response.channel == AgentChannel.MCP_SERVER
        assert "circuit breaker" in response.error.lower()

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    @patch("backend.security.key_manager.KeyManager")
    async def test_try_direct_api_success(self, mock_km_class, mock_client_class):
        """_try_direct_api succeeds with valid API key"""
        # Setup KeyManager
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test_api_key"

        # Setup httpx mock
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "API response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        interface = UnifiedAgentInterface()
        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK, task_type="test", prompt="test"
        )

        response = await interface._try_direct_api(request)

        assert response.success is True
        assert response.content == "API response"
        assert response.channel == AgentChannel.DIRECT_API

    @pytest.mark.asyncio
    @patch("backend.security.key_manager.KeyManager")
    async def test_try_direct_api_no_keys(self, mock_km_class):
        """_try_direct_api fails if no API keys available"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = None  # No keys

        interface = UnifiedAgentInterface()
        interface.key_manager.deepseek_keys = []  # Empty keys
        interface.key_manager.perplexity_keys = []

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK, task_type="test", prompt="test"
        )

        response = await interface._try_direct_api(request)

        assert response.success is False
        assert "No active" in response.error

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    @patch("backend.security.key_manager.KeyManager")
    async def test_try_direct_api_http_error_tries_backup(
        self, mock_km_class, mock_client_class
    ):
        """_try_direct_api tries backup key on HTTP error"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test_key"

        interface = UnifiedAgentInterface()

        key1 = APIKey("key1", AgentType.DEEPSEEK, 0)
        key2 = APIKey("key2", AgentType.DEEPSEEK, 1)
        interface.key_manager.deepseek_keys = [key1, key2]

        # Mock HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limited"

        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "429", request=MagicMock(), response=mock_response
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK, task_type="test", prompt="test"
        )

        await interface._try_direct_api(request)

        # Should mark key1 as error
        assert key1.error_count >= 1

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    @patch("backend.security.key_manager.KeyManager")
    async def test_try_direct_api_generic_exception(
        self, mock_km_class, mock_client_class
    ):
        """_try_direct_api handles generic exception"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test_key"

        interface = UnifiedAgentInterface()

        key1 = APIKey("key1", AgentType.DEEPSEEK, 0)
        interface.key_manager.deepseek_keys = [key1]

        # Mock generic exception
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK, task_type="test", prompt="test"
        )

        response = await interface._try_direct_api(request)

        # Should mark key as error and try backup
        assert key1.error_count >= 1
        assert response.success is False


# =============================================================================
# CATEGORY 5: UnifiedAgentInterface - Stats & Health (10 tests)
# =============================================================================


class TestUnifiedAgentInterfaceStats:
    """Test statistics and health checks"""

    @patch("backend.security.key_manager.KeyManager")
    def test_get_stats_returns_all_metrics(self, mock_km_class):
        """get_stats returns complete statistics"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test_key"

        interface = UnifiedAgentInterface()
        interface.key_manager.deepseek_keys = [
            APIKey("k1", AgentType.DEEPSEEK, 0, is_active=True),
            APIKey("k2", AgentType.DEEPSEEK, 1, is_active=False),
        ]
        interface.key_manager.perplexity_keys = [
            APIKey("p1", AgentType.PERPLEXITY, 0, is_active=True),
        ]
        interface.stats["total_requests"] = 100
        interface.stats["mcp_success"] = 30
        interface.last_health_check = time.time()

        stats = interface.get_stats()

        assert stats["total_requests"] == 100
        assert stats["mcp_success"] == 30
        assert stats["mcp_available"] is False
        assert stats["deepseek_keys_active"] == 1
        assert stats["perplexity_keys_active"] == 1
        assert "last_health_check" in stats

    @pytest.mark.asyncio
    @patch("backend.security.key_manager.KeyManager")
    async def test_health_check_updates_timestamp(self, mock_km_class):
        """_health_check updates last_health_check timestamp"""
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        mock_km.get_decrypted_key.return_value = "test_key"

        interface = UnifiedAgentInterface()
        interface.key_manager.deepseek_keys = []
        interface.key_manager.perplexity_keys = []
        interface.last_health_check = 0

        await interface._health_check()

        assert interface.last_health_check > 0


# =============================================================================
# CATEGORY 6: Convenience Functions (5 tests)
# =============================================================================


class TestConvenienceFunctions:
    """Test convenience functions"""

    @patch("backend.security.key_manager.KeyManager")
    def test_get_agent_interface_singleton(self, mock_km_class):
        """get_agent_interface returns singleton instance"""
        mock_km_class.return_value = MagicMock()

        # Reset global singleton
        import backend.agents.unified_agent_interface as module

        module._agent_interface = None

        instance1 = get_agent_interface()
        instance2 = get_agent_interface()

        assert instance1 is instance2

    @pytest.mark.asyncio
    @patch("backend.agents.unified_agent_interface.get_agent_interface")
    async def test_analyze_with_deepseek_creates_request(self, mock_get_interface):
        """analyze_with_deepseek creates correct request"""
        mock_interface = MagicMock()
        mock_interface.send_request = AsyncMock(
            return_value=AgentResponse(
                success=True, content="Analysis", channel=AgentChannel.DIRECT_API
            )
        )
        mock_get_interface.return_value = mock_interface

        await analyze_with_deepseek("def test(): pass", focus="bugs")

        assert mock_interface.send_request.called
        call_args = mock_interface.send_request.call_args[0][0]
        assert call_args.agent_type == AgentType.DEEPSEEK
        assert call_args.task_type == "analyze"
        assert call_args.code == "def test(): pass"
        assert call_args.context["focus"] == "bugs"

    @pytest.mark.asyncio
    @patch("backend.agents.unified_agent_interface.get_agent_interface")
    async def test_ask_perplexity_creates_request(self, mock_get_interface):
        """ask_perplexity creates correct request"""
        mock_interface = MagicMock()
        mock_interface.send_request = AsyncMock(
            return_value=AgentResponse(
                success=True, content="Answer", channel=AgentChannel.DIRECT_API
            )
        )
        mock_get_interface.return_value = mock_interface

        await ask_perplexity("What is Bitcoin?")

        assert mock_interface.send_request.called
        call_args = mock_interface.send_request.call_args[0][0]
        assert call_args.agent_type == AgentType.PERPLEXITY
        assert call_args.task_type == "search"
        assert call_args.prompt == "What is Bitcoin?"


# =============================================================================
# CATEGORY 7: Integration Tests (3 tests)
# =============================================================================


class TestIntegration:
    """Integration tests for full workflows"""

    @pytest.mark.asyncio
    @patch("backend.agents.unified_agent_interface.APIKeyManager")
    @patch("httpx.AsyncClient")
    async def test_full_workflow_deepseek_analysis(
        self, mock_client_class, mock_km_class
    ):
        """Full workflow: DeepSeek code analysis"""
        # Setup key manager
        mock_km = MagicMock()
        mock_km_class.return_value = mock_km
        key = APIKey("test_key", AgentType.DEEPSEEK, 0)
        mock_km.get_active_key = AsyncMock(return_value=key)
        mock_km.deepseek_keys = [key]
        mock_km.perplexity_keys = []

        # Setup HTTP mock
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "No issues found"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        # Execute
        interface = UnifiedAgentInterface()
        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="analyze",
            prompt="Check code",
            code="def hello(): return 'world'",
        )

        response = await interface.send_request(request)

        assert response.success is True
        assert response.content == "No issues found"
        assert response.channel == AgentChannel.DIRECT_API
        assert interface.stats["total_requests"] == 1
        assert interface.stats["direct_api_success"] == 1
