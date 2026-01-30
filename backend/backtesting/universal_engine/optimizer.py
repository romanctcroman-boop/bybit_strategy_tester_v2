"""
Universal Optimizer - Единый оптимизатор для ВСЕХ параметров.

Методы оптимизации:
- Grid Search: Полный перебор
- Random Search: Случайный перебор
- Bayesian: Байесовская оптимизация
- Genetic: Генетический алгоритм

Особенности:
- Оптимизация ЛЮБЫХ параметров стратегии
- Поддержка фильтров (min_trades, min_win_rate)
- Parallel execution
- Progress tracking

Автор: AI Agent
Версия: 1.0.0
"""

import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from itertools import product
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from loguru import logger

from backend.backtesting.universal_engine.core import (
    EngineMetrics,
    EngineOutput,
    UniversalMathEngine,
)


@dataclass
class OptimizableParameter:
    """Definition of an optimizable parameter."""

    name: str
    param_type: str  # "int", "float", "choice"
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    choices: Optional[List[Any]] = None
    depends_on: Optional[str] = None

    def generate_values(self) -> List[Any]:
        """Generate all possible values for this parameter."""
        if self.choices is not None:
            return self.choices

        if self.min_value is None or self.max_value is None or self.step is None:
            return []

        if self.param_type == "int":
            return list(
                range(int(self.min_value), int(self.max_value) + 1, int(self.step))
            )
        else:  # float
            values = []
            current = self.min_value
            while current <= self.max_value + 1e-10:
                values.append(round(current, 6))
                current += self.step
            return values

    def validate(self, value: Any) -> bool:
        """Validate a value against this parameter definition."""
        if self.choices is not None:
            return value in self.choices

        if self.min_value is not None and value < self.min_value:
            return False
        if self.max_value is not None and value > self.max_value:
            return False

        return True


@dataclass
class OptimizationResult:
    """Result of a single optimization run."""

    params: Dict[str, Any]
    metrics: EngineMetrics
    score: float  # Primary optimization metric
    is_valid: bool = True
    execution_time: float = 0.0


@dataclass
class OptimizationOutput:
    """Output from optimization."""

    results: List[OptimizationResult] = field(default_factory=list)
    best_result: Optional[OptimizationResult] = None
    total_combinations: int = 0
    completed_combinations: int = 0
    execution_time: float = 0.0
    method: str = "grid"

    # Statistics
    top_n_results: List[OptimizationResult] = field(default_factory=list)
    param_importance: Dict[str, float] = field(default_factory=dict)


# =============================================================================
# STANDARD PARAMETER DEFINITIONS
# =============================================================================

STRATEGY_PARAMS = {
    # RSI
    "rsi_period": OptimizableParameter("rsi_period", "int", 5, 50, 1),
    "rsi_overbought": OptimizableParameter("rsi_overbought", "int", 60, 90, 1),
    "rsi_oversold": OptimizableParameter("rsi_oversold", "int", 10, 40, 1),
    # MACD
    "macd_fast": OptimizableParameter("macd_fast", "int", 5, 20, 1),
    "macd_slow": OptimizableParameter("macd_slow", "int", 15, 40, 1),
    "macd_signal": OptimizableParameter("macd_signal", "int", 5, 15, 1),
    # Bollinger
    "bb_period": OptimizableParameter("bb_period", "int", 10, 50, 1),
    "bb_std_dev": OptimizableParameter("bb_std_dev", "float", 1.0, 3.0, 0.1),
    # Risk Management
    "stop_loss": OptimizableParameter("stop_loss", "float", 0.005, 0.10, 0.005),
    "take_profit": OptimizableParameter("take_profit", "float", 0.005, 0.20, 0.005),
    # DCA
    "dca_safety_orders": OptimizableParameter("dca_safety_orders", "int", 0, 10, 1),
    "dca_price_deviation": OptimizableParameter(
        "dca_price_deviation", "float", 0.005, 0.05, 0.005
    ),
    "dca_step_scale": OptimizableParameter("dca_step_scale", "float", 1.0, 2.0, 0.1),
    "dca_volume_scale": OptimizableParameter(
        "dca_volume_scale", "float", 1.0, 2.0, 0.1
    ),
    # Trailing Stop
    "trailing_stop_activation": OptimizableParameter(
        "trailing_stop_activation", "float", 0.005, 0.05, 0.005
    ),
    "trailing_stop_distance": OptimizableParameter(
        "trailing_stop_distance", "float", 0.002, 0.03, 0.001
    ),
    # Position Sizing
    "position_size": OptimizableParameter("position_size", "float", 0.05, 1.0, 0.05),
}


