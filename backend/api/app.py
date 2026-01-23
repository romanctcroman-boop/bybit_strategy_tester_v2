import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure UTF-8 streams on Windows to avoid emoji-related encoding crashes
try:  # pragma: no cover - platform-specific safeguard
    if sys.platform.startswith("win"):
        for _stream in (sys.stdout, sys.stderr):
            if hasattr(_stream, "reconfigure"):
                _stream.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
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

# noqa: E402 - imports must be after sys.path manipulation
from backend.api import (  # noqa: E402
    agent_to_agent_api,  # ✅ Week 5 Day 5: AI Agent Communication (DeepSeek + Perplexity)
    orchestrator,  # ✅ Week 6: Orchestrator Dashboard (MOVED BEFORE metrics to avoid circular import)
)
from backend.api.routers import active_deals as active_deals_router  # noqa: E402
from backend.api.routers import (  # noqa: E402
    admin,
    backtests,
    inference,
    marketdata,
    optimizations,
    strategies,
)
from backend.api.routers import (  # noqa: E402
    advanced_backtesting as advanced_backtesting_router,
)
from backend.api.routers import agents as agents_router  # noqa: E402
from backend.api.routers import ai as ai_router  # noqa: E402
from backend.api.routers import (  # noqa: E402
    ai_strategy_generator as ai_strategy_generator_router,
)
from backend.api.routers import alerts as alerts_router  # noqa: E402
from backend.api.routers import bots as bots_router  # noqa: E402
from backend.api.routers import cache as cache_router  # noqa: E402
from backend.api.routers import chat_history as chat_history_router  # noqa: E402
from backend.api.routers import context as context_router  # noqa: E402
from backend.api.routers import csv_export as csv_export_router  # noqa: E402
from backend.api.routers import dashboard as dashboard_router  # noqa: E402
from backend.api.routers import (  # noqa: E402
    dashboard_improvements as dashboard_improvements_router,
)
from backend.api.routers import (  # noqa: E402
    dashboard_metrics as dashboard_metrics_router,
)
from backend.api.routers import enhanced_ml as enhanced_ml_router  # noqa: E402
from backend.api.routers import executions as executions_router  # noqa: E402
from backend.api.routers import file_ops as file_ops_router  # noqa: E402
from backend.api.routers import health as health_router  # noqa: E402
from backend.api.routers import (  # noqa: E402
    health_monitoring as health_monitoring_router,
)
from backend.api.routers import live as live_router  # noqa: E402
from backend.api.routers import live_trading as live_trading_router  # noqa: E402
from backend.api.routers import metrics as metrics_router  # noqa: E402
from backend.api.routers import monitoring as monitoring_router  # noqa: E402
from backend.api.routers import monte_carlo as monte_carlo_router  # noqa: E402
from backend.api.routers import perplexity as perplexity_router  # noqa: E402
from backend.api.routers import queue as queue_router  # noqa: E402
from backend.api.routers import risk_management as risk_management_router  # noqa: E402
from backend.api.routers import security as security_router  # noqa: E402
from backend.api.routers import slo_error_budget as slo_router  # noqa: E402
from backend.api.routers import (  # noqa: E402
    strategy_builder as strategy_builder_router,
)
from backend.api.routers import (  # noqa: E402
    strategy_isolation as strategy_isolation_router,
)
from backend.api.routers import (  # noqa: E402
    strategy_library as strategy_library_router,
)
from backend.api.routers import (  # noqa: E402
    strategy_templates as strategy_templates_router,
)
from backend.api.routers import test as test_router  # noqa: E402
from backend.api.routers import test_runner as test_runner_router  # noqa: E402
from backend.api.routers import tick_charts as tick_charts_router  # noqa: E402
from backend.api.routers import walk_forward as walk_forward_router  # noqa: E402
from backend.api.routers import wizard as wizard_router  # noqa: E402

# Optional: start BybitWsManager on app startup when feature flag is enabled
try:
    from backend.services.bybit_ws_manager import BybitWsManager
    from redis.asyncio import Redis
