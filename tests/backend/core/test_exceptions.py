"""
Comprehensive tests for backend/core/exceptions.py

Coverage Target: 100%
Tests: Custom Bybit API exceptions and error mapping
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
    handle_bybit_error,
)


# ==================== BASE EXCEPTION TESTS ====================


class TestBybitAPIError:
    """Test base BybitAPIError exception"""

    def test_basic_message(self):
        """Test creating exception with just a message"""
        error = BybitAPIError("Something went wrong")
        assert error.message == "Something went wrong"
        assert error.ret_code is None
        assert error.ret_msg is None
        assert str(error) == "BybitAPIError: Something went wrong"

    def test_with_ret_code(self):
        """Test creating exception with ret_code"""
        error = BybitAPIError("API Error", ret_code=10001)
        assert error.message == "API Error"
        assert error.ret_code == 10001
        assert error.ret_msg is None
        assert str(error) == "BybitAPIError [10001]: API Error"

    def test_with_all_parameters(self):
        """Test creating exception with all parameters"""
        error = BybitAPIError(
            "Custom message",
            ret_code=10002,
            ret_msg="Original Bybit message"
        )
        assert error.message == "Custom message"
        assert error.ret_code == 10002
        assert error.ret_msg == "Original Bybit message"
        assert str(error) == "BybitAPIError [10002]: Custom message"

    def test_exception_inheritance(self):
        """Test that BybitAPIError inherits from Exception"""
        error = BybitAPIError("Test")
        assert isinstance(error, Exception)
        assert isinstance(error, BybitAPIError)

    def test_can_be_raised(self):
        """Test that exception can be raised and caught"""
        with pytest.raises(BybitAPIError) as exc_info:
            raise BybitAPIError("Test error", ret_code=999)
        
        assert exc_info.value.message == "Test error"
        assert exc_info.value.ret_code == 999

    def test_str_without_ret_code(self):
        """Test string representation without ret_code"""
        error = BybitAPIError("No code error")
        result = str(error)
        assert result == "BybitAPIError: No code error"
        assert "[" not in result  # No brackets when no ret_code


# ==================== SPECIFIC EXCEPTION TESTS ====================


class TestRateLimitError:
    """Test BybitRateLimitError exception"""

    def test_inheritance(self):
        """Test that RateLimitError inherits from BybitAPIError"""
        error = BybitRateLimitError("Rate limit exceeded")
        assert isinstance(error, BybitRateLimitError)
        assert isinstance(error, BybitAPIError)
        assert isinstance(error, Exception)

    def test_with_parameters(self):
        """Test creating with full parameters"""
        error = BybitRateLimitError("Too many requests", ret_code=10004)
        assert str(error) == "BybitAPIError [10004]: Too many requests"

    def test_can_be_raised(self):
        """Test raising the exception"""
        with pytest.raises(BybitRateLimitError):
            raise BybitRateLimitError("Rate limit")


class TestSymbolNotFoundError:
    """Test BybitSymbolNotFoundError exception"""

    def test_inheritance(self):
        """Test inheritance chain"""
        error = BybitSymbolNotFoundError("Symbol not found")
        assert isinstance(error, BybitSymbolNotFoundError)
        assert isinstance(error, BybitAPIError)

    def test_with_symbol_name(self):
        """Test with symbol information"""
        error = BybitSymbolNotFoundError("INVALIDBTC not found", ret_code=10016)
        assert "INVALIDBTC" in error.message


class TestInvalidIntervalError:
    """Test BybitInvalidIntervalError exception"""

    def test_inheritance(self):
        """Test inheritance"""
        error = BybitInvalidIntervalError("Invalid interval")
        assert isinstance(error, BybitInvalidIntervalError)
        assert isinstance(error, BybitAPIError)

    def test_interval_codes(self):
        """Test with different interval error codes"""
        error1 = BybitInvalidIntervalError("Bad interval", ret_code=10017)
        error2 = BybitInvalidIntervalError("Bad interval", ret_code=33004)
        assert error1.ret_code == 10017
        assert error2.ret_code == 33004


class TestInvalidParameterError:
    """Test BybitInvalidParameterError exception"""

    def test_inheritance(self):
        """Test inheritance"""
        error = BybitInvalidParameterError("Invalid param")
        assert isinstance(error, BybitInvalidParameterError)
        assert isinstance(error, BybitAPIError)


class TestAuthenticationError:
    """Test BybitAuthenticationError exception"""

    def test_inheritance(self):
        """Test inheritance"""
        error = BybitAuthenticationError("Auth failed")
        assert isinstance(error, BybitAuthenticationError)
        assert isinstance(error, BybitAPIError)

    def test_auth_codes(self):
        """Test with auth-related codes"""
        error1 = BybitAuthenticationError("Invalid API key", ret_code=10003)
        error2 = BybitAuthenticationError("Permission denied", ret_code=10005)
        assert error1.ret_code == 10003
        assert error2.ret_code == 10005


class TestConnectionError:
    """Test BybitConnectionError exception"""

    def test_inheritance(self):
        """Test inheritance"""
        error = BybitConnectionError("Connection failed")
        assert isinstance(error, BybitConnectionError)
        assert isinstance(error, BybitAPIError)


class TestTimeoutError:
    """Test BybitTimeoutError exception"""

    def test_inheritance(self):
        """Test inheritance"""
        error = BybitTimeoutError("Request timeout")
        assert isinstance(error, BybitTimeoutError)
        assert isinstance(error, BybitAPIError)


class TestDataError:
    """Test BybitDataError exception"""

    def test_inheritance(self):
        """Test inheritance"""
        error = BybitDataError("Invalid data")
        assert isinstance(error, BybitDataError)
        assert isinstance(error, BybitAPIError)


# ==================== ERROR MAPPING TESTS ====================


class TestErrorMapping:
    """Test BYBIT_ERROR_MAPPING dictionary"""

    def test_mapping_structure(self):
        """Test that mapping has correct structure"""
        assert isinstance(BYBIT_ERROR_MAPPING, dict)
        assert len(BYBIT_ERROR_MAPPING) > 0
        
        # Check all entries have tuple structure
        for code, (exc_class, msg) in BYBIT_ERROR_MAPPING.items():
            assert isinstance(code, int)
            assert issubclass(exc_class, BybitAPIError)
            assert isinstance(msg, str)

    def test_all_mapped_codes(self):
        """Test all known error codes are mapped"""
        expected_codes = {10001, 10002, 10003, 10004, 10005, 10006, 10016, 10017, 33004}
        mapped_codes = set(BYBIT_ERROR_MAPPING.keys())
        assert mapped_codes == expected_codes

    def test_parameter_error_codes(self):
        """Test parameter error codes map correctly"""
        assert BYBIT_ERROR_MAPPING[10001][0] == BybitInvalidParameterError
        assert BYBIT_ERROR_MAPPING[10002][0] == BybitInvalidParameterError

    def test_auth_error_codes(self):
        """Test authentication error codes"""
        assert BYBIT_ERROR_MAPPING[10003][0] == BybitAuthenticationError
        assert BYBIT_ERROR_MAPPING[10005][0] == BybitAuthenticationError

    def test_rate_limit_codes(self):
        """Test rate limit error codes"""
        assert BYBIT_ERROR_MAPPING[10004][0] == BybitRateLimitError
        assert BYBIT_ERROR_MAPPING[10006][0] == BybitRateLimitError

    def test_symbol_error_code(self):
        """Test symbol not found error code"""
        assert BYBIT_ERROR_MAPPING[10016][0] == BybitSymbolNotFoundError

    def test_interval_error_codes(self):
        """Test interval error codes"""
        assert BYBIT_ERROR_MAPPING[10017][0] == BybitInvalidIntervalError
        assert BYBIT_ERROR_MAPPING[33004][0] == BybitInvalidIntervalError


# ==================== HANDLE_BYBIT_ERROR TESTS ====================


class TestHandleBybitError:
    """Test handle_bybit_error function"""

    def test_known_error_code_parameter_error(self):
        """Test handling known parameter error code"""
        error = handle_bybit_error(10001, "Invalid parameter")
        assert isinstance(error, BybitInvalidParameterError)
        assert error.ret_code == 10001
        assert error.message == "Invalid parameter"
        assert error.ret_msg == "Invalid parameter"

    def test_known_error_code_rate_limit(self):
        """Test handling rate limit error"""
        error = handle_bybit_error(10004, "Too many requests")
        assert isinstance(error, BybitRateLimitError)
        assert error.ret_code == 10004
        assert error.message == "Too many requests"

    def test_known_error_code_auth(self):
        """Test handling authentication error"""
        error = handle_bybit_error(10003, "Invalid API key")
        assert isinstance(error, BybitAuthenticationError)
        assert error.ret_code == 10003

    def test_known_error_code_symbol_not_found(self):
        """Test handling symbol not found error"""
        error = handle_bybit_error(10016, "Symbol BTCUSDX not found")
        assert isinstance(error, BybitSymbolNotFoundError)
        assert error.ret_code == 10016

    def test_known_error_code_invalid_interval(self):
        """Test handling invalid interval error"""
        error = handle_bybit_error(10017, "Invalid interval 999")
        assert isinstance(error, BybitInvalidIntervalError)
        assert error.ret_code == 10017

    def test_unknown_error_code(self):
        """Test handling unknown error code"""
        error = handle_bybit_error(99999, "Unknown error")
        assert isinstance(error, BybitAPIError)
        assert not isinstance(error, BybitRateLimitError)  # Not a specific subclass
        assert error.ret_code == 99999
        assert "API error 99999" in error.message
        assert "Unknown error" in error.message

    def test_uses_default_message_when_ret_msg_empty(self):
        """Test that default message is used when ret_msg is empty"""
        error = handle_bybit_error(10001, "")
        assert error.message == "Parameter error"  # Default message from mapping

    def test_uses_default_message_when_ret_msg_none(self):
        """Test that default message is used when ret_msg is None"""
        error = handle_bybit_error(10004, None)
        assert error.message == "Rate limit exceeded"  # Default message

    def test_prefers_ret_msg_over_default(self):
        """Test that ret_msg is preferred over default message"""
        error = handle_bybit_error(10001, "Custom error message")
        assert error.message == "Custom error message"
        assert error.message != "Parameter error"  # Not the default

    def test_all_mapped_codes_work(self):
        """Test that all codes in mapping can be handled"""
        for code in BYBIT_ERROR_MAPPING.keys():
            error = handle_bybit_error(code, f"Error {code}")
            assert isinstance(error, BybitAPIError)
            assert error.ret_code == code

    def test_returns_exception_not_raises(self):
        """Test that function returns exception, doesn't raise it"""
        # Should not raise, should return
        error = handle_bybit_error(10001, "Test")
        assert isinstance(error, Exception)
        
        # But the returned exception can be raised
        with pytest.raises(BybitInvalidParameterError):
            raise error


