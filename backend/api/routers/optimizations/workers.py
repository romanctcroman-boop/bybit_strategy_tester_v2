"""
Optimization Router — Internal worker/helper functions.

Thin delegates to refactored modules in backend.optimization.*
Kept here for backward compatibility and to keep the router clean.

Functions:
- _run_batch_backtests      → delegates to backend.optimization.workers
- _run_single_backtest_for_process → legacy process-pool helper
- _calculate_composite_score → delegates to backend.optimization.scoring
- _rank_by_multi_criteria   → delegates to backend.optimization.scoring
- _compute_weighted_composite
- _apply_custom_sort_order  → delegates to backend.optimization.scoring
- _generate_smart_recommendations → delegates to backend.optimization.recommendations
- _passes_filters           → delegates to backend.optimization.filters
- _passes_dynamic_constraints
- _run_single_backtest
"""

# mypy: disable-error-code="arg-type, assignment, var-annotated, return-value, union-attr, operator, attr-defined, misc, dict-item"

import logging
from typing import Any

from backend.optimization.filters import passes_filters
from backend.optimization.recommendations import generate_smart_recommendations
from backend.optimization.scoring import (
    apply_custom_sort_order,
    calculate_composite_score,
    rank_by_multi_criteria,
)

logger = logging.getLogger(__name__)


def _run_batch_backtests(
    batch: list,
    request_params: dict,
    candles_dict: list,
    start_dt_str: str,
    end_dt_str: str,
    strategy_type_str: str,
    param_names: list[str] | None = None,
) -> list:
    """
    Выполняет батч бэктестов в отдельном процессе.

    Thin wrapper — delegates to workers.run_batch_backtests()
    which handles universal strategy dispatch + DRY helpers.
    """
    from backend.optimization.workers import run_batch_backtests

    return run_batch_backtests(
        batch=batch,
        request_params=request_params,
        candles_dict=candles_dict,
        start_dt_str=start_dt_str,
        end_dt_str=end_dt_str,
        strategy_type_str=strategy_type_str,
        param_names=param_names,
    )


def _run_single_backtest_for_process(args: tuple) -> dict:
    """
    Выполняет один бэктест для заданных параметров.
    Версия для ProcessPoolExecutor - принимает tuple аргументов.
    """
    (
        period,
        overbought,
        oversold,
        request_params,
        candles_dict,
        start_dt_str,
        end_dt_str,
    ) = args

    from datetime import datetime as dt

    import pandas as pd

    from backend.backtesting.engine import BacktestEngine
    from backend.backtesting.models import BacktestConfig, StrategyType

    try:
        # Восстанавливаем DataFrame из dict
        candles = pd.DataFrame(candles_dict)
        candles["timestamp"] = pd.to_datetime(candles["timestamp"])
        candles.set_index("timestamp", inplace=True)

        # Парсим даты
        start_dt = dt.fromisoformat(start_dt_str)
        end_dt = dt.fromisoformat(end_dt_str)

        # Собрать конфигурацию стратегии
        strategy_params = {
            "period": period,
            "overbought": overbought,
            "oversold": oversold,
        }

        # Преобразуем strategy_type в StrategyType enum
        if request_params["strategy_type"].lower() == "rsi":
            strategy_type = StrategyType.RSI
        else:
            strategy_type = StrategyType.SMA_CROSSOVER

        config = BacktestConfig(
            symbol=request_params["symbol"],
            interval=request_params["interval"],
            start_date=start_dt,
            end_date=end_dt,
            strategy_type=strategy_type,
            strategy_params=strategy_params,
            initial_capital=request_params["initial_capital"],
            leverage=request_params["leverage"],
            direction=request_params["direction"],
            stop_loss=request_params["stop_loss_percent"] / 100.0 if request_params["stop_loss_percent"] else None,
            take_profit=request_params["take_profit_percent"] / 100.0
            if request_params["take_profit_percent"]
            else None,
            taker_fee=request_params["commission"],
            maker_fee=request_params["commission"],
        )

        engine = BacktestEngine()
        bt_result = engine.run(config, candles)

        # BacktestResult -> dict
        result = {
            "total_return": bt_result.metrics.total_return if bt_result.metrics else 0,
            "sharpe_ratio": bt_result.metrics.sharpe_ratio if bt_result.metrics else 0,
            "max_drawdown": bt_result.metrics.max_drawdown if bt_result.metrics else 0,
            "win_rate": bt_result.metrics.win_rate if bt_result.metrics else 0,
            "total_trades": bt_result.metrics.total_trades if bt_result.metrics else 0,
            "profit_factor": bt_result.metrics.profit_factor if bt_result.metrics else 0,
        }

        # Получить значение метрики
        metric_value = result.get(request_params["optimize_metric"], 0) or 0

        return {
            "params": {
                "rsi_period": period,
                "rsi_overbought": overbought,
                "rsi_oversold": oversold,
            },
            "score": metric_value,
            "total_return": result.get("total_return", 0),
            "sharpe_ratio": result.get("sharpe_ratio", 0),
            "max_drawdown": result.get("max_drawdown", 0),
            "win_rate": result.get("win_rate", 0),
            "total_trades": result.get("total_trades", 0),
        }
    except Exception:
        return None


