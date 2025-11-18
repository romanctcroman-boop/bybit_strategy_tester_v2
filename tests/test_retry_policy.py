"""
Unit Tests for Retry Policy

Tests all retry scenarios based on DeepSeek + Perplexity Agent recommendations:
1. Successful retry after transient failure
2. Max retries exhausted (permanent failure)
3. Exponential backoff timing verification
4. Jitter randomization
5. Exception filtering (retryable vs non-retryable)
6. HTTP status code filtering (5xx vs 4xx)
7. Metrics accuracy
8. Integration scenarios
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock

from reliability.retry_policy import (
    RetryPolicy,
    RetryConfig,
    RetryableException,
    NonRetryableException,
    is_http_error_retryable,
)


@pytest.fixture
def retry_policy():
    """Create retry policy with test-friendly config"""
    config = RetryConfig(
        max_retries=3,
        base_delay=0.1,  # 100ms for faster tests
        max_delay=1.0,   # 1 second max
        exponential_base=2,
        jitter=False     # Disable jitter for predictable tests
    )
    return RetryPolicy(config)


@pytest.fixture
def retry_policy_with_jitter():
    """Create retry policy with jitter enabled"""
    config = RetryConfig(
        max_retries=3,
        base_delay=0.1,
        max_delay=1.0,
        exponential_base=2,
        jitter=True,
        jitter_min=0.5,
        jitter_max=1.5
    )
    return RetryPolicy(config)


class TestRetryPolicyInit:
    """Test retry policy initialization"""
    
    def test_init_default_config(self):
        """Test initialization with default config"""
        policy = RetryPolicy()
        assert policy.config.max_retries == 3
        assert policy.config.base_delay == 1.0
        assert policy.config.max_delay == 30.0
        assert policy.config.exponential_base == 2
        assert policy.config.jitter is True
        assert policy.total_attempts == 0
        assert policy.total_successes == 0
        assert policy.total_failures == 0
    
    def test_init_custom_config(self):
        """Test initialization with custom config"""
        config = RetryConfig(
            max_retries=5,
            base_delay=2.0,
            max_delay=60.0
        )
        policy = RetryPolicy(config)
        assert policy.config.max_retries == 5
        assert policy.config.base_delay == 2.0
        assert policy.config.max_delay == 60.0


class TestRetryPolicySuccessScenarios:
    """Test successful retry scenarios"""
    
    @pytest.mark.asyncio
    async def test_first_attempt_succeeds(self, retry_policy):
        """Test function succeeds on first attempt (no retry needed)"""
        async def always_succeeds():
            return "success"
        
        result = await retry_policy.retry(always_succeeds)
        
        assert result == "success"
        assert retry_policy.total_attempts == 1
        assert retry_policy.total_successes == 1
        assert retry_policy.total_failures == 0
    
    @pytest.mark.asyncio
    async def test_succeeds_after_one_retry(self, retry_policy):
        """Test function succeeds on second attempt"""
        call_count = 0
        
        async def fails_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Transient error")
            return "success"
        
        start_time = time.time()
        result = await retry_policy.retry(fails_once)
        elapsed = time.time() - start_time
        
        assert result == "success"
        assert retry_policy.total_attempts == 2
        assert retry_policy.total_successes == 1
        assert retry_policy.total_failures == 1
        # Should have delayed ~0.1s for one retry
        assert elapsed >= 0.1
    
    @pytest.mark.asyncio
    async def test_succeeds_after_multiple_retries(self, retry_policy):
        """Test function succeeds after multiple retries"""
        call_count = 0
        
        async def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError("Transient error")
            return "success"
        
        result = await retry_policy.retry(fails_twice)
        
        assert result == "success"
        assert retry_policy.total_attempts == 3
        assert retry_policy.total_successes == 1
        assert retry_policy.total_failures == 2


class TestRetryPolicyFailureScenarios:
    """Test failure scenarios"""
    
    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self, retry_policy):
        """Test all retries exhausted with permanent failure"""
        async def always_fails():
            raise ValueError("Permanent error")
        
        with pytest.raises(ValueError, match="Permanent error"):
            await retry_policy.retry(always_fails)
        
        # 1 initial + 3 retries = 4 attempts
        assert retry_policy.total_attempts == 4
        assert retry_policy.total_successes == 0
        assert retry_policy.total_failures == 4
    
    @pytest.mark.asyncio
    async def test_non_retryable_exception_fails_immediately(self, retry_policy):
        """Test non-retryable exception fails without retry"""
        async def non_retryable_error():
            raise NonRetryableException("Client error - don't retry")
        
        with pytest.raises(NonRetryableException):
            await retry_policy.retry(non_retryable_error)
        
        # Only 1 attempt (no retries)
        assert retry_policy.total_attempts == 1
        assert retry_policy.total_failures == 1


class TestExponentialBackoff:
    """Test exponential backoff timing"""
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self, retry_policy):
        """Test that delays follow exponential pattern"""
        async def always_fails():
            raise ValueError("Error")
        
        start_time = time.time()
        
        with pytest.raises(ValueError):
            await retry_policy.retry(always_fails)
        
        elapsed = time.time() - start_time
        
        # Expected delays: 0.1s, 0.2s, 0.4s = 0.7s total
        # Allow 10% tolerance for execution overhead
        assert 0.63 <= elapsed <= 0.8
    
    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Test that delay is capped at max_delay"""
        config = RetryConfig(
            max_retries=5,
            base_delay=1.0,
            max_delay=2.0,  # Cap at 2 seconds
            exponential_base=2,
            jitter=False
        )
        policy = RetryPolicy(config)
        
        # Test delay calculation directly
        delay_0 = policy._calculate_delay(0)  # 1.0 * 2^0 = 1.0
        delay_1 = policy._calculate_delay(1)  # 1.0 * 2^1 = 2.0
        delay_2 = policy._calculate_delay(2)  # 1.0 * 2^2 = 4.0 → capped to 2.0
        delay_3 = policy._calculate_delay(3)  # 1.0 * 2^3 = 8.0 → capped to 2.0
        
        assert delay_0 == 1.0
        assert delay_1 == 2.0
        assert delay_2 == 2.0  # Capped
        assert delay_3 == 2.0  # Capped