# ==================== INTEGRATION TESTS ====================


class TestExceptionIntegration:
    """Integration tests for exception handling"""

    def test_catch_base_exception_catches_all(self):
        """Test that catching BybitAPIError catches all subtypes"""
        exceptions = [
            BybitRateLimitError("rate"),
            BybitSymbolNotFoundError("symbol"),
            BybitInvalidIntervalError("interval"),
            BybitAuthenticationError("auth"),
            BybitConnectionError("connection"),
            BybitTimeoutError("timeout"),
            BybitDataError("data"),
        ]
        
        for exc in exceptions:
            with pytest.raises(BybitAPIError):
                raise exc

    def test_catch_specific_exception(self):
        """Test catching specific exception type"""
        with pytest.raises(BybitRateLimitError):
            raise BybitRateLimitError("Rate limit")
        
        # Should not catch other types
        with pytest.raises(BybitSymbolNotFoundError):
            try:
                raise BybitSymbolNotFoundError("Symbol")
            except BybitRateLimitError:
                pytest.fail("Should not catch different exception type")

    def test_error_handler_integration(self):
        """Test full error handling flow"""
        # Simulate API error response
        ret_code = 10004
        ret_msg = "Rate limit exceeded, please retry after 60 seconds"
        
        # Handle error
        error = handle_bybit_error(ret_code, ret_msg)
        
        # Verify correct exception type
        assert isinstance(error, BybitRateLimitError)
        assert error.ret_code == 10004
        assert "Rate limit" in error.message
        
        # Can be raised and caught
        with pytest.raises(BybitRateLimitError) as exc_info:
            raise error
        
        assert exc_info.value.ret_code == 10004

    def test_error_message_formats(self):
        """Test various error message formats"""
        # With ret_code
        error1 = handle_bybit_error(10001, "Bad param")
        assert "[10001]" in str(error1)
        
        # Unknown code
        error2 = handle_bybit_error(88888, "Strange error")
        assert "[88888]" in str(error2)
        assert "API error 88888" in str(error2)

    def test_exception_chain(self):
        """Test exception can be part of exception chain"""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                # Re-raise as Bybit error with context
                raise BybitDataError("Data processing failed") from e
        except BybitDataError as exc:
            assert exc.message == "Data processing failed"
            assert isinstance(exc.__cause__, ValueError)
