"""
Unit tests for Circuit Breaker Manager

Phase 1 Implementation - Week 1
Tests circuit breaker functionality for AI agent system.
"""

import asyncio
import pytest
from backend.agents.circuit_breaker_manager import (
    AgentCircuitBreakerManager,
    CircuitState,
    CircuitBreakerError,
    get_circuit_manager,
)


@pytest.fixture
def circuit_manager():
    """Fresh circuit breaker manager for each test"""
    return AgentCircuitBreakerManager()


@pytest.fixture
def registered_manager(circuit_manager):
    """Circuit manager with test breaker registered"""
    circuit_manager.register_breaker(
        name="test_service",
        fail_max=3,
        timeout_duration=1  # 1 second for fast tests
    )
    return circuit_manager


@pytest.mark.asyncio
async def test_register_breaker(circuit_manager):
    """Test circuit breaker registration"""
    circuit_manager.register_breaker(
        name="test_api",
        fail_max=5,
        timeout_duration=60
    )
    
    assert "test_api" in circuit_manager.get_all_breakers()
    state = circuit_manager.get_breaker_state("test_api")
    assert state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_successful_call(registered_manager):
    """Test successful function call through circuit breaker"""
    async def success_func():
        return "success"
    
    result = await registered_manager.call_with_breaker(
        "test_service",
        success_func
    )
    
    assert result == "success"
    
    # Check metrics
    metrics = registered_manager.get_metrics()
    assert metrics.breakers["test_service"].total_calls == 1
    assert metrics.breakers["test_service"].successful_calls == 1
    assert metrics.breakers["test_service"].failed_calls == 0


@pytest.mark.asyncio
async def test_circuit_opens_after_failures(registered_manager):
    """Test circuit breaker opens after fail_max failures"""
    async def failing_func():
        raise Exception("Simulated failure")
    
    # Make 3 failing calls (fail_max=3)
    for i in range(3):
        with pytest.raises(Exception):
            await registered_manager.call_with_breaker(
                "test_service",
                failing_func
            )
    
    # Circuit should now be OPEN
    state = registered_manager.get_breaker_state("test_service")
    assert state == CircuitState.OPEN
    
    # Check metrics
    metrics = registered_manager.get_metrics()
    config = metrics.breakers["test_service"]
    assert config.total_trips == 1
    assert config.failed_calls == 3
    assert config.last_trip_time is not None


