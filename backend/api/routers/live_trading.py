"""
Live Trading API Router.

REST and WebSocket endpoints for live trading operations.

Endpoints:
- POST /live/start - Start live trading
- POST /live/stop - Stop live trading
- GET /live/status - Get trading status
- POST /live/order - Place order
- DELETE /live/order/{id} - Cancel order
- GET /live/positions - Get positions
- POST /live/close/{symbol} - Close position
- WS /live/ws - Real-time trading updates
"""

import asyncio
import json
import logging
import os

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.services.live_trading.order_executor import (
    OrderExecutor,
    TimeInForce,
)
from backend.services.live_trading.position_manager import PositionManager
from backend.services.live_trading.strategy_runner import LiveStrategyRunner
from backend.services.trading_engine_interface import OrderSide

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Live Trading"])


# ==============================================================================
# Pydantic Models
# ==============================================================================


class OrderRequest(BaseModel):
    """Order request model."""

    symbol: str = Field(..., description="Trading pair, e.g., BTCUSDT")
    side: str = Field(..., description="buy or sell")
    order_type: str = Field("market", description="market, limit, stop_market")
    qty: float = Field(..., gt=0, description="Order quantity")
    price: float | None = Field(None, description="Limit price")
    trigger_price: float | None = Field(None, description="Stop trigger price")
    stop_loss: float | None = Field(None, description="Stop loss price")
    take_profit: float | None = Field(None, description="Take profit price")
    reduce_only: bool = Field(False, description="Reduce only flag")
    time_in_force: str = Field("GTC", description="GTC, IOC, FOK, PostOnly")


class StrategyStartRequest(BaseModel):
    """Strategy start request."""

    name: str = Field(..., description="Strategy name")
    symbol: str = Field(..., description="Trading pair")
    timeframe: str = Field("1", description="Candle timeframe")
    position_size_percent: float = Field(
        5.0, ge=0.1, le=100, description="Position size %"
    )
    leverage: float = Field(1.0, ge=1, le=100, description="Leverage")
    stop_loss_percent: float | None = Field(2.0, description="Stop loss %")
    take_profit_percent: float | None = Field(4.0, description="Take profit %")
    paper_trading: bool = Field(True, description="Paper trading mode")


class SetSLTPRequest(BaseModel):
    """Set SL/TP request."""

    symbol: str
    stop_loss: float | None = None
    take_profit: float | None = None


class LeverageRequest(BaseModel):
    """Set leverage request."""

    symbol: str
    leverage: float = Field(..., ge=1, le=100)


# ==============================================================================
# Singleton Instances
# ==============================================================================


# Global instances (initialized on first use)
_executor: OrderExecutor | None = None
_position_manager: PositionManager | None = None
_strategy_runner: LiveStrategyRunner | None = None
_ws_connections: list[WebSocket] = []


def get_api_credentials() -> tuple[str, str]:
    """Get API credentials from environment."""
    api_key = os.environ.get("BYBIT_API_KEY", "")
    api_secret = os.environ.get("BYBIT_API_SECRET", "")

    if not api_key or not api_secret:
        raise HTTPException(
            status_code=400,
            detail="BYBIT_API_KEY and BYBIT_API_SECRET environment variables required",
        )

    return api_key, api_secret


def is_testnet() -> bool:
    """Check if testnet mode is enabled."""
    return os.environ.get("BYBIT_TESTNET", "true").lower() in ("true", "1", "yes")


async def get_executor() -> OrderExecutor:
    """Get or create OrderExecutor instance."""
    global _executor

    if _executor is None:
        api_key, api_secret = get_api_credentials()
        _executor = OrderExecutor(
            api_key=api_key,
            api_secret=api_secret,
            testnet=is_testnet(),
        )

    return _executor


async def get_position_manager() -> PositionManager:
    """Get or create PositionManager instance."""
    global _position_manager

    if _position_manager is None:
        api_key, api_secret = get_api_credentials()
        _position_manager = PositionManager(
            api_key=api_key,
            api_secret=api_secret,
            testnet=is_testnet(),
        )

    return _position_manager


