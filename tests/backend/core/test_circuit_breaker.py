"""
Tests for backend/core/circuit_breaker.py

Basic tests for circuit breaker functionality.
"""


import pytest

from backend.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
    circuit_breaker,
    get_circuit_registry,
    resilient_call,
)


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.timeout == 30.0
        assert config.half_open_max_calls == 3
        assert config.success_threshold == 3

    def test_custom_values(self):
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            timeout=60.0,
            half_open_max_calls=5,
            success_threshold=3,
        )
        assert config.failure_threshold == 10
        assert config.timeout == 60.0


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state(self):
        """Test initial state is closed."""
        breaker = CircuitBreaker("test_breaker")
        assert breaker.state == CircuitState.CLOSED

    def test_record_success(self):
        """Test recording success."""
        breaker = CircuitBreaker("test_success")
        breaker.record_success(latency_ms=100)
        assert breaker.state == CircuitState.CLOSED

    def test_get_status(self):
        """Test getting circuit breaker status."""
        breaker = CircuitBreaker("test_stats")
        breaker.record_success(latency_ms=50)

        status = breaker.get_status()

        assert status["name"] == "test_stats"
        assert status["state"] == "closed"


class TestCircuitBreakerRegistry:
    """Tests for circuit breaker registry."""

    def test_get_or_create(self):
        """Test getting or creating circuit breaker."""
        registry = CircuitBreakerRegistry()

        breaker1 = registry.get_or_create("test_service_reg")
        breaker2 = registry.get_or_create("test_service_reg")

        assert breaker1 is breaker2

    def test_get_or_create_with_config(self):
        """Test getting circuit breaker with custom config."""
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig(failure_threshold=10)

        breaker = registry.get_or_create("custom_service_reg", config)
        assert breaker.config.failure_threshold == 10


class TestGlobalRegistry:
    """Tests for global registry function."""

    def test_get_circuit_registry(self):
        """Test getting global registry."""
        registry = get_circuit_registry()
        assert registry is not None
        assert isinstance(registry, CircuitBreakerRegistry)

    def test_global_registry_is_singleton(self):
        """Test global registry is same instance."""
        reg1 = get_circuit_registry()
        reg2 = get_circuit_registry()
        assert reg1 is reg2


class TestCircuitBreakerDecorator:
    """Tests for circuit_breaker decorator."""

    @pytest.mark.asyncio
    async def test_decorator_on_async_function(self):
        """Test decorator on async function."""
        call_count = 0

        @circuit_breaker("decorator_test_new")
        async def decorated_fn():
            nonlocal call_count
            call_count += 1
            return "decorated result"

        result = await decorated_fn()
        assert result == "decorated result"
        assert call_count == 1


class TestResilientCall:
    """Tests for resilient_call decorator."""

    @pytest.mark.asyncio
    async def test_successful_call(self):
        """Test successful async call with resilient_call."""

        @resilient_call("resilient_test_new")
        async def success_fn():
            return "success"

        result = await success_fn()
        assert result == "success"