except Exception:
    Redis = None  # type: ignore
    BybitWsManager = None  # type: ignore


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log Alembic DB version vs code head(s) on startup
    try:
        from alembic.config import Config as _AlConfig  # type: ignore
        from alembic.script import ScriptDirectory  # type: ignore

        from backend.database import engine  # lazy to avoid import cycles

        db_rev = None
        with engine.connect() as conn:
            try:
                db_rev = conn.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar()
            except Exception:
                db_rev = None

        code_heads = None
        try:
            alembic_cfg = _AlConfig("alembic.ini")
            script = ScriptDirectory.from_config(alembic_cfg)
            code_heads = script.get_heads()
        except Exception:
            code_heads = None

        logging.getLogger("uvicorn.error").info(
            "Alembic versions: db=%s code_heads=%s match=%s",
            db_rev,
            code_heads,
            (db_rev in (code_heads or [])),
        )
    except Exception as _e:  # best-effort only
        logging.getLogger("uvicorn.error").info("Alembic status check skipped: %s", _e)

    # Create database tables on startup if they don't exist
    try:
        from backend.database import Base as _Base
        from backend.database import engine as _eng

        _Base.metadata.create_all(bind=_eng)
        logging.getLogger("uvicorn.error").info("тЬЕ Database tables created/verified")
    except Exception as _e:
        logging.getLogger("uvicorn.error").info(
            "Database table creation skipped: %s", _e
        )

    # Warmup Numba JIT functions for fast optimization (avoids cold start delay)
    try:
        from backend.backtesting.fast_optimizer import warmup_jit_functions

        warmup_jit_functions()
        logging.getLogger("uvicorn.error").info("✅ Numba JIT functions warmed up")
    except Exception as _e:
        logging.getLogger("uvicorn.error").info("Numba JIT warmup skipped: %s", _e)

    # Initialize Redis Queue Manager
    # Ensure queue_adapter variable always exists for later dependency wiring
    queue_adapter = None
    try:
        from backend.queue import queue_adapter as _qa

        queue_adapter = _qa

        await queue_adapter._ensure_connected()
        logging.getLogger("uvicorn.error").info("тЬЕ Redis Queue Manager connected")
    except Exception as _e:
        logging.getLogger("uvicorn.error").info(
            "Redis Queue Manager initialization skipped: %s", _e
        )

    # =========================================================================
    # PHASE 2: Circuit Breaker Persistence (Production Deployment)
    # =========================================================================
    try:
        from backend.agents.circuit_breaker_manager import get_circuit_manager
        from backend.config import CONFIG

        circuit_mgr = get_circuit_manager()
        persistence_enabled = await circuit_mgr.enable_persistence(
            redis_url=CONFIG.redis.url, autosave_interval=60
        )

        if persistence_enabled:
            logging.getLogger("uvicorn.error").info(
                "✅ Phase 2: Circuit Breaker Persistence enabled (Redis autosave: 60s)"
            )
        else:
            logging.getLogger("uvicorn.error").debug(
                "Phase 2: Circuit Breaker Persistence unavailable (Redis connection failed)"
            )
    except Exception as _e:
        logging.getLogger("uvicorn.error").debug(
            "Phase 2: Circuit Breaker Persistence not configured: %s", _e
        )

    # Start config file watcher for hot-reload (Priority 1)
    config_watcher = None
    try:
        from backend.agents.agent_config import (
            register_reload_callback,
            start_config_watcher,
        )
        from backend.agents.circuit_breaker_manager import on_config_change

        register_reload_callback(on_config_change)
        config_watcher = start_config_watcher()

        logging.getLogger("uvicorn.error").info(
            "тЬЕ Config hot-reload enabled: watching agents.yaml"
        )
        app.state.config_watcher = config_watcher
    except Exception as _e:
        logging.getLogger("uvicorn.error").info("Config hot-reload disabled: %s", _e)
        app.state.config_watcher = None

    # Initialize Plugin Manager (from MCP Server)
    try:
        import sys
        from pathlib import Path

        # Add mcp-server to path if not already there
        mcp_server_path = Path(__file__).parent.parent.parent / "mcp-server"
        if str(mcp_server_path) not in sys.path:
            sys.path.insert(0, str(mcp_server_path))

        from orchestrator.plugin_system import PluginManager

        plugin_manager = PluginManager(
            plugins_dir=mcp_server_path / "orchestrator" / "plugins",
            orchestrator=None,
            auto_reload=True,
            reload_interval=60,
        )

        await plugin_manager.initialize()
        await plugin_manager.load_all_plugins()

        plugins = plugin_manager.list_plugins()
        logging.getLogger("uvicorn.error").info(
            "Plugin Manager initialized: %s plugins loaded", len(plugins)
        )

        # Set dependencies for orchestrator API
        orchestrator.set_dependencies(plugin_manager, queue_adapter)
        app.state.plugin_manager = plugin_manager

    except Exception as _e:
        logging.getLogger("uvicorn.error").info("Plugin Manager disabled: %s", _e)
        app.state.plugin_manager = None

    # Initialize MCP Bridge (Task 9: MCP integration)
    try:
        from backend.mcp.mcp_integration import ensure_mcp_bridge_initialized

        await ensure_mcp_bridge_initialized()
        logging.getLogger("uvicorn.error").info("MCP Bridge initialized")

        # Capture MCP tool registry after bridge initialization
        asyncio.create_task(capture_tool_registry())
    except Exception as _e:
        logging.getLogger("uvicorn.error").debug(
            "MCP Bridge initialization skipped: %s", _e
        )

    # Start KlineDBService for candle upserts (fixes stale candle data issue)
    try:
        from backend.services.kline_db_service import KlineDBService

        kline_db_service = KlineDBService.get_instance()
        kline_db_service.start()
        app.state.kline_db_service = kline_db_service
        logging.getLogger("uvicorn.error").info("KlineDBService started")
    except Exception as _e:
        logging.getLogger("uvicorn.error").info("KlineDBService disabled: %s", _e)
        app.state.kline_db_service = None

    # Pre-warm SmartKlineService cache for popular symbols (faster first page load)
    # Skip warmup if SKIP_CACHE_WARMUP env var is set (useful when network is slow)
    import os as _warmup_os

    if _warmup_os.getenv("SKIP_CACHE_WARMUP", "").lower() in ("1", "true", "yes"):
        logging.getLogger("uvicorn.error").info(
            "SmartKline cache warmup SKIPPED (SKIP_CACHE_WARMUP=1)"
        )
    else:
        try:
            from backend.services.smart_kline_service import SMART_KLINE_SERVICE

            warmup_pairs = [
                ("BTCUSDT", "15"),
                ("BTCUSDT", "60"),
                ("BTCUSDT", "D"),  # Daily for volatility/risk calculations
            ]  # Core pairs for startup

            import concurrent.futures
            import time as _time

            def _warmup():
                start = _time.time()
                for symbol, interval in warmup_pairs:
                    try:
                        candles = SMART_KLINE_SERVICE.get_candles(symbol, interval, 500)
                        if candles:
                            logging.getLogger("uvicorn.error").info(
                                "Warmed: %s:%s (%s candles)",
                                symbol,
                                interval,
                                len(candles),
                            )
                    except Exception as e:
                        # Non-critical: warmup may fail on individual symbols
                        logging.getLogger("uvicorn.error").info(
                            "Warmup skipped %s:%s: %s", symbol, interval, e
                        )
                elapsed = _time.time() - start
                logging.getLogger("uvicorn.error").info(
                    "SmartKline cache warmup completed in %.1fs", elapsed
                )

            # Run warmup with short timeout - don't block startup
            logging.getLogger("uvicorn.error").info(
                "SmartKline cache warmup starting..."
            )
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_warmup)
                # Wait up to 10 seconds only - don't block startup
                try:
                    future.result(timeout=10)
                except concurrent.futures.TimeoutError:
                    # Avoid red output for expected timeout guard
                    logging.getLogger("uvicorn.error").info(
                        "SmartKline cache warmup timed out (10s), continuing..."
                    )
        except Exception as _e:
            logging.getLogger("uvicorn.error").info(
                "SmartKline cache warmup skipped: %s", _e
            )

    # Background task: Refresh daily candles for all symbols (for volatility calculations)
    async def _refresh_daily_data_background():
        """Refresh daily candle data for all symbols in background."""
        import asyncio as _asyncio

        await _asyncio.sleep(5)  # Wait for server to fully start
        try:
            import os
            from datetime import datetime

            from sqlalchemy import distinct, func

            from backend.database import SessionLocal
            from backend.models.bybit_kline_audit import BybitKlineAudit
            from backend.services.adapters.bybit import BybitAdapter

            db = SessionLocal()
            try:
                # Get all unique symbols
                symbols = db.query(distinct(BybitKlineAudit.symbol)).all()
                symbols = [s[0] for s in symbols if s[0]]

                if not symbols:
                    logging.getLogger("uvicorn.error").info(
                        "[VOLATILITY] No symbols in DB to refresh daily data"
                    )
                    return

                adapter = BybitAdapter(
                    api_key=os.environ.get("BYBIT_API_KEY"),
                    api_secret=os.environ.get("BYBIT_API_SECRET"),
                )

                from datetime import timezone

                now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                one_day_ms = 24 * 60 * 60 * 1000
                updated = 0

                for symbol in symbols:
                    # Check latest daily candle
                    latest = (
                        db.query(func.max(BybitKlineAudit.open_time))
                        .filter(
                            BybitKlineAudit.symbol == symbol,
                            BybitKlineAudit.interval == "D",
                        )
                        .scalar()
                    )

                    # Skip if fresh (less than 1 day old)
                    if latest and (now_ms - latest) < one_day_ms:
                        continue

                    # Fetch and persist daily candles
                    try:
                        rows = adapter.get_klines(symbol=symbol, interval="D", limit=90)
                        if rows:
                            rows_with_interval = [{**r, "interval": "D"} for r in rows]
                            adapter._persist_klines_to_db(symbol, rows_with_interval)
                            updated += 1
                    except Exception as e:
                        logging.getLogger("uvicorn.error").info(
                            f"[VOLATILITY] Skipped refresh {symbol}: {e}"
                        )

                    await _asyncio.sleep(0.2)  # Rate limiting

                logging.getLogger("uvicorn.error").info(
                    f"[VOLATILITY] Daily data refresh: {updated}/{len(symbols)} symbols updated"
                )
            finally:
                db.close()
        except Exception as e:
            logging.getLogger("uvicorn.error").info(
                f"[VOLATILITY] Background refresh skipped: {e}"
            )

    # Start background daily data refresh
    import asyncio as _startup_asyncio

    _startup_asyncio.create_task(_refresh_daily_data_background())

    # Startup
    if CONFIG.ws_enabled and Redis is not None and BybitWsManager is not None:
        try:
            r = Redis.from_url(
                CONFIG.redis.url, encoding="utf-8", decode_responses=True
            )
            mgr = BybitWsManager(
                r, CONFIG.redis.channel_ticks, CONFIG.redis.channel_klines
            )
            await mgr.start(symbols=CONFIG.ws_symbols, intervals=CONFIG.ws_intervals)
            app.state.ws_resources = (mgr, r)
        except Exception:
            app.state.ws_resources = None
    else:
        app.state.ws_resources = None

    # MCP is already integrated via FastMCP.from_fastapi() - no separate lifespan needed
    yield

    # Shutdown
    # Stop config watcher
    cw = getattr(app.state, "config_watcher", None)
    if cw:
        try:
            cw.stop()
            cw.join(timeout=2)
            logging.getLogger("uvicorn.error").info("ЁЯЫС Config watcher stopped")
        except Exception as _e:
            logging.getLogger("uvicorn.error").warning(
                "тЪая╕П Config watcher shutdown error: %s", _e
            )

    pm = getattr(app.state, "plugin_manager", None)
    if pm:
        try:
            logging.getLogger("uvicorn.error").info(
                "ЁЯФМ Shutting down Plugin Manager..."
            )
            await pm.unload_all_plugins()
        except Exception as _e:
            logging.getLogger("uvicorn.error").warning(
                "тЪая╕П Plugin Manager shutdown error: %s", _e
            )

    ws = getattr(app.state, "ws_resources", None)
    if ws:
        mgr, r = ws
        try:
            await mgr.stop()
        finally:
            try:
                await r.close()
            except Exception as _e:
                logging.getLogger("backend.api.app").warning(
                    "Failed to update metrics: %s", _e
                )

    # Stop KlineDBService
    kdb = getattr(app.state, "kline_db_service", None)
    if kdb:
        try:
            kdb.stop()
            logging.getLogger("uvicorn.error").info("🛑 KlineDBService stopped")
        except Exception as _e:
            logging.getLogger("uvicorn.error").warning(
                "⚠️ KlineDBService shutdown error: %s", _e
            )


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
logging.getLogger("uvicorn.error").info(
    f"[FRONTEND] Dir check: {_frontend_dir}, exists={_frontend_dir.exists()}"
)
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


