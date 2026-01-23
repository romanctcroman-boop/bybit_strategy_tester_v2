"""
Tests for backend/agents/circuit_breaker_manager.py

Tests cover:
1. CircuitBreakerManager registration and state management
2. get_breaker_metrics() method
3. call_with_breaker() functionality
4. Adaptive thresholds
5. Integration with FallbackService
"""

import pytest

from backend.agents.circuit_breaker_manager import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerManager,
    CircuitState,
    get_circuit_manager,
)


class TestCircuitBreakerManager:
    """Tests for CircuitBreakerManager class"""

    @pytest.fixture
    def manager(self):
        """Create a fresh CircuitBreakerManager instance"""
        return CircuitBreakerManager()

    def test_init_creates_default_breakers(self, manager):
        """Test that manager initializes with default breakers"""
        # Should have some breakers registered by default
        assert manager.breakers is not None
        assert isinstance(manager.breakers, dict)

    def test_register_breaker(self, manager):
        """Test registering a new circuit breaker"""
        manager.register_breaker(
            name="test_service",
            fail_max=5,
            timeout_duration=60,
            expected_exception=Exception,
        )

        assert "test_service" in manager.breakers

    def test_get_breaker_existing(self, manager):
        """Test getting an existing breaker"""
        manager.register_breaker(name="existing_service", fail_max=3)

        breaker = manager.get_breaker("existing_service")

        assert breaker is not None
        assert isinstance(breaker, CircuitBreaker)

    def test_get_breaker_auto_create(self, manager):
        """Test that get_breaker creates breaker if not exists"""
        breaker = manager.get_breaker("new_service")

        assert breaker is not None
        assert "new_service" in manager.breakers

    def test_get_breaker_state(self, manager):
        """Test getting circuit breaker state"""
        manager.register_breaker(name="state_test", fail_max=5)

        state = manager.get_breaker_state("state_test")

        assert state == CircuitState.CLOSED

    def test_get_breaker_state_nonexistent(self, manager):
        """Test getting state for non-existent breaker"""
        state = manager.get_breaker_state("nonexistent_breaker")

        assert state is None

    def test_reset_all_breakers(self, manager):
        """Test resetting all circuit breakers"""
        manager.register_breaker(name="reset_test", fail_max=1)
        breaker = manager.get_breaker("reset_test")

        # Force some failures
        for _ in range(5):
            breaker._on_failure()

        # Reset all
        manager.reset_all()

        # State should be closed after reset
        assert manager.get_breaker_state("reset_test") == CircuitState.CLOSED

    def test_get_all_breakers(self, manager):
        """Test getting all breakers"""
        manager.register_breaker(name="service1", fail_max=5)
        manager.register_breaker(name="service2", fail_max=10)

        all_breakers = manager.get_all_breakers()

        assert "service1" in all_breakers
        assert "service2" in all_breakers


class TestCircuitBreakerMetrics:
    """Tests for get_breaker_metrics() method"""

    @pytest.fixture
    def manager(self):
        return CircuitBreakerManager()

    def test_get_breaker_metrics_basic(self, manager):
        """Test basic metrics retrieval"""
        manager.register_breaker(name="metrics_test", fail_max=5)

        metrics = manager.get_breaker_metrics("metrics_test")

        assert metrics is not None
        assert "state" in metrics
        assert "failure_count" in metrics
        assert "success_count" in metrics
        assert "total_calls" in metrics
        assert "error_rate" in metrics

    def test_get_breaker_metrics_nonexistent(self, manager):
        """Test metrics for non-existent breaker returns None"""
        metrics = manager.get_breaker_metrics("nonexistent_breaker")

        assert metrics is None

    def test_get_breaker_metrics_after_successes(self, manager):
        """Test metrics after recording successes"""
        manager.register_breaker(name="success_metrics", fail_max=5)
        breaker = manager.get_breaker("success_metrics")

        # Record successes
        for _ in range(10):
            breaker._on_success()

        metrics = manager.get_breaker_metrics("success_metrics")

        assert metrics["success_count"] == 10
        assert metrics["error_rate"] == 0.0

    def test_get_breaker_metrics_after_failures(self, manager):
        """Test metrics after recording failures"""
        manager.register_breaker(name="failure_metrics", fail_max=10)
        breaker = manager.get_breaker("failure_metrics")

        # Record some successes and failures
        for _ in range(7):
            breaker._on_success()
        for _ in range(3):
            breaker._on_failure()

        metrics = manager.get_breaker_metrics("failure_metrics")

        assert metrics["success_count"] == 7
        assert metrics["failure_count"] == 3
        assert metrics["total_calls"] == 10
        assert metrics["error_rate"] == 30.0  # 3/10 * 100

    def test_get_metrics_wrapper(self, manager):
        """Test get_metrics() wrapper method"""
        manager.register_breaker(name="wrapper_test", fail_max=5)

        metrics = manager.get_metrics()

        assert metrics is not None
        assert hasattr(metrics, "to_dict")
        assert hasattr(metrics, "breakers")

        data = metrics.to_dict()
        assert "wrapper_test" in data


