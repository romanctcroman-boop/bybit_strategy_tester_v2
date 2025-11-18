"""
Comprehensive tests for backend/core/retry.py

Target: 100% coverage (36 statements)
Strategy: Test decorator with various scenarios, exception types, and edge cases
"""

import pytest
import time
from unittest.mock import Mock, patch, call
from backend.core.retry import (
    retry_with_backoff,
    RetryableError,
    RateLimitError,
    NetworkError
)


# ==================== FIXTURES ====================

@pytest.fixture
def mock_function():
    """Mock function for testing decorator"""
    return Mock(__name__='test_function')


@pytest.fixture
def mock_logger():
    """Mock logger to verify logging behavior"""
    with patch('backend.core.retry.logger') as mock_log:
        yield mock_log


# ==================== TEST RETRY DECORATOR ====================

class TestRetryWithBackoffSuccess:
    """Tests for successful function execution"""
    
    def test_first_attempt_success(self, mock_function):
        """First attempt succeeds immediately"""
        mock_function.return_value = 'success'
        
        @retry_with_backoff(max_attempts=3)
        def test_func():
            return mock_function()
        
        result = test_func()
        
        assert result == 'success'
        assert mock_function.call_count == 1
    
    def test_second_attempt_success(self, mock_function, mock_logger):
        """First attempt fails, second succeeds"""
        mock_function.side_effect = [ConnectionError("network error"), 'success']
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def test_func():
            return mock_function()
        
        result = test_func()
        
        assert result == 'success'
        assert mock_function.call_count == 2
        mock_logger.warning.assert_called_once()
    
    def test_third_attempt_success(self, mock_function, mock_logger):
        """First two attempts fail, third succeeds"""
        mock_function.side_effect = [
            TimeoutError("timeout 1"),
            TimeoutError("timeout 2"),
            'success'
        ]
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def test_func():
            return mock_function()
        
        result = test_func()
        
        assert result == 'success'
        assert mock_function.call_count == 3
        assert mock_logger.warning.call_count == 2


class TestRetryWithBackoffFailure:
    """Tests for all attempts failing"""
    
    def test_all_attempts_fail_connection_error(self, mock_function, mock_logger):
        """All attempts fail with ConnectionError"""
        mock_function.side_effect = ConnectionError("network error")
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def test_func():
            return mock_function()
        
        with pytest.raises(ConnectionError, match="network error"):
            test_func()
        
        assert mock_function.call_count == 3
        assert mock_logger.warning.call_count == 2  # First 2 attempts
        mock_logger.error.assert_called_once()  # Final failure
    
    def test_all_attempts_fail_timeout_error(self, mock_function, mock_logger):
        """All attempts fail with TimeoutError"""
        mock_function.side_effect = TimeoutError("timeout")
        
        @retry_with_backoff(max_attempts=2, initial_delay=0.01)
        def test_func():
            return mock_function()
        
        with pytest.raises(TimeoutError, match="timeout"):
            test_func()
        
        assert mock_function.call_count == 2
        assert mock_logger.warning.call_count == 1
        mock_logger.error.assert_called_once()
    
    def test_single_attempt_fails(self, mock_function, mock_logger):
        """Only one attempt, fails immediately"""
        mock_function.side_effect = ConnectionError("network error")
        
        @retry_with_backoff(max_attempts=1, initial_delay=0.01)
        def test_func():
            return mock_function()
        
        with pytest.raises(ConnectionError, match="network error"):
            test_func()
        
        assert mock_function.call_count == 1
        mock_logger.warning.assert_not_called()  # No retries
        mock_logger.error.assert_called_once()


