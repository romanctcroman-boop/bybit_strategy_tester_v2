"""
Timing Middleware - Log slow requests for performance monitoring.
"""

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("slow_requests")


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs slow requests.

    Configuration:
        - slow_threshold_ms: Requests taking longer than this are logged as WARNING (default: 500ms)
        - very_slow_threshold_ms: Requests taking longer than this are logged as ERROR (default: 2000ms)
        - extended_threshold_paths: Paths that use external APIs and need higher thresholds
    """

    def __init__(
        self,
        app,
        slow_threshold_ms: int = 500,
        very_slow_threshold_ms: int = 2000,
        excluded_paths: list | None = None,
        extended_threshold_paths: list | None = None,
    ):
        super().__init__(app)
        self.slow_threshold_ms = slow_threshold_ms
        self.very_slow_threshold_ms = very_slow_threshold_ms
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/favicon.ico"]
        # Paths that call external APIs - use 2x thresholds
        self.extended_threshold_paths = extended_threshold_paths or [
            "/api/v1/marketdata/bybit/klines",
            "/api/v1/agents/query",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip excluded paths
        if any(request.url.path.startswith(p) for p in self.excluded_paths):
            return await call_next(request)

        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Add timing header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Use extended thresholds for external API paths
        is_external_api = any(
            request.url.path.startswith(p) for p in self.extended_threshold_paths
        )
        slow_threshold = (
            self.slow_threshold_ms * 2 if is_external_api else self.slow_threshold_ms
        )
        very_slow_threshold = (
            self.very_slow_threshold_ms * 2
            if is_external_api
            else self.very_slow_threshold_ms
        )

        # Log slow requests
        if duration_ms >= very_slow_threshold:
            logger.error(
                "🐢 VERY SLOW REQUEST: %s %s took %.0fms (threshold: %dms)",
                request.method,
                request.url.path,
                duration_ms,
                very_slow_threshold,
            )
        elif duration_ms >= slow_threshold:
            logger.warning(
                "⚠️ Slow request: %s %s took %.0fms (threshold: %dms)",
                request.method,
                request.url.path,
                duration_ms,
                slow_threshold,
            )

        return response
