"""
Application Lifespan Management

Extracted from app.py for better maintainability.
Handles startup/shutdown logic for the FastAPI application.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("uvicorn.error")

# Strong references to background tasks — prevents GC before completion (RUF006)
_background_tasks: set[asyncio.Task] = set()


def _fire_and_forget(coroutine) -> asyncio.Task:
    """Schedule a coroutine as a background task and keep a strong reference."""
    task = asyncio.create_task(coroutine)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def capture_tool_registry():
    """Capture MCP tool registry after bridge initialization."""
    try:
        from backend.mcp.mcp_integration import get_mcp_bridge

        bridge = get_mcp_bridge()
        if bridge:
            logger.info("MCP tool registry captured")
    except Exception as e:
        logger.debug(f"MCP tool registry capture skipped: {e}")


async def _check_alembic_version():
    """Log Alembic DB version vs code head(s) on startup."""
    try:
        from alembic.config import Config as AlConfig
        from alembic.script import ScriptDirectory

        from backend.database import engine

        db_rev = None
        with engine.connect() as conn:
            try:
                db_rev = conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar()
            except Exception:
                db_rev = None

        code_heads = None
        try:
            alembic_cfg = AlConfig("alembic.ini")
            script = ScriptDirectory.from_config(alembic_cfg)
            code_heads = script.get_heads()
        except Exception:
            code_heads = None

        logger.info(
            "Alembic versions: db=%s code_heads=%s match=%s",
            db_rev,
            code_heads,
            (db_rev in (code_heads or [])),
        )
    except Exception as e:
        logger.info("Alembic status check skipped: %s", e)


async def _create_database_tables():
    """Create database tables on startup if they don't exist."""
    try:
        from backend.database import Base, engine

        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created/verified")
    except Exception as e:
        logger.info("Database table creation skipped: %s", e)


async def _warmup_numba_jit():
    """Warmup Numba JIT functions for fast optimization."""
    if os.getenv("FAST_DEV_MODE", "").lower() in ("1", "true", "yes"):
        logger.info("⏭️ Numba JIT warmup SKIPPED (FAST_DEV_MODE=1)")
        return
    try:
        from backend.backtesting.fast_optimizer import warmup_jit_functions

        warmup_jit_functions()
        logger.info("✅ Numba JIT functions warmed up")
    except Exception as e:
        logger.info("Numba JIT warmup skipped: %s", e)


async def _init_redis_queue():
    """Initialize Redis Queue Manager."""
    try:
        from backend.queue import queue_adapter

        await queue_adapter._ensure_connected()
        logger.info("✅ Redis Queue Manager connected")
        return queue_adapter
    except Exception as e:
        logger.info("Redis Queue Manager initialization skipped: %s", e)
        return None


async def _init_circuit_breaker_persistence():
    """Initialize circuit breaker persistence with Redis."""
    try:
        from backend.agents.circuit_breaker_manager import get_circuit_manager
        from backend.config import CONFIG

        circuit_mgr = get_circuit_manager()
        persistence_enabled = await circuit_mgr.enable_persistence(redis_url=CONFIG.redis.url, autosave_interval=60)

        if persistence_enabled:
            logger.info("✅ Phase 2: Circuit Breaker Persistence enabled (Redis autosave: 60s)")
        else:
            logger.debug("Phase 2: Circuit Breaker Persistence unavailable (Redis connection failed)")
    except Exception as e:
        logger.debug("Phase 2: Circuit Breaker Persistence not configured: %s", e)


async def _start_config_watcher(app: "FastAPI"):
    """Start config file watcher for hot-reload."""
    try:
        from backend.agents.agent_config import (
            register_reload_callback,
            start_config_watcher,
        )
        from backend.agents.circuit_breaker_manager import on_config_change

        register_reload_callback(on_config_change)
        config_watcher = start_config_watcher()

        logger.info("✅ Config hot-reload enabled: watching agents.yaml")
        app.state.config_watcher = config_watcher
        return config_watcher
    except Exception as e:
        logger.info("Config hot-reload disabled: %s", e)
        app.state.config_watcher = None
        return None