class TestJitter:
    """Test jitter randomization"""
    
    @pytest.mark.asyncio
    async def test_jitter_adds_randomization(self, retry_policy_with_jitter):
        """Test that jitter randomizes delays"""
        delays = []
        
        for _ in range(10):
            delay = retry_policy_with_jitter._calculate_delay(1)
            delays.append(delay)
        
        # Expected base delay: 0.1 * 2^1 = 0.2
        # With jitter (0.5x to 1.5x): 0.1 to 0.3
        assert all(0.1 <= d <= 0.3 for d in delays)
        
        # Delays should vary (not all the same)
        assert len(set(delays)) > 1
    
    def test_jitter_disabled_gives_consistent_delay(self, retry_policy):
        """Test that disabled jitter gives consistent delays"""
        delay_1 = retry_policy._calculate_delay(1)
        delay_2 = retry_policy._calculate_delay(1)
        delay_3 = retry_policy._calculate_delay(1)
        
        # All delays should be identical (no jitter)
        assert delay_1 == delay_2 == delay_3


class TestExceptionFiltering:
    """Test exception filtering logic"""
    
    @pytest.mark.asyncio
    async def test_custom_retryable_exceptions(self, retry_policy):
        """Test custom retryable exception types"""
        call_count = 0
        
        async def specific_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Network error")
            return "success"
        
        result = await retry_policy.retry(
            specific_error,
            retryable_exceptions=(ConnectionError,)
        )
        
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_non_retryable_custom_exception(self, retry_policy):
        """Test that non-specified exceptions are not retried"""
        async def different_error():
            raise KeyError("Key not found")
        
        # Only retry ValueError, not KeyError
        with pytest.raises(KeyError):
            await retry_policy.retry(
                different_error,
                retryable_exceptions=(ValueError,)
            )
        
        # Should fail immediately (no retries)
        assert retry_policy.total_attempts == 1


