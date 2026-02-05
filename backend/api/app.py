import logging
import sys
from pathlib import Path

# Ensure UTF-8 streams on Windows to avoid emoji-related encoding crashes
try:  # pragma: no cover - platform-specific safeguard
    if sys.platform.startswith("win"):
        for _stream in (sys.stdout, sys.stderr):
            if hasattr(_stream, "reconfigure"):
                _stream.reconfigure(encoding="utf-8", errors="replace")
except Exception as _e:  # Intentional: optional; see docs/DECISIONS.md ADR-003
    logging.getLogger(__name__).debug("UTF-8 stream reconfigure skipped: %s", _e)

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

# Load .env file FIRST before any other imports that might need env vars
_project_root = Path(__file__).resolve().parent.parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

# Add mcp-server to Python path BEFORE imports (fixes orchestrator.api.metrics import in metrics_router)
_mcp_server_path = _project_root / "mcp-server"
if _mcp_server_path.exists() and str(_mcp_server_path) not in sys.path:
    sys.path.insert(0, str(_mcp_server_path))


from backend.api import (
    agent_to_agent_api,  # ✅ Week 5 Day 5: AI Agent Communication (DeepSeek + Perplexity)
    orchestrator,  # ✅ Week 6: Orchestrator Dashboard (MOVED BEFORE metrics to avoid circular import)
)

# Import lifespan from dedicated module (extracted for maintainability)
from backend.api.lifespan import lifespan

# Import middleware configuration (extracted for maintainability)
from backend.api.middleware_setup import (
    configure_middleware,
    create_prometheus_metrics_middleware,
)
from backend.api.routers import active_deals as active_deals_router
from backend.api.routers import (
    admin,
    backtests,
    inference,
    marketdata,
    optimizations,
    strategies,
)
from backend.api.routers import (
    advanced_backtesting as advanced_backtesting_router,
)
from backend.api.routers import agents as agents_router
from backend.api.routers import ai as ai_router
from backend.api.routers import (
    ai_strategy_generator as ai_strategy_generator_router,
)
from backend.api.routers import alerts as alerts_router
from backend.api.routers import bots as bots_router
from backend.api.routers import cache as cache_router
from backend.api.routers import chat_history as chat_history_router
from backend.api.routers import context as context_router
from backend.api.routers import csv_export as csv_export_router
from backend.api.routers import dashboard as dashboard_router
from backend.api.routers import (
    dashboard_improvements as dashboard_improvements_router,
)
from backend.api.routers import (
    dashboard_metrics as dashboard_metrics_router,
)
from backend.api.routers import enhanced_ml as enhanced_ml_router
from backend.api.routers import executions as executions_router
from backend.api.routers import file_ops as file_ops_router
from backend.api.routers import health as health_router
from backend.api.routers import (
    health_monitoring as health_monitoring_router,
)
from backend.api.routers import live as live_router
from backend.api.routers import live_trading as live_trading_router
from backend.api.routers import market_regime as market_regime_router
from backend.api.routers import marketplace as marketplace_router
from backend.api.routers import metrics as metrics_router
from backend.api.routers import monitoring as monitoring_router
from backend.api.routers import monte_carlo as monte_carlo_router
from backend.api.routers import paper_trading as paper_trading_router
from backend.api.routers import perplexity as perplexity_router
from backend.api.routers import queue as queue_router
from backend.api.routers import risk_management as risk_management_router
from backend.api.routers import security as security_router
from backend.api.routers import slo_error_budget as slo_router
from backend.api.routers import (
    strategy_builder as strategy_builder_router,
)
from backend.api.routers import (
    strategy_isolation as strategy_isolation_router,
)
from backend.api.routers import (
    strategy_library as strategy_library_router,
)
from backend.api.routers import (
    strategy_templates as strategy_templates_router,
)
from backend.api.routers import (
    strategy_validation_ws as strategy_validation_ws_router,
)
from backend.api.routers import test as test_router
from backend.api.routers import test_runner as test_runner_router
from backend.api.routers import tick_charts as tick_charts_router
from backend.api.routers import walk_forward as walk_forward_router
from backend.api.routers import wizard as wizard_router