import asyncio  # noqa: E402

# Make FastMCP optional - may fail on Windows due to pywintypes issues
_FASTMCP_AVAILABLE = False
FastMCP = None
mcp = None

try:
    from fastmcp import FastMCP  # noqa: E402

    _FASTMCP_AVAILABLE = True
except ImportError as _mcp_err:
    logging.getLogger("uvicorn.error").warning(
        "FastMCP not available (import error): %s. MCP tools will be disabled.",
        _mcp_err,
    )
except Exception as _mcp_err:
    logging.getLogger("uvicorn.error").warning(
        "FastMCP not available: %s. MCP tools will be disabled.", _mcp_err
    )

# Import MCP error handling and middleware

# =============================
# MCP Hardening Environment Config (Removed - now in middleware factory)
# =============================

# Recommended: Create MCP server from FastAPI app (industry standard)
if _FASTMCP_AVAILABLE and FastMCP is not None:
    mcp = FastMCP.from_fastapi(app=app, name="Bybit Strategy Tester", version="2.0.0")
else:
    logging.getLogger("uvicorn.error").info(
        "MCP server disabled - FastMCP not available"
    )

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
# Debug endpoint to check app routes
# =============================
@app.get("/debug/routes")
async def debug_routes():
    """Debug endpoint to check all registered routes."""
    routes = []
    for route in app.routes:
        route_info = {
            "path": getattr(route, "path", str(route)),
            "name": getattr(route, "name", None),
        }
        routes.append(route_info)
    return {"total_routes": len(routes), "routes": routes[:50]}  # First 50


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
    from datetime import timezone

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

    allowed_origins_str = _os.getenv(
        "MCP_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )
    allowed_origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]
    version = _os.getenv("APP_VERSION", "2.0.0")

    return {
        "status": status,
        "timestamp": _dt.now(timezone.utc).isoformat(),
        "version": version,
        "tool_count": tool_count,
        "tools_registered": tools_registered,
        "sessions_active": sessions_active,
        "auth_required": auth_required,
        "allowed_origins": allowed_origins,
        "checks": checks,
    }


