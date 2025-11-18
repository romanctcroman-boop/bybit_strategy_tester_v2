"""
Comprehensive test suite for backend/api/error_handling.py
Target: 20% → 85% coverage (Quick Win: +2% total coverage)

Test Scenarios:
1. Custom exception classes (BacktestError, ValidationError, etc.)
2. Error response creation
3. Exception handlers
4. Parameter validation
5. Database operation decorator
6. Edge cases and error propagation
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from fastapi import Request, status
from fastapi.responses import JSONResponse

from backend.api.error_handling import (
    BacktestError,
    ValidationError,
    ResourceNotFoundError,
    DatabaseError,
    RateLimitError,
    DataFetchError,
    StrategyError,
    create_error_response,
    backtest_exception_handler,
    general_exception_handler,
    validate_backtest_params,
    handle_database_operation
)


class TestBacktestError:
    """Test BacktestError base exception"""
    
    def test_backtest_error_creation(self):
        """Test creating BacktestError with all parameters"""
        error = BacktestError(
            message="Test error",
            code="TEST_ERROR",
            details={"key": "value"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
        
        assert error.message == "Test error"
        assert error.code == "TEST_ERROR"
        assert error.details == {"key": "value"}
        assert error.status_code == 400
        assert str(error) == "Test error"
    
    def test_backtest_error_defaults(self):
        """Test BacktestError with default values"""
        error = BacktestError(message="Simple error")
        
        assert error.message == "Simple error"
        assert error.code == "BACKTEST_ERROR"
        assert error.details == {}
        assert error.status_code == 400
    
    def test_backtest_error_inheritance(self):
        """Test BacktestError is Exception"""
        error = BacktestError("test")
        assert isinstance(error, Exception)


class TestValidationError:
    """Test ValidationError exception"""
    
    def test_validation_error_with_field(self):
        """Test ValidationError with field name"""
        error = ValidationError(message="Invalid value", field="symbol")
        
        assert error.message == "Invalid value"
        assert error.code == "VALIDATION_ERROR"
        assert error.details["field"] == "symbol"
        assert error.status_code == 422
    
    def test_validation_error_without_field(self):
        """Test ValidationError without field"""
        error = ValidationError(message="General validation error")
        
        assert error.message == "General validation error"
        assert error.details["field"] is None
    
    def test_validation_error_with_details(self):
        """Test ValidationError with additional details"""
        error = ValidationError(
            message="Invalid range",
            field="date",
            details={"min": "2020-01-01", "max": "2025-12-31"}
        )
        
        assert error.details["field"] == "date"
        assert error.details["min"] == "2020-01-01"
        assert error.details["max"] == "2025-12-31"


class TestResourceNotFoundError:
    """Test ResourceNotFoundError exception"""
    
    def test_resource_not_found_string_id(self):
        """Test ResourceNotFoundError with string ID"""
        error = ResourceNotFoundError(resource="Backtest", resource_id="bt123")
        
        assert error.message == "Backtest not found"
        assert error.code == "RESOURCE_NOT_FOUND"
        assert error.details["resource"] == "Backtest"
        assert error.details["id"] == "bt123"
        assert error.status_code == 404
    
    def test_resource_not_found_int_id(self):
        """Test ResourceNotFoundError with integer ID"""
        error = ResourceNotFoundError(resource="Strategy", resource_id=42)
        
        assert error.details["id"] == 42


class TestDatabaseError:
    """Test DatabaseError exception"""
    
    def test_database_error_basic(self):
        """Test DatabaseError with operation"""
        error = DatabaseError(message="Connection failed", operation="connect")
        
        assert error.message == "Connection failed"
        assert error.code == "DATABASE_ERROR"
        assert error.details["operation"] == "connect"
        assert error.status_code == 500
    
    def test_database_error_with_details(self):
        """Test DatabaseError with additional details"""
        error = DatabaseError(
            message="Query timeout",
            operation="query",
            details={"table": "backtests", "timeout": 30}
        )
        
        assert error.details["operation"] == "query"
        assert error.details["table"] == "backtests"
        assert error.details["timeout"] == 30


class TestRateLimitError:
    """Test RateLimitError exception"""
    
    def test_rate_limit_error_default(self):
        """Test RateLimitError with default message"""
        error = RateLimitError()
        
        assert error.message == "Rate limit exceeded"
        assert error.code == "RATE_LIMIT_EXCEEDED"
        assert error.status_code == 429
    
    def test_rate_limit_error_with_retry_after(self):
        """Test RateLimitError with retry_after"""
        error = RateLimitError(message="Too many requests", retry_after=60)
        
        assert error.message == "Too many requests"
        assert error.details["retry_after"] == 60
    
    def test_rate_limit_error_without_retry_after(self):
        """Test RateLimitError without retry_after"""
        error = RateLimitError()
        
        assert error.details == {}


class TestDataFetchError:
    """Test DataFetchError exception"""
    
    def test_data_fetch_error_basic(self):
        """Test DataFetchError with source"""
        error = DataFetchError(message="API timeout", source="Bybit")
        
        assert error.message == "API timeout"
        assert error.code == "DATA_FETCH_ERROR"
        assert error.details["source"] == "Bybit"
        assert error.status_code == 502
    
    def test_data_fetch_error_with_details(self):
        """Test DataFetchError with additional details"""
        error = DataFetchError(
            message="Invalid response",
            source="Exchange",
            details={"endpoint": "/v5/klines", "status": 500}
        )
        
        assert error.details["source"] == "Exchange"
        assert error.details["endpoint"] == "/v5/klines"


class TestStrategyError:
    """Test StrategyError exception"""
    
    def test_strategy_error_basic(self):
        """Test StrategyError with strategy name"""
        error = StrategyError(message="Invalid signal", strategy_name="BollingerBands")
        
        assert error.message == "Invalid signal"
        assert error.code == "STRATEGY_ERROR"
        assert error.details["strategy"] == "BollingerBands"
        assert error.status_code == 400
    
    def test_strategy_error_with_details(self):
        """Test StrategyError with additional details"""
        error = StrategyError(
            message="Parameter out of range",
            strategy_name="RSI",
            details={"parameter": "period", "value": -5}
        )
        
        assert error.details["strategy"] == "RSI"
        assert error.details["parameter"] == "period"


class TestCreateErrorResponse:
    """Test create_error_response function"""
    
    @pytest.fixture
    def mock_request(self):
        """Create mock FastAPI request"""
        request = Mock(spec=Request)
        request.url.path = "/api/backtests"
        request.method = "POST"
        return request
    
    def test_create_error_response_backtest_error(self, mock_request):
        """Test error response for BacktestError"""
        error = BacktestError(
            message="Test failed",
            code="TEST_CODE",
            details={"reason": "invalid"}
        )
        
        response = create_error_response(error, mock_request)
        
        assert response["error"]["code"] == "TEST_CODE"
        assert response["error"]["message"] == "Test failed"
        assert response["error"]["details"]["reason"] == "invalid"
        assert response["error"]["path"] == "/api/backtests"
        assert "timestamp" in response["error"]
    
    def test_create_error_response_http_exception(self, mock_request):
        """Test error response for HTTPException"""
        from fastapi import HTTPException
        
        error = HTTPException(status_code=404, detail="Not found")
        response = create_error_response(error, mock_request)
        
        assert response["error"]["code"] == "HTTP_404"
        assert response["error"]["message"] == "Not found"
        assert response["error"]["path"] == "/api/backtests"
    
    def test_create_error_response_unexpected_error(self, mock_request):
        """Test error response for unexpected exception"""
        error = ValueError("Unexpected error")
        
        response = create_error_response(error, mock_request)
        
        assert response["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert response["error"]["message"] == "An unexpected error occurred"
        assert "error_id" in response["error"]
        assert response["error"]["path"] == "/api/backtests"
    
    def test_create_error_response_with_trace(self, mock_request):
        """Test error response includes trace when requested"""
        error = RuntimeError("Test error")
        
        response = create_error_response(error, mock_request, include_trace=True)
        
        assert "trace" in response["error"]
        # Note: trace format may vary, just ensure it exists
        assert response["error"]["trace"] is not None
    
    def test_create_error_response_no_trace_for_backtest_error(self, mock_request):
        """Test trace not included for BacktestError even if requested"""
        error = BacktestError("Test")
        
        response = create_error_response(error, mock_request, include_trace=True)
        
        assert "trace" not in response["error"]


class TestExceptionHandlers:
    """Test exception handler functions"""
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request"""
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.method = "GET"
        return request
    
    @pytest.mark.asyncio
    async def test_backtest_exception_handler(self, mock_request):
        """Test backtest_exception_handler"""
        error = ValidationError(message="Invalid input", field="test")
        
        response = await backtest_exception_handler(mock_request, error)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_general_exception_handler(self, mock_request):
        """Test general_exception_handler"""
        error = ValueError("Unexpected")
        
        response = await general_exception_handler(mock_request, error)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500