app = FastAPI(
    title="Bybit Strategy Tester API",
    version="2.0.0",
    description="""
## 🚀 Professional Backtesting & Live Trading Platform

This API provides comprehensive trading strategy backtesting and live trading capabilities for **Bybit Exchange**.

### Features

- **📊 Backtesting Engine** - High-performance backtesting with GPU acceleration
- **🤖 AI Analysis** - DeepSeek/Perplexity-powered trade analysis
- **📈 Market Data** - Real-time and historical Bybit data
- **🔧 Strategy Management** - CRUD operations for trading strategies
- **📉 Risk Metrics** - Sortino, Sharpe, Max Drawdown, and more
- **🔌 MCP Integration** - Model Context Protocol for AI assistants

### Authentication

Most endpoints require API key authentication via `X-API-Key` header.

### Rate Limiting

- Standard endpoints: **100 requests/minute**
- Heavy operations: **10 requests/minute**
- Health checks: **Unlimited**

### Links

- [Dashboard](/frontend/dashboard.html) - Web interface
- [Health Dashboard](/frontend/health-dashboard.html) - Service status
- [Prometheus Metrics](/api/v1/health/metrics) - Monitoring
    """,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Health", "description": "Service health and monitoring endpoints"},
        {"name": "Backtests", "description": "Backtest execution and results"},
        {"name": "Strategies", "description": "Trading strategy management"},
        {"name": "Market Data", "description": "Historical and real-time market data"},
        {"name": "Optimizations", "description": "Strategy parameter optimization"},
        {"name": "AI Analysis", "description": "AI-powered trade analysis"},
        {"name": "MCP", "description": "Model Context Protocol integration"},
    ],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "deepLinking": True,
        "displayRequestDuration": True,
        "filter": True,
        "showExtensions": True,
        "syntaxHighlight": {"theme": "monokai"},
    },
)

# Silence noisy FastMCP warnings (e.g., legacy OpenAPI parser)
for _mcp_logger_name in ("fastmcp", "fastmcp.openapi", "fastmcp.server"):
    logging.getLogger(_mcp_logger_name).setLevel(logging.ERROR)

# =============================
# Mount static files for frontend (MUST be after app creation but before workers start)
# =============================
_frontend_dir = Path(__file__).parent.parent.parent / "frontend"
logging.getLogger("uvicorn.error").info(f"[FRONTEND] Dir check: {_frontend_dir}, exists={_frontend_dir.exists()}")
if _frontend_dir.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount(
        "/frontend",
        StaticFiles(directory=str(_frontend_dir), html=True),
        name="frontend",
    )
    logging.getLogger("uvicorn.error").info("[FRONTEND] MOUNTED at /frontend")
else:
    # Optional frontend bundle: downgrade to INFO to avoid noisy warnings
    logging.getLogger("uvicorn.error").info(f"[FRONTEND] NOT FOUND: {_frontend_dir}")


# Friendly redirects so / and /frontend land on dashboard
@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/frontend/dashboard.html", status_code=307)


@app.get("/frontend", include_in_schema=False)
@app.get("/frontend/", include_in_schema=False)
async def frontend_redirect():
    return RedirectResponse(url="/frontend/dashboard.html", status_code=307)


# Strategy Builder redirect for convenience
@app.get("/strategy-builder", include_in_schema=False)
async def strategy_builder_redirect():
    return RedirectResponse(url="/frontend/strategy-builder.html", status_code=307)


# =============================================================================
# Root-level health endpoints for K8s probes and startup scripts
# =============================================================================
@app.get("/healthz", include_in_schema=False)
async def root_healthz():
    """K8s startup/liveness probe at root level."""
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
async def root_readyz():
    """K8s readiness probe at root level."""
    return {"status": "ready"}


@app.get("/livez", include_in_schema=False)
async def root_livez():
    """K8s liveness probe at root level."""
    return {"status": "live"}


import asyncio
from datetime import UTC

# Make FastMCP optional - may fail on Windows due to pywintypes issues
_FASTMCP_AVAILABLE = False
FastMCP = None
mcp = None

try:
    from fastmcp import FastMCP

    _FASTMCP_AVAILABLE = True
except ImportError as _mcp_err:
    logging.getLogger("uvicorn.error").warning(
        "FastMCP not available (import error): %s. MCP tools will be disabled.",
        _mcp_err,
    )
except Exception as _mcp_err:
    logging.getLogger("uvicorn.error").warning("FastMCP not available: %s. MCP tools will be disabled.", _mcp_err)

# Import MCP error handling and middleware

# =============================
# MCP Hardening Environment Config (Removed - now in middleware factory)
# =============================

# Recommended: Create MCP server from FastAPI app (industry standard)
if _FASTMCP_AVAILABLE and FastMCP is not None:
    mcp = FastMCP.from_fastapi(app=app, name="Bybit Strategy Tester", version="2.0.0")