class TestRetryBackoffTiming:
    """Tests for exponential backoff behavior"""
    
    @patch('backend.core.retry.time.sleep')
    def test_exponential_backoff_delays(self, mock_sleep, mock_function):
        """Verify exponential backoff: 1s, 2s, 4s"""
        mock_function.side_effect = [
            ConnectionError("error 1"),
            ConnectionError("error 2"),
            ConnectionError("error 3"),
            'success'
        ]
        
        @retry_with_backoff(
            max_attempts=4,
            initial_delay=1.0,
            backoff_factor=2.0
        )
        def test_func():
            return mock_function()
        
        result = test_func()
        
        assert result == 'success'
        assert mock_sleep.call_count == 3
        mock_sleep.assert_has_calls([
            call(1.0),  # First retry
            call(2.0),  # Second retry
            call(4.0)   # Third retry
        ])
    
    @patch('backend.core.retry.time.sleep')
    def test_custom_backoff_factor(self, mock_sleep, mock_function):
        """Test custom backoff factor (3x)"""
        mock_function.side_effect = [
            ConnectionError("error"),
            ConnectionError("error"),
            'success'
        ]
        
        @retry_with_backoff(
            max_attempts=3,
            initial_delay=0.5,
            backoff_factor=3.0
        )
        def test_func():
            return mock_function()
        
        result = test_func()
        
        assert result == 'success'
        mock_sleep.assert_has_calls([
            call(0.5),  # 0.5s
            call(1.5)   # 0.5 * 3 = 1.5s
        ])
    
    @patch('backend.core.retry.time.sleep')
    def test_no_sleep_on_last_attempt(self, mock_sleep, mock_function):
        """No sleep after final attempt"""
        mock_function.side_effect = ConnectionError("error")
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.1)
        def test_func():
            return mock_function()
        
        with pytest.raises(ConnectionError):
            test_func()
        
        # Should sleep only 2 times (after attempt 1 and 2), not after attempt 3
        assert mock_sleep.call_count == 2


class TestRetryExceptionTypes:
    """Tests for different exception types"""
    
    def test_custom_exception_tuple(self, mock_function):
        """Test with custom exception types"""
        mock_function.side_effect = [
            RateLimitError("rate limited"),
            'success'
        ]
        
        @retry_with_backoff(
            max_attempts=2,
            initial_delay=0.01,
            exceptions=(RateLimitError, NetworkError)
        )
        def test_func():
            return mock_function()
        
        result = test_func()
        assert result == 'success'
        assert mock_function.call_count == 2
    
    def test_non_retryable_exception_raised_immediately(self, mock_function, mock_logger):
        """Non-retryable exception is raised immediately"""
        mock_function.side_effect = ValueError("bad value")
        
        @retry_with_backoff(
            max_attempts=3,
            initial_delay=0.01,
            exceptions=(ConnectionError, TimeoutError)
        )
        def test_func():
            return mock_function()
        
        with pytest.raises(ValueError, match="bad value"):
            test_func()
        
        # Should fail immediately without retries
        assert mock_function.call_count == 1
        mock_logger.warning.assert_not_called()
        mock_logger.error.assert_called_once()
        
        # Check error log contains "Non-retryable error"
        error_call = mock_logger.error.call_args
        assert "Non-retryable error" in error_call[0][0]
    
    def test_retryable_then_non_retryable(self, mock_function, mock_logger):
        """Retryable error followed by non-retryable error"""
        mock_function.side_effect = [
            ConnectionError("network error"),
            ValueError("bad value")
        ]
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def test_func():
            return mock_function()
        
        with pytest.raises(ValueError, match="bad value"):
            test_func()
        
        assert mock_function.call_count == 2
        mock_logger.warning.assert_called_once()  # First retry
        mock_logger.error.assert_called_once()    # Non-retryable error