async def get_strategy_runner() -> LiveStrategyRunner:
    """Get or create LiveStrategyRunner instance."""
    global _strategy_runner

    if _strategy_runner is None:
        api_key, api_secret = get_api_credentials()
        _strategy_runner = LiveStrategyRunner(
            api_key=api_key,
            api_secret=api_secret,
            testnet=is_testnet(),
            paper_trading=True,  # Default to paper trading
        )

    return _strategy_runner


# ==============================================================================
# Order Endpoints
# ==============================================================================


@router.post("/order")
async def place_order(request: OrderRequest):
    """
    Place a trading order.

    Examples:
    - Market buy: {"symbol": "BTCUSDT", "side": "buy", "qty": 0.001}
    - Limit sell: {"symbol": "BTCUSDT", "side": "sell", "qty": 0.001, "order_type": "limit", "price": 50000}
    - With SL/TP: {"symbol": "BTCUSDT", "side": "buy", "qty": 0.001, "stop_loss": 48000, "take_profit": 52000}
    """
    executor = await get_executor()

    # Map string to enum
    side = OrderSide.BUY if request.side.lower() == "buy" else OrderSide.SELL

    # Map time in force
    tif_map = {
        "GTC": TimeInForce.GTC,
        "IOC": TimeInForce.IOC,
        "FOK": TimeInForce.FOK,
        "PostOnly": TimeInForce.POST_ONLY,
    }
    time_in_force = tif_map.get(request.time_in_force, TimeInForce.GTC)

    # Place order based on type
    if request.order_type.lower() == "market":
        result = await executor.place_market_order(
            symbol=request.symbol,
            side=side,
            qty=request.qty,
            reduce_only=request.reduce_only,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
        )
    elif request.order_type.lower() == "limit":
        if not request.price:
            raise HTTPException(
                status_code=400, detail="Price required for limit order"
            )
        result = await executor.place_limit_order(
            symbol=request.symbol,
            side=side,
            qty=request.qty,
            price=request.price,
            time_in_force=time_in_force,
            reduce_only=request.reduce_only,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
        )
    elif request.order_type.lower() == "stop_market":
        if not request.trigger_price:
            raise HTTPException(
                status_code=400, detail="Trigger price required for stop order"
            )
        result = await executor.place_stop_market_order(
            symbol=request.symbol,
            side=side,
            qty=request.qty,
            trigger_price=request.trigger_price,
            reduce_only=request.reduce_only,
        )
    else:
        raise HTTPException(
            status_code=400, detail=f"Unknown order type: {request.order_type}"
        )

    if result.success:
        return {
            "success": True,
            "order_id": result.order.order_id if result.order else None,
            "client_order_id": result.order.client_order_id if result.order else None,
            "latency_ms": result.latency_ms,
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Order failed: {result.error_code} - {result.error_message}",
        )


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: str,
    symbol: str = Query(..., description="Trading pair"),
):
    """Cancel an order by ID."""
    executor = await get_executor()

    result = await executor.cancel_order(
        symbol=symbol,
        order_id=order_id,
    )

    if result.success:
        return {"success": True, "message": f"Order {order_id} cancelled"}
    else:
        raise HTTPException(
            status_code=400, detail=f"Cancel failed: {result.error_message}"
        )


@router.delete("/orders")
async def cancel_all_orders(
    symbol: str | None = Query(None, description="Filter by symbol"),
):
    """Cancel all open orders."""
    executor = await get_executor()

    result = await executor.cancel_all_orders(symbol=symbol)

    if result.success:
        return {"success": True, "message": "All orders cancelled"}
    else:
        raise HTTPException(status_code=400, detail=result.error_message)