else:
    logging.getLogger("uvicorn.error").info("MCP server disabled - FastMCP not available")

    # Create a dummy MCP object that does nothing (no-op decorator)
    class _DummyMCP:
        """Dummy MCP server when FastMCP is not available."""

        def tool(self):
            """No-op decorator - just returns the function as-is."""

            def decorator(func):
                return func

            return decorator

        def resource(self, *args, **kwargs):
            """No-op decorator."""

            def decorator(func):
                return func

            return decorator

    mcp = _DummyMCP()

# =============================
# MCP Modular Tools Registration (2026-01-23)
# =============================
# Modular tools extracted to backend/api/mcp/tools/ for better maintainability
try:
    from backend.api.mcp import register_all_tools

    register_all_tools(mcp)
    logging.getLogger("uvicorn.error").info("✅ Modular MCP tools registered")
except Exception as _e:
    logging.getLogger("uvicorn.error").warning(f"⚠️ Modular MCP tools: {_e}")


# =============================
# Note: MCP tools (agent_tools, file_tools) are now in backend/api/mcp/tools/
# CircuitBreaker and concurrency control are in backend/api/mcp/circuit_breaker.py
# All tools registered via register_all_tools(mcp) above
# =============================


# =============================
# Note: All MCP tools have been migrated to backend/api/mcp/tools/
# and are registered via register_all_tools(mcp) above.
# =============================
# MCP ASGI routes will be registered after custom routes are defined (see below)


# =============================
# Unified MCP Middleware (replaces McpHardeningMiddleware)
# =============================
# Middleware will be registered after CORS setup (see below)


# =============================
# MCP-native health endpoint using app.get on /mcp/health
# =============================
@app.get("/mcp/health")
async def mcp_health_native():
    """
    Enhanced health check via direct FastAPI route (avoids MCP-internal routing)
    Returns detailed status with per-check granularity
    """
    import os as _os
    from datetime import datetime as _dt

    checks = {}

    # Tools from MCP registry (access via get_tools async method)
    tool_count = 0
    tools_registered = []
    try:
        tools_dict = await mcp.get_tools()
        tools_registered = list(tools_dict.keys())
        tool_count = len(tools_registered)
        checks["mcp_tools_available"] = tool_count > 0
    except Exception:
        checks["mcp_tools_available"] = False

    # Auth configured (if required)
    auth_required = _os.getenv("MCP_REQUIRE_AUTH", "0") in ("1", "true", "yes", "True")
    auth_token = _os.getenv("MCP_AUTH_TOKEN", "")
    checks["auth_configured"] = (not auth_required) or bool(auth_token)

    # Database connected
    try:
        from backend.database import engine as _engine

        with _engine.connect() as _conn:
            _conn.exec_driver_sql("SELECT 1")
        checks["database_connected"] = True
    except Exception:
        checks["database_connected"] = False

    # Session manager (if available)
    sessions_active = 0
    _sm = getattr(mcp, "session_manager", None)
    if _sm and hasattr(_sm, "sessions"):
        try:
            sessions_active = len(_sm.sessions)
        except Exception:
            sessions_active = 0

    status = "healthy" if all(checks.values()) else "degraded"

    allowed_origins_str = _os.getenv("MCP_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    allowed_origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]
    version = _os.getenv("APP_VERSION", "2.0.0")

    return {
        "status": status,
        "timestamp": _dt.now(UTC).isoformat(),
        "version": version,
        "tool_count": tool_count,
        "tools_registered": tools_registered,
        "sessions_active": sessions_active,
        "auth_required": auth_required,
        "allowed_origins": allowed_origins,
        "checks": checks,
    }


# ============================================================================
# MIDDLEWARE SETUP (extracted to backend/api/middleware_setup.py)
# ============================================================================
# Configure all middleware via dedicated module for maintainability
configure_middleware(app)

# ============================================================================
# Prometheus Metrics Middleware (records API request counts/durations)
# ============================================================================
# Note: This must be registered separately as it uses @app.middleware decorator
create_prometheus_metrics_middleware(app)

import os as _os

app.include_router(security_router.router, prefix="/api/v1", tags=["security"])
app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["strategies"])
if _os.environ.get("USE_MOCK_BACKTESTS", "0").lower() in ("1", "true", "yes"):
    try:
        from backend.api.routers import mock_backtests as _mock_bt

        app.include_router(_mock_bt.router, prefix="/api/v1/backtests", tags=["backtests-mock"])
    except Exception as _e:
        logging.getLogger("uvicorn.error").warning("Failed to enable mock backtests: %s", _e)
        app.include_router(backtests.router, prefix="/api/v1/backtests", tags=["backtests"])