# ============================================================================
# PHASE 1 SECURITY: Rate Limiting Middleware (MUST BE FIRST!)
# ============================================================================
from backend.middleware.rate_limiter import (  # noqa: E402
    RateLimitMiddleware,
    get_rate_limiter,
)

rate_limiter = get_rate_limiter()
app.add_middleware(RateLimitMiddleware, limiter=rate_limiter)

# ============================================================================
# Slow Request Timing Middleware (performance monitoring)
# ============================================================================
from backend.middleware.timing import TimingMiddleware  # noqa: E402

app.add_middleware(
    TimingMiddleware,
    slow_threshold_ms=500,  # Warn for requests > 500ms
    very_slow_threshold_ms=2000,  # Error for requests > 2s
    excluded_paths=["/health", "/metrics", "/favicon.ico", "/api/v1/health"],
)

# ============================================================================
# Gzip Compression Middleware (reduce response sizes)
# ============================================================================
from starlette.middleware.gzip import GZipMiddleware  # noqa: E402

app.add_middleware(GZipMiddleware, minimum_size=1000)  # Compress responses > 1KB

# ============================================================================
# OpenTelemetry Tracing Middleware (distributed tracing)
# ============================================================================
from backend.middleware.opentelemetry_tracing import (  # noqa: E402
    OpenTelemetryMiddleware,
)

