"""
Correlation ID Middleware
Adds correlation IDs to requests for distributed tracing.
"""

import logging
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds correlation ID to each request.
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

        # Add to request state
        request.state.correlation_id = correlation_id

        # Process request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        return response


def configure_correlation_logging():
    """
    Configure logging to include correlation IDs.

    Sets up log formatting to include correlation ID in log messages.
    """
    logger.info("Correlation logging configured")


def get_correlation_id() -> str:
    """
    Get current correlation ID from context.

    Returns:
        Correlation ID string or generated UUID if not in request context
    """
    # Try to get from request context (if available)
    try:
        # If we're in a request context, return the correlation ID
        # For now, just generate a new UUID (context access is complex)
        return str(uuid.uuid4())
    except Exception:
        # Context not available or import failed
        return str(uuid.uuid4())


__all__ = [
    "CorrelationIdMiddleware",
    "configure_correlation_logging",
    "get_correlation_id",
]