class TestValidateBacktestParams:
    """Test validate_backtest_params function"""
    
    def test_validate_valid_params(self):
        """Test validation passes for valid parameters"""
        params = {
            "strategy_id": "test_strategy",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T00:00:00Z",
            "initial_capital": 10000
        }
        
        # Should not raise
        validate_backtest_params(params)
    
    def test_validate_missing_required_field(self):
        """Test validation fails for missing required field"""
        params = {
            "symbol": "BTCUSDT",
            "timeframe": "1h"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_backtest_params(params)
        
        assert "required" in exc_info.value.message.lower()
        assert exc_info.value.details["field"] in ["strategy_id", "start_date", "end_date", "initial_capital"]
    
    def test_validate_negative_capital(self):
        """Test validation fails for negative capital"""
        params = {
            "strategy_id": "test",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T00:00:00Z",
            "initial_capital": -1000
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_backtest_params(params)
        
        assert "positive" in exc_info.value.message.lower()
        assert exc_info.value.details["field"] == "initial_capital"
    
    def test_validate_excessive_capital(self):
        """Test validation fails for excessive capital"""
        params = {
            "strategy_id": "test",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T00:00:00Z",
            "initial_capital": 2_000_000_000
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_backtest_params(params)
        
        assert "exceeds" in exc_info.value.message.lower()
        assert exc_info.value.details["max"] == 1_000_000_000
    
    def test_validate_start_after_end(self):
        """Test validation fails when start date after end date"""
        params = {
            "strategy_id": "test",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2024-12-31T00:00:00Z",
            "end_date": "2024-01-01T00:00:00Z",
            "initial_capital": 10000
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_backtest_params(params)
        
        assert "before" in exc_info.value.message.lower()
        assert exc_info.value.details["field"] == "date_range"
    
    def test_validate_excessive_date_range(self):
        """Test validation fails for date range > 5 years"""
        params = {
            "strategy_id": "test",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2020-01-01T00:00:00Z",
            "end_date": "2026-01-01T00:00:00Z",
            "initial_capital": 10000
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_backtest_params(params)
        
        assert "5 years" in exc_info.value.message
        assert exc_info.value.details["max_days"] == 365 * 5
    
    def test_validate_invalid_date_format(self):
        """Test validation fails for invalid date format"""
        params = {
            "strategy_id": "test",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "invalid-date",
            "end_date": "2024-12-31T00:00:00Z",
            "initial_capital": 10000
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_backtest_params(params)
        
        assert "date format" in exc_info.value.message.lower()
    
    def test_validate_invalid_leverage(self):
        """Test validation fails for invalid leverage"""
        params = {
            "strategy_id": "test",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T00:00:00Z",
            "initial_capital": 10000,
            "leverage": 150
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_backtest_params(params)
        
        assert "leverage" in exc_info.value.message.lower()
        assert exc_info.value.details["min"] == 1
        assert exc_info.value.details["max"] == 100
    
    def test_validate_invalid_commission(self):
        """Test validation fails for invalid commission"""
        params = {
            "strategy_id": "test",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T00:00:00Z",
            "initial_capital": 10000,
            "commission": 1.5
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_backtest_params(params)
        
        assert "commission" in exc_info.value.message.lower()
        assert exc_info.value.details["max"] == 1
    
    def test_validate_valid_optional_params(self):
        """Test validation passes with valid optional parameters"""
        params = {
            "strategy_id": "test",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T00:00:00Z",
            "initial_capital": 10000,
            "leverage": 10,
            "commission": 0.001
        }
        
        # Should not raise
        validate_backtest_params(params)


class TestHandleDatabaseOperation:
    """Test handle_database_operation decorator"""
    
    def test_sync_function_success(self):
        """Test decorator on successful sync function"""
        @handle_database_operation("test_operation")
        def test_func():
            return "success"
        
        result = test_func()
        assert result == "success"
    
    def test_sync_function_failure(self):
        """Test decorator on failing sync function"""
        @handle_database_operation("test_operation")
        def test_func():
            raise ValueError("DB error")
        
        with pytest.raises(DatabaseError) as exc_info:
            test_func()
        
        assert "test_operation" in exc_info.value.message
        assert exc_info.value.details["operation"] == "test_operation"
    
    @pytest.mark.asyncio
    async def test_async_function_success(self):
        """Test decorator on successful async function"""
        @handle_database_operation("async_operation")
        async def test_func():
            return "async_success"
        
        result = await test_func()
        assert result == "async_success"
    
    @pytest.mark.asyncio
    async def test_async_function_failure(self):
        """Test decorator on failing async function"""
        @handle_database_operation("async_operation")
        async def test_func():
            raise ConnectionError("Async DB error")
        
        with pytest.raises(DatabaseError) as exc_info:
            await test_func()
        
        assert "async_operation" in exc_info.value.message
        assert exc_info.value.details["operation"] == "async_operation"
    
    def test_decorator_preserves_function_args(self):
        """Test decorator passes through function arguments"""
        @handle_database_operation("get_user")
        def get_user(user_id: int, name: str):
            return f"User {user_id}: {name}"
        
        result = get_user(123, "Alice")
        assert result == "User 123: Alice"
    
    @pytest.mark.asyncio
    async def test_decorator_preserves_async_function_args(self):
        """Test decorator passes through async function arguments"""
        @handle_database_operation("get_data")
        async def get_data(key: str, default=None):
            return key if key else default
        
        result = await get_data("test_key")
        assert result == "test_key"


class TestErrorResponseTimestamp:
    """Test timestamp formatting in error responses"""
    
    @pytest.fixture
    def mock_request(self):
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.method = "GET"
        return request
    
    def test_timestamp_format(self, mock_request):
        """Test timestamp is in ISO format"""
        error = BacktestError("Test")
        response = create_error_response(error, mock_request)
        
        timestamp = response["error"]["timestamp"]
        
        # Should be valid ISO format
        datetime.fromisoformat(timestamp)
        
        # Should be recent (within last minute)
        timestamp_dt = datetime.fromisoformat(timestamp)
        now = datetime.utcnow()
        assert (now - timestamp_dt).total_seconds() < 60


class TestEdgeCases:
    """Test edge cases and error scenarios"""
    
    @pytest.fixture
    def mock_request(self):
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.method = "GET"
        return request
    
    def test_none_details_in_backtest_error(self):
        """Test BacktestError with None details"""
        error = BacktestError(message="Test", details=None)
        assert error.details == {}
    
    def test_empty_message_in_error(self):
        """Test error with empty message"""
        error = BacktestError(message="")
        assert error.message == ""
    
    def test_unicode_in_error_message(self):
        """Test error with Unicode characters"""
        error = BacktestError(message="Ошибка тестирования 测试错误")
        assert "Ошибка" in error.message
        assert "测试错误" in error.message
    
    def test_special_characters_in_error_code(self):
        """Test error with special characters in code"""
        error = BacktestError(message="Test", code="ERROR_CODE_123-ABC")
        assert error.code == "ERROR_CODE_123-ABC"
    
    def test_validate_params_with_none_values(self):
        """Test validation with None values for required fields"""
        params = {
            "strategy_id": None,
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T00:00:00Z",
            "initial_capital": 10000
        }
        
        with pytest.raises(ValidationError):
            validate_backtest_params(params)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
