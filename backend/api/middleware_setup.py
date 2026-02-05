"""
Middleware configuration module for FastAPI application.

Extracted from app.py for better maintainability.
Configures all middleware in the correct order (order matters in FastAPI).

Middleware execution order (request flow):
1. RateLimitMiddleware - First line of defense
2. TimingMiddleware - Performance monitoring
3. GZipMiddleware - Compression
4. OpenTelemetryMiddleware - Distributed tracing
5. CorrelationIdMiddleware - Request tracking
6. CacheHeadersMiddleware - HTTP caching
7. SecurityHeadersMiddleware - Security hardening
8. CORSMiddleware - Cross-origin requests
9. UnifiedMcpMiddleware - MCP-specific handling
"""

import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from backend.middleware.cache_headers import CacheHeadersMiddleware
from backend.middleware.correlation_id import CorrelationIdMiddleware
from backend.middleware.opentelemetry_tracing import OpenTelemetryMiddleware
from backend.middleware.rate_limiter import RateLimitMiddleware
from backend.middleware.security_headers import SecurityHeadersMiddleware
from backend.middleware.timing import TimingMiddleware

logger = logging.getLogger("uvicorn.error")


def configure_middleware(app: FastAPI) -> None:
    """
    Configure all middleware for the FastAPI application.

    Order matters! Middleware are executed in reverse order of registration
    for requests, and in registration order for responses.

    Args:
        app: FastAPI application instance
    """
    # ========================================================================
    # PHASE 1: Rate Limiting (MUST BE FIRST!)
    # Uses Token Bucket algorithm with per-IP tracking.
    # Limits configured via environment variables:
    #   - RATE_LIMIT_ENABLED (default: true)
    #   - RATE_LIMIT_DEFAULT_CALLS (default: 100)
    #   - RATE_LIMIT_DEFAULT_PERIOD (default: 60s)
    #   - RATE_LIMIT_AGENT_CALLS (default: 30) - for AI agent endpoints
    #   - RATE_LIMIT_MARKET_CALLS (default: 500) - for market data endpoints
    # See backend/middleware/rate_limiter.py for details.
    # ========================================================================
    # NOTE: RateLimitMiddleware reads config from env vars, not from constructor
    app.add_middleware(RateLimitMiddleware)

    # ========================================================================
    # Slow Request Timing Middleware (performance monitoring)
    # - extended_threshold_paths: 2x thresholds (WARNING/ERROR at 1s/4s)
    # - long_running_paths: Bybit instruments/symbols, 8x very_slow (~16s) before ERROR
    # ========================================================================
    app.add_middleware(
        TimingMiddleware,
        slow_threshold_ms=500,  # Warn for requests > 500ms
        very_slow_threshold_ms=2000,  # Error for requests > 2s
        excluded_paths=["/health", "/metrics", "/favicon.ico", "/api/v1/health"],
        extended_threshold_paths=[
            "/api/v1/marketdata/bybit/klines",
            "/api/v1/agents/query",
        ],
        long_running_paths=[
            "/api/v1/marketdata/symbols",  # instrument-info, symbols-list
            "/api/v1/refresh-tickers",
        ],
    )

    # ========================================================================
    # Gzip Compression Middleware (reduce response sizes)
    # ========================================================================
    app.add_middleware(GZipMiddleware, minimum_size=1000)  # Compress responses > 1KB

    # ========================================================================
    # OpenTelemetry Tracing Middleware (distributed tracing)
    # ========================================================================
    app.add_middleware(
        OpenTelemetryMiddleware,
        service_name="bybit-strategy-tester",
        excluded_paths=["/health", "/metrics", "/favicon.ico", "/api/v1/health"],
    )

    # ========================================================================
    # Correlation ID Middleware (for distributed tracing)
    # ========================================================================
    app.add_middleware(CorrelationIdMiddleware, header_name="X-Request-ID")

    # ========================================================================
    # HTTP Cache Headers Middleware
    # ========================================================================
    app.add_middleware(
        CacheHeadersMiddleware,
        max_age=60,
        enable_etag=True,
        enable_last_modified=True,
    )

    # ========================================================================
    # Security Headers Middleware (basic hardening + CSP)
    # ========================================================================
    app.add_middleware(SecurityHeadersMiddleware)

    # ========================================================================
    # CORS Middleware (Production-ready with environment configuration)
    # ========================================================================
    cors_config = _get_cors_config()
    logger.info(
        f"CORS configured: origins={cors_config['origins'][:3]}{'...' if len(cors_config['origins']) > 3 else ''}"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config["origins"],
        allow_credentials=cors_config["allow_credentials"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-Request-ID",
        ],
    )

    # ========================================================================
    # MCP Unified Middleware (AFTER CORS for proper override)
    # ========================================================================
    _configure_mcp_middleware(app)

    logger.info("✅ All middleware configured successfully")