else:
    app.include_router(backtests.router, prefix="/api/v1/backtests", tags=["backtests"])
app.include_router(marketdata.router, prefix="/api/v1/marketdata", tags=["marketdata"])
# Tickers API (symbols-list, refresh-tickers) — register on app so paths are guaranteed
from backend.api.routers.tickers_api import get_symbols_list as tickers_get_symbols_list
from backend.api.routers.tickers_api import refresh_tickers as tickers_refresh_tickers

app.add_api_route(
    "/api/v1/marketdata/symbols-list",
    tickers_get_symbols_list,
    methods=["GET"],
    tags=["tickers"],
    include_in_schema=False,
)
app.add_api_route(
    "/api/v1/refresh-tickers",
    tickers_refresh_tickers,
    methods=["POST"],
    tags=["tickers"],
    include_in_schema=False,
)
# Tick Charts - Real-time tick-based candlestick charts
app.include_router(tick_charts_router.router, prefix="/api/v1/marketdata", tags=["tick-charts"])

app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(optimizations.router, prefix="/api/v1/optimizations", tags=["optimizations"])
app.include_router(live_router.router, prefix="/api/v1", tags=["live"])
app.include_router(live_router.router, prefix="/ws", tags=["live-ws"])
app.include_router(
    live_trading_router.router, prefix="/api/v1/live", tags=["live-trading"]
)  # NEW: Real-time live trading with Bybit WebSocket
app.include_router(
    risk_management_router.router,
    prefix="/api/v1/risk-management",
    tags=["risk-management"],
)  # NEW: Extended risk management API
app.include_router(wizard_router.router, prefix="/api/v1/wizard", tags=["wizard"])
app.include_router(bots_router.router, prefix="/api/v1/bots", tags=["bots"])
app.include_router(
    strategy_library_router.router,
    prefix="/api/v1/strategy-library",
    tags=["strategy-library"],
)  # NEW: Strategy Library with pre-built strategies
app.include_router(
    strategy_builder_router.router, prefix="/api/v1", tags=["strategy-builder"]
)  # NEW: Visual Strategy Builder
app.include_router(
    strategy_validation_ws_router.router, prefix="/api/v1", tags=["strategy-builder-ws"]
)  # NEW: WebSocket real-time validation for Strategy Builder
app.include_router(
    strategy_isolation_router.router, prefix="/api/v1", tags=["strategy-isolation"]
)  # DeepSeek: Strategy Isolation Framework
app.include_router(active_deals_router.router, prefix="/api/v1/active-deals", tags=["active-deals"])
app.include_router(health_router.router, prefix="/api/v1", tags=["health"])
# K8s probes at root level (without /api/v1 prefix)
app.include_router(health_router.router, prefix="", tags=["k8s-probes"], include_in_schema=False)
app.include_router(alerts_router.router, prefix="/api/v1", tags=["alerts"])  # NEW: Alerting endpoints
app.include_router(monte_carlo_router.router, prefix="/api/v1", tags=["monte-carlo"])  # NEW: Monte Carlo simulation
app.include_router(
    marketplace_router.router, prefix="/api/v1", tags=["marketplace"]
)  # NEW: Strategy Marketplace - sharing strategies between users
app.include_router(
    market_regime_router.router, prefix="/api/v1", tags=["market-regime"]
)  # NEW: Market Regime Detection - ADX/DI/BB analysis
app.include_router(
    paper_trading_router.router, prefix="/api/v1", tags=["paper-trading"]
)  # NEW: Paper Trading - real-time trading simulation
app.include_router(
    walk_forward_router.router, prefix="/api/v1", tags=["walk-forward"]
)  # NEW: Walk-forward optimization
app.include_router(slo_router.router, prefix="/api/v1", tags=["slo-error-budget"])  # NEW: SLO Error Budget tracking
app.include_router(health_monitoring_router.router, prefix="/api/v1", tags=["health-monitoring"])
app.include_router(monitoring_router.router, tags=["monitoring"])  # Phase 4: Prometheus metrics and monitoring
app.include_router(csv_export_router.router, prefix="/api/v1", tags=["csv-export"])
app.include_router(context_router.router, prefix="/api/v1", tags=["context"])
app.include_router(file_ops_router.router, prefix="/api/v1", tags=["file-ops"])
app.include_router(test_runner_router.router, prefix="/api/v1", tags=["tests"])
app.include_router(
    advanced_backtesting_router.router, prefix="/api/v1", tags=["advanced-backtesting"]
)  # NEW: Advanced backtesting with slippage, portfolio, analytics
app.include_router(perplexity_router.router, prefix="/api/v1", tags=["perplexity"])
app.include_router(ai_router.router, prefix="/api/v1", tags=["ai"])
app.include_router(agents_router.router, prefix="/api/v1/agents", tags=["agents"])  # NEW: AI Agents API
# Advanced AI Agent System - Multi-Agent Deliberation, Memory, Self-Improvement, MCP
from backend.api.routers import agents_advanced as agents_advanced_router

