"""
🧪 Tests for AI Agent Background Service

Coverage Target: 0% → 60% (baseline +60%)
Expected Tests: 40-50 tests across 8 categories

Module: backend/agents/agent_background_service.py
Size: ~400 lines, ~220 statements
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, Mock

import pytest
import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.agents.agent_background_service import AIAgentBackgroundService
from backend.agents.unified_agent_interface import AgentRequest, AgentResponse, AgentType, APIKey, APIKeyManager
from backend.agents.circuit_breaker_manager import CircuitState


# =============================================================================
# Test Helpers
# =============================================================================

def create_api_key(value="test_key", agent_type=AgentType.DEEPSEEK, index=0, is_active=True, error_count=0):
    """Helper to create APIKey for testing"""
    key = APIKey(
        value=value,
        agent_type=agent_type,
        index=index
    )
    key.is_active = is_active
    key.error_count = error_count
    return key


# =============================================================================
# Category 1: Initialization (6 tests)
# =============================================================================

class TestAIAgentBackgroundServiceInit:
    """Test service initialization"""
    
    @pytest.mark.asyncio
    async def test_init_creates_interface(self):
        """Test __init__ creates unified agent interface"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            assert service.interface == mock_interface
            assert service.running is False
            assert isinstance(service.start_time, float)
    
    @pytest.mark.asyncio
    async def test_init_sets_default_intervals(self):
        """Test __init__ sets default health check intervals"""
        with patch('backend.agents.agent_background_service.get_agent_interface'):
            service = AIAgentBackgroundService()
            
            assert service.health_check_interval == 30
            assert service.full_health_check_interval == 300
            assert service.last_full_check == 0
    
    @pytest.mark.asyncio
    async def test_init_initializes_stats(self):
        """Test __init__ initializes statistics"""
        with patch('backend.agents.agent_background_service.get_agent_interface'):
            service = AIAgentBackgroundService()
            
            assert service.stats["health_checks"] == 0
            assert service.stats["health_check_failures"] == 0
            assert service.stats["api_key_rotations"] == 0
            assert service.stats["mcp_availability_changes"] == 0
    
    @pytest.mark.asyncio
    async def test_init_fails_if_interface_unavailable(self):
        """Test __init__ raises error if interface initialization fails"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_get.side_effect = RuntimeError("Interface init failed")
            
            with pytest.raises(RuntimeError, match="Interface init failed"):
                AIAgentBackgroundService()
    
    @pytest.mark.asyncio
    async def test_init_logs_success(self):
        """Test __init__ logs success message"""
        with patch('backend.agents.agent_background_service.get_agent_interface'):
            with patch('backend.agents.agent_background_service.logger') as mock_logger:
                service = AIAgentBackgroundService()
                
                mock_logger.success.assert_called_once()
                assert "Unified Agent Interface initialized" in str(mock_logger.success.call_args)
    
    @pytest.mark.asyncio
    async def test_init_start_time_is_current(self):
        """Test __init__ sets start_time to current time"""
        with patch('backend.agents.agent_background_service.get_agent_interface'):
            before = time.time()
            service = AIAgentBackgroundService()
            after = time.time()
            
            assert before <= service.start_time <= after


# =============================================================================
# Category 2: Service Start/Stop (3 tests - simplified to avoid async hangs)
# =============================================================================

class TestServiceStartStop:
    """Test service start and stop"""
    
    @pytest.mark.asyncio
    async def test_start_initial_flow(self):
        """Test start() initial flow: sets running=True, logs info, runs health check"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.key_manager.deepseek_keys = [Mock(), Mock()]
            mock_interface.key_manager.perplexity_keys = [Mock()]
            mock_get.return_value = mock_interface
            
            with patch('backend.agents.agent_background_service.logger') as mock_logger:
                service = AIAgentBackgroundService()
                
                # Mock health check to immediately stop service
                check_count = 0
                async def mock_health_check():
                    nonlocal check_count
                    check_count += 1
                    service.running = False  # Stop after first check
                
                service._comprehensive_health_check = AsyncMock(side_effect=mock_health_check)
                
                # Run service (will stop after first health check)
                await service.start()
                
                # Verify logging
                info_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("STARTED" in call for call in info_calls)
                assert any("DeepSeek keys: 2" in call for call in info_calls)
                assert any("Perplexity keys: 1" in call for call in info_calls)
                
                # Health check should have been called
                assert check_count == 1
    
    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self):
        """Test stop() sets running to False"""
        with patch('backend.agents.agent_background_service.get_agent_interface'):
            service = AIAgentBackgroundService()
            service.running = True
            
            await service.stop()
            
            assert service.running is False
    
    @pytest.mark.asyncio
    async def test_stop_logs_shutdown_message(self):
        """Test stop() logs shutdown message"""
        with patch('backend.agents.agent_background_service.get_agent_interface'):
            with patch('backend.agents.agent_background_service.logger') as mock_logger:
                service = AIAgentBackgroundService()
                
                await service.stop()
                
                info_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("STOPPED" in call for call in info_calls)
    
    @pytest.mark.asyncio
    async def test_start_awaits_health_check_in_loop(self):
        """Test start() awaits health checks with sleep interval"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.key_manager.deepseek_keys = []
            mock_interface.key_manager.perplexity_keys = []
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            service.health_check_interval = 0.01  # Very short for testing
            
            check_count = 0
            async def mock_health_check():
                nonlocal check_count
                check_count += 1
                if check_count >= 2:  # Stop after 2 checks
                    service.running = False
            
            service._comprehensive_health_check = AsyncMock(side_effect=mock_health_check)
            
            await service.start()
            
            # Should have done at least 2 checks
            assert check_count >= 2


# =============================================================================
# Category 3: Health Check Orchestration (5 tests)
# =============================================================================

class TestHealthCheckOrchestration:
    """Test comprehensive health check"""
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_increments_counter(self):
        """Test _comprehensive_health_check increments stats counter"""
        with patch('backend.agents.agent_background_service.get_agent_interface'):
            service = AIAgentBackgroundService()
            service._check_api_keys = AsyncMock()
            service._check_mcp_server = AsyncMock()
            service._test_deepseek_connection = AsyncMock()
            service._test_perplexity_connection = AsyncMock()
            service._print_health_summary = MagicMock()
            
            await service._comprehensive_health_check()
            
            assert service.stats["health_checks"] == 1
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_full_after_interval(self):
        """Test _comprehensive_health_check runs full check after interval"""
        with patch('backend.agents.agent_background_service.get_agent_interface'):
            service = AIAgentBackgroundService()
            service._check_api_keys = AsyncMock()
            service._check_mcp_server = AsyncMock()
            service._test_deepseek_connection = AsyncMock()
            service._test_perplexity_connection = AsyncMock()
            service._test_deepseek_connection_full = AsyncMock()
            service._test_perplexity_connection_full = AsyncMock()
            service._print_health_summary = MagicMock()
            
            # Simulate time passing
            service.last_full_check = time.time() - 400  # 400s ago
            service.full_health_check_interval = 300  # 5 min
            
            await service._comprehensive_health_check()
            
            # Should call full versions
            service._test_deepseek_connection_full.assert_called_once()
            service._test_perplexity_connection_full.assert_called_once()
            
            # Should NOT call lightweight versions
            service._test_deepseek_connection.assert_not_called()
            service._test_perplexity_connection.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_updates_last_full_check(self):
        """Test _comprehensive_health_check updates last_full_check timestamp"""
        with patch('backend.agents.agent_background_service.get_agent_interface'):
            service = AIAgentBackgroundService()
            service._check_api_keys = AsyncMock()
            service._check_mcp_server = AsyncMock()
            service._test_deepseek_connection_full = AsyncMock()
            service._test_perplexity_connection_full = AsyncMock()
            service._print_health_summary = MagicMock()
            
            service.last_full_check = time.time() - 400
            service.full_health_check_interval = 300
            
            before = time.time()
            await service._comprehensive_health_check()
            after = time.time()
            
            assert before <= service.last_full_check <= after
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_handles_exception(self):
        """Test _comprehensive_health_check handles exceptions"""
        with patch('backend.agents.agent_background_service.get_agent_interface'):
            service = AIAgentBackgroundService()
            service._check_api_keys = AsyncMock(side_effect=RuntimeError("Check failed"))
            
            # Should not raise, but increment failure counter
            await service._comprehensive_health_check()
            
            assert service.stats["health_check_failures"] == 1


# =============================================================================
# Category 4: API Key Checks (6 tests)
# =============================================================================

class TestAPIKeyChecks:
    """Test API key health checks"""
    
    @pytest.mark.asyncio
    async def test_check_api_keys_counts_active_keys(self):
        """Test _check_api_keys counts active and total keys"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.key_manager.deepseek_keys = [
                create_api_key(value="key1", agent_type=AgentType.DEEPSEEK, index=0, is_active=True, error_count=0),
                create_api_key(value="key2", agent_type=AgentType.DEEPSEEK, index=1, is_active=False, error_count=5)
            ]
            mock_interface.key_manager.perplexity_keys = [
                create_api_key(value="key3", agent_type=AgentType.PERPLEXITY, index=0, is_active=True, error_count=0)
            ]
            mock_interface._test_key_health = AsyncMock(return_value=True)
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            # Should not raise, just log
            await service._check_api_keys()
    
    @pytest.mark.asyncio
    async def test_check_api_keys_resets_all_disabled_deepseek(self):
        """Test _check_api_keys resets all disabled DeepSeek keys"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            key1 = create_api_key(value="key1", agent_type=AgentType.DEEPSEEK, index=0, is_active=False, error_count=5)
            key2 = create_api_key(value="key2", agent_type=AgentType.DEEPSEEK, index=1, is_active=False, error_count=3)
            mock_interface.key_manager.deepseek_keys = [key1, key2]
            mock_interface.key_manager.perplexity_keys = []
            mock_interface._test_key_health = AsyncMock(return_value=True)
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            await service._check_api_keys()
            
            assert key1.is_active is True
            assert key1.error_count == 1
            assert key2.is_active is True
            assert key2.error_count == 1
            assert service.stats["api_key_rotations"] == 1

    @pytest.mark.asyncio
    async def test_check_api_keys_resets_all_disabled_perplexity(self):
        """Test _check_api_keys resets all disabled Perplexity keys"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            key1 = create_api_key(value="key1", agent_type=AgentType.PERPLEXITY, index=0, is_active=False, error_count=5)
            mock_interface.key_manager.deepseek_keys = []
            mock_interface.key_manager.perplexity_keys = [key1]
            mock_interface._test_key_health = AsyncMock(return_value=True)
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            await service._check_api_keys()
            
            assert key1.is_active is True
            assert key1.error_count == 1
            assert service.stats["api_key_rotations"] == 1
    
    @pytest.mark.asyncio
    async def test_check_api_keys_no_reset_if_any_active(self):
        """Test _check_api_keys doesn't reset if any key is active"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            key1 = create_api_key(value="key1", agent_type=AgentType.DEEPSEEK, index=0, is_active=True, error_count=0)
            key2 = create_api_key(value="key2", agent_type=AgentType.DEEPSEEK, index=1, is_active=False, error_count=5)
            mock_interface.key_manager.deepseek_keys = [key1, key2]
            mock_interface.key_manager.perplexity_keys = []
            mock_interface._test_key_health = AsyncMock(return_value=True)
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            await service._check_api_keys()
            
            # key2 should remain disabled
            assert key2.is_active is False
            assert key2.error_count == 5
            assert service.stats["api_key_rotations"] == 0
    
    @pytest.mark.asyncio
    async def test_check_api_keys_resets_and_increments_stat(self):
        """Test _check_api_keys resets keys and increments rotation stat"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            key1 = create_api_key(value="key1", agent_type=AgentType.DEEPSEEK, index=0, is_active=False, error_count=5)
            mock_interface.key_manager.deepseek_keys = [key1]
            mock_interface.key_manager.perplexity_keys = []
            mock_interface._test_key_health = AsyncMock(return_value=True)
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            await service._check_api_keys()
            
            # Should have reset and incremented stat
            assert key1.is_active is True
            assert key1.error_count == 1
            assert service.stats["api_key_rotations"] == 1
    
    @pytest.mark.asyncio
    async def test_check_api_keys_handles_empty_key_lists(self):
        """Test _check_api_keys handles empty key lists"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.key_manager.deepseek_keys = []
            mock_interface.key_manager.perplexity_keys = []
            mock_interface._test_key_health = AsyncMock(return_value=True)
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            # Should not raise
            await service._check_api_keys()
            
            assert service.stats["api_key_rotations"] == 0


# =============================================================================
# Category 5: MCP Server Checks (4 tests)
# =============================================================================

class TestMCPServerChecks:
    """Test MCP server health checks"""
    
    @pytest.mark.asyncio
    async def test_check_mcp_server_sets_available_on_success(self):
        """_check_mcp_server marks MCP available when health endpoint responds"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.mcp_available = False
            mock_interface.circuit_manager = None
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "status": "healthy",
                "tools_registered": [
                    "mcp_agent_to_agent_send_to_deepseek",
                    "mcp_agent_to_agent_send_to_perplexity",
                    "mcp_agent_to_agent_get_consensus"
                ]
            }
            mock_response.raise_for_status.return_value = None
            
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            
            with patch('backend.agents.agent_background_service.httpx.AsyncClient', return_value=mock_client):
                await service._check_mcp_server()
            
            assert service.interface.mcp_available is True
            assert service.stats["mcp_availability_changes"] == 1
    
    @pytest.mark.asyncio
    async def test_check_mcp_server_sets_unavailable_on_error(self):
        """_check_mcp_server marks MCP unavailable when probe fails"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.mcp_available = True
            mock_interface.circuit_manager = None
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            request_error = httpx.RequestError("boom", request=MagicMock())
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.side_effect = request_error
            
            with patch('backend.agents.agent_background_service.httpx.AsyncClient', return_value=mock_client):
                await service._check_mcp_server()
            
            assert service.interface.mcp_available is False
            assert service.stats["mcp_availability_changes"] == 1
    
    @pytest.mark.asyncio
    async def test_check_mcp_server_no_stat_change_when_state_same(self):
        """No stat increment if availability doesn't change"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.mcp_available = False
            mock_interface.circuit_manager = None
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "status": "error",
                "tools_registered": []
            }
            mock_response.raise_for_status.return_value = None
            
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            
            with patch('backend.agents.agent_background_service.httpx.AsyncClient', return_value=mock_client):
                await service._check_mcp_server()
            
            assert service.stats["mcp_availability_changes"] == 0
    
    @pytest.mark.asyncio
    async def test_check_mcp_server_logs_status(self):
        """_check_mcp_server logs current MCP status"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.mcp_available = False
            mock_interface.circuit_manager = None
            mock_get.return_value = mock_interface
            
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "status": "healthy",
                "tools_registered": [
                    "mcp_agent_to_agent_send_to_deepseek",
                    "mcp_agent_to_agent_send_to_perplexity",
                    "mcp_agent_to_agent_get_consensus"
                ]
            }
            mock_response.raise_for_status.return_value = None
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            
            with patch('backend.agents.agent_background_service.logger') as mock_logger:
                with patch('backend.agents.agent_background_service.httpx.AsyncClient', return_value=mock_client):
                    service = AIAgentBackgroundService()
                    await service._check_mcp_server()
            
            info_calls = " ".join(str(call) for call in mock_logger.info.call_args_list)
            assert "MCP Server" in info_calls

    @pytest.mark.asyncio
    async def test_check_mcp_server_respects_open_breaker(self):
        """Breaker open state skips probe and increments stat"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.mcp_available = True
            circuit_manager = MagicMock()
            circuit_manager.get_breaker_state.return_value = CircuitState.OPEN
            mock_interface.circuit_manager = circuit_manager
            mock_get.return_value = mock_interface

            service = AIAgentBackgroundService()
            service.stats["mcp_breaker_rejections"] = 0

            with patch('backend.agents.agent_background_service.logger') as mock_logger:
                await service._check_mcp_server()

            circuit_manager.call_with_breaker.assert_not_called()
            assert service.stats["mcp_breaker_rejections"] == 1
            assert service.interface.mcp_available is False
            warn_calls = " ".join(str(call) for call in mock_logger.warning.call_args_list)
            assert "circuit breaker" in warn_calls.lower()

    @pytest.mark.asyncio
    async def test_check_mcp_server_uses_breaker_when_available(self):
        """Health probe executes via circuit breaker manager when configured"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.mcp_available = False
            circuit_manager = MagicMock()
            circuit_manager.get_breaker_state.return_value = CircuitState.CLOSED
            circuit_manager.call_with_breaker = AsyncMock(return_value=MagicMock(json=MagicMock(return_value={
                "status": "healthy",
                "tools_registered": [
                    "mcp_agent_to_agent_send_to_deepseek",
                    "mcp_agent_to_agent_send_to_perplexity",
                    "mcp_agent_to_agent_get_consensus"
                ]
            }), raise_for_status=MagicMock(return_value=None)))
            mock_interface.circuit_manager = circuit_manager
            mock_get.return_value = mock_interface

            service = AIAgentBackgroundService()

            await service._check_mcp_server()

            circuit_manager.call_with_breaker.assert_awaited()
            assert service.interface.mcp_available is True


# =============================================================================
# Category 6: DeepSeek Connection Tests (4 tests)
# =============================================================================

class TestDeepSeekConnectionTests:
    """Test DeepSeek connection health checks"""
    
    @pytest.mark.asyncio
    async def test_test_deepseek_connection_with_active_keys(self):
        """Test _test_deepseek_connection with active keys"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.key_manager.deepseek_keys = [
                create_api_key(value="key1", agent_type=AgentType.DEEPSEEK, index=0, is_active=True, error_count=0),
                create_api_key(value="key2", agent_type=AgentType.DEEPSEEK, index=1, is_active=True, error_count=0)
            ]
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            # Should not raise
            await service._test_deepseek_connection()
    
    @pytest.mark.asyncio
    async def test_test_deepseek_connection_with_no_active_keys(self):
        """Test _test_deepseek_connection with no active keys"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.key_manager.deepseek_keys = [
                create_api_key(value="key1", agent_type=AgentType.DEEPSEEK, index=0, is_active=False, error_count=5)
            ]
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            # Should not raise, just warn
            await service._test_deepseek_connection()
    
    @pytest.mark.asyncio
    async def test_test_deepseek_connection_full_with_success(self):
        """Test _test_deepseek_connection_full with successful response"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.send_request = AsyncMock(return_value=AgentResponse(
                success=True,
                content="OK",
                api_key_index=0,
                latency_ms=123.4,
                channel="direct"
            ))
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            # Should not raise
            await service._test_deepseek_connection_full()
    
    @pytest.mark.asyncio
    async def test_test_deepseek_connection_full_with_failure(self):
        """Test _test_deepseek_connection_full with failed response"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.send_request = AsyncMock(return_value=AgentResponse(
                success=False,
                content="",
                error="API timeout",
                channel="direct"
            ))
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            # Should not raise, just warn
            await service._test_deepseek_connection_full()


# =============================================================================
# Category 7: Perplexity Connection Tests (4 tests)
# =============================================================================

class TestPerplexityConnectionTests:
    """Test Perplexity connection health checks"""
    
    @pytest.mark.asyncio
    async def test_test_perplexity_connection_with_active_keys(self):
        """Test _test_perplexity_connection with active keys"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.key_manager.perplexity_keys = [
                create_api_key(value="key1", agent_type=AgentType.PERPLEXITY, index=0, is_active=True, error_count=0)
            ]
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            # Should not raise
            await service._test_perplexity_connection()
    
    @pytest.mark.asyncio
    async def test_test_perplexity_connection_with_no_active_keys(self):
        """Test _test_perplexity_connection with no active keys"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.key_manager.perplexity_keys = [
                create_api_key(value="key1", agent_type=AgentType.PERPLEXITY, index=0, is_active=False, error_count=5)
            ]
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            # Should not raise, just warn
            await service._test_perplexity_connection()
    
    @pytest.mark.asyncio
    async def test_test_perplexity_connection_full_with_success(self):
        """Test _test_perplexity_connection_full with successful response"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.send_request = AsyncMock(return_value=AgentResponse(
                success=True,
                content="4",
                api_key_index=0,
                latency_ms=234.5,
                channel="direct"
            ))
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            # Should not raise
            await service._test_perplexity_connection_full()
    
    @pytest.mark.asyncio
    async def test_test_perplexity_connection_full_with_failure(self):
        """Test _test_perplexity_connection_full with failed response"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.send_request = AsyncMock(return_value=AgentResponse(
                success=False,
                content="",
                error="Rate limit exceeded",
                channel="direct"
            ))
            mock_get.return_value = mock_interface
            
            service = AIAgentBackgroundService()
            
            # Should not raise, just warn
            await service._test_perplexity_connection_full()


# =============================================================================
# Category 8: Health Summary (2 tests)
# =============================================================================

class TestHealthSummary:
    """Test health summary printing"""
    
    @pytest.mark.asyncio
    async def test_print_health_summary_logs_uptime(self):
        """Test _print_health_summary logs uptime"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.get_stats.return_value = {
                "total_requests": 10,
                "mcp_success": 0,
                "mcp_failed": 0,
                "direct_api_success": 10,
                "direct_api_failed": 0
            }
            mock_get.return_value = mock_interface
            
            with patch('backend.agents.agent_background_service.logger') as mock_logger:
                service = AIAgentBackgroundService()
                service.start_time = time.time() - 3661  # 1h 1m 1s ago
                
                service._print_health_summary()
                
                info_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("Uptime:" in call and "1h" in call for call in info_calls)
    
    @pytest.mark.asyncio
    async def test_print_health_summary_logs_statistics(self):
        """Test _print_health_summary logs statistics"""
        with patch('backend.agents.agent_background_service.get_agent_interface') as mock_get:
            mock_interface = MagicMock()
            mock_interface.get_stats.return_value = {
                "total_requests": 42,
                "mcp_success": 5,
                "mcp_failed": 3,
                "direct_api_success": 30,
                "direct_api_failed": 4
            }
            mock_get.return_value = mock_interface
            
            with patch('backend.agents.agent_background_service.logger') as mock_logger:
                service = AIAgentBackgroundService()
                service.stats["api_key_rotations"] = 2
                
                service._print_health_summary()
                
                info_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("Total requests: 42" in call for call in info_calls)
                assert any("Direct API success: 30" in call for call in info_calls)
                assert any("Key rotations: 2" in call for call in info_calls)
