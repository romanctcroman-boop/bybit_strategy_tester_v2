"""
Risk Management API Router

Extended API endpoints for the new risk management module including:
- Position sizing calculations
- Trade validation
- Exposure monitoring
- Risk assessments
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services.risk_management import (
    AccountState,
    PositionSizer,
    RiskEngine,
    SizingMethod,
    TradeRequest,
    create_aggressive_risk_engine,
    create_conservative_risk_engine,
    create_moderate_risk_engine,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Risk Management V2"])

# Global risk engine instance (will be initialized on startup)
_risk_engine: Optional[RiskEngine] = None


def get_risk_engine() -> RiskEngine:
    """Get the global risk engine instance."""
    global _risk_engine
    if _risk_engine is None:
        _risk_engine = create_moderate_risk_engine(equity=10000.0)
    return _risk_engine


# ============================================================================
# Request/Response Models
# ============================================================================


class PositionSizeRequest(BaseModel):
    """Request for position size calculation."""

    equity: float = Field(..., gt=0, description="Current account equity")
    entry_price: float = Field(..., gt=0, description="Entry price")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    method: str = Field("fixed_percent", description="Sizing method")
    risk_per_trade_pct: float = Field(
        1.0, ge=0.1, le=10.0, description="Risk per trade %"
    )
    volatility: Optional[float] = Field(None, description="Symbol volatility")
    atr: Optional[float] = Field(None, description="ATR value")
    win_rate: float = Field(0.5, ge=0, le=1, description="Historical win rate")
    avg_win: float = Field(1.0, gt=0, description="Average win amount")
    avg_loss: float = Field(1.0, gt=0, description="Average loss amount")


class PositionSizeResponse(BaseModel):
    """Response with calculated position size."""

    position_size: float
    notional_value: float
    risk_amount: float
    risk_pct: float
    method_used: str
    leverage_applied: float
    details: Dict[str, Any]


class TradeValidationRequest(BaseModel):
    """Request to validate a trade."""

    symbol: str = Field(..., description="Trading symbol")
    side: str = Field(..., pattern="^(buy|sell)$", description="Trade side")
    order_type: str = Field("market", description="Order type")
    quantity: float = Field(..., gt=0, description="Order quantity")
    price: Optional[float] = Field(None, description="Limit price")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    leverage: float = Field(1.0, ge=1, le=100, description="Leverage")
    strategy_id: Optional[str] = Field(None, description="Strategy ID")


class TradeValidationResponse(BaseModel):
    """Response with trade validation result."""

    approved: bool
    result: str
    rejection_reasons: List[str]
    warnings: List[str]
    modifications: Dict[str, Any]
    validation_time_ms: float
    details: Dict[str, Any]


class RiskAssessmentRequest(BaseModel):
    """Request for comprehensive risk assessment."""

    symbol: str = Field(..., description="Trading symbol")
    side: str = Field(..., pattern="^(buy|sell)$", description="Trade side")
    entry_price: float = Field(..., gt=0, description="Entry price")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    volatility: Optional[float] = Field(None, description="Symbol volatility")
    atr: Optional[float] = Field(None, description="ATR value")
    win_rate: float = Field(0.5, ge=0, le=1, description="Historical win rate")
    avg_win: float = Field(1.0, gt=0, description="Average win")
    avg_loss: float = Field(1.0, gt=0, description="Average loss")


class RiskAssessmentResponse(BaseModel):
    """Response with risk assessment."""

    approved: bool
    risk_level: str
    position_size: float
    recommended_stop_loss: Optional[float]
    recommended_take_profit: Optional[float]
    max_allowed_size: float
    current_exposure_pct: float
    available_capacity_pct: float
    warnings: List[str]
    rejection_reasons: List[str]
    details: Dict[str, Any]


class ExposureStatusResponse(BaseModel):
    """Current exposure status."""

    total_exposure_pct: float
    available_exposure_pct: float
    used_margin: float
    current_drawdown_pct: float
    daily_pnl: float
    positions_count: int
    active_stops_count: int
    is_trading_allowed: bool
    violations: List[Dict[str, Any]]


class RiskEngineStatusResponse(BaseModel):
    """Risk engine status."""

    status: str
    trading_allowed: bool
    trading_paused: bool
    pause_reason: Optional[str]
    current_snapshot: Dict[str, Any]
    config: Dict[str, Any]
    components: Dict[str, Any]


class UpdateEquityRequest(BaseModel):
    """Request to update equity."""

    equity: float = Field(..., gt=0, description="New equity value")


class RegisterTradeRequest(BaseModel):
    """Request to register a trade."""

    symbol: str
    side: str = Field(..., pattern="^(buy|sell)$")
    size: float = Field(..., gt=0)
    entry_price: float = Field(..., gt=0)
    leverage: float = Field(1.0, ge=1)
    stop_loss: Optional[float] = None


class UpdatePriceRequest(BaseModel):
    """Request to update symbol price."""

    symbol: str
    price: float = Field(..., gt=0)


class StopLossConfigRequest(BaseModel):
    """Stop loss configuration."""

    stop_type: str = Field("trailing", description="Stop loss type")
    stop_loss_pct: float = Field(2.0, ge=0.1, le=50.0, description="Stop loss %")
    trailing_offset_pct: float = Field(
        0.5, ge=0, le=10.0, description="Trailing offset %"
    )
    enable_breakeven: bool = Field(True, description="Enable breakeven")
    breakeven_trigger_pct: float = Field(
        2.0, ge=0, le=50.0, description="Breakeven trigger %"
    )


class RiskLimitsRequest(BaseModel):
    """Risk limits configuration."""

    max_position_size_pct: float = Field(10.0, ge=1, le=100)
    max_total_exposure_pct: float = Field(100.0, ge=10, le=500)
    max_leverage: float = Field(5.0, ge=1, le=125)
    max_drawdown_pct: float = Field(20.0, ge=1, le=100)
    daily_loss_limit_pct: float = Field(5.0, ge=0.5, le=50)


# ============================================================================
# Position Sizing Endpoints
# ============================================================================


@router.post("/sizing/calculate", response_model=PositionSizeResponse)
async def calculate_position_size(request: PositionSizeRequest):
    """
    Calculate optimal position size using various methods.

    Methods available:
    - fixed_percent: Fixed percentage of equity
    - kelly: Kelly Criterion
    - volatility: Volatility-adjusted sizing
    - atr: ATR-based sizing
    - optimal_f: Optimal-F method
    """
    try:
        # Map method string to enum
        method_map = {
            "fixed_percent": SizingMethod.FIXED_PERCENTAGE,
            "kelly": SizingMethod.KELLY_CRITERION,
            "volatility": SizingMethod.VOLATILITY_BASED,
            "atr": SizingMethod.VOLATILITY_BASED,  # Use volatility for ATR
            "optimal_f": SizingMethod.OPTIMAL_F,
        }

        method = method_map.get(request.method.lower(), SizingMethod.FIXED_PERCENTAGE)

        # Create position sizer
        sizer = PositionSizer(
            equity=request.equity,
            default_risk_pct=request.risk_per_trade_pct,
            max_position_pct=20.0,
            max_risk_pct=request.risk_per_trade_pct * 2,
        )

        # Calculate size using the appropriate method
        result = sizer.calculate_size(
            entry_price=request.entry_price,
            stop_loss_price=request.stop_loss,
            method=method,
        )

        return PositionSizeResponse(
            position_size=result.position_size,
            notional_value=result.position_value,
            risk_amount=result.risk_amount,
            risk_pct=result.risk_percentage,
            method_used=request.method,
            leverage_applied=1.0,
            details=result.details,
        )

    except Exception as e:
        logger.error(f"Position sizing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sizing/methods")
async def get_sizing_methods():
    """Get available position sizing methods."""
    return {
        "methods": [
            {
                "id": "fixed_percent",
                "name": "Fixed Percentage",
                "description": "Risk a fixed percentage of equity per trade",
            },
            {
                "id": "kelly",
                "name": "Kelly Criterion",
                "description": "Optimal sizing based on win rate and payoff ratio",
            },
            {
                "id": "volatility",
                "name": "Volatility-Based",
                "description": "Size inversely proportional to volatility",
            },
            {
                "id": "atr",
                "name": "ATR-Based",
                "description": "Size based on Average True Range",
            },
            {
                "id": "optimal_f",
                "name": "Optimal-F",
                "description": "Ralph Vince's optimal fraction method",
            },
        ]
    }


# ============================================================================
# Trade Validation Endpoints
# ============================================================================


@router.post("/validate/trade", response_model=TradeValidationResponse)
async def validate_trade(request: TradeValidationRequest):
    """
    Validate a trade before execution.

    Checks:
    - Balance sufficiency
    - Position size limits
    - Leverage limits
    - Symbol restrictions
    - Trading frequency
    - Risk/reward ratio
    """
    try:
        engine = get_risk_engine()

        # Build trade request
        trade_request = TradeRequest(
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            leverage=request.leverage,
            strategy_id=request.strategy_id,
        )

        # Build account state from engine
        account_state = AccountState(
            total_equity=engine.exposure_controller.equity,
            available_balance=engine.exposure_controller.equity
            - engine.exposure_controller.used_margin,
            used_margin=engine.exposure_controller.used_margin,
            total_pnl=engine.exposure_controller.total_pnl,
            daily_pnl=engine.exposure_controller.daily_pnl,
            open_positions_count=len(engine.exposure_controller.positions),
            positions_by_symbol={s: 1 for s in engine.exposure_controller.positions},
            trades_today=0,
            trades_this_hour=0,
            last_trade_time=None,
            is_trading_paused=engine._trading_paused,
            current_drawdown_pct=engine.exposure_controller.current_drawdown_pct,
        )

        # Validate
        report = engine.trade_validator.validate(trade_request, account_state)

        return TradeValidationResponse(
            approved=report.approved,
            result=report.result.value,
            rejection_reasons=[r.value for r in report.rejection_reasons],
            warnings=report.warnings,
            modifications=report.modifications,
            validation_time_ms=report.validation_time_ms,
            details=report.details,
        )

    except Exception as e:
        logger.error(f"Trade validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Risk Assessment Endpoints
# ============================================================================


@router.post("/assess", response_model=RiskAssessmentResponse)
async def assess_trade_risk(request: RiskAssessmentRequest):
    """
    Comprehensive risk assessment for a potential trade.

    Combines:
    - Position sizing calculation
    - Exposure check
    - Trade validation
    - Risk level determination
    """
    try:
        engine = get_risk_engine()

        assessment = engine.assess_trade(
            symbol=request.symbol,
            side=request.side,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volatility=request.volatility,
            atr=request.atr,
            win_rate=request.win_rate,
            avg_win=request.avg_win,
            avg_loss=request.avg_loss,
        )

        return RiskAssessmentResponse(
            approved=assessment.approved,
            risk_level=assessment.risk_level.value,
            position_size=assessment.position_size,
            recommended_stop_loss=assessment.recommended_stop_loss,
            recommended_take_profit=assessment.recommended_take_profit,
            max_allowed_size=assessment.max_allowed_size,
            current_exposure_pct=assessment.current_exposure_pct,
            available_capacity_pct=assessment.available_capacity_pct,
            warnings=assessment.warnings,
            rejection_reasons=assessment.rejection_reasons,
            details=assessment.details,
        )

    except Exception as e:
        logger.error(f"Risk assessment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Exposure & Status Endpoints
# ============================================================================


@router.get("/exposure", response_model=ExposureStatusResponse)
async def get_exposure_status():
    """Get current exposure and risk status."""
    try:
        engine = get_risk_engine()

        return ExposureStatusResponse(
            total_exposure_pct=engine.exposure_controller.get_current_exposure(),
            available_exposure_pct=engine.exposure_controller.get_available_exposure(),
            used_margin=engine.exposure_controller.used_margin,
            current_drawdown_pct=engine.exposure_controller.current_drawdown_pct,
            daily_pnl=engine.exposure_controller.daily_pnl,
            positions_count=len(engine.exposure_controller.positions),
            active_stops_count=len(engine.stop_loss_manager.active_stops),
            is_trading_allowed=engine.is_trading_allowed(),
            violations=[
                v.to_dict() for v in engine.exposure_controller.violations_today
            ],
        )

    except Exception as e:
        logger.error(f"Exposure status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=RiskEngineStatusResponse)
async def get_risk_engine_status():
    """Get full risk engine status."""
    try:
        engine = get_risk_engine()
        status = engine.get_status()

        return RiskEngineStatusResponse(**status)

    except Exception as e:
        logger.error(f"Risk engine status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshot")
async def get_risk_snapshot():
    """Get current portfolio risk snapshot."""
    try:
        engine = get_risk_engine()
        snapshot = engine.get_risk_snapshot()

        return snapshot.to_dict()

    except Exception as e:
        logger.error(f"Risk snapshot error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_risk_history(
    limit: int = Query(100, ge=1, le=1000, description="Number of snapshots"),
):
    """Get risk history snapshots."""
    try:
        engine = get_risk_engine()
        history = engine.get_risk_history(limit=limit)

        return {"count": len(history), "snapshots": [s.to_dict() for s in history]}

    except Exception as e:
        logger.error(f"Risk history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Control Endpoints
# ============================================================================


@router.post("/equity/update")
async def update_equity(request: UpdateEquityRequest):
    """Update account equity in risk engine."""
    try:
        engine = get_risk_engine()
        engine.update_equity(request.equity)

        return {
            "success": True,
            "new_equity": request.equity,
            "current_exposure_pct": engine.exposure_controller.get_current_exposure(),
            "current_drawdown_pct": engine.exposure_controller.current_drawdown_pct,
        }

    except Exception as e:
        logger.error(f"Update equity error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade/register")
async def register_trade(request: RegisterTradeRequest):
    """Register an executed trade with the risk engine."""
    try:
        engine = get_risk_engine()

        engine.register_trade(
            symbol=request.symbol,
            side=request.side,
            size=request.size,
            entry_price=request.entry_price,
            leverage=request.leverage,
            stop_loss=request.stop_loss,
        )

        return {
            "success": True,
            "message": f"Trade registered: {request.symbol} {request.side}",
            "positions_count": len(engine.exposure_controller.positions),
            "exposure_pct": engine.exposure_controller.get_current_exposure(),
        }

    except Exception as e:
        logger.error(f"Register trade error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/position/close/{symbol}")
async def close_position(symbol: str, exit_price: float = Query(..., gt=0)):
    """Close a position and remove from risk tracking."""
    try:
        engine = get_risk_engine()
        engine.close_position(symbol, exit_price)

        return {
            "success": True,
            "message": f"Position closed: {symbol}",
            "remaining_positions": len(engine.exposure_controller.positions),
        }

    except Exception as e:
        logger.error(f"Close position error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/price/update")
async def update_price(request: UpdatePriceRequest):
    """Update symbol price for stop loss checking."""
    try:
        engine = get_risk_engine()
        triggered = engine.update_price(request.symbol, request.price)

        return {
            "success": True,
            "symbol": request.symbol,
            "price": request.price,
            "stop_triggered": triggered is not None,
            "triggered_details": triggered.to_dict() if triggered else None,
        }

    except Exception as e:
        logger.error(f"Update price error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trading/pause")
async def pause_trading(reason: str = Query(..., description="Reason for pausing")):
    """Pause all trading."""
    try:
        engine = get_risk_engine()
        engine.pause_trading(reason)

        return {"success": True, "trading_paused": True, "reason": reason}

    except Exception as e:
        logger.error(f"Pause trading error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trading/resume")
async def resume_trading():
    """Resume trading."""
    try:
        engine = get_risk_engine()
        engine.resume_trading()

        return {"success": True, "trading_paused": False}

    except Exception as e:
        logger.error(f"Resume trading error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/daily/reset")
async def reset_daily_tracking():
    """Reset daily tracking (call at start of trading day)."""
    try:
        engine = get_risk_engine()
        engine.reset_daily()

        return {
            "success": True,
            "message": "Daily tracking reset",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Reset daily error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Configuration Endpoints
# ============================================================================


@router.get("/config")
async def get_risk_config():
    """Get current risk engine configuration."""
    try:
        engine = get_risk_engine()

        return {
            "sizing": {
                "method": engine.config.sizing_method.value,
                "risk_per_trade_pct": engine.config.risk_per_trade_pct,
                "max_position_size_pct": engine.config.max_position_size_pct,
            },
            "stops": {
                "default_stop_type": engine.config.default_stop_type.value,
                "default_stop_pct": engine.config.default_stop_pct,
                "trailing_offset_pct": engine.config.trailing_offset_pct,
            },
            "exposure": {
                "max_total_exposure_pct": engine.config.max_total_exposure_pct,
                "max_leverage": engine.config.max_leverage,
                "max_drawdown_pct": engine.config.max_drawdown_pct,
                "daily_loss_limit_pct": engine.config.daily_loss_limit_pct,
            },
            "validation": {
                "min_balance": engine.config.min_balance,
                "max_trades_per_day": engine.config.max_trades_per_day,
                "min_risk_reward": engine.config.min_risk_reward,
            },
        }

    except Exception as e:
        logger.error(f"Get config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/limits")
async def update_risk_limits(request: RiskLimitsRequest):
    """Update risk limits."""
    try:
        engine = get_risk_engine()

        # Update exposure limits
        engine.exposure_controller.limits.max_position_size_pct = (
            request.max_position_size_pct
        )
        engine.exposure_controller.limits.max_total_exposure_pct = (
            request.max_total_exposure_pct
        )
        engine.exposure_controller.limits.max_leverage = request.max_leverage
        engine.exposure_controller.limits.max_drawdown_pct = request.max_drawdown_pct
        engine.exposure_controller.limits.daily_loss_limit_pct = (
            request.daily_loss_limit_pct
        )

        # Update config
        engine.config.max_position_size_pct = request.max_position_size_pct
        engine.config.max_total_exposure_pct = request.max_total_exposure_pct
        engine.config.max_leverage = request.max_leverage
        engine.config.max_drawdown_pct = request.max_drawdown_pct
        engine.config.daily_loss_limit_pct = request.daily_loss_limit_pct

        return {
            "success": True,
            "message": "Risk limits updated",
            "new_limits": {
                "max_position_size_pct": request.max_position_size_pct,
                "max_total_exposure_pct": request.max_total_exposure_pct,
                "max_leverage": request.max_leverage,
                "max_drawdown_pct": request.max_drawdown_pct,
                "daily_loss_limit_pct": request.daily_loss_limit_pct,
            },
        }

    except Exception as e:
        logger.error(f"Update limits error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/engine/reset")
async def reset_risk_engine(
    profile: str = Query("moderate", pattern="^(conservative|moderate|aggressive)$"),
):
    """Reset risk engine with a new profile."""
    global _risk_engine

    try:
        equity = 10000.0
        if _risk_engine:
            equity = _risk_engine.exposure_controller.equity

        if profile == "conservative":
            _risk_engine = create_conservative_risk_engine(equity)
        elif profile == "aggressive":
            _risk_engine = create_aggressive_risk_engine(equity)
        else:
            _risk_engine = create_moderate_risk_engine(equity)

        return {
            "success": True,
            "message": f"Risk engine reset with {profile} profile",
            "profile": profile,
            "equity": equity,
        }

    except Exception as e:
        logger.error(f"Reset engine error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