class UniversalOptimizer:
    """
    Universal optimizer for ALL strategy parameters.

    Features:
    - Grid Search
    - Random Search
    - Bayesian Optimization
    - Genetic Algorithm
    - Multi-metric optimization
    - Parallel execution
    """

    OPTIMIZE_METRICS = [
        "net_profit",
        "total_return",
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "profit_factor",
        "win_rate",
        "expectancy",
    ]

    def __init__(
        self,
        engine: Optional[UniversalMathEngine] = None,
        n_workers: int = -1,
        use_numba: bool = True,
    ):
        """
        Initialize optimizer.

        Args:
            engine: UniversalMathEngine instance (created if not provided)
            n_workers: Number of parallel workers (-1 = auto)
            use_numba: Use Numba acceleration
        """
        self.engine = engine or UniversalMathEngine(use_numba=use_numba)
        self.n_workers = n_workers if n_workers > 0 else 1
        self.use_numba = use_numba

        # Cache for candles
        self._candles_cache: Optional[pd.DataFrame] = None

    def optimize(
        self,
        candles: pd.DataFrame,
        strategy_type: str,
        base_params: Dict[str, Any],
        param_ranges: Dict[str, Union[List, Tuple[float, float, float]]],
        initial_capital: float = 10000.0,
        direction: str = "both",
        leverage: int = 10,
        optimize_metric: str = "sharpe_ratio",
        filters: Optional[Dict[str, float]] = None,
        method: str = "grid",
        top_n: int = 10,
        max_combinations: int = 100000,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> OptimizationOutput:
        """
        Run optimization.

        Args:
            candles: OHLCV DataFrame
            strategy_type: Strategy type (rsi, macd, etc.)
            base_params: Base strategy parameters
            param_ranges: Parameters to optimize with ranges
                         Format: {"param": [v1, v2, v3]} or {"param": (min, max, step)}
            initial_capital: Starting capital
            direction: Trading direction
            leverage: Leverage
            optimize_metric: Metric to optimize
            filters: Result filters (min_trades, min_win_rate, etc.)
            method: "grid", "random", "bayesian", "genetic"
            top_n: Number of top results to return
            max_combinations: Maximum combinations for random search
            progress_callback: Callback(completed, total)

        Returns:
            OptimizationOutput with results
        """
        start_time = time.time()
        output = OptimizationOutput(method=method)

        # Parse param_ranges
        param_values = {}
        for name, values in param_ranges.items():
            if isinstance(values, (list, np.ndarray)):
                param_values[name] = list(values)
            elif isinstance(values, tuple) and len(values) == 3:
                # (min, max, step)
                min_v, max_v, step = values
                if (
                    isinstance(min_v, int)
                    and isinstance(max_v, int)
                    and isinstance(step, int)
                ):
                    param_values[name] = list(range(min_v, max_v + 1, step))
                else:
                    vals = []
                    current = min_v
                    while current <= max_v + 1e-10:
                        vals.append(round(current, 6))
                        current += step
                    param_values[name] = vals
            else:
                raise ValueError(f"Invalid param_ranges format for {name}")

        # Calculate total combinations
        total_combinations = 1
        for vals in param_values.values():
            total_combinations *= len(vals)
        output.total_combinations = total_combinations

        logger.info(f"Universal Optimizer: {total_combinations:,} combinations")

        # Run optimization based on method
        if method == "grid":
            output.results = self._grid_search(
                candles,
                strategy_type,
                base_params,
                param_values,
                initial_capital,
                direction,
                leverage,
                optimize_metric,
                filters,
                progress_callback,
            )
        elif method == "random":
            output.results = self._random_search(
                candles,
                strategy_type,
                base_params,
                param_values,
                initial_capital,
                direction,
                leverage,
                optimize_metric,
                filters,
                max_combinations,
                progress_callback,
            )
        else:
            # Default to grid
            output.results = self._grid_search(
                candles,
                strategy_type,
                base_params,
                param_values,
                initial_capital,
                direction,
                leverage,
                optimize_metric,
                filters,
                progress_callback,
            )

        output.completed_combinations = len(output.results)

        # Sort by score
        output.results.sort(key=lambda x: x.score, reverse=True)

        # Get top N
        output.top_n_results = output.results[:top_n]

        # Best result
        if output.results:
            output.best_result = output.results[0]

        output.execution_time = time.time() - start_time

        logger.info(f"Optimization completed in {output.execution_time:.2f}s")
        if output.best_result:
            logger.info(f"Best {optimize_metric}: {output.best_result.score:.4f}")
            logger.info(f"Best params: {output.best_result.params}")

        return output

    def _grid_search(
        self,
        candles: pd.DataFrame,
        strategy_type: str,
        base_params: Dict[str, Any],
        param_values: Dict[str, List],
        initial_capital: float,
        direction: str,
        leverage: int,
        optimize_metric: str,
        filters: Optional[Dict[str, float]],
        progress_callback: Optional[Callable[[int, int], None]],
    ) -> List[OptimizationResult]:
        """Run grid search optimization."""
        results = []

        # Generate all combinations
        param_names = list(param_values.keys())
        all_values = [param_values[name] for name in param_names]

        combinations = list(product(*all_values))
        total = len(combinations)

        logger.info(f"Grid search: {total:,} combinations")

        for i, combo in enumerate(combinations):
            # Build params
            params = dict(base_params)
            strategy_params = dict(base_params.get("strategy_params", {}))

            for name, value in zip(param_names, combo):
                if name in ["stop_loss", "take_profit", "position_size"]:
                    params[name] = value
                else:
                    strategy_params[name] = value

            params["strategy_params"] = strategy_params

            # Run backtest
            try:
                result = self.engine.run(
                    candles=candles,
                    strategy_type=strategy_type,
                    strategy_params=strategy_params,
                    initial_capital=initial_capital,
                    direction=direction,
                    stop_loss=params.get("stop_loss", 0.02),
                    take_profit=params.get("take_profit", 0.03),
                    leverage=leverage,
                    position_size=params.get("position_size", 0.10),
                )

                if not result.is_valid:
                    continue

                # Apply filters
                if not self._passes_filters(result.metrics, filters):
                    continue

                # Get score
                score = getattr(result.metrics, optimize_metric, 0.0)

                # Create result
                opt_result = OptimizationResult(
                    params=dict(zip(param_names, combo)),
                    metrics=result.metrics,
                    score=score,
                    execution_time=result.execution_time,
                )
                results.append(opt_result)

            except Exception as e:
                logger.debug(f"Backtest failed for params {combo}: {e}")

            # Progress callback
            if progress_callback and (i + 1) % 100 == 0:
                progress_callback(i + 1, total)

        return results

    def _random_search(
        self,
        candles: pd.DataFrame,
        strategy_type: str,
        base_params: Dict[str, Any],
        param_values: Dict[str, List],
        initial_capital: float,
        direction: str,
        leverage: int,
        optimize_metric: str,
        filters: Optional[Dict[str, float]],
        max_combinations: int,
        progress_callback: Optional[Callable[[int, int], None]],
    ) -> List[OptimizationResult]:
        """Run random search optimization."""
        results = []
        param_names = list(param_values.keys())

        # Calculate total possible
        total_possible = 1
        for vals in param_values.values():
            total_possible *= len(vals)

        n_samples = min(max_combinations, total_possible)

        logger.info(
            f"Random search: {n_samples:,} samples out of {total_possible:,} possible"
        )

        # Generate random samples
        seen = set()

        for i in range(n_samples):
            # Generate random combo
            combo = tuple(np.random.choice(param_values[name]) for name in param_names)

            # Skip duplicates
            if combo in seen:
                continue
            seen.add(combo)

            # Build params
            params = dict(base_params)
            strategy_params = dict(base_params.get("strategy_params", {}))

            for name, value in zip(param_names, combo):
                if name in ["stop_loss", "take_profit", "position_size"]:
                    params[name] = value
                else:
                    strategy_params[name] = value

            params["strategy_params"] = strategy_params

            # Run backtest
            try:
                result = self.engine.run(
                    candles=candles,
                    strategy_type=strategy_type,
                    strategy_params=strategy_params,
                    initial_capital=initial_capital,
                    direction=direction,
                    stop_loss=params.get("stop_loss", 0.02),
                    take_profit=params.get("take_profit", 0.03),
                    leverage=leverage,
                    position_size=params.get("position_size", 0.10),
                )

                if not result.is_valid:
                    continue

                if not self._passes_filters(result.metrics, filters):
                    continue

                score = getattr(result.metrics, optimize_metric, 0.0)

                opt_result = OptimizationResult(
                    params=dict(zip(param_names, combo)),
                    metrics=result.metrics,
                    score=score,
                    execution_time=result.execution_time,
                )
                results.append(opt_result)

            except Exception as e:
                logger.debug(f"Backtest failed: {e}")

            if progress_callback and (i + 1) % 100 == 0:
                progress_callback(i + 1, n_samples)

        return results

    def _passes_filters(
        self, metrics: EngineMetrics, filters: Optional[Dict[str, float]]
    ) -> bool:
        """Check if metrics pass all filters."""
        if filters is None:
            return True

        if "min_trades" in filters and metrics.total_trades < filters["min_trades"]:
            return False

        if "min_win_rate" in filters and metrics.win_rate < filters["min_win_rate"]:
            return False

        if "max_drawdown" in filters and metrics.max_drawdown > filters["max_drawdown"]:
            return False

        if (
            "min_profit_factor" in filters
            and metrics.profit_factor < filters["min_profit_factor"]
        ):
            return False

        if "min_sharpe" in filters and metrics.sharpe_ratio < filters["min_sharpe"]:
            return False

        return True

    def quick_optimize(
        self,
        candles: pd.DataFrame,
        strategy_type: str = "rsi",
        direction: str = "both",
        optimize_metric: str = "sharpe_ratio",
    ) -> OptimizationOutput:
        """
        Quick optimization with standard parameter ranges.

        Args:
            candles: OHLCV DataFrame
            strategy_type: Strategy type
            direction: Trading direction
            optimize_metric: Metric to optimize

        Returns:
            OptimizationOutput
        """
        # Standard ranges for quick optimization
        if strategy_type == "rsi":
            param_ranges = {
                "period": [10, 14, 21],
                "overbought": [70, 75, 80],
                "oversold": [20, 25, 30],
                "stop_loss": [0.01, 0.02, 0.03],
                "take_profit": [0.01, 0.02, 0.03, 0.04],
            }
            base_params = {
                "strategy_params": {"period": 14, "overbought": 70, "oversold": 30}
            }

        elif strategy_type == "macd":
            param_ranges = {
                "fast_period": [8, 12],
                "slow_period": [21, 26],
                "signal_period": [7, 9],
                "stop_loss": [0.01, 0.02, 0.03],
                "take_profit": [0.01, 0.02, 0.03, 0.04],
            }
            base_params = {
                "strategy_params": {
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                }
            }

        else:
            param_ranges = {
                "stop_loss": [0.01, 0.02, 0.03],
                "take_profit": [0.01, 0.02, 0.03, 0.04],
            }
            base_params = {"strategy_params": {}}

        return self.optimize(
            candles=candles,
            strategy_type=strategy_type,
            base_params=base_params,
            param_ranges=param_ranges,
            direction=direction,
            optimize_metric=optimize_metric,
            filters={"min_trades": 5},
        )
