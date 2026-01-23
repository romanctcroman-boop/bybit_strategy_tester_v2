"""
Walk-Forward Optimization Service.

Provides rolling window validation to:
- Test strategy robustness across different market regimes
- Detect overfitting by validating on out-of-sample data
- Calculate stability metrics for parameter selection
- Generate optimization recommendations

Usage:
    from backend.services.walk_forward import WalkForwardOptimizer

    optimizer = WalkForwardOptimizer(
        n_splits=5,
        train_ratio=0.7,
    )

    results = optimizer.optimize(
        data=candles,
        strategy_class=GridStrategy,
        param_grid={"grid_size": [5, 10, 15], "tp_pct": [0.01, 0.02]},
        initial_capital=10000,
    )
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardWindow:
    """Single walk-forward window result."""

    window_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime

    # Training period results
    train_return: float = 0.0
    train_sharpe: float = 0.0
    train_max_drawdown: float = 0.0
    train_trades: int = 0

    # Testing period results (out-of-sample)
    test_return: float = 0.0
    test_sharpe: float = 0.0
    test_max_drawdown: float = 0.0
    test_trades: int = 0

    # Best parameters from this window
    best_params: dict[str, Any] = field(default_factory=dict)

    # Performance degradation
    return_degradation: float = 0.0  # test_return / train_return
    sharpe_degradation: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "window_id": self.window_id,
            "train_period": {
                "start": self.train_start.isoformat() if self.train_start else None,
                "end": self.train_end.isoformat() if self.train_end else None,
            },
            "test_period": {
                "start": self.test_start.isoformat() if self.test_start else None,
                "end": self.test_end.isoformat() if self.test_end else None,
            },
            "train_metrics": {
                "return_pct": round(self.train_return * 100, 2),
                "sharpe": round(self.train_sharpe, 3),
                "max_drawdown_pct": round(self.train_max_drawdown * 100, 2),
                "trades": self.train_trades,
            },
            "test_metrics": {
                "return_pct": round(self.test_return * 100, 2),
                "sharpe": round(self.test_sharpe, 3),
                "max_drawdown_pct": round(self.test_max_drawdown * 100, 2),
                "trades": self.test_trades,
            },
            "best_params": self.best_params,
            "degradation": {
                "return_pct": round(self.return_degradation * 100, 2),
                "sharpe_pct": round(self.sharpe_degradation * 100, 2),
            },
        }


@dataclass
class WalkForwardResult:
    """Complete walk-forward optimization result."""

    n_splits: int
    train_ratio: float
    windows: list[WalkForwardWindow]

    # Aggregate metrics
    avg_train_return: float = 0.0
    avg_test_return: float = 0.0
    avg_train_sharpe: float = 0.0
    avg_test_sharpe: float = 0.0

    # Consistency metrics
    consistency_ratio: float = 0.0  # % of windows where test > 0
    parameter_stability: float = 0.0  # How stable are optimal params
    avg_degradation: float = 0.0

    # Overfitting score (0 = no overfit, 1 = severe overfit)
    overfit_score: float = 0.0

    # Recommended parameters
    recommended_params: dict[str, Any] = field(default_factory=dict)
    confidence_level: str = "low"  # low, medium, high

    # Timing
    optimization_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "config": {
                "n_splits": self.n_splits,
                "train_ratio": self.train_ratio,
            },
            "aggregate_metrics": {
                "train": {
                    "avg_return_pct": round(self.avg_train_return * 100, 2),
                    "avg_sharpe": round(self.avg_train_sharpe, 3),
                },
                "test": {
                    "avg_return_pct": round(self.avg_test_return * 100, 2),
                    "avg_sharpe": round(self.avg_test_sharpe, 3),
                },
            },
            "robustness": {
                "consistency_ratio_pct": round(self.consistency_ratio * 100, 2),
                "parameter_stability_pct": round(self.parameter_stability * 100, 2),
                "avg_degradation_pct": round(self.avg_degradation * 100, 2),
                "overfit_score": round(self.overfit_score, 3),
            },
            "recommendation": {
                "params": self.recommended_params,
                "confidence": self.confidence_level,
            },
            "windows": [w.to_dict() for w in self.windows],
            "optimization_time_ms": round(self.optimization_time_ms, 2),
        }


class WalkForwardOptimizer:
    """
    Walk-Forward Optimization for strategy validation.

    Splits data into rolling train/test windows to:
    1. Optimize parameters on training data
    2. Validate on out-of-sample test data
    3. Detect overfitting
    4. Find robust parameter combinations
    """

    def __init__(
        self,
        n_splits: int = 5,
        train_ratio: float = 0.7,
        gap_periods: int = 0,
    ):
        """
        Initialize walk-forward optimizer.

        Args:
            n_splits: Number of walk-forward windows
            train_ratio: Ratio of data for training vs testing in each window
            gap_periods: Number of periods to skip between train and test (avoid lookahead)
        """
        self.n_splits = n_splits
        self.train_ratio = train_ratio
        self.gap_periods = gap_periods

    def optimize(
        self,
        data: list[dict],
        strategy_runner: Callable[[list[dict], dict, float], dict],
        param_grid: dict[str, list[Any]],
        initial_capital: float = 10000.0,
        metric: str = "sharpe",  # Metric to optimize
    ) -> WalkForwardResult:
        """
        Run walk-forward optimization.

        Args:
            data: List of candle dictionaries with 'open_time', 'open', 'high', 'low', 'close', 'volume'
            strategy_runner: Function that runs strategy and returns results dict
                            Signature: (data, params, capital) -> {"return": float, "sharpe": float, ...}
            param_grid: Dictionary of parameter names to lists of values to try
            initial_capital: Starting capital
            metric: Metric to optimize ('return', 'sharpe', 'calmar')

        Returns:
            WalkForwardResult with all window results and recommendations
        """
        import time
        from itertools import product

        start_time = time.perf_counter()

        # Sort data by time
        sorted_data = sorted(data, key=lambda x: x.get("open_time", 0))
        total_len = len(sorted_data)

        if total_len < self.n_splits * 10:
            raise ValueError(
                f"Insufficient data: {total_len} candles for {self.n_splits} splits"
            )

        # Calculate window sizes
        window_size = total_len // self.n_splits
        train_size = int(window_size * self.train_ratio)
        test_size = window_size - train_size - self.gap_periods

        # Generate parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(product(*param_values))

        logger.info(
            f"Walk-forward: {self.n_splits} splits, {len(param_combinations)} param combos"
        )

        windows: list[WalkForwardWindow] = []
        all_best_params: list[dict] = []

        for split_idx in range(self.n_splits):
            start_idx = split_idx * window_size
            train_end_idx = start_idx + train_size
            test_start_idx = train_end_idx + self.gap_periods
            test_end_idx = min(test_start_idx + test_size, total_len)

            train_data = sorted_data[start_idx:train_end_idx]
            test_data = sorted_data[test_start_idx:test_end_idx]

            if not train_data or not test_data:
                continue

            # Get timestamps
            train_start = self._extract_datetime(train_data[0])
            train_end = self._extract_datetime(train_data[-1])
            test_start = self._extract_datetime(test_data[0])
            test_end = self._extract_datetime(test_data[-1])

            # Optimize on training data
            best_train_result = None
            best_train_metric = float("-inf")
            best_params = {}

            for combo in param_combinations:
                params = dict(zip(param_names, combo))
                try:
                    result = strategy_runner(train_data, params, initial_capital)
                    metric_value = result.get(metric, result.get("return", 0))

                    if metric_value > best_train_metric:
                        best_train_metric = metric_value
                        best_train_result = result
                        best_params = params.copy()
                except Exception as e:
                    logger.debug(f"Strategy run failed for {params}: {e}")
                    continue

            if best_train_result is None:
                continue

            # Validate on test data with best params
            try:
                test_result = strategy_runner(test_data, best_params, initial_capital)
            except Exception as e:
                logger.warning(f"Test run failed: {e}")
                test_result = {"return": 0, "sharpe": 0, "max_drawdown": 0, "trades": 0}

            # Calculate degradation
            train_ret = best_train_result.get("return", 0)
            test_ret = test_result.get("return", 0)
            return_deg = (test_ret / train_ret - 1) if train_ret != 0 else 0

            train_sharpe = best_train_result.get("sharpe", 0)
            test_sharpe = test_result.get("sharpe", 0)
            sharpe_deg = (test_sharpe / train_sharpe - 1) if train_sharpe != 0 else 0

            window = WalkForwardWindow(
                window_id=split_idx + 1,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_return=train_ret,
                train_sharpe=train_sharpe,
                train_max_drawdown=best_train_result.get("max_drawdown", 0),
                train_trades=best_train_result.get("trades", 0),
                test_return=test_ret,
                test_sharpe=test_sharpe,
                test_max_drawdown=test_result.get("max_drawdown", 0),
                test_trades=test_result.get("trades", 0),
                best_params=best_params,
                return_degradation=return_deg,
                sharpe_degradation=sharpe_deg,
            )

            windows.append(window)
            all_best_params.append(best_params)

        if not windows:
            raise ValueError("No valid windows generated")

        # Calculate aggregate metrics
        result = self._calculate_aggregates(windows, all_best_params, param_names)
        result.optimization_time_ms = (time.perf_counter() - start_time) * 1000

        return result

    def _calculate_aggregates(
        self,
        windows: list[WalkForwardWindow],
        all_best_params: list[dict],
        param_names: list[str],
    ) -> WalkForwardResult:
        """Calculate aggregate metrics and recommendations."""
        n = len(windows)

        # Average metrics
        avg_train_return = np.mean([w.train_return for w in windows])
        avg_test_return = np.mean([w.test_return for w in windows])
        avg_train_sharpe = np.mean([w.train_sharpe for w in windows])
        avg_test_sharpe = np.mean([w.test_sharpe for w in windows])

        # Consistency: % of windows with positive test return
        positive_windows = sum(1 for w in windows if w.test_return > 0)
        consistency_ratio = positive_windows / n if n > 0 else 0

        # Parameter stability: How often same params are selected
        if all_best_params:
            param_stability = self._calculate_param_stability(
                all_best_params, param_names
            )
        else:
            param_stability = 0

        # Average degradation
        avg_degradation = np.mean([w.return_degradation for w in windows])

        # Overfit score: combination of degradation and inconsistency
        overfit_score = min(
            1.0,
            max(
                0.0,
                0.5 * (1 - consistency_ratio)
                + 0.3 * min(1.0, abs(avg_degradation))
                + 0.2 * (1 - param_stability),
            ),
        )

        # Recommended params: most frequent or median values
        recommended_params = self._calculate_recommended_params(
            all_best_params, param_names
        )

        # Confidence level
        if overfit_score < 0.2 and consistency_ratio >= 0.8:
            confidence = "high"
        elif overfit_score < 0.4 and consistency_ratio >= 0.6:
            confidence = "medium"
        else:
            confidence = "low"

        return WalkForwardResult(
            n_splits=self.n_splits,
            train_ratio=self.train_ratio,
            windows=windows,
            avg_train_return=float(avg_train_return),
            avg_test_return=float(avg_test_return),
            avg_train_sharpe=float(avg_train_sharpe),
            avg_test_sharpe=float(avg_test_sharpe),
            consistency_ratio=float(consistency_ratio),
            parameter_stability=float(param_stability),
            avg_degradation=float(avg_degradation),
            overfit_score=float(overfit_score),
            recommended_params=recommended_params,
            confidence_level=confidence,
        )

    def _calculate_param_stability(
        self,
        all_params: list[dict],
        param_names: list[str],
    ) -> float:
        """Calculate how stable parameters are across windows."""
        if not all_params or not param_names:
            return 0.0

        stabilities = []
        for name in param_names:
            values = [p.get(name) for p in all_params if name in p]
            if not values:
                continue

            # For numeric: use coefficient of variation
            try:
                numeric_vals = [float(v) for v in values]
                if len(set(numeric_vals)) == 1:
                    stabilities.append(1.0)  # All same value
                else:
                    mean_val = np.mean(numeric_vals)
                    std_val = np.std(numeric_vals)
                    cv = std_val / abs(mean_val) if mean_val != 0 else 1
                    stabilities.append(max(0, 1 - cv))
            except (ValueError, TypeError):
                # Non-numeric: use mode frequency
                from collections import Counter

                counts = Counter(values)
                mode_freq = counts.most_common(1)[0][1] / len(values)
                stabilities.append(mode_freq)

        return np.mean(stabilities) if stabilities else 0.0

    def _calculate_recommended_params(
        self,
        all_params: list[dict],
        param_names: list[str],
    ) -> dict[str, Any]:
        """Calculate recommended parameters from all windows."""
        from collections import Counter

        recommended = {}

        for name in param_names:
            values = [p.get(name) for p in all_params if name in p]
            if not values:
                continue

            try:
                # Numeric: use median
                numeric_vals = [float(v) for v in values]
                recommended[name] = float(np.median(numeric_vals))
            except (ValueError, TypeError):
                # Non-numeric: use mode
                counts = Counter(values)
                recommended[name] = counts.most_common(1)[0][0]

        return recommended

    @staticmethod
    def _extract_datetime(candle: dict) -> datetime:
        """Extract datetime from candle."""
        ts = candle.get("open_time", candle.get("timestamp", 0))
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, (int, float)):
            # Assume milliseconds if > 1e12
            if ts > 1e12:
                ts = ts / 1000
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        return datetime.now(timezone.utc)


def simple_strategy_runner(
    data: list[dict],
    params: dict,
    capital: float,
) -> dict:
    """
    Simple example strategy runner for testing.

    This is a placeholder - real strategies should be implemented properly.
    """
    if not data:
        return {"return": 0, "sharpe": 0, "max_drawdown": 0, "trades": 0}

    # Extract parameters
    lookback = params.get("lookback", 20)
    threshold = params.get("threshold", 0.02)

    # Calculate simple returns
    closes = np.array([c.get("close", c.get("close_price", 0)) for c in data])
    if len(closes) < lookback + 1:
        return {"return": 0, "sharpe": 0, "max_drawdown": 0, "trades": 0}

    # Simple momentum strategy
    returns = np.diff(closes) / closes[:-1]

    # Filter by threshold
    signals = np.where(np.abs(returns) > threshold, np.sign(returns), 0)
    strategy_returns = returns[lookback:] * signals[lookback - 1 : -1]

    if len(strategy_returns) == 0:
        return {"return": 0, "sharpe": 0, "max_drawdown": 0, "trades": 0}

    total_return = float(np.sum(strategy_returns))
    sharpe = (
        float(np.mean(strategy_returns) / np.std(strategy_returns) * np.sqrt(252))
        if np.std(strategy_returns) > 0
        else 0
    )

    # Calculate max drawdown
    cumulative = np.cumprod(1 + strategy_returns)
    peak = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - peak) / peak
    max_dd = float(np.min(drawdown)) if len(drawdown) > 0 else 0

    trades = int(np.sum(np.abs(np.diff(signals[lookback:])) > 0))

    return {
        "return": total_return,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "trades": trades,
    }


# Global instance
_walk_forward_optimizer: Optional[WalkForwardOptimizer] = None


def get_walk_forward_optimizer() -> WalkForwardOptimizer:
    """Get or create the global walk-forward optimizer instance."""
    global _walk_forward_optimizer
    if _walk_forward_optimizer is None:
        _walk_forward_optimizer = WalkForwardOptimizer()
    return _walk_forward_optimizer