app.include_router(
    agents_advanced_router.router,
    prefix="/api/v1/agents/advanced",
    tags=["agents-advanced"],
)  # NEW: Advanced AI Agent System (MCP, Memory, Consensus, Self-Improvement)
app.include_router(
    ai_strategy_generator_router.router,
    prefix="/api/v1",
    tags=["ai-strategy-generator"],
)  # NEW: AI Strategy Generator - LLM-based strategy creation
app.include_router(
    enhanced_ml_router.router, tags=["machine-learning"]
)  # NEW: Enhanced ML - drift detection, model registry, AutoML, online learning

# Cost Dashboard API
from backend.api import cost_dashboard as cost_dashboard_router

app.include_router(cost_dashboard_router.router, tags=["costs"])

# Streaming API for real-time AI responses
from backend.api import streaming as streaming_router

app.include_router(streaming_router.router, tags=["streaming"])

# Rate Limit Dashboard API
from backend.api import (
    rate_limit_dashboard as rate_limit_dashboard_router,
)

app.include_router(rate_limit_dashboard_router.router, tags=["rate-limits"])

# Circuit Breaker Monitoring API
from backend.api.routers import (
    circuit_breakers as circuit_breakers_router,
)

app.include_router(circuit_breakers_router.router, tags=["circuit-breakers"])

# OpenTelemetry Tracing API
from backend.api.routers import tracing as tracing_router

app.include_router(tracing_router.router, tags=["tracing"])

# LangGraph Multi-Agent Orchestration API
from backend.api.routers import orchestration as orchestration_router

app.include_router(orchestration_router.router, tags=["orchestration"])

# Graceful Degradation API
from backend.api.routers import degradation as degradation_router

app.include_router(degradation_router.router, tags=["degradation"])

# Risk Dashboard API
from backend.api.routers import risk as risk_router

app.include_router(risk_router.router, tags=["risk"])

# Chaos Engineering API
from backend.api.routers import chaos as chaos_router

app.include_router(chaos_router.router, tags=["chaos"])

# ML Anomaly Detection API
from backend.api.routers import (
    anomaly_detection as anomaly_detection_router,
)

app.include_router(anomaly_detection_router.router, tags=["anomaly-detection"])

# API Key Rotation Service
from backend.api.routers import key_rotation as key_rotation_router

app.include_router(key_rotation_router.router, tags=["key-rotation"])

# Data Quality Layer
from backend.api.routers import data_quality as data_quality_router

app.include_router(data_quality_router.router, tags=["data-quality"])

# Synthetic Monitoring
from backend.api.routers import (
    synthetic_monitoring as synthetic_monitoring_router,
)

app.include_router(synthetic_monitoring_router.router, tags=["synthetic-monitoring"])

# Property-Based Testing
from backend.api.routers import (
    property_testing as property_testing_router,
)

app.include_router(property_testing_router.router, tags=["property-testing"])

# Rate Limiting
from backend.api.routers import rate_limiting as rate_limiting_router

app.include_router(rate_limiting_router.router, tags=["rate-limiting"])

# Trading Halt Mechanisms
from backend.api.routers import trading_halt as trading_halt_router

app.include_router(trading_halt_router.router, tags=["trading-halt"])

# Database Metrics
from backend.api.routers import db_metrics as db_metrics_router

app.include_router(db_metrics_router.router, tags=["db-metrics"])

# KMS Integration (Phase 4)
from backend.api.routers import kms as kms_router

app.include_router(kms_router.router, tags=["kms"])

# Git Secrets Scanner (Phase 4)
from backend.api.routers import secrets_scanner as secrets_scanner_router

