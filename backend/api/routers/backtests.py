"""
Backtests Router
Endpoints for managing and executing strategy backtests.

Provides real backtesting functionality using vectorbt engine.
Integrates with Strategies CRUD for running backtests from saved strategies.
"""

from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field, ValidationError
from pydantic_core import ValidationError as PydanticCoreValidationError
from sqlalchemy.orm import Session

from backend.backtesting.engine import get_engine
from backend.backtesting.interfaces import TradeDirection
from backend.backtesting.models import (
    BacktestConfig,
    BacktestCreateRequest,
    BacktestListResponse,
    BacktestResult,
    BacktestStatus,
    EquityCurve,
    PerformanceMetrics,
    StrategyType,
    TradeRecord,
)
from backend.backtesting.service import get_backtest_service
from backend.backtesting.strategies import list_available_strategies
from backend.database import get_db
from backend.database.models import Backtest as BacktestModel
from backend.database.models import BacktestStatus as DBBacktestStatus
from backend.database.models import Strategy

router = APIRouter(tags=["Backtests"])


def _get_side_value(side: Any) -> str:
    """Safely extract side value from enum or return string representation."""
    if side is None:
        return "unknown"
    if hasattr(side, "value"):
        return str(side.value)
    return str(side)


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert SQLAlchemy Column or other value to float."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert SQLAlchemy Column or other value to int."""
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _safe_str(val: Any, default: str = "") -> str:
    """Safely convert SQLAlchemy Column or other value to str."""
    if val is None:
        return default
    return str(val)


def downsample_list(data: list, max_points: int = 500) -> list:
    """Evenly downsample a list to max_points, keeping first and last."""
    if not data or len(data) <= max_points:
        return data

    # Always include first and last points
    step = (len(data) - 1) / (max_points - 1)
    indices = [int(i * step) for i in range(max_points - 1)]
    indices.append(len(data) - 1)  # Ensure last point is included

    return [data[i] for i in indices]


def build_equity_curve_response(
    equity_curve: EquityCurve, trades: list | None = None, max_points: int = 800
) -> dict[str, Any] | None:
    """Build equity curve response with one point per trade exit.

    Returns equity value at the moment each trade closes.
    Number of points = number of trades (like TradingView).
    """
    if not equity_curve:
        return None

    timestamps = equity_curve.timestamps or []
    equity = equity_curve.equity or []
    drawdown = equity_curve.drawdown or []
    bh_equity = equity_curve.bh_equity or []
    bh_drawdown = equity_curve.bh_drawdown or []

    n = len(timestamps)
    if n == 0:
        return None

    # If no trades, return start and end points only
    if not trades or len(trades) == 0:
        return {
            "timestamps": [
                timestamps[0].isoformat() if hasattr(timestamps[0], "isoformat") else str(timestamps[0]),
                timestamps[-1].isoformat() if hasattr(timestamps[-1], "isoformat") else str(timestamps[-1]),
            ],
            "equity": [float(equity[0]), float(equity[-1])] if equity else [],
            "drawdown": [float(drawdown[0]), float(drawdown[-1])] if drawdown else [],
            "bh_equity": [float(bh_equity[0]), float(bh_equity[-1])] if bh_equity else [],
            "bh_drawdown": [float(bh_drawdown[0]), float(bh_drawdown[-1])] if bh_drawdown else [],
        }

    # Create timestamp -> index mapping for fast lookup
    ts_to_idx = {}
    for i, ts in enumerate(timestamps):
        ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        # Normalize: remove timezone suffix variations
        ts_str = ts_str.replace("+00:00", "Z").rstrip("Z") + "Z"
        ts_to_idx[ts_str] = i
        # Also add without Z for matching
        ts_to_idx[ts_str.rstrip("Z")] = i

    # Collect indices for trade EXIT times only (one point per closed trade)
    exit_indices = []
    for trade in trades:
        exit_time = trade.exit_time if hasattr(trade, "exit_time") else trade.get("exit_time")

        if exit_time:
            exit_str = exit_time.isoformat() if hasattr(exit_time, "isoformat") else str(exit_time)
            # Normalize
            exit_str_z = exit_str.replace("+00:00", "Z").rstrip("Z") + "Z"
            exit_str_no_z = exit_str.rstrip("Z").replace("+00:00", "")

            idx = ts_to_idx.get(exit_str_z) or ts_to_idx.get(exit_str_no_z)
            if idx is not None:
                exit_indices.append(idx)

    # If we couldn't match any trades, fallback to first/last
    if not exit_indices:
        return {
            "timestamps": [
                timestamps[0].isoformat() if hasattr(timestamps[0], "isoformat") else str(timestamps[0]),
                timestamps[-1].isoformat() if hasattr(timestamps[-1], "isoformat") else str(timestamps[-1]),
            ],
            "equity": [float(equity[0]), float(equity[-1])] if equity else [],
            "drawdown": [float(drawdown[0]), float(drawdown[-1])] if drawdown else [],
            "bh_equity": [],
            "bh_drawdown": [],
        }

    # Sort indices chronologically
    indices = sorted(set(exit_indices))

    return {
        "timestamps": [
            timestamps[i].isoformat() if hasattr(timestamps[i], "isoformat") else str(timestamps[i])
            for i in indices
            if i < len(timestamps)
        ],
        "equity": [float(equity[i]) for i in indices if i < len(equity)],
        "drawdown": [float(drawdown[i]) for i in indices if i < len(drawdown)],
        "bh_equity": [float(bh_equity[i]) for i in indices if i < len(bh_equity)] if bh_equity else [],
        "bh_drawdown": [float(bh_drawdown[i]) for i in indices if i < len(bh_drawdown)] if bh_drawdown else [],
    }


# ============================================================================
# ENGINE SELECTION ENDPOINTS
# ============================================================================


@router.get("/engines")
async def list_available_engines():
    """
    List all available backtest engines and their capabilities.

    Returns information about each engine:
    - Availability (installed and working)
    - Description and acceleration type
    - Bar Magnifier support

    All engines produce 100% identical results (147-metric parity verified).
    The choice affects performance only, not accuracy.
    """
    from backend.backtesting.engine_selector import get_available_engines

    engines = get_available_engines()

    return {
        "engines": engines,
        "recommended": "gpu"
        if engines.get("gpu", {}).get("available")
        else ("numba" if engines.get("numba", {}).get("available") else "fallback"),
        "note": "All engines produce 100% identical results (bit-level parity verified)",
    }


class RunFromStrategyRequest(BaseModel):
    """Request to run backtest from a saved strategy"""

    symbol: str | None = Field(default=None, description="Override strategy's symbol")
    interval: str | None = Field(default=None, description="Override strategy's timeframe")
    start_date: datetime = Field(..., description="Backtest start date")
    end_date: datetime = Field(..., description="Backtest end date")
    initial_capital: float | None = Field(default=None, ge=100, description="Override strategy's initial capital")
    position_size: float | None = Field(default=None, ge=0.01, le=1.0, description="Override position size")
    save_result: bool = Field(default=True, description="Save result to database and update strategy metrics")


class RunFromStrategyResponse(BaseModel):
    """Response from running backtest from strategy"""

    backtest_id: str
    strategy_id: str
    strategy_name: str
    status: str
    metrics: dict | None = None
    error_message: str | None = None
    saved_to_db: bool = False