@router.get("/orders")
async def get_open_orders(
    symbol: str | None = Query(None, description="Filter by symbol"),
):
    """Get all open orders."""
    executor = await get_executor()

    orders = await executor.get_open_orders(symbol=symbol)

    return {
        "orders": [o.to_dict() for o in orders],
        "count": len(orders),
    }


@router.get("/orders/history")
async def get_order_history(
    symbol: str | None = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get order history."""
    executor = await get_executor()

    orders = await executor.get_order_history(symbol=symbol, limit=limit)

    return {
        "orders": [o.to_dict() for o in orders],
        "count": len(orders),
    }


# ==============================================================================
# Position Endpoints
# ==============================================================================


@router.get("/positions")
async def get_positions(
    symbol: str | None = Query(None, description="Filter by symbol"),
):
    """Get all open positions."""
    executor = await get_executor()

    positions = await executor.get_positions(symbol=symbol)

    return {
        "positions": positions,
        "count": len(positions),
    }


@router.post("/positions/close/{symbol}")
async def close_position(
    symbol: str,
    qty: float | None = Query(None, description="Quantity to close (None = full)"),
):
    """Close a position."""
    manager = await get_position_manager()

    # Initialize if needed
    if not manager._running:
        await manager._load_initial_state()

    success = await manager.close_position(symbol, qty)

    if success:
        return {"success": True, "message": f"Position {symbol} close initiated"}
    else:
        raise HTTPException(
            status_code=400, detail=f"Failed to close position {symbol}"
        )


@router.post("/positions/close-all")
async def close_all_positions():
    """Close all open positions."""
    manager = await get_position_manager()

    if not manager._running:
        await manager._load_initial_state()

    results = await manager.close_all_positions()

    return {
        "results": results,
        "closed": sum(1 for v in results.values() if v),
        "failed": sum(1 for v in results.values() if not v),
    }


@router.post("/positions/sl-tp")
async def set_position_sl_tp(request: SetSLTPRequest):
    """Set stop loss and/or take profit for a position."""
    manager = await get_position_manager()

    if not manager._running:
        await manager._load_initial_state()

    success = await manager.set_position_sl_tp(
        symbol=request.symbol,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
    )

    if success:
        return {"success": True, "message": f"SL/TP set for {request.symbol}"}
    else:
        raise HTTPException(status_code=400, detail="Failed to set SL/TP")


# ==============================================================================
# Account Endpoints
# ==============================================================================


@router.get("/balance")
async def get_balance(account_type: str = Query("UNIFIED", description="Account type")):
    """Get wallet balance."""
    executor = await get_executor()

    balance = await executor.get_wallet_balance(account_type)

    return balance


@router.post("/leverage")
async def set_leverage(request: LeverageRequest):
    """Set leverage for a symbol."""
    executor = await get_executor()

    success = await executor.set_leverage(request.symbol, request.leverage)

    if success:
        return {"success": True, "message": f"Leverage set to {request.leverage}x"}
    else:
        raise HTTPException(status_code=400, detail="Failed to set leverage")


# ==============================================================================
# Strategy Runner Endpoints
# ==============================================================================


@router.get("/status")
async def get_trading_status():
    """Get live trading status."""
    global _strategy_runner

    if _strategy_runner is None:
        return {
            "running": False,
            "paper_trading": None,
            "strategies": {},
            "message": "Strategy runner not initialized",
        }

    return _strategy_runner.get_status()


@router.post("/start")
async def start_trading(
    paper_trading: bool = Query(True, description="Enable paper trading"),
):
    """Start live trading with default monitoring."""
    runner = await get_strategy_runner()

    if runner._running:
        return {"success": False, "message": "Already running"}

    runner.paper_trading = paper_trading

    try:
        await runner.start()
        return {
            "success": True,
            "message": f"Trading started ({'paper' if paper_trading else 'live'} mode)",
            "testnet": is_testnet(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_trading():
    """Stop live trading."""
    global _strategy_runner

    if _strategy_runner is None or not _strategy_runner._running:
        return {"success": False, "message": "Not running"}

    await _strategy_runner.stop()

    return {"success": True, "message": "Trading stopped"}


@router.post("/paper/balance")
async def set_paper_balance(
    balance: float = Query(..., gt=0, description="New balance"),
):
    """Set paper trading balance."""
    runner = await get_strategy_runner()

    runner.set_paper_balance(balance)

    return {"success": True, "balance": balance}


@router.get("/paper/balance")
async def get_paper_balance():
    """Get paper trading balance."""
    runner = await get_strategy_runner()

    return {"balance": runner.get_paper_balance()}


# ==============================================================================
# WebSocket Endpoint
# ==============================================================================


@router.websocket("/ws")
async def live_trading_websocket(websocket: WebSocket):
    """
    WebSocket for real-time trading updates.

    Streams:
    - Position updates
    - Order updates
    - Wallet updates
    - Trade executions
    - Strategy signals

    Usage:
        const ws = new WebSocket('ws://localhost:8000/api/v1/live/ws');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log(data.type, data.data);
        };
    """
    await websocket.accept()
    _ws_connections.append(websocket)

    logger.info(f"Live trading WebSocket connected. Total: {len(_ws_connections)}")

    try:
        # Get or create position manager
        manager = await get_position_manager()

        # Register callbacks for streaming
        async def on_position_update(summary):
            await broadcast_message("position", summary)

        async def on_wallet_update(wallet):
            await broadcast_message("wallet", wallet)

        async def on_execution(executions):
            await broadcast_message("execution", executions)

        manager.on_position_update(on_position_update)
        manager.on_wallet_update(on_wallet_update)
        manager.on_execution(on_execution)

        # Start manager if not running
        if not manager._running:
            await manager.start()

        # Send initial state
        await websocket.send_json(
            {
                "type": "connected",
                "data": {
                    "testnet": is_testnet(),
                    "positions": manager.get_position_summary(),
                },
            }
        )

        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)

                # Handle incoming commands
                try:
                    cmd = json.loads(data)
                    await handle_ws_command(websocket, cmd, manager)
                except json.JSONDecodeError:
                    await websocket.send_json({"error": "Invalid JSON"})

            except TimeoutError:
                # Send ping/keepalive
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        logger.info("Live trading WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in _ws_connections:
            _ws_connections.remove(websocket)


async def broadcast_message(msg_type: str, data: dict):
    """Broadcast message to all connected WebSocket clients."""
    message = {"type": msg_type, "data": data}

    for ws in _ws_connections[:]:  # Copy list to avoid modification during iteration
        try:
            await ws.send_json(message)
        except Exception:
            _ws_connections.remove(ws)


async def handle_ws_command(
    websocket: WebSocket,
    cmd: dict,
    manager: PositionManager,
):
    """Handle incoming WebSocket command."""
    action = cmd.get("action", "")

    if action == "get_positions":
        summary = manager.get_position_summary()
        await websocket.send_json({"type": "positions", "data": summary})

    elif action == "get_wallet":
        wallet = manager.get_wallet()
        await websocket.send_json(
            {"type": "wallet", "data": wallet.to_dict() if wallet else {}}
        )

    elif action == "close_position":
        symbol = cmd.get("symbol")
        if symbol:
            success = await manager.close_position(symbol)
            await websocket.send_json(
                {"type": "close_result", "data": {"symbol": symbol, "success": success}}
            )

    elif action == "pong":
        pass  # Keepalive response

    else:
        await websocket.send_json({"error": f"Unknown action: {action}"})


# ==============================================================================
# Cleanup
# ==============================================================================


async def cleanup():
    """Cleanup on shutdown."""
    global _executor, _position_manager, _strategy_runner

    if _strategy_runner:
        await _strategy_runner.stop()
        _strategy_runner = None

    if _position_manager:
        await _position_manager.stop()
        _position_manager = None

    if _executor:
        await _executor.close()
        _executor = None

    logger.info("Live trading cleanup complete")