app.include_router(secrets_scanner_router.router, tags=["secrets-scanner"])

# Security Services - already registered with prefix="/api/v1" at line ~981
# Removed duplicate registration here to avoid path conflicts (/security vs /api/v1/security)

# State Management Service (Phase 5)
from backend.api.routers import (
    state_management as state_management_router,
)

app.include_router(state_management_router.router, tags=["state-management"])

# Cache Warming Service (Phase 5)
from backend.api.routers import cache_warming as cache_warming_router

app.include_router(cache_warming_router.router, tags=["cache-warming"])

# A/B Testing Framework (Phase 5)
from backend.api.routers import ab_testing as ab_testing_router

app.include_router(ab_testing_router.router, prefix="/api/v1", tags=["ab-testing"])

app.include_router(inference.router, prefix="/api/v1", tags=["inference"])
app.include_router(metrics_router.router, prefix="/api/v1", tags=["metrics"])
app.include_router(dashboard_router.router, tags=["dashboard"])
app.include_router(dashboard_metrics_router.router, prefix="/api/v1", tags=["dashboard-metrics"])
app.include_router(
    dashboard_improvements_router.router,
    prefix="/api/v1",
    tags=["dashboard-improvements"],
)
app.include_router(strategy_templates_router.router, prefix="/api/v1", tags=["strategy-templates"])
app.include_router(test_router.router, prefix="/api/v1", tags=["testing"])
app.include_router(cache_router.router, prefix="/api/v1", tags=["cache"])
app.include_router(chat_history_router.router, prefix="/api/v1", tags=["chat-history"])
app.include_router(queue_router.router, prefix="/api/v1", tags=["queue"])
app.include_router(executions_router.router, prefix="/api/v1", tags=["executions"])
app.include_router(agent_to_agent_api.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(orchestrator.router, prefix="/api/v1/orchestrator", tags=["orchestrator"])

# Task 9: Include MCP bridge routes (optional - not critical if missing)
try:
    from backend.api.mcp_routes import router as mcp_bridge_router

    app.include_router(mcp_bridge_router, tags=["mcp-bridge"])
    logging.getLogger("uvicorn.error").info("✅ MCP bridge routes included at /mcp/bridge")
except Exception as _e:
    logging.getLogger("uvicorn.error").debug("MCP bridge routes not available: %s", _e)

# =============================
# Reset OpenAPI schema cache after all routers are added
# FastMCP.from_fastapi() was called early and cached empty schema
# This forces regeneration with all 600+ routes
# =============================
app.openapi_schema = None
logging.getLogger("uvicorn.error").info("тЬЕ OpenAPI schema cache reset - will regenerate with all routes")

try:
    _logger = logging.getLogger("uvicorn.error")
    _routes_info = []
    for r in app.router.routes:
        try:
            methods = sorted(getattr(r, "methods", []) or [])
            path = getattr(r, "path", "")
            name = getattr(r, "name", "")
            _routes_info.append(f"{methods}:{path}:{name}")
        except Exception:
            continue
    _logger.info("ROUTE_REGISTRY_START (%d routes)", len(_routes_info))
    for _ri in _routes_info:
        _logger.info("ROUTE %s", _ri)
    _logger.info("ROUTE_REGISTRY_END")
except Exception as _e:
    logging.getLogger("uvicorn.error").warning("Route registry logging failed: %s", _e)


from fastapi import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

REGISTRY = CollectorRegistry()
BACKFILL_UPSERTS = Counter(
    "backfill_upserts_total",
    "Total number of upserts performed by backfill",
    labelnames=("symbol", "interval"),
    registry=REGISTRY,
)
BACKFILL_PAGES = Counter(
    "backfill_pages_total",
    "Total number of pages processed by backfill",
    labelnames=("symbol", "interval"),
    registry=REGISTRY,
)
BACKFILL_DURATION = Histogram(
    "backfill_duration_seconds",
    "Backfill duration in seconds",
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1200, float("inf")),
    registry=REGISTRY,
)
RUNS_BY_STATUS = Counter(
    "backfill_runs_total",
    "Backfill runs by terminal status",
    labelnames=("status",),
    registry=REGISTRY,
)
# MCP metrics (registered in same custom registry)
MCP_TOOL_CALLS = Counter(
    "mcp_tool_calls_total",
    "Total MCP tool invocations",
    labelnames=("tool", "success"),
    registry=REGISTRY,
)
MCP_TOOL_ERRORS = Counter(
    "mcp_tool_errors_total",
    "Total MCP tool errors",
    labelnames=("tool", "error_type"),
    registry=REGISTRY,
)
MCP_TOOL_DURATION = Histogram(
    "mcp_tool_duration_seconds",
    "MCP tool execution latency",
    labelnames=("tool",),
    buckets=(
        0.1,
        0.5,
        1.0,
        2.0,
        5.0,
        10.0,
        20.0,
        30.0,
        60.0,
        120.0,
        float("inf"),
    ),  # Extended buckets for AI workloads (P95/P99)
    registry=REGISTRY,
)

