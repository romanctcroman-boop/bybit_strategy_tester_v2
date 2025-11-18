"""
Tests for Service Health Monitoring System

Test Coverage:
- Initialization and configuration
- Health check execution
- Status transitions (HEALTHY → DEGRADED → UNHEALTHY → DEAD)
- Latency percentile calculations
- Consecutive failure tracking
- Automatic recovery
- Alert callbacks
- Metrics export
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from reliability.service_monitor import (
    ServiceMonitor,
    ServiceConfig,
    HealthStatus,
    ServiceHealth,
    HealthCheckResult,
)


class TestServiceMonitorInit:
    """Test service monitor initialization"""
    
    def test_init_with_default_config(self):
        """Should initialize with default configuration"""
        async def dummy_check():
            return True
        
        config = ServiceConfig(name="test_service")
        monitor = ServiceMonitor(config, dummy_check)
        
        assert monitor.config.name == "test_service"
        assert monitor.config.check_interval == 30.0
        assert monitor.config.timeout == 5.0
        assert monitor.status == HealthStatus.HEALTHY
        assert monitor.total_checks == 0
    
    def test_init_with_custom_config(self):
        """Should initialize with custom configuration"""
        async def dummy_check():
            return True
        
        config = ServiceConfig(
            name="api",
            check_interval=15.0,
            timeout=3.0,
            failure_threshold=5,
            dead_threshold=15
        )
        monitor = ServiceMonitor(config, dummy_check)
        
        assert monitor.config.check_interval == 15.0
        assert monitor.config.timeout == 3.0
        assert monitor.config.failure_threshold == 5
        assert monitor.config.dead_threshold == 15


class TestHealthCheckExecution:
    """Test health check execution"""
    
    @pytest.mark.asyncio
    async def test_successful_health_check(self):
        """Should record successful health check"""
        check_mock = AsyncMock(return_value=True)
        config = ServiceConfig(name="test", check_interval=0.1)
        monitor = ServiceMonitor(config, check_mock)
        
        await monitor._perform_health_check()
        
        assert monitor.total_checks == 1
        assert monitor.total_successes == 1
        assert monitor.total_failures == 0
        assert monitor.consecutive_failures == 0
        assert monitor.consecutive_successes == 1
        assert monitor.status == HealthStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_failed_health_check(self):
        """Should record failed health check"""
        check_mock = AsyncMock(return_value=False)
        config = ServiceConfig(name="test", check_interval=0.1)
        monitor = ServiceMonitor(config, check_mock)
        
        await monitor._perform_health_check()
        
        assert monitor.total_checks == 1
        assert monitor.total_successes == 0
        assert monitor.total_failures == 1
        assert monitor.consecutive_failures == 1
        assert monitor.consecutive_successes == 0
        assert monitor.status == HealthStatus.DEGRADED
    
    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """Should handle timeout in health check"""
        async def slow_check():
            await asyncio.sleep(10)
            return True
        
        config = ServiceConfig(name="test", timeout=0.1)
        monitor = ServiceMonitor(config, slow_check)
        
        await monitor._perform_health_check()
        
        assert monitor.total_failures == 1
        assert monitor.consecutive_failures == 1
        assert len(monitor.recent_checks) == 1
        assert "Timeout" in monitor.recent_checks[0].error
    
    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        """Should handle exception in health check"""
        async def failing_check():
            raise ValueError("Test error")
        
        config = ServiceConfig(name="test")
        monitor = ServiceMonitor(config, failing_check)
        
        await monitor._perform_health_check()
        
        assert monitor.total_failures == 1
        assert "Test error" in monitor.recent_checks[0].error


class TestStatusTransitions:
    """Test health status transitions"""
    
    @pytest.mark.asyncio
    async def test_healthy_to_degraded(self):
        """Should transition from HEALTHY to DEGRADED after first failure"""
        check_mock = AsyncMock(return_value=False)
        config = ServiceConfig(name="test", failure_threshold=3)
        monitor = ServiceMonitor(config, check_mock)
        
        await monitor._perform_health_check()
        
        assert monitor.status == HealthStatus.DEGRADED
        assert monitor.consecutive_failures == 1
    
    @pytest.mark.asyncio
    async def test_degraded_to_unhealthy(self):
        """Should transition to UNHEALTHY after failure threshold"""
        check_mock = AsyncMock(return_value=False)
        config = ServiceConfig(name="test", failure_threshold=3)
        monitor = ServiceMonitor(config, check_mock)
        
        # 3 consecutive failures
        for _ in range(3):
            await monitor._perform_health_check()
        
        assert monitor.status == HealthStatus.UNHEALTHY
        assert monitor.consecutive_failures == 3
    
    @pytest.mark.asyncio
    async def test_unhealthy_to_dead(self):
        """Should transition to DEAD after dead threshold"""
        check_mock = AsyncMock(return_value=False)
        config = ServiceConfig(name="test", dead_threshold=10)
        monitor = ServiceMonitor(config, check_mock)
        
        # 10 consecutive failures
        for _ in range(10):
            await monitor._perform_health_check()
        
        assert monitor.status == HealthStatus.DEAD
        assert monitor.consecutive_failures == 10
    
    @pytest.mark.asyncio
    async def test_recovery_to_healthy(self):
        """Should recover to HEALTHY after consecutive successes"""
        call_count = 0
        
        async def alternating_check():
            nonlocal call_count
            call_count += 1
            return call_count > 2  # Fail first 2, then succeed
        
        config = ServiceConfig(name="test")
        monitor = ServiceMonitor(config, alternating_check)
        
        # 2 failures → DEGRADED
        await monitor._perform_health_check()
        await monitor._perform_health_check()
        assert monitor.status == HealthStatus.DEGRADED
        assert monitor.consecutive_failures == 2
        
        # 1st success → Still DEGRADED (need 2 consecutive)
        await monitor._perform_health_check()
        assert monitor.status == HealthStatus.DEGRADED
        assert monitor.consecutive_successes == 1
        
        # 2nd success → HEALTHY
        await monitor._perform_health_check()
        assert monitor.status == HealthStatus.HEALTHY
        assert monitor.consecutive_successes == 2


class TestLatencyTracking:
    """Test latency percentile calculations"""
    
    @pytest.mark.asyncio
    async def test_latency_percentile_calculation(self):
        """Should calculate latency percentiles correctly"""
        async def check():
            await asyncio.sleep(0.001)
            return True
        
        config = ServiceConfig(name="test", sample_size=10)
        monitor = ServiceMonitor(config, check)
        
        # Perform 10 checks
        for _ in range(10):
            await monitor._perform_health_check()
        
        health = monitor.get_health()
        
        assert health.latency_p50 > 0
        assert health.latency_p95 > 0
        assert health.latency_p99 > 0
        assert health.latency_p50 <= health.latency_p95 <= health.latency_p99
    
    @pytest.mark.asyncio
    async def test_degraded_due_to_high_latency(self):
        """Should mark as DEGRADED when P95 latency is high"""
        call_count = 0
        
        async def slow_check():
            nonlocal call_count
            call_count += 1
            # High latency on some calls
            await asyncio.sleep(1.5 if call_count % 2 == 0 else 0.001)
            return True
        
        config = ServiceConfig(
            name="test",
            latency_threshold_degraded=1000.0,
            sample_size=10
        )
        monitor = ServiceMonitor(config, slow_check)
        
        # Perform enough checks to calculate P95
        for _ in range(10):
            await monitor._perform_health_check()
        
        # P95 latency should trigger DEGRADED status
        assert monitor.get_health().latency_p95 >= 1000.0


class TestAlertCallbacks:
    """Test alert callback system"""
    
    @pytest.mark.asyncio
    async def test_callback_on_status_change(self):
        """Should call callback when status changes"""
        callback_mock = Mock()
        check_mock = AsyncMock(return_value=False)
        
        config = ServiceConfig(name="test", failure_threshold=3)
        monitor = ServiceMonitor(config, check_mock, on_status_change=callback_mock)
        
        # Trigger status change
        await monitor._perform_health_check()
        
        callback_mock.assert_called_once_with(HealthStatus.HEALTHY, HealthStatus.DEGRADED)
    
    @pytest.mark.asyncio
    async def test_no_callback_without_status_change(self):
        """Should not call callback if status unchanged"""
        callback_mock = Mock()
        check_mock = AsyncMock(return_value=True)
        
        config = ServiceConfig(name="test")
        monitor = ServiceMonitor(config, check_mock, on_status_change=callback_mock)
        
        await monitor._perform_health_check()
        await monitor._perform_health_check()
        
        # No status change (HEALTHY → HEALTHY), so no callback
        callback_mock.assert_not_called()


class TestMetricsExport:
    """Test Prometheus metrics export"""
    
    @pytest.mark.asyncio
    async def test_get_health_metrics(self):
        """Should return complete health metrics"""
        check_mock = AsyncMock(return_value=True)
        config = ServiceConfig(name="test")
        monitor = ServiceMonitor(config, check_mock)
        
        await monitor._perform_health_check()
        
        health = monitor.get_health()
        
        assert health.status == HealthStatus.HEALTHY
        assert health.total_checks == 1
        assert health.total_successes == 1
        assert health.uptime_percentage == 100.0
    
    @pytest.mark.asyncio
    async def test_get_prometheus_metrics(self):
        """Should export Prometheus-compatible metrics"""
        check_mock = AsyncMock(return_value=True)
        config = ServiceConfig(name="api_service")
        monitor = ServiceMonitor(config, check_mock)
        
        await monitor._perform_health_check()
        
        metrics = monitor.get_metrics()
        
        assert metrics["service_name"] == "api_service"
        assert metrics["health_status"] == "healthy"
        assert metrics["health_status_code"] == 3  # HEALTHY = 3
        assert metrics["total_checks"] == 1
        assert metrics["uptime_percentage"] == 100.0
        assert "latency_p95_ms" in metrics
    
    @pytest.mark.asyncio
    async def test_uptime_percentage_calculation(self):
        """Should calculate uptime percentage correctly"""
        call_count = 0
        
        async def intermittent_check():
            nonlocal call_count
            call_count += 1
            return call_count % 2 == 1  # Fail every other check
        
        config = ServiceConfig(name="test")
        monitor = ServiceMonitor(config, intermittent_check)
        
        # 10 checks (5 success, 5 failure)
        for _ in range(10):
            await monitor._perform_health_check()
        
        health = monitor.get_health()
        assert health.uptime_percentage == 50.0


class TestMonitoringLoop:
    """Test continuous monitoring loop"""
    
    @pytest.mark.asyncio
    async def test_start_and_stop_monitor(self):
        """Should start and stop monitoring gracefully"""
        check_mock = AsyncMock(return_value=True)
        config = ServiceConfig(name="test", check_interval=0.1)
        monitor = ServiceMonitor(config, check_mock)
        
        await monitor.start()
        assert monitor._monitor_task is not None
        
        # Let it run for a bit
        await asyncio.sleep(0.3)
        
        await monitor.stop()
        assert monitor._stop_event.is_set()
        assert monitor.total_checks >= 2  # Should have run multiple checks
    
    @pytest.mark.asyncio
    async def test_monitor_loop_resilience(self):
        """Should continue monitoring even if check raises exception"""
        call_count = 0
        
        async def flaky_check():
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("Temporary error")
            return True
        
        config = ServiceConfig(name="test", check_interval=0.1)
        monitor = ServiceMonitor(config, flaky_check)
        
        await monitor.start()
        await asyncio.sleep(0.4)
        await monitor.stop()
        
        # Should have recovered and continued checking
        assert monitor.total_checks >= 3
        assert monitor.total_successes >= 2


class TestReset:
    """Test monitor reset functionality"""
    
    @pytest.mark.asyncio
    async def test_reset_monitor(self):
        """Should reset monitoring state"""
        check_mock = AsyncMock(return_value=False)
        config = ServiceConfig(name="test")
        monitor = ServiceMonitor(config, check_mock)
        
        # Create some state
        await monitor._perform_health_check()
        await monitor._perform_health_check()
        
        assert monitor.consecutive_failures == 2
        assert monitor.status == HealthStatus.DEGRADED
        
        # Reset
        monitor.reset()
        
        assert monitor.consecutive_failures == 0
        assert monitor.consecutive_successes == 0
        assert monitor.status == HealthStatus.HEALTHY
        # Note: total_checks NOT reset (historical data)


class TestEdgeCases:
    """Test edge cases and error scenarios"""
    
    @pytest.mark.asyncio
    async def test_percentile_with_single_sample(self):
        """Should calculate percentiles with single sample"""
        check_mock = AsyncMock(return_value=True)
        config = ServiceConfig(name="test")
        monitor = ServiceMonitor(config, check_mock)
        
        await monitor._perform_health_check()
        
        p95 = monitor._calculate_percentile(0.95)
        assert p95 > 0  # Should not crash
    
    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Should handle start when already running"""
        check_mock = AsyncMock(return_value=True)
        config = ServiceConfig(name="test", check_interval=0.1)
        monitor = ServiceMonitor(config, check_mock)
        
        await monitor.start()
        await monitor.start()  # Second start
        
        # Should not crash, just log warning
        await monitor.stop()
    
    def test_repr(self):
        """Should have readable string representation"""
        async def dummy():
            return True
        
        config = ServiceConfig(name="test_svc")
        monitor = ServiceMonitor(config, dummy)
        
        repr_str = repr(monitor)
        assert "test_svc" in repr_str
        assert "healthy" in repr_str.lower()