def _calculate_composite_score(result: dict, metric: str, weights: dict | None = None) -> float:
    """Delegate to backend.optimization.scoring.calculate_composite_score."""
    return calculate_composite_score(result, metric, weights)


def _rank_by_multi_criteria(results: list, selection_criteria: list) -> list:
    """Delegate to backend.optimization.scoring.rank_by_multi_criteria."""
    return rank_by_multi_criteria(results, selection_criteria)


def _compute_weighted_composite(result: dict, weights: dict) -> float:
    """Compute weighted composite score from evaluation criteria weights.

    Supports all 20 metrics from EvaluationCriteriaPanel.
    Each metric is normalized to 0-1 range before applying weight.
    """
    if not weights:
        return 0.0

    # Normalization ranges for each metric type
    normalization = {
        "total_return": lambda v: (min(max(v, -100.0), 500.0) + 100.0) / 600.0,
        "cagr": lambda v: (min(max(v, -50.0), 200.0) + 50.0) / 250.0,
        "sharpe_ratio": lambda v: (min(max(v, -2.0), 3.0) + 2.0) / 5.0,
        "sortino_ratio": lambda v: (min(max(v, -2.0), 5.0) + 2.0) / 7.0,
        "calmar_ratio": lambda v: (min(max(v, -5.0), 10.0) + 5.0) / 15.0,
        "net_profit": lambda v: (min(max(v, -10000.0), 50000.0) + 10000.0) / 60000.0,
        "risk_adjusted_return": lambda v: (min(max(v, -100.0), 500.0) + 100.0) / 600.0,
        "max_drawdown": lambda v: 1.0 - min(abs(v), 100.0) / 100.0,
        "avg_drawdown": lambda v: 1.0 - min(abs(v), 50.0) / 50.0,
        "volatility": lambda v: 1.0 - min(abs(v), 100.0) / 100.0,
        "var_95": lambda v: 1.0 - min(abs(v), 50.0) / 50.0,
        "win_rate": lambda v: min(v, 100.0) / 100.0,
        "profit_factor": lambda v: min(v, 5.0) / 5.0,
        "avg_win": lambda v: min(max(v, 0.0), 10.0) / 10.0,
        "avg_loss": lambda v: 1.0 - min(abs(v), 10.0) / 10.0,
        "expectancy": lambda v: (min(max(v, -500.0), 2000.0) + 500.0) / 2500.0,
        "payoff_ratio": lambda v: min(v, 5.0) / 5.0,
        "recovery_factor": lambda v: min(v, 10.0) / 10.0,
        "total_trades": lambda v: min(v, 500.0) / 500.0,
        "trades_per_month": lambda v: min(v, 100.0) / 100.0,
        "avg_trade_duration": lambda v: min(v, 100.0) / 100.0,
        "avg_bars_in_trade": lambda v: min(v, 100.0) / 100.0,
    }

    score = 0.0
    for metric, weight in weights.items():
        value = result.get(metric, 0) or 0
        normalizer = normalization.get(metric)
        normalized = normalizer(value) if normalizer else min(max(value, 0.0), 1.0)
        score += normalized * weight

    return round(score, 4)


def _apply_custom_sort_order(results: list, sort_order: list[dict]) -> list:
    """Delegate to backend.optimization.scoring.apply_custom_sort_order."""
    return apply_custom_sort_order(results, sort_order)


def _generate_smart_recommendations(results: list) -> dict:
    """Delegate to backend.optimization.recommendations.generate_smart_recommendations."""
    return generate_smart_recommendations(results)


def _passes_filters(result: dict, request_params: dict) -> bool:
    """Delegate to backend.optimization.filters.passes_filters."""
    return passes_filters(result, request_params)