app.add_middleware(
    OpenTelemetryMiddleware,
    service_name="bybit-strategy-tester",
    excluded_paths=["/health", "/metrics", "/favicon.ico", "/api/v1/health"],
)

# ============================================================================
# Task 10: Correlation ID Middleware (for distributed tracing)
# ============================================================================
from backend.middleware.correlation_id import CorrelationIdMiddleware  # noqa: E402

app.add_middleware(CorrelationIdMiddleware, header_name="X-Request-ID")
# Note: configure_correlation_logging() called in lifespan if needed (optional)

# ============================================================================
# WEEK 2 DAY 2: HTTP Cache Headers Middleware
# ============================================================================
from backend.middleware.cache_headers import CacheHeadersMiddleware  # noqa: E402
from backend.middleware.security_headers import SecurityHeadersMiddleware  # noqa: E402

app.add_middleware(
    CacheHeadersMiddleware,
    max_age=60,
    enable_etag=True,
    enable_last_modified=True,
)

# ============================================================================
# Prometheus Metrics Middleware (records API request counts/durations)
# ============================================================================


@app.middleware("http")
async def prometheus_metrics_middleware(request: Request, call_next):
    """Record per-request metrics for Prometheus collector.

    Uses the Phase 5 monitoring collector (separate registry) to increment
    api_requests_total and observe api_request_duration_seconds.
    """

    import time as _time  # local to avoid global conflicts

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
            logging.getLogger("backend.api.app").debug(
                "Prometheus metrics middleware skipped: %s", exc
            )


# ============================================================================
# Security Headers Middleware (basic hardening + CSP)
# ============================================================================
app.add_middleware(SecurityHeadersMiddleware)

# ============================================================================
# CORS Middleware (Production-ready with environment configuration)
# ============================================================================
import os as _cors_os  # noqa: E402

# Configure allowed origins via environment variable
# Default: permissive for development, restrict in production
_cors_origins_str = _cors_os.getenv(
    "CORS_ALLOWED_ORIGINS",
    # Default: allow common development origins
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
)
_cors_allow_all = _cors_os.getenv("CORS_ALLOW_ALL", "false").lower() in (
    "true",
    "1",
    "yes",
)

if _cors_allow_all:
    # Development mode: allow all origins
    _cors_origins = ["*"]
    _cors_allow_credentials = False  # Cannot use credentials with wildcard
else:
    # Production mode: use specific origins
    _cors_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]
    _cors_allow_credentials = True

logging.getLogger("uvicorn.error").info(
    f"CORS configured: origins={_cors_origins[:3]}{'...' if len(_cors_origins) > 3 else ''}"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-Request-ID",
    ],
)

# ============================================================================
# MCP Unified Middleware (AFTER CORS for proper override)
# ============================================================================
import os as _env_os  # noqa: E402

from backend.api.mcp_middleware import UnifiedMcpMiddleware  # noqa: E402