class TestRetryLogging:
    """Tests for logging behavior"""
    
    def test_warning_log_contains_metadata(self, mock_function, mock_logger):
        """Warning log contains function name, attempt, delay, error"""
        mock_function.side_effect = [ConnectionError("network issue"), 'success']
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.5)
        def test_func():
            return mock_function()
        
        result = test_func()
        
        assert result == 'success'
        warning_call = mock_logger.warning.call_args
        
        # Check log message
        assert "Attempt 1/3 failed" in warning_call[0][0]
        assert "retrying in 0.5s" in warning_call[0][0]
        
        # Check extra metadata
        extra = warning_call[1]['extra']
        assert extra['function'] == 'test_func'
        assert extra['attempt'] == 1
        assert extra['max_attempts'] == 3
        assert extra['delay'] == 0.5
        assert extra['error'] == "network issue"
        assert extra['error_type'] == 'ConnectionError'
    
    def test_error_log_on_all_attempts_failed(self, mock_function, mock_logger):
        """Error log when all attempts fail"""
        mock_function.side_effect = TimeoutError("timeout")
        
        @retry_with_backoff(max_attempts=2, initial_delay=0.01)
        def test_func():
            return mock_function()
        
        with pytest.raises(TimeoutError):
            test_func()
        
        error_call = mock_logger.error.call_args
        
        # Check error message
        assert "All 2 attempts failed" in error_call[0][0]
        assert "test_func" in error_call[0][0]
        
        # Check extra metadata
        extra = error_call[1]['extra']
        assert extra['function'] == 'test_func'
        assert extra['error'] == "timeout"
        assert extra['error_type'] == 'TimeoutError'
    
    def test_error_log_on_non_retryable_exception(self, mock_function, mock_logger):
        """Error log for non-retryable exceptions"""
        mock_function.side_effect = RuntimeError("unexpected error")
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def test_func():
            return mock_function()
        
        with pytest.raises(RuntimeError):
            test_func()
        
        error_call = mock_logger.error.call_args
        
        assert "Non-retryable error" in error_call[0][0]
        assert "test_func" in error_call[0][0]
        
        extra = error_call[1]['extra']
        assert extra['error_type'] == 'RuntimeError'


class TestRetryEdgeCases:
    """Edge cases and special scenarios"""
    
    def test_max_attempts_zero_edge_case(self):
        """Max attempts of 0 means no execution"""
        @retry_with_backoff(max_attempts=0, initial_delay=0.01)
        def test_func():
            return 'never called'
        
        # With 0 attempts, function is never executed
        # last_exception is None, so raise last_exception raises None (returns None)
        result = test_func()
        
        # This actually returns None because range(1, 1) produces empty sequence
        # and last_exception is None, so nothing is raised
        assert result is None
    
    def test_last_exception_raised_after_all_retries(self):
        """Ensures last_exception is raised when all retries fail"""
        # This test specifically covers the "raise last_exception" line (line 90)
        mock_func = Mock(__name__='test_func')
        mock_func.side_effect = TimeoutError("persistent timeout")
        
        @retry_with_backoff(max_attempts=2, initial_delay=0.01)
        def test_func():
            return mock_func()
        
        # This should trigger all retries and finally raise last_exception
        with pytest.raises(TimeoutError, match="persistent timeout"):
            test_func()
        
        assert mock_func.call_count == 2
    
    def test_function_with_arguments(self, mock_function):
        """Decorated function preserves arguments"""
        mock_function.return_value = 'success'
        
        @retry_with_backoff(max_attempts=2, initial_delay=0.01)
        def test_func(a, b, c=None):
            return mock_function(a, b, c=c)
        
        result = test_func(1, 2, c=3)
        
        assert result == 'success'
        mock_function.assert_called_once_with(1, 2, c=3)
    
    def test_function_with_return_none(self, mock_function):
        """Function that returns None (valid return)"""
        mock_function.return_value = None
        
        @retry_with_backoff(max_attempts=2, initial_delay=0.01)
        def test_func():
            return mock_function()
        
        result = test_func()
        
        assert result is None
        assert mock_function.call_count == 1
    
    def test_decorator_preserves_function_metadata(self):
        """Decorator preserves function name and docstring"""
        @retry_with_backoff(max_attempts=2)
        def example_function():
            """Example docstring"""
            return 'result'
        
        assert example_function.__name__ == 'example_function'
        assert example_function.__doc__ == 'Example docstring'
    
    def test_multiple_decorators_applied(self, mock_function):
        """Function can have retry decorator with other decorators"""
        mock_function.return_value = 'success'
        
        def uppercase_decorator(func):
            def wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                return result.upper() if isinstance(result, str) else result
            return wrapper
        
        @uppercase_decorator
        @retry_with_backoff(max_attempts=2, initial_delay=0.01)
        def test_func():
            return mock_function()
        
        result = test_func()
        
        assert result == 'SUCCESS'
        assert mock_function.call_count == 1