# Task 13: Enhanced metrics for multi-agent system
CONSENSUS_LOOP_PREVENTED = Counter(
    "consensus_loop_prevented_total",
    "Total consensus loops prevented by guard",
    labelnames=("reason",),  # iteration_cap, duplicate, frequency, depth
    registry=REGISTRY,
)
DLQ_MESSAGES = Counter(
    "dlq_messages_total",
    "Total messages enqueued to DLQ",
    labelnames=("priority", "agent_type"),
    registry=REGISTRY,
)
DLQ_RETRIES = Counter(
    "dlq_retries_total",
    "Total DLQ retry attempts",
    labelnames=("status",),  # success, failed, expired
    registry=REGISTRY,
)
CORRELATION_ID_REQUESTS = Counter(
    "correlation_id_requests_total",
    "Requests with correlation IDs",
    labelnames=("has_correlation_id",),  # true, false
    registry=REGISTRY,
)
MCP_BRIDGE_CALLS = Counter(
    "mcp_bridge_calls_total",
    "MCP bridge direct calls (no HTTP)",
    labelnames=("tool", "success"),
    registry=REGISTRY,
)
MCP_BRIDGE_DURATION = Histogram(
    "mcp_bridge_tool_duration_seconds",
    "Duration of MCP bridge tool calls",
    labelnames=("tool", "success"),
    buckets=(
        0.001,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1,
        2,
        5,
        10,
        30,
        float("inf"),
    ),  # Fine-grained latency buckets
    registry=REGISTRY,
)

# Phase 4/5: Initialize monitoring metrics collector (it maintains its own registry)
try:
    import backend.monitoring.prometheus_metrics as prom_metrics

    _app_metrics_collector = prom_metrics.get_metrics_collector()
    logging.info("[OK] Monitoring metrics collector initialized")
except Exception as e:
    logging.warning(f"Failed to initialize monitoring metrics collector: {e}", exc_info=True)


def metrics_inc_upserts(symbol: str, interval: str, n: int = 1):
    try:
        BACKFILL_UPSERTS.labels(symbol=symbol, interval=interval).inc(n)
    except Exception as _e:
        logging.getLogger("backend.api.app").warning("Failed to update metrics: %s", _e)


def metrics_inc_pages(symbol: str, interval: str, n: int = 1):
    try:
        BACKFILL_PAGES.labels(symbol=symbol, interval=interval).inc(n)
    except Exception as _e:
        logging.getLogger("backend.api.app").warning("Failed to update metrics: %s", _e)


def metrics_observe_duration(seconds: float):
    try:
        BACKFILL_DURATION.observe(seconds)
    except Exception as _e:
        logging.getLogger("backend.api.app").warning("Failed to update metrics: %s", _e)