async def _init_plugin_manager(app: "FastAPI", queue_adapter):
    """Initialize Plugin Manager from MCP Server."""
    try:
        import sys

        mcp_server_path = Path(__file__).parent.parent.parent / "mcp-server"
        if str(mcp_server_path) not in sys.path:
            sys.path.insert(0, str(mcp_server_path))

        from orchestrator.plugin_system import PluginManager

        # Import orchestrator for dependency injection
        from backend.api import orchestrator

        plugin_manager = PluginManager(
            plugins_dir=mcp_server_path / "orchestrator" / "plugins",
            orchestrator=None,
            auto_reload=True,
            reload_interval=60,
        )

        await plugin_manager.initialize()
        await plugin_manager.load_all_plugins()

        plugins = plugin_manager.list_plugins()
        logger.info("Plugin Manager initialized: %s plugins loaded", len(plugins))

        orchestrator.set_dependencies(plugin_manager, queue_adapter)
        app.state.plugin_manager = plugin_manager
        return plugin_manager

    except Exception as e:
        logger.info("Plugin Manager disabled: %s", e)
        app.state.plugin_manager = None
        return None


async def _init_mcp_bridge():
    """Initialize MCP Bridge."""
    try:
        from backend.mcp.mcp_integration import ensure_mcp_bridge_initialized

        await ensure_mcp_bridge_initialized()
        logger.info("MCP Bridge initialized")

        _fire_and_forget(capture_tool_registry())
    except Exception as e:
        logger.debug("MCP Bridge initialization skipped: %s", e)


async def _start_kline_db_service(app: "FastAPI"):
    """Start KlineDBService for candle upserts (bulk insert-or-update)."""
    try:
        from backend.services.kline_db_service import KlineDBService

        kline_db_service = KlineDBService.get_instance()
        kline_db_service.start()
        app.state.kline_db_service = kline_db_service
        logger.info("KlineDBService started")
        return kline_db_service
    except Exception as e:
        logger.info("KlineDBService disabled: %s", e)
        app.state.kline_db_service = None
        return None


def _warmup_smart_kline_cache():
    """Pre-warm SmartKlineService cache for popular symbols."""
    import time

    from backend.services.smart_kline_service import SMART_KLINE_SERVICE

    warmup_pairs = [
        ("BTCUSDT", "15"),
        ("BTCUSDT", "60"),
        ("BTCUSDT", "D"),
    ]

    start = time.time()
    for symbol, interval in warmup_pairs:
        try:
            candles = SMART_KLINE_SERVICE.get_candles(symbol, interval, 500)
            if candles:
                logger.info("Warmed: %s:%s (%s candles)", symbol, interval, len(candles))
        except Exception as e:
            logger.info("Warmup skipped %s:%s: %s", symbol, interval, e)

    elapsed = time.time() - start
    logger.info("SmartKline cache warmup completed in %.1fs", elapsed)


