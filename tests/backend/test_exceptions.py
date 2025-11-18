"""
Comprehensive test suite for backend/core/exceptions.py
Target: 76% → 95% coverage (Quick Win: +1% total coverage)

Test Scenarios:
1. BybitAPIError base class
2. All derived exception classes
3. BYBIT_ERROR_MAPPING completeness
4. handle_bybit_error() factory function
5. Error code handling edge cases
"""

import pytest
from backend.core.exceptions import (
    BybitAPIError,
    BybitRateLimitError,
    BybitSymbolNotFoundError,
    BybitInvalidIntervalError,
    BybitInvalidParameterError,
    BybitAuthenticationError,
    BybitConnectionError,
    BybitTimeoutError,
    BybitDataError,
    BYBIT_ERROR_MAPPING,
    handle_bybit_error
)


class TestBybitAPIError:
    """Test BybitAPIError base exception"""
    
    def test_base_error_with_all_params(self):
        """Test creating BybitAPIError with all parameters"""
        error = BybitAPIError(
            message="API error",
            ret_code=10001,
            ret_msg="Invalid parameter"
        )
        
        assert error.message == "API error"
        assert error.ret_code == 10001
        assert error.ret_msg == "Invalid parameter"
        # Actual __str__ format: "BybitAPIError [10001]: API error"
        str_repr = str(error)
        assert "API error" in str_repr
        assert "10001" in str_repr
    
    def test_base_error_minimal_params(self):
        """Test BybitAPIError with only message"""
        error = BybitAPIError(message="Simple error")
        
        assert error.message == "Simple error"
        assert error.ret_code is None
        assert error.ret_msg is None
        # Actual format: "BybitAPIError: Simple error"
        str_repr = str(error)
        assert "Simple error" in str_repr
    
    def test_base_error_with_ret_code_only(self):
        """Test BybitAPIError with ret_code but no ret_msg"""
        error = BybitAPIError(message="Error", ret_code=500)
        
        assert error.ret_code == 500
        assert error.ret_msg is None
    
    def test_base_error_with_ret_msg_only(self):
        """Test BybitAPIError with ret_msg but no ret_code"""
        error = BybitAPIError(message="Error", ret_msg="Server error")
        
        assert error.ret_code is None
        assert error.ret_msg == "Server error"
    
    def test_base_error_inheritance(self):
        """Test BybitAPIError inherits from Exception"""
        error = BybitAPIError("test")
        assert isinstance(error, Exception)
    
    def test_base_error_str_representation(self):
        """Test __str__ method formatting"""
        error = BybitAPIError(
            message="Test",
            ret_code=123,
            ret_msg="Details"
        )
        
        str_repr = str(error)
        assert "Test" in str_repr
        assert "123" in str_repr
        # Note: ret_msg may not be in str representation


class TestRateLimitError:
    """Test BybitRateLimitError exception"""
    
    def test_rate_limit_error_inheritance(self):
        """Test BybitRateLimitError inherits from BybitAPIError"""
        error = BybitRateLimitError("Rate limit")
        assert isinstance(error, BybitAPIError)
    
    def test_rate_limit_error_with_all_params(self):
        """Test BybitRateLimitError with all parameters"""
        error = BybitRateLimitError(
            message="Too many requests",
            ret_code=10006,
            ret_msg="Rate limit exceeded"
        )
        
        assert error.message == "Too many requests"
        assert error.ret_code == 10006
        assert error.ret_msg == "Rate limit exceeded"
    
    def test_rate_limit_error_simple(self):
        """Test BybitRateLimitError with simple message"""
        error = BybitRateLimitError("Rate limit hit")
        assert error.message == "Rate limit hit"


class TestSymbolNotFoundError:
    """Test BybitSymbolNotFoundError exception"""
    
    def test_symbol_not_found_inheritance(self):
        """Test BybitSymbolNotFoundError inherits from BybitAPIError"""
        error = BybitSymbolNotFoundError("Symbol error")
        assert isinstance(error, BybitAPIError)
    
    def test_symbol_not_found_with_params(self):
        """Test BybitSymbolNotFoundError with parameters"""
        error = BybitSymbolNotFoundError(
            message="Symbol BTCUSDT not found",
            ret_code=10001,
            ret_msg="symbol not found"
        )
        
        assert "BTCUSDT" in error.message
        assert error.ret_code == 10001


class TestInvalidIntervalError:
    """Test BybitInvalidIntervalError exception"""
    
    def test_invalid_interval_inheritance(self):
        """Test BybitInvalidIntervalError inherits from BybitAPIError"""
        error = BybitInvalidIntervalError("Invalid interval")
        assert isinstance(error, BybitAPIError)
    
    def test_invalid_interval_with_params(self):
        """Test BybitInvalidIntervalError with parameters"""
        error = BybitInvalidIntervalError(
            message="Interval 7d not supported",
            ret_code=10002,
            ret_msg="invalid interval"
        )
        
        assert "7d" in error.message
        assert error.ret_code == 10002


