"""
Tick Chart API Router with Redis Pub/Sub Support.

Week 2 Optimization: Hybrid mode supporting both:
1. Legacy mode: TickService singleton (backward compatible)
2. Redis mode: Distributed architecture with Redis Pub/Sub

Set environment variable USE_REDIS_PUBSUB=true to enable Redis mode.
"""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import List

import redis.asyncio as redis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.services.tick_service import Trade, get_tick_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ticks", tags=["Tick Charts"])

# =============================================================================
# CONFIGURATION
# =============================================================================

USE_REDIS = os.getenv("USE_REDIS_PUBSUB", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

logger.info(f"Tick Charts Router Mode: {'REDIS' if USE_REDIS else 'LEGACY'}")

# =============================================================================
# RATE LIMITING & CONNECTION MANAGEMENT
# =============================================================================

MAX_CONNECTIONS_PER_WORKER = 800
MAX_CONNECTIONS_PER_IP = 50
MAX_CONNECTIONS_GLOBAL = 5000

connection_ips = defaultdict(list)
active_connections = 0
active_connections_lock = asyncio.Lock()


async def check_connection_limit(client_ip: str) -> tuple[bool, str]:
    """Check if connection is allowed based on limits."""
    global active_connections

    async with active_connections_lock:
        if active_connections >= MAX_CONNECTIONS_PER_WORKER:
            return (
                False,
                f"Worker at capacity ({MAX_CONNECTIONS_PER_WORKER} connections)",
            )

        now = time.time()
        connection_ips[client_ip] = [
            ts for ts in connection_ips[client_ip] if now - ts < 60
        ]

        if len(connection_ips[client_ip]) >= MAX_CONNECTIONS_PER_IP:
            return False, f"Too many connections from IP ({MAX_CONNECTIONS_PER_IP} max)"

        connection_ips[client_ip].append(now)
        active_connections += 1

        return True, "OK"


async def release_connection(client_ip: str):
    """Release a connection slot."""
    global active_connections

    async with active_connections_lock:
        active_connections = max(0, active_connections - 1)


# =============================================================================
# MODELS
# =============================================================================


class TickCandleOut(BaseModel):
    """Tick candle output model."""

    tick_count: int
    open_time: int
    close_time: int
    time: int
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
    subscribed_symbols: List[str]


# =============================================================================
# REST ENDPOINTS (Compatible with both modes)
# =============================================================================


@router.get("/candles", response_model=List[TickCandleOut])
async def get_tick_candles(
    symbol: str = Query("BTCUSDT", description="Trading pair symbol"),
    ticks: int = Query(100, ge=10, le=10000, description="Ticks per candle (10-10000)"),
    limit: int = Query(100, ge=1, le=1000, description="Number of candles to return"),
):
    """Get tick-based candles (legacy mode only)."""
    if USE_REDIS:
        return {"error": "Use WebSocket for Redis mode"}

    service = get_tick_service()
    service.get_aggregator(symbol, ticks)
    candles = service.get_tick_candles(symbol, ticks, limit)
    return candles


@router.get("/status")
async def get_status():
    """Get tick service status."""
    if USE_REDIS:
        # Try to get Redis stats
        try:
            redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
            info = await redis_client.info("stats")
            return {
                "mode": "redis",
                "redis_connected": True,
                "total_commands_processed": info.get(
                    "total_commands_processed", "unknown"
                ),
            }
        except Exception as e:
            return {"mode": "redis", "redis_connected": False, "error": str(e)}

    # Legacy mode
    service = get_tick_service()
    return service.get_stats()


# =============================================================================
# WEBSOCKET ENDPOINT - LEGACY MODE
# =============================================================================


async def handle_legacy_websocket(
    websocket: WebSocket, symbol: str, ticks: int, client_ip: str
):
    """Handle WebSocket in legacy mode (TickService singleton)."""
    logger.info(f"Legacy WS: {symbol}, {ticks} ticks (IP: {client_ip})")

    service = get_tick_service()

    if not service.is_running():
        asyncio.create_task(service.start([symbol]))

    service.get_aggregator(symbol, ticks)

    pending_candle = None
    pending_trades = []
    MAX_PENDING_TRADES = 20
    trade_sample_counter = 0
    TRADE_SAMPLE_RATE = 3

    def on_trade(trade_symbol: str, trade: Trade):
        nonlocal trade_sample_counter
        if trade_symbol == symbol:
            trade_sample_counter += 1
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
                if len(pending_trades) > MAX_PENDING_TRADES:
                    pending_trades.pop(0)

    def on_candle(candle_symbol: str, candle_ticks: int, candle):
        nonlocal pending_candle
        if candle_symbol == symbol and candle_ticks == ticks:
            pending_candle = candle.to_dict()

    service.add_trade_callback(on_trade)
    service.add_candle_callback(on_candle)

    history = service.get_tick_candles(symbol, ticks, limit=100)
    await websocket.send_json({"type": "history", "data": history})

    while True:
        await asyncio.sleep(0.05)

        if pending_candle is not None:
            await websocket.send_json({"type": "candle", "data": pending_candle})
            pending_candle = None
            continue

        current = service.get_current_candle(symbol, ticks)
        if current:
            current["server_time"] = int(datetime.now(timezone.utc).timestamp() * 1000)
            await websocket.send_json({"type": "current", "data": current})

        if pending_trades:
            trades_to_send = pending_trades.copy()
            pending_trades.clear()
            await websocket.send_json({"type": "trades", "data": trades_to_send})


# =============================================================================
# WEBSOCKET ENDPOINT - REDIS MODE
# =============================================================================


async def handle_redis_websocket(
    websocket: WebSocket, symbol: str, ticks: int, client_ip: str
):
    """
    Handle WebSocket in Redis mode.

    Subscribes to:
    - candles:{symbol}:{ticks} - Completed candles from aggregator
    - trades:{symbol} - Live trades (optional, for UI)
    """
    logger.info(f"Redis WS: {symbol}, {ticks} ticks (IP: {client_ip})")

    redis_client = None
    pubsub = None

    try:
        # Connect to Redis
        redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
        pubsub = redis_client.pubsub()

        # Subscribe to candles channel
        candle_channel = f"candles:{symbol}:{ticks}"
        trade_channel = f"trades:{symbol}"

        await pubsub.subscribe(candle_channel, trade_channel)
        logger.info(f"Subscribed to: {candle_channel}, {trade_channel}")

        # Send initial empty history (Redis mode doesn't store history yet)
        await websocket.send_json(
            {
                "type": "history",
                "data": [],
                "message": "Redis mode - connect to see live candles",
            }
        )

        # State tracking for current candle
        current_candle_state = None
        pending_trades = []
        trade_sample_counter = 0
        TRADE_SAMPLE_RATE = 3

        # Listen for Redis messages
        listen_task = asyncio.create_task(pubsub.listen())

        while True:
            try:
                # Get next message from Redis (with timeout)
                message = await asyncio.wait_for(listen_task.__anext__(), timeout=0.05)

                # Parse Redis message
                if message["type"] == "message":
                    channel = message["channel"]
                    data = json.loads(message["data"])

                    if channel == candle_channel:
                        # Completed candle from aggregator
                        candle_dict = data.get("candle", data)
                        await websocket.send_json(
                            {"type": "candle", "data": candle_dict}
                        )

                        # Update current candle state
                        current_candle_state = data.get("current_candle")

                    elif channel == trade_channel:
                        # Live trade (optional)
                        trade_sample_counter += 1
                        if trade_sample_counter >= TRADE_SAMPLE_RATE:
                            trade_sample_counter = 0
                            pending_trades.append(data)
                            if len(pending_trades) > 20:
                                pending_trades.pop(0)

            except asyncio.TimeoutError:
                # No message within 50ms - send current candle state
                if current_candle_state:
                    current_candle_state["server_time"] = int(
                        datetime.now(timezone.utc).timestamp() * 1000
                    )
                    await websocket.send_json(
                        {"type": "current", "data": current_candle_state}
                    )

                # Send pending trades
                if pending_trades:
                    trades_to_send = pending_trades.copy()
                    pending_trades.clear()
                    await websocket.send_json(
                        {"type": "trades", "data": trades_to_send}
                    )

    except Exception as e:
        logger.error(f"Redis WS error: {e}")
        raise

    finally:
        if pubsub:
            await pubsub.unsubscribe()
            await pubsub.close()
        if redis_client:
            await redis_client.close()


# =============================================================================
# MAIN WEBSOCKET ROUTER
# =============================================================================


@router.websocket("/ws/{symbol}")
async def tick_websocket(
    websocket: WebSocket,
    symbol: str,
    ticks: int = 100,
):
    """
    WebSocket endpoint for real-time tick data.

    Supports both legacy and Redis modes via USE_REDIS_PUBSUB environment variable.

    Legacy mode:
    - Uses TickService singleton
    - Limited to 800 connections per worker

    Redis mode:
    - Subscribes to Redis Pub/Sub
    - Horizontally scalable (add more workers)
    - Requires TradePublisher and TickAggregatorService running
    """
    client_ip = websocket.client.host if websocket.client else "unknown"

    # Check connection limits
    allowed, reason = await check_connection_limit(client_ip)
    if not allowed:
        await websocket.close(code=1008, reason=reason)
        logger.warning(f"Connection rejected from {client_ip}: {reason}")
        return

    await websocket.accept()
    logger.info(
        f"Tick WebSocket connected: {symbol}, {ticks} ticks "
        f"(Mode: {'Redis' if USE_REDIS else 'Legacy'}, IP: {client_ip}, "
        f"Active: {active_connections}/{MAX_CONNECTIONS_PER_WORKER})"
    )

    try:
        if USE_REDIS:
            await handle_redis_websocket(websocket, symbol, ticks, client_ip)
        else:
            await handle_legacy_websocket(websocket, symbol, ticks, client_ip)

    except WebSocketDisconnect:
        logger.info(f"Tick WebSocket disconnected: {symbol} (IP: {client_ip})")
    except Exception as e:
        logger.error(f"Tick WebSocket error: {e}")
    finally:
        await release_connection(client_ip)
        logger.info(
            f"Tick WebSocket closed: {symbol} (IP: {client_ip}, "
            f"Remaining: {active_connections})"
        )