def _passes_dynamic_constraints(result: dict, constraints: list[dict]) -> bool:
    """Check if result passes all dynamic constraints from frontend.

    Constraint format: {"metric": "max_drawdown", "operator": "<=", "value": 15}
    Supported operators: <=, >=, <, >, ==, !=
    """
    for constraint in constraints:
        metric = constraint.get("metric")
        operator = constraint.get("operator")
        threshold = constraint.get("value")

        if not metric or not operator or threshold is None:
            continue

        value = result.get(metric, 0) or 0

        # For percentage metrics stored as negative (like max_drawdown), use absolute
        if metric in ("max_drawdown", "avg_drawdown") and value < 0:
            value = abs(value)

        try:
            if (
                (operator == "<=" and value > threshold)
                or (operator == ">=" and value < threshold)
                or (operator == "<" and value >= threshold)
                or (operator == ">" and value <= threshold)
                or (operator == "==" and value != threshold)
                or (operator == "!=" and value == threshold)
            ):
                return False
        except (TypeError, ValueError):
            continue

    return True


def _run_single_backtest(
    period: int,
    overbought: int,
    oversold: int,
    stop_loss_pct: float,
    take_profit_pct: float,
    request_params: dict,
    candles: Any,  # pandas DataFrame already prepared
    start_dt: Any,
    end_dt: Any,
    engine: Any,  # BacktestEngine already created
    strategy_type: Any,  # StrategyType already determined
) -> dict:
    """
    Выполняет один бэктест для заданных параметров.
    Функция для параллельного выполнения.
    Оптимизировано: переиспользует engine и candles DataFrame.
    """
    from backend.backtesting.models import BacktestConfig

    try:
        strategy_params = {
            "period": period,
            "overbought": overbought,
            "oversold": oversold,
        }

        position_size = 1.0
        if request_params.get("use_fixed_amount"):
            fixed_amount = request_params.get("fixed_amount") or 0
            initial_capital = request_params.get("initial_capital") or 1
            position_size = max(0.0001, min(1.0, fixed_amount / initial_capital))

        config = BacktestConfig(
            symbol=request_params["symbol"],
            interval=request_params["interval"],
            start_date=start_dt,
            end_date=end_dt,
            strategy_type=strategy_type,
            strategy_params=strategy_params,
            initial_capital=request_params["initial_capital"],
            position_size=position_size,
            leverage=request_params["leverage"],
            direction=request_params["direction"],
            stop_loss=stop_loss_pct / 100.0 if stop_loss_pct else None,
            take_profit=take_profit_pct / 100.0 if take_profit_pct else None,
            taker_fee=request_params["commission"],
            maker_fee=request_params["commission"],
            commission_on_margin=True,
        )

        bt_result = engine.run(config, candles, silent=True)

        result = {
            "total_return": bt_result.metrics.total_return if bt_result.metrics else 0,
            "sharpe_ratio": bt_result.metrics.sharpe_ratio if bt_result.metrics else 0,
            "max_drawdown": bt_result.metrics.max_drawdown if bt_result.metrics else 0,
            "win_rate": bt_result.metrics.win_rate if bt_result.metrics else 0,
            "total_trades": bt_result.metrics.total_trades if bt_result.metrics else 0,
            "profit_factor": bt_result.metrics.profit_factor if bt_result.metrics else 0,
        }

        if not _passes_filters(result, request_params):
            return None

        metric_value = _calculate_composite_score(
            result, request_params["optimize_metric"], request_params.get("weights")
        )

        return {
            "params": {
                "rsi_period": period,
                "rsi_overbought": overbought,
                "rsi_oversold": oversold,
                "stop_loss_pct": stop_loss_pct,
                "take_profit_pct": take_profit_pct,
            },
            "score": metric_value,
            "total_return": result.get("total_return", 0),
            "sharpe_ratio": result.get("sharpe_ratio", 0),
            "max_drawdown": result.get("max_drawdown", 0),
            "win_rate": result.get("win_rate", 0),
            "total_trades": result.get("total_trades", 0),
            "profit_factor": result.get("profit_factor", 0),
            "calmar_ratio": result.get("total_return", 0) / max(abs(result.get("max_drawdown", 0.01) * 100), 0.01),
        }
    except Exception as e:
        from loguru import logger as loguru_logger

        loguru_logger.warning(
            f"Backtest failed for period={period}, ob={overbought}, os={oversold}, "
            f"SL={stop_loss_pct}, TP={take_profit_pct}: {e}"
        )
        return None