class TestInvalidParameterError:
    """Test BybitInvalidParameterError exception"""
    
    def test_invalid_parameter_inheritance(self):
        """Test BybitInvalidParameterError inherits from BybitAPIError"""
        error = BybitInvalidParameterError("Invalid param")
        assert isinstance(error, BybitAPIError)
    
    def test_invalid_parameter_with_params(self):
        """Test BybitInvalidParameterError with parameters"""
        error = BybitInvalidParameterError(
            message="Invalid limit parameter",
            ret_code=10003,
            ret_msg="limit must be between 1-1000"
        )
        
        assert "limit" in error.message
        assert error.ret_code == 10003


class TestAuthenticationError:
    """Test BybitAuthenticationError exception"""
    
    def test_authentication_error_inheritance(self):
        """Test BybitAuthenticationError inherits from BybitAPIError"""
        error = BybitAuthenticationError("Auth failed")
        assert isinstance(error, BybitAPIError)
    
    def test_authentication_error_with_params(self):
        """Test BybitAuthenticationError with parameters"""
        error = BybitAuthenticationError(
            message="Invalid API key",
            ret_code=10004,
            ret_msg="authentication failed"
        )
        
        assert "API key" in error.message
        assert error.ret_code == 10004


class TestConnectionError:
    """Test BybitConnectionError exception"""
    
    def test_connection_error_inheritance(self):
        """Test BybitConnectionError inherits from BybitAPIError"""
        error = BybitConnectionError("Connection failed")
        assert isinstance(error, BybitAPIError)
    
    def test_connection_error_with_params(self):
        """Test BybitConnectionError with parameters"""
        error = BybitConnectionError(
            message="Unable to connect to Bybit API",
            ret_code=10005,
            ret_msg="connection timeout"
        )
        
        assert "connect" in error.message.lower()
        assert error.ret_code == 10005


class TestTimeoutError:
    """Test BybitTimeoutError exception"""
    
    def test_timeout_error_inheritance(self):
        """Test BybitTimeoutError inherits from BybitAPIError"""
        error = BybitTimeoutError("Request timeout")
        assert isinstance(error, BybitAPIError)
    
    def test_timeout_error_with_params(self):
        """Test BybitTimeoutError with parameters"""
        error = BybitTimeoutError(
            message="Request timed out after 30s",
            ret_code=10007,
            ret_msg="timeout"
        )
        
        assert "30s" in error.message
        assert error.ret_code == 10007


class TestDataError:
    """Test BybitDataError exception"""
    
    def test_data_error_inheritance(self):
        """Test BybitDataError inherits from BybitAPIError"""
        error = BybitDataError("Data error")
        assert isinstance(error, BybitAPIError)
    
    def test_data_error_with_params(self):
        """Test BybitDataError with parameters"""
        error = BybitDataError(
            message="Invalid data format",
            ret_code=10008,
            ret_msg="malformed response"
        )
        
        assert "format" in error.message.lower()
        assert error.ret_code == 10008


class TestBybitErrorMapping:
    """Test BYBIT_ERROR_MAPPING dictionary"""
    
    def test_mapping_exists(self):
        """Test BYBIT_ERROR_MAPPING is defined"""
        assert BYBIT_ERROR_MAPPING is not None
        assert isinstance(BYBIT_ERROR_MAPPING, dict)
    
    def test_mapping_contains_rate_limit(self):
        """Test mapping contains rate limit error codes"""
        assert 10004 in BYBIT_ERROR_MAPPING or 10006 in BYBIT_ERROR_MAPPING
    
    def test_mapping_contains_authentication_error(self):
        """Test mapping contains authentication error codes"""
        assert 10003 in BYBIT_ERROR_MAPPING or 10005 in BYBIT_ERROR_MAPPING
    
    def test_mapping_contains_symbol_not_found(self):
        """Test mapping contains symbol not found error code"""
        assert 10016 in BYBIT_ERROR_MAPPING
    
    def test_mapping_contains_invalid_interval(self):
        """Test mapping contains invalid interval error codes"""
        assert 10017 in BYBIT_ERROR_MAPPING or 33004 in BYBIT_ERROR_MAPPING
    
    def test_mapping_all_values_are_tuples(self):
        """Test all mapped values are tuples of (exception_class, message)"""
        for error_code, value in BYBIT_ERROR_MAPPING.items():
            assert isinstance(value, tuple)
            assert len(value) == 2
            exception_class, message = value
            assert issubclass(exception_class, BybitAPIError)
            assert isinstance(message, str)