mcp_require_auth = _env_os.getenv("MCP_REQUIRE_AUTH", "false").lower() in (
    "true",
    "1",
    "yes",
)
mcp_auth_token = _env_os.getenv(
    "MCP_API_KEY", ""
)  # Changed from MCP_AUTH_TOKEN to MCP_API_KEY
mcp_allowed_origins_str = _env_os.getenv(
    "MCP_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)
mcp_allowed_origins = [
    o.strip() for o in mcp_allowed_origins_str.split(",") if o.strip()
]

# Perplexity recommendation: Enable auth in staging by default
# Override via env: MCP_REQUIRE_AUTH=false to disable
staging_or_prod = _env_os.getenv("ENVIRONMENT", "development") in (
    "staging",
    "production",
)
if staging_or_prod and not mcp_require_auth:
    logging.getLogger("uvicorn.error").warning(
        "тЪая╕П MCP auth disabled in staging/production! Set MCP_REQUIRE_AUTH=true and MCP_API_KEY."
    )

app.add_middleware(
    UnifiedMcpMiddleware,
    require_auth=mcp_require_auth,
    auth_token=mcp_auth_token,
    allowed_origins=mcp_allowed_origins,
)

import os as _os  # noqa: E402

app.include_router(security_router.router, prefix="/api/v1", tags=["security"])
app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["strategies"])
if _os.environ.get("USE_MOCK_BACKTESTS", "0").lower() in ("1", "true", "yes"):
    try:
        from backend.api.routers import mock_backtests as _mock_bt

        app.include_router(
            _mock_bt.router, prefix="/api/v1/backtests", tags=["backtests-mock"]
        )
    except Exception as _e:
        logging.getLogger("uvicorn.error").warning(
            "Failed to enable mock backtests: %s", _e
        )
        app.include_router(
            backtests.router, prefix="/api/v1/backtests", tags=["backtests"]
        )
else:
    app.include_router(backtests.router, prefix="/api/v1/backtests", tags=["backtests"])
app.include_router(marketdata.router, prefix="/api/v1/marketdata", tags=["marketdata"])

# Tick Charts - Real-time tick-based candlestick charts
app.include_router(
    tick_charts_router.router, prefix="/api/v1/marketdata", tags=["tick-charts"]
)

app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(
    optimizations.router, prefix="/api/v1/optimizations", tags=["optimizations"]
)
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
    strategy_isolation_router.router, prefix="/api/v1", tags=["strategy-isolation"]
)  # DeepSeek: Strategy Isolation Framework
app.include_router(
    active_deals_router.router, prefix="/api/v1/active-deals", tags=["active-deals"]
)
app.include_router(health_router.router, prefix="/api/v1", tags=["health"])
# K8s probes at root level (without /api/v1 prefix)
app.include_router(
    health_router.router, prefix="", tags=["k8s-probes"], include_in_schema=False
)
app.include_router(
    alerts_router.router, prefix="/api/v1", tags=["alerts"]
)  # NEW: Alerting endpoints
app.include_router(
    monte_carlo_router.router, prefix="/api/v1", tags=["monte-carlo"]
)  # NEW: Monte Carlo simulation
app.include_router(
    walk_forward_router.router, prefix="/api/v1", tags=["walk-forward"]
)  # NEW: Walk-forward optimization
app.include_router(
    slo_router.router, prefix="/api/v1", tags=["slo-error-budget"]
)  # NEW: SLO Error Budget tracking
app.include_router(
    health_monitoring_router.router, prefix="/api/v1", tags=["health-monitoring"]
)
app.include_router(
    monitoring_router.router, tags=["monitoring"]
)  # Phase 4: Prometheus metrics and monitoring
app.include_router(csv_export_router.router, prefix="/api/v1", tags=["csv-export"])
app.include_router(context_router.router, prefix="/api/v1", tags=["context"])
app.include_router(file_ops_router.router, prefix="/api/v1", tags=["file-ops"])
app.include_router(test_runner_router.router, prefix="/api/v1", tags=["tests"])
app.include_router(
    advanced_backtesting_router.router, prefix="/api/v1", tags=["advanced-backtesting"]
)  # NEW: Advanced backtesting with slippage, portfolio, analytics
app.include_router(perplexity_router.router, prefix="/api/v1", tags=["perplexity"])
app.include_router(ai_router.router, prefix="/api/v1", tags=["ai"])
app.include_router(
    agents_router.router, prefix="/api/v1/agents", tags=["agents"]
)  # NEW: AI Agents API
# Advanced AI Agent System - Multi-Agent Deliberation, Memory, Self-Improvement, MCP
from backend.api.routers import agents_advanced as agents_advanced_router  # noqa: E402

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
from backend.api import cost_dashboard as cost_dashboard_router  # noqa: E402

app.include_router(cost_dashboard_router.router, tags=["costs"])

# Streaming API for real-time AI responses
from backend.api import streaming as streaming_router  # noqa: E402

app.include_router(streaming_router.router, tags=["streaming"])

# Rate Limit Dashboard API
from backend.api import (  # noqa: E402
    rate_limit_dashboard as rate_limit_dashboard_router,
)

app.include_router(rate_limit_dashboard_router.router, tags=["rate-limits"])

# Circuit Breaker Monitoring API
from backend.api.routers import (  # noqa: E402
    circuit_breakers as circuit_breakers_router,
)

app.include_router(circuit_breakers_router.router, tags=["circuit-breakers"])

