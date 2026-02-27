"""
Optimization Router — Sync Grid Search and Optuna Search endpoints.

Covers:
- POST /sync/grid-search
- POST /sync/optuna-search
"""

# mypy: disable-error-code="arg-type, assignment, var-annotated, return-value, union-attr, operator, attr-defined, misc, dict-item"

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.routers.optimizations.helpers import _normalize_interval
from backend.api.routers.optimizations.workers import (
    _apply_custom_sort_order,
    _calculate_composite_score,
    _compute_weighted_composite,
    _generate_smart_recommendations,
    _passes_filters,
    _rank_by_multi_criteria,
    _run_batch_backtests,
)
from backend.database import get_db
from backend.optimization.models import (
    OptunaSyncRequest,
    SmartRecommendation,
    SmartRecommendations,
    SyncOptimizationRequest,
    SyncOptimizationResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/sync/grid-search", response_model=SyncOptimizationResponse)
async def sync_grid_search_optimization(
    request: SyncOptimizationRequest,
    db: Session = Depends(get_db),
):
    """
    РЎРёРЅС…СЂРѕРЅРЅР°СЏ Grid Search РѕРїС‚РёРјРёР·Р°С†РёСЏ (Р±РµР· Celery).

    РўРµСЃС‚РёСЂСѓРµС‚ РІСЃРµ РєРѕРјР±РёРЅР°С†РёРё РїР°СЂР°РјРµС‚СЂРѕРІ RSI Рё РІРѕР·РІСЂР°С‰Р°РµС‚ Р»СѓС‡С€РёРµ СЂРµР·СѓР»СЊС‚Р°С‚С‹.
    РџРѕРґС…РѕРґРёС‚ РґР»СЏ РЅРµР±РѕР»СЊС€РѕРіРѕ РїСЂРѕСЃС‚СЂР°РЅСЃС‚РІР° РїР°СЂР°РјРµС‚СЂРѕРІ (РґРѕ 100-200 РєРѕРјР±РёРЅР°С†РёР№).
    """
    import time
    from datetime import datetime as dt

    import pandas as pd

    from backend.services.data_service import DataService

    start_time = time.time()

    logger.info("рџ”Ќ Starting sync grid search optimization")
    logger.info(f"   Symbol: {request.symbol}, Interval: {request.interval}")
    logger.info(f"   Period range: {request.rsi_period_range}")
    logger.info(f"   Overbought range: {request.rsi_overbought_range}")
    logger.info(f"   Oversold range: {request.rsi_oversold_range}")

    # Map max_trials from frontend to max_iterations for Random Search
    if request.max_trials and request.max_trials > 0 and request.max_iterations == 0:
        request.max_iterations = request.max_trials
        logger.info(f"   Mapped max_trials={request.max_trials} в†’ max_iterations={request.max_iterations}")

    # Log optimization config fields
    logger.info(f"   Workers: {request.workers}, Timeout: {request.timeout_seconds}s")
    logger.info(f"   Train split: {request.train_split}, Search method: {request.search_method}")
    logger.info(f"   Early stopping: {request.early_stopping} (patience={request.early_stopping_patience})")
    logger.info(f"   Random seed: {request.random_seed}")

    # Normalize interval format for database queries (4h -> 240, 1h -> 60, etc.)
    db_interval = _normalize_interval(request.interval)
    logger.info(f"   Normalized interval: {request.interval} -> {db_interval}")

    try:
        # РџСЂРµРѕР±СЂР°Р·РѕРІР°С‚СЊ СЃС‚СЂРѕРєРё РґР°С‚ РІ datetime
        start_dt = dt.fromisoformat(request.start_date)
        end_dt = dt.fromisoformat(request.end_date)
    except Exception as parse_err:
        logger.error(f"Date parsing error: {parse_err}")
        raise HTTPException(status_code=400, detail=f"Invalid date format: {parse_err}")

    try:
        # Load data with market_type consideration (SPOT for TV parity, LINEAR for futures)
        market_type = getattr(request, "market_type", "linear")
        logger.info(f"   Market type: {market_type}")

        data_service = DataService(db)
        candle_records = data_service.get_market_data(
            symbol=request.symbol,
            timeframe=db_interval,  # Use normalized interval
            start_time=start_dt,
            end_time=end_dt,
            market_type=market_type,  # SPOT or LINEAR data filter
        )
    except Exception as data_err:
        logger.error(f"Data loading error: {data_err}")
        raise HTTPException(status_code=500, detail=f"Data loading failed: {data_err}")

    if not candle_records:
        raise HTTPException(
            status_code=400,
            detail=f"No data for {request.symbol} {request.interval} ({market_type}) from {request.start_date} to {request.end_date}",
        )

    # РљРѕРЅРІРµСЂС‚РёСЂСѓРµРј РІ DataFrame РґР»СЏ РґРІРёР¶РєР° Р±СЌРєС‚РµСЃС‚Р°
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
    # РЈСЃС‚Р°РЅР°РІР»РёРІР°РµРј timestamp РєР°Рє РёРЅРґРµРєСЃ
    candles.set_index("timestamp", inplace=True)

    logger.info(f"рџ“Љ Loaded {len(candles)} candles")

    # Generate parameter combinations using universal generator
    from backend.optimization.utils import combo_to_params, generate_param_combinations

    search_method = getattr(request, "search_method", "grid").lower()
    max_iter = getattr(request, "max_iterations", 0)
    random_seed = getattr(request, "random_seed", None)

    param_combinations, total_combinations, param_names = generate_param_combinations(
        request,
        search_method=search_method,
        max_iterations=max_iter,
        random_seed=random_seed,
    )

    # No limit - user is informed about time estimate in UI
    strategy_type_str = getattr(request, "strategy_type", "rsi").lower().strip()

    # Р—Р°РїСѓСЃРє Р±СЌРєС‚РµСЃС‚РѕРІ
    from backend.backtesting.models import StrategyType

    results: list[dict[str, Any]] = []

    best_score = float("-inf")
    best_params: dict[str, Any] | None = None
    best_result: dict[str, Any] | None = None

    # Market Regime: Numba РЅРµ РїРѕРґРґРµСЂР¶РёРІР°РµС‚ regime в†’ РїСЂРё РІРєР»СЋС‡РµРЅРёРё РёСЃРїРѕР»СЊР·СѓРµРј FallbackV4
    effective_engine = request.engine_type
    if getattr(request, "market_regime_enabled", False):
        effective_engine = "fallback_v4"
        logger.info("рџ“Љ Market regime enabled в†’ using FallbackV4 for regime filter support")

    # РџРѕРґРіРѕС‚РѕРІРёС‚СЊ РїР°СЂР°РјРµС‚СЂС‹ Р·Р°РїСЂРѕСЃР° РґР»СЏ РїРµСЂРµРґР°С‡Рё РІ worker
    request_params = {
        "symbol": request.symbol,
        "interval": db_interval,  # Use normalized interval for BacktestConfig
        "initial_capital": request.initial_capital,
        "leverage": request.leverage,
        "direction": request.direction,
        "commission": request.commission,
        "strategy_type": request.strategy_type,
        "optimize_metric": request.optimize_metric,
        "use_fixed_amount": request.use_fixed_amount,
        "fixed_amount": request.fixed_amount,
        # РќРѕРІР°СЏ СЃРёСЃС‚РµРјР°: РјР°СЃСЃРёРІ РєСЂРёС‚РµСЂРёРµРІ РѕС‚Р±РѕСЂР°
        "selection_criteria": request.selection_criteria,
        # Р’С‹Р±СЂР°РЅРЅС‹Р№ РґРІРёР¶РѕРє (fallback РїСЂРё regime)
        "engine_type": effective_engine,
        # Market Regime Filter (P1)
        "market_regime_enabled": getattr(request, "market_regime_enabled", False),
        "market_regime_filter": getattr(request, "market_regime_filter", "not_volatile"),
        "market_regime_lookback": getattr(request, "market_regime_lookback", 50),
        # EvaluationCriteriaPanel: constraints, sort_order, composite score
        "constraints": getattr(request, "constraints", None),
        "sort_order": getattr(request, "sort_order", None),
        "use_composite": getattr(request, "use_composite", False),
        "weights": getattr(request, "weights", None),
    }

    # РџСЂРµРѕР±СЂР°Р·СѓРµРј strategy_type РІ StrategyType enum (СЃРѕС…СЂР°РЅСЏРµРј РІ request_params)
    if request.strategy_type.lower() == "rsi":
        request_params["strategy_type_enum"] = StrategyType.RSI
    else:
        request_params["strategy_type_enum"] = StrategyType.SMA_CROSSOVER

    # Smart execution strategy based on engine type:
    # - GPU Batch: ultra-fast batch optimization (GPU accelerated)
    # - GPU/Numba: single-process (avoid CUDA context issues, JIT warmup)
    # - Fallback: multiprocessing (CPU parallelism)
    import os
    from concurrent.futures import ProcessPoolExecutor, as_completed

    engine_type = effective_engine.lower()
    completed = 0  # Initialize counter

    logger.info(f"рџ”§ Engine type requested: {engine_type}")

    # GPU Batch Optimization - ultra fast screening + full verification
    if engine_type == "gpu" and total_combinations >= 50 and request.strategy_type.lower() == "rsi":
        logger.info(f"рџљЂ Using GPU Batch Optimizer (hybrid mode) for {total_combinations} combinations")

        try:
            from backend.backtesting.engine_selector import get_engine
            from backend.backtesting.gpu_batch_optimizer import GPUBatchOptimizer
            from backend.backtesting.signal_generators import generate_signals_for_strategy
            from backend.optimization.utils import (
                build_backtest_input,
                extract_metrics_from_output,
                parse_trade_direction,
            )

            # Phase 1: Fast GPU Batch screening
            batch_optimizer = GPUBatchOptimizer()
            batch_results = batch_optimizer.optimize_rsi_batch(
                candles=candles,
                param_combinations=param_combinations,
                initial_capital=request.initial_capital,
                leverage=request.leverage,
                commission=request.commission,
                direction=request.direction,
            )

            # Sort by score and take top 20 for verification
            batch_with_scores = []
            for res in batch_results:
                result_entry = {
                    "total_return": res.total_return,
                    "sharpe_ratio": res.sharpe_ratio,
                    "max_drawdown": res.max_drawdown,
                    "win_rate": res.win_rate,
                    "total_trades": res.total_trades,
                    "profit_factor": res.profit_factor,
                    "net_profit": res.net_profit,
                    "params": res.params,
                }
                score = _calculate_composite_score(
                    result_entry,
                    request_params.get("optimize_metric", "sharpe_ratio"),
                    request_params.get("weights"),
                )
                result_entry["score"] = score
                batch_with_scores.append(result_entry)

            # Sort by score descending
            batch_with_scores.sort(key=lambda x: x["score"], reverse=True)

            # Phase 2: Full verification of top candidates
            top_n = min(100, len(batch_with_scores))  # Verify top 100 for better accuracy
            logger.info(f"рџ”Ќ Phase 2: Verifying top {top_n} candidates with full engine")

            # Get full engine for verification
            engine = get_engine(engine_type="numba")  # Use Numba for verification (faster than fallback)

            # Convert direction
            direction_str = request_params.get("direction", "both")
            trade_direction = parse_trade_direction(direction_str)

            for candidate in batch_with_scores[:top_n]:
                params: dict[str, Any] = candidate["params"]
                stop_loss = params.get("stop_loss_pct", 0)
                take_profit = params.get("take_profit_pct", 0)
                # Strategy params (without SL/TP)
                signal_params = {k: v for k, v in params.items() if k not in ("stop_loss_pct", "take_profit_pct")}

                try:
                    # Generate signals with universal dispatcher
                    long_entries, long_exits, short_entries, short_exits = generate_signals_for_strategy(
                        candles=candles,
                        strategy_type=strategy_type_str,
                        params=signal_params,
                        direction=direction_str,
                    )

                    backtest_input = build_backtest_input(
                        candles=candles,
                        long_entries=long_entries,
                        long_exits=long_exits,
                        short_entries=short_entries,
                        short_exits=short_exits,
                        request_params=request_params,
                        trade_direction=trade_direction,
                        stop_loss_pct=stop_loss,
                        take_profit_pct=take_profit,
                    )

                    bt_output = engine.run(backtest_input)

                    if bt_output.is_valid and bt_output.metrics:
                        result_entry = extract_metrics_from_output(bt_output, win_rate_as_pct=True)
                        result_entry["params"] = params

                        # Apply constraints/filters from EvaluationCriteriaPanel
                        if not _passes_filters(result_entry, request_params):
                            continue

                        score = _calculate_composite_score(
                            result_entry,
                            request_params.get("optimize_metric", "sharpe_ratio"),
                            request_params.get("weights"),
                        )
                        result_entry["score"] = score

                        results.append(result_entry)
                        completed += 1

                        if score > best_score:
                            best_score = score
                            best_params = result_entry["params"]
                            best_result = result_entry

                except Exception as verify_err:
                    logger.warning(f"Verification failed for {params}: {verify_err}")

            logger.info(f"вњ… GPU Batch Hybrid completed: {total_combinations} screened, {completed} verified")

        except Exception as batch_err:
            logger.warning(f"GPU Batch failed: {batch_err}, falling back to single-process")
            # Fall through to single-process mode
            engine_type = "numba"  # Use Numba as fallback

    # Single-process mode for GPU/Numba/FallbackV4/Optimization OR small jobs
    # FallbackV4 required for market_regime (Numba doesn't support it)
    # "optimization" = Numba-based, works best in single-process (JIT warmup)
    if completed == 0 and (engine_type in ("gpu", "numba", "fallback_v4", "optimization") or total_combinations <= 10):
        logger.info(f"вљЎ Using single-process mode for {engine_type} ({total_combinations} combinations)")

        from backend.backtesting.engine_selector import get_engine
        from backend.backtesting.signal_generators import generate_signals_for_strategy
        from backend.optimization.utils import (
            EarlyStopper,
            TimeoutChecker,
            build_backtest_input,
            combo_to_params,
            extract_metrics_from_output,
            parse_trade_direction,
            split_candles,
        )

        # Get engine once (single warmup)
        engine = get_engine(engine_type=engine_type)
        logger.info(f"   Engine: {engine.__class__.__name__}")

        # Convert direction
        direction_str = request_params.get("direction", "both")
        trade_direction = parse_trade_direction(direction_str)

        # Train/Test split
        train_split = getattr(request, "train_split", 1.0)
        train_candles, test_candles = split_candles(candles, train_split)
        if test_candles is not None:
            logger.info(f"   Train/Test split: {len(train_candles)}/{len(test_candles)} candles ({train_split:.0%})")

        # Timeout checker
        timeout_checker = TimeoutChecker(getattr(request, "timeout_seconds", 3600))

        # Early stopping
        early_stopper = None
        if getattr(request, "early_stopping", False):
            early_stopper = EarlyStopper(patience=getattr(request, "early_stopping_patience", 20))
            logger.info(f"   Early stopping enabled: patience={early_stopper.patience}")

        # Process all combinations in single process
        for combo in param_combinations:
            # Check timeout
            if timeout_checker.is_expired():
                logger.warning(f"вЏ° Timeout reached after {timeout_checker.elapsed:.1f}s")
                break

            # Check early stopping
            if early_stopper and early_stopper.should_stop(best_score):
                logger.info(
                    f"рџ›‘ Early stopping at iteration {completed} (no improvement for {early_stopper.patience} steps)"
                )
                break

            try:
                # Convert combo to named params using universal helper
                named_params = combo_to_params(combo, param_names)
                stop_loss = named_params.pop("stop_loss_pct", 0)
                take_profit = named_params.pop("take_profit_pct", 0)

                # Generate signals using universal dispatcher
                long_entries, long_exits, short_entries, short_exits = generate_signals_for_strategy(
                    candles=train_candles,
                    strategy_type=strategy_type_str,
                    params=named_params,
                    direction=direction_str,
                )

                # Create BacktestInput using DRY builder
                backtest_input = build_backtest_input(
                    candles=train_candles,
                    long_entries=long_entries,
                    long_exits=long_exits,
                    short_entries=short_entries,
                    short_exits=short_exits,
                    request_params=request_params,
                    trade_direction=trade_direction,
                    stop_loss_pct=stop_loss,
                    take_profit_pct=take_profit,
                )

                # Run backtest
                bt_output = engine.run(backtest_input)

                if not bt_output.is_valid:
                    continue

                # Extract metrics using DRY helper
                result_entry = extract_metrics_from_output(bt_output, win_rate_as_pct=True)

                # Apply constraints/filters from EvaluationCriteriaPanel
                if not _passes_filters(result_entry, request_params):
                    continue

                # Calculate score
                score = _calculate_composite_score(
                    result_entry,
                    request_params.get("optimize_metric", "sharpe_ratio"),
                    request_params.get("weights"),
                )
                result_entry["score"] = score
                result_entry["params"] = {
                    **named_params,
                    "stop_loss_pct": stop_loss,
                    "take_profit_pct": take_profit,
                }

                # Memory optimization: only store trades for top results
                # Trades are stored temporarily, will be pruned later
                results.append(result_entry)
                completed += 1

                if score > best_score:
                    best_score = score
                    best_params = result_entry["params"]
                    best_result = result_entry

            except Exception as e:
                logger.warning(f"Combo failed: {combo} - {e}")

        # Memory optimization: keep trades only for top 10 results
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        for i, r in enumerate(results):
            if i >= 10 and "trades" in r:
                del r["trades"]

        logger.info(f"   Completed: {completed}/{total_combinations}")

    # Multiprocessing mode for Fallback (CPU parallelism)
    if completed == 0:
        # Use workers from request if provided, capped at cpu_count
        cpu_count = os.cpu_count() or 4
        requested_workers = getattr(request, "workers", None)
        if requested_workers and requested_workers > 0:
            max_workers = min(requested_workers, cpu_count)
        else:
            max_workers = min(cpu_count, 8)
        logger.info(f"рџ“ќ Using multiprocessing with {max_workers} processes for {engine_type}")

        # Prepare serializable data
        candles_dict = candles.reset_index().to_dict("records")
        start_dt_str = start_dt.isoformat()
        end_dt_str = end_dt.isoformat()
        strategy_type_str = request.strategy_type.lower()

        # Split into batches
        batch_size = max(1, len(param_combinations) // max_workers)
        batches = [param_combinations[i : i + batch_size] for i in range(0, len(param_combinations), batch_size)]
        logger.info(f"рџ“¦ Split into {len(batches)} batches of ~{batch_size} combinations each")

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _run_batch_backtests,
                    batch,
                    request_params,
                    candles_dict,
                    start_dt_str,
                    end_dt_str,
                    strategy_type_str,
                    param_names,
                ): batch
                for batch in batches
            }

            for future in as_completed(futures):
                try:
                    batch_results = future.result()
                    if batch_results:
                        for result_entry in batch_results:
                            if result_entry:
                                results.append(result_entry)
                                completed += 1

                                if float(result_entry["score"]) > best_score:
                                    best_score = float(result_entry["score"])
                                    best_params = result_entry["params"]
                                    best_result = result_entry

                        logger.info(
                            f"   Progress: {completed}/{total_combinations} ({completed / total_combinations * 100:.1f}%)"
                        )

                except Exception as e:
                    logger.warning(f"Batch failed: {e}")

    # РџСЂРёРјРµРЅСЏРµРј РјСѓР»СЊС‚РёРєСЂРёС‚РµСЂРёР°Р»СЊРЅРѕРµ СЂР°РЅР¶РёСЂРѕРІР°РЅРёРµ РµСЃР»Рё РµСЃС‚СЊ selection_criteria
    selection_criteria = getattr(request, "selection_criteria", None) or [request.optimize_metric]
    if len(selection_criteria) > 1:
        # РСЃРїРѕР»СЊР·СѓРµРј РјСѓР»СЊС‚РёРєСЂРёС‚РµСЂРёР°Р»СЊРЅРѕРµ СЂР°РЅР¶РёСЂРѕРІР°РЅРёРµ
        results = _rank_by_multi_criteria(results, selection_criteria)
        logger.info(f"   Applied multi-criteria ranking: {selection_criteria}")
    else:
        # РЎС‚Р°РЅРґР°СЂС‚РЅР°СЏ СЃРѕСЂС‚РёСЂРѕРІРєР° РїРѕ РѕРґРЅРѕРјСѓ РєСЂРёС‚РµСЂРёСЋ
        results.sort(key=lambda x: x["score"], reverse=True)

    # Apply custom sort_order from frontend if provided
    custom_sort_order = getattr(request, "sort_order", None)
    if custom_sort_order and len(custom_sort_order) > 0:
        results = _apply_custom_sort_order(results, custom_sort_order)
        logger.info(f"   Applied custom sort order: {custom_sort_order}")

    # Calculate composite_score for each result if use_composite=True
    use_composite = getattr(request, "use_composite", False)
    composite_weights = getattr(request, "weights", None)
    if use_composite and composite_weights and results:
        for result in results:
            composite_score = _compute_weighted_composite(result, composite_weights)
            result["composite_score"] = composite_score
        logger.info(f"   Calculated composite scores with weights: {composite_weights}")

    # РћР±РЅРѕРІР»СЏРµРј Р»СѓС‡С€РёР№ СЂРµР·СѓР»СЊС‚Р°С‚ РїРѕСЃР»Рµ СЂР°РЅР¶РёСЂРѕРІР°РЅРёСЏ
    if results:
        best_result = results[0]
        best_score = best_result["score"]
        best_params = best_result["params"]

    execution_time = time.time() - start_time

    # Hybrid pipeline: optional FallbackV4 validation for gold-standard metrics
    validated_metrics = None
    if getattr(request, "validate_best_with_fallback", False) and best_params and engine_type in ("numba", "gpu"):
        try:
            from backend.backtesting.engine_selector import get_engine
            from backend.backtesting.signal_generators import generate_signals_for_strategy
            from backend.optimization.utils import (
                build_backtest_input,
                extract_metrics_from_output,
                parse_trade_direction,
            )

            fallback_engine = get_engine(engine_type="fallback_v4")
            direction_str = request_params.get("direction", "both")
            trade_direction = parse_trade_direction(direction_str)
            # Extract signal params (without SL/TP)
            signal_params = {k: v for k, v in best_params.items() if k not in ("stop_loss_pct", "take_profit_pct")}
            long_entries, long_exits, short_entries, short_exits = generate_signals_for_strategy(
                candles=candles,
                strategy_type=strategy_type_str,
                params=signal_params,
                direction=direction_str,
            )
            bt_input = build_backtest_input(
                candles=candles,
                long_entries=long_entries,
                long_exits=long_exits,
                short_entries=short_entries,
                short_exits=short_exits,
                request_params=request_params,
                trade_direction=trade_direction,
                stop_loss_pct=best_params.get("stop_loss_pct", 0),
                take_profit_pct=best_params.get("take_profit_pct", 0),
            )
            bt_out = fallback_engine.run(bt_input)
            if bt_out.is_valid and bt_out.metrics:
                validated_metrics = {
                    "sharpe_ratio": bt_out.metrics.sharpe_ratio,
                    "total_return": bt_out.metrics.total_return,
                    "max_drawdown": bt_out.metrics.max_drawdown,
                    "win_rate": bt_out.metrics.win_rate * 100,
                    "total_trades": bt_out.metrics.total_trades,
                    "net_profit": bt_out.metrics.net_profit,
                    "profit_factor": bt_out.metrics.profit_factor,
                }
                logger.info(f"   вњ… FallbackV4 validation: Sharpe={validated_metrics['sharpe_ratio']:.4f}")
        except Exception as val_err:
            logger.warning(f"FallbackV4 validation failed: {val_err}")

    logger.info(f"вњ… Optimization completed in {execution_time:.2f}s")
    logger.info(f"   Selection criteria: {selection_criteria}")
    logger.info(f"   Best params: {best_params}")

    # Р“РµРЅРµСЂРёСЂСѓРµРј СѓРјРЅС‹Рµ СЂРµРєРѕРјРµРЅРґР°С†РёРё
    smart_recs = _generate_smart_recommendations(results)

    # РџСЂРµРѕР±СЂР°Р·СѓРµРј РІ РјРѕРґРµР»СЊ
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
    speed = int(len(results) / execution_time) if execution_time > 0 else 0

    return SyncOptimizationResponse(
        status="completed",
        total_combinations=total_combinations,
        tested_combinations=len(results),
        best_params=best_params or {},
        best_score=best_score if best_score != float("-inf") else 0,
        best_metrics={
            "total_return": best_result.get("total_return", 0) if best_result else 0,
            "sharpe_ratio": best_result.get("sharpe_ratio", 0) if best_result else 0,
            "max_drawdown": best_result.get("max_drawdown", 0) if best_result else 0,
            "max_drawdown_value": best_result.get("max_drawdown_value", 0) if best_result else 0,
            "win_rate": best_result.get("win_rate", 0) if best_result else 0,
            "total_trades": best_result.get("total_trades", 0) if best_result else 0,
            "winning_trades": best_result.get("winning_trades", 0) if best_result else 0,
            "losing_trades": best_result.get("losing_trades", 0) if best_result else 0,
            "profit_factor": best_result.get("profit_factor", 0) if best_result else 0,
            "net_profit": best_result.get("net_profit", 0) if best_result else 0,
            "gross_profit": best_result.get("gross_profit", 0) if best_result else 0,
            "gross_loss": best_result.get("gross_loss", 0) if best_result else 0,
            "avg_win": best_result.get("avg_win", 0) if best_result else 0,
            "avg_loss": best_result.get("avg_loss", 0) if best_result else 0,
            "avg_win_value": best_result.get("avg_win_value", best_result.get("avg_win", 0)) if best_result else 0,
            "avg_loss_value": best_result.get("avg_loss_value", best_result.get("avg_loss", 0)) if best_result else 0,
            "largest_win": best_result.get("largest_win", 0) if best_result else 0,
            "largest_loss": best_result.get("largest_loss", 0) if best_result else 0,
            "largest_win_value": best_result.get("largest_win", 0) if best_result else 0,
            "largest_loss_value": best_result.get("largest_loss", 0) if best_result else 0,
            "recovery_factor": best_result.get("recovery_factor", 0) if best_result else 0,
            "expectancy": best_result.get("expectancy", 0) if best_result else 0,
            "sortino_ratio": best_result.get("sortino_ratio", 0) if best_result else 0,
            "calmar_ratio": best_result.get("calmar_ratio", 0) if best_result else 0,
            "max_consecutive_wins": best_result.get("max_consecutive_wins", 0) if best_result else 0,
            "max_consecutive_losses": best_result.get("max_consecutive_losses", 0) if best_result else 0,
            "best_trade": best_result.get("best_trade", 0) if best_result else 0,
            "worst_trade": best_result.get("worst_trade", 0) if best_result else 0,
            "best_trade_pct": best_result.get("best_trade_pct", 0) if best_result else 0,
            "worst_trade_pct": best_result.get("worst_trade_pct", 0) if best_result else 0,
            # Long/Short statistics
            "long_trades": best_result.get("long_trades", 0) if best_result else 0,
            "long_winning_trades": best_result.get("long_winning_trades", 0) if best_result else 0,
            "long_losing_trades": best_result.get("long_losing_trades", 0) if best_result else 0,
            "long_win_rate": best_result.get("long_win_rate", 0) if best_result else 0,
            "long_gross_profit": best_result.get("long_gross_profit", 0) if best_result else 0,
            "long_gross_loss": best_result.get("long_gross_loss", 0) if best_result else 0,
            "long_net_profit": best_result.get("long_net_profit", 0) if best_result else 0,
            "long_profit_factor": best_result.get("long_profit_factor", 0) if best_result else 0,
            "long_avg_win": best_result.get("long_avg_win", 0) if best_result else 0,
            "long_avg_loss": best_result.get("long_avg_loss", 0) if best_result else 0,
            "short_trades": best_result.get("short_trades", 0) if best_result else 0,
            "short_winning_trades": best_result.get("short_winning_trades", 0) if best_result else 0,
            "short_losing_trades": best_result.get("short_losing_trades", 0) if best_result else 0,
            "short_win_rate": best_result.get("short_win_rate", 0) if best_result else 0,
            "short_gross_profit": best_result.get("short_gross_profit", 0) if best_result else 0,
            "short_gross_loss": best_result.get("short_gross_loss", 0) if best_result else 0,
            "short_net_profit": best_result.get("short_net_profit", 0) if best_result else 0,
            "short_profit_factor": best_result.get("short_profit_factor", 0) if best_result else 0,
            "short_avg_win": best_result.get("short_avg_win", 0) if best_result else 0,
            "short_avg_loss": best_result.get("short_avg_loss", 0) if best_result else 0,
            # Average bars in trade
            "avg_bars_in_trade": best_result.get("avg_bars_in_trade", 0) if best_result else 0,
            "avg_bars_in_winning": best_result.get("avg_bars_in_winning", 0) if best_result else 0,
            "avg_bars_in_losing": best_result.get("avg_bars_in_losing", 0) if best_result else 0,
            "avg_bars_in_long": best_result.get("avg_bars_in_long", 0) if best_result else 0,
            "avg_bars_in_short": best_result.get("avg_bars_in_short", 0) if best_result else 0,
            "avg_bars_in_winning_long": best_result.get("avg_bars_in_winning_long", 0) if best_result else 0,
            "avg_bars_in_losing_long": best_result.get("avg_bars_in_losing_long", 0) if best_result else 0,
            "avg_bars_in_winning_short": best_result.get("avg_bars_in_winning_short", 0) if best_result else 0,
            "avg_bars_in_losing_short": best_result.get("avg_bars_in_losing_short", 0) if best_result else 0,
            # Recovery factor Long/Short
            "recovery_long": best_result.get("recovery_long", 0) if best_result else 0,
            "recovery_short": best_result.get("recovery_short", 0) if best_result else 0,
            # Commission, Buy&Hold, CAGR
            "total_commission": best_result.get("total_commission", 0) if best_result else 0,
            "buy_hold_return": best_result.get("buy_hold_return", 0) if best_result else 0,
            "buy_hold_return_pct": best_result.get("buy_hold_return_pct", 0) if best_result else 0,
            "strategy_outperformance": best_result.get("strategy_outperformance", 0) if best_result else 0,
            "cagr": best_result.get("cagr", 0) if best_result else 0,
            "cagr_long": best_result.get("cagr_long", 0) if best_result else 0,
            "cagr_short": best_result.get("cagr_short", 0) if best_result else 0,
        },
        top_results=results[:10],
        execution_time_seconds=round(execution_time, 2),
        speed_combinations_per_sec=speed,
        num_workers=os.cpu_count() or 4,
        smart_recommendations=smart_recommendations,
        validated_metrics=validated_metrics,
    )


