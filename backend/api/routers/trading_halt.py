"""
Trading Halt API Router.

Provides REST API for trading halt management and emergency stop.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.trading_halt import (
    HaltLevel,
    HaltReason,
    RiskMetrics,
    get_trading_halt_service,
)

router = APIRouter(prefix="/api/v1/trading-halt")


# ============================================================
# Request/Response Models
# ============================================================


class EmergencyStopRequest(BaseModel):
    """Request for emergency stop."""

    reason: str = "Manual emergency stop"
    triggered_by: str = "api"


class HaltTradingRequest(BaseModel):
    """Request to halt trading."""

    reason: str  # HaltReason value
    level: str = "hard"  # HaltLevel value
    triggered_by: str = "api"
    duration_minutes: Optional[int] = None
    message: Optional[str] = None


class ResumeRequest(BaseModel):
    """Request to resume trading."""

    resumed_by: str = "api"
    force: bool = False


class ValidateTradeRequest(BaseModel):
    """Request to validate a trade."""

    trade_type: str  # "open" or "close"
    position_size: float
    current_equity: float


class UpdateConfigRequest(BaseModel):
    """Request to update halt configuration."""

    max_daily_loss_pct: Optional[float] = None
    max_weekly_loss_pct: Optional[float] = None
    max_trade_loss_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    max_open_positions: Optional[int] = None
    max_position_size_pct: Optional[float] = None
    max_total_exposure_pct: Optional[float] = None
    volatility_threshold: Optional[float] = None
    auto_recovery_enabled: Optional[bool] = None
    recovery_cooldown_minutes: Optional[int] = None


class RiskMetricsRequest(BaseModel):
    """Request to update risk metrics."""

    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    weekly_pnl: float = 0.0
    weekly_pnl_pct: float = 0.0
    current_drawdown_pct: float = 0.0
    peak_equity: float = 0.0
    current_equity: float = 0.0
    open_positions: int = 0
    total_exposure: float = 0.0
    total_exposure_pct: float = 0.0
    largest_position_pct: float = 0.0


class HaltEventResponse(BaseModel):
    """Response for a halt event."""

    id: str
    reason: str
    level: str
    timestamp: str
    triggered_by: str
    details: dict
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None


class TradingStatusResponse(BaseModel):
    """Response for trading status."""

    trading_status: str
    halt_level: Optional[str]
    halt_reason: Optional[str]
    halted_at: Optional[str]
    halted_by: Optional[str]
    resume_at: Optional[str]
    message: str
    can_open_positions: bool
    can_close_positions: bool


# ============================================================
# API Endpoints
# ============================================================


@router.get("/status", response_model=TradingStatusResponse)
async def get_trading_status():
    """Get current trading halt status."""
    service = get_trading_halt_service()
    status = service.get_status()
    return TradingStatusResponse(**status)


@router.post("/emergency-stop", response_model=HaltEventResponse)
async def emergency_stop(request: EmergencyStopRequest):
    """
    Trigger emergency stop - immediately halts ALL trading.

    This is the most severe action - use only in emergencies.
    """
    service = get_trading_halt_service()

    event = await service.emergency_stop(
        reason=request.reason,
        triggered_by=request.triggered_by,
    )

    return HaltEventResponse(
        id=event.id,
        reason=event.reason.value,
        level=event.level.value,
        timestamp=event.timestamp.isoformat(),
        triggered_by=event.triggered_by,
        details=event.details,
    )


@router.post("/halt", response_model=HaltEventResponse)
async def halt_trading(request: HaltTradingRequest):
    """Halt trading with specified level and reason."""
    service = get_trading_halt_service()

    # Validate reason
    try:
        reason = HaltReason(request.reason)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reason: {request.reason}. Valid: {[r.value for r in HaltReason]}",
        )

    # Validate level
    try:
        level = HaltLevel(request.level)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level: {request.level}. Valid: {[lv.value for lv in HaltLevel]}",
        )

    details = {}
    if request.message:
        details["message"] = request.message

    event = await service.halt_trading(
        reason=reason,
        level=level,
        triggered_by=request.triggered_by,
        duration_minutes=request.duration_minutes,
        details=details,
    )

    return HaltEventResponse(
        id=event.id,
        reason=event.reason.value,
        level=event.level.value,
        timestamp=event.timestamp.isoformat(),
        triggered_by=event.triggered_by,
        details=event.details,
    )


@router.post("/resume")
async def resume_trading(request: ResumeRequest):
    """Resume trading after a halt."""
    service = get_trading_halt_service()

    success = await service.resume_trading(
        resumed_by=request.resumed_by,
        force=request.force,
    )

    if success:
        return {"status": "resumed", "resumed_by": request.resumed_by}
    else:
        raise HTTPException(
            status_code=400,
            detail="Cannot resume trading - cooldown active. Use force=true to override.",
        )


@router.post("/validate-trade")
async def validate_trade(request: ValidateTradeRequest):
    """Validate if a trade is allowed."""
    service = get_trading_halt_service()

    allowed, reason = service.validate_trade(
        trade_type=request.trade_type,
        position_size=request.position_size,
        current_equity=request.current_equity,
    )

    return {
        "allowed": allowed,
        "reason": reason,
        "trade_type": request.trade_type,
    }


@router.get("/can-trade")
async def can_trade():
    """Quick check if trading is currently allowed."""
    service = get_trading_halt_service()

    can_open, open_reason = service.can_open_position()
    can_close, close_reason = service.can_close_position()

    return {
        "can_open_positions": can_open,
        "open_reason": open_reason,
        "can_close_positions": can_close,
        "close_reason": close_reason,
    }


@router.get("/config")
async def get_config():
    """Get current halt configuration."""
    service = get_trading_halt_service()
    return service.get_config()


@router.put("/config")
async def update_config(request: UpdateConfigRequest):
    """Update halt configuration."""
    service = get_trading_halt_service()

    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(
            status_code=400,
            detail="No configuration values provided",
        )

    return service.update_config(**updates)


@router.get("/events", response_model=list[HaltEventResponse])
async def get_events(
    limit: int = 50,
    include_resolved: bool = True,
):
    """Get halt event history."""
    service = get_trading_halt_service()
    events = service.get_events(limit=limit, include_resolved=include_resolved)
    return [HaltEventResponse(**e) for e in events]


@router.get("/events/active", response_model=list[HaltEventResponse])
async def get_active_events():
    """Get currently active (unresolved) halt events."""
    service = get_trading_halt_service()
    events = service.get_events(include_resolved=False)
    return [HaltEventResponse(**e) for e in events]


@router.get("/risk-metrics")
async def get_risk_metrics():
    """Get current risk metrics."""
    service = get_trading_halt_service()
    return service.get_risk_metrics()


@router.post("/risk-metrics")
async def update_risk_metrics(request: RiskMetricsRequest):
    """Update risk metrics and check for auto-halt triggers."""
    service = get_trading_halt_service()

    metrics = RiskMetrics(
        daily_pnl=request.daily_pnl,
        daily_pnl_pct=request.daily_pnl_pct,
        weekly_pnl=request.weekly_pnl,
        weekly_pnl_pct=request.weekly_pnl_pct,
        current_drawdown_pct=request.current_drawdown_pct,
        peak_equity=request.peak_equity,
        current_equity=request.current_equity,
        open_positions=request.open_positions,
        total_exposure=request.total_exposure,
        total_exposure_pct=request.total_exposure_pct,
        largest_position_pct=request.largest_position_pct,
    )

    halt_event = await service.update_risk_metrics(metrics)

    if halt_event:
        return {
            "halt_triggered": True,
            "event": HaltEventResponse(
                id=halt_event.id,
                reason=halt_event.reason.value,
                level=halt_event.level.value,
                timestamp=halt_event.timestamp.isoformat(),
                triggered_by=halt_event.triggered_by,
                details=halt_event.details,
            ).model_dump(),
        }

    return {"halt_triggered": False, "metrics_updated": True}


@router.get("/halt-reasons")
async def list_halt_reasons():
    """List all available halt reasons."""
    return [
        {"value": r.value, "description": r.name.replace("_", " ").title()}
        for r in HaltReason
    ]


@router.get("/halt-levels")
async def list_halt_levels():
    """List all available halt levels."""
    return [
        {
            "value": "soft",
            "description": "Warning level - allows manual override, limits new positions",
        },
        {
            "value": "hard",
            "description": "Block new positions, only allow closing existing",
        },
        {
            "value": "emergency",
            "description": "Block all trading activity immediately",
        },
    ]


@router.get("/summary")
async def get_trading_halt_summary():
    """Get comprehensive trading halt summary."""
    service = get_trading_halt_service()

    status = service.get_status()
    config = service.get_config()
    metrics = service.get_risk_metrics()
    events = service.get_events(limit=5)

    return {
        "current_status": status["trading_status"],
        "is_halted": status["trading_status"] != "active",
        "halt_level": status["halt_level"],
        "halt_reason": status["halt_reason"],
        "can_trade": {
            "open": status["can_open_positions"],
            "close": status["can_close_positions"],
        },
        "risk_summary": {
            "daily_pnl_pct": metrics["daily_pnl_pct"],
            "drawdown_pct": metrics["current_drawdown_pct"],
            "open_positions": metrics["open_positions"],
            "exposure_pct": metrics["total_exposure_pct"],
        },
        "limits": {
            "max_daily_loss_pct": config["max_daily_loss_pct"],
            "max_drawdown_pct": config["max_drawdown_pct"],
            "max_positions": config["max_open_positions"],
        },
        "recent_events": len(events),
        "auto_recovery_enabled": config["auto_recovery_enabled"],
    }