# ==================== TEST CUSTOM EXCEPTIONS ====================

class TestCustomExceptions:
    """Tests for custom exception classes"""
    
    def test_retryable_error_inheritance(self):
        """RetryableError is an Exception"""
        error = RetryableError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"
    
    def test_rate_limit_error_inheritance(self):
        """RateLimitError inherits from RetryableError"""
        error = RateLimitError("rate limited")
        assert isinstance(error, RetryableError)
        assert isinstance(error, Exception)
        assert str(error) == "rate limited"
    
    def test_network_error_inheritance(self):
        """NetworkError inherits from RetryableError"""
        error = NetworkError("network down")
        assert isinstance(error, RetryableError)
        assert isinstance(error, Exception)
        assert str(error) == "network down"
    
    def test_catch_retryable_errors(self, mock_function):
        """Can catch all retryable errors with base class"""
        mock_function.side_effect = [
            RateLimitError("rate limit"),
            NetworkError("network issue"),
            'success'
        ]
        
        @retry_with_backoff(
            max_attempts=3,
            initial_delay=0.01,
            exceptions=(RetryableError,)
        )
        def test_func():
            return mock_function()
        
        result = test_func()
        
        assert result == 'success'
        assert mock_function.call_count == 3


# ==================== INTEGRATION TESTS ====================

class TestRetryIntegration:
    """Integration tests simulating real-world usage"""
    
    @patch('backend.core.retry.time.sleep')
    def test_api_call_simulation(self, mock_sleep):
        """Simulate API call with intermittent failures"""
        call_count = 0
        
        @retry_with_backoff(
            max_attempts=5,
            initial_delay=0.1,
            backoff_factor=2.0,
            exceptions=(ConnectionError, TimeoutError, RateLimitError)
        )
        def fetch_api_data():
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                raise ConnectionError("Connection refused")
            elif call_count == 2:
                raise TimeoutError("Request timeout")
            elif call_count == 3:
                raise RateLimitError("Too many requests")
            else:
                return {"status": "ok", "data": [1, 2, 3]}
        
        result = fetch_api_data()
        
        assert result == {"status": "ok", "data": [1, 2, 3]}
        assert call_count == 4
        assert mock_sleep.call_count == 3
    
    def test_database_connection_retry(self, mock_logger):
        """Simulate database connection retry"""
        attempts = 0
        
        @retry_with_backoff(
            max_attempts=3,
            initial_delay=0.01,
            exceptions=(ConnectionError,)
        )
        def connect_to_db():
            nonlocal attempts
            attempts += 1
            
            if attempts < 3:
                raise ConnectionError(f"DB connection failed (attempt {attempts})")
            
            return "connected"
        
        result = connect_to_db()
        
        assert result == "connected"
        assert attempts == 3
        assert mock_logger.warning.call_count == 2
    
    def test_mixed_success_and_failure_patterns(self):
        """Test various success/failure patterns"""
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def pattern_1():  # Immediate success
            return "success"
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def pattern_2():  # Always fails
            raise ConnectionError("persistent error")
        
        call_count = 0
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def pattern_3():  # Success on last attempt
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temp error")
            return "success"
        
        # Test pattern 1
        assert pattern_1() == "success"
        
        # Test pattern 2
        with pytest.raises(ConnectionError, match="persistent error"):
            pattern_2()
        
        # Test pattern 3
        call_count = 0
        assert pattern_3() == "success"
        assert call_count == 3