# =============================================================================
# OPTUNA BAYESIAN OPTIMIZATION (TPE/GP, fewer iterations, same quality)
# =============================================================================

# OptunaSyncRequest imported from backend.optimization.models


@router.post("/sync/optuna-search", response_model=SyncOptimizationResponse)
async def sync_optuna_optimization(
    request: OptunaSyncRequest,
    db: Session = Depends(get_db),
):
    """
    Bayesian optimization (Optuna TPE).

    Fewer iterations at the same quality, multi-criteria support, constraints.
    Supports all strategy types (RSI, MACD, Bollinger, SMA/EMA crossover).
    Returns top-N results with full metrics.
    """
    import time
    from datetime import datetime as dt

    import pandas as pd

    from backend.backtesting.engine_selector import get_engine
    from backend.backtesting.signal_generators import generate_signals_for_strategy
    from backend.optimization.optuna_optimizer import OPTUNA_AVAILABLE, OptunaOptimizer
    from backend.optimization.scoring import calculate_composite_score
    from backend.optimization.utils import (
        build_backtest_input,
        extract_metrics_from_output,
        parse_trade_direction,
    )
    from backend.services.data_service import DataService

    if not OPTUNA_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="Optuna not installed. pip install optuna",
        )

    start_time = time.time()
    strategy_type_str = request.strategy_type.lower()
    logger.info("рџ”¬ Starting Optuna Bayesian optimization")
    logger.info(f"   strategy={strategy_type_str}, n_trials={request.n_trials}, sampler={request.sampler_type}")

    db_interval = _normalize_interval(request.interval)
    try:
        start_dt = dt.fromisoformat(request.start_date)
        end_dt = dt.fromisoformat(request.end_date)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date: {e}")

    market_type = getattr(request, "market_type", "linear")
    data_service = DataService(db)
    candle_records = data_service.get_market_data(
        symbol=request.symbol,
        timeframe=db_interval,
        start_time=start_dt,
        end_time=end_dt,
        market_type=market_type,
    )
    if not candle_records:
        raise HTTPException(
            status_code=400,
            detail=f"No data for {request.symbol} {request.interval}",
        )

    candles = pd.DataFrame(
        [
            {
                "timestamp": pd.to_datetime(c.open_time, unit="ms", utc=True),
                "open": float(c.open_price or 0),
                "high": float(c.high_price or 0),
                "low": float(c.low_price or 0),
                "close": float(c.close_price or 0),
                "volume": float(c.volume or 0),
            }
            for c in candle_records
        ]
    )
    candles.set_index("timestamp", inplace=True)

    # в”Ђв”Ђ Build param_space based on strategy_type в”Ђв”Ђ
    def _low_high(arr, default_lo, default_hi):
        if not arr:
            return default_lo, default_hi
        return min(arr), max(arr)

    # Common: stop_loss and take_profit
    param_space = {
        "stop_loss_pct": {
            "type": "float",
            "low": _low_high(request.stop_loss_range, 1.0, 10.0)[0],
            "high": _low_high(request.stop_loss_range, 1.0, 10.0)[1],
            "step": 0.5,
        },
        "take_profit_pct": {
            "type": "float",
            "low": _low_high(request.take_profit_range, 1.0, 20.0)[0],
            "high": _low_high(request.take_profit_range, 1.0, 20.0)[1],
            "step": 0.5,
        },
    }

    # Strategy-specific params
    if strategy_type_str in ("sma_crossover", "sma"):
        param_space["sma_fast_period"] = {
            "type": "int",
            "low": _low_high(request.sma_fast_period_range, 5, 20)[0],
            "high": _low_high(request.sma_fast_period_range, 5, 20)[1],
        }
        param_space["sma_slow_period"] = {
            "type": "int",
            "low": _low_high(request.sma_slow_period_range, 30, 100)[0],
            "high": _low_high(request.sma_slow_period_range, 30, 100)[1],
        }
    elif strategy_type_str in ("ema_crossover", "ema"):
        param_space["ema_fast_period"] = {
            "type": "int",
            "low": _low_high(request.ema_fast_period_range, 5, 20)[0],
            "high": _low_high(request.ema_fast_period_range, 5, 20)[1],
        }
        param_space["ema_slow_period"] = {
            "type": "int",
            "low": _low_high(request.ema_slow_period_range, 30, 100)[0],
            "high": _low_high(request.ema_slow_period_range, 30, 100)[1],
        }
    elif strategy_type_str == "macd":
        param_space["macd_fast_period"] = {
            "type": "int",
            "low": _low_high(request.macd_fast_period_range, 8, 16)[0],
            "high": _low_high(request.macd_fast_period_range, 8, 16)[1],
        }
        param_space["macd_slow_period"] = {
            "type": "int",
            "low": _low_high(request.macd_slow_period_range, 20, 30)[0],
            "high": _low_high(request.macd_slow_period_range, 20, 30)[1],
        }
        param_space["macd_signal_period"] = {
            "type": "int",
            "low": _low_high(request.macd_signal_period_range, 7, 12)[0],
            "high": _low_high(request.macd_signal_period_range, 7, 12)[1],
        }
    elif strategy_type_str in ("bollinger_bands", "bollinger", "bb"):
        param_space["bb_period"] = {
            "type": "int",
            "low": _low_high(request.bb_period_range, 10, 30)[0],
            "high": _low_high(request.bb_period_range, 10, 30)[1],
        }
        param_space["bb_std_dev"] = {
            "type": "float",
            "low": _low_high(request.bb_std_dev_range, 1.5, 3.0)[0],
            "high": _low_high(request.bb_std_dev_range, 1.5, 3.0)[1],
            "step": 0.1,
        }
    else:
        # Default: RSI
        param_space["rsi_period"] = {
            "type": "int",
            "low": _low_high(request.rsi_period_range, 7, 30)[0],
            "high": _low_high(request.rsi_period_range, 7, 30)[1],
        }
        param_space["rsi_overbought"] = {
            "type": "int",
            "low": _low_high(request.rsi_overbought_range, 65, 85)[0],
            "high": _low_high(request.rsi_overbought_range, 65, 85)[1],
        }
        param_space["rsi_oversold"] = {
            "type": "int",
            "low": _low_high(request.rsi_oversold_range, 15, 35)[0],
            "high": _low_high(request.rsi_oversold_range, 15, 35)[1],
        }

    # Market regime requires FallbackV4 (Numba doesn't support it)
    optuna_engine = "fallback_v4" if getattr(request, "market_regime_enabled", False) else "numba"
    engine = get_engine(engine_type=optuna_engine)
    request_params = {
        "symbol": request.symbol,
        "interval": request.interval,
        "initial_capital": request.initial_capital,
        "leverage": request.leverage,
        "commission": request.commission,
        "use_fixed_amount": request.use_fixed_amount,
        "fixed_amount": request.fixed_amount,
        "optimize_metric": request.optimize_metric,
        "direction": request.direction,
        "market_regime_enabled": getattr(request, "market_regime_enabled", False),
        "market_regime_filter": getattr(request, "market_regime_filter", "not_volatile"),
        "market_regime_lookback": getattr(request, "market_regime_lookback", 50),
    }
    direction_str = request.direction
    trade_direction = parse_trade_direction(direction_str)

    def objective(params):
        """Universal objective вЂ” works for any strategy_type."""
        try:
            # Separate stop_loss/take_profit from signal params
            signal_params = {k: v for k, v in params.items() if k not in ("stop_loss_pct", "take_profit_pct")}

            le, lex, se, sex = generate_signals_for_strategy(
                candles=candles,
                strategy_type=strategy_type_str,
                params=signal_params,
                direction=direction_str,
            )

            sl_pct = params.get("stop_loss_pct", 0)
            tp_pct = params.get("take_profit_pct", 0)

            bt_input = build_backtest_input(
                candles=candles,
                long_entries=le,
                long_exits=lex,
                short_entries=se,
                short_exits=sex,
                request_params=request_params,
                trade_direction=trade_direction,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
            )

            out = engine.run(bt_input)
            if not out.is_valid or not out.metrics:
                return float("-inf")

            return calculate_composite_score(
                {
                    "sharpe_ratio": out.metrics.sharpe_ratio,
                    "total_return": out.metrics.total_return,
                    "max_drawdown": out.metrics.max_drawdown,
                    "win_rate": out.metrics.win_rate,
                    "total_trades": out.metrics.total_trades,
                    "profit_factor": out.metrics.profit_factor,
                    "net_profit": out.metrics.net_profit,
                },
                request_params["optimize_metric"],
                None,
            )
        except Exception as e:
            logger.debug(f"Optuna trial failed: {e}")
            return float("-inf")

    optuna_opt = OptunaOptimizer(sampler_type=request.sampler_type)
    result = optuna_opt.optimize_strategy(
        objective_fn=objective,
        param_space=param_space,
        n_trials=request.n_trials,
        n_jobs=request.n_jobs,
        show_progress=True,
    )

    # в”Ђв”Ђ Re-run top-N trials for full metrics в”Ђв”Ђ
    # Sort all completed trials by value (descending), take top 10
    top_n = 10
    sorted_trials = sorted(result.all_trials, key=lambda t: t["value"], reverse=True)
    top_trials = sorted_trials[:top_n]

    results = []
    for trial_info in top_trials:
        try:
            trial_params = trial_info["params"]
            signal_params = {k: v for k, v in trial_params.items() if k not in ("stop_loss_pct", "take_profit_pct")}

            le, lex, se, sex = generate_signals_for_strategy(
                candles=candles,
                strategy_type=strategy_type_str,
                params=signal_params,
                direction=direction_str,
            )

            sl_pct = trial_params.get("stop_loss_pct", 0)
            tp_pct = trial_params.get("take_profit_pct", 0)

            bt_input = build_backtest_input(
                candles=candles,
                long_entries=le,
                long_exits=lex,
                short_entries=se,
                short_exits=sex,
                request_params=request_params,
                trade_direction=trade_direction,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
            )

            out = engine.run(bt_input)
            if not out.is_valid:
                continue

            metrics_dict = extract_metrics_from_output(out, win_rate_as_pct=True)
            score = calculate_composite_score(
                metrics_dict,
                request_params["optimize_metric"],
                None,
            )

            results.append(
                {
                    "params": trial_params,
                    "score": score,
                    **metrics_dict,
                }
            )
        except Exception as e:
            logger.warning(f"Re-run of trial failed: {e}")

    # Sort results by score
    results.sort(key=lambda x: x["score"], reverse=True)

    best_result = results[0] if results else {"params": result.best_params, "score": result.best_value}

    execution_time = time.time() - start_time

    return SyncOptimizationResponse(
        status="completed",
        total_combinations=request.n_trials,
        tested_combinations=len(result.all_trials),
        best_params=best_result["params"],
        best_score=best_result["score"],
        best_metrics=best_result,
        top_results=results[:top_n],
        execution_time_seconds=round(execution_time, 2),
        speed_combinations_per_sec=int(request.n_trials / execution_time) if execution_time > 0 else 0,
        num_workers=request.n_jobs,
        smart_recommendations=None,
        validated_metrics=None,
    )
