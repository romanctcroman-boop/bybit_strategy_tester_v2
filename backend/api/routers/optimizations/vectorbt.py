"""
Optimization Router — VectorBT high-performance grid search endpoints.

Covers:
- POST /vectorbt/grid-search
- GET  /vectorbt/grid-search-stream
"""

# mypy: disable-error-code="arg-type, assignment, var-annotated, return-value, union-attr, operator, attr-defined, misc, dict-item"

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.routers.optimizations.helpers import _normalize_interval
from backend.api.routers.optimizations.workers import _generate_smart_recommendations
from backend.database import get_db
from backend.optimization.models import (
    SmartRecommendation,
    SmartRecommendations,
    VectorbtOptimizationRequest,
    VectorbtOptimizationResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# =============================================================================
# VECTORBT HIGH-PERFORMANCE OPTIMIZATION (100K - 100M+ combinations)
# =============================================================================

# VectorbtOptimizationRequest, VectorbtOptimizationResponse imported from backend.optimization.models


@router.post("/vectorbt/grid-search", response_model=VectorbtOptimizationResponse)
async def vectorbt_grid_search_optimization(
    request: VectorbtOptimizationRequest,
    db: Session = Depends(get_db),
):
    """
    рџљЂ Ultra-Fast Numba JIT Grid Search Optimization.

    Designed for massive parameter spaces (1,000 - 100,000+ combinations).

    Performance targets:
    - 1,000 combinations: < 1 second
    - 10,000 combinations: < 5 seconds
    - 100,000 combinations: < 30 seconds

    Uses:
    - Pure Numba JIT compilation (no VectorBT overhead)
    - Parallel processing with Numba prange
    - Pre-computed RSI caching
    - Vectorized PnL calculation
    """
    from datetime import datetime as dt

    import numpy as np
    import pandas as pd

    from backend.backtesting.fast_optimizer import (
        get_candle_cache,
        load_candles_fast,
    )

    # Use Universal optimizer with auto backend selection (GPU if available, CPU otherwise)
    from backend.backtesting.optimizer import (
        UniversalOptimizer,
        get_available_backends,
        get_recommended_backend,
    )

    backends = get_available_backends()
    recommended = get_recommended_backend()
    optimizer = UniversalOptimizer(backend="auto")
    logger.info(f"рџљЂ Using UniversalOptimizer (auto-backend: {recommended}, GPU: {backends.get('gpu', False)})")

    logger.info("рџљЂ Starting ultra-fast optimization")

    # DEBUG: Log received parameters
    logger.info(f"   RSI Period range: {request.rsi_period_range}")
    logger.info(f"   Overbought range: {request.rsi_overbought_range}")
    logger.info(f"   Oversold range: {request.rsi_oversold_range}")
    logger.info(f"   Stop Loss range: {request.stop_loss_range}")
    logger.info(f"   Take Profit range: {request.take_profit_range}")

    # Calculate total combinations
    total_combinations = (
        len(request.rsi_period_range)
        * len(request.rsi_overbought_range)
        * len(request.rsi_oversold_range)
        * len(request.stop_loss_range)
        * len(request.take_profit_range)
    )

    logger.info(f"   Total combinations: {total_combinations:,}")

    try:
        # Parse dates
        start_dt = dt.fromisoformat(request.start_date)
        end_dt = dt.fromisoformat(request.end_date)
    except Exception as parse_err:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {parse_err}")

    # Normalize interval format: "30m" -> "30", "1h" -> "60", "4h" -> "240", "1d" -> "D"
    interval = _normalize_interval(request.interval)
    logger.info(f"рџ“Љ Normalized interval: {request.interval} -> {interval}")

    # Get DB path from environment with dynamic fallback
    from pathlib import Path

    default_db = str(Path(__file__).resolve().parents[3] / "data.sqlite3")
    db_path = os.environ.get("DATABASE_PATH", default_db)

    try:
        # Load market data via DIRECT SQL (bypass ORM for speed)
        import time as _time

        load_start = _time.perf_counter()

        candle_data = load_candles_fast(
            db_path=db_path,
            symbol=request.symbol,
            interval=interval,
            start_date=start_dt,
            end_date=end_dt,
            use_cache=True,
        )

        load_time = _time.perf_counter() - load_start
        cache_stats = get_candle_cache().stats()
        logger.info(
            f"рџ“Љ Data loaded in {load_time:.3f}s (cache size: {cache_stats['size']}/{cache_stats['max_size']})"
        )

    except Exception as data_err:
        logger.error(f"Direct SQL load failed: {data_err}, falling back to ORM")
        # Fallback to ORM if direct SQL fails
        from backend.services.data_service import DataService

        data_service = DataService(db)
        candle_records = data_service.get_market_data(
            symbol=request.symbol,
            timeframe=interval,
            start_time=start_dt,
            end_time=end_dt,
        )
        if candle_records:
            candle_data = np.array(
                [
                    [
                        c.open_time,
                        c.open_price,
                        c.high_price,
                        c.low_price,
                        c.close_price,
                        c.volume,
                    ]
                    for c in candle_records
                ],
                dtype=np.float64,
            )
        else:
            candle_data = None

    if candle_data is None or len(candle_data) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No data for {request.symbol} interval={interval} (original: {request.interval}). Check that data is loaded.",
        )

    # Convert numpy array to DataFrame
    # candle_data columns: [open_time, open, high, low, close, volume]
    candles = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(candle_data[:, 0], unit="ms", utc=True),
            "open": candle_data[:, 1],
            "high": candle_data[:, 2],
            "low": candle_data[:, 3],
            "close": candle_data[:, 4],
            "volume": candle_data[:, 5],
        }
    )
    candles.set_index("timestamp", inplace=True)

    logger.info(f"рџ“Љ Loaded {len(candles)} candles")

    # Prepare filters
    filters = {}
    if request.min_trades:
        filters["min_trades"] = request.min_trades
    if request.max_drawdown_limit:
        filters["max_drawdown_limit"] = request.max_drawdown_limit
    if request.min_profit_factor:
        filters["min_profit_factor"] = request.min_profit_factor
    if request.min_win_rate:
        filters["min_win_rate"] = request.min_win_rate

    # Prepare weights
    weights = {
        "return": request.weight_return,
        "drawdown": request.weight_drawdown,
        "sharpe": request.weight_sharpe,
        "win_rate": request.weight_win_rate,
    }

    try:
        # Run optimization (GPU optimizer already created above)
        result = optimizer.optimize(
            candles=candles,
            rsi_period_range=request.rsi_period_range,
            rsi_overbought_range=request.rsi_overbought_range,
            rsi_oversold_range=request.rsi_oversold_range,
            stop_loss_range=request.stop_loss_range,
            take_profit_range=request.take_profit_range,
            initial_capital=request.initial_capital,
            leverage=request.leverage,
            commission=request.commission,
            slippage=request.slippage,
            optimize_metric=request.optimize_metric,
            direction=request.direction,
            # position_size removed - not supported by VectorBT optimizer
            weights=weights,
            filters=filters if filters else None,
        )
    except Exception as e:
        logger.exception("Optimization failed")
        raise HTTPException(status_code=500, detail=f"Optimization failed: {e!s}")

    # Enrich best result with full metrics using BacktestEngine
    if result.top_results:
        try:
            from backend.backtesting.engine import BacktestEngine
            from backend.backtesting.models import BacktestConfig, StrategyType

            best = result.top_results[0]
            best_params = best.get("params", {})

            logger.info(f"рџ”„ Enriching best result with full metrics: {best_params}")

            # Build proper BacktestConfig
            backtest_config = BacktestConfig(
                symbol=request.symbol,
                interval=request.interval,
                start_date=dt.fromisoformat(request.start_date),
                end_date=dt.fromisoformat(request.end_date),
                strategy_type=StrategyType.RSI,
                strategy_params={
                    "period": best_params.get("rsi_period", 14),
                    "overbought": best_params.get("rsi_overbought", 70),
                    "oversold": best_params.get("rsi_oversold", 30),
                },
                initial_capital=request.initial_capital,
                leverage=request.leverage,
                # GPU optimizer treats 'both' as 'long' (direction >= 0), so match that here
                direction="long" if request.direction in ("long", "both") else "short",
                stop_loss=best_params.get("stop_loss_pct", 0) / 100 if best_params.get("stop_loss_pct") else None,
                take_profit=best_params.get("take_profit_pct", 0) / 100 if best_params.get("take_profit_pct") else None,
                taker_fee=request.commission,
                maker_fee=request.commission,
                slippage=request.slippage,
                position_size=1.0,  # Match GPU optimizer's 100% allocation
            )

            # Run full backtest
            engine = BacktestEngine()
            full_result = engine.run(backtest_config, candles, silent=True)

            if full_result and full_result.metrics:
                metrics = full_result.metrics
                # Enrich best result with full metrics from PerformanceMetrics
                # Core trade statistics (for header cards)
                best["total_trades"] = getattr(metrics, "total_trades", 0)
                best["winning_trades"] = getattr(metrics, "winning_trades", 0)
                best["losing_trades"] = getattr(metrics, "losing_trades", 0)
                best["win_rate"] = getattr(metrics, "win_rate", 0)
                # Long/Short breakdown
                best["long_trades"] = getattr(metrics, "long_trades", 0)
                best["short_trades"] = getattr(metrics, "short_trades", 0)
                best["long_winning_trades"] = getattr(metrics, "long_winning_trades", 0)
                best["short_winning_trades"] = getattr(metrics, "short_winning_trades", 0)
                best["long_win_rate"] = getattr(metrics, "long_win_rate", 0)
                best["short_win_rate"] = getattr(metrics, "short_win_rate", 0)
                best["long_gross_profit"] = getattr(metrics, "long_gross_profit", 0)
                best["long_gross_loss"] = getattr(metrics, "long_gross_loss", 0)
                best["short_gross_profit"] = getattr(metrics, "short_gross_profit", 0)
                best["short_gross_loss"] = getattr(metrics, "short_gross_loss", 0)
                best["long_net_profit"] = getattr(metrics, "long_net_profit", 0)
                best["short_net_profit"] = getattr(metrics, "short_net_profit", 0)
                best["long_profit_factor"] = getattr(metrics, "long_profit_factor", 0)
                best["short_profit_factor"] = getattr(metrics, "short_profit_factor", 0)
                best["gross_profit"] = getattr(metrics, "gross_profit", 0)
                best["gross_loss"] = getattr(metrics, "gross_loss", 0)
                best["net_profit"] = getattr(metrics, "net_profit", 0)
                best["avg_win"] = getattr(metrics, "avg_win", 0)
                best["avg_loss"] = getattr(metrics, "avg_loss", 0)
                best["avg_trade"] = getattr(metrics, "avg_trade", 0)
                best["avg_win_value"] = getattr(metrics, "avg_win_value", 0)
                best["avg_loss_value"] = getattr(metrics, "avg_loss_value", 0)
                best["avg_trade_value"] = getattr(metrics, "avg_trade_value", 0)
                best["largest_win"] = getattr(metrics, "largest_win", 0)
                best["largest_loss"] = getattr(metrics, "largest_loss", 0)
                best["largest_win_value"] = getattr(metrics, "largest_win_value", 0)
                best["largest_loss_value"] = getattr(metrics, "largest_loss_value", 0)
                best["sharpe_ratio"] = getattr(metrics, "sharpe_ratio", 0)
                best["sortino_ratio"] = getattr(metrics, "sortino_ratio", 0)
                best["calmar_ratio"] = getattr(metrics, "calmar_ratio", 0)
                # Only overwrite max_drawdown if full backtest calculated a valid value
                # GPU optimizer already has correct max_drawdown from simulation
                full_bt_max_dd = getattr(metrics, "max_drawdown", 0)
                if full_bt_max_dd > 0:
                    best["max_drawdown"] = full_bt_max_dd
                    best["max_drawdown_value"] = getattr(metrics, "max_drawdown_value", 0)
                # else: keep GPU optimizer's max_drawdown from top_results[0]
                best["recovery_factor"] = getattr(metrics, "recovery_factor", 0)
                best["expectancy"] = getattr(metrics, "expectancy", 0)
                best["cagr"] = getattr(metrics, "cagr", 0)
                best["total_commission"] = getattr(metrics, "total_commission", 0)

                best["avg_bars_in_trade"] = getattr(metrics, "avg_bars_in_trade", 0)
                best["avg_bars_in_winning"] = getattr(metrics, "avg_bars_in_winning", 0)
                best["avg_bars_in_losing"] = getattr(metrics, "avg_bars_in_losing", 0)

                # Convert trades to dict list
                best["trades"] = [t.model_dump() for t in full_result.trades] if full_result.trades else []

                # Convert equity curve (EquityCurve has timestamps and equity lists)
                if full_result.equity_curve and hasattr(full_result.equity_curve, "timestamps"):
                    ec = full_result.equity_curve
                    drawdowns = ec.drawdown if hasattr(ec, "drawdown") and ec.drawdown else [0] * len(ec.equity)
                    best["equity_curve"] = [
                        {
                            "timestamp": t.isoformat() if hasattr(t, "isoformat") else str(t),
                            "equity": v,
                            "drawdown": d,
                        }
                        for t, v, d in zip(
                            ec.timestamps,
                            ec.equity,
                            drawdowns,
                            strict=False,
                        )
                    ]
                else:
                    best["equity_curve"] = []

                logger.info(
                    f"вњ… Enriched best result with full metrics: Long={best['long_trades']}, Short={best['short_trades']}"
                )

                # Also update best_metrics in result
                result.best_metrics.update(
                    {
                        # Core trade stats
                        "total_trades": best.get("total_trades", len(best.get("trades", []))),
                        "winning_trades": best.get("winning_trades", 0),
                        "losing_trades": best.get("losing_trades", 0),
                        "win_rate": best.get("win_rate", 0),
                        # Long/Short stats
                        "long_trades": best["long_trades"],
                        "short_trades": best["short_trades"],
                        "long_win_rate": best["long_win_rate"],
                        "short_win_rate": best["short_win_rate"],
                        "gross_profit": best["gross_profit"],
                        "gross_loss": best["gross_loss"],
                        "net_profit": best["net_profit"],
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to enrich best result with full metrics: {e}")

    # Generate smart recommendations
    smart_recs = _generate_smart_recommendations(result.top_results)

    # DEBUG: Log trade data
    if result.top_results:
        first = result.top_results[0]
        logger.info(f"DEBUG top_results[0] keys: {list(first.keys())}")
        logger.info(f"DEBUG trades: {len(first.get('trades', [])) if first.get('trades') else 'None'}")
        logger.info(f"DEBUG equity_curve: {first.get('equity_curve') is not None}")

    def _to_recommendation(r: dict) -> SmartRecommendation | None:
        if not r:
            return None
        return SmartRecommendation(
            params=r.get("params"),
            total_return=r.get("total_return"),
            max_drawdown=r.get("max_drawdown"),
            sharpe_ratio=r.get("sharpe_ratio"),
            win_rate=r.get("win_rate"),
            total_trades=r.get("total_trades"),
        )

    smart_recommendations = SmartRecommendations(
        best_balanced=_to_recommendation(smart_recs.get("best_balanced")),
        best_conservative=_to_recommendation(smart_recs.get("best_conservative")),
        best_aggressive=_to_recommendation(smart_recs.get("best_aggressive")),
        recommendation_text=smart_recs.get("recommendation_text", ""),
    )

    # Calculate speed
    speed = int(result.tested_combinations / result.execution_time_seconds) if result.execution_time_seconds > 0 else 0
    num_workers = getattr(result, "num_workers", None) or (os.cpu_count() or 4)

    return VectorbtOptimizationResponse(
        status=result.status,
        total_combinations=result.total_combinations,
        tested_combinations=result.tested_combinations,
        execution_time_seconds=result.execution_time_seconds,
        speed_combinations_per_sec=speed,
        num_workers=num_workers,
        best_params=result.best_params,
        best_score=result.best_score,
        best_metrics=result.best_metrics,
        top_results=result.top_results,
        performance_stats=result.performance_stats,
        smart_recommendations=smart_recommendations,
    )


# =============================================================================
# SSE STREAMING OPTIMIZATION (for large parameter spaces > 2 minutes)
