"""Tick Chart API Router.

Provides REST and WebSocket endpoints for tick-based charts.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.api.websocket_auth import get_ws_authenticator
from backend.core.metrics import get_metrics
from backend.services.tick_service import Trade, get_tick_service

# Strong references to background tasks — prevents GC before completion (RUF006)
_background_tasks: set[asyncio.Task] = set()


def _fire_and_forget(coroutine) -> asyncio.Task:
    task = asyncio.create_task(coroutine)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ticks", tags=["Tick Charts"])

# =============================================================================
# RATE LIMITING & CONNECTION MANAGEMENT
# =============================================================================

# Week 1 Optimization: Connection limits per DeepSeek recommendations
MAX_CONNECTIONS_PER_WORKER = 800  # Safe limit for single asyncio event loop
MAX_CONNECTIONS_PER_IP = 50  # Prevent single IP from hogging all connections
MAX_CONNECTIONS_GLOBAL = 5000  # Total across all workers (Nginx will balance)
CONNECTION_HISTORY_TTL = 60  # Seconds to keep connection history for rate limiting

# Connection tracking
connection_ips: dict[str, list[float]] = defaultdict(list)  # IP -> [timestamps]
active_connections = 0
active_connections_lock = asyncio.Lock()


async def check_connection_limit(client_ip: str) -> tuple[bool, str]:
    """Check if connection is allowed based on limits.

    Args:
        client_ip: Client IP address.

    Returns:
        Tuple of (allowed: bool, reason: str).
    """
    global active_connections

    async with active_connections_lock:
        # Check per-worker limit (most important for stability)
        if active_connections >= MAX_CONNECTIONS_PER_WORKER:
            return (
                False,
                f"Worker at capacity ({MAX_CONNECTIONS_PER_WORKER} connections)",
            )

        # Check per-IP limit (prevent abuse)
        now = time.time()
        # Clean old entries (older than TTL)
        connection_ips[client_ip] = [ts for ts in connection_ips[client_ip] if now - ts < CONNECTION_HISTORY_TTL]

        if len(connection_ips[client_ip]) >= MAX_CONNECTIONS_PER_IP:
            return False, f"Too many connections from IP ({MAX_CONNECTIONS_PER_IP} max)"

        # Allow connection
        connection_ips[client_ip].append(now)
        active_connections += 1

        # Record metric
        service = get_tick_service()
        mode = "redis" if service.use_redis else "direct"
        get_metrics().tick_websocket_connection(mode, 1)

        return True, "OK"


async def release_connection(_client_ip: str) -> None:
    """Release a connection slot.

    Args:
        _client_ip: Client IP address (unused, kept for rate limiting history).
    """
    global active_connections

    async with active_connections_lock:
        active_connections = max(0, active_connections - 1)
        # Note: We don't remove from connection_ips to maintain rate limiting history

        # Record metric
        service = get_tick_service()
        mode = "redis" if service.use_redis else "direct"
        get_metrics().tick_websocket_connection(mode, -1)


# =============================================================================
# MODELS
# =============================================================================


class TickCandleOut(BaseModel):
    """Tick candle output model."""

    tick_count: int
    open_time: int
    close_time: int
    time: int  # For LightweightCharts (seconds)
    open: float
    high: float
    low: float
    close: float
    volume: float
    buy_volume: float
    sell_volume: float
    trade_count: int


class TradeOut(BaseModel):
    """Trade output model."""

    timestamp: int
    price: float
    qty: float
    side: str
    trade_id: str


class TickServiceStatus(BaseModel):
    """Tick service status."""

    running: bool
    trades_received: int
    candles_created: int
    reconnects: int
    last_trade_time: str | None
    subscribed_symbols: list[str]


# =============================================================================
# REST ENDPOINTS
# =============================================================================


@router.get("/candles", response_model=list[TickCandleOut])
async def get_tick_candles(
    symbol: str = Query("BTCUSDT", description="Trading pair symbol"),
    ticks: int = Query(100, ge=10, le=10000, description="Ticks per candle (10-10000)"),
    limit: int = Query(100, ge=1, le=1000, description="Number of candles to return"),
):
    """
    Get tick-based candles.

    Each candle represents N trades (ticks), not a time period.
    Useful for:
    - High-frequency analysis
    - Filtering low-activity periods
    - Consistent volatility per bar
    """
    service = get_tick_service()

    # Ensure aggregator exists for this configuration
    service.get_aggregator(symbol, ticks)

    candles = service.get_tick_candles(symbol, ticks, limit)
    return candles


@router.get("/candles/current")
async def get_current_candle(
    symbol: str = Query("BTCUSDT", description="Trading pair symbol"),
    ticks: int = Query(100, ge=10, le=10000, description="Ticks per candle"),
):
    """
    Get current (incomplete) tick candle.

    Shows progress towards next completed candle.
    """
    service = get_tick_service()
    current = service.get_current_candle(symbol, ticks)
    return current or {"message": "No trades yet"}


@router.get("/trades", response_model=list[TradeOut])
async def get_recent_trades(
    symbol: str = Query("BTCUSDT", description="Trading pair symbol"),
    limit: int = Query(100, ge=1, le=1000, description="Number of trades to return"),
):
    """
    Get recent trades (raw ticks).

    Returns the last N trades received from Bybit.
    """
    service = get_tick_service()
    trades = service.get_recent_trades(symbol, limit)
    return trades


@router.get("/status", response_model=TickServiceStatus)
async def get_tick_service_status():
    """Get tick service status and statistics."""
    service = get_tick_service()
    stats = service.get_stats()
    return stats


@router.get("/health")
async def tick_service_health():
    """
    Health check endpoint for Tick Service.

    Used by Kubernetes/load balancers to monitor service health.
    Returns detailed status for debugging and monitoring.
    """
    service = get_tick_service()
    stats = service.get_stats()

    # Calculate health status
    is_running = stats.get("running", False)
    last_trade_time = stats.get("last_trade_time")

    # Check if trades are being received (stale if no trade in 60s)
    is_stale = False
    last_trade_age_ms = None
    if last_trade_time:
        try:
            from datetime import datetime

            last_dt = datetime.fromisoformat(last_trade_time.replace("Z", "+00:00"))
            age = (datetime.now(UTC) - last_dt).total_seconds()
            last_trade_age_ms = int(age * 1000)
            is_stale = age > 60  # Stale if no trade in 60 seconds
        except Exception:
            pass

    # Determine overall health
    if not is_running:
        health_status = "stopped"
    elif is_stale:
        health_status = "degraded"
    else:
        health_status = "healthy"

    return {
        "status": health_status,
        "running": is_running,
        "mode": stats.get("mode", "unknown"),
        "last_trade_age_ms": last_trade_age_ms,
        "is_stale": is_stale,
        "trades_received": stats.get("trades_received", 0),
        "candles_created": stats.get("candles_created", 0),
        "reconnects": stats.get("reconnects", 0),
        "trade_callbacks_count": stats.get("trade_callbacks_count", 0),
        "candle_callbacks_count": stats.get("candle_callbacks_count", 0),
        "aggregators_count": stats.get("aggregators_count", 0),
        "active_websocket_connections": active_connections,
        "subscribed_symbols": stats.get("subscribed_symbols", []),
    }


@router.post("/start")
async def start_tick_service(
    symbols: list[str] = Query(["BTCUSDT"], description="Symbols to subscribe"),
    ticks: int = Query(100, ge=10, le=10000, description="Default ticks per candle"),
):
    """
    Start the tick service.

    Begins WebSocket connection to Bybit and starts collecting trades.
    """
    service = get_tick_service()

    if service.is_running():
        return {
            "status": "already_running",
            "symbols": list(service._subscribed_symbols),
        }

    # Create default aggregators for each symbol BEFORE starting
    # This ensures trades are collected from the beginning
    for symbol in symbols:
        service.get_aggregator(symbol, ticks)

    # Start in background
    _fire_and_forget(service.start(symbols))

    return {"status": "starting", "symbols": symbols, "ticks_per_bar": ticks}


@router.post("/stop")
async def stop_tick_service():
    """Stop the tick service."""
    service = get_tick_service()

    if not service.is_running():
        return {"status": "not_running"}

    await service.stop()
    return {"status": "stopped"}


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================


@router.websocket("/ws/{symbol}")
async def tick_websocket(
    websocket: WebSocket,
    symbol: str,
    ticks: int = 100,
    token: str = Query(None, description="Authentication token"),
):
    """
    WebSocket endpoint for real-time tick data.

    WEEK 1 OPTIMIZATION:
    - Connection limits per worker (800 max)
    - Per-IP rate limiting (50 max)
    - Proper connection tracking and cleanup

    Authentication (optional):
    - Query parameter: ws://host/ticks/ws/BTCUSDT?token=xxx
    - Set ALLOW_ANONYMOUS_WS=false to require authentication

    Sends:
    - {"type": "candle", "data": {...}} when candle completes
    - {"type": "current", "data": {...}} periodic current candle update (every 200ms)
    - {"type": "trade", "data": {...}} sampled trades
    """
    client_ip = websocket.client.host if websocket.client else "unknown"

    # Authenticate connection
    authenticator = get_ws_authenticator()
    auth_result = await authenticator.authenticate(websocket, token)

    if not auth_result.authenticated:
        await websocket.close(code=4001, reason=auth_result.error or "Authentication failed")
        logger.warning(f"WebSocket auth failed from {client_ip}: {auth_result.error}")
        return

    # Check connection limits BEFORE accepting WebSocket
    allowed, reason = await check_connection_limit(client_ip)
    if not allowed:
        await websocket.close(code=1008, reason=reason)
        logger.warning(f"Connection rejected from {client_ip}: {reason}")
        return

    await websocket.accept()
    logger.info(
        f"Tick WebSocket connected: {symbol}, {ticks} ticks/bar "
        f"(IP: {client_ip}, Active: {active_connections}/{MAX_CONNECTIONS_PER_WORKER})"
    )

    try:
        service = get_tick_service()

        # Ensure service is running
        if not service.is_running():
            _fire_and_forget(service.start([symbol]))

        # Ensure aggregator exists
        service.get_aggregator(symbol, ticks)

        # Pending messages - candles have priority
        pending_candle = None
        pending_trades = []
        MAX_PENDING_TRADES = 20  # Keep last 20 trades

        # Trade sampling for UI - every Nth trade (but we count all for ETA)
        trade_sample_counter = 0
        TRADE_SAMPLE_RATE = 3  # Show 1 of every 3 trades in UI

        # Register callbacks
        def on_trade(trade_symbol: str, trade: Trade):
            nonlocal trade_sample_counter
            if trade_symbol == symbol:
                trade_sample_counter += 1
                # Sample trades for UI display only
                if trade_sample_counter >= TRADE_SAMPLE_RATE:
                    trade_sample_counter = 0
                    pending_trades.append(
                        {
                            "timestamp": trade.timestamp,
                            "price": trade.price,
                            "qty": trade.qty,
                            "side": trade.side,
                        }
                    )
                    # Keep only last N trades
                    if len(pending_trades) > MAX_PENDING_TRADES:
                        pending_trades.pop(0)

        def on_candle(candle_symbol: str, candle_ticks: int, candle):
            nonlocal pending_candle
            if candle_symbol == symbol and candle_ticks == ticks:
                pending_candle = candle.to_dict()

        service.add_trade_callback(on_trade)
        service.add_candle_callback(on_candle)

        # Send initial history
        history = service.get_tick_candles(symbol, ticks, limit=100)
        await websocket.send_json({"type": "history", "data": history})

        # Main loop - send updates every 50ms (~20 updates per second)
        last_loop_time = asyncio.get_running_loop().time()

        while True:
            # Measure loop lag (detect if backend is overloaded)
            now = asyncio.get_running_loop().time()
            loop_delta = now - last_loop_time
            if loop_delta > 0.2:  # If loop took > 200ms (expected ~50ms)
                logger.warning(f"Tick WS loop lag: {loop_delta * 1000:.1f}ms")
            last_loop_time = now

            await asyncio.sleep(0.05)  # 20 updates per second

            # Priority 1: Send completed candle immediately
            if pending_candle is not None:
                try:
                    await websocket.send_json({"type": "candle", "data": pending_candle})
                    pending_candle = None
                except Exception:
                    break

                # Avoid immediately sending a "current" snapshot in the same
                # iteration right after a completed candle. This reduces UI churn
                # and prevents an extra update for a candle that just reset.
                continue

            # Send current candle state
            current = service.get_current_candle(symbol, ticks)
            if current:
                try:
                    # Add server timestamp for latency monitoring
                    current["server_time"] = int(datetime.now(UTC).timestamp() * 1000)
                    await websocket.send_json({"type": "current", "data": current})
                except Exception:
                    break

            # Send pending trades in batch
            if pending_trades:
                trades_to_send = pending_trades.copy()
                pending_trades.clear()

                # Send in a single message to reduce per-message overhead.
                try:
                    await websocket.send_json({"type": "trades", "data": trades_to_send})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f"Tick WebSocket disconnected: {symbol} (IP: {client_ip})")
    except Exception as e:
        logger.error(f"Tick WebSocket error: {e}")
    finally:
        # CRITICAL: Remove callbacks to prevent memory leak
        # Without this, callbacks accumulate indefinitely as connections close
        try:
            service.remove_trade_callback(on_trade)
            service.remove_candle_callback(on_candle)
            logger.debug(f"Callbacks removed for {symbol} (IP: {client_ip})")
        except Exception as cleanup_error:
            logger.warning(f"Callback cleanup error: {cleanup_error}")

        # Release connection slot
        await release_connection(client_ip)
        logger.info(f"Tick WS closed: {symbol} (IP: {client_ip}, Remaining: {active_connections})")
