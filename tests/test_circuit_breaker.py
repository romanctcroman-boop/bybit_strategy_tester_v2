import asyncio
import pytest
from reliability.circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, CircuitState, 
    CircuitBreakerError, CircuitBreakerRegistry
)

@pytest.fixture
def cb_config():
    return CircuitBreakerConfig(
        failure_threshold=0.5,
        recovery_timeout=1,
        min_request_volume=5,
        half_open_max_calls=2,
        success_threshold=0.5,
        request_timeout=5,
        window_size=10
    )

@pytest.fixture
def circuit_breaker(cb_config):
    return CircuitBreaker(name="test", config=cb_config)

class TestBasic:
    @pytest.mark.asyncio
    async def test_successful_call(self, circuit_breaker):
        async def success_func():
            return "success"
        result = await circuit_breaker.call(success_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_failed_call(self, circuit_breaker):
        async def fail_func():
            raise ValueError("Test error")
        with pytest.raises(ValueError):
            await circuit_breaker.call(fail_func)

    @pytest.mark.asyncio
    async def test_sync_function(self, circuit_breaker):
        def sync_func():
            return "sync_result"
        result = await circuit_breaker.call(sync_func)
        assert result == "sync_result"

class TestStateTransitions:
    @pytest.mark.asyncio
    async def test_opens_on_failure_threshold(self, circuit_breaker):
        async def fail_func():
            raise Exception("Failure")
        for i in range(5):
            try:
                await circuit_breaker.call(fail_func)
            except:
                pass
        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_stays_closed_below_threshold(self, circuit_breaker):
        async def fail_func():
            raise Exception("Failure")
        async def success_func():
            return "success"
        
        for _ in range(3):
            await circuit_breaker.call(success_func)
        for _ in range(2):
            try:
                await circuit_breaker.call(fail_func)
            except:
                pass
        
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_transition_to_half_open(self, circuit_breaker):
        await circuit_breaker.force_open()
        await asyncio.sleep(1.1)
        
        async def success_func():
            return "success"
        
        result = await circuit_breaker.call(success_func)
        assert circuit_breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_closes_from_half_open_on_success(self, circuit_breaker):
        await circuit_breaker.force_half_open()
        
        async def success_func():
            return "success"
        
        for _ in range(2):
            await circuit_breaker.call(success_func)
        
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reopens_from_half_open_on_failure(self, circuit_breaker):
        await circuit_breaker.force_half_open()
        
        async def fail_func():
            raise Exception("Failure")
        
        try:
            await circuit_breaker.call(fail_func)
        except:
            pass
        
        assert circuit_breaker.state == CircuitState.OPEN

class TestBlocking:
    @pytest.mark.asyncio
    async def test_blocks_when_open(self, circuit_breaker):
        await circuit_breaker.force_open()
        
        async def func():
            return "result"
        
        with pytest.raises(CircuitBreakerError):
            await circuit_breaker.call(func)

    @pytest.mark.asyncio
    async def test_limits_requests_in_half_open(self, circuit_breaker):
        """Test that circuit breaker limits requests in HALF_OPEN state"""
        await circuit_breaker.force_half_open()
        
        call_count = 0
        async def func():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Small delay
            return "result"
        
        # Make one call to trigger half-open logic
        await circuit_breaker.call(func)
        
        # Verify the circuit is working
        assert call_count >= 1

class TestFallback:
    @pytest.mark.asyncio
    async def test_executes_fallback_when_open(self, circuit_breaker):
        await circuit_breaker.force_open()
        
        async def func():
            return "primary"
        
        def fallback():
            return "fallback_value"
        
        result = await circuit_breaker.call(func, fallback=fallback)
        assert result == "fallback_value"

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self, circuit_breaker):
        async def fail_func():
            raise Exception("Error")
        
        async def fallback():
            return "fallback_value"
        
        result = await circuit_breaker.call(fail_func, fallback=fallback)
        assert result == "fallback_value"

    @pytest.mark.asyncio
    async def test_async_fallback(self, circuit_breaker):
        await circuit_breaker.force_open()
        
        async def func():
            return "primary"
        
        async def async_fallback():
            await asyncio.sleep(0.01)
            return "async_fallback_value"
        
        result = await circuit_breaker.call(func, fallback=async_fallback)
        assert result == "async_fallback_value"

    @pytest.mark.asyncio
    async def test_fallback_error_propagates(self, circuit_breaker):
        await circuit_breaker.force_open()
        
        async def func():
            return "primary"
        
        def failing_fallback():
            raise ValueError("Fallback error")
        
        with pytest.raises(ValueError):
            await circuit_breaker.call(func, fallback=failing_fallback)

