"""
Integration Tests: Retry Policy + Circuit Breaker

Tests the combined behavior of retry policy and circuit breaker patterns.
This demonstrates production-ready error handling with:
- Fast failure detection (circuit breaker)
- Automatic recovery attempts (retry policy)
- Cascading failure prevention
"""

import asyncio
import pytest
import time

from reliability import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenException,
    RetryPolicy,
    RetryConfig,
)


@pytest.fixture
def circuit_breaker():
    """Create circuit breaker with test-friendly config"""
    config = CircuitBreakerConfig(
        failure_threshold=0.5,
        window_size=10,
        open_timeout=1.0,  # 1 second for faster tests
        half_open_max_probes=3,
        min_requests=3
    )
    return CircuitBreaker("test_api", config)


@pytest.fixture
def retry_policy():
    """Create retry policy with test-friendly config"""
    config = RetryConfig(
        max_retries=3,
        base_delay=0.1,
        max_delay=1.0,
        jitter=False
    )
    return RetryPolicy(config)


class TestRetryWithCircuitBreaker:
    """Test retry policy working with circuit breaker"""
    
    @pytest.mark.asyncio
    async def test_retry_succeeds_before_circuit_opens(self, circuit_breaker, retry_policy):
        """Test retry recovers from transient failures before circuit opens"""
        call_count = 0
        
        async def flaky_api():
            nonlocal call_count
            call_count += 1
            # Fail first 2 attempts, succeed on 3rd
            if call_count <= 2:
                raise ValueError("Transient error")
            return "success"
        
        # Wrap with both circuit breaker and retry
        async def protected_api():
            return await circuit_breaker.call(flaky_api)
        
        result = await retry_policy.retry(protected_api)
        
        assert result == "success"
        assert call_count == 3
        # Circuit should still be CLOSED (retry succeeded before threshold)
        assert circuit_breaker.state.value == "closed"
    
    @pytest.mark.asyncio
    async def test_circuit_opens_when_retries_exhausted(self, circuit_breaker, retry_policy):
        """Test circuit opens when all retries fail"""
        async def always_fails():
            raise ValueError("Permanent failure")
        
        async def protected_api():
            return await circuit_breaker.call(always_fails)
        
        # First call: retry exhausts (4 attempts: 1 initial + 3 retries)
        # Circuit opens on 3rd attempt, 4th attempt raises CircuitBreakerOpenException
        with pytest.raises(CircuitBreakerOpenException):
            await retry_policy.retry(protected_api)
        
        # Circuit should be OPEN (exceeded failure threshold)
        assert circuit_breaker.state.value == "open"
        
        # Second call: circuit is OPEN, should fail immediately (no retries)
        with pytest.raises(CircuitBreakerOpenException):
            await circuit_breaker.call(always_fails)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_unnecessary_retries(self, circuit_breaker, retry_policy):
        """Test circuit breaker stops retries when OPEN"""
        call_count = 0
        
        async def counting_failure():
            nonlocal call_count
            call_count += 1
            raise ValueError("Error")
        
        async def protected_api():
            return await circuit_breaker.call(counting_failure)
        
        # Trip the circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                await protected_api()
        
        assert circuit_breaker.state.value == "open"
        
        # Reset call counter
        call_count = 0
        
        # Now try with retry - circuit should block immediately
        with pytest.raises(CircuitBreakerOpenException):
            await retry_policy.retry(protected_api)
        
        # No actual API calls should have been made (call_count stays 0)
        assert call_count == 0