@router.post("/", response_model=BacktestResult)
async def create_backtest(request: BacktestCreateRequest):
    """
    Create and run a new backtest.

    Executes the selected strategy on historical data and returns
    comprehensive performance metrics, trades, and equity curve.

    **Example Request:**
    ```json
    {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-06-01T00:00:00Z",
        "strategy_type": "sma_crossover",
        "strategy_params": {"fast_period": 10, "slow_period": 30},
        "initial_capital": 10000,
        "position_size": 0.5
    }
    ```

    **Available Strategies:**
    - `sma_crossover`: SMA Crossover (fast_period, slow_period)
    - `rsi`: RSI Strategy (period, oversold, overbought)
    - `macd`: MACD Strategy (fast_period, slow_period, signal_period)
    - `bollinger_bands`: Bollinger Bands (period, std_dev)
    """
    logger.info(f"Creating backtest: {request.symbol} {request.interval} strategy={request.strategy_type}")

    # Extract commission/slippage from strategy_params if provided
    params = request.strategy_params or {}
    commission = float(params.get("_commission", 0.0007))  # 0.07% TradingView parity
    slippage = float(params.get("_slippage", 0.0005))  # Default 0.05%

    # Extract no_trade_days from strategy_params (UI sends as _no_trade_days)
    no_trade_days_raw = params.get("_no_trade_days", [])
    no_trade_days = tuple(no_trade_days_raw) if no_trade_days_raw else ()

    # Get direction from strategy_params if not explicitly set in request
    # This allows strategy-defined direction to be used automatically
    direction = request.direction
    if direction == "long" and params.get("_direction"):
        # If direction is default "long" but strategy has _direction, use strategy's
        direction = params.get("_direction", "long")
        logger.info(f"Using direction from strategy_params: {direction}")

    # Handle position size based on type (percent, fixed_amount, contracts)
    position_size_type = params.get("_position_size_type", "percent")
    order_amount = params.get("_order_amount")  # Fixed $ amount or contracts

    position_size: float = request.position_size
    if position_size_type == "fixed_amount" and order_amount:
        # Convert fixed $ amount to fraction of capital (with leverage)
        effective_order = float(order_amount) * float(request.leverage)
        position_size = min(effective_order / float(request.initial_capital), 1.0)
        logger.info(
            f"Using fixed order amount: ${order_amount} x {request.leverage}x = "
            f"${effective_order} = {position_size * 100:.1f}% of ${request.initial_capital}"
        )
    elif position_size_type == "contracts" and order_amount:
        # For contracts mode, pass through (engine will handle)
        position_size = float(order_amount)
        logger.info(f"Using fixed contracts: {order_amount}")

    # Build config with validation error handling
    try:
        config = BacktestConfig(
            symbol=request.symbol,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            strategy_type=request.strategy_type,
            strategy_params=request.strategy_params,
            initial_capital=request.initial_capital,
            position_size=position_size,
            leverage=request.leverage,
            direction=direction,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            taker_fee=commission,
            maker_fee=commission,
            slippage=slippage,
            no_trade_days=no_trade_days,
        )
    except (ValidationError, PydanticCoreValidationError) as e:
        # Return 422 for validation errors (standard FastAPI behavior)
        logger.warning(f"Backtest validation error: {e}")
        # Use string representation to avoid datetime serialization issues
        raise HTTPException(
            status_code=422,
            detail=str(e),
        )

    # Run backtest
    service = get_backtest_service()
    result = await service.run_backtest(config)

    if result.status == BacktestStatus.FAILED:
        logger.error(f"Backtest failed: {result.error_message}")
        raise HTTPException(
            status_code=400,
            detail=f"Backtest failed: {result.error_message}",
        )

    # Save to database if requested
    if request.save_to_db and result.metrics:
        try:
            from backend.database import get_db as get_db_session

            db = next(get_db_session())
            m = result.metrics

            # Build optimization_metrics for list_backtests to read
            optimization_metrics = {
                "max_runup": getattr(m, "max_runup", 0),
                "max_runup_value": getattr(m, "max_runup_value", 0),
                "net_profit": m.net_profit,
                "net_profit_pct": m.net_profit_pct,
                "gross_profit": m.gross_profit,
                "gross_loss": m.gross_loss,
                "avg_win": getattr(m, "avg_win", 0),
                "avg_loss": getattr(m, "avg_loss", 0),
                "best_trade": getattr(m, "best_trade", 0),
                "worst_trade": getattr(m, "worst_trade", 0),
                "avg_bars_in_trade": getattr(m, "avg_bars_in_trade", 0),
                "buy_hold_return": m.buy_hold_return,
                "buy_hold_return_pct": m.buy_hold_return_pct,
                # Long/Short breakdown metrics
                "long_trades": getattr(m, "long_trades", 0),
                "long_winning_trades": getattr(m, "long_winning_trades", 0),
                "long_losing_trades": getattr(m, "long_losing_trades", 0),
                "long_win_rate": getattr(m, "long_win_rate", 0),
                "long_gross_profit": getattr(m, "long_gross_profit", 0),
                "long_gross_loss": getattr(m, "long_gross_loss", 0),
                "long_net_profit": getattr(m, "long_net_profit", 0),
                "long_profit_factor": getattr(m, "long_profit_factor", 0),
                "long_avg_win": getattr(m, "long_avg_win", 0),
                "long_avg_loss": getattr(m, "long_avg_loss", 0),
                "short_trades": getattr(m, "short_trades", 0),
                "short_winning_trades": getattr(m, "short_winning_trades", 0),
                "short_losing_trades": getattr(m, "short_losing_trades", 0),
                "short_win_rate": getattr(m, "short_win_rate", 0),
                "short_gross_profit": getattr(m, "short_gross_profit", 0),
                "short_gross_loss": getattr(m, "short_gross_loss", 0),
                "short_net_profit": getattr(m, "short_net_profit", 0),
                "short_profit_factor": getattr(m, "short_profit_factor", 0),
                "short_avg_win": getattr(m, "short_avg_win", 0),
                "short_avg_loss": getattr(m, "short_avg_loss", 0),
                # Long/Short consecutive wins/losses (TradingView)
                "long_max_consec_wins": getattr(m, "long_max_consec_wins", 0),
                "long_max_consec_losses": getattr(m, "long_max_consec_losses", 0),
                "short_max_consec_wins": getattr(m, "short_max_consec_wins", 0),
                "short_max_consec_losses": getattr(m, "short_max_consec_losses", 0),
                # Long/Short payoff ratio and expectancy
                "long_payoff_ratio": getattr(m, "long_payoff_ratio", 0),
                "short_payoff_ratio": getattr(m, "short_payoff_ratio", 0),
                "long_expectancy": getattr(m, "long_expectancy", 0),
                "short_expectancy": getattr(m, "short_expectancy", 0),
                # Long/Short largest trades
                "long_largest_win": getattr(m, "long_largest_win_value", 0),
                "long_largest_loss": getattr(m, "long_largest_loss_value", 0),
                "short_largest_win": getattr(m, "short_largest_win_value", 0),
                "short_largest_loss": getattr(m, "short_largest_loss_value", 0),
                # Additional bar-based metrics
                "avg_bars_in_winning": getattr(m, "avg_bars_in_winning", 0),
                "avg_bars_in_losing": getattr(m, "avg_bars_in_losing", 0),
                "avg_bars_in_long": getattr(m, "avg_bars_in_long", 0),
                "avg_bars_in_short": getattr(m, "avg_bars_in_short", 0),
                "total_commission": getattr(m, "total_commission", 0),
            }
            # Normalize trades source: engines may return trades under different names
            trades_source = (
                result.trades or getattr(result, "all_trades", None) or getattr(result, "trade_list", None) or []
            )

            # Normalize trades into dicts suitable for DB storage
            trades_list: list[dict[str, Any]] = []
            for t in (trades_source or [])[:500]:
                if hasattr(t, "__dict__") and not isinstance(t, dict):
                    # object-like trade
                    entry_time = getattr(t, "entry_time", None)
                    exit_time = getattr(t, "exit_time", None)
                    side = getattr(t, "side", None)
                    trades_list.append(
                        {
                            "entry_time": entry_time.isoformat() if entry_time else None,
                            "exit_time": exit_time.isoformat() if exit_time else None,
                            "side": _get_side_value(side),
                            "entry_price": float(getattr(t, "entry_price", 0) or 0),
                            "exit_price": float(getattr(t, "exit_price", 0) or 0),
                            "size": float(getattr(t, "size", 1.0) or 1.0),
                            "pnl": float(getattr(t, "pnl", 0) or 0),
                            "pnl_pct": float(getattr(t, "pnl_pct", 0) or 0),
                            "fees": float(getattr(t, "fees", 0) or 0),
                            "duration_bars": int(getattr(t, "duration_bars", 0) or 0),
                            "mfe": float(getattr(t, "mfe", 0) or 0),
                            "mae": float(getattr(t, "mae", 0) or 0),
                        }
                    )
                elif isinstance(t, dict):
                    trades_list.append(
                        {
                            "entry_time": t.get("entry_time"),
                            "exit_time": t.get("exit_time"),
                            "side": t.get("side", "long"),
                            "entry_price": float(t.get("entry_price", 0) or 0),
                            "exit_price": float(t.get("exit_price", 0) or 0),
                            "size": float(t.get("size", 1.0) or 1.0),
                            "pnl": float(t.get("pnl", 0) or 0),
                            "pnl_pct": float(t.get("pnl_pct", 0) or 0),
                            "fees": float(t.get("fees", 0) or 0),
                            "duration_bars": int(t.get("duration_bars", 0) or 0),
                            "mfe": float(t.get("mfe", 0) or 0),
                            "mae": float(t.get("mae", 0) or 0),
                        }
                    )

            # Build equity curve payload for DB
            equity_payload = None
            ec_source = result.equity_curve or getattr(result, "equity", None)
            if ec_source:
                equity_payload = build_equity_curve_response(ec_source, trades_list)

            # Normalize trades source: engines may return trades under different names
            trades_source = (
                result.trades or getattr(result, "all_trades", None) or getattr(result, "trade_list", None) or []
            )

            # Normalize trades into dicts suitable for DB storage
            trades_list = []
            for t in (trades_source or [])[:500]:
                if hasattr(t, "__dict__") and not isinstance(t, dict):
                    # object-like trade
                    entry_time = getattr(t, "entry_time", None)
                    exit_time = getattr(t, "exit_time", None)
                    side = getattr(t, "side", None)
                    trades_list.append(
                        {
                            "entry_time": entry_time.isoformat() if entry_time else None,
                            "exit_time": exit_time.isoformat() if exit_time else None,
                            "side": _get_side_value(side),
                            "entry_price": float(getattr(t, "entry_price", 0) or 0),
                            "exit_price": float(getattr(t, "exit_price", 0) or 0),
                            "size": float(getattr(t, "size", 1.0) or 1.0),
                            "pnl": float(getattr(t, "pnl", 0) or 0),
                            "pnl_pct": float(getattr(t, "pnl_pct", 0) or 0),
                            "fees": float(getattr(t, "fees", 0) or 0),
                            "duration_bars": int(getattr(t, "duration_bars", 0) or 0),
                            "mfe": float(getattr(t, "mfe", 0) or 0),
                            "mae": float(getattr(t, "mae", 0) or 0),
                        }
                    )
                elif isinstance(t, dict):
                    trades_list.append(
                        {
                            "entry_time": t.get("entry_time"),
                            "exit_time": t.get("exit_time"),
                            "side": t.get("side", "long"),
                            "entry_price": float(t.get("entry_price", 0) or 0),
                            "exit_price": float(t.get("exit_price", 0) or 0),
                            "size": float(t.get("size", 1.0) or 1.0),
                            "pnl": float(t.get("pnl", 0) or 0),
                            "pnl_pct": float(t.get("pnl_pct", 0) or 0),
                            "fees": float(t.get("fees", 0) or 0),
                            "duration_bars": int(t.get("duration_bars", 0) or 0),
                            "mfe": float(t.get("mfe", 0) or 0),
                            "mae": float(t.get("mae", 0) or 0),
                        }
                    )

            # Build equity curve payload for DB
            equity_payload = None
            ec_source = result.equity_curve or getattr(result, "equity", None)
            if ec_source:
                equity_payload = build_equity_curve_response(ec_source, trades_list)

            db_backtest = BacktestModel(
                id=result.id,
                strategy_type=request.strategy_type,
                symbol=request.symbol,
                timeframe=request.interval,
                start_date=request.start_date,
                end_date=request.end_date,
                initial_capital=request.initial_capital,
                parameters={
                    "strategy_params": request.strategy_params or {},
                    "optimization_metrics": optimization_metrics,
                },
                status=DBBacktestStatus.COMPLETED,
                metrics_json=m.model_dump(mode="json") if hasattr(m, "model_dump") else None,  # Full metrics JSON
                # Basic metrics
                total_return=m.total_return,
                annual_return=m.annual_return,
                sharpe_ratio=m.sharpe_ratio,
                sortino_ratio=m.sortino_ratio,
                calmar_ratio=m.calmar_ratio,
                max_drawdown=m.max_drawdown,
                win_rate=m.win_rate,
                profit_factor=m.profit_factor,
                total_trades=m.total_trades,
                winning_trades=m.winning_trades,
                losing_trades=m.losing_trades,
                final_capital=result.final_equity,
                # New TradingView-compatible metrics
                net_profit=m.net_profit,
                net_profit_pct=m.net_profit_pct,
                gross_profit=m.gross_profit,
                gross_loss=m.gross_loss,
                total_commission=m.total_commission,
                buy_hold_return=m.buy_hold_return,
                buy_hold_return_pct=m.buy_hold_return_pct,
                cagr=m.cagr,
                cagr_long=getattr(m, "cagr_long", None),
                cagr_short=getattr(m, "cagr_short", None),
                recovery_factor=m.recovery_factor,
                expectancy=m.expectancy,
                volatility=getattr(m, "volatility", None),
                max_consecutive_wins=m.max_consecutive_wins,
                max_consecutive_losses=m.max_consecutive_losses,
                long_trades=getattr(m, "long_trades", None),
                short_trades=getattr(m, "short_trades", None),
                long_pnl=getattr(m, "long_pnl", None),
                short_pnl=getattr(m, "short_pnl", None),
                long_win_rate=getattr(m, "long_win_rate", None),
                short_win_rate=getattr(m, "short_win_rate", None),
                avg_bars_in_trade=getattr(m, "avg_bars_in_trade", None),
                exposure_time=getattr(m, "exposure_time", None),
                trades=trades_list,
                equity_curve=equity_payload,
            )
            db.add(db_backtest)
            db.commit()
            logger.info(f"Saved backtest {result.id} to database")
        except Exception as e:
            logger.error(f"Failed to save backtest to database: {e}")

    # Apply downsampling to equity curve before returning to client
    # This ensures the response is not too large (35k+ points -> ~800 points)
    if result.equity_curve:
        downsampled_ec = build_equity_curve_response(result.equity_curve, result.trades)
        if downsampled_ec:
            # Create a copy of equity curve with downsampled data
            from backend.backtesting.models import EquityCurve

            result.equity_curve = EquityCurve(
                timestamps=[
                    datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
                    for ts in downsampled_ec["timestamps"]
                ],
                equity=downsampled_ec["equity"],
                drawdown=downsampled_ec["drawdown"],
                bh_equity=downsampled_ec.get("bh_equity", []),
                bh_drawdown=downsampled_ec.get("bh_drawdown", []),
            )

    return result


