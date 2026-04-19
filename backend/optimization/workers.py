"""
Optimization Workers.

Multiprocessing batch worker for grid search optimization.
Extracted from optimizations.py for maintainability.
"""

from __future__ import annotations

import logging

import pandas as pd

from backend.optimization.filters import passes_filters
from backend.optimization.scoring import calculate_composite_score
from backend.optimization.utils import (
    build_backtest_input,
    extract_metrics_from_output,
    parse_trade_direction,
)

logger = logging.getLogger(__name__)


def run_batch_backtests(
    batch: list[tuple],
    request_params: dict,
    candles_dict: list[dict],
    start_dt_str: str,
    end_dt_str: str,
    strategy_type_str: str,
    param_names: list[str] | None = None,
) -> list[dict]:
    """
    Run a batch of backtests in a subprocess.

    Designed for ProcessPoolExecutor — takes serializable args,
    reconstructs DataFrame internally.

    Args:
        batch: List of param tuples (values correspond to param_names).
        request_params: Serializable dict with all config.
        candles_dict: Candle data as list of dicts (serializable).
        start_dt_str: ISO start date string.
        end_dt_str: ISO end date string.
        strategy_type_str: Strategy type string.
        param_names: Ordered list of param names matching combo tuple positions.

    Returns:
        List of result dicts (may contain None for failed backtests).
    """
    from backend.backtesting.engine_selector import get_engine
    from backend.backtesting.signal_generators import generate_signals_for_strategy
    from backend.optimization.utils import combo_to_params

    # Reconstruct DataFrame from serializable data
    candles = pd.DataFrame(candles_dict)
    if "timestamp" in candles.columns:
        candles["timestamp"] = pd.to_datetime(candles["timestamp"])
        candles.set_index("timestamp", inplace=True)

    # Get engine (single warmup per process)
    engine_type = request_params.get("engine_type", "numba")
    engine = get_engine(engine_type=engine_type)

    # Parse direction
    direction_str = request_params.get("direction", "both")
    trade_direction = parse_trade_direction(direction_str)

    # Default param_names for backward compat (RSI)
    if param_names is None:
        param_names = ["rsi_period", "rsi_overbought", "rsi_oversold", "stop_loss_pct", "take_profit_pct"]

    results = []

    for combo in batch:
        try:
            # Convert combo tuple to named params dict
            named_params = combo_to_params(combo, param_names)
            stop_loss = named_params.pop("stop_loss_pct", 0)
            take_profit = named_params.pop("take_profit_pct", 0)

            # Generate signals using universal dispatcher
            long_entries, long_exits, short_entries, short_exits = generate_signals_for_strategy(
                candles=candles,
                strategy_type=strategy_type_str,
                params=named_params,
                direction=direction_str,
            )

            # Build input using shared builder
            bt_input = build_backtest_input(
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

            # Run backtest
            bt_output = engine.run(bt_input)

            if not bt_output.is_valid:
                continue

            # Extract metrics
            result = extract_metrics_from_output(bt_output, win_rate_as_pct=True)

            # Apply filters
            if not passes_filters(result, request_params):
                continue

            # Calculate score
            score = calculate_composite_score(
                result,
                request_params.get("optimize_metric", "sharpe_ratio"),
                request_params.get("weights"),
            )

            # Build result entry (without trades — memory optimization)
            result_entry = {
                "params": {
                    **named_params,
                    "stop_loss_pct": stop_loss,
                    "take_profit_pct": take_profit,
                },
                "score": score,
                **result,
            }

            results.append(result_entry)

        except Exception as e:
            logger.warning(f"Batch backtest failed: {combo} - {e}")

    return results
