"""
Tests for MCP Server Manager

Test Coverage:
- Initialization and configuration
- Process start/stop lifecycle
- Health monitoring and auto-restart
- Restart rate limiting
- Exponential backoff
- Graceful shutdown
- PID file management
- Resource monitoring (CPU, memory)
- Alert callbacks
- Error handling

Note: Tests use mock processes to avoid spawning real subprocesses
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from pathlib import Path
from reliability.mcp_manager import (
    MCPServerManager,
    ServerConfig,
    ProcessState,
)


@pytest.fixture
def basic_config():
    """Basic server configuration for tests"""
    return ServerConfig(
        name="test-server",
        command=["python", "-m", "test_module"],
        max_restarts_per_hour=10,
        health_check_interval=1.0,
        restart_delay=0.1,
        max_restart_delay=1.0,
    )


class TestManagerInit:
    """Test manager initialization"""
    
    def test_init_with_basic_config(self, basic_config):
        """Should initialize with basic configuration"""
        manager = MCPServerManager(basic_config)
        
        assert manager.config.name == "test-server"
        assert manager.state == ProcessState.STOPPED
        assert manager.pid is None
        assert manager.total_restarts == 0
        assert manager.total_failures == 0
    
    def test_init_with_custom_config(self):
        """Should initialize with custom configuration"""
        config = ServerConfig(
            name="custom-server",
            command=["node", "server.js"],
            working_dir="/tmp",
            max_restarts_per_hour=5,
            health_check_interval=60.0,
            restart_delay=10.0,
            pid_file="/tmp/server.pid",
        )
        
        manager = MCPServerManager(config)
        
        assert manager.config.name == "custom-server"
        assert manager.config.max_restarts_per_hour == 5
        assert manager.config.pid_file == "/tmp/server.pid"


class TestProcessLifecycle:
    """Test process start/stop lifecycle"""
    
    @pytest.mark.asyncio
    async def test_start_server(self, basic_config):
        """Should start server successfully"""
        manager = MCPServerManager(basic_config)
        
        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.pid = 12345
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await manager.start()
        
        assert result is True
        assert manager.state == ProcessState.RUNNING
        assert manager.pid == 12345
        assert manager.start_time is not None
    
    @pytest.mark.asyncio
    async def test_start_already_running(self, basic_config):
        """Should not start if already running"""
        manager = MCPServerManager(basic_config)
        manager.state = ProcessState.RUNNING
        
        result = await manager.start()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_stop_server(self, basic_config):
        """Should stop server gracefully"""
        manager = MCPServerManager(basic_config)
        
        # Mock running process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.wait = AsyncMock()
        mock_process.terminate = Mock()  # Sync method
        
        manager.process = mock_process
        manager.pid = 12345
        manager.state = ProcessState.RUNNING
        
        result = await manager.stop(timeout=1.0)
        
        assert result is True
        assert manager.state == ProcessState.STOPPED
        assert manager.pid is None
        mock_process.terminate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_with_force_kill(self, basic_config):
        """Should force kill if graceful shutdown times out"""
        manager = MCPServerManager(basic_config)
        
        # Mock process that doesn't respond to terminate
        mock_process = Mock()
        mock_process.pid = 12345
        # First wait() times out, second wait() (after kill) succeeds
        mock_process.wait = AsyncMock(side_effect=[asyncio.TimeoutError(), None])
        mock_process.terminate = Mock()  # Sync method
        mock_process.kill = Mock()  # Sync method
        
        manager.process = mock_process
        manager.pid = 12345
        manager.state = ProcessState.RUNNING
        
        result = await manager.stop(timeout=0.1)
        
        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_already_stopped(self, basic_config):
        """Should handle stop when already stopped"""
        manager = MCPServerManager(basic_config)
        
        result = await manager.stop()
        
        assert result is True


class TestRestartLogic:
    """Test restart logic and rate limiting"""
    
    @pytest.mark.asyncio
    async def test_restart_successful(self, basic_config):
        """Should restart server successfully"""
        manager = MCPServerManager(basic_config)
        
        # Mock process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.wait = AsyncMock()
        mock_process.terminate = Mock()
        
        manager.process = mock_process
        manager.pid = 12345
        manager.state = ProcessState.RUNNING
        manager.start_time = time.time()
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await manager.restart()
        
        assert result is True
        assert manager.total_restarts == 1
        assert len(manager.restart_history) == 1
    
    @pytest.mark.asyncio
    async def test_restart_rate_limiting(self, basic_config):
        """Should enforce restart rate limit"""
        basic_config.max_restarts_per_hour = 3
        manager = MCPServerManager(basic_config)
        
        # Fill restart history
        current_time = time.time()
        manager.restart_history = [
            current_time - 10,
            current_time - 20,
            current_time - 30,
        ]
        
        result = await manager.restart()
        
        assert result is False  # Rate limit exceeded
    
    def test_can_restart_with_old_history(self, basic_config):
        """Should allow restart if old restarts are expired"""
        manager = MCPServerManager(basic_config)
        
        # Add old restarts (more than 1 hour ago)
        old_time = time.time() - 7200  # 2 hours ago
        manager.restart_history = [old_time, old_time + 10, old_time + 20]
        
        assert manager._can_restart() is True
        assert len(manager.restart_history) == 0  # Old entries cleaned
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self, basic_config):
        """Should apply exponential backoff on restarts"""
        manager = MCPServerManager(basic_config)
        
        # Mock process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.wait = AsyncMock()
        mock_process.terminate = Mock()
        
        manager.process = mock_process
        manager.pid = 12345
        manager.state = ProcessState.RUNNING
        manager.start_time = time.time()
        
        initial_delay = manager.current_restart_delay
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await manager.restart()
        
        # Delay should double
        assert manager.current_restart_delay == initial_delay * 2
    
    @pytest.mark.asyncio
    async def test_backoff_cap(self, basic_config):
        """Should cap exponential backoff at max_restart_delay"""
        manager = MCPServerManager(basic_config)
        manager.current_restart_delay = basic_config.max_restart_delay
        
        # Mock process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.wait = AsyncMock()
        mock_process.terminate = Mock()
        
        manager.process = mock_process
        manager.pid = 12345
        manager.state = ProcessState.RUNNING
        manager.start_time = time.time()
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await manager.restart()
        
        # Should not exceed max
        assert manager.current_restart_delay == basic_config.max_restart_delay


class TestHealthMonitoring:
    """Test health monitoring"""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, basic_config):
        """Should pass health check for running process"""
        manager = MCPServerManager(basic_config)
        manager.pid = 12345
        manager.process = AsyncMock()
        
        # Mock psutil Process
        mock_psutil_process = Mock()
        mock_psutil_process.is_running.return_value = True
        mock_psutil_process.status.return_value = "running"
        
        with patch('psutil.Process', return_value=mock_psutil_process):
            is_healthy = await manager._check_health()
        
        assert is_healthy is True
        assert manager.last_health_check is not None
    
    @pytest.mark.asyncio
    async def test_health_check_no_process(self, basic_config):
        """Should fail health check if no process"""
        manager = MCPServerManager(basic_config)
        
        is_healthy = await manager._check_health()
        
        assert is_healthy is False
    
    @pytest.mark.asyncio
    async def test_health_check_zombie_process(self, basic_config):
        """Should fail health check for zombie process"""
        manager = MCPServerManager(basic_config)
        manager.pid = 12345
        manager.process = AsyncMock()
        
        # Mock zombie process
        mock_psutil_process = Mock()
        mock_psutil_process.is_running.return_value = True
        mock_psutil_process.status.return_value = "zombie"
        
        with patch('psutil.Process', return_value=mock_psutil_process):
            is_healthy = await manager._check_health()
        
        assert is_healthy is False


class TestPIDFile:
    """Test PID file management"""
    
    def test_write_pid_file(self, basic_config, tmp_path):
        """Should write PID to file"""
        pid_file = tmp_path / "server.pid"
        basic_config.pid_file = str(pid_file)
        
        manager = MCPServerManager(basic_config)
        manager.pid = 12345
        
        manager._write_pid_file()
        
        assert pid_file.exists()
        assert pid_file.read_text() == "12345"
    
    def test_remove_pid_file(self, basic_config, tmp_path):
        """Should remove PID file"""
        pid_file = tmp_path / "server.pid"
        pid_file.write_text("12345")
        basic_config.pid_file = str(pid_file)
        
        manager = MCPServerManager(basic_config)
        
        manager._remove_pid_file()
        
        assert not pid_file.exists()


class TestAlertCallbacks:
    """Test alert callbacks"""
    
    @pytest.mark.asyncio
    async def test_alert_on_start(self, basic_config):
        """Should call alert callback on start"""
        alert_calls = []
        
        def alert_callback(event, data):
            alert_calls.append((event, data))
        
        basic_config.alert_callback = alert_callback
        manager = MCPServerManager(basic_config)
        
        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.pid = 12345
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await manager.start()
        
        assert len(alert_calls) == 1
        assert alert_calls[0][0] == "server_started"
        assert alert_calls[0][1]["pid"] == 12345
    
    @pytest.mark.asyncio
    async def test_alert_on_stop(self, basic_config):
        """Should call alert callback on stop"""
        alert_calls = []
        
        def alert_callback(event, data):
            alert_calls.append((event, data))
        
        basic_config.alert_callback = alert_callback
        manager = MCPServerManager(basic_config)
        
        # Mock running process
        mock_process = Mock()
        mock_process.wait = AsyncMock()
        mock_process.terminate = Mock()
        manager.process = mock_process
        manager.pid = 12345
        manager.state = ProcessState.RUNNING
        
        await manager.stop()
        
        # Should have stop alert
        assert any(event == "server_stopped" for event, _ in alert_calls)
    
    @pytest.mark.asyncio
    async def test_alert_on_rate_limit(self, basic_config):
        """Should call alert on restart rate limit"""
        alert_calls = []
        
        def alert_callback(event, data):
            alert_calls.append((event, data))
        
        basic_config.alert_callback = alert_callback
        basic_config.max_restarts_per_hour = 1
        manager = MCPServerManager(basic_config)
        
        # Fill restart history
        manager.restart_history = [time.time()]
        
        await manager.restart()
        
        # Should have rate limit alert
        assert any(
            event == "restart_rate_limit_exceeded" 
            for event, _ in alert_calls
        )


class TestHealthMetrics:
    """Test health metrics export"""
    
    def test_get_health_metrics(self, basic_config):
        """Should return comprehensive health metrics"""
        manager = MCPServerManager(basic_config)
        manager.pid = 12345
        manager.state = ProcessState.RUNNING
        manager.start_time = time.time() - 100  # 100s uptime
        manager.total_restarts = 5
        manager.total_failures = 2
        
        # Mock psutil
        mock_psutil_process = Mock()
        mock_psutil_process.cpu_percent.return_value = 15.5
        mock_psutil_process.memory_info.return_value = Mock(rss=50 * 1024 * 1024)  # 50 MB
        
        with patch('psutil.Process', return_value=mock_psutil_process):
            health = manager.get_health()
        
        assert health["name"] == "test-server"
        assert health["state"] == "running"
        assert health["pid"] == 12345
        assert health["uptime"] >= 100
        assert health["restarts"]["total"] == 5
        assert health["failures"]["total"] == 2
        assert health["resources"]["cpu_percent"] == 15.5
        assert health["resources"]["memory_mb"] == 50.0
    
    def test_get_health_stopped(self, basic_config):
        """Should return metrics for stopped server"""
        manager = MCPServerManager(basic_config)
        
        health = manager.get_health()
        
        assert health["state"] == "stopped"
        assert health["pid"] is None
        assert health["uptime"] == 0.0


class TestRepr:
    """Test string representation"""
    
    def test_repr(self, basic_config):
        """Should have readable string representation"""
        manager = MCPServerManager(basic_config)
        manager.pid = 12345
        manager.state = ProcessState.RUNNING
        manager.start_time = time.time()
        
        repr_str = repr(manager)
        
        assert "MCPServerManager" in repr_str
        assert "test-server" in repr_str
        assert "running" in repr_str
        assert "12345" in repr_str