@router.get("/", response_model=BacktestListResponse)
async def list_backtests(
    limit: int = Query(default=20, ge=1, le=100),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
):
    """
    List all backtest results.

    Combines in-memory cached results with persisted database records.
    """
    # Get in-memory results
    service = get_backtest_service()
    memory_results = service.list_results(limit=1000)
    memory_ids = {r.id for r in memory_results}

    # Expire all cached objects to ensure fresh data after deletions
    # This prevents returning "ghost" records that were deleted in other requests
    db.expire_all()

    # Get database results (includes optimization results)
    db_backtests = db.query(BacktestModel).order_by(BacktestModel.created_at.desc()).limit(1000).all()

    # Convert DB records to BacktestResult format
    db_results = []
    for bt in db_backtests:
        if bt.id in memory_ids:
            continue  # Skip duplicates

        # Convert DB model to BacktestResult
        try:
            # Parse dates - they may be strings or datetime objects
            start_dt: datetime | None = cast(datetime | None, bt.start_date)
            end_dt: datetime | None = cast(datetime | None, bt.end_date)
            if isinstance(start_dt, str):
                start_dt = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
            if isinstance(end_dt, str):
                end_dt = datetime.fromisoformat(end_dt.replace("Z", "+00:00"))
            if start_dt and start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=UTC)
            if end_dt and end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=UTC)

            config = BacktestConfig(
                symbol=str(bt.symbol or "BTCUSDT"),
                interval=str(bt.timeframe or "30"),
                start_date=start_dt or datetime.now(UTC),
                end_date=end_dt or datetime.now(UTC),
                initial_capital=float(bt.initial_capital or 10000.0),
                strategy_type=StrategyType(str(bt.strategy_type or "rsi")),
                strategy_params=bt.parameters.get("strategy_params", {}) if bt.parameters else {},
                stop_loss=bt.parameters.get("stop_loss_pct") if bt.parameters else None,
                take_profit=bt.parameters.get("take_profit_pct") if bt.parameters else None,
                leverage=bt.parameters.get("leverage", 10) if bt.parameters else 10,
                # Extract direction from parameters._direction (DCA strategies store it there)
                direction=bt.parameters.get("_direction", "both") if bt.parameters else "both",
            )

            # Build PerformanceMetrics from DB fields + stored optimization_metrics
            net_profit = bt.final_capital - bt.initial_capital if bt.final_capital and bt.initial_capital else 0

            # Get stored metrics - prioritize metrics_json (full data), fallback to parameters.optimization_metrics
            # metrics_json is the Single Source of Truth (SSoT) for all detailed metrics
            opt_metrics: dict[str, Any] = {}

            # First, try metrics_json (contains complete metrics snapshot)
            if bt.metrics_json and isinstance(bt.metrics_json, dict):
                opt_metrics = dict(bt.metrics_json)

            # Merge with optimization_metrics from parameters (legacy support)
            if bt.parameters and isinstance(bt.parameters, dict):
                legacy_metrics = bt.parameters.get("optimization_metrics", {})
                if legacy_metrics and isinstance(legacy_metrics, dict):
                    # Only fill in missing keys from legacy source
                    for k, v in legacy_metrics.items():
                        if k not in opt_metrics:
                            opt_metrics[k] = v

            # Calculate max_drawdown_value in $ from percentage
            initial_cap = bt.initial_capital or 10000.0
            max_dd_pct = bt.max_drawdown or 0
            max_dd_value = opt_metrics.get("max_drawdown_value", abs(max_dd_pct) * initial_cap / 100.0)

            # Calculate winning/losing trades from win_rate if not stored
            # Try DB fields first, then opt_metrics from parameters JSON
            total_trades_count = bt.total_trades or opt_metrics.get("total_trades", 0)
            winning_trades_count = bt.winning_trades or opt_metrics.get("winning_trades", 0)
            losing_trades_count = bt.losing_trades or opt_metrics.get("losing_trades", 0)
            win_rate_val = bt.win_rate or opt_metrics.get("win_rate", 0)

            # If winning_trades is 0 but we have trades and win_rate, calculate it
            if winning_trades_count == 0 and total_trades_count > 0 and win_rate_val > 0:
                # Determine if win_rate is in percentage (>1) or decimal (<1) format
                win_rate_decimal = win_rate_val / 100.0 if win_rate_val > 1 else win_rate_val
                winning_trades_count = int(round(total_trades_count * win_rate_decimal))
                losing_trades_count = total_trades_count - winning_trades_count

            metrics = PerformanceMetrics(
                net_profit=_safe_float(opt_metrics.get("net_profit", net_profit)),
                net_profit_pct=_safe_float(opt_metrics.get("net_profit_pct", bt.total_return or 0)),
                total_return=_safe_float(bt.total_return or 0),
                annual_return=_safe_float(bt.annual_return or opt_metrics.get("annual_return", 0)),
                sharpe_ratio=_safe_float(bt.sharpe_ratio or 0),
                sortino_ratio=_safe_float(bt.sortino_ratio or 0),
                calmar_ratio=_safe_float(bt.calmar_ratio or opt_metrics.get("calmar_ratio", 0)),
                max_drawdown=_safe_float(bt.max_drawdown or 0),
                max_drawdown_value=_safe_float(max_dd_value),
                avg_drawdown=_safe_float(opt_metrics.get("avg_drawdown", 0)),
                avg_drawdown_value=_safe_float(opt_metrics.get("avg_drawdown_value", 0)),
                max_drawdown_duration_days=_safe_float(opt_metrics.get("max_drawdown_duration_days", 0)),
                total_trades=_safe_int(total_trades_count),
                winning_trades=_safe_int(winning_trades_count),
                losing_trades=_safe_int(losing_trades_count),
                win_rate=_safe_float(bt.win_rate or 0),
                profit_factor=_safe_float(bt.profit_factor or 0),
                avg_win=_safe_float(opt_metrics.get("avg_win", 0)),
                avg_loss=_safe_float(opt_metrics.get("avg_loss", 0)),
                # avg_win/avg_loss are already in USD, copy to _value fields
                avg_win_value=_safe_float(opt_metrics.get("avg_win", 0)),
                avg_loss_value=_safe_float(opt_metrics.get("avg_loss", 0)),
                exposure_time=_safe_float(
                    bt.exposure_time if bt.exposure_time is not None else opt_metrics.get("exposure_time", 0)
                ),
                avg_trade_duration_hours=_safe_float(opt_metrics.get("avg_trade_duration_hours", 0)),
                # Extended metrics - DB columns first, then opt_metrics fallback
                gross_profit=_safe_float(
                    bt.gross_profit if bt.gross_profit is not None else opt_metrics.get("gross_profit", 0)
                ),
                gross_loss=_safe_float(
                    bt.gross_loss if bt.gross_loss is not None else opt_metrics.get("gross_loss", 0)
                ),
                expectancy=_safe_float(
                    bt.expectancy if bt.expectancy is not None else opt_metrics.get("expectancy", 0)
                ),
                max_consecutive_wins=_safe_int(
                    bt.max_consecutive_wins
                    if bt.max_consecutive_wins is not None
                    else opt_metrics.get("max_consecutive_wins", 0)
                ),
                max_consecutive_losses=_safe_int(
                    bt.max_consecutive_losses
                    if bt.max_consecutive_losses is not None
                    else opt_metrics.get("max_consecutive_losses", 0)
                ),
                recovery_factor=_safe_float(
                    bt.recovery_factor if bt.recovery_factor is not None else opt_metrics.get("recovery_factor", 0)
                ),
                largest_win=_safe_float(opt_metrics.get("best_trade", 0)),
                largest_loss=_safe_float(opt_metrics.get("worst_trade", 0)),
                largest_win_value=_safe_float(opt_metrics.get("best_trade", 0)),
                largest_loss_value=_safe_float(opt_metrics.get("worst_trade", 0)),
                # Long/Short statistics - DB columns first, then opt_metrics fallback
                long_trades=_safe_int(
                    bt.long_trades if bt.long_trades is not None else opt_metrics.get("long_trades", 0)
                ),
                long_winning_trades=_safe_int(opt_metrics.get("long_winning_trades", 0)),
                long_losing_trades=_safe_int(opt_metrics.get("long_losing_trades", 0)),
                long_win_rate=_safe_float(
                    bt.long_win_rate if bt.long_win_rate is not None else opt_metrics.get("long_win_rate", 0)
                ),
                long_gross_profit=_safe_float(opt_metrics.get("long_gross_profit", 0)),
                long_gross_profit_pct=_safe_float(opt_metrics.get("long_gross_profit_pct", 0)),
                long_gross_loss=_safe_float(opt_metrics.get("long_gross_loss", 0)),
                long_gross_loss_pct=_safe_float(opt_metrics.get("long_gross_loss_pct", 0)),
                long_net_profit=_safe_float(
                    bt.long_pnl if bt.long_pnl is not None else opt_metrics.get("long_net_profit", 0)
                ),
                long_profit_factor=_safe_float(opt_metrics.get("long_profit_factor", 0)),
                long_avg_win=_safe_float(opt_metrics.get("long_avg_win", 0)),
                long_avg_loss=_safe_float(opt_metrics.get("long_avg_loss", 0)),
                short_trades=_safe_int(
                    bt.short_trades if bt.short_trades is not None else opt_metrics.get("short_trades", 0)
                ),
                short_winning_trades=_safe_int(opt_metrics.get("short_winning_trades", 0)),
                short_losing_trades=_safe_int(opt_metrics.get("short_losing_trades", 0)),
                short_win_rate=_safe_float(
                    bt.short_win_rate if bt.short_win_rate is not None else opt_metrics.get("short_win_rate", 0)
                ),
                short_gross_profit=_safe_float(opt_metrics.get("short_gross_profit", 0)),
                short_gross_profit_pct=_safe_float(opt_metrics.get("short_gross_profit_pct", 0)),
                short_gross_loss=_safe_float(opt_metrics.get("short_gross_loss", 0)),
                short_gross_loss_pct=_safe_float(opt_metrics.get("short_gross_loss_pct", 0)),
                short_net_profit=_safe_float(
                    bt.short_pnl if bt.short_pnl is not None else opt_metrics.get("short_net_profit", 0)
                ),
                short_profit_factor=_safe_float(opt_metrics.get("short_profit_factor", 0)),
                short_avg_win=_safe_float(opt_metrics.get("short_avg_win", 0)),
                short_avg_loss=_safe_float(opt_metrics.get("short_avg_loss", 0)),
                # Additional metrics
                avg_bars_in_trade=_safe_float(opt_metrics.get("avg_bars_in_trade", 0)),
                avg_bars_in_winning=_safe_float(opt_metrics.get("avg_bars_in_winning", 0)),
                avg_bars_in_losing=_safe_float(opt_metrics.get("avg_bars_in_losing", 0)),
                avg_bars_in_long=_safe_float(opt_metrics.get("avg_bars_in_long", 0)),
                avg_bars_in_short=_safe_float(opt_metrics.get("avg_bars_in_short", 0)),
                avg_bars_in_winning_long=_safe_float(opt_metrics.get("avg_bars_in_winning_long", 0)),
                avg_bars_in_losing_long=_safe_float(opt_metrics.get("avg_bars_in_losing_long", 0)),
                avg_bars_in_winning_short=_safe_float(opt_metrics.get("avg_bars_in_winning_short", 0)),
                avg_bars_in_losing_short=_safe_float(opt_metrics.get("avg_bars_in_losing_short", 0)),
                recovery_long=_safe_float(opt_metrics.get("recovery_long", 0)),
                recovery_short=_safe_float(opt_metrics.get("recovery_short", 0)),
                # Long/Short consecutive and payoff metrics (TradingView)
                long_max_consec_wins=_safe_int(opt_metrics.get("long_max_consec_wins", 0)),
                long_max_consec_losses=_safe_int(opt_metrics.get("long_max_consec_losses", 0)),
                short_max_consec_wins=_safe_int(opt_metrics.get("short_max_consec_wins", 0)),
                short_max_consec_losses=_safe_int(opt_metrics.get("short_max_consec_losses", 0)),
                long_payoff_ratio=_safe_float(opt_metrics.get("long_payoff_ratio", 0)),
                short_payoff_ratio=_safe_float(opt_metrics.get("short_payoff_ratio", 0)),
                long_expectancy=_safe_float(opt_metrics.get("long_expectancy", 0)),
                short_expectancy=_safe_float(opt_metrics.get("short_expectancy", 0)),
                # Use DB columns first, fallback to opt_metrics
                total_commission=_safe_float(
                    bt.total_commission if bt.total_commission is not None else opt_metrics.get("total_commission", 0)
                ),
                buy_hold_return=_safe_float(
                    bt.buy_hold_return if bt.buy_hold_return is not None else opt_metrics.get("buy_hold_return", 0)
                ),
                buy_hold_return_pct=_safe_float(
                    bt.buy_hold_return_pct
                    if bt.buy_hold_return_pct is not None
                    else opt_metrics.get("buy_hold_return_pct", 0)
                ),
                strategy_outperformance=_safe_float(opt_metrics.get("strategy_outperformance", 0)),
                cagr=_safe_float(bt.cagr if bt.cagr is not None else opt_metrics.get("cagr", 0)),
                cagr_long=_safe_float(bt.cagr_long if bt.cagr_long is not None else opt_metrics.get("cagr_long", 0)),
                cagr_short=_safe_float(
                    bt.cagr_short if bt.cagr_short is not None else opt_metrics.get("cagr_short", 0)
                ),
                max_runup=_safe_float(opt_metrics.get("max_runup", 0)),
                max_runup_value=_safe_float(opt_metrics.get("max_runup_value", 0)),
                avg_runup_duration_bars=_safe_float(opt_metrics.get("avg_runup_duration_bars", 0)),
                avg_drawdown_duration_bars=_safe_float(opt_metrics.get("avg_drawdown_duration_bars", 0)),
                best_trade=_safe_float(opt_metrics.get("best_trade", 0)),
                worst_trade=_safe_float(opt_metrics.get("worst_trade", 0)),
            )

            # Get trades and equity curve from DB if available
            trades_data: list[Any] = list(bt.trades) if bt.trades else []  # type: ignore[arg-type]

            # Convert equity_curve from list format to EquityCurve model
            equity_curve_data = None
            if bt.equity_curve:
                raw_ec = bt.equity_curve
                # Check if it's already in EquityCurve format (dict with timestamps key)
                if isinstance(raw_ec, dict) and "timestamps" in raw_ec:
                    equity_curve_data = EquityCurve(**raw_ec)
                elif isinstance(raw_ec, list) and len(raw_ec) > 0:
                    # Convert from list of {timestamp, equity, drawdown} to EquityCurve
                    timestamps = []
                    equity = []
                    drawdown = []
                    returns_list = []
                    for point in raw_ec:
                        ts = point.get("timestamp", 0)
                        # Convert ms timestamp to datetime
                        if isinstance(ts, (int, float)):
                            ts = datetime.fromtimestamp(ts / 1000, tz=UTC)
                        elif isinstance(ts, str):
                            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        timestamps.append(ts)
                        equity.append(point.get("equity", 0))
                        drawdown.append(point.get("drawdown", 0))
                        returns_list.append(point.get("returns", 0))
                    equity_curve_data = EquityCurve(
                        timestamps=timestamps,
                        equity=equity,
                        drawdown=drawdown,
                        returns=returns_list if any(returns_list) else [],
                    )

            result = BacktestResult(
                id=str(bt.id) if bt.id else "",
                status=BacktestStatus.COMPLETED if bt.status == DBBacktestStatus.COMPLETED else BacktestStatus.FAILED,
                created_at=cast(datetime, bt.created_at) if bt.created_at else datetime.now(UTC),
                config=config,
                metrics=metrics,
                trades=cast(list[TradeRecord], list(trades_data)) if trades_data else [],
                equity_curve=equity_curve_data,
                final_equity=float(bt.final_capital) if bt.final_capital else None,
                final_pnl=float(net_profit) if net_profit else None,
                final_pnl_pct=float(bt.total_return) if bt.total_return else 0.0,
            )
            db_results.append(result)
        except Exception as e:
            logger.warning(f"Failed to convert DB backtest {bt.id}: {e}")
            continue

    # Combine and sort by created_at
    all_results = memory_results + db_results
    all_results.sort(key=lambda x: x.created_at, reverse=True)

    # Paginate
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    items = all_results[start_idx:end_idx]

    return BacktestListResponse(
        total=len(all_results),
        items=items,
        page=page,
        page_size=limit,
    )


@router.get("/strategies")
async def list_strategies() -> list[dict[str, Any]]:
    """
    List all available trading strategies with their default parameters.

    **Response Example:**
    ```json
    [
        {
            "name": "sma_crossover",
            "description": "SMA Crossover - Buy when fast SMA crosses above slow SMA",
            "default_params": {"fast_period": 10, "slow_period": 30}
        },
        ...
    ]
    ```
    """
    return list_available_strategies()


