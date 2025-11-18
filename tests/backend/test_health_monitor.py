"""
Unit tests for Health Monitor

Phase 1 Implementation - Week 1
Tests health monitoring and auto-recovery functionality.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from backend.agents.health_monitor import (
    HealthMonitor,
    HealthStatus,
    HealthCheckResult,
    RecoveryAction,
    RecoveryActionType,
    get_health_monitor,
)


@pytest.fixture
def health_monitor():
    """Fresh health monitor for each test"""
    return HealthMonitor()


@pytest.fixture
async def registered_monitor(health_monitor):
    """Health monitor with test component registered"""
    # Dummy health check that always returns HEALTHY
    async def check_healthy():
        return HealthCheckResult(
            component="test_component",
            status=HealthStatus.HEALTHY,
            message="Component is healthy"
        )
    
    # Dummy recovery function
    async def recover(action_type):
        pass
    
    health_monitor.register_health_check(
        "test_component",
        check_healthy,
        recover
    )
    
    return health_monitor


@pytest.mark.asyncio
async def test_register_health_check(health_monitor):
    """Test health check registration"""
    async def check_func():
        return HealthCheckResult(
            component="api",
            status=HealthStatus.HEALTHY,
            message="OK"
        )
    
    health_monitor.register_health_check("api", check_func)
    
    # Check initial status
    status = health_monitor.get_component_health("api")
    assert status is not None
    assert status.component == "api"
    assert status.status == HealthStatus.UNKNOWN


@pytest.mark.asyncio
async def test_check_component_health(registered_monitor):
    """Test health check execution"""
    result = await registered_monitor.check_component_health("test_component")
    
    assert result.component == "test_component"
    assert result.status == HealthStatus.HEALTHY
    assert result.message == "Component is healthy"
    assert result.checked_at is not None


@pytest.mark.asyncio
async def test_unhealthy_detection(health_monitor):
    """Test detecting unhealthy component"""
    async def check_unhealthy():
        return HealthCheckResult(
            component="failing_service",
            status=HealthStatus.UNHEALTHY,
            message="Service is down",
            recovery_suggested=RecoveryActionType.RESTART_SERVICE
        )
    
    health_monitor.register_health_check("failing_service", check_unhealthy)
    
    result = await health_monitor.check_component_health("failing_service")
    
    assert result.status == HealthStatus.UNHEALTHY
    assert result.recovery_suggested == RecoveryActionType.RESTART_SERVICE


@pytest.mark.asyncio
async def test_degraded_status(health_monitor):
    """Test detecting degraded component"""
    async def check_degraded():
        return HealthCheckResult(
            component="slow_service",
            status=HealthStatus.DEGRADED,
            message="High latency detected",
            details={"latency_ms": 500}
        )
    
    health_monitor.register_health_check("slow_service", check_degraded)
    
    result = await health_monitor.check_component_health("slow_service")
    
    assert result.status == HealthStatus.DEGRADED
    assert result.details["latency_ms"] == 500


@pytest.mark.asyncio
async def test_recovery_execution(health_monitor):
    """Test recovery action execution"""
    recovery_called = False
    
    async def check_unhealthy():
        return HealthCheckResult(
            component="broken_service",
            status=HealthStatus.UNHEALTHY,
            message="Service broken"
        )
    
    async def recover(action_type):
        nonlocal recovery_called
        recovery_called = True
    
    health_monitor.register_health_check(
        "broken_service",
        check_unhealthy,
        recover
    )
    
    # Execute recovery
    action = await health_monitor.execute_recovery(
        "broken_service",
        RecoveryActionType.RESTART_SERVICE
    )
    
    assert action.success is True
    assert recovery_called is True
    assert action.component == "broken_service"
    assert action.action_type == RecoveryActionType.RESTART_SERVICE


@pytest.mark.asyncio
async def test_recovery_failure(health_monitor):
    """Test recovery action failure handling"""
    async def check_unhealthy():
        return HealthCheckResult(
            component="broken_service",
            status=HealthStatus.UNHEALTHY,
            message="Service broken"
        )
    
    async def failing_recovery(action_type):
        raise Exception("Recovery failed")
    
    health_monitor.register_health_check(
        "broken_service",
        check_unhealthy,
        failing_recovery
    )
    
    action = await health_monitor.execute_recovery(
        "broken_service",
        RecoveryActionType.RESTART_SERVICE
    )
    
    assert action.success is False
    assert action.error is not None
    assert "Recovery failed" in action.error


@pytest.mark.asyncio
async def test_recovery_history(health_monitor):
    """Test recovery history tracking"""
    async def check_func():
        return HealthCheckResult("service", HealthStatus.HEALTHY, "OK")
    
    async def recover(action_type):
        pass
    
    health_monitor.register_health_check("service", check_func, recover)
    
    # Execute 3 recoveries
    for i in range(3):
        await health_monitor.execute_recovery(
            "service",
            RecoveryActionType.RESET_ERRORS
        )
    
    # Check history
    history = health_monitor.get_recovery_history(limit=10)
    assert len(history) == 3
    assert all(r.component == "service" for r in history)


@pytest.mark.asyncio
async def test_get_all_health(health_monitor):
    """Test getting health status for all components"""
    async def check1():
        return HealthCheckResult("service1", HealthStatus.HEALTHY, "OK")
    
    async def check2():
        return HealthCheckResult("service2", HealthStatus.DEGRADED, "Slow")
    
    health_monitor.register_health_check("service1", check1)
    health_monitor.register_health_check("service2", check2)
    
    # Execute checks
    await health_monitor.check_component_health("service1")
    await health_monitor.check_component_health("service2")
    
    # Get all health
    all_health = health_monitor.get_all_health()
    
    assert len(all_health) == 2
    assert all_health["service1"].status == HealthStatus.HEALTHY
    assert all_health["service2"].status == HealthStatus.DEGRADED


@pytest.mark.asyncio
async def test_monitoring_loop(health_monitor):
    """Test background monitoring loop"""
    check_count = 0
    
    async def check_func():
        nonlocal check_count
        check_count += 1
        return HealthCheckResult("service", HealthStatus.HEALTHY, "OK")
    
    health_monitor.register_health_check("service", check_func)
    
    # Start monitoring with short interval
    await health_monitor.start_monitoring(interval_seconds=0.1)
    
    # Wait for a few checks
    await asyncio.sleep(0.35)
    
    # Stop monitoring
    await health_monitor.stop_monitoring()
    
    # Should have run 3-4 checks (0.35s / 0.1s)
    assert check_count >= 3


@pytest.mark.asyncio
async def test_auto_recovery_trigger(health_monitor):
    """Test automatic recovery is triggered for unhealthy components"""
    recovery_count = 0
    
    async def check_unhealthy():
        return HealthCheckResult(
            component="failing",
            status=HealthStatus.UNHEALTHY,
            message="Down",
            recovery_suggested=RecoveryActionType.RESET_ERRORS
        )
    
    async def recover(action_type):
        nonlocal recovery_count
        recovery_count += 1
    
    health_monitor.register_health_check("failing", check_unhealthy, recover)
    
    # Start monitoring
    await health_monitor.start_monitoring(interval_seconds=0.1)
    
    # Wait for auto-recovery to trigger
    await asyncio.sleep(0.35)
    
    # Stop monitoring
    await health_monitor.stop_monitoring()
    
    # Recovery should have been triggered at least once
    assert recovery_count >= 1


@pytest.mark.asyncio
async def test_metrics_calculation(health_monitor):
    """Test health metrics calculation"""
    async def check1():
        return HealthCheckResult("healthy1", HealthStatus.HEALTHY, "OK")
    
    async def check2():
        return HealthCheckResult("healthy2", HealthStatus.HEALTHY, "OK")
    
    async def check3():
        return HealthCheckResult("degraded", HealthStatus.DEGRADED, "Slow")
    
    async def check4():
        return HealthCheckResult("unhealthy", HealthStatus.UNHEALTHY, "Down")
    
    async def recover(action_type):
        pass
    
    # Register components
    health_monitor.register_health_check("healthy1", check1)
    health_monitor.register_health_check("healthy2", check2)
    health_monitor.register_health_check("degraded", check3, recover)
    health_monitor.register_health_check("unhealthy", check4, recover)
    
    # Run checks
    await health_monitor.check_component_health("healthy1")
    await health_monitor.check_component_health("healthy2")
    await health_monitor.check_component_health("degraded")
    await health_monitor.check_component_health("unhealthy")
    
    # Get metrics
    metrics = health_monitor.get_metrics()
    
    assert metrics["total_components"] == 4
    assert metrics["healthy_components"] == 2
    assert metrics["degraded_components"] == 1
    assert metrics["unhealthy_components"] == 1


@pytest.mark.asyncio
async def test_recovery_success_rate(health_monitor):
    """Test recovery success rate calculation"""
    success_count = 0
    
    async def check_func():
        return HealthCheckResult("service", HealthStatus.HEALTHY, "OK")
    
    async def recover_success(action_type):
        nonlocal success_count
        success_count += 1
    
    async def recover_fail(action_type):
        raise Exception("Failed")
    
    health_monitor.register_health_check("success", check_func, recover_success)
    health_monitor.register_health_check("fail", check_func, recover_fail)
    
    # 3 successful recoveries
    for _ in range(3):
        await health_monitor.execute_recovery("success", RecoveryActionType.RESET_ERRORS)
    
    # 1 failed recovery
    await health_monitor.execute_recovery("fail", RecoveryActionType.RESET_ERRORS)
    
    # Check metrics
    metrics = health_monitor.get_metrics()
    
    assert metrics["total_recovery_attempts"] == 4
    assert metrics["successful_recoveries"] == 3
    assert metrics["recovery_success_rate"] == 75.0


@pytest.mark.asyncio
async def test_singleton_pattern():
    """Test global singleton returns same instance"""
    monitor1 = get_health_monitor()
    monitor2 = get_health_monitor()
    
    assert monitor1 is monitor2


@pytest.mark.asyncio
async def test_health_check_exception_handling(health_monitor):
    """Test health check exceptions are caught and logged"""
    async def broken_check():
        raise Exception("Check failed")
    
    health_monitor.register_health_check("broken", broken_check)
    
    # Should not raise, but return UNHEALTHY result
    result = await health_monitor.check_component_health("broken")
    
    assert result.status == HealthStatus.UNHEALTHY
    assert "Check failed" in result.message


@pytest.mark.asyncio
async def test_concurrent_health_checks(health_monitor):
    """Test concurrent health checks work correctly"""
    check_count = 0
    
    async def check_func():
        nonlocal check_count
        check_count += 1
        await asyncio.sleep(0.01)  # Simulate async work
        return HealthCheckResult(
            f"service_{check_count}",
            HealthStatus.HEALTHY,
            "OK"
        )
    
    # Register 5 services
    for i in range(5):
        health_monitor.register_health_check(f"service_{i}", check_func)
    
    # Run checks concurrently
    tasks = [
        health_monitor.check_component_health(f"service_{i}")
        for i in range(5)
    ]
    
    results = await asyncio.gather(*tasks)
    
    assert len(results) == 5
    assert check_count == 5


@pytest.mark.asyncio
async def test_no_recovery_registered(health_monitor):
    """Test recovery without registered recovery function"""
    async def check_func():
        return HealthCheckResult("service", HealthStatus.HEALTHY, "OK")
    
    # Register without recovery function
    health_monitor.register_health_check("service", check_func)
    
    # Try to execute recovery
    action = await health_monitor.execute_recovery(
        "service",
        RecoveryActionType.RESET_ERRORS
    )
    
    assert action.success is False
    assert "No recovery action registered" in action.error
