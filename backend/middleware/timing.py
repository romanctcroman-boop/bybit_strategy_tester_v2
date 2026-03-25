"""
Timing Middleware - Log slow requests for performance monitoring.
"""

import logging
import time
from collections.abc import Callable

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
        - extended_threshold_paths: Paths that use external APIs - use 2x thresholds
        - long_running_paths: Paths that may block on Bybit (e.g. instruments/symbols) - use 6x very_slow
    """

    def __init__(
        self,
        app,
        slow_threshold_ms: int = 500,
        very_slow_threshold_ms: int = 2000,
        excluded_paths: list | None = None,
        extended_threshold_paths: list | None = None,
        long_running_paths: list | None = None,
    ):
        super().__init__(app)
        self.slow_threshold_ms = slow_threshold_ms
        self.very_slow_threshold_ms = very_slow_threshold_ms
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/favicon.ico"]
        self.extended_threshold_paths = extended_threshold_paths or [
            "/api/v1/marketdata/bybit/klines",
            "/api/v1/agents/query",
        ]
        # Paths that may block on Bybit (instruments, symbols-list) - ERROR only above 8x very_slow (~16s)
        self.long_running_paths = long_running_paths or []

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip excluded paths
        if any(request.url.path.startswith(p) for p in self.excluded_paths):
            return await call_next(request)

        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Add timing header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        path = request.url.path
        is_long_running = any(path.startswith(p) for p in self.long_running_paths)
        is_external_api = any(path.startswith(p) for p in self.extended_threshold_paths)

        if is_long_running:
            # Bybit instruments/symbols: WARNING up to 8x very_slow (~16s), ERROR above
            slow_threshold = self.slow_threshold_ms * 2
            very_slow_threshold = self.very_slow_threshold_ms * 8
        elif is_external_api:
            slow_threshold = self.slow_threshold_ms * 2
            very_slow_threshold = self.very_slow_threshold_ms * 2
        else:
            slow_threshold = self.slow_threshold_ms
            very_slow_threshold = self.very_slow_threshold_ms

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