class TestRecoveryScenarios:
    """Test recovery scenarios with both patterns"""
    
    @pytest.mark.asyncio
    async def test_recovery_after_circuit_half_open(self, circuit_breaker, retry_policy):
        """Test successful recovery when circuit transitions to HALF_OPEN"""
        call_count = 0
        
        async def intermittent_api():
            nonlocal call_count
            call_count += 1
            # Fail first 3 calls, then succeed
            if call_count <= 3:
                raise ValueError("Service down")
            return "recovered"
        
        async def protected_api():
            return await circuit_breaker.call(intermittent_api)
        
        # Trip the circuit (3 failures)
        for _ in range(3):
            with pytest.raises(ValueError):
                await protected_api()
        
        assert circuit_breaker.state.value == "open"
        
        # Wait for circuit to transition to HALF_OPEN
        await asyncio.sleep(1.1)
        
        # Now retry should succeed (circuit will allow probe)
        result = await retry_policy.retry(protected_api)
        
        assert result == "recovered"
        # After successful probes, circuit closes
        assert circuit_breaker.state.value in ("half_open", "closed")
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self, circuit_breaker, retry_policy):
        """Test system degrades gracefully under load"""
        call_count = 0
        
        async def unreliable_api():
            nonlocal call_count
            call_count += 1
            # Deterministic: fail on 1st, 3rd, 5th calls (50% failure rate)
            if call_count % 2 == 1:
                raise ValueError("Intermittent failure")
            return "ok"
        
        async def protected_api():
            return await circuit_breaker.call(unreliable_api)
        
        # Make multiple calls
        results = []
        for _ in range(10):
            try:
                result = await retry_policy.retry(protected_api)
                results.append(result)
            except Exception:
                results.append(None)
        
        # Some calls should succeed (with retries recovering from failures)
        successful_results = [r for r in results if r is not None]
        assert len(successful_results) > 0
        
        # System should still be operational
        print(f"Success rate: {len(successful_results)}/10")
        print(f"Circuit state: {circuit_breaker.state.value}")


class TestPerformanceCharacteristics:
    """Test performance characteristics of combined patterns"""
    
    @pytest.mark.asyncio
    async def test_fast_failure_when_circuit_open(self, circuit_breaker, retry_policy):
        """Test that circuit breaker provides fast failure"""
        async def slow_failing_api():
            await asyncio.sleep(0.5)  # Slow API
            raise ValueError("Slow failure")
        
        async def protected_api():
            return await circuit_breaker.call(slow_failing_api)
        
        # Trip the circuit (3 slow failures = 1.5s)
        for _ in range(3):
            with pytest.raises(ValueError):
                await protected_api()
        
        assert circuit_breaker.state.value == "open"
        
        # Now calls should fail FAST (no 0.5s delay)
        start_time = time.time()
        with pytest.raises(CircuitBreakerOpenException):
            await retry_policy.retry(protected_api)
        elapsed = time.time() - start_time
        
        # Should be instant (< 0.1s), not 0.5s
        assert elapsed < 0.1
    
    @pytest.mark.asyncio
    async def test_retry_overhead_is_minimal(self, retry_policy):
        """Test that retry overhead is minimal for successful calls"""
        async def fast_api():
            return "instant"
        
        start_time = time.time()
        result = await retry_policy.retry(fast_api)
        elapsed = time.time() - start_time
        
        assert result == "instant"
        # Should be nearly instant (< 10ms overhead)
        assert elapsed < 0.01


class TestMetricsIntegration:
    """Test metrics from both patterns"""
    
    @pytest.mark.asyncio
    async def test_combined_metrics(self, circuit_breaker, retry_policy):
        """Test metrics from both circuit breaker and retry policy"""
        call_count = 0
        
        async def sometimes_fails():
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 1:
                raise ValueError("Every 3rd call fails")
            return "ok"
        
        async def protected_api():
            return await circuit_breaker.call(sometimes_fails)
        
        # Make several calls
        for _ in range(6):
            try:
                await retry_policy.retry(protected_api)
            except Exception:
                pass
        
        # Check circuit breaker metrics
        cb_metrics = circuit_breaker.get_metrics()
        assert cb_metrics["total_requests"] > 0
        
        # Check retry policy metrics
        retry_metrics = retry_policy.get_metrics()
        assert retry_metrics["total_attempts"] > 0
        
        print(f"Circuit Breaker: {cb_metrics['total_requests']} requests, "
              f"{cb_metrics['success_rate']:.1%} success rate")
        print(f"Retry Policy: {retry_metrics['total_attempts']} attempts, "
              f"{retry_metrics['success_rate']:.1%} success rate")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