def _get_cors_config() -> dict:
    """
    Get CORS configuration from environment variables.

    Returns:
        dict with 'origins' and 'allow_credentials' keys
    """
    cors_origins_str = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        # Default: allow common development origins
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
    )
    cors_allow_all = os.getenv("CORS_ALLOW_ALL", "false").lower() in ("true", "1", "yes")

    if cors_allow_all:
        # Development mode: allow all origins
        return {
            "origins": ["*"],
            "allow_credentials": False,  # Cannot use credentials with wildcard
        }
    else:
        # Production mode: use specific origins
        origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()]
        return {
            "origins": origins,
            "allow_credentials": True,
        }


def _configure_mcp_middleware(app: FastAPI) -> None:
    """
    Configure MCP-specific middleware.

    Args:
        app: FastAPI application instance
    """
    from backend.api.mcp_middleware import UnifiedMcpMiddleware

    mcp_require_auth = os.getenv("MCP_REQUIRE_AUTH", "false").lower() in ("true", "1", "yes")
    mcp_auth_token = os.getenv("MCP_API_KEY", "")  # Changed from MCP_AUTH_TOKEN
    mcp_allowed_origins_str = os.getenv("MCP_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    mcp_allowed_origins = [o.strip() for o in mcp_allowed_origins_str.split(",") if o.strip()]

    # Perplexity recommendation: Enable auth in staging by default
    staging_or_prod = os.getenv("ENVIRONMENT", "development") in ("staging", "production")
    if staging_or_prod and not mcp_require_auth:
        logger.warning("⚠️ MCP auth disabled in staging/production! Set MCP_REQUIRE_AUTH=true and MCP_API_KEY.")

    app.add_middleware(
        UnifiedMcpMiddleware,
        require_auth=mcp_require_auth,
        auth_token=mcp_auth_token,
        allowed_origins=mcp_allowed_origins,
    )


def create_prometheus_metrics_middleware(app: FastAPI) -> None:
    """
    Create and attach Prometheus metrics middleware.

    This is a separate function because it uses @app.middleware decorator
    which requires the app instance.

    Args:
        app: FastAPI application instance
    """

    @app.middleware("http")
    async def prometheus_metrics_middleware(request: Request, call_next):
        """Record per-request metrics for Prometheus collector.

        Uses the Phase 5 monitoring collector (separate registry) to increment
        api_requests_total and observe api_request_duration_seconds.
        """
        import time as _time

        start = _time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = _time.perf_counter() - start
            try:
                from backend.monitoring.prometheus_metrics import get_metrics_collector

                collector = get_metrics_collector()
                collector.record_api_request(
                    endpoint=request.url.path,
                    method=request.method,
                    status=status_code,
                    duration_seconds=duration,
                )
            except Exception as exc:  # pragma: no cover - best-effort metrics
                logging.getLogger("backend.api.app").debug("Prometheus metrics middleware skipped: %s", exc)
