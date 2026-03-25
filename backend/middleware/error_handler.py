"""
Centralized Error Handler Middleware.

Catches all unhandled exceptions and returns structured JSON error responses.
Features:
- Consistent error response format
- Hides internal errors in production
- Includes correlation ID for tracing
- Logs errors with context
"""

import os
import traceback
from datetime import UTC, datetime

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Centralized error handling middleware.

    Features:
    - Catches all unhandled exceptions
    - Returns structured JSON error responses
    - Logs errors with context
    - Hides internal errors in production
    - Includes correlation ID for tracing
    """

    def __init__(
        self,
        app,
        debug: bool | None = None,
        include_traceback: bool | None = None,
    ):
        super().__init__(app)
        env_debug = os.environ.get("DEBUG", "").lower() in ("true", "1", "yes")
        self.debug = debug if debug is not None else env_debug
        self.include_traceback = include_traceback if include_traceback is not None else self.debug

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            response = await call_next(request)
            return response

        except Exception as exc:
            # Get correlation ID if available
            correlation_id = getattr(request.state, "correlation_id", None)

            # Log error with context
            error_context = {
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            }

            logger.error(
                f"Unhandled exception on {request.method} {request.url.path}: {exc}",
                exc_info=True,
                **error_context,
            )

            # Determine status code
            status_code = getattr(exc, "status_code", 500)

            # Build error response
            error_body: dict = {
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc) if self.debug else "Internal Server Error",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            }

            # Add correlation ID if available
            if correlation_id:
                error_body["error"]["correlation_id"] = correlation_id

            # Add traceback in debug mode
            if self.include_traceback:
                error_body["error"]["traceback"] = traceback.format_exc()

            headers = {"X-Error-Type": type(exc).__name__}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            return JSONResponse(
                status_code=status_code,
                content=error_body,
                headers=headers,
            )
