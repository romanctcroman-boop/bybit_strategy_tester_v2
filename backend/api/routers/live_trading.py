"""
📈 Live Trading API Router

REST API for live trading:
- POST /live/order - Submit order
- GET /live/positions - Get positions
- POST /live/close - Close position
- GET /live/performance - Get performance

Example request:
```json
{
  "symbol": "BTCUSDT",
  "side": "buy",
  "quantity": 0.1,
  "type": "market"
}
```
"""

# mypy: disable-error-code="arg-type, assignment, var-annotated, return-value, union-attr, operator, attr-defined, misc, dict-item"

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live", tags=["Live Trading"])

# Global instances (in production, use dependency injection)
_paper_engine = None
_risk_limits = None
_position_tracker = None


def get_paper_engine():
    """Get paper trading engine"""
    global _paper_engine
    if _paper_engine is None:
        from backend.trading.paper_trading import PaperTradingEngine

        _paper_engine = PaperTradingEngine(
            initial_balance=10000.0,
            commission=0.0007,
        )
    return _paper_engine


def get_risk_limits():
    """Get risk limits"""
    global _risk_limits
    if _risk_limits is None:
        from backend.trading.risk_limits import RiskLimits

        _risk_limits = RiskLimits(
            max_daily_loss=1000.0,
            max_trade_loss=200.0,
            max_position_size=10000.0,
            max_drawdown=0.1,
        )
    return _risk_limits


def get_position_tracker():
    """Get position tracker"""
    global _position_tracker
    if _position_tracker is None:
        from backend.trading.position_tracker import PositionTracker

        _position_tracker = PositionTracker()
    return _position_tracker


class OrderRequest(BaseModel):
    """Order request"""

    symbol: str
    side: str = Field(..., description="buy or sell")
    quantity: float = Field(..., gt=0)
    type: str = Field(default="market", description="market or limit")
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None


class OrderResponse(BaseModel):
    """Order response"""

    success: bool
    trade_id: str | None = None
    entry_price: float | None = None
    quantity: float = 0.0
    balance: float = 0.0
    equity: float = 0.0
    error: str | None = None


class ClosePositionRequest(BaseModel):
    """Close position request"""

    symbol: str
    price: float | None = None


class PositionInfo(BaseModel):
    """Position information"""

    symbol: str
    quantity: float
    side: str
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_percent: float


class PerformanceInfo(BaseModel):
    """Performance information"""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    max_drawdown: float
    final_balance: float
    return_percent: float


@router.post("/order", response_model=OrderResponse)
async def submit_order(request: OrderRequest):
    """
    Submit paper trading order.
    """
    try:
        paper_engine = get_paper_engine()
        risk_limits = get_risk_limits()

        # Check risk limits
        risk_check = risk_limits.check_all()

        if not risk_check.allowed:
            return OrderResponse(
                success=False,
                error=risk_check.reason,
                quantity=0,
                balance=paper_engine.balance,
                equity=paper_engine.equity,
            )

        # Get current price (mock - in production, get from WebSocket)
        current_price = 50000.0  # Mock price

        # Update price
        paper_engine.update_price(request.symbol, current_price)

        # Open position
        result = paper_engine.open_position(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=request.price or current_price,
        )

        if result.success:
            # Update risk limits
            risk_limits.increment_trades()

            return OrderResponse(
                success=True,
                trade_id=result.trade.id if result.trade else None,
                entry_price=result.trade.entry_price if result.trade else current_price,
                quantity=request.quantity,
                balance=result.balance,
                equity=result.equity,
            )
        else:
            return OrderResponse(
                success=False,
                error=result.error,
                quantity=0,
                balance=result.balance,
                equity=result.equity,
            )

    except Exception as e:
        logger.error(f"Order failed: {e}", exc_info=True)
        return OrderResponse(
            success=False,
            error=str(e),
            quantity=0,
            balance=0,
            equity=0,
        )


@router.get("/positions", response_model=list[PositionInfo])
async def get_positions():
    """Get all open positions"""
    try:
        paper_engine = get_paper_engine()
        positions = paper_engine.get_positions()

        return [
            PositionInfo(
                symbol=symbol,
                quantity=data["quantity"],
                side=data["side"],
                entry_price=data["entry_price"],
                current_price=data["current_price"],
                unrealized_pnl=data["unrealized_pnl"],
                unrealized_pnl_percent=data["unrealized_pnl_percent"],
            )
            for symbol, data in positions.items()
        ]

    except Exception as e:
        logger.error(f"Get positions failed: {e}", exc_info=True)
        return []


@router.post("/close")
async def close_position(request: ClosePositionRequest):
    """Close position"""
    try:
        paper_engine = get_paper_engine()
        risk_limits = get_risk_limits()

        # Get current price
        current_price = 50000.0  # Mock

        # Close position
        result = paper_engine.close_position(
            symbol=request.symbol,
            price=request.price or current_price,
        )

        if result.success:
            # Update risk limits
            if result.trade:
                risk_limits.update_pnl(result.trade.pnl)

            return {
                "success": True,
                "trade": result.trade.to_dict() if result.trade else None,
                "balance": result.balance,
                "equity": result.equity,
            }
        else:
            return {
                "success": False,
                "error": result.error,
            }

    except Exception as e:
        logger.error(f"Close position failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@router.get("/performance", response_model=PerformanceInfo)
async def get_performance():
    """Get trading performance"""
    try:
        paper_engine = get_paper_engine()
        perf = paper_engine.get_performance()

        return PerformanceInfo(
            total_trades=perf["total_trades"],
            winning_trades=perf["winning_trades"],
            losing_trades=perf["losing_trades"],
            win_rate=perf["win_rate"],
            total_pnl=perf["total_pnl"],
            avg_pnl=perf["avg_pnl"],
            max_drawdown=perf["max_drawdown"],
            final_balance=perf["final_balance"],
            return_percent=perf["return_percent"],
        )

    except Exception as e:
        logger.error(f"Get performance failed: {e}", exc_info=True)
        return PerformanceInfo(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl=0.0,
            avg_pnl=0.0,
            max_drawdown=0.0,
            final_balance=0.0,
            return_percent=0.0,
        )


@router.get("/risk-status")
async def get_risk_status():
    """Get risk limits status"""
    try:
        risk_limits = get_risk_limits()

        return {
            "daily_pnl": risk_limits.daily_pnl,
            "daily_trades": risk_limits.daily_trades,
            "circuit_breaker_active": risk_limits.circuit_breaker_active,
            "limits": {
                "max_daily_loss": risk_limits.max_daily_loss,
                "max_trade_loss": risk_limits.max_trade_loss,
                "max_position_size": risk_limits.max_position_size,
                "max_drawdown": risk_limits.max_drawdown,
                "max_trades_per_day": risk_limits.max_trades_per_day,
            },
        }

    except Exception as e:
        logger.error(f"Get risk status failed: {e}", exc_info=True)
        return {}