@pytest.mark.asyncio
async def test_circuit_rejects_when_open(registered_manager):
    """Test circuit breaker rejects calls when open"""
    async def failing_func():
        raise Exception("Failure")
    
    # Trigger circuit to open (3 failures)
    for i in range(3):
        with pytest.raises(Exception):
            await registered_manager.call_with_breaker(
                "test_service",
                failing_func
            )
    
    # Next call should be rejected immediately
    with pytest.raises(CircuitBreakerError) as exc_info:
        await registered_manager.call_with_breaker(
            "test_service",
            failing_func
        )
    
    assert "Circuit breaker" in str(exc_info.value)
    assert "is open" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_circuit_recovery_half_open(registered_manager):
    """Test circuit breaker transitions to HALF_OPEN after timeout"""
    async def failing_func():
        raise Exception("Failure")
    
    async def success_func():
        return "recovered"
    
    # Open the circuit (3 failures)
    for i in range(3):
        with pytest.raises(Exception):
            await registered_manager.call_with_breaker(
                "test_service",
                failing_func
            )
    
    assert registered_manager.get_breaker_state("test_service") == CircuitState.OPEN
    
    # Wait for timeout (1 second)
    await asyncio.sleep(1.2)
    
    # Next call should transition to HALF_OPEN and succeed
    result = await registered_manager.call_with_breaker(
        "test_service",
        success_func
    )
    
    assert result == "recovered"
    
    # Circuit should be CLOSED after successful recovery
    state = registered_manager.get_breaker_state("test_service")
    assert state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_reopens_on_failure_in_half_open(registered_manager):
    """Test circuit reopens if call fails during HALF_OPEN"""
    async def failing_func():
        raise Exception("Still failing")
    
    # Open the circuit
    for i in range(3):
        with pytest.raises(Exception):
            await registered_manager.call_with_breaker(
                "test_service",
                failing_func
            )
    
    # Wait for timeout
    await asyncio.sleep(1.2)
    
    # Fail during HALF_OPEN
    with pytest.raises(Exception):
        await registered_manager.call_with_breaker(
            "test_service",
            failing_func
        )
    
    # Circuit should be OPEN again
    state = registered_manager.get_breaker_state("test_service")
    assert state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_manual_reset(registered_manager):
    """Test manual circuit breaker reset"""
    async def failing_func():
        raise Exception("Failure")
    
    # Open the circuit
    for i in range(3):
        with pytest.raises(Exception):
            await registered_manager.call_with_breaker(
                "test_service",
                failing_func
            )
    
    assert registered_manager.get_breaker_state("test_service") == CircuitState.OPEN
    
    # Manual reset
    success = registered_manager.reset_breaker("test_service")
    
    assert success is True
    assert registered_manager.get_breaker_state("test_service") == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_multiple_breakers(circuit_manager):
    """Test multiple independent circuit breakers"""
    circuit_manager.register_breaker("service_a", fail_max=2, timeout_duration=1)
    circuit_manager.register_breaker("service_b", fail_max=2, timeout_duration=1)
    
    async def failing_func():
        raise Exception("Failure")
    
    # Open service_a circuit
    for i in range(2):
        with pytest.raises(Exception):
            await circuit_manager.call_with_breaker("service_a", failing_func)
    
    # service_a should be OPEN, service_b should be CLOSED
    assert circuit_manager.get_breaker_state("service_a") == CircuitState.OPEN
    assert circuit_manager.get_breaker_state("service_b") == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_metrics_tracking(registered_manager):
    """Test metrics are tracked correctly"""
    async def success_func():
        return "ok"
    
    async def failing_func():
        raise Exception("fail")
    
    # 2 successes
    await registered_manager.call_with_breaker("test_service", success_func)
    await registered_manager.call_with_breaker("test_service", success_func)
    
    # 1 failure
    with pytest.raises(Exception):
        await registered_manager.call_with_breaker("test_service", failing_func)
    
    # Check metrics
    metrics = registered_manager.get_metrics()
    config = metrics.breakers["test_service"]
    
    assert config.total_calls == 3
    assert config.successful_calls == 2
    assert config.failed_calls == 1
    assert config.total_trips == 0  # Not opened yet


@pytest.mark.asyncio
async def test_get_metrics_dict(registered_manager):
    """Test metrics can be converted to dict"""
    async def success_func():
        return "ok"
    
    await registered_manager.call_with_breaker("test_service", success_func)
    
    metrics = registered_manager.get_metrics()
    metrics_dict = metrics.to_dict()
    
    assert "breakers" in metrics_dict
    assert "test_service" in metrics_dict["breakers"]
    assert "total_calls" in metrics_dict
    assert "total_failures" in metrics_dict
    assert "total_trips" in metrics_dict
    
    breaker_data = metrics_dict["breakers"]["test_service"]
    assert "state" in breaker_data
    assert "total_calls" in breaker_data
    assert breaker_data["state"] == "CLOSED"


@pytest.mark.asyncio
async def test_singleton_pattern():
    """Test global singleton returns same instance"""
    manager1 = get_circuit_manager()
    manager2 = get_circuit_manager()
    
    assert manager1 is manager2


@pytest.mark.asyncio
async def test_unknown_breaker_error(circuit_manager):
    """Test calling unknown breaker raises error"""
    async def func():
        return "ok"
    
    with pytest.raises(ValueError) as exc_info:
        await circuit_manager.call_with_breaker("nonexistent", func)
    
    assert "Unknown circuit breaker" in str(exc_info.value)


@pytest.mark.asyncio
async def test_concurrent_calls(registered_manager):
    """Test circuit breaker handles concurrent calls correctly"""
    call_count = 0
    
    async def counting_func():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Simulate async work
        return call_count
    
    # Make 10 concurrent calls
    tasks = [
        registered_manager.call_with_breaker("test_service", counting_func)
        for _ in range(10)
    ]
    
    results = await asyncio.gather(*tasks)
    
    assert len(results) == 10
    assert call_count == 10
    
    # Check metrics
    metrics = registered_manager.get_metrics()
    assert metrics.breakers["test_service"].total_calls == 10
    assert metrics.breakers["test_service"].successful_calls == 10