# OpenTelemetry Tracing API
from backend.api.routers import tracing as tracing_router  # noqa: E402

app.include_router(tracing_router.router, tags=["tracing"])

# LangGraph Multi-Agent Orchestration API
from backend.api.routers import orchestration as orchestration_router  # noqa: E402

app.include_router(orchestration_router.router, tags=["orchestration"])

# Graceful Degradation API
from backend.api.routers import degradation as degradation_router  # noqa: E402

app.include_router(degradation_router.router, tags=["degradation"])

# Risk Dashboard API
from backend.api.routers import risk as risk_router  # noqa: E402

app.include_router(risk_router.router, tags=["risk"])

# Chaos Engineering API
from backend.api.routers import chaos as chaos_router  # noqa: E402

app.include_router(chaos_router.router, tags=["chaos"])

# ML Anomaly Detection API
from backend.api.routers import (  # noqa: E402
    anomaly_detection as anomaly_detection_router,
)

app.include_router(anomaly_detection_router.router, tags=["anomaly-detection"])

# API Key Rotation Service
from backend.api.routers import key_rotation as key_rotation_router  # noqa: E402

app.include_router(key_rotation_router.router, tags=["key-rotation"])

# Data Quality Layer
from backend.api.routers import data_quality as data_quality_router  # noqa: E402

app.include_router(data_quality_router.router, tags=["data-quality"])

# Synthetic Monitoring
from backend.api.routers import (  # noqa: E402
    synthetic_monitoring as synthetic_monitoring_router,
)

app.include_router(synthetic_monitoring_router.router, tags=["synthetic-monitoring"])

# Property-Based Testing
from backend.api.routers import (  # noqa: E402
    property_testing as property_testing_router,
)

app.include_router(property_testing_router.router, tags=["property-testing"])

# Rate Limiting
from backend.api.routers import rate_limiting as rate_limiting_router  # noqa: E402

app.include_router(rate_limiting_router.router, tags=["rate-limiting"])

# Trading Halt Mechanisms
from backend.api.routers import trading_halt as trading_halt_router  # noqa: E402

app.include_router(trading_halt_router.router, tags=["trading-halt"])

# Database Metrics
from backend.api.routers import db_metrics as db_metrics_router  # noqa: E402

app.include_router(db_metrics_router.router, tags=["db-metrics"])

# KMS Integration (Phase 4)
from backend.api.routers import kms as kms_router  # noqa: E402

app.include_router(kms_router.router, tags=["kms"])

# Git Secrets Scanner (Phase 4)
from backend.api.routers import secrets_scanner as secrets_scanner_router  # noqa: E402

app.include_router(secrets_scanner_router.router, tags=["secrets-scanner"])

# Security Services - Key Audit, IP Whitelist, Secure Config (Phase 4)
from backend.api.routers import security as security_router  # noqa: E402

app.include_router(security_router.router, tags=["security"])

# State Management Service (Phase 5)
from backend.api.routers import (  # noqa: E402
    state_management as state_management_router,
)

app.include_router(state_management_router.router, tags=["state-management"])

# Cache Warming Service (Phase 5)
from backend.api.routers import cache_warming as cache_warming_router  # noqa: E402

app.include_router(cache_warming_router.router, tags=["cache-warming"])

# A/B Testing Framework (Phase 5)
from backend.api.routers import ab_testing as ab_testing_router  # noqa: E402

app.include_router(ab_testing_router.router, prefix="/api/v1", tags=["ab-testing"])