class TestHandleBybitError:
    """Test handle_bybit_error() factory function"""
    
    def test_handle_rate_limit_error(self):
        """Test factory creates BybitRateLimitError"""
        error = handle_bybit_error(
            ret_code=10004,
            ret_msg="Rate limit exceeded"
        )
        
        assert isinstance(error, BybitRateLimitError)
        assert error.ret_code == 10004
        assert error.ret_msg == "Rate limit exceeded"
    
    def test_handle_symbol_not_found_code(self):
        """Test factory creates BybitSymbolNotFoundError"""
        error = handle_bybit_error(
            ret_code=10016,
            ret_msg="symbol not found"
        )
        
        assert isinstance(error, BybitSymbolNotFoundError)
        assert error.ret_code == 10016
    
    def test_handle_invalid_interval_code(self):
        """Test factory creates BybitInvalidIntervalError"""
        error = handle_bybit_error(
            ret_code=10017,
            ret_msg="invalid interval"
        )
        
        assert isinstance(error, BybitInvalidIntervalError)
        assert error.ret_code == 10017
    
    def test_handle_authentication_error_code(self):
        """Test factory creates BybitAuthenticationError"""
        error = handle_bybit_error(
            ret_code=10003,
            ret_msg="authentication failed"
        )
        
        assert isinstance(error, BybitAuthenticationError)
        assert error.ret_code == 10003
    
    def test_handle_unknown_error_code(self):
        """Test factory creates generic BybitAPIError for unknown code"""
        error = handle_bybit_error(
            ret_code=99999,
            ret_msg="Unknown error"
        )
        
        assert isinstance(error, BybitAPIError)
        assert type(error) == BybitAPIError  # Not a derived class
        assert error.ret_code == 99999
        assert error.ret_msg == "Unknown error"
    
    def test_handle_error_uses_ret_msg(self):
        """Test factory uses ret_msg from API"""
        error = handle_bybit_error(
            ret_code=10001,
            ret_msg="Custom error message from API"
        )
        
        assert "Custom error message" in error.message
    
    def test_handle_error_falls_back_to_default(self):
        """Test factory uses default message when ret_msg is empty"""
        error = handle_bybit_error(
            ret_code=10001,
            ret_msg=""
        )
        
        assert isinstance(error, BybitInvalidParameterError)
        # Should use default message from mapping
        assert len(error.message) > 0


class TestExceptionStringRepresentation:
    """Test string representations of all exceptions"""
    
    def test_all_exceptions_have_str_method(self):
        """Test all exception classes have __str__ method"""
        exception_classes = [
            BybitAPIError,
            BybitRateLimitError,
            BybitSymbolNotFoundError,
            BybitInvalidIntervalError,
            BybitInvalidParameterError,
            BybitAuthenticationError,
            BybitConnectionError,
            BybitTimeoutError,
            BybitDataError
        ]
        
        for exc_class in exception_classes:
            error = exc_class("test message", ret_code=123, ret_msg="details")
            str_repr = str(error)
            
            # Just verify str() doesn't raise and returns a string
            assert isinstance(str_repr, str)
            assert len(str_repr) > 0


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_error_with_empty_message(self):
        """Test exception with empty message"""
        error = BybitAPIError(message="")
        assert error.message == ""
    
    def test_error_with_unicode_message(self):
        """Test exception with Unicode characters"""
        error = BybitAPIError(
            message="错误消息 Сообщение об ошибке",
            ret_code=10001,
            ret_msg="Unicode ret_msg: 日本語"
        )
        
        assert "错误消息" in error.message
        assert "Сообщение" in error.message
        assert "日本語" in error.ret_msg
    
    def test_error_with_very_long_message(self):
        """Test exception with very long message"""
        long_message = "A" * 10000
        error = BybitAPIError(message=long_message)
        
        assert len(error.message) == 10000
        assert error.message == long_message
    
    def test_handle_error_with_negative_ret_code(self):
        """Test factory with negative error code"""
        error = handle_bybit_error(
            ret_code=-1,
            ret_msg="Negative code"
        )
        
        assert isinstance(error, BybitAPIError)
        assert error.ret_code == -1
    
    def test_handle_error_with_zero_ret_code(self):
        """Test factory with zero error code"""
        error = handle_bybit_error(
            ret_code=0,
            ret_msg="Zero code"
        )
        
        assert isinstance(error, BybitAPIError)
        assert error.ret_code == 0
    
    def test_multiple_errors_independence(self):
        """Test multiple error instances don't interfere"""
        error1 = BybitAPIError("Error 1", ret_code=1, ret_msg="msg1")
        error2 = BybitAPIError("Error 2", ret_code=2, ret_msg="msg2")
        
        assert error1.ret_code != error2.ret_code
        assert error1.ret_msg != error2.ret_msg
        assert error1.message != error2.message


class TestExceptionRaising:
    """Test that exceptions can be raised properly"""
    
    def test_raise_bybit_api_error(self):
        """Test raising BybitAPIError"""
        with pytest.raises(BybitAPIError) as exc_info:
            raise BybitAPIError("Test error", ret_code=123)
        
        assert exc_info.value.ret_code == 123
    
    def test_raise_rate_limit_error(self):
        """Test raising BybitRateLimitError"""
        with pytest.raises(BybitRateLimitError):
            raise BybitRateLimitError("Rate limit")
    
    def test_catch_derived_as_base(self):
        """Test catching derived exception as base type"""
        with pytest.raises(BybitAPIError):
            raise BybitSymbolNotFoundError("Symbol error")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