class TestCallWithBreaker:
    """Tests for call_with_breaker() method"""

    @pytest.fixture
    def manager(self):
        return CircuitBreakerManager()

    @pytest.mark.asyncio
    async def test_call_with_breaker_success(self, manager):
        """Test successful call through breaker"""
        manager.register_breaker(name="call_test", fail_max=5)

        async def success_func():
            return "success"

        result = await manager.call_with_breaker("call_test", success_func)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_call_with_breaker_sync_function(self, manager):
        """Test calling sync function through breaker"""
        manager.register_breaker(name="sync_test", fail_max=5)

        def sync_func():
            return 42

        result = await manager.call_with_breaker("sync_test", sync_func)

        assert result == 42

    @pytest.mark.asyncio
    async def test_call_with_breaker_failure(self, manager):
        """Test failure handling through breaker"""
        manager.register_breaker(name="fail_test", fail_max=5)

        async def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await manager.call_with_breaker("fail_test", failing_func)

        # Failure should be recorded
        metrics = manager.get_breaker_metrics("fail_test")
        assert metrics["failure_count"] >= 1

    @pytest.mark.asyncio
    async def test_call_with_breaker_open_circuit(self, manager):
        """Test that open circuit rejects calls"""
        manager.register_breaker(name="open_test", fail_max=2)
        breaker = manager.get_breaker("open_test")

        # Force circuit open
        for _ in range(5):
            breaker._on_failure()

        async def never_called():
            return "should not reach here"

        # Should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            await manager.call_with_breaker("open_test", never_called)


class TestCircuitBreakerState:
    """Tests for CircuitState enum"""

    def test_states_exist(self):
        """Test all circuit states are defined"""
        assert CircuitState.CLOSED is not None
        assert CircuitState.OPEN is not None
        assert CircuitState.HALF_OPEN is not None

    def test_state_values(self):
        """Test state values"""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestGetCircuitManager:
    """Tests for global circuit manager getter"""

    def test_get_circuit_manager_returns_manager(self):
        """Test that get_circuit_manager returns a manager"""
        manager = get_circuit_manager()

        assert manager is not None
        assert isinstance(manager, CircuitBreakerManager)

    def test_get_circuit_manager_singleton(self):
        """Test that get_circuit_manager returns same instance"""
        manager1 = get_circuit_manager()
        manager2 = get_circuit_manager()

        assert manager1 is manager2


class TestCircuitBreakerError:
    """Tests for CircuitBreakerError exception"""

    def test_error_message(self):
        """Test error contains message"""
        error = CircuitBreakerError("Service unavailable")

        assert str(error) == "Service unavailable"

    def test_error_inheritance(self):
        """Test error is an Exception"""
        error = CircuitBreakerError("Test")

        assert isinstance(error, Exception)


class TestMaybeAdaptBreakers:
    """Tests for adaptive breaker tuning"""

    @pytest.fixture
    def manager(self):
        return CircuitBreakerManager()

    def test_maybe_adapt_breakers_respects_interval(self, manager):
        """Test that adaptation respects minimum interval"""
        # First call
        _result1 = manager.maybe_adapt_breakers()

        # Immediate second call should be skipped
        result2 = manager.maybe_adapt_breakers()

        # Second result should be empty (skipped due to interval)
        assert result2 == {}

    def test_maybe_adapt_breakers_force(self, manager):
        """Test forcing adaptation bypasses interval"""
        # First call
        manager.maybe_adapt_breakers()

        # Forced call should work
        result = manager.maybe_adapt_breakers(force=True)

        # Should not raise, may return empty dict
        assert isinstance(result, dict)