app.include_router(inference.router, prefix="/api/v1", tags=["inference"])
app.include_router(metrics_router.router, prefix="/api/v1", tags=["metrics"])
app.include_router(dashboard_router.router, tags=["dashboard"])
app.include_router(
    dashboard_metrics_router.router, prefix="/api/v1", tags=["dashboard-metrics"]
)
app.include_router(
    dashboard_improvements_router.router,
    prefix="/api/v1",
    tags=["dashboard-improvements"],
)
app.include_router(
    strategy_templates_router.router, prefix="/api/v1", tags=["strategy-templates"]
)
app.include_router(test_router.router, prefix="/api/v1", tags=["testing"])
app.include_router(cache_router.router, prefix="/api/v1", tags=["cache"])
app.include_router(chat_history_router.router, prefix="/api/v1", tags=["chat-history"])
app.include_router(queue_router.router, prefix="/api/v1", tags=["queue"])
app.include_router(executions_router.router, prefix="/api/v1", tags=["executions"])
app.include_router(agent_to_agent_api.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(
    orchestrator.router, prefix="/api/v1/orchestrator", tags=["orchestrator"]
)

# Task 9: Include MCP bridge routes (optional - not critical if missing)
try:
    from backend.api.mcp_routes import router as mcp_bridge_router

    app.include_router(mcp_bridge_router, tags=["mcp-bridge"])
    logging.getLogger("uvicorn.error").info(
        "✅ MCP bridge routes included at /mcp/bridge"
    )
except Exception as _e:
    logging.getLogger("uvicorn.error").debug("MCP bridge routes not available: %s", _e)

# =============================
# Reset OpenAPI schema cache after all routers are added
# FastMCP.from_fastapi() was called early and cached empty schema
# This forces regeneration with all 600+ routes
# =============================
app.openapi_schema = None
logging.getLogger("uvicorn.error").info(
    "тЬЕ OpenAPI schema cache reset - will regenerate with all routes"
)

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


@app.get("/api/test-simple")
async def test_simple_endpoint():
    return {"message": "Simple test works!", "status": "ok"}


from fastapi import Response  # noqa: E402
from prometheus_client import (  # noqa: E402
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
    logging.warning(
        f"Failed to initialize monitoring metrics collector: {e}", exc_info=True
    )


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


@app.get("/metrics-test-endpoint")
async def metrics_test():
    return {"status": "test endpoint works"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint - combines all metrics sources"""
    import os

    logger = logging.getLogger("backend.api.app")

    # Debug: write to file to verify endpoint is being called
    debug_file = os.path.join(
        os.path.dirname(__file__), "../../logs/metrics_endpoint_debug.log"
    )

    def debug_write(msg):
        with open(debug_file, "a") as f:
            f.write(msg + "\n")

    debug_write("📊 /metrics endpoint called")
    logger.info("📊 /metrics endpoint called")

    # 1. Legacy/backfill metrics from global REGISTRY
    legacy_metrics = generate_latest(REGISTRY).decode("utf-8")
    debug_write(f"Legacy: {len(legacy_metrics)} bytes")
    logger.info(f"📊 Legacy metrics: {len(legacy_metrics)} bytes")

    # 2. Orchestrator/MCP metrics
    orchestrator_metrics = ""
    try:
        from orchestrator.api.metrics import get_metrics

        metrics_collector = get_metrics()
        orchestrator_metrics = await metrics_collector.export_prometheus()
        debug_write(f"Orchestrator: {len(orchestrator_metrics)} bytes")
        logger.info(f"📊 Orchestrator metrics: {len(orchestrator_metrics)} bytes")
    except Exception as e:
        debug_write(f"Orchestrator error: {e}")
        logger.warning(f"Orchestrator metrics unavailable: {e}")
        orchestrator_metrics = f"# MCP Orchestrator metrics unavailable: {str(e)}\n"

    # 3. Application monitoring metrics (cache, AI, backtest) - uses SEPARATE registry
    monitoring_metrics = ""
    try:
        from backend.monitoring.prometheus_metrics import get_metrics_collector

        # Get collector - it maintains its own registry with all metrics
        monitoring_collector = get_metrics_collector()
        monitoring_metrics = monitoring_collector.get_metrics_text()
        debug_write(f"Monitoring: {len(monitoring_metrics)} bytes")
        if "cache_hits" in monitoring_metrics:
            debug_write("  ✓ Has cache_hits")
        else:
            debug_write("  ✗ NO cache_hits")
        logger.info(f"📊 Monitoring metrics: {len(monitoring_metrics)} bytes")
    except Exception as e:
        debug_write(f"Monitoring error: {e}")
        logger.error(f"Failed to get monitoring metrics: {e}", exc_info=True)
        monitoring_metrics = f"# Monitoring metrics unavailable: {str(e)}\n"

    # Combine all metrics
    combined = legacy_metrics + "\n" + orchestrator_metrics + "\n" + monitoring_metrics

    debug_write(f"Combined: {len(combined)} bytes")
    logger.info(
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

        return FastAPIResponse(
            content=metrics_text, media_type="text/plain; version=0.0.4; charset=utf-8"
        )
    except Exception as e:
        return FastAPIResponse(content=f"# Error: {str(e)}\n", media_type="text/plain")


# NOTE: K8s probes (/healthz, /readyz, /livez) moved to backend/api/routers/health.py


@app.get("/api/v1/exchangez")
def exchangez():
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
            content={
                "status": "down",
                "latency_ms": round(latency * 1000, 1),
                "http": status,
                "retCode": ret_code,
            }.__str__(),
            media_type="application/json",
            status_code=503,
        )
    except Exception as e:
        latency = time.perf_counter() - t0
        return Response(
            content={
                "status": "down",
                "error": str(e),
                "latency_ms": round(latency * 1000, 1),
            }.__str__(),
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
        logging.getLogger("uvicorn.error").info(
            "MCP tool registry skipped - FastMCP not available"
        )
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
        logging.getLogger("uvicorn.error").warning(
            f"⚠️ Could not access MCP tool registry: {e}"
        )


# Removed: asyncio.create_task() at module level causes "no running event loop" error
# This will be called via lifespan startup instead
