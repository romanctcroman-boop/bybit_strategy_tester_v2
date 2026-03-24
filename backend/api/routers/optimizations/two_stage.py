"""
Optimization Router — VectorBT streaming and Two-Stage optimization endpoints.

Covers:
- GET  /vectorbt/grid-search-stream (SSE streaming)
- POST /two-stage/optimize
"""

# mypy: disable-error-code="arg-type, assignment, var-annotated, return-value, union-attr, operator, attr-defined, misc, dict-item"

import logging
import os
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.routers.optimizations.helpers import _normalize_interval
from backend.api.routers.optimizations.workers import _generate_smart_recommendations
from backend.database import get_db
from backend.optimization.models import VectorbtOptimizationRequest

logger = logging.getLogger(__name__)
router = APIRouter()

# =============================================================================


@router.get("/vectorbt/grid-search-stream")
async def vectorbt_grid_search_stream(
    symbol: str = Query("BTCUSDT"),
    interval: str = Query("30m"),
    start_date: str = Query(...),
    end_date: str = Query(...),
    direction: str = Query("long"),
    leverage: int = Query(10),
    initial_capital: float = Query(10000.0),
    commission: float = Query(0.0007, description="0.07% TradingView parity"),
    position_size: float = Query(1.0),
    rsi_period_range: str = Query("7,14,21"),
    rsi_overbought_range: str = Query("70,75,80"),
    rsi_oversold_range: str = Query("20,25,30"),
    stop_loss_range: str = Query("5.0,10.0,15.0"),
    take_profit_range: str = Query("1.0,2.0,3.0"),
    optimize_metric: str = Query("sharpe_ratio"),
    weight_return: float = Query(0.4),
    weight_drawdown: float = Query(0.3),
    weight_sharpe: float = Query(0.2),
    weight_win_rate: float = Query(0.1),
    min_trades: int | None = Query(None),
    max_drawdown_limit: float | None = Query(None),
    min_profit_factor: float | None = Query(None),
    min_win_rate: float | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    рџљЂ SSE Streaming Grid Search Optimization.

    Uses Server-Sent Events to send progress updates and keep connection alive.
    Ideal for large parameter spaces (>1M combinations) that take >2 minutes.

    Events:
    - progress: {percent, tested, total, speed, eta_seconds}
    - heartbeat: {timestamp} (every 10 sec to keep connection alive)
    - complete: {result JSON}
    - error: {message}
    """
    import asyncio
    import json
    import time
    from concurrent.futures import ThreadPoolExecutor

    from fastapi.responses import StreamingResponse

    # Parse comma-separated ranges
    def parse_int_list(s: str) -> list[int]:
        return [int(x.strip()) for x in s.split(",") if x.strip()]

    def parse_float_list(s: str) -> list[float]:
        return [float(x.strip()) for x in s.split(",") if x.strip()]

    period_range = parse_int_list(rsi_period_range)
    overbought_range = parse_int_list(rsi_overbought_range)
    oversold_range = parse_int_list(rsi_oversold_range)
    sl_range = parse_float_list(stop_loss_range)
    tp_range = parse_float_list(take_profit_range)

    total_combinations = len(period_range) * len(overbought_range) * len(oversold_range) * len(sl_range) * len(tp_range)

    logger.info(f"рџљЂ SSE Grid Search: {total_combinations:,} combinations")

    # Build request object
    request = VectorbtOptimizationRequest(
        symbol=symbol,
        interval=interval,
        start_date=start_date,
        end_date=end_date,
        direction=direction,
        leverage=leverage,
        initial_capital=initial_capital,
        commission=commission,
        position_size=position_size,
        rsi_period_range=period_range,
        rsi_overbought_range=overbought_range,
        rsi_oversold_range=oversold_range,
        stop_loss_range=sl_range,
        take_profit_range=tp_range,
        optimize_metric=optimize_metric,
        weight_return=weight_return,
        weight_drawdown=weight_drawdown,
        weight_sharpe=weight_sharpe,
        weight_win_rate=weight_win_rate,
        min_trades=min_trades,
        max_drawdown_limit=max_drawdown_limit,
        min_profit_factor=min_profit_factor,
        min_win_rate=min_win_rate,
    )

    # Result container for thread
    result_container: dict[str, Any] = {"result": None, "error": None, "done": False}

    def run_optimization():
        """Run optimization in thread"""
        try:
            import os
            from datetime import datetime as dt

            from backend.backtesting.fast_optimizer import load_candles_fast

            # Use Universal optimizer with auto backend selection
            from backend.backtesting.optimizer import UniversalOptimizer

            optimizer = UniversalOptimizer(backend="auto")

            # Get DB path with dynamic fallback
            from pathlib import Path

            default_db = str(Path(__file__).resolve().parents[3] / "data.sqlite3")
            db_path = os.environ.get("DATABASE_PATH", default_db)

            # Normalize interval
            interval_map = {
                "1m": "1",
                "3m": "3",
                "5m": "5",
                "15m": "15",
                "30m": "30",
                "1h": "60",
                "2h": "120",
                "4h": "240",
                "1d": "D",
                "1w": "W",
            }
            db_interval = interval_map.get(request.interval.lower(), request.interval)

            # Parse dates
            start_dt = dt.fromisoformat(request.start_date)
            end_dt = dt.fromisoformat(request.end_date)

            # Load candles
            candle_data = load_candles_fast(
                db_path=db_path,
                symbol=request.symbol,
                interval=db_interval,
                start_date=start_dt,
                end_date=end_dt,
                use_cache=True,
            )

            if candle_data is None or len(candle_data) < 50:
                result_container["error"] = (
                    f"Not enough data: {len(candle_data) if candle_data is not None else 0} candles"
                )
                result_container["done"] = True
                return

            # Convert numpy array to DataFrame
            import pandas as pd

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

            # Run optimization
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
                optimize_metric=request.optimize_metric,
                direction=request.direction,
            )

            # Convert result to dict for JSON serialization
            speed_per_sec = (
                int(result.tested_combinations / result.execution_time_seconds)
                if result.execution_time_seconds > 0
                else 0
            )

            logger.info("[SSE] Optimization completed, preparing result dict...")

            # Get trades and equity from best result (first in top_results)
            best_result = result.top_results[0] if result.top_results else {}
            trades = best_result.get("trades", [])
            equity_curve = best_result.get("equity_curve", [])

            # ============================================
            # ENRICH with full backtest if trades are missing
            # GPU optimizer only returns metrics, not actual trades
            # ============================================
            if not trades and best_result:
                try:
                    from backend.backtesting.engine import BacktestEngine
                    from backend.backtesting.models import BacktestConfig, StrategyType

                    best_params = best_result.get("params", {})
                    logger.info(f"[SSE] Running full backtest for enrichment: {best_params}")

                    backtest_config = BacktestConfig(
                        symbol=request.symbol,
                        interval=request.interval,
                        start_date=dt.fromisoformat(request.start_date),
                        end_date=dt.fromisoformat(request.end_date),
                        strategy_type=StrategyType.RSI,
                        strategy_params={
                            "rsi_period": best_params.get("rsi_period", 14),
                            "rsi_overbought": best_params.get("rsi_overbought", 70),
                            "rsi_oversold": best_params.get("rsi_oversold", 30),
                        },
                        initial_capital=request.initial_capital,
                        leverage=request.leverage,
                        direction=request.direction,
                        stop_loss=best_params.get("stop_loss_pct", best_params.get("stop_loss", 0)) / 100
                        if best_params.get("stop_loss_pct", best_params.get("stop_loss"))
                        else None,
                        take_profit=best_params.get("take_profit_pct", best_params.get("take_profit", 0)) / 100
                        if best_params.get("take_profit_pct", best_params.get("take_profit"))
                        else None,
                        taker_fee=request.commission,
                        maker_fee=request.commission,
                        position_size=1.0,
                    )

                    engine = BacktestEngine()
                    full_result = engine.run(backtest_config, candles, silent=True)

                    if full_result and full_result.trades:
                        trades = [t.model_dump() for t in full_result.trades]
                        logger.info(f"[SSE] Got {len(trades)} trades from full backtest")

                        # Update best_result with full metrics
                        if full_result.metrics:
                            m = full_result.metrics
                            best_result["avg_win"] = getattr(m, "avg_win", 0)
                            best_result["avg_loss"] = getattr(m, "avg_loss", 0)
                            best_result["avg_trade"] = getattr(m, "avg_trade", 0)
                            best_result["avg_win_value"] = getattr(m, "avg_win_value", 0)
                            best_result["avg_loss_value"] = getattr(m, "avg_loss_value", 0)
                            best_result["largest_win"] = getattr(m, "largest_win", 0)
                            best_result["largest_loss"] = getattr(m, "largest_loss", 0)
                            best_result["largest_win_value"] = getattr(m, "largest_win_value", 0)
                            best_result["largest_loss_value"] = getattr(m, "largest_loss_value", 0)
                            best_result["gross_profit"] = getattr(m, "gross_profit", 0)
                            best_result["gross_loss"] = getattr(m, "gross_loss", 0)
                            best_result["net_profit"] = getattr(m, "net_profit", 0)
                            best_result["long_trades"] = getattr(m, "long_trades", 0)
                            best_result["short_trades"] = getattr(m, "short_trades", 0)
                            best_result["long_winning_trades"] = getattr(m, "long_winning_trades", 0)
                            best_result["short_winning_trades"] = getattr(m, "short_winning_trades", 0)
                            best_result["long_win_rate"] = getattr(m, "long_win_rate", 0)
                            best_result["short_win_rate"] = getattr(m, "short_win_rate", 0)
                            best_result["long_gross_profit"] = getattr(m, "long_gross_profit", 0)
                            best_result["long_gross_loss"] = getattr(m, "long_gross_loss", 0)
                            best_result["short_gross_profit"] = getattr(m, "short_gross_profit", 0)
                            best_result["short_gross_loss"] = getattr(m, "short_gross_loss", 0)
                            best_result["long_net_profit"] = getattr(m, "long_net_profit", 0)
                            best_result["short_net_profit"] = getattr(m, "short_net_profit", 0)
                            best_result["max_consecutive_wins"] = getattr(m, "max_consecutive_wins", 0)
                            best_result["max_consecutive_losses"] = getattr(m, "max_consecutive_losses", 0)
                            best_result["expectancy"] = getattr(m, "expectancy", 0)
                            best_result["total_commission"] = getattr(m, "total_commission", 0)
                            best_result["trades"] = trades
                            logger.info(f"[SSE] Enriched with full metrics: avg_win={best_result['avg_win']:.2f}%")

                    if full_result and full_result.equity_curve:
                        ec = full_result.equity_curve
                        if hasattr(ec, "timestamps") and hasattr(ec, "equity"):
                            drawdowns = ec.drawdown if hasattr(ec, "drawdown") and ec.drawdown else [0] * len(ec.equity)
                            equity_curve = [
                                {
                                    "timestamp": t.isoformat() if hasattr(t, "isoformat") else str(t),
                                    "equity": v,
                                    "drawdown": d,
                                }
                                for t, v, d in zip(ec.timestamps, ec.equity, drawdowns, strict=False)
                            ]
                            logger.info(f"[SSE] Got {len(equity_curve)} equity curve points")

                except Exception as enrich_err:
                    logger.warning(f"[SSE] Failed to enrich with full backtest: {enrich_err}")

            result_dict = {
                "best_params": result.best_params,
                "best_metrics": result.best_metrics,
                "top_results": result.top_results[:50] if result.top_results else [],
                "tested_combinations": result.tested_combinations,
                "execution_time": result.execution_time_seconds,
                "speed_per_sec": speed_per_sec,
                "trades": trades,
                "equity_curve": equity_curve,
            }

            logger.info(f"[SSE] Result dict ready, trades={len(trades)}, equity={len(equity_curve)}")

            result_container["result"] = result_dict
            result_container["done"] = True

            logger.info("[SSE] Container updated successfully")

        except Exception as e:
            logger.exception(f"SSE optimization error: {e}")
            result_container["error"] = str(e)
            result_container["done"] = True

    async def event_generator():
        """Generate SSE events"""
        # Start optimization in thread
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(run_optimization)  # Fire and forget - results via container

        start_time = time.time()
        last_heartbeat = time.time()
        heartbeat_interval = 3  # Send heartbeat every 3 seconds (was 10, too slow!)

        try:
            # Send initial event
            yield f"data: {json.dumps({'event': 'start', 'total': total_combinations})}\n\n"

            while not result_container["done"]:
                await asyncio.sleep(0.3)  # Check more frequently

                current_time = time.time()
                elapsed = current_time - start_time

                # Send heartbeat to keep connection alive (every 3 sec)
                if current_time - last_heartbeat >= heartbeat_interval:
                    # Estimate progress based on expected speed (~25k combos/sec)
                    estimated_speed = 25000
                    estimated_done = min(int(elapsed * estimated_speed), total_combinations)
                    percent = min(99, int(estimated_done * 100 / total_combinations)) if total_combinations > 0 else 0
                    eta = max(0, (total_combinations - estimated_done) / estimated_speed) if estimated_speed > 0 else 0

                    yield f"data: {json.dumps({'event': 'heartbeat', 'elapsed': round(elapsed, 1), 'percent': percent, 'eta_seconds': round(eta, 0)})}\n\n"
                    last_heartbeat = current_time

            # Check for error
            if result_container["error"]:
                logger.error(f"[SSE] Optimization error: {result_container['error']}")
                yield f"data: {json.dumps({'event': 'error', 'message': result_container['error']})}\n\n"
                return

            # Send result
            logger.info("[SSE] Preparing to send result to client...")
            result = result_container["result"]
            if result:
                # Build response - result is a dict, access via []
                top_results = result.get("top_results", [])
                smart_recs = _generate_smart_recommendations(top_results)

                def _to_rec(r):
                    if not r:
                        return None
                    return {
                        "params": r.get("params"),
                        "total_return": r.get("total_return"),
                        "max_drawdown": r.get("max_drawdown"),
                        "sharpe_ratio": r.get("sharpe_ratio"),
                        "win_rate": r.get("win_rate"),
                        "total_trades": r.get("total_trades"),
                    }

                tested = result.get("tested_combinations", 0)
                exec_time = result.get("execution_time", 0)
                speed = int(tested / exec_time) if exec_time > 0 else 0

                response_data = {
                    "event": "complete",
                    "status": "completed",
                    "total_combinations": tested,
                    "tested_combinations": tested,
                    "execution_time_seconds": round(exec_time, 2),
                    "speed_combinations_per_sec": speed,
                    "num_workers": os.cpu_count() or 4,
                    "best_params": result.get("best_params"),
                    "best_score": result.get("best_metrics", {}).get("sharpe_ratio", 0),
                    "best_metrics": result.get("best_metrics"),
                    "top_results": top_results[:10],
                    "trades": result.get("trades", []),
                    "equity_curve": result.get("equity_curve", []),
                    "performance_stats": {},
                    "smart_recommendations": {
                        "best_balanced": _to_rec(smart_recs.get("best_balanced")),
                        "best_conservative": _to_rec(smart_recs.get("best_conservative")),
                        "best_aggressive": _to_rec(smart_recs.get("best_aggressive")),
                        "recommendation_text": smart_recs.get("recommendation_text", ""),
                    },
                }

                logger.info(
                    f"[SSE] Sending complete event, JSON size: {len(json.dumps(response_data, default=str))} bytes"
                )
                yield f"data: {json.dumps(response_data, default=str)}\n\n"
                logger.info("[SSE] Complete event sent successfully")

        except Exception as e:
            logger.exception(f"SSE generator error: {e}")
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
        finally:
            executor.shutdown(wait=False)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# TWO-STAGE OPTIMIZATION (VBT Screening + Fallback Validation)
# =============================================================================


class TwoStageOptimizationRequest(BaseModel):
    """Request for two-stage optimization."""

    # Data
    symbol: str = Field("BTCUSDT", description="Trading symbol")
    interval: str = Field("60", description="Timeframe (1, 5, 15, 30, 60, 240, D)")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")

    # Strategy parameters
    rsi_period_range: list[int] = Field([7, 14, 21], description="RSI periods")
    rsi_overbought_range: list[int] = Field([65, 70, 75, 80], description="Overbought levels")
    rsi_oversold_range: list[int] = Field([20, 25, 30, 35], description="Oversold levels")
    stop_loss_range: list[float] = Field([0.02, 0.03, 0.05], description="Stop loss %")
    take_profit_range: list[float] = Field([0.02, 0.04, 0.06], description="Take profit %")

    # Trading settings
    direction: str = Field("both", description="long/short/both")
    leverage: int = Field(10, ge=1, le=125)
    initial_capital: float = Field(10000.0)
    commission: float = Field(0.0007, description="0.07% TradingView parity")
    slippage: float = Field(0.0005)

    # Two-stage settings
    top_n: int = Field(50, ge=10, le=200, description="Candidates to validate in Stage 2")
    use_bar_magnifier: bool = Field(True, description="Use tick-level precision (Bar Magnifier)")
    parallel_workers: int = Field(4, ge=1, le=8, description="Parallel validation workers")
    drift_threshold: float = Field(0.25, description="Max acceptable metric drift")

    # TradingView-like simulation settings
    fill_mode: str = Field(
        "next_bar_open",
        description="Order execution mode: 'bar_close' or 'next_bar_open'",
    )
    max_drawdown_trading: float = Field(
        0.0,
        ge=0,
        le=1.0,
        description="Max drawdown limit to stop trading (0 = disabled)",
    )


class TwoStageValidationResult(BaseModel):
    """Single validated result from Stage 2."""

    rank_stage1: int
    params: dict[str, Any]

    # VBT metrics
    vbt_sharpe: float
    vbt_total_return: float

    # Validated metrics
    validated_sharpe: float
    validated_total_return: float
    validated_max_drawdown: float
    validated_win_rate: float
    validated_total_trades: int

    # Analysis
    sharpe_drift: float
    is_reliable: bool
    confidence_score: float


class TwoStageOptimizationResponse(BaseModel):
    """Response for two-stage optimization."""

    status: str

    # Stage 1
    stage1_total_combinations: int
    stage1_tested: int
    stage1_execution_time: float
    stage1_backend: str

    # Stage 2
    stage2_candidates: int
    stage2_validated: int
    stage2_execution_time: float
    use_bar_magnifier: bool

    # Best result
    best_params: dict[str, Any]
    best_validated_sharpe: float
    best_validated_return: float
    best_confidence: float

    # All validated
    validated_results: list[TwoStageValidationResult]

    # Drift stats
    avg_sharpe_drift: float
    max_sharpe_drift: float
    reliable_count: int

    # Performance
    total_execution_time: float
    speedup_factor: float


@router.post(
    "/two-stage/optimize",
    response_model=TwoStageOptimizationResponse,
    summary="рџљЂ Two-Stage Optimization",
    description="""
    Two-Stage Optimization combines VBT speed with Fallback precision.

    **Stage 1 (Screening):** Fast VBT/GPU grid search over all combinations
    **Stage 2 (Validation):** Precise Fallback validation of top-N candidates

    Benefits:
    - 100x-600x faster than full Fallback optimization
    - Validates top candidates with tick-level precision
    - Detects "false champions" (VBT overestimates)
    - Calculates confidence scores for results
    """,
)
async def two_stage_optimization(
    request: TwoStageOptimizationRequest,
    db: Session = Depends(get_db),
):
    """
    Run two-stage optimization: VBT screening в†’ Fallback validation.
    """
    import os
    import time
    from datetime import datetime as dt

    from backend.backtesting.fast_optimizer import load_candles_fast
    from backend.backtesting.two_stage_optimizer import TwoStageOptimizer

    logger.info("=" * 60)
    logger.info("рџљЂ TWO-STAGE OPTIMIZATION API")
    logger.info("=" * 60)

    total_combinations = (
        len(request.rsi_period_range)
        * len(request.rsi_overbought_range)
        * len(request.rsi_oversold_range)
        * len(request.stop_loss_range)
        * len(request.take_profit_range)
    )

    logger.info(f"   Total combinations: {total_combinations:,}")
    logger.info(f"   Top-N for validation: {request.top_n}")
    logger.info(f"   Bar Magnifier: {request.use_bar_magnifier}")

    try:
        # Parse dates
        start_dt = dt.fromisoformat(request.start_date)
        end_dt = dt.fromisoformat(request.end_date)
    except Exception as parse_err:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {parse_err}")

    # Normalize interval
    interval = _normalize_interval(request.interval)

    # Load data - try DB first, then SmartKlineService
    from pathlib import Path

    default_db = str(Path(__file__).resolve().parents[3] / "data.sqlite3")
    db_path = os.environ.get("DATABASE_PATH", default_db)
    candle_data = None

    try:
        load_start = time.perf_counter()
        candle_data = load_candles_fast(
            db_path=db_path,
            symbol=request.symbol,
            interval=interval,
            start_date=start_dt,
            end_date=end_dt,
            use_cache=True,
        )
        load_time = time.perf_counter() - load_start
        if candle_data is not None and len(candle_data) > 0:
            logger.info(f"рџ“Љ Data loaded from DB in {load_time:.3f}s ({len(candle_data)} candles)")

    except Exception as e:
        logger.warning(f"DB load failed: {e}, trying SmartKlineService...")

    # Fallback to SmartKlineService if DB has no data
    if candle_data is None or len(candle_data) == 0:
        try:
            import numpy as np

            from backend.services.smart_kline_service import SMART_KLINE_SERVICE

            logger.info("рџ“Љ Loading data via SmartKlineService...")
            raw_candles = SMART_KLINE_SERVICE.get_candles(request.symbol, interval, limit=5000)

            if raw_candles:
                # Convert list of dicts to numpy array
                candle_data = np.array(
                    [
                        [
                            c["open_time"],
                            c["open"],
                            c["high"],
                            c["low"],
                            c["close"],
                            c["volume"],
                        ]
                        for c in raw_candles
                    ],
                    dtype=np.float64,
                )
                logger.info(f"рџ“Љ Loaded {len(candle_data)} candles via SmartKlineService")
        except Exception as e:
            logger.error(f"SmartKlineService failed: {e}")

    if candle_data is None or len(candle_data) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No data for {request.symbol}/{interval}. Load data first.",
        )

    # Convert to DataFrame
    candles = pd.DataFrame(
        {
            "open_time": candle_data[:, 0],  # Keep as ms for TwoStageOptimizer
            "open": candle_data[:, 1],
            "high": candle_data[:, 2],
            "low": candle_data[:, 3],
            "close": candle_data[:, 4],
            "volume": candle_data[:, 5],
        }
    )

    logger.info(f"рџ“Љ Loaded {len(candles)} candles")

    # Initialize optimizer
    optimizer = TwoStageOptimizer(
        top_n=request.top_n,
        use_bar_magnifier=request.use_bar_magnifier,
        parallel_workers=request.parallel_workers,
        drift_threshold=request.drift_threshold,
    )

    try:
        # Run two-stage optimization
        result = optimizer.optimize(
            candles=candles,
            symbol=request.symbol,
            interval=interval,
            rsi_period_range=request.rsi_period_range,
            rsi_overbought_range=request.rsi_overbought_range,
            rsi_oversold_range=request.rsi_oversold_range,
            stop_loss_range=request.stop_loss_range,
            take_profit_range=request.take_profit_range,
            initial_capital=request.initial_capital,
            leverage=request.leverage,
            commission=request.commission,
            slippage=request.slippage,
            direction=request.direction,
            # TradingView-like simulation settings
            fill_mode=request.fill_mode,
            max_drawdown=request.max_drawdown_trading,
        )

    except Exception as e:
        logger.exception("Two-stage optimization failed")
        raise HTTPException(status_code=500, detail=f"Optimization failed: {e}")

    # Convert validated results to response format
    validated_results = []
    for r in result.validated_results[:100]:  # Limit to top 100
        validated_results.append(
            TwoStageValidationResult(
                rank_stage1=r.rank_stage1,
                params=r.params,
                vbt_sharpe=r.vbt_sharpe,
                vbt_total_return=r.vbt_total_return,
                validated_sharpe=r.validated_sharpe,
                validated_total_return=r.validated_total_return,
                validated_max_drawdown=r.validated_max_drawdown,
                validated_win_rate=r.validated_win_rate,
                validated_total_trades=r.validated_total_trades,
                sharpe_drift=r.sharpe_drift,
                is_reliable=r.is_reliable,
                confidence_score=r.confidence_score,
            )
        )

    logger.info(f"вњ… Two-stage optimization completed in {result.total_execution_time:.1f}s")
    logger.info(f"рџљЂ Speedup: {result.speedup_factor:.0f}x")

    return TwoStageOptimizationResponse(
        status=result.status,
        stage1_total_combinations=result.stage1_total_combinations,
        stage1_tested=result.stage1_tested,
        stage1_execution_time=result.stage1_execution_time,
        stage1_backend=result.stage1_backend,
        stage2_candidates=result.stage2_candidates,
        stage2_validated=result.stage2_validated,
        stage2_execution_time=result.stage2_execution_time,
        use_bar_magnifier=result.use_bar_magnifier,
        best_params=result.best_params,
        best_validated_sharpe=result.best_validated_sharpe,
        best_validated_return=result.best_validated_return,
        best_confidence=result.best_confidence,
        validated_results=validated_results,
        avg_sharpe_drift=result.avg_sharpe_drift,
        max_sharpe_drift=result.max_sharpe_drift,
        reliable_count=result.reliable_count,
        total_execution_time=result.total_execution_time,
        speedup_factor=result.speedup_factor,
    )