async def _warmup_cache():
    """Run cache warmup with timeout."""
    import concurrent.futures

    if os.getenv("FAST_DEV_MODE", "").lower() in ("1", "true", "yes"):
        logger.info("⏭️ SmartKline cache warmup SKIPPED (FAST_DEV_MODE=1)")
        return

    if os.getenv("SKIP_CACHE_WARMUP", "").lower() in ("1", "true", "yes"):
        logger.info("SmartKline cache warmup SKIPPED (SKIP_CACHE_WARMUP=1)")
        return

    try:
        logger.info("SmartKline cache warmup starting...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_warmup_smart_kline_cache)
            try:
                future.result(timeout=10)
            except concurrent.futures.TimeoutError:
                logger.info("SmartKline cache warmup timed out (10s), continuing...")
    except Exception as e:
        logger.info("SmartKline cache warmup skipped: %s", e)


async def _preload_symbols_list(app: "FastAPI"):
    """Preload Bybit symbols list (linear + spot) for Properties Symbol dropdown."""
    await asyncio.sleep(3)  # Let server start
    try:
        from backend.services.adapters.bybit import BybitAdapter

        adapter = BybitAdapter(
            api_key=os.environ.get("BYBIT_API_KEY"),
            api_secret=os.environ.get("BYBIT_API_SECRET"),
        )
        loop = asyncio.get_event_loop()
        linear = await loop.run_in_executor(
            None, lambda: adapter.get_symbols_list(category="linear", trading_only=True)
        )
        spot = await loop.run_in_executor(None, lambda: adapter.get_symbols_list(category="spot", trading_only=True))
        if not hasattr(app.state, "symbols_cache"):
            app.state.symbols_cache = {}
        app.state.symbols_cache["linear"] = linear or []
        app.state.symbols_cache["spot"] = spot or []
        logger.info(
            "[TICKERS] Preloaded symbols: linear=%s, spot=%s",
            len(app.state.symbols_cache.get("linear", [])),
            len(app.state.symbols_cache.get("spot", [])),
        )
    except Exception as e:
        logger.warning("Tickers preload skipped: %s", e)
        if not hasattr(app.state, "symbols_cache"):
            app.state.symbols_cache = {}


async def _refresh_daily_data_background():
    """Refresh daily candle data for all symbols in background."""
    await asyncio.sleep(5)  # Wait for server to fully start

    try:
        from datetime import datetime

        from sqlalchemy import distinct, func

        from backend.database import SessionLocal
        from backend.models.bybit_kline_audit import BybitKlineAudit
        from backend.services.adapters.bybit import BybitAdapter

        db = SessionLocal()
        try:
            symbols = db.query(distinct(BybitKlineAudit.symbol)).all()
            symbols = [s[0] for s in symbols if s[0]]

            if not symbols:
                logger.info("[VOLATILITY] No symbols in DB to refresh daily data")
                return

            adapter = BybitAdapter(
                api_key=os.environ.get("BYBIT_API_KEY"),
                api_secret=os.environ.get("BYBIT_API_SECRET"),
            )

            now_ms = int(datetime.now(UTC).timestamp() * 1000)
            one_day_ms = 24 * 60 * 60 * 1000
            updated = 0

            for symbol in symbols:
                latest = (
                    db.query(func.max(BybitKlineAudit.open_time))
                    .filter(
                        BybitKlineAudit.symbol == symbol,
                        BybitKlineAudit.interval == "D",
                    )
                    .scalar()
                )

                if latest and (now_ms - latest) < one_day_ms:
                    continue

                try:
                    rows = adapter.get_klines(symbol=symbol, interval="D", limit=90)
                    if rows:
                        rows_with_interval = [{**r, "interval": "D"} for r in rows]
                        adapter._persist_klines_to_db(symbol, rows_with_interval)
                        updated += 1
                except Exception as e:
                    logger.info(f"[VOLATILITY] Skipped refresh {symbol}: {e}")

                await asyncio.sleep(0.2)  # Rate limiting

            logger.info(f"[VOLATILITY] Daily data refresh: {updated}/{len(symbols)} symbols updated")
        finally:
            db.close()
    except Exception as e:
        logger.info(f"[VOLATILITY] Background refresh skipped: {e}")


async def _start_websocket_manager(app: "FastAPI", CONFIG):
    """Start WebSocket manager if enabled."""
    try:
        from redis.asyncio import Redis

        from backend.services.bybit_ws_manager import BybitWsManager

        if CONFIG.ws_enabled:
            r = Redis.from_url(CONFIG.redis.url, encoding="utf-8", decode_responses=True)
            mgr = BybitWsManager(r, CONFIG.redis.channel_ticks, CONFIG.redis.channel_klines)
            await mgr.start(symbols=CONFIG.ws_symbols, intervals=CONFIG.ws_intervals)
            app.state.ws_resources = (mgr, r)
            return (mgr, r)
    except Exception as e:
        logger.debug("Redis/Bybit WS manager not started (optional): %s", e)

    app.state.ws_resources = None
    return None


async def _shutdown_config_watcher(app: "FastAPI"):
    """Stop config watcher on shutdown."""
    cw = getattr(app.state, "config_watcher", None)
    if cw:
        try:
            cw.stop()  # stop() already includes thread join internally
            logger.info("🛑 Config watcher stopped")
        except Exception as e:
            logger.warning("⚠️ Config watcher shutdown error: %s", e)


async def _shutdown_plugin_manager(app: "FastAPI"):
    """Shutdown plugin manager."""
    pm = getattr(app.state, "plugin_manager", None)
    if pm:
        try:
            logger.info("🔌 Shutting down Plugin Manager...")
            # Plugin manager cleanup - check for available methods
            if hasattr(pm, "unload_all_plugins"):
                await pm.unload_all_plugins()
            elif hasattr(pm, "stop"):
                await pm.stop()
            elif hasattr(pm, "shutdown"):
                await pm.shutdown()
            logger.info("🔌 Plugin Manager shut down")
        except Exception as e:
            logger.warning("⚠️ Plugin Manager shutdown error: %s", e)


async def _shutdown_websocket(app: "FastAPI"):
    """Shutdown WebSocket resources."""
    ws = getattr(app.state, "ws_resources", None)
    if ws:
        mgr, r = ws
        try:
            await mgr.stop()
        finally:
            try:
                await r.close()
            except Exception as e:
                logger.warning("Failed to close Redis: %s", e)


async def _shutdown_kline_db_service(app: "FastAPI"):
    """Stop KlineDBService."""
    kdb = getattr(app.state, "kline_db_service", None)
    if kdb:
        try:
            kdb.stop()
            logger.info("🛑 KlineDBService stopped")
        except Exception as e:
            logger.warning("⚠️ KlineDBService shutdown error: %s", e)


def get_config():
    """Get CONFIG with fallback."""
    try:
        from backend.config import CONFIG

        return CONFIG
    except Exception:

        class _FallbackConfig:
            ws_enabled = False
            redis = None
            ws_symbols = []
            ws_intervals = []

        return _FallbackConfig()


@asynccontextmanager
async def lifespan(app: "FastAPI"):
    """
    Application lifespan manager.

    Handles startup and shutdown logic for the FastAPI application.
    Extracted from app.py for better maintainability.
    """
    CONFIG = get_config()

    # Cache for Bybit tickers (linear/spot), filled by _preload_symbols_list
    if not hasattr(app.state, "symbols_cache"):
        app.state.symbols_cache = {}

    # =========================================================================
    # STARTUP
    # =========================================================================

    # Check FAST_DEV_MODE for quick startup during development
    fast_dev_mode = os.getenv("FAST_DEV_MODE", "").lower() in ("1", "true", "yes")
    if fast_dev_mode:
        logger.info("🚀 FAST_DEV_MODE enabled - skipping warmup for faster startup")

    # Check Alembic version
    await _check_alembic_version()

    # Create database tables
    await _create_database_tables()

    # Initialize Redis Queue (needed by other services)
    queue_adapter = await _init_redis_queue()

    # PARALLEL WARMUP: JIT (CPU-bound) and Cache (I/O-bound) run simultaneously
    # This saves ~8 seconds on startup since they don't block each other
    logger.info("🔄 Starting parallel warmup (JIT + Cache)...")
    await asyncio.gather(
        _warmup_numba_jit(),
        _warmup_cache(),
    )

    # Initialize Circuit Breaker Persistence
    await _init_circuit_breaker_persistence()

    # Start config watcher
    await _start_config_watcher(app)

    # Initialize Plugin Manager
    await _init_plugin_manager(app, queue_adapter)

    # Initialize MCP Bridge
    await _init_mcp_bridge()

    # Start KlineDBService
    await _start_kline_db_service(app)

    # NOTE: Daily data refresh removed from startup — syncing happens when user
    # selects a symbol in the Parameters panel (sync-all-tf-stream endpoint).
    # This avoids duplicate functionality and unnecessary API calls on boot.

    # Preload Bybit tickers list for Properties Symbol dropdown (linear + spot)
    _fire_and_forget(_preload_symbols_list(app))

    # Start WebSocket manager
    await _start_websocket_manager(app, CONFIG)

    # =========================================================================
    # YIELD - Application runs here
    # =========================================================================
    yield

    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    await _shutdown_config_watcher(app)
    await _shutdown_plugin_manager(app)
    await _shutdown_websocket(app)
    await _shutdown_kline_db_service(app)