def metrics_inc_run_status(status: str):
    try:
        RUNS_BY_STATUS.labels(status=status).inc(1)
    except Exception as _e:
        logging.getLogger("backend.api.app").warning("Failed to update metrics: %s", _e)


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint - combines all metrics sources"""
    logger = logging.getLogger("backend.api.app")

    # Debug logging removed for production (was writing to file on every scrape)
    # Use logger.debug() instead if debugging is needed
    logger.debug("📊 /metrics endpoint called")

    # 1. Legacy/backfill metrics from global REGISTRY
    legacy_metrics = generate_latest(REGISTRY).decode("utf-8")
    logger.debug(f"📊 Legacy metrics: {len(legacy_metrics)} bytes")

    # 2. Orchestrator/MCP metrics
    orchestrator_metrics = ""
    try:
        from orchestrator.api.metrics import get_metrics

        metrics_collector = get_metrics()
        orchestrator_metrics = await metrics_collector.export_prometheus()
        logger.debug(f"📊 Orchestrator metrics: {len(orchestrator_metrics)} bytes")
    except Exception as e:
        logger.debug(f"Orchestrator metrics unavailable: {e}")
        orchestrator_metrics = f"# MCP Orchestrator metrics unavailable: {e!s}\n"

    # 3. Application monitoring metrics (cache, AI, backtest) - uses SEPARATE registry
    monitoring_metrics = ""
    try:
        from backend.monitoring.prometheus_metrics import get_metrics_collector

        # Get collector - it maintains its own registry with all metrics
        monitoring_collector = get_metrics_collector()
        monitoring_metrics = monitoring_collector.get_metrics_text()
        logger.debug(f"📊 Monitoring metrics: {len(monitoring_metrics)} bytes")
    except Exception as e:
        logger.warning(f"Failed to get monitoring metrics: {e}")
        monitoring_metrics = f"# Monitoring metrics unavailable: {e!s}\n"

    # Combine all metrics
    combined = legacy_metrics + "\n" + orchestrator_metrics + "\n" + monitoring_metrics

    logger.debug(
        f"📊 Combined metrics: {len(combined)} bytes (legacy={len(legacy_metrics)}, orch={len(orchestrator_metrics)}, mon={len(monitoring_metrics)})"
    )
    return Response(combined, media_type=CONTENT_TYPE_LATEST)


@app.get("/prometheus-metrics")
async def prometheus_metrics_endpoint():
    """Alternative Prometheus metrics endpoint that bypasses JSON serialization"""
    try:
        from backend.monitoring.prometheus_metrics import get_metrics_collector

        collector = get_metrics_collector()
        metrics_text = collector.get_metrics_text()
        from fastapi import Response as FastAPIResponse

        return FastAPIResponse(content=metrics_text, media_type="text/plain; version=0.0.4; charset=utf-8")
    except Exception as e:
        return FastAPIResponse(content=f"# Error: {e!s}\n", media_type="text/plain")


# NOTE: K8s probes (/healthz, /readyz, /livez) moved to backend/api/routers/health.py


@app.get("/api/v1/exchangez")
def exchangez():
    import json
    import time
    from typing import Any

    import requests

    t0 = time.perf_counter()
    url = "https://api.bybit.com/v5/market/kline"
    params = {"category": "linear", "symbol": "BTCUSDT", "interval": "1", "limit": 1}
    try:
        r = requests.get(url, params=params, timeout=2.0)
        latency = time.perf_counter() - t0
        status = r.status_code
        ok = r.ok
        payload: Any = None
        try:
            payload = r.json()
        except Exception:
            payload = None
        ret_code = None
        if isinstance(payload, dict):
            ret_code = payload.get("retCode") or payload.get("code")
        if ok and (ret_code in (0, None)):
            return {
                "status": "ok",
                "latency_ms": round(latency * 1000, 1),
                "http": status,
            }
        return Response(
            content=json.dumps(
                {
                    "status": "down",
                    "latency_ms": round(latency * 1000, 1),
                    "http": status,
                    "retCode": ret_code,
                }
            ),
            media_type="application/json",
            status_code=503,
        )
    except Exception as e:
        latency = time.perf_counter() - t0
        return Response(
            content=json.dumps(
                {
                    "status": "down",
                    "error": str(e),
                    "latency_ms": round(latency * 1000, 1),
                }
            ),
            media_type="application/json",
            status_code=503,
        )


# Background Bybit WS manager is handled via the app lifespan above.

# =============================
# NOW register MCP HTTP routes (after custom health route is defined)
# =============================
if _FASTMCP_AVAILABLE and mcp is not None and hasattr(mcp, "http_app"):
    mcp_app = mcp.http_app(path="/mcp")
    app.router.routes.extend(mcp_app.routes)


# Capture tool registry snapshot with delay for proper registration
async def capture_tool_registry():
    if not _FASTMCP_AVAILABLE or mcp is None:
        logging.getLogger("uvicorn.error").info("MCP tool registry skipped - FastMCP not available")
        return
    await asyncio.sleep(1)  # Wait for tools to fully register
    try:
        tools_dict = await mcp.get_tools()
        tools = list(tools_dict.keys())
        app.state.mcp_tools = tools
        logging.getLogger("uvicorn.error").info(
            f"✅ MCP Server routes added at /mcp ({len(tools)} agent tools registered: {tools})"
        )
    except Exception as e:
        logging.getLogger("uvicorn.error").warning(f"⚠️ Could not access MCP tool registry: {e}")


# Removed: asyncio.create_task() at module level causes "no running event loop" error
# This will be called via lifespan startup instead
