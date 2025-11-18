"""
Enhanced Error Handling Module for Backend API

Provides:
- Custom exception classes
- Detailed error responses
- Error logging with context
- User-friendly error messages
"""
import traceback
from datetime import datetime, timezone
from backend.utils.time import utc_now
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from loguru import logger


class BacktestError(Exception):
    """Base exception for backtest-related errors"""
    
    def __init__(
        self,
        message: str,
        code: str = "BACKTEST_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = status.HTTP_400_BAD_REQUEST
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(message)


class ValidationError(BacktestError):
    """Validation error for input parameters"""
    
    def __init__(self, message: str, field: str | None = None, details: dict | None = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={"field": field, **(details or {})},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )


class ResourceNotFoundError(BacktestError):
    """Resource not found error"""
    
    def __init__(self, resource: str, resource_id: Any):
        super().__init__(
            message=f"{resource} not found",
            code="RESOURCE_NOT_FOUND",
            details={"resource": resource, "id": resource_id},
            status_code=status.HTTP_404_NOT_FOUND
        )


class DatabaseError(BacktestError):
    """Database operation error"""
    
    def __init__(self, message: str, operation: str, details: dict | None = None):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            details={"operation": operation, **(details or {})},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class RateLimitError(BacktestError):
    """Rate limit exceeded error"""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int | None = None):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after} if retry_after else {},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )


class DataFetchError(BacktestError):
    """External data fetch error"""
    
    def __init__(self, message: str, source: str, details: dict | None = None):
        super().__init__(
            message=message,
            code="DATA_FETCH_ERROR",
            details={"source": source, **(details or {})},
            status_code=status.HTTP_502_BAD_GATEWAY
        )


class StrategyError(BacktestError):
    """Strategy execution error"""
    
    def __init__(self, message: str, strategy_name: str, details: dict | None = None):
        super().__init__(
            message=message,
            code="STRATEGY_ERROR",
            details={"strategy": strategy_name, **(details or {})},
            status_code=status.HTTP_400_BAD_REQUEST
        )


def create_error_response(
    error: Exception,
    request: Request,
    include_trace: bool = False
) -> dict[str, Any]:
    """
    Create standardized error response
    
    Args:
        error: Exception instance
        request: FastAPI request object
        include_trace: Whether to include stack trace (dev mode only)
    
    Returns:
        Error response dictionary
    """
    # Use UTC-aware timestamp with explicit offset
    timestamp = utc_now().isoformat()
    
    if isinstance(error, BacktestError):
        response = {
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
                "timestamp": timestamp,
                "path": str(request.url.path)
            }
        }
        
        # Log error with context
        logger.error(
            f"API Error: {error.code} - {error.message}",
            extra={
                "code": error.code,
                "path": request.url.path,
                "method": request.method,
                "details": error.details
            }
        )
        
    elif isinstance(error, HTTPException):
        response = {
            "error": {
                "code": f"HTTP_{error.status_code}",
                "message": error.detail,
                "timestamp": timestamp,
                "path": str(request.url.path)
            }
        }
        
        logger.warning(
            f"HTTP Exception: {error.status_code} - {error.detail}",
            extra={"path": request.url.path, "method": request.method}
        )
        
    else:
        # Unexpected error
        error_id = f"ERR_{int(utc_now().timestamp())}"
        response = {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "error_id": error_id,
                "timestamp": timestamp,
                "path": str(request.url.path)
            }
        }
        
        # Log with full traceback
        logger.exception(
            f"Unexpected error {error_id}: {str(error)}",
            extra={
                "error_id": error_id,
                "path": request.url.path,
                "method": request.method,
                "error_type": type(error).__name__
            }
        )
    
    # Include stack trace in development
    if include_trace and not isinstance(error, (BacktestError, HTTPException)):
        response["error"]["trace"] = traceback.format_exc()
    
    return response


async def backtest_exception_handler(request: Request, exc: BacktestError) -> JSONResponse:
    """Exception handler for BacktestError"""
    response = create_error_response(exc, request)
    return JSONResponse(
        status_code=exc.status_code,
        content=response
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """General exception handler for unhandled errors"""
    response = create_error_response(exc, request)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response
    )


def validate_backtest_params(payload: dict[str, Any]) -> None:
    """
    Validate backtest parameters with detailed error messages
    
    Raises:
        ValidationError: If validation fails
    """
    # Required fields
    required = ["strategy_id", "symbol", "timeframe", "start_date", "end_date", "initial_capital"]
    for field in required:
        if field not in payload or payload[field] is None:
            raise ValidationError(
                message=f"Field '{field}' is required",
                field=field
            )
    
    # Validate capital
    if payload["initial_capital"] <= 0:
        raise ValidationError(
            message="Initial capital must be positive",
            field="initial_capital",
            details={"value": payload["initial_capital"]}
        )
    
    if payload["initial_capital"] > 1_000_000_000:
        raise ValidationError(
            message="Initial capital exceeds maximum allowed (1B)",
            field="initial_capital",
            details={"value": payload["initial_capital"], "max": 1_000_000_000}
        )
    
    # Validate dates
    from datetime import datetime
    try:
        start = datetime.fromisoformat(payload["start_date"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(payload["end_date"].replace("Z", "+00:00"))
        
        if start >= end:
            raise ValidationError(
                message="Start date must be before end date",
                field="date_range",
                details={"start_date": payload["start_date"], "end_date": payload["end_date"]}
            )
        
        # Max 5 years range
        if (end - start).days > 365 * 5:
            raise ValidationError(
                message="Date range cannot exceed 5 years",
                field="date_range",
                details={"days": (end - start).days, "max_days": 365 * 5}
            )
            
    except ValueError as e:
        raise ValidationError(
            message=f"Invalid date format: {str(e)}",
            field="date_format",
            details={"start_date": payload["start_date"], "end_date": payload["end_date"]}
        )
    
    # Validate leverage
    if "leverage" in payload:
        if not 1 <= payload["leverage"] <= 100:
            raise ValidationError(
                message="Leverage must be between 1 and 100",
                field="leverage",
                details={"value": payload["leverage"], "min": 1, "max": 100}
            )
    
    # Validate commission
    if "commission" in payload:
        if not 0 <= payload["commission"] <= 1:
            raise ValidationError(
                message="Commission must be between 0 and 1 (0-100%)",
                field="commission",
                details={"value": payload["commission"], "min": 0, "max": 1}
            )


def handle_database_operation(operation: str):
    """
    Decorator for database operations with error handling
    
    Usage:
        @handle_database_operation("get_backtest")
        def get_backtest(backtest_id: int):
            ...
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.exception(f"Database operation '{operation}' failed: {str(e)}")
                raise DatabaseError(
                    message=f"Failed to {operation}",
                    operation=operation,
                    details={"error": str(e)}
                )
        
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception(f"Database operation '{operation}' failed: {str(e)}")
                raise DatabaseError(
                    message=f"Failed to {operation}",
                    operation=operation,
                    details={"error": str(e)}
                )
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
