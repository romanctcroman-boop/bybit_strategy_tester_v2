"""
Paper Trading API Router.

Endpoints for simulated trading:
- Account management
- Order placement
- Position management
- Trade history
"""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services.paper_trading import (
    OrderSide,
    OrderType,
    get_paper_trading_engine,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/paper-trading", tags=["Paper Trading"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class PlaceOrderRequest(BaseModel):
    """Request to place an order."""

    symbol: str = Field(..., description="Trading pair, e.g., BTCUSDT")
    side: str = Field(..., description="buy or sell")
    qty: float = Field(..., gt=0, description="Order quantity")
    order_type: str = Field(default="market", description="market, limit, stop_market")
    price: float | None = Field(None, description="Limit price")
    stop_price: float | None = Field(None, description="Stop trigger price")
    reduce_only: bool = Field(default=False, description="Only reduce position")
    leverage: float | None = Field(
        None, ge=1, le=100, description="Position leverage"
    )


class OrderResponse(BaseModel):
    """Order response."""

    id: str
    symbol: str
    side: str
    order_type: str
    qty: float
    price: float | None
    status: str
    filled_qty: float
    filled_price: float
    created_at: str


class PositionResponse(BaseModel):
    """Position response."""

    symbol: str
    side: str
    size: float
    entry_price: float
    leverage: float
    unrealized_pnl: float
    realized_pnl: float
    notional_value: float
    margin_used: float
    liquidation_price: float | None
    stop_loss: float | None
    take_profit: float | None


class AccountResponse(BaseModel):
    """Account response."""

    initial_balance: float
    balance: float
    equity: float
    available_balance: float
    margin_used: float
    unrealized_pnl: float
    realized_pnl: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_return: float


class TradeResponse(BaseModel):
    """Trade response."""

    id: str
    order_id: str
    symbol: str
    side: str
    qty: float
    price: float
    fee: float
    pnl: float
    executed_at: str


class UpdatePriceRequest(BaseModel):
    """Request to update price."""

    symbol: str
    price: float = Field(..., gt=0)


class SetSLTPRequest(BaseModel):
    """Request to set SL/TP."""

    stop_loss: float | None = None
    take_profit: float | None = None


class ResetAccountRequest(BaseModel):
    """Request to reset account."""

    initial_balance: float = Field(default=10000.0, gt=0)


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("/account", response_model=AccountResponse)
async def get_account():
    """Get paper trading account information."""
    engine = get_paper_trading_engine()
    return engine.account.to_dict()


@router.post("/account/reset", response_model=AccountResponse)
async def reset_account(request: ResetAccountRequest):
    """Reset paper trading account."""
    engine = get_paper_trading_engine(
        initial_balance=request.initial_balance,
        reset=True,
    )
    logger.info(f"Paper trading account reset with balance: {request.initial_balance}")
    return engine.account.to_dict()


@router.get("/positions")
async def get_positions():
    """Get all open positions."""
    engine = get_paper_trading_engine()
    return {
        "positions": [p.to_dict() for p in engine.positions.values()],
        "count": len(engine.positions),
    }


@router.get("/positions/{symbol}", response_model=PositionResponse)
async def get_position(symbol: str):
    """Get position for specific symbol."""
    engine = get_paper_trading_engine()
    position = engine.positions.get(symbol.upper())

    if not position:
        raise HTTPException(status_code=404, detail=f"No position for {symbol}")

    return position.to_dict()


@router.post("/positions/{symbol}/close")
async def close_position(
    symbol: str,
    qty: float | None = Query(None, description="Quantity to close (None = full)"),
):
    """Close a position (fully or partially)."""
    engine = get_paper_trading_engine()

    order = engine.close_position(symbol.upper(), qty)
    if not order:
        raise HTTPException(status_code=404, detail=f"No position for {symbol}")

    return {
        "message": "Position close order placed",
        "order": order.to_dict(),
    }


@router.post("/positions/{symbol}/sltp")
async def set_position_sltp(symbol: str, request: SetSLTPRequest):
    """Set stop loss and/or take profit for position."""
    engine = get_paper_trading_engine()

    if symbol.upper() not in engine.positions:
        raise HTTPException(status_code=404, detail=f"No position for {symbol}")

    if request.stop_loss is not None:
        engine.set_stop_loss(symbol.upper(), request.stop_loss)

    if request.take_profit is not None:
        engine.set_take_profit(symbol.upper(), request.take_profit)

    return {
        "message": "SL/TP updated",
        "position": engine.positions[symbol.upper()].to_dict(),
    }


@router.post("/orders", response_model=OrderResponse)
async def place_order(request: PlaceOrderRequest):
    """Place a paper trading order."""
    engine = get_paper_trading_engine()

    try:
        side = OrderSide(request.side.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid side: {request.side}")

    try:
        order_type = OrderType(request.order_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid order type: {request.order_type}"
        )

    # Validate limit orders have price
    if order_type == OrderType.LIMIT and not request.price:
        raise HTTPException(status_code=400, detail="Limit orders require price")

    # Validate stop orders have stop_price
    if (
        order_type in (OrderType.STOP_MARKET, OrderType.TAKE_PROFIT_MARKET)
        and not request.stop_price
    ):
        raise HTTPException(status_code=400, detail="Stop orders require stop_price")

    order = engine.place_order(
        symbol=request.symbol.upper(),
        side=side,
        qty=request.qty,
        order_type=order_type,
        price=request.price,
        stop_price=request.stop_price,
        reduce_only=request.reduce_only,
        leverage=request.leverage,
    )

    return order.to_dict()


@router.get("/orders")
async def get_orders(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500),
):
    """Get orders."""
    engine = get_paper_trading_engine()

    orders = list(engine.orders.values())

    if status:
        orders = [o for o in orders if o.status.value == status.lower()]

    # Sort by created_at desc
    orders.sort(key=lambda o: o.created_at, reverse=True)

    return {
        "orders": [o.to_dict() for o in orders[:limit]],
        "count": len(orders),
    }


@router.get("/orders/pending")
async def get_pending_orders():
    """Get pending orders."""
    engine = get_paper_trading_engine()
    return {
        "orders": [o.to_dict() for o in engine.pending_orders],
        "count": len(engine.pending_orders),
    }


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    """Cancel a pending order."""
    engine = get_paper_trading_engine()

    success = engine.cancel_order(order_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Order {order_id} not found or not cancellable",
        )

    return {"message": f"Order {order_id} cancelled"}


@router.get("/trades", response_model=list[TradeResponse])
async def get_trades(
    symbol: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get trade history."""
    engine = get_paper_trading_engine()

    trades = engine.trades

    if symbol:
        trades = [t for t in trades if t.symbol == symbol.upper()]

    # Return most recent first
    trades = sorted(trades, key=lambda t: t.executed_at, reverse=True)

    return [t.to_dict() for t in trades[:limit]]


@router.get("/equity-curve")
async def get_equity_curve():
    """Get equity curve data."""
    engine = get_paper_trading_engine()
    return {
        "data": engine.get_equity_curve(),
        "count": len(engine.equity_curve),
    }


@router.get("/summary")
async def get_summary():
    """Get full paper trading summary."""
    engine = get_paper_trading_engine()
    return engine.get_account_summary()


@router.post("/price")
async def update_price(request: UpdatePriceRequest):
    """
    Update price for a symbol.

    This triggers order execution checks and P&L updates.
    In production, this would be called by WebSocket price feed.
    """
    engine = get_paper_trading_engine()
    engine.update_price(request.symbol.upper(), request.price)

    return {
        "symbol": request.symbol.upper(),
        "price": request.price,
        "positions_updated": request.symbol.upper() in engine.positions,
    }


@router.post("/prices/bulk")
async def update_prices_bulk(prices: dict[str, float]):
    """
    Update prices for multiple symbols at once.

    Body: {"BTCUSDT": 45000.0, "ETHUSDT": 3000.0}
    """
    engine = get_paper_trading_engine()

    for symbol, price in prices.items():
        engine.update_price(symbol.upper(), price)

    return {
        "updated": len(prices),
        "symbols": list(prices.keys()),
    }