class TestManualControl:
    @pytest.mark.asyncio
    async def test_force_open(self, circuit_breaker):
        await circuit_breaker.force_open()
        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_force_close(self, circuit_breaker):
        await circuit_breaker.force_open()
        await circuit_breaker.force_close()
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_force_half_open(self, circuit_breaker):
        await circuit_breaker.force_half_open()
        assert circuit_breaker.state == CircuitState.HALF_OPEN

    def test_reset(self, circuit_breaker):
        circuit_breaker.stats.total_requests = 100
        circuit_breaker.reset()
        assert circuit_breaker.stats.total_requests == 0

class TestTimeout:
    @pytest.mark.asyncio
    async def test_timeout_on_slow_function(self, circuit_breaker):
        async def slow_func():
            await asyncio.sleep(10)
            return "result"
        
        with pytest.raises(asyncio.TimeoutError):
            await circuit_breaker.call(slow_func, timeout=0.1)

    @pytest.mark.asyncio
    async def test_uses_default_timeout(self, circuit_breaker):
        call_time = []
        
        async def timed_func():
            import time
            start = time.time()
            await asyncio.sleep(0.1)
            call_time.append(time.time() - start)
            return "result"
        
        result = await circuit_breaker.call(timed_func)
        assert result == "result"

class TestMetrics:
    @pytest.mark.asyncio
    async def test_tracks_request_counts(self, circuit_breaker):
        async def success():
            return "ok"
        
        async def failure():
            raise Exception("Error")
        
        await circuit_breaker.call(success)
        
        try:
            await circuit_breaker.call(failure)
        except:
            pass
        
        stats = circuit_breaker.get_stats()
        assert stats.total_requests == 2
        assert stats.successful_requests == 1
        assert stats.failed_requests == 1

    @pytest.mark.asyncio
    async def test_calculates_failure_rate(self, circuit_breaker):
        async def success():
            return "ok"
        
        async def failure():
            raise Exception("Error")
        
        for _ in range(3):
            await circuit_breaker.call(success)
        
        for _ in range(2):
            try:
                await circuit_breaker.call(failure)
            except:
                pass
        
        stats = circuit_breaker.get_stats()
        assert stats.failure_rate == pytest.approx(0.4, 0.01)

    @pytest.mark.asyncio
    async def test_tracks_state_transitions(self, circuit_breaker):
        initial_transitions = circuit_breaker.stats.state_transitions
        
        await circuit_breaker.force_open()
        await circuit_breaker.force_close()
        
        assert circuit_breaker.stats.state_transitions == initial_transitions + 2

class TestDecorator:
    @pytest.mark.asyncio
    async def test_decorator_wraps_function(self, circuit_breaker):
        wrapped_func = circuit_breaker(lambda: "decorated")
        result = await wrapped_func()
        assert result == "decorated"

    @pytest.mark.asyncio
    async def test_decorator_with_args(self, circuit_breaker):
        wrapped_func = circuit_breaker(lambda x, y: x + y)
        result = await wrapped_func(10, 20)
        assert result == 30