@router.get("/{backtest_id}", response_model=BacktestResult)
async def get_backtest(backtest_id: str, db: Session = Depends(get_db)):
    """
    Get a specific backtest result by ID.

    Returns the full backtest result including metrics, trades, and equity curve.
    Searches both in-memory cache and database.
    """
    logger.debug(f"[GET_BACKTEST] Called with id={backtest_id}")
    # First try in-memory cache
    service = get_backtest_service()
    result = service.get_result(backtest_id)

    if result is not None:
        return result

    # If not in memory, try database
    bt = db.query(BacktestModel).filter(BacktestModel.id == backtest_id).first()

    if bt is None:
        raise HTTPException(
            status_code=404,
            detail=f"Backtest {backtest_id} not found",
        )

    # Convert DB model to BacktestResult
    try:
        # Parse dates - they may be strings or datetime objects
        start_dt: datetime | None = cast(datetime | None, bt.start_date)
        end_dt: datetime | None = cast(datetime | None, bt.end_date)
        if isinstance(start_dt, str):
            start_dt = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
        if isinstance(end_dt, str):
            end_dt = datetime.fromisoformat(end_dt.replace("Z", "+00:00"))
        if start_dt and start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=UTC)
        if end_dt and end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=UTC)

        config = BacktestConfig(
            symbol=str(bt.symbol or "BTCUSDT"),
            interval=str(bt.timeframe or "30"),
            start_date=cast(datetime, start_dt) if start_dt else datetime.now(UTC),
            end_date=cast(datetime, end_dt) if end_dt else datetime.now(UTC),
            initial_capital=float(bt.initial_capital or 10000.0),
            strategy_type=StrategyType(str(bt.strategy_type or "rsi")),
            strategy_params=bt.parameters.get("strategy_params", {}) if bt.parameters else {},
            stop_loss=bt.parameters.get("stop_loss_pct") if bt.parameters else None,
            take_profit=bt.parameters.get("take_profit_pct") if bt.parameters else None,
            leverage=bt.parameters.get("leverage", 10) if bt.parameters else 10,
        )

        # Build PerformanceMetrics from DB fields + stored optimization_metrics
        net_profit = bt.final_capital - bt.initial_capital if bt.final_capital and bt.initial_capital else 0

        # Get stored metrics - prioritize metrics_json (full data), fallback to parameters.optimization_metrics
        # metrics_json is the Single Source of Truth (SSoT) for all detailed metrics
        opt_metrics: dict[str, Any] = {}

        # First, try metrics_json (contains complete metrics snapshot)
        if bt.metrics_json and isinstance(bt.metrics_json, dict):
            opt_metrics = dict(bt.metrics_json)

        # Merge with optimization_metrics from parameters (legacy support)
        if bt.parameters and isinstance(bt.parameters, dict):
            legacy_metrics = bt.parameters.get("optimization_metrics", {})
            if legacy_metrics and isinstance(legacy_metrics, dict):
                # Only fill in missing keys from legacy source
                for k, v in legacy_metrics.items():
                    if k not in opt_metrics:
                        opt_metrics[k] = v

        logger.info(
            f"[get_backtest] opt_metrics (merged) long_trades={opt_metrics.get('long_trades', 'N/A')}, "
            f"short_trades={opt_metrics.get('short_trades', 'N/A')}, "
            f"long_win_rate={opt_metrics.get('long_win_rate', 'N/A')}, "
            f"short_win_rate={opt_metrics.get('short_win_rate', 'N/A')}"
        )

        # Calculate max_drawdown_value in $ from percentage
        initial_cap = bt.initial_capital or 10000.0
        max_dd_pct = bt.max_drawdown or 0
        max_dd_value = opt_metrics.get("max_drawdown_value", abs(max_dd_pct) * initial_cap / 100.0)

        # Calculate winning/losing trades from win_rate if not stored
        # Use opt_metrics as fallback for optimization results
        total_trades_count = bt.total_trades or opt_metrics.get("total_trades", 0)
        winning_trades_count = bt.winning_trades or opt_metrics.get("winning_trades", 0)
        losing_trades_count = bt.losing_trades or opt_metrics.get("losing_trades", 0)

        # If winning_trades is 0 but we have trades and win_rate, calculate it
        win_rate_val = bt.win_rate or 0
        if winning_trades_count == 0 and total_trades_count > 0 and win_rate_val > 0:
            # Determine if win_rate is in percentage (>1) or decimal (<1) format
            win_rate_decimal = win_rate_val / 100.0 if win_rate_val > 1 else win_rate_val
            winning_trades_count = int(round(total_trades_count * win_rate_decimal))
            losing_trades_count = total_trades_count - winning_trades_count

        metrics = PerformanceMetrics(
            net_profit=_safe_float(opt_metrics.get("net_profit", net_profit)),
            net_profit_pct=_safe_float(opt_metrics.get("net_profit_pct", bt.total_return or 0)),
            total_return=_safe_float(bt.total_return or 0),
            annual_return=_safe_float(bt.annual_return or opt_metrics.get("annual_return", 0)),
            sharpe_ratio=_safe_float(bt.sharpe_ratio or 0),
            sortino_ratio=_safe_float(bt.sortino_ratio or 0),
            calmar_ratio=_safe_float(bt.calmar_ratio or opt_metrics.get("calmar_ratio", 0)),
            max_drawdown=_safe_float(bt.max_drawdown or 0),
            max_drawdown_value=_safe_float(max_dd_value),
            avg_drawdown=_safe_float(opt_metrics.get("avg_drawdown", 0)),
            avg_drawdown_value=_safe_float(opt_metrics.get("avg_drawdown_value", 0)),
            max_drawdown_duration_days=_safe_float(opt_metrics.get("max_drawdown_duration_days", 0)),
            total_trades=_safe_int(total_trades_count),
            winning_trades=_safe_int(winning_trades_count),
            losing_trades=_safe_int(losing_trades_count),
            win_rate=_safe_float(bt.win_rate or 0),
            profit_factor=_safe_float(bt.profit_factor or 0),
            avg_win=_safe_float(opt_metrics.get("avg_win", 0)),
            avg_loss=_safe_float(opt_metrics.get("avg_loss", 0)),
            avg_trade=_safe_float(opt_metrics.get("avg_trade", 0)),
            avg_win_value=_safe_float(opt_metrics.get("avg_win_value", opt_metrics.get("avg_win", 0))),
            avg_loss_value=_safe_float(opt_metrics.get("avg_loss_value", opt_metrics.get("avg_loss", 0))),
            avg_trade_value=_safe_float(opt_metrics.get("avg_trade_value", 0)),
            exposure_time=_safe_float(
                bt.exposure_time if bt.exposure_time is not None else opt_metrics.get("exposure_time", 0)
            ),
            avg_trade_duration_hours=_safe_float(opt_metrics.get("avg_trade_duration_hours", 0)),
            gross_profit=_safe_float(
                bt.gross_profit if bt.gross_profit is not None else opt_metrics.get("gross_profit", 0)
            ),
            gross_loss=_safe_float(bt.gross_loss if bt.gross_loss is not None else opt_metrics.get("gross_loss", 0)),
            expectancy=_safe_float(bt.expectancy if bt.expectancy is not None else opt_metrics.get("expectancy", 0)),
            max_consecutive_wins=_safe_int(
                bt.max_consecutive_wins
                if bt.max_consecutive_wins is not None
                else opt_metrics.get("max_consecutive_wins", 0)
            ),
            max_consecutive_losses=_safe_int(
                bt.max_consecutive_losses
                if bt.max_consecutive_losses is not None
                else opt_metrics.get("max_consecutive_losses", 0)
            ),
            recovery_factor=_safe_float(
                bt.recovery_factor if bt.recovery_factor is not None else opt_metrics.get("recovery_factor", 0)
            ),
            largest_win=_safe_float(opt_metrics.get("largest_win", 0)),
            largest_loss=_safe_float(opt_metrics.get("largest_loss", 0)),
            largest_win_value=_safe_float(opt_metrics.get("largest_win_value", 0)),
            largest_loss_value=_safe_float(opt_metrics.get("largest_loss_value", 0)),
            long_trades=_safe_int(bt.long_trades if bt.long_trades is not None else opt_metrics.get("long_trades", 0)),
            long_winning_trades=_safe_int(opt_metrics.get("long_winning_trades", 0)),
            long_losing_trades=_safe_int(opt_metrics.get("long_losing_trades", 0)),
            long_win_rate=_safe_float(
                bt.long_win_rate if bt.long_win_rate is not None else opt_metrics.get("long_win_rate", 0)
            ),
            long_gross_profit=_safe_float(opt_metrics.get("long_gross_profit", 0)),
            long_gross_profit_pct=_safe_float(opt_metrics.get("long_gross_profit_pct", 0)),
            long_gross_loss=_safe_float(opt_metrics.get("long_gross_loss", 0)),
            long_gross_loss_pct=_safe_float(opt_metrics.get("long_gross_loss_pct", 0)),
            long_net_profit=_safe_float(
                bt.long_pnl if bt.long_pnl is not None else opt_metrics.get("long_net_profit", 0)
            ),
            long_profit_factor=_safe_float(opt_metrics.get("long_profit_factor", 0)),
            long_avg_win=_safe_float(opt_metrics.get("long_avg_win_pct", 0)),
            long_avg_loss=_safe_float(opt_metrics.get("long_avg_loss_pct", 0)),
            short_trades=_safe_int(
                bt.short_trades if bt.short_trades is not None else opt_metrics.get("short_trades", 0)
            ),
            short_winning_trades=_safe_int(opt_metrics.get("short_winning_trades", 0)),
            short_losing_trades=_safe_int(opt_metrics.get("short_losing_trades", 0)),
            short_win_rate=_safe_float(
                bt.short_win_rate if bt.short_win_rate is not None else opt_metrics.get("short_win_rate", 0)
            ),
            short_gross_profit=_safe_float(opt_metrics.get("short_gross_profit", 0)),
            short_gross_profit_pct=_safe_float(opt_metrics.get("short_gross_profit_pct", 0)),
            short_gross_loss=_safe_float(opt_metrics.get("short_gross_loss", 0)),
            short_gross_loss_pct=_safe_float(opt_metrics.get("short_gross_loss_pct", 0)),
            short_net_profit=_safe_float(
                bt.short_pnl if bt.short_pnl is not None else opt_metrics.get("short_net_profit", 0)
            ),
            short_profit_factor=_safe_float(opt_metrics.get("short_profit_factor", 0)),
            short_avg_win=_safe_float(opt_metrics.get("short_avg_win_pct", 0)),
            short_avg_loss=_safe_float(opt_metrics.get("short_avg_loss_pct", 0)),
            recovery_long=_safe_float(opt_metrics.get("recovery_long", 0)),
            recovery_short=_safe_float(opt_metrics.get("recovery_short", 0)),
            long_avg_win_value=_safe_float(opt_metrics.get("long_avg_win", 0)),
            long_avg_loss_value=_safe_float(opt_metrics.get("long_avg_loss", 0)),
            short_avg_win_value=_safe_float(opt_metrics.get("short_avg_win", 0)),
            short_avg_loss_value=_safe_float(opt_metrics.get("short_avg_loss", 0)),
            long_largest_win=_safe_float(opt_metrics.get("long_largest_win", 0)),
            long_largest_loss=_safe_float(opt_metrics.get("long_largest_loss", 0)),
            short_largest_win=_safe_float(opt_metrics.get("short_largest_win", 0)),
            short_largest_loss=_safe_float(opt_metrics.get("short_largest_loss", 0)),
            long_max_consec_wins=_safe_int(opt_metrics.get("long_max_consec_wins", 0)),
            long_max_consec_losses=_safe_int(opt_metrics.get("long_max_consec_losses", 0)),
            short_max_consec_wins=_safe_int(opt_metrics.get("short_max_consec_wins", 0)),
            short_max_consec_losses=_safe_int(opt_metrics.get("short_max_consec_losses", 0)),
            long_payoff_ratio=_safe_float(opt_metrics.get("long_payoff_ratio", 0)),
            short_payoff_ratio=_safe_float(opt_metrics.get("short_payoff_ratio", 0)),
            long_expectancy=_safe_float(opt_metrics.get("long_expectancy", 0)),
            short_expectancy=_safe_float(opt_metrics.get("short_expectancy", 0)),
            total_commission=_safe_float(
                bt.total_commission if bt.total_commission is not None else opt_metrics.get("total_commission", 0)
            ),
            buy_hold_return=_safe_float(
                bt.buy_hold_return if bt.buy_hold_return is not None else opt_metrics.get("buy_hold_return", 0)
            ),
            buy_hold_return_pct=_safe_float(
                bt.buy_hold_return_pct
                if bt.buy_hold_return_pct is not None
                else opt_metrics.get("buy_hold_return_pct", 0)
            ),
            strategy_outperformance=_safe_float(opt_metrics.get("strategy_outperformance", 0)),
            cagr=_safe_float(bt.cagr if bt.cagr is not None else opt_metrics.get("cagr", 0)),
            cagr_long=_safe_float(bt.cagr_long if bt.cagr_long is not None else opt_metrics.get("cagr_long", 0)),
            cagr_short=_safe_float(bt.cagr_short if bt.cagr_short is not None else opt_metrics.get("cagr_short", 0)),
            max_runup=_safe_float(opt_metrics.get("max_runup", 0)),
            max_runup_value=_safe_float(opt_metrics.get("max_runup_value", 0)),
            avg_runup_duration_bars=_safe_float(opt_metrics.get("avg_runup_duration_bars", 0)),
            avg_drawdown_duration_bars=_safe_float(opt_metrics.get("avg_drawdown_duration_bars", 0)),
            avg_bars_in_trade=_safe_float(
                bt.avg_bars_in_trade if bt.avg_bars_in_trade is not None else opt_metrics.get("avg_bars_in_trade", 0)
            ),
            avg_bars_in_winning=_safe_float(opt_metrics.get("avg_bars_in_winning", 0)),
            avg_bars_in_losing=_safe_float(opt_metrics.get("avg_bars_in_losing", 0)),
            avg_bars_in_long=_safe_float(opt_metrics.get("avg_bars_in_long", 0)),
            avg_bars_in_short=_safe_float(opt_metrics.get("avg_bars_in_short", 0)),
            avg_bars_in_winning_long=_safe_float(opt_metrics.get("avg_bars_in_winning_long", 0)),
            avg_bars_in_winning_short=_safe_float(opt_metrics.get("avg_bars_in_winning_short", 0)),
            avg_bars_in_losing_long=_safe_float(opt_metrics.get("avg_bars_in_losing_long", 0)),
            avg_bars_in_losing_short=_safe_float(opt_metrics.get("avg_bars_in_losing_short", 0)),
        )

        # Get trades and equity curve from DB if available
        trades_data: list[Any] = []
        trades_list = list(bt.trades) if bt.trades else []  # type: ignore[arg-type]
        if trades_list:
            for t in trades_list:
                # Convert timestamp (ms) to datetime if needed
                entry_time = t.get("entry_time")
                exit_time = t.get("exit_time")

                if isinstance(entry_time, (int, float)):
                    entry_time = datetime.fromtimestamp(entry_time / 1000, tz=UTC)
                elif isinstance(entry_time, str):
                    entry_time = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))

                if isinstance(exit_time, (int, float)):
                    exit_time = datetime.fromtimestamp(exit_time / 1000, tz=UTC)
                elif isinstance(exit_time, str):
                    exit_time = datetime.fromisoformat(exit_time.replace("Z", "+00:00"))

                trades_data.append(
                    TradeRecord(
                        entry_time=entry_time,
                        exit_time=exit_time,
                        side=t.get("side", "long"),
                        entry_price=t.get("entry_price", 0),
                        exit_price=t.get("exit_price", 0),
                        size=t.get("size", 1.0),
                        pnl=t.get("pnl", 0),
                        pnl_pct=t.get("pnl_pct", 0),
                        bars_in_trade=t.get("duration_bars", 0),
                        exit_comment=t.get("exit_reason", ""),
                        commission=t.get("commission", 0),
                        fees=t.get("commission", 0),
                        # MFE/MAE (TradingView Favorable/Adverse Excursion)
                        mfe=t.get("mfe", 0),
                        mae=t.get("mae", 0),
                        mfe_pct=t.get("mfe_pct", 0),
                        mae_pct=t.get("mae_pct", 0),
                    )
                )

        equity_curve_data = None
        logger.info(f"[DEBUG] bt.equity_curve type: {type(bt.equity_curve)}, truthy: {bool(bt.equity_curve)}")
        if bt.equity_curve:
            logger.info(
                f"[DEBUG] equity_curve is dict: {isinstance(bt.equity_curve, dict)}, has equity: {'equity' in bt.equity_curve if isinstance(bt.equity_curve, dict) else 'N/A'}"
            )
            # Support both formats:
            # 1. List of objects: [{timestamp, equity, drawdown}, ...]
            # 2. Dict with arrays: {timestamps: [], equity: [], drawdown: [], bh_equity: [], ...}
            if isinstance(bt.equity_curve, dict) and "equity" in bt.equity_curve:
                # Dict format - already in EquityCurve-like structure
                timestamps_raw = bt.equity_curve.get("timestamps", [])
                timestamps = []
                for ts in timestamps_raw:
                    if isinstance(ts, (int, float)):
                        ts = datetime.fromtimestamp(ts / 1000, tz=UTC)
                    elif isinstance(ts, str):
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    timestamps.append(ts)

                equity_curve_data = EquityCurve(
                    timestamps=timestamps,
                    equity=bt.equity_curve.get("equity", []),
                    drawdown=bt.equity_curve.get("drawdown", []),
                    bh_equity=bt.equity_curve.get("bh_equity", []),
                    bh_drawdown=bt.equity_curve.get("bh_drawdown", []),
                )
            elif isinstance(bt.equity_curve, list) and len(bt.equity_curve) > 0:
                # List format - convert to EquityCurve
                timestamps = []
                equity = []
                drawdown = []

                for point in bt.equity_curve:
                    ts = point.get("timestamp")
                    if isinstance(ts, (int, float)):
                        ts = datetime.fromtimestamp(ts / 1000, tz=UTC)
                    elif isinstance(ts, str):
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    timestamps.append(ts)
                    equity.append(point.get("equity", 0))
                    drawdown.append(point.get("drawdown", 0))

                equity_curve_data = EquityCurve(
                    timestamps=timestamps,
                    equity=equity,
                    drawdown=drawdown,
                )

        return BacktestResult(
            id=str(bt.id) if bt.id else "",
            status=BacktestStatus.COMPLETED if bt.status == DBBacktestStatus.COMPLETED else BacktestStatus.FAILED,
            created_at=cast(datetime, bt.created_at) if bt.created_at else datetime.now(UTC),
            config=config,
            metrics=metrics,
            trades=cast(list[TradeRecord], trades_data) if trades_data else [],
            equity_curve=equity_curve_data,
            final_equity=float(bt.final_capital) if bt.final_capital else None,
            final_pnl=float(net_profit) if net_profit else None,
            final_pnl_pct=float(bt.total_return) if bt.total_return else 0.0,
        )
    except Exception as e:
        logger.warning(f"Failed to convert DB backtest {bt.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to convert backtest: {e!s}",
        )


