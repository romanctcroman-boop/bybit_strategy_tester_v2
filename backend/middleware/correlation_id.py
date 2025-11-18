"""Correlation ID Middleware

Injects X-Request-ID into all requests and propagates through logs/responses.
Critical for distributed tracing in multi-agent communication.

Flow:
1. Extract X-Request-ID from request header (or generate UUID)
2. Store in request.state for access by handlers
3. Inject into all log records via contextvars
4. Add to response headers

Integration with agents:
- UnifiedAgentInterface can access via request context
- Agent-to-agent calls propagate correlation ID
- Enables end-to-end tracing across DeepSeek/Perplexity calls
"""
from __future__ import annotations

import contextvars
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

# Context var for correlation ID (thread-safe)
correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


def get_correlation_id() -> str | None:
    """Get current correlation ID from context"""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID in context"""
    correlation_id_var.set(correlation_id)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to inject and propagate correlation IDs"""

    def __init__(self, app, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract or generate correlation ID
        correlation_id = request.headers.get(self.header_name)
        has_correlation_id = correlation_id is not None
        
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Store in request state for access by handlers
        request.state.correlation_id = correlation_id

        # Set in context var for log propagation
        set_correlation_id(correlation_id)
        
        # Task 13: Track correlation ID metrics
        try:
            from backend.api.app import CORRELATION_ID_REQUESTS
            CORRELATION_ID_REQUESTS.labels(
                has_correlation_id=str(has_correlation_id).lower()
            ).inc()
        except Exception:
            pass  # Metrics not critical

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Ensure correlation ID in error responses
            logger.error(
                f"Request failed with correlation_id={correlation_id}: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
        finally:
            # Clear context after request
            correlation_id_var.set(None)

        # Add correlation ID to response headers
        response.headers[self.header_name] = correlation_id

        return response


# Loguru filter to inject correlation ID into log records
def correlation_id_filter(record):
    """Inject correlation ID into log record if available"""
    correlation_id = get_correlation_id()
    record["extra"]["correlation_id"] = correlation_id or "N/A"
    return True


def configure_correlation_logging():
    """Configure loguru to include correlation IDs in all logs
    
    Call this during app startup to enable correlation ID logging.
    Format: [correlation_id={id}] message
    """
    # Remove default handler
    logger.remove()
    
    # Add new handler with correlation ID
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>correlation_id={extra[correlation_id]}</cyan> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        filter=correlation_id_filter,
        level="DEBUG"
    )


__all__ = [
    "CorrelationIdMiddleware",
    "get_correlation_id",
    "set_correlation_id",
    "configure_correlation_logging",
]
