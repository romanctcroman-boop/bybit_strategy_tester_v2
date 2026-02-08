"""
Risk Dashboard Router
Provides API endpoints for risk monitoring and management.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services.risk_dashboard import (
    PositionRisk,
    RiskLevel,
    get_risk_dashboard,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/risk", tags=["Risk Management"])


# ============================================================================
# Request/Response Models
# ============================================================================


class PositionRiskRequest(BaseModel):
    """Request to update a position."""

    symbol: str
    side: str = Field(..., pattern="^(long|short)$")
    size: float
    entry_price: float
    current_price: float
    leverage: float = 1.0
    stop_loss: float | None = None
    take_profit: float | None = None


class PositionRiskResponse(BaseModel):
    """Position risk information."""

    symbol: str
    side: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    exposure: float
    exposure_pct: float
    risk_score: float
    leverage: float
    stop_loss: float | None = None
    take_profit: float | None = None


class PortfolioRiskResponse(BaseModel):
    """Portfolio risk metrics."""

    total_equity: float
    total_exposure: float
    exposure_pct: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    realized_pnl_today: float
    max_drawdown: float
    current_drawdown: float
    var_95: float
    var_99: float
    sharpe_ratio: float
    sortino_ratio: float
    win_rate: float
    profit_factor: float
    risk_score: float
    positions_count: int
    open_orders_count: int


class RiskAlertResponse(BaseModel):
    """Risk alert information."""

    id: str
    alert_type: str
    level: str
    message: str
    value: float
    threshold: float
    timestamp: str
    strategy_id: str | None = None
    acknowledged: bool


class RiskSummaryResponse(BaseModel):
    """Risk summary."""

    overall_risk_level: str
    risk_score: float
    portfolio: dict[str, Any]
    positions_count: int
    active_alerts: int
    critical_alerts: int
    thresholds: dict[str, float]
    last_update: str | None = None


class ThresholdsRequest(BaseModel):
    """Request to update risk thresholds."""

    max_drawdown_pct: float | None = Field(None, ge=0, le=100)
    max_exposure_pct: float | None = Field(None, ge=0, le=500)
    max_position_size_pct: float | None = Field(None, ge=0, le=100)
    max_daily_loss_pct: float | None = Field(None, ge=0, le=100)
    max_correlation: float | None = Field(None, ge=0, le=1)
    min_liquidity_ratio: float | None = Field(None, ge=0, le=1)


class TradeRecordRequest(BaseModel):
    """Request to record a trade."""

    symbol: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    fees: float = 0.0


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/summary", response_model=RiskSummaryResponse)
async def get_risk_summary():
    """
    Get comprehensive risk summary.

    Returns:
        Overall risk level, score, and key metrics
    """
    try:
        dashboard = get_risk_dashboard()
        summary = dashboard.get_risk_summary()
        return RiskSummaryResponse(**summary)
    except Exception as e:
        logger.error(f"Error getting risk summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio", response_model=PortfolioRiskResponse)
async def get_portfolio_risk():
    """
    Get current portfolio risk metrics.

    Returns:
        Detailed portfolio risk analysis
    """
    try:
        dashboard = get_risk_dashboard()
        portfolio = dashboard.get_portfolio_risk()

        return PortfolioRiskResponse(
            total_equity=portfolio.total_equity,
            total_exposure=portfolio.total_exposure,
            exposure_pct=portfolio.exposure_pct,
            unrealized_pnl=portfolio.unrealized_pnl,
            unrealized_pnl_pct=portfolio.unrealized_pnl_pct,
            realized_pnl_today=portfolio.realized_pnl_today,
            max_drawdown=portfolio.max_drawdown,
            current_drawdown=portfolio.current_drawdown,
            var_95=portfolio.var_95,
            var_99=portfolio.var_99,
            sharpe_ratio=portfolio.sharpe_ratio,
            sortino_ratio=portfolio.sortino_ratio,
            win_rate=portfolio.win_rate,
            profit_factor=portfolio.profit_factor,
            risk_score=portfolio.risk_score,
            positions_count=portfolio.positions_count,
            open_orders_count=portfolio.open_orders_count,
        )
    except Exception as e:
        logger.error(f"Error getting portfolio risk: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions", response_model=list[PositionRiskResponse])
async def get_positions():
    """
    Get risk metrics for all open positions.

    Returns:
        List of position risk information
    """
    try:
        dashboard = get_risk_dashboard()
        positions = []

        for pos in dashboard.positions.values():
            positions.append(
                PositionRiskResponse(
                    symbol=pos.symbol,
                    side=pos.side,
                    size=pos.size,
                    entry_price=pos.entry_price,
                    current_price=pos.current_price,
                    unrealized_pnl=pos.unrealized_pnl,
                    unrealized_pnl_pct=pos.unrealized_pnl_pct,
                    exposure=pos.exposure,
                    exposure_pct=pos.exposure_pct,
                    risk_score=pos.risk_score,
                    leverage=pos.leverage,
                    stop_loss=pos.stop_loss,
                    take_profit=pos.take_profit,
                )
            )

        return positions
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/positions")
async def update_position(request: PositionRiskRequest):
    """
    Update or add a position for risk tracking.

    Args:
        request: Position details

    Returns:
        Updated position risk metrics
    """
    try:
        dashboard = get_risk_dashboard()
        total_equity = (
            dashboard.equity_history[-1] if dashboard.equity_history else 10000.0
        )

        # Calculate metrics
        pnl_multiplier = 1 if request.side == "long" else -1
        unrealized_pnl = (
            (request.current_price - request.entry_price)
            * request.size
            * pnl_multiplier
        )
        unrealized_pnl_pct = (
            (unrealized_pnl / (request.entry_price * request.size) * 100)
            if request.entry_price > 0
            else 0
        )
        exposure = request.current_price * request.size * request.leverage
        exposure_pct = (exposure / total_equity * 100) if total_equity > 0 else 0

        # Simple risk score
        risk_score = min(100, exposure_pct * 0.5 + abs(unrealized_pnl_pct) * 0.5)

        position = PositionRisk(
            symbol=request.symbol,
            side=request.side,
            size=request.size,
            entry_price=request.entry_price,
            current_price=request.current_price,
            unrealized_pnl=round(unrealized_pnl, 2),
            unrealized_pnl_pct=round(unrealized_pnl_pct, 2),
            exposure=round(exposure, 2),
            exposure_pct=round(exposure_pct, 2),
            risk_score=round(risk_score, 2),
            leverage=request.leverage,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
        )

        dashboard.update_position(position)

        return {
            "success": True,
            "message": f"Position {request.symbol} updated",
            "position": {
                "symbol": position.symbol,
                "risk_score": position.risk_score,
                "exposure_pct": position.exposure_pct,
            },
        }
    except Exception as e:
        logger.error(f"Error updating position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/positions/{symbol}")
async def remove_position(symbol: str):
    """
    Remove a position from risk tracking.

    Args:
        symbol: Position symbol

    Returns:
        Confirmation of removal
    """
    try:
        dashboard = get_risk_dashboard()
        dashboard.remove_position(symbol)
        return {"success": True, "message": f"Position {symbol} removed"}
    except Exception as e:
        logger.error(f"Error removing position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/equity")
async def update_equity(equity: float = Query(..., gt=0)):
    """
    Update current equity value.

    Args:
        equity: Current equity value

    Returns:
        Confirmation with updated metrics
    """
    try:
        dashboard = get_risk_dashboard()
        dashboard.update_equity(equity)

        return {
            "success": True,
            "equity": equity,
            "data_points": len(dashboard.equity_history),
        }
    except Exception as e:
        logger.error(f"Error updating equity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trades")
async def record_trade(request: TradeRecordRequest):
    """
    Record a completed trade for statistics.

    Args:
        request: Trade details

    Returns:
        Confirmation with updated statistics
    """
    try:
        dashboard = get_risk_dashboard()
        dashboard.record_trade(
            {
                "symbol": request.symbol,
                "side": request.side,
                "entry_price": request.entry_price,
                "exit_price": request.exit_price,
                "size": request.size,
                "pnl": request.pnl,
                "fees": request.fees,
            }
        )

        return {
            "success": True,
            "message": "Trade recorded",
            "total_trades": len(dashboard.trades_history),
        }
    except Exception as e:
        logger.error(f"Error recording trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts", response_model=list[RiskAlertResponse])
async def get_alerts(
    unacknowledged: bool = Query(False, description="Only show unacknowledged alerts"),
    level: str | None = Query(None, description="Filter by risk level"),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Get risk alerts.

    Args:
        unacknowledged: Filter to only unacknowledged alerts
        level: Filter by risk level
        limit: Maximum number of alerts

    Returns:
        List of risk alerts
    """
    try:
        dashboard = get_risk_dashboard()

        risk_level = None
        if level:
            try:
                risk_level = RiskLevel(level.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid risk level. Must be one of: {[lv.value for lv in RiskLevel]}",
                )

        alerts = dashboard.get_alerts(
            unacknowledged_only=unacknowledged,
            level=risk_level,
            limit=limit,
        )

        return [RiskAlertResponse(**a.to_dict()) for a in alerts]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """
    Acknowledge a risk alert.

    Args:
        alert_id: Alert ID to acknowledge

    Returns:
        Confirmation of acknowledgment
    """
    try:
        dashboard = get_risk_dashboard()
        success = dashboard.acknowledge_alert(alert_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        return {"success": True, "message": f"Alert {alert_id} acknowledged"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-alerts")
async def check_portfolio_alerts():
    """
    Manually trigger portfolio alert checks.

    Returns:
        Number of new alerts generated
    """
    try:
        dashboard = get_risk_dashboard()
        before_count = len(dashboard.alerts)
        dashboard.check_portfolio_alerts()
        new_alerts = len(dashboard.alerts) - before_count

        return {
            "success": True,
            "new_alerts": new_alerts,
            "total_alerts": len(dashboard.alerts),
        }
    except Exception as e:
        logger.error(f"Error checking alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/thresholds")
async def get_thresholds():
    """
    Get current risk thresholds.

    Returns:
        Current threshold configuration
    """
    try:
        dashboard = get_risk_dashboard()
        t = dashboard.thresholds

        return {
            "max_drawdown_pct": t.max_drawdown_pct,
            "max_exposure_pct": t.max_exposure_pct,
            "max_position_size_pct": t.max_position_size_pct,
            "max_daily_loss_pct": t.max_daily_loss_pct,
            "max_correlation": t.max_correlation,
            "min_liquidity_ratio": t.min_liquidity_ratio,
            "var_confidence": t.var_confidence,
            "volatility_lookback_days": t.volatility_lookback_days,
        }
    except Exception as e:
        logger.error(f"Error getting thresholds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/thresholds")
async def update_thresholds(request: ThresholdsRequest):
    """
    Update risk thresholds.

    Args:
        request: New threshold values

    Returns:
        Updated thresholds
    """
    try:
        dashboard = get_risk_dashboard()
        t = dashboard.thresholds

        if request.max_drawdown_pct is not None:
            t.max_drawdown_pct = request.max_drawdown_pct
        if request.max_exposure_pct is not None:
            t.max_exposure_pct = request.max_exposure_pct
        if request.max_position_size_pct is not None:
            t.max_position_size_pct = request.max_position_size_pct
        if request.max_daily_loss_pct is not None:
            t.max_daily_loss_pct = request.max_daily_loss_pct
        if request.max_correlation is not None:
            t.max_correlation = request.max_correlation
        if request.min_liquidity_ratio is not None:
            t.min_liquidity_ratio = request.min_liquidity_ratio

        return {
            "success": True,
            "message": "Thresholds updated",
            "thresholds": {
                "max_drawdown_pct": t.max_drawdown_pct,
                "max_exposure_pct": t.max_exposure_pct,
                "max_position_size_pct": t.max_position_size_pct,
                "max_daily_loss_pct": t.max_daily_loss_pct,
            },
        }
    except Exception as e:
        logger.error(f"Error updating thresholds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_service_metrics():
    """
    Get risk dashboard service metrics.

    Returns:
        Service metrics and statistics
    """
    try:
        dashboard = get_risk_dashboard()
        return dashboard.get_metrics()
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