@router.get("/{backtest_id}/trades")
async def get_backtest_trades(backtest_id: str):
    """
    Get trade history for a specific backtest.

    Returns detailed trade-by-trade breakdown with entry/exit times,
    prices, PnL, and fees.
    """
    service = get_backtest_service()
    result = service.get_result(backtest_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Backtest {backtest_id} not found",
        )

    return {
        "backtest_id": backtest_id,
        "total_trades": len(result.trades),
        "trades": result.trades,
    }


@router.get("/{backtest_id}/equity")
async def get_backtest_equity(backtest_id: str):
    """
    Get equity curve data for a specific backtest.

    Returns time series data suitable for charting:
    - timestamps
    - equity values
    - drawdown values
    - returns
    """
    service = get_backtest_service()
    result = service.get_result(backtest_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Backtest {backtest_id} not found",
        )

    if result.equity_curve is None:
        raise HTTPException(
            status_code=404,
            detail=f"No equity curve data for backtest {backtest_id}",
        )

    return {
        "backtest_id": backtest_id,
        "equity_curve": result.equity_curve,
    }


@router.get("/{backtest_id}/metrics")
async def get_backtest_metrics(backtest_id: str):
    """
    Get performance metrics for a specific backtest.

    Returns comprehensive metrics including:
    - Returns (total, annual)
    - Risk metrics (Sharpe, Sortino, Calmar)
    - Drawdown stats
    - Trade statistics (win rate, profit factor)
    """
    service = get_backtest_service()
    result = service.get_result(backtest_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Backtest {backtest_id} not found",
        )

    if result.metrics is None:
        raise HTTPException(
            status_code=404,
            detail=f"No metrics available for backtest {backtest_id}",
        )

    return {
        "backtest_id": backtest_id,
        "metrics": result.metrics,
        "final_equity": result.final_equity,
        "final_pnl": result.final_pnl,
        "final_pnl_pct": result.final_pnl_pct,
    }


# ============================================================================
# STRATEGY INTEGRATION ENDPOINTS
# ============================================================================


@router.post("/from-strategy/{strategy_id}", response_model=RunFromStrategyResponse)
async def run_backtest_from_strategy(
    strategy_id: str,
    request: RunFromStrategyRequest,
    db: Session = Depends(get_db),
):
    """
    Run a backtest using a saved strategy's configuration.

    Loads the strategy from database, runs backtest with its parameters,
    and optionally saves results back to update strategy metrics.

    **Workflow:**
    1. Load strategy from database by ID
    2. Build backtest config from strategy parameters
    3. Run backtest using vectorbt engine
    4. If save_result=True: save backtest to DB and update strategy metrics

    **Example Request:**
    ```json
    {
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-06-01T00:00:00Z",
        "save_result": true
    }
    ```

    **Overrides:**
    - symbol: Override strategy's default symbol
    - interval: Override strategy's default timeframe
    - initial_capital: Override strategy's default capital
    - position_size: Override position size fraction
    """
    logger.info(f"Running backtest from strategy: {strategy_id}")

    # Load strategy from database
    strategy = (
        db.query(Strategy)
        .filter(
            Strategy.id == strategy_id,
            Strategy.is_deleted == False,  # noqa: E712
        )
        .first()
    )

    if strategy is None:
        raise HTTPException(
            status_code=404,
            detail=f"Strategy {strategy_id} not found",
        )

    # Build backtest config from strategy
    symbol = request.symbol or str(strategy.symbol or "BTCUSDT")
    interval = request.interval or str(strategy.timeframe or "1h")
    initial_capital = float(request.initial_capital or strategy.initial_capital or 10000.0)

    # Extract trading parameters from strategy.parameters (stored with _ prefix)
    # Note: commission and slippage are already stored as decimals (e.g., 0.001 for 0.1%)
    params: dict[str, Any] = dict(strategy.parameters) if strategy.parameters else {}
    leverage = float(params.get("_leverage", 1))
    direction = params.get("_direction", "both")
    pyramiding = int(params.get("_pyramiding", 1))
    commission = float(params.get("_commission", 0.001))  # Already decimal (0.001 = 0.1%)
    slippage = float(params.get("_slippage", 0.0005))  # Already decimal (0.0005 = 0.05%)

    # Handle position size based on type
    position_size_type = params.get("_position_size_type", "percent")
    order_amount = params.get("_order_amount")  # Fixed $ amount or contracts

    position_size: float
    if position_size_type == "fixed_amount" and order_amount:
        # Convert fixed $ amount to fraction of capital
        # The order amount with leverage
        effective_order = float(order_amount) * float(leverage)
        position_size = min(effective_order / float(initial_capital), 1.0)
        logger.info(
            f"Using fixed order amount: ${order_amount} x {leverage}x leverage = "
            f"${effective_order} = {position_size * 100:.1f}% of ${initial_capital}"
        )
    elif position_size_type == "contracts" and order_amount:
        # For contracts, we'll pass it through and let engine handle
        position_size = float(order_amount)
        logger.info(f"Using fixed contracts: {order_amount}")
    else:
        # Percent mode - use strategy.position_size (already as fraction)
        position_size = _safe_float(request.position_size) or _safe_float(strategy.position_size) or 1.0

    # Build config with validation error handling
    try:
        # Include position size config in strategy_params for engine to use
        strategy_params_with_size = dict(strategy.parameters or {})
        strategy_params_with_size["_position_size_type"] = position_size_type
        if order_amount is not None:
            strategy_params_with_size["_order_amount"] = float(order_amount)

        config = BacktestConfig(
            symbol=symbol,
            interval=interval,
            start_date=request.start_date,
            end_date=request.end_date,
            strategy_type=strategy.strategy_type.value,
            strategy_params=strategy_params_with_size,
            initial_capital=initial_capital,
            position_size=position_size,
            leverage=leverage,
            direction=direction,
            pyramiding=pyramiding,
            taker_fee=commission,
            maker_fee=commission,
            slippage=slippage,
            stop_loss=_safe_float(strategy.stop_loss_pct) / 100 if strategy.stop_loss_pct else None,
            take_profit=_safe_float(strategy.take_profit_pct) / 100 if strategy.take_profit_pct else None,
        )
    except (ValidationError, PydanticCoreValidationError) as e:
        # Return 422 for validation errors
        logger.warning(f"Backtest validation error: {e}")
        raise HTTPException(
            status_code=422,
            detail=str(e),
        )

    # Log config for debugging
    logger.info(
        f"Backtest config: symbol={symbol}, interval={interval}, "
        f"leverage={leverage}x, direction={direction}, position_size={position_size:.4f}, "
        f"commission={commission:.4f}, slippage={slippage:.4f}"
    )

    # Run backtest
    service = get_backtest_service()
    result = await service.run_backtest(config)

    if result.status == BacktestStatus.FAILED:
        logger.error(f"Backtest from strategy {strategy_id} failed: {result.error_message}")
        return RunFromStrategyResponse(
            backtest_id=result.id or "",
            strategy_id=strategy_id,
            strategy_name=str(strategy.name or ""),
            status="failed",
            error_message=result.error_message,
            saved_to_db=False,
        )

    # Prepare response
    metrics_dict = None
    if result.metrics:
        # Use full metrics dump for immediate response to include all fields
        metrics_dict = result.metrics.model_dump(mode="json")

    saved_to_db = False

    # Save to database if requested
    if request.save_result:
        try:
            # Create backtest record with all metrics
            m = result.metrics  # shortcut
            db_backtest = BacktestModel(
                strategy_id=strategy.id,
                metrics_json=m.model_dump(mode="json") if m else None,  # Save full metrics JSON
                strategy_type=strategy.strategy_type.value,
                symbol=symbol,
                timeframe=interval,
                start_date=request.start_date,
                end_date=request.end_date,
                initial_capital=initial_capital,
                parameters=strategy.parameters or {},
                status=DBBacktestStatus.COMPLETED,
                # Basic metrics
                total_return=m.total_return if m else None,
                annual_return=m.annual_return if m else None,
                sharpe_ratio=m.sharpe_ratio if m else None,
                sortino_ratio=m.sortino_ratio if m else None,
                calmar_ratio=m.calmar_ratio if m else None,
                max_drawdown=m.max_drawdown if m else None,
                win_rate=m.win_rate if m else None,
                profit_factor=m.profit_factor if m else None,
                total_trades=m.total_trades if m else None,
                winning_trades=m.winning_trades if m else None,
                losing_trades=m.losing_trades if m else None,
                final_capital=result.final_equity,
                # New TradingView-compatible metrics
                net_profit=m.net_profit if m else None,
                net_profit_pct=m.net_profit_pct if m else None,
                gross_profit=m.gross_profit if m else None,
                gross_loss=m.gross_loss if m else None,
                total_commission=m.total_commission if m else None,
                buy_hold_return=m.buy_hold_return if m else None,
                buy_hold_return_pct=m.buy_hold_return_pct if m else None,
                cagr=m.cagr if m else None,
                cagr_long=getattr(m, "cagr_long", None) if m else None,
                cagr_short=getattr(m, "cagr_short", None) if m else None,
                recovery_factor=m.recovery_factor if m else None,
                expectancy=m.expectancy if m else None,
                volatility=getattr(m, "volatility", None) if m else None,
                max_consecutive_wins=m.max_consecutive_wins if m else None,
                max_consecutive_losses=m.max_consecutive_losses if m else None,
                long_trades=getattr(m, "long_trades", None) if m else None,
                short_trades=getattr(m, "short_trades", None) if m else None,
                long_pnl=getattr(m, "long_pnl", None) if m else None,
                short_pnl=getattr(m, "short_pnl", None) if m else None,
                long_win_rate=getattr(m, "long_win_rate", None) if m else None,
                short_win_rate=getattr(m, "short_win_rate", None) if m else None,
                avg_bars_in_trade=getattr(m, "avg_bars_in_trade", None) if m else None,
                exposure_time=getattr(m, "exposure_time", None) if m else None,
                # Trades and Equity Curve (with MFE/MAE)
                trades=[
                    {
                        "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                        "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                        "side": t.side.value if hasattr(t.side, "value") else str(t.side),
                        "entry_price": float(t.entry_price) if t.entry_price else 0,
                        "exit_price": float(t.exit_price) if t.exit_price else 0,
                        "size": float(t.size) if t.size else 0,
                        "pnl": float(t.pnl) if t.pnl else 0,
                        "pnl_pct": float(t.pnl_pct) if t.pnl_pct else 0,
                        "fees": float(t.fees) if t.fees else 0,
                        "duration_hours": float(t.duration_hours) if t.duration_hours else 0,
                        "mfe": float(t.mfe) if hasattr(t, "mfe") and t.mfe else 0,
                        "mae": float(t.mae) if hasattr(t, "mae") and t.mae else 0,
                        "mfe_pct": float(t.mfe) if hasattr(t, "mfe") and t.mfe else 0,
                        "mae_pct": float(t.mae) if hasattr(t, "mae") and t.mae else 0,
                    }
                    for t in (result.trades or [])[:500]
                ],
                equity_curve=build_equity_curve_response(result.equity_curve, result.trades)
                if result.equity_curve
                else None,
            )
            db.add(db_backtest)

            # Update strategy metrics with best/latest results
            if result.metrics:
                strategy.total_return = result.metrics.total_return  # type: ignore[assignment]
                strategy.sharpe_ratio = result.metrics.sharpe_ratio  # type: ignore[assignment]
                strategy.win_rate = result.metrics.win_rate  # type: ignore[assignment]
                strategy.total_trades = result.metrics.total_trades  # type: ignore[assignment]
                strategy.backtest_count = _safe_int(strategy.backtest_count) + 1  # type: ignore[assignment]
                strategy.last_backtest_at = datetime.now(UTC)  # type: ignore[assignment]

            db.commit()
            saved_to_db = True
            logger.info(f"Saved backtest result to database for strategy {strategy_id}")

        except Exception as e:
            logger.error(f"Failed to save backtest to database: {e}")
            db.rollback()

    return RunFromStrategyResponse(
        backtest_id=result.id,
        strategy_id=strategy_id,
        strategy_name=str(strategy.name or ""),
        status="completed",
        metrics=metrics_dict,
        saved_to_db=saved_to_db,
    )


