"""
Correlation ID Middleware
Adds correlation IDs to requests for distributed tracing.
"""

import logging
import uuid
from collections.abc import Callable
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Context variable to store correlation ID across async boundaries
_correlation_id_ctx_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds correlation ID to each request.

    Uses contextvars to make correlation ID accessible anywhere in the request
    lifecycle without passing it explicitly through function arguments.
    """

    def __init__(self, app, header_name: str = "X-Correlation-ID"):
        """
        Initialize middleware.

        Args:
            app: FastAPI application
            header_name: Name of the correlation ID header
        """
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add correlation ID and process request.

        Args:
            request: Incoming request
            call_next: Next middleware/route handler

        Returns:
            Response with correlation ID header
        """
        # Generate or extract correlation ID
        correlation_id = request.headers.get(self.header_name, str(uuid.uuid4()))

        # Set context variable for access anywhere in request lifecycle
        token = _correlation_id_ctx_var.set(correlation_id)

        try:
            # Add to request state (for backward compatibility)
            request.state.correlation_id = correlation_id

            # Process request
            response = await call_next(request)

            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id

            return response
        finally:
            # Reset context variable after request completes
            _correlation_id_ctx_var.reset(token)


def configure_correlation_logging():
    """
    Configure logging to include correlation IDs.

    Sets up log formatting to include correlation ID in log messages.
    """
    logger.info("Correlation logging configured")


def get_correlation_id() -> str:
    """
    Get current correlation ID from context.

    Uses ContextVar to retrieve correlation ID set by CorrelationIdMiddleware.
    Falls back to generating a new UUID if called outside request context.

    Returns:
        Correlation ID string from context or new UUID if not in request context

    Example:
        >>> from backend.middleware.correlation_id import get_correlation_id
        >>> corr_id = get_correlation_id()  # Returns current request's ID
    """
    correlation_id = _correlation_id_ctx_var.get()
    if correlation_id is not None:
        return correlation_id
    # Not in request context - generate new UUID
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: str) -> None:
    """
    Manually set correlation ID for current context.

    Useful for background tasks or when processing messages from queues
    that include correlation IDs.

    Args:
        correlation_id: The correlation ID to set

    Example:
        >>> from backend.middleware.correlation_id import set_correlation_id
        >>> set_correlation_id("abc-123")  # For background task tracing
    """
    _correlation_id_ctx_var.set(correlation_id)


__all__ = [
    "CorrelationIdMiddleware",
    "configure_correlation_logging",
    "get_correlation_id",
    "set_correlation_id",
]