class TestHTTPStatusCodeFiltering:
    """Test HTTP status code retry logic"""
    
    def test_5xx_errors_are_retryable(self):
        """Test that 5xx errors should be retried"""
        assert is_http_error_retryable(500) is True  # Internal Server Error
        assert is_http_error_retryable(502) is True  # Bad Gateway
        assert is_http_error_retryable(503) is True  # Service Unavailable
        assert is_http_error_retryable(504) is True  # Gateway Timeout
    
    def test_4xx_errors_not_retryable(self):
        """Test that most 4xx errors should NOT be retried"""
        assert is_http_error_retryable(400) is False  # Bad Request
        assert is_http_error_retryable(401) is False  # Unauthorized
        assert is_http_error_retryable(403) is False  # Forbidden
        assert is_http_error_retryable(404) is False  # Not Found
    
    def test_special_4xx_are_retryable(self):
        """Test that specific 4xx errors ARE retryable"""
        assert is_http_error_retryable(408) is True  # Request Timeout
        assert is_http_error_retryable(429) is True  # Too Many Requests (rate limit)
    
    def test_2xx_3xx_not_retryable(self):
        """Test that success codes don't need retry"""
        assert is_http_error_retryable(200) is False  # OK
        assert is_http_error_retryable(201) is False  # Created
        assert is_http_error_retryable(301) is False  # Moved Permanently
        assert is_http_error_retryable(304) is False  # Not Modified


class TestMetrics:
    """Test retry policy metrics"""
    
    @pytest.mark.asyncio
    async def test_metrics_accuracy(self, retry_policy):
        """Test that metrics are accurately tracked"""
        call_count = 0
        
        async def sometimes_fails():
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 1:
                raise ValueError("Odd failure")
            return "success"
        
        # Call twice (both need retry)
        await retry_policy.retry(sometimes_fails)  # Attempt 1 fails, attempt 2 succeeds
        await retry_policy.retry(sometimes_fails)  # Attempt 3 fails, attempt 4 succeeds
        
        metrics = retry_policy.get_metrics()
        
        assert metrics["total_attempts"] == 4  # 2 failures + 2 successes
        assert metrics["total_successes"] == 2
        assert metrics["total_failures"] == 2
        assert metrics["success_rate"] == pytest.approx(0.5, rel=0.01)  # 2/4 = 50%
    
    @pytest.mark.asyncio
    async def test_metrics_reset(self, retry_policy):
        """Test metrics reset functionality"""
        async def always_succeeds():
            return "ok"
        
        await retry_policy.retry(always_succeeds)
        
        assert retry_policy.total_attempts > 0
        
        retry_policy.reset()
        
        assert retry_policy.total_attempts == 0
        assert retry_policy.total_successes == 0
        assert retry_policy.total_failures == 0
        assert len(retry_policy.retry_history) == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    @pytest.mark.asyncio
    async def test_zero_max_retries(self):
        """Test with max_retries=0 (no retries allowed)"""
        config = RetryConfig(max_retries=0)
        policy = RetryPolicy(config)
        
        async def always_fails():
            raise ValueError("Error")
        
        with pytest.raises(ValueError):
            await policy.retry(always_fails)
        
        # Only 1 attempt (0 retries)
        assert policy.total_attempts == 1
    
    @pytest.mark.asyncio
    async def test_sync_function_wrapper(self, retry_policy):
        """Test that async wrapper works with sync-like functions"""
        call_count = 0
        
        async def async_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First call fails")
            return "success"
        
        result = await retry_policy.retry(async_func)
        assert result == "success"
        assert call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