@router.get("/by-strategy/{strategy_id}")
async def list_backtests_for_strategy(
    strategy_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
):
    """
    List all backtests for a specific strategy.

    Returns paginated list of backtest results saved for this strategy.
    """
    # Verify strategy exists
    strategy = (
        db.query(Strategy)
        .filter(
            Strategy.id == strategy_id,
            Strategy.is_deleted == False,  # noqa: E712
        )
        .first()
    )

    if strategy is None:
        raise HTTPException(
            status_code=404,
            detail=f"Strategy {strategy_id} not found",
        )

    # Query backtests
    query = (
        db.query(BacktestModel)
        .filter(
            BacktestModel.strategy_id == strategy_id,
        )
        .order_by(BacktestModel.created_at.desc())
    )

    total = query.count()
    offset = (page - 1) * limit
    backtests = query.offset(offset).limit(limit).all()

    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy.name,
        "total": total,
        "page": page,
        "page_size": limit,
        "items": [bt.to_dict() for bt in backtests],
    }


class SaveOptimizationResultRequest(BaseModel):
    """Request to save optimization result as a backtest"""

    name: str = Field(..., description="Name for the backtest")
    strategy_id: str | None = Field(default=None, description="Link to parent strategy for metrics update")
    config: dict = Field(..., description="Backtest configuration")
    results: dict = Field(..., description="Performance metrics")
    status: str = Field(default="completed")
    metadata: dict | None = Field(default=None, description="Additional metadata")


class SaveOptimizationResultResponse(BaseModel):
    """Response after saving optimization result"""

    id: str
    name: str
    status: str
    created_at: str