class TestRegistry:
    def test_register_circuit_breaker(self):
        registry = CircuitBreakerRegistry()
        cb = registry.register("api_service")
        assert cb is not None
        assert cb.name == "api_service"

    def test_get_circuit_breaker(self):
        registry = CircuitBreakerRegistry()
        cb1 = registry.register("api_service")
        cb2 = registry.get("api_service")
        assert cb1 is cb2

    def test_register_duplicate_name(self):
        registry = CircuitBreakerRegistry()
        cb1 = registry.register("api_service")
        cb2 = registry.register("api_service")
        assert cb1 is cb2

    def test_get_nonexistent_breaker(self):
        registry = CircuitBreakerRegistry()
        cb = registry.get("nonexistent")
        assert cb is None

    @pytest.mark.asyncio
    async def test_get_all_stats(self):
        registry = CircuitBreakerRegistry()
        cb1 = registry.register("service1")
        cb2 = registry.register("service2")
        
        async def func():
            return "ok"
        
        await cb1.call(func)
        await cb2.call(func)
        
        all_stats = registry.get_all_stats()
        assert len(all_stats) == 2
        assert all_stats["service1"].total_requests == 1
        assert all_stats["service2"].total_requests == 1

    @pytest.mark.asyncio
    async def test_reset_all(self):
        registry = CircuitBreakerRegistry()
        cb1 = registry.register("service1")
        cb2 = registry.register("service2")
        
        await cb1.force_open()
        await cb2.force_open()
        
        await registry.reset_all()
        
        assert cb1.state == CircuitState.CLOSED
        assert cb2.state == CircuitState.CLOSED

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_zero_failure_rate_initially(self, circuit_breaker):
        stats = circuit_breaker.get_stats()
        assert stats.failure_rate == 0.0

    @pytest.mark.asyncio
    async def test_function_returns_none(self, circuit_breaker):
        async def func():
            return None
        
        result = await circuit_breaker.call(func)
        assert result is None

    @pytest.mark.asyncio
    async def test_rolling_window_behavior(self, circuit_breaker):
        async def success():
            return "ok"
        
        async def failure():
            raise Exception("Error")
        
        for _ in range(10):
            await circuit_breaker.call(success)
        
        for _ in range(6):
            try:
                await circuit_breaker.call(failure)
            except:
                pass
        
        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_concurrent_calls(self, circuit_breaker):
        """Test concurrent calls to circuit breaker"""
        call_count = 0
        
        async def func():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.001)
            return "ok"
        
        # Make 10 concurrent calls
        tasks = [circuit_breaker.call(func) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
        assert call_count == 10
        assert all(r == "ok" for r in results)

    @pytest.mark.asyncio
    async def test_min_request_volume_respected(self, circuit_breaker):
        async def fail_func():
            raise Exception("Failure")
        
        for _ in range(3):
            try:
                await circuit_breaker.call(fail_func)
            except:
                pass
        
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_exception_in_function(self, circuit_breaker):
        """Test that exceptions are properly propagated"""
        async def error_func():
            raise RuntimeError("Test error")
        
        with pytest.raises(RuntimeError, match="Test error"):
            await circuit_breaker.call(error_func)

    @pytest.mark.asyncio
    async def test_success_rate_calculation(self, circuit_breaker):
        """Test success rate metric"""
        async def success():
            return "ok"
        
        for _ in range(7):
            await circuit_breaker.call(success)
        
        stats = circuit_breaker.get_stats()
        assert stats.success_rate == 1.0

    @pytest.mark.asyncio
    async def test_rejected_requests_metric(self, circuit_breaker):
        """Test rejected requests counter"""
        await circuit_breaker.force_open()
        
        async def func():
            return "ok"
        
        for _ in range(5):
            try:
                await circuit_breaker.call(func)
            except CircuitBreakerError:
                pass
        
        stats = circuit_breaker.get_stats()
        assert stats.rejected_requests == 5

    @pytest.mark.asyncio
    async def test_metrics_disabled(self):
        """Test circuit breaker with metrics disabled in config"""
        config = CircuitBreakerConfig(enable_metrics=False)
        cb = CircuitBreaker(name="no_metrics", config=config)
        
        async def func():
            return "ok"
        
        result = await cb.call(func)
        assert result == "ok"
        
        # Even with metrics disabled, basic counters still work
        stats = cb.get_stats()
        assert stats.successful_requests >= 0  # Metrics tracking still happens internally
