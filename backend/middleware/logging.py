"""
Logging middleware для FastAPI

Добавляет structured logging с контекстной информацией для debugging
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger
import json


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware для логирования HTTP requests с контекстом
    
    Добавляет к каждому request:
    - request_id (UUID)
    - Время выполнения
    - HTTP method + path
    - Status code
    - Client IP
    - Query parameters
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]
        
        # Add request_id to request state (available in route handlers)
        request.state.request_id = request_id
        
        # Extract context information
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)
        client_ip = request.client.host if request.client else "unknown"
        
        # Log request start
        logger.bind(
            request_id=request_id,
            method=method,
            path=path,
            client_ip=client_ip,
            query_params=query_params
        ).info(f"Request started: {method} {path}")
        
        # Measure execution time
        start_time = time.time()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log successful response
            logger.bind(
                request_id=request_id,
                method=method,
                path=path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2)
            ).info(
                f"Request completed: {method} {path} - "
                f"{response.status_code} ({duration:.3f}s)"
            )
            
            # Add request_id to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration = time.time() - start_time
            
            # Log error
            logger.bind(
                request_id=request_id,
                method=method,
                path=path,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration * 1000, 2)
            ).error(
                f"Request failed: {method} {path} - "
                f"{type(e).__name__}: {str(e)} ({duration:.3f}s)"
            )
            
            # Re-raise exception
            raise


def setup_structured_logging(app):
    """
    Настроить structured logging для приложения
    
    Usage:
        from backend.middleware.logging import setup_structured_logging
        
        app = FastAPI()
        setup_structured_logging(app)
    """
    # Add middleware
    app.add_middleware(RequestLoggingMiddleware)
    
    logger.info("Structured logging enabled")


# Helper function для добавления контекста в логи endpoint'ов
def log_with_context(request: Request, message: str, **extra):
    """
    Log message with request context
    
    Usage in route handler:
        from backend.middleware.logging import log_with_context
        
        @router.post("/backtest")
        async def run_backtest(request: Request, data: BacktestRequest):
            log_with_context(
                request,
                "Starting backtest",
                symbol=data.symbol,
                interval=data.interval
            )
    """
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    logger.bind(
        request_id=request_id,
        **extra
    ).info(message)


# Helper для логирования операций с данными
def log_data_operation(
    request_id: str,
    operation: str,
    symbol: str,
    interval: str,
    **extra
):
    """
    Log data loading operation with context
    
    Usage:
        log_data_operation(
            request_id="abc123",
            operation="load_candles",
            symbol="BTCUSDT",
            interval="15",
            candles_count=1000,
            duration_ms=1234
        )
    """
    logger.bind(
        request_id=request_id,
        operation=operation,
        symbol=symbol,
        interval=interval,
        **extra
    ).info(f"Data operation: {operation} - {symbol} {interval}")


# Helper для логирования backtests
def log_backtest_operation(
    request_id: str,
    operation: str,
    symbol: str,
    interval: str,
    strategy: str,
    **extra
):
    """
    Log backtest operation with context
    
    Usage:
        log_backtest_operation(
            request_id="abc123",
            operation="backtest_start",
            symbol="BTCUSDT",
            interval="15",
            strategy="RSI Mean Reversion",
            initial_capital=10000,
            leverage=1.0
        )
    """
    logger.bind(
        request_id=request_id,
        operation=operation,
        symbol=symbol,
        interval=interval,
        strategy=strategy,
        **extra
    ).info(f"Backtest operation: {operation} - {strategy} on {symbol} {interval}")