@router.post("/save-optimization", response_model=SaveOptimizationResultResponse)
async def save_optimization_result(
    request: SaveOptimizationResultRequest,
    db: Session = Depends(get_db),
):
    """
    Save optimization best result as a backtest record.

    This allows viewing detailed metrics on the backtest results page
    after running an optimization.
    """
    logger.info(f"Saving optimization result: {request.name}")

    try:
        config = request.config
        results = request.results

        # ============================================
        # RUN FULL BACKTEST to get trades and equity curve
        # Optimization only returns metrics, not actual trades
        # IMPORTANT: Always run full backtest because trades from request
        # may be aggregated from multiple optimization runs (wrong count)
        # ============================================
        trades_list = []  # Ignore trades from request - they are often wrong
        equity_curve_data = results.get("equity_curve", []) or []

        logger.info(
            "[save_optimization_result] Will run full backtest to get accurate trades (ignoring request trades)"
        )

        # Always run a full backtest with best params to get correct trades
        if True:  # Always run
            try:
                from datetime import datetime as dt

                import pandas as pd

                from backend.backtesting.engine import BacktestEngine
                from backend.backtesting.models import BacktestConfig, StrategyType
                from backend.services.data_service import DataService

                logger.info("Running full backtest to get trades and equity curve...")

                # Parse dates
                start_date = config.get("start_date", dt.now().isoformat())
                end_date = config.get("end_date", dt.now().isoformat())
                if isinstance(start_date, str):
                    start_date = dt.fromisoformat(start_date.replace("Z", "+00:00"))
                if isinstance(end_date, str):
                    end_date = dt.fromisoformat(end_date.replace("Z", "+00:00"))

                # Load market data
                # IMPORTANT: Normalize interval format to match database format
                # Frontend may send "15m", "1h", "4h", "1d" but DB stores "15", "60", "240", "D"
                raw_interval = config.get("interval", "30")
                # Bybit API v5: 1,3,5,15,30,60,120,240,360,720,D,W,M
                interval_map = {
                    "1m": "1",
                    "3m": "3",
                    "5m": "5",
                    "15m": "15",
                    "30m": "30",
                    "1h": "60",
                    "2h": "120",
                    "4h": "240",
                    "6h": "360",
                    "12h": "720",
                    "1d": "D",
                    "1w": "W",
                    "1M": "M",
                    "M": "M",
                }
                db_interval = interval_map.get(raw_interval, raw_interval)
                logger.info(f"[save_optimization_result] Normalized interval: {raw_interval} -> {db_interval}")

                data_service = DataService(db)
                candle_records = data_service.get_market_data(
                    symbol=config.get("symbol", "BTCUSDT"),
                    timeframe=db_interval,
                    start_time=start_date,
                    end_time=end_date,
                )

                logger.info(
                    f"[save_optimization_result] DataService returned {len(candle_records) if candle_records else 0} candles for {config.get('symbol')}/{config.get('interval')}"
                )

                if candle_records:
                    candles = pd.DataFrame(
                        [
                            {
                                "timestamp": pd.to_datetime(c.open_time, unit="ms", utc=True),
                                "open": float(c.open_price) if c.open_price else 0,
                                "high": float(c.high_price) if c.high_price else 0,
                                "low": float(c.low_price) if c.low_price else 0,
                                "close": float(c.close_price) if c.close_price else 0,
                                "volume": float(c.volume) if c.volume else 0,
                            }
                            for c in candle_records
                        ]
                    )
                    candles.set_index("timestamp", inplace=True)

                    # Determine strategy type
                    strategy_type_str = config.get("strategy_type", "rsi").lower()
                    if strategy_type_str == "rsi":
                        strategy_type_enum = StrategyType.RSI
                    else:
                        strategy_type_enum = StrategyType.SMA_CROSSOVER

                    # Build BacktestConfig
                    # IMPORTANT: Use best_params from optimization results, NOT config.strategy_params!
                    # config.strategy_params contains default/original params, not optimized ones.
                    best_params = results.get("best_params", config.get("strategy_params", {}))
                    logger.info(f"Running full backtest with best_params: {best_params}")

                    backtest_config = BacktestConfig(
                        symbol=config.get("symbol", "BTCUSDT"),
                        interval=config.get("interval", "30"),
                        start_date=start_date,
                        end_date=end_date,
                        strategy_type=strategy_type_enum,
                        strategy_params=best_params,  # Use optimized params!
                        initial_capital=config.get("initial_capital", 10000.0),
                        leverage=config.get("leverage", 10),
                        direction=config.get("direction", "both"),
                        stop_loss=config.get("stop_loss_pct", 0) / 100 if config.get("stop_loss_pct") else None,
                        take_profit=config.get("take_profit_pct", 0) / 100 if config.get("take_profit_pct") else None,
                        taker_fee=config.get("commission", 0.0006),
                        maker_fee=config.get("commission", 0.0006),
                    )

                    # Run full backtest
                    engine = BacktestEngine()
                    full_result = engine.run(backtest_config, candles, silent=True)

                    logger.info(
                        f"[save_optimization_result] Backtest result: status={full_result.status if full_result else 'None'}, trades={len(full_result.trades) if full_result and full_result.trades else 0}, error={full_result.error_message if full_result else 'N/A'}"
                    )

                    if full_result and full_result.trades:
                        # Convert trades to dict list for JSON storage
                        # Truncate trades if there are too many to avoid exceeding JSON/DB limits
                        MAX_TRADES_TO_SAVE = 5000
                        if len(full_result.trades) > MAX_TRADES_TO_SAVE:
                            logger.warning(
                                f"Too many trades ({len(full_result.trades)}), truncating to {MAX_TRADES_TO_SAVE}"
                            )
                            trades_list = [t.model_dump() for t in full_result.trades[:MAX_TRADES_TO_SAVE]]
                        else:
                            trades_list = [t.model_dump() for t in full_result.trades]

                        # IMPORTANT: Convert Pandas Timestamp objects to ISO strings for JSON serialization
                        def serialize_trade(trade_dict):
                            """Convert Timestamp objects to ISO format strings"""
                            for key, value in trade_dict.items():
                                if hasattr(value, "isoformat"):
                                    trade_dict[key] = value.isoformat()
                                elif hasattr(value, "timestamp"):
                                    # Pandas Timestamp
                                    trade_dict[key] = pd.Timestamp(value).isoformat()
                            return trade_dict

                        trades_list = [serialize_trade(t) for t in trades_list]
                        logger.info(f"Got {len(trades_list)} trades from full backtest")
                        # Update total_trades metric from full result if present
                        if full_result.metrics and hasattr(full_result.metrics, "total_trades"):
                            results["total_trades"] = getattr(full_result.metrics, "total_trades", len(trades_list))
                        # Truncate trades to match total_trades metric (avoid excess entries)
                        metric_total = results.get("total_trades", len(trades_list))
                        if len(trades_list) > metric_total:
                            trades_list = trades_list[:metric_total]
                            logger.info(f"Truncated trades to metric total_trades={metric_total}")

                        # CRITICAL: Update ALL summary metrics from full_result.metrics
                        # This ensures "ВСЕ" column matches "ДЛИННАЯ/КОРОТКАЯ" columns
                        logger.info(
                            f"[save_optimization_result] full_result.metrics exists: {full_result.metrics is not None}, type: {type(full_result.metrics) if full_result.metrics else 'None'}"
                        )
                        if full_result.metrics:
                            m = full_result.metrics
                            logger.info(
                                f"[save_optimization_result] Metrics object attrs: winning_trades={getattr(m, 'winning_trades', 'N/A')}, losing_trades={getattr(m, 'losing_trades', 'N/A')}"
                            )
                            # Core summary metrics
                            results["winning_trades"] = getattr(m, "winning_trades", 0)
                            results["losing_trades"] = getattr(m, "losing_trades", 0)
                            results["win_rate"] = getattr(m, "win_rate", 0)
                            results["profit_factor"] = getattr(m, "profit_factor", 0)

                            # Profit/Loss metrics
                            results["net_profit"] = getattr(m, "net_profit", 0)
                            results["net_profit_pct"] = getattr(m, "net_profit_pct", 0)
                            results["gross_profit"] = getattr(m, "gross_profit", 0)
                            results["gross_loss"] = getattr(m, "gross_loss", 0)
                            results["total_commission"] = getattr(m, "total_commission", 0)

                            # Average trade metrics
                            # Average trade metrics
                            results["avg_trade"] = getattr(m, "avg_trade", 0)
                            results["avg_win"] = getattr(m, "avg_win", 0)
                            results["avg_loss"] = getattr(m, "avg_loss", 0)
                            results["best_trade"] = getattr(m, "best_trade", 0)  # USD
                            results["worst_trade"] = getattr(m, "worst_trade", 0)  # USD

                            # Currency ($) metrics - CRITICAL for frontend display
                            results["avg_trade_value"] = getattr(m, "avg_trade_value", 0)
                            results["avg_win_value"] = getattr(m, "avg_win_value", 0)
                            results["avg_loss_value"] = getattr(m, "avg_loss_value", 0)

                            logger.info(
                                f"[metrics_debug] Avg ($): win={results['avg_win_value']}, loss={results['avg_loss_value']}"
                            )

                            results["best_trade_pct"] = getattr(m, "best_trade_pct", 0)
                            results["worst_trade_pct"] = getattr(m, "worst_trade_pct", 0)

                            # Duration metrics
                            results["avg_bars_in_trade"] = getattr(m, "avg_bars_in_trade", 0)
                            results["avg_bars_in_winning"] = getattr(m, "avg_bars_in_winning", 0)
                            results["avg_bars_in_losing"] = getattr(m, "avg_bars_in_losing", 0)

                            # Drawdown and risk metrics
                            results["max_drawdown"] = getattr(m, "max_drawdown", 0)
                            results["max_drawdown_pct"] = getattr(m, "max_drawdown_pct", 0)
                            results["sharpe_ratio"] = getattr(m, "sharpe_ratio", 0)
                            results["sortino_ratio"] = getattr(m, "sortino_ratio", 0)
                            results["calmar_ratio"] = getattr(m, "calmar_ratio", 0)

                            # Consecutive wins/losses
                            results["max_consecutive_wins"] = getattr(m, "max_consecutive_wins", 0)
                            results["max_consecutive_losses"] = getattr(m, "max_consecutive_losses", 0)

                            # Final capital from full result
                            if hasattr(m, "final_capital"):
                                results["final_capital"] = getattr(m, "final_capital", 0)

                            logger.info(
                                f"[save_optimization_result] Updated summary metrics from full backtest: total_trades={results.get('total_trades')}, winning={results.get('winning_trades')}, losing={results.get('losing_trades')}, net_profit={results.get('net_profit')}"
                            )

                        # Also update Long/Short metrics from the full result
                        if full_result.metrics:
                            m = full_result.metrics
                            results["long_trades"] = getattr(m, "long_trades", 0)
                            results["long_winning_trades"] = getattr(m, "long_winning_trades", 0)
                            results["long_losing_trades"] = getattr(m, "long_losing_trades", 0)
                            results["long_win_rate"] = getattr(m, "long_win_rate", 0)
                            results["long_gross_profit"] = getattr(m, "long_gross_profit", 0)
                            results["long_gross_loss"] = getattr(m, "long_gross_loss", 0)
                            results["long_net_profit"] = getattr(m, "long_net_profit", 0)
                            results["long_profit_factor"] = getattr(m, "long_profit_factor", 0)
                            results["long_avg_win"] = getattr(m, "long_avg_win", 0)
                            results["long_avg_loss"] = getattr(m, "long_avg_loss", 0)
                            results["short_trades"] = getattr(m, "short_trades", 0)
                            results["short_winning_trades"] = getattr(m, "short_winning_trades", 0)
                            results["short_losing_trades"] = getattr(m, "short_losing_trades", 0)
                            results["short_win_rate"] = getattr(m, "short_win_rate", 0)
                            results["short_gross_profit"] = getattr(m, "short_gross_profit", 0)
                            results["short_gross_loss"] = getattr(m, "short_gross_loss", 0)
                            results["short_net_profit"] = getattr(m, "short_net_profit", 0)
                            results["short_profit_factor"] = getattr(m, "short_profit_factor", 0)
                            results["short_avg_win"] = getattr(m, "short_avg_win", 0)
                            results["short_avg_loss"] = getattr(m, "short_avg_loss", 0)

                            # Add avg_trade metrics for Long/Short
                            results["long_avg_trade"] = getattr(m, "long_avg_trade", 0)
                            results["long_avg_trade_value"] = getattr(m, "long_avg_trade_value", 0)
                            results["long_avg_trade_pct"] = getattr(m, "long_avg_trade_pct", 0)
                            results["short_avg_trade"] = getattr(m, "short_avg_trade", 0)
                            results["short_avg_trade_value"] = getattr(m, "short_avg_trade_value", 0)
                            results["short_avg_trade_pct"] = getattr(m, "short_avg_trade_pct", 0)

                            # Add _value and _pct variants for long/short avg_win and avg_loss
                            results["long_avg_win_value"] = getattr(
                                m, "long_avg_win_value", getattr(m, "long_avg_win", 0)
                            )
                            results["long_avg_win_pct"] = getattr(m, "long_avg_win_pct", 0)
                            results["long_avg_loss_value"] = getattr(
                                m, "long_avg_loss_value", getattr(m, "long_avg_loss", 0)
                            )
                            results["long_avg_loss_pct"] = getattr(m, "long_avg_loss_pct", 0)
                            results["short_avg_win_value"] = getattr(
                                m, "short_avg_win_value", getattr(m, "short_avg_win", 0)
                            )
                            results["short_avg_win_pct"] = getattr(m, "short_avg_win_pct", 0)
                            results["short_avg_loss_value"] = getattr(
                                m,
                                "short_avg_loss_value",
                                getattr(m, "short_avg_loss", 0),
                            )
                            results["short_avg_loss_pct"] = getattr(m, "short_avg_loss_pct", 0)

                            # Add missing bars metrics for Long/Short
                            results["avg_bars_in_long"] = getattr(m, "avg_bars_in_long", 0)
                            results["avg_bars_in_short"] = getattr(m, "avg_bars_in_short", 0)
                            results["avg_bars_in_winning_long"] = getattr(m, "avg_bars_in_winning_long", 0)
                            results["avg_bars_in_winning_short"] = getattr(m, "avg_bars_in_winning_short", 0)
                            results["avg_bars_in_losing_long"] = getattr(m, "avg_bars_in_losing_long", 0)
                            results["avg_bars_in_losing_short"] = getattr(m, "avg_bars_in_losing_short", 0)

                            # CAGR metrics
                            results["cagr"] = getattr(m, "cagr", 0)
                            results["cagr_long"] = getattr(m, "cagr_long", 0)
                            results["cagr_short"] = getattr(m, "cagr_short", 0)

                            # Recovery metrics
                            results["recovery_factor"] = getattr(m, "recovery_factor", 0)
                            results["recovery_long"] = getattr(m, "recovery_long", 0)
                            results["recovery_short"] = getattr(m, "recovery_short", 0)

                            # Buy & Hold and outperformance
                            results["buy_hold_return"] = getattr(m, "buy_hold_return", 0)
                            results["buy_hold_return_pct"] = getattr(m, "buy_hold_return_pct", 0)
                            results["strategy_outperformance"] = getattr(m, "strategy_outperformance", 0)

                            # Drawdown value metrics
                            results["max_drawdown_value"] = getattr(m, "max_drawdown_value", 0)
                            results["max_drawdown_pct"] = getattr(m, "max_drawdown", 0)

                            # Best/worst trade and expectancy
                            results["expectancy"] = getattr(m, "expectancy", 0)
                            results["largest_win"] = getattr(m, "largest_win", 0)
                            results["largest_loss"] = getattr(m, "largest_loss", 0)
                            results["best_trade_pct"] = (
                                getattr(m, "best_trade", 0) if getattr(m, "best_trade", 0) else 0
                            )
                            results["worst_trade_pct"] = (
                                getattr(m, "worst_trade", 0) if getattr(m, "worst_trade", 0) else 0
                            )

                            # IMPORTANT: Long/Short advanced metrics (consecutive wins/losses, payoff ratio, expectancy)
                            # These are calculated by MetricsCalculator but were missing from results extraction
                            results["long_max_consec_wins"] = getattr(m, "long_max_consec_wins", 0)
                            results["long_max_consec_losses"] = getattr(m, "long_max_consec_losses", 0)
                            results["short_max_consec_wins"] = getattr(m, "short_max_consec_wins", 0)
                            results["short_max_consec_losses"] = getattr(m, "short_max_consec_losses", 0)
                            results["long_payoff_ratio"] = getattr(m, "long_payoff_ratio", 0)
                            results["short_payoff_ratio"] = getattr(m, "short_payoff_ratio", 0)
                            results["long_expectancy"] = getattr(m, "long_expectancy", 0)
                            results["short_expectancy"] = getattr(m, "short_expectancy", 0)
                            results["long_largest_win"] = getattr(m, "long_largest_win", 0)
                            results["long_largest_loss"] = getattr(m, "long_largest_loss", 0)
                            results["short_largest_win"] = getattr(m, "short_largest_win", 0)
                            results["short_largest_loss"] = getattr(m, "short_largest_loss", 0)

                    if full_result and full_result.equity_curve:
                        ec = full_result.equity_curve
                        if hasattr(ec, "timestamps") and hasattr(ec, "equity"):
                            drawdowns = ec.drawdown if hasattr(ec, "drawdown") and ec.drawdown else [0] * len(ec.equity)
                            equity_curve_data = [
                                {
                                    "timestamp": t.isoformat() if hasattr(t, "isoformat") else str(t),
                                    "equity": v,
                                    "drawdown": d,
                                }
                                for t, v, d in zip(ec.timestamps, ec.equity, drawdowns)
                            ]
                            logger.info("Got %s equity curve points", len(equity_curve_data))
                        else:
                            logger.warning("Equity curve missing timestamps or equity attributes")
                    else:
                        logger.warning("Full backtest result missing equity_curve")

            except Exception as backtest_err:
                logger.warning("Failed to run full backtest for trades: %s", backtest_err)
                # Continue with empty trades/equity curve

        # ============================================

        # Calculate derived metrics
        initial_capital = config.get("initial_capital", 10000.0)

        # Use net_profit from results if available (already includes commission)
        # Otherwise calculate from total_return (backwards compatibility)
        net_profit = results.get("net_profit")
        if net_profit is None:
            total_return_pct = results.get("total_return_pct", results.get("total_return", 0))
            net_profit = initial_capital * total_return_pct / 100

        final_capital = initial_capital + net_profit
        total_return_pct = (net_profit / initial_capital * 100) if initial_capital > 0 else 0

        # Store ALL metrics in parameters for full restoration
        full_metrics = {
            "strategy_params": config.get("strategy_params", {}),
            "stop_loss_pct": config.get("stop_loss_pct", 0),
            "take_profit_pct": config.get("take_profit_pct", 0),
            "leverage": config.get("leverage", 10),
            "direction": config.get("direction", "long"),
            # Store optimization results for full restoration
            "optimization_metrics": {
                "net_profit": net_profit,
                "net_profit_pct": total_return_pct,
                "gross_profit": results.get("gross_profit", 0),
                "gross_loss": results.get("gross_loss", 0),
                "annual_return": results.get("annual_return", 0),
                "calmar_ratio": results.get("calmar_ratio", 0),
                "avg_drawdown": results.get("avg_drawdown", 0),
                "max_drawdown_duration_days": results.get("max_drawdown_duration_days", 0),
                "avg_win": results.get("avg_win", 0),
                "avg_loss": results.get("avg_loss", 0),
                "avg_trade": results.get("avg_trade", 0),
                "avg_win_value": results.get("avg_win_value", 0),
                "avg_loss_value": results.get("avg_loss_value", 0),
                "avg_trade_value": results.get("avg_trade_value", 0),
                "largest_win": results.get("largest_win", 0),
                "largest_loss": results.get("largest_loss", 0),
                "largest_win_value": results.get("largest_win_value", 0),
                "largest_loss_value": results.get("largest_loss_value", 0),
                "avg_win_pct": results.get("avg_win_pct", results.get("avg_win", 0)),
                "avg_loss_pct": results.get("avg_loss_pct", results.get("avg_loss", 0)),
                "max_consecutive_wins": results.get("max_consecutive_wins", 0),
                "max_consecutive_losses": results.get("max_consecutive_losses", 0),
                "exposure_time": results.get("exposure_time", 0),
                "avg_trade_duration_hours": results.get("avg_trade_duration_hours", 0),
                "avg_bars_in_trade": results.get("avg_bars_in_trade", 0),
                "avg_bars_in_winning": results.get("avg_bars_in_winning", 0),
                "avg_bars_in_losing": results.get("avg_bars_in_losing", 0),
                "best_trade_pct": results.get("best_trade_pct", 0),
                "worst_trade_pct": results.get("worst_trade_pct", 0),
                # best/worst trade in USD (from largest_win/loss or best_trade)
                "best_trade": results.get("best_trade", results.get("largest_win", 0)),
                "worst_trade": results.get("worst_trade", results.get("largest_loss", 0)),
                "recovery_factor": results.get("recovery_factor", 0),
                "expectancy": results.get("expectancy", 0),
                "buy_hold_return": results.get("buy_hold_return", 0),
                # Core trade statistics
                "total_trades": results.get("total_trades", len(trades_list) if trades_list else 0),
                "winning_trades": results.get("winning_trades", 0),
                "losing_trades": results.get("losing_trades", 0),
                "win_rate": results.get("win_rate", 0),
                # Long/Short statistics
                "long_trades": results.get("long_trades", 0),
                "long_winning_trades": results.get("long_winning_trades", 0),
                "long_losing_trades": results.get("long_losing_trades", 0),
                "long_win_rate": results.get("long_win_rate", 0),
                "long_gross_profit": results.get("long_gross_profit", 0),
                "long_gross_loss": results.get("long_gross_loss", 0),
                "long_net_profit": results.get("long_net_profit", 0),
                "long_profit_factor": results.get("long_profit_factor", 0),
                "long_avg_win": results.get("long_avg_win", 0),
                "long_avg_loss": results.get("long_avg_loss", 0),
                "long_avg_win_pct": results.get("long_avg_win_pct", results.get("long_avg_win", 0)),
                "long_avg_loss_pct": results.get("long_avg_loss_pct", results.get("long_avg_loss", 0)),
                "long_largest_win": results.get("long_largest_win", 0),
                "long_largest_loss": results.get("long_largest_loss", 0),
                "short_trades": results.get("short_trades", 0),
                "short_winning_trades": results.get("short_winning_trades", 0),
                "short_losing_trades": results.get("short_losing_trades", 0),
                "short_win_rate": results.get("short_win_rate", 0),
                "short_gross_profit": results.get("short_gross_profit", 0),
                "short_gross_loss": results.get("short_gross_loss", 0),
                "short_net_profit": results.get("short_net_profit", 0),
                "short_profit_factor": results.get("short_profit_factor", 0),
                "short_avg_win": results.get("short_avg_win", 0),
                "short_avg_loss": results.get("short_avg_loss", 0),
                "short_avg_win_pct": results.get("short_avg_win_pct", results.get("short_avg_win", 0)),
                "short_avg_loss_pct": results.get("short_avg_loss_pct", results.get("short_avg_loss", 0)),
                "short_largest_win": results.get("short_largest_win", 0),
                "short_largest_loss": results.get("short_largest_loss", 0),
                # Average bars in trade by Long/Short
                "avg_bars_in_long": results.get("avg_bars_in_long", 0),
                "avg_bars_in_short": results.get("avg_bars_in_short", 0),
                "avg_bars_in_winning_long": results.get("avg_bars_in_winning_long", 0),
                "avg_bars_in_losing_long": results.get("avg_bars_in_losing_long", 0),
                "avg_bars_in_winning_short": results.get("avg_bars_in_winning_short", 0),
                "avg_bars_in_losing_short": results.get("avg_bars_in_losing_short", 0),
                # Long/Short consecutive wins/losses (TradingView)
                "long_max_consec_wins": results.get("long_max_consec_wins", 0),
                "long_max_consec_losses": results.get("long_max_consec_losses", 0),
                "short_max_consec_wins": results.get("short_max_consec_wins", 0),
                "short_max_consec_losses": results.get("short_max_consec_losses", 0),
                # Long/Short payoff ratio and expectancy
                "long_payoff_ratio": results.get("long_payoff_ratio", 0),
                "short_payoff_ratio": results.get("short_payoff_ratio", 0),
                "long_expectancy": results.get("long_expectancy", 0),
                "short_expectancy": results.get("short_expectancy", 0),
                # Recovery factor by direction
                "recovery_long": results.get("recovery_long", 0),
                "recovery_short": results.get("recovery_short", 0),
            },
            **(request.metadata or {}),
        }

        # Lookup strategy if strategy_id is provided
        strategy = None
        if request.strategy_id:
            strategy = db.query(Strategy).filter(Strategy.id == request.strategy_id).first()

        # Create backtest record with ALL available fields
        db_backtest = BacktestModel(
            strategy_id=strategy.id if strategy else None,  # Link to parent strategy
            strategy_type=config.get("strategy_type", "rsi"),
            symbol=config.get("symbol", "BTCUSDT"),
            timeframe=config.get("interval", "30"),
            start_date=datetime.fromisoformat(config.get("start_date", datetime.now().isoformat())),
            end_date=datetime.fromisoformat(config.get("end_date", datetime.now().isoformat())),
            initial_capital=initial_capital,
            parameters=full_metrics,
            status=DBBacktestStatus.COMPLETED,
            # Main performance metrics
            total_return=total_return_pct,
            annual_return=results.get("annual_return", 0),
            sharpe_ratio=results.get("sharpe_ratio", 0),
            sortino_ratio=results.get("sortino_ratio", 0),
            calmar_ratio=results.get("calmar_ratio", 0),
            max_drawdown=results.get("max_drawdown_pct", results.get("max_drawdown", 0)),
            win_rate=results.get("win_rate", 0),
            profit_factor=results.get("profit_factor", 0),
            # Trade statistics
            total_trades=results.get("total_trades", 0),
            winning_trades=results.get("winning_trades", 0),
            losing_trades=results.get("losing_trades", 0),
            avg_trade_pnl=results.get("avg_trade_return", 0),
            best_trade=results.get("best_trade_pct", 0),
            worst_trade=results.get("worst_trade_pct", 0),
            # Portfolio stats
            final_capital=final_capital,
            peak_capital=results.get("peak_capital", final_capital),
            # Store trades and equity curve from full backtest
            trades=trades_list,
            equity_curve=equity_curve_data,
            metrics_json=results,  # Store full results dict as metrics_json
        )

        db.add(db_backtest)

        # Update strategy metrics if linked
        if strategy:
            strategy.total_return = total_return_pct  # type: ignore[assignment]
            strategy.sharpe_ratio = results.get("sharpe_ratio", 0)  # type: ignore[assignment]
            strategy.win_rate = results.get("win_rate", 0)  # type: ignore[assignment]
            strategy.total_trades = results.get("total_trades", 0)  # type: ignore[assignment]
            strategy.backtest_count = _safe_int(strategy.backtest_count) + 1  # type: ignore[assignment]
            strategy.last_backtest_at = datetime.now(UTC)  # type: ignore[assignment]
            logger.info(f"Updated strategy {strategy.id} metrics from optimization")

        db.commit()
        db.refresh(db_backtest)

        logger.info(f"Saved optimization backtest with ID: {db_backtest.id}")

        return SaveOptimizationResultResponse(
            id=str(db_backtest.id),
            name=request.name,
            status="completed",
            created_at=db_backtest.created_at.isoformat(),
        )

    except Exception as e:
        logger.error(f"Failed to save optimization result: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# MTF (Multi-Timeframe) BACKTEST ENDPOINT
# ===========================================================================


class MTFBacktestRequest(BaseModel):
    """Request model for MTF backtest."""

    # Standard params
    symbol: str = Field(..., description="Trading pair (e.g., BTCUSDT)")
    interval: str = Field(..., description="LTF interval (e.g., 15m, 5m)")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    initial_capital: float = Field(default=10000.0, ge=100)
    leverage: int = Field(default=10, ge=1, le=125)
    direction: str = Field(default="both", pattern="^(long|short|both)$")

    # Risk management
    stop_loss: float = Field(default=0.02, ge=0.001, le=0.5)
    take_profit: float = Field(default=0.03, ge=0.001, le=1.0)

    # Strategy params
    strategy_type: str = Field(default="rsi", description="Strategy: rsi, sma_crossover")
    strategy_params: dict = Field(default_factory=dict)

    # MTF params
    htf_interval: str = Field(default="60", description="HTF interval (e.g., 60, 240)")
    htf_filter_type: str = Field(default="sma", pattern="^(sma|ema)$")
    htf_filter_period: int = Field(default=200, ge=1, le=500)
    mtf_neutral_zone_pct: float = Field(default=0.0, ge=0.0, le=5.0)

    # BTC correlation (optional)
    use_btc_filter: bool = Field(default=False)
    btc_sma_period: int = Field(default=50, ge=1, le=200)

    # Advanced features (optional)
    trailing_stop_enabled: bool = Field(default=False)
    trailing_stop_activation: float = Field(default=0.01)
    trailing_stop_distance: float = Field(default=0.005)
    breakeven_enabled: bool = Field(default=False)
    dca_enabled: bool = Field(default=False)
    dca_safety_orders: int = Field(default=0, ge=0, le=10)


class MTFBacktestResponse(BaseModel):
    """Response model for MTF backtest."""

    backtest_id: str
    status: str
    is_valid: bool

    # Metrics
    total_trades: int
    filtered_trades: int  # Trades filtered by MTF
    net_profit: float
    total_return_pct: float
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float

    # MTF stats
    mtf_filter_type: str
    mtf_filter_period: int
    htf_interval: str
    long_signals_allowed: int
    short_signals_allowed: int
    long_signals_filtered: int
    short_signals_filtered: int

    # Comparison (MTF vs no MTF)
    baseline_trades: int | None = None
    baseline_pnl: float | None = None
    mtf_improvement_pct: float | None = None

    # Trades (limited)
    trades: list[dict] = Field(default_factory=list)

    # Equity curve
    equity_curve: dict | None = None


@router.post("/mtf", response_model=MTFBacktestResponse)
async def run_mtf_backtest(request: MTFBacktestRequest):
    """
    Run backtest with Multi-Timeframe (MTF) filtering.

    MTF filtering improves strategy performance by:
    - Only taking LONG signals when HTF trend is bullish
    - Only taking SHORT signals when HTF trend is bearish

    **Example Request:**
    ```json
    {
        "symbol": "BTCUSDT",
        "interval": "15m",
        "start_date": "2025-07-01",
        "end_date": "2026-01-26",
        "strategy_type": "rsi",
        "strategy_params": {"period": 14, "oversold": 30, "overbought": 70},
        "htf_interval": "60",
        "htf_filter_type": "sma",
        "htf_filter_period": 200
    }
    ```

    **Strategies:**
    - `rsi`: RSI oversold/overbought crossover
    - `sma_crossover`: Golden/Death cross

    **HTF Filters:**
    - `sma`: Simple Moving Average (default SMA200)
    - `ema`: Exponential Moving Average
    """
    import sqlite3
    import uuid

    import numpy as np
    import pandas as pd

    from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
    from backend.backtesting.interfaces import BacktestInput
    from backend.backtesting.mtf.index_mapper import create_htf_index_map
    from backend.backtesting.mtf.signals import (
        generate_mtf_rsi_signals,
        generate_mtf_signals_with_btc,
        generate_mtf_sma_crossover_signals,
    )

    logger.info(
        f"MTF Backtest: {request.symbol} {request.interval} → HTF {request.htf_interval} "
        f"filter={request.htf_filter_type.upper()}{request.htf_filter_period}"
    )

    try:
        # Load LTF data
        conn = sqlite3.connect("data.sqlite3")
        ltf_query = f"""
            SELECT open_time, open_price as open, high_price as high,
                   low_price as low, close_price as close, volume
            FROM bybit_kline_audit
            WHERE symbol = '{request.symbol}'
              AND interval = '{request.interval.replace("m", "")}'
              AND open_time >= {int(pd.Timestamp(request.start_date).timestamp() * 1000)}
              AND open_time <= {int(pd.Timestamp(request.end_date).timestamp() * 1000)}
            ORDER BY open_time
        """
        ltf_df = pd.read_sql(ltf_query, conn)

        if ltf_df.empty:
            raise HTTPException(
                status_code=400,
                detail=f"No LTF data found for {request.symbol} {request.interval}",
            )

        # Convert to datetime index
        ltf_df["open_time"] = pd.to_datetime(ltf_df["open_time"], unit="ms")
        ltf_df.set_index("open_time", inplace=True)

        # Load HTF data
        htf_interval = request.htf_interval.replace("m", "")
        htf_query = f"""
            SELECT open_time, open_price as open, high_price as high,
                   low_price as low, close_price as close, volume
            FROM bybit_kline_audit
            WHERE symbol = '{request.symbol}'
              AND interval = '{htf_interval}'
              AND open_time >= {int(pd.Timestamp(request.start_date).timestamp() * 1000)}
              AND open_time <= {int(pd.Timestamp(request.end_date).timestamp() * 1000)}
            ORDER BY open_time
        """
        htf_df = pd.read_sql(htf_query, conn)

        if htf_df.empty:
            raise HTTPException(
                status_code=400,
                detail=f"No HTF data found for {request.symbol} {request.htf_interval}",
            )

        htf_df["open_time"] = pd.to_datetime(htf_df["open_time"], unit="ms")
        htf_df.set_index("open_time", inplace=True)

        # Load BTC data if needed
        btc_df = None
        btc_index_map = None
        if request.use_btc_filter and request.symbol != "BTCUSDT":
            btc_query = f"""
                SELECT open_time, open_price as open, high_price as high,
                       low_price as low, close_price as close, volume
                FROM bybit_kline_audit
                WHERE symbol = 'BTCUSDT'
                  AND interval = '{htf_interval}'
                  AND open_time >= {int(pd.Timestamp(request.start_date).timestamp() * 1000)}
                  AND open_time <= {int(pd.Timestamp(request.end_date).timestamp() * 1000)}
                ORDER BY open_time
            """
            btc_df = pd.read_sql(btc_query, conn)
            if not btc_df.empty:
                btc_df["open_time"] = pd.to_datetime(btc_df["open_time"], unit="ms")
                btc_df.set_index("open_time", inplace=True)
                btc_index_map = create_htf_index_map(ltf_df, btc_df)

        conn.close()

        # Create HTF index map
        htf_index_map = create_htf_index_map(ltf_df, htf_df)

        # Generate MTF signals
        strategy_params = request.strategy_params.copy()

        if request.use_btc_filter and btc_df is not None and btc_index_map is not None:
            long_entries, long_exits, short_entries, short_exits = generate_mtf_signals_with_btc(
                ltf_candles=ltf_df,
                htf_candles=htf_df,
                htf_index_map=htf_index_map,
                btc_candles=btc_df,
                btc_index_map=btc_index_map,
                strategy_type=request.strategy_type,
                strategy_params=strategy_params,
                htf_filter_type=request.htf_filter_type,
                htf_filter_period=request.htf_filter_period,
                btc_filter_period=request.btc_sma_period,
                direction=request.direction,
            )
        elif request.strategy_type == "rsi":
            long_entries, long_exits, short_entries, short_exits = generate_mtf_rsi_signals(
                ltf_candles=ltf_df,
                htf_candles=htf_df,
                htf_index_map=htf_index_map,
                htf_filter_type=request.htf_filter_type,
                htf_filter_period=request.htf_filter_period,
                neutral_zone_pct=request.mtf_neutral_zone_pct,
                direction=request.direction,
                **strategy_params,
            )
        elif request.strategy_type == "sma_crossover":
            long_entries, long_exits, short_entries, short_exits = generate_mtf_sma_crossover_signals(
                ltf_candles=ltf_df,
                htf_candles=htf_df,
                htf_index_map=htf_index_map,
                htf_filter_type=request.htf_filter_type,
                htf_filter_period=request.htf_filter_period,
                neutral_zone_pct=request.mtf_neutral_zone_pct,
                direction=request.direction,
                **strategy_params,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown strategy type: {request.strategy_type}",
            )

        # Count signals
        n_long_entries = int(np.sum(long_entries))
        n_short_entries = int(np.sum(short_entries))

        # Build BacktestInput
        input_data = BacktestInput(
            symbol=request.symbol,
            interval=request.interval,
            initial_capital=request.initial_capital,
            leverage=request.leverage,
            direction=TradeDirection(request.direction),
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            # MTF
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type=request.htf_filter_type,
            mtf_filter_period=request.htf_filter_period,
            # Advanced features
            trailing_stop_enabled=request.trailing_stop_enabled,
            trailing_stop_activation=request.trailing_stop_activation,
            trailing_stop_distance=request.trailing_stop_distance,
            breakeven_enabled=request.breakeven_enabled,
            dca_enabled=request.dca_enabled,
            dca_safety_orders=request.dca_safety_orders,
        )

        # Run backtest
        engine = FallbackEngineV4()
        result = engine.run(input_data)

        # Build response
        m = result.metrics
        backtest_id = str(uuid.uuid4())[:8]

        # Format trades for response
        trades_list = []
        for t in (result.trades or [])[:100]:
            trades_list.append(
                {
                    "entry_time": str(t.entry_time) if t.entry_time else None,
                    "exit_time": str(t.exit_time) if t.exit_time else None,
                    "direction": t.direction,
                    "entry_price": float(t.entry_price),
                    "exit_price": float(t.exit_price),
                    "pnl": float(t.pnl),
                    "pnl_pct": float(t.pnl_pct),
                    "exit_reason": str(t.exit_reason) if t.exit_reason else None,
                }
            )

        return MTFBacktestResponse(
            backtest_id=backtest_id,
            status="completed" if result.is_valid else "failed",
            is_valid=result.is_valid,
            total_trades=m.total_trades,
            filtered_trades=0,  # TODO: calculate from baseline comparison
            net_profit=float(m.net_profit),
            total_return_pct=float(m.total_return),
            win_rate=float(m.win_rate),
            max_drawdown=float(m.max_drawdown),
            sharpe_ratio=float(m.sharpe_ratio),
            profit_factor=float(m.profit_factor),
            mtf_filter_type=request.htf_filter_type,
            mtf_filter_period=request.htf_filter_period,
            htf_interval=request.htf_interval,
            long_signals_allowed=n_long_entries,
            short_signals_allowed=n_short_entries,
            long_signals_filtered=0,  # TODO
            short_signals_filtered=0,  # TODO
            trades=trades_list,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"MTF backtest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{backtest_id}")
async def delete_backtest(backtest_id: str, db: Session = Depends(get_db)):
    """
    Delete a backtest by ID.
    Removes from both database and in-memory cache.
    """
    # Remove from in-memory cache
    engine = get_engine()
    engine.remove_from_cache(backtest_id)

    bt = db.query(BacktestModel).filter(BacktestModel.id == backtest_id).first()

    if bt is None:
        raise HTTPException(
            status_code=404,
            detail=f"Backtest {backtest_id} not found",
        )

    db.delete(bt)
    db.commit()

    logger.info(f"Deleted backtest {backtest_id} from DB and cache")
    return {"status": "deleted", "id": backtest_id}


@router.delete("/")
async def delete_all_backtests(db: Session = Depends(get_db)):
    """
    Delete all backtests from database and clear in-memory cache.
    """
    # Clear in-memory cache
    engine = get_engine()
    cache_count = engine.clear_cache()

    db_count = db.query(BacktestModel).count()
    db.query(BacktestModel).delete()
    db.commit()

    logger.info(f"Deleted {db_count} backtests from DB and {cache_count} from cache")
    return {"status": "deleted", "db_count": db_count, "cache_count": cache_count}
