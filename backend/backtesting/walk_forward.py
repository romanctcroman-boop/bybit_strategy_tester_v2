"""
Walk-Forward Optimization Framework.

Provides tools for robust strategy validation using rolling window optimization:
- In-sample optimization to find best parameters
- Out-of-sample testing to validate parameters
- Anchored and rolling window modes
- Performance degradation analysis
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Tuple

import numpy as np
import pandas as pd


@dataclass
class WalkForwardWindow:
    """Single walk-forward window result."""

    window_idx: int
    in_sample_start: datetime
    in_sample_end: datetime
    out_sample_start: datetime
    out_sample_end: datetime
    best_params: Dict[str, Any]
    in_sample_sharpe: float
    in_sample_return: float
    in_sample_trades: int
    out_sample_sharpe: float
    out_sample_return: float
    out_sample_trades: int
    # Performance degradation
    sharpe_degradation: float = 0.0  # % change from IS to OOS
    return_degradation: float = 0.0


@dataclass
class WalkForwardResult:
    """Complete walk-forward optimization result."""

    strategy_name: str
    total_windows: int
    windows: List[WalkForwardWindow]
    # Aggregated metrics
    avg_is_sharpe: float = 0.0
    avg_oos_sharpe: float = 0.0
    avg_sharpe_degradation: float = 0.0
    avg_is_return: float = 0.0
    avg_oos_return: float = 0.0
    avg_return_degradation: float = 0.0
    total_is_trades: int = 0
    total_oos_trades: int = 0
    # Robustness metrics
    oos_win_rate: float = 0.0  # % of windows where OOS was profitable
    parameter_stability: float = 0.0  # How stable are optimal params across windows
    # Combined OOS equity curve
    combined_oos_equity: List[float] = field(default_factory=list)
    combined_oos_sharpe: float = 0.0
    combined_oos_return: float = 0.0


class WalkForwardOptimizer:
    """
    Walk-Forward Optimization for strategy validation.

    Splits data into rolling windows:
    - In-sample (IS): Used to optimize parameters
    - Out-of-sample (OOS): Used to test optimized parameters

    Modes:
    - Rolling: Fixed-size sliding window
    - Anchored: In-sample starts from beginning, grows over time
    """

    def __init__(
        self,
        in_sample_ratio: float = 0.7,  # 70% in-sample, 30% out-of-sample
        n_windows: int = 5,  # Number of walk-forward windows
        mode: str = "rolling",  # "rolling" or "anchored"
        min_trades_per_window: int = 10,  # Minimum trades for valid window
    ):
        """
        Initialize Walk-Forward Optimizer.

        Args:
            in_sample_ratio: Ratio of data for in-sample optimization
            n_windows: Number of walk-forward windows
            mode: "rolling" (fixed size) or "anchored" (growing IS period)
            min_trades_per_window: Minimum trades required per window
        """
        self.in_sample_ratio = in_sample_ratio
        self.n_windows = n_windows
        self.mode = mode
        self.min_trades_per_window = min_trades_per_window

    def _create_windows(
        self, data: pd.DataFrame, timestamp_col: str = "timestamp"
    ) -> List[
        Tuple[pd.DataFrame, pd.DataFrame, datetime, datetime, datetime, datetime]
    ]:
        """
        Create walk-forward windows from data.

        Returns list of tuples: (is_data, oos_data, is_start, is_end, oos_start, oos_end)
        """
        n = len(data)
        windows = []

        if self.mode == "rolling":
            # Rolling window: fixed-size windows that slide through data
            total_window_size = n // self.n_windows
            is_size = int(total_window_size * self.in_sample_ratio)
            oos_size = total_window_size - is_size

            for i in range(self.n_windows):
                is_start_idx = i * total_window_size
                is_end_idx = is_start_idx + is_size
                oos_start_idx = is_end_idx
                oos_end_idx = min(oos_start_idx + oos_size, n)

                if oos_end_idx <= oos_start_idx:
                    continue

                is_data = data.iloc[is_start_idx:is_end_idx].copy()
                oos_data = data.iloc[oos_start_idx:oos_end_idx].copy()

                # Get timestamps
                is_start = (
                    is_data[timestamp_col].iloc[0]
                    if timestamp_col in is_data.columns
                    else datetime.now()
                )
                is_end = (
                    is_data[timestamp_col].iloc[-1]
                    if timestamp_col in is_data.columns
                    else datetime.now()
                )
                oos_start = (
                    oos_data[timestamp_col].iloc[0]
                    if timestamp_col in oos_data.columns
                    else datetime.now()
                )
                oos_end = (
                    oos_data[timestamp_col].iloc[-1]
                    if timestamp_col in oos_data.columns
                    else datetime.now()
                )

                windows.append(
                    (is_data, oos_data, is_start, is_end, oos_start, oos_end)
                )

        elif self.mode == "anchored":
            # Anchored window: IS always starts from beginning, grows over time
            oos_size = n // (self.n_windows + 1)

            for i in range(self.n_windows):
                is_start_idx = 0
                is_end_idx = (i + 1) * oos_size
                oos_start_idx = is_end_idx
                oos_end_idx = min(oos_start_idx + oos_size, n)

                if oos_end_idx <= oos_start_idx:
                    continue

                is_data = data.iloc[is_start_idx:is_end_idx].copy()
                oos_data = data.iloc[oos_start_idx:oos_end_idx].copy()

                # Get timestamps
                is_start = (
                    is_data[timestamp_col].iloc[0]
                    if timestamp_col in is_data.columns
                    else datetime.now()
                )
                is_end = (
                    is_data[timestamp_col].iloc[-1]
                    if timestamp_col in is_data.columns
                    else datetime.now()
                )
                oos_start = (
                    oos_data[timestamp_col].iloc[0]
                    if timestamp_col in oos_data.columns
                    else datetime.now()
                )
                oos_end = (
                    oos_data[timestamp_col].iloc[-1]
                    if timestamp_col in oos_data.columns
                    else datetime.now()
                )

                windows.append(
                    (is_data, oos_data, is_start, is_end, oos_start, oos_end)
                )

        return windows

    def optimize(
        self,
        data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        backtest_func: Callable,
        optimize_metric: str = "sharpe_ratio",
        timestamp_col: str = "timestamp",
        strategy_name: str = "Strategy",
    ) -> WalkForwardResult:
        """
        Run walk-forward optimization.

        Args:
            data: Full dataset with OHLCV data
            param_grid: Parameter grid to search (e.g., {"period": [10,14,20], "threshold": [30,40]})
            backtest_func: Function that takes (data, params) and returns metrics dict
            optimize_metric: Metric to optimize (default: "sharpe_ratio")
            timestamp_col: Name of timestamp column
            strategy_name: Name for reporting

        Returns:
            WalkForwardResult with all windows and aggregated metrics
        """
        windows_data = self._create_windows(data, timestamp_col)
        results = []
        all_params_used = []

        for idx, (is_data, oos_data, is_start, is_end, oos_start, oos_end) in enumerate(
            windows_data
        ):
            # === IN-SAMPLE OPTIMIZATION ===
            best_params = None
            best_is_metric = -np.inf
            best_is_result = None

            # Grid search on in-sample data
            param_combinations = self._generate_param_combinations(param_grid)

            for params in param_combinations:
                try:
                    is_result = backtest_func(is_data, params)
                    metric_value = is_result.get(optimize_metric, -np.inf)

                    # Check minimum trades
                    trades = is_result.get("total_trades", 0)
                    if trades < self.min_trades_per_window:
                        continue

                    if metric_value > best_is_metric:
                        best_is_metric = metric_value
                        best_params = params
                        best_is_result = is_result
                except Exception:
                    continue

            if best_params is None:
                # No valid parameters found, skip window
                continue

            all_params_used.append(best_params)

            # === OUT-OF-SAMPLE TESTING ===
            try:
                oos_result = backtest_func(oos_data, best_params)
            except Exception:
                continue

            # Safety check for None results
            if best_is_result is None or oos_result is None:
                continue

            # Calculate degradation
            is_sharpe = best_is_result.get("sharpe_ratio", 0)
            oos_sharpe = oos_result.get("sharpe_ratio", 0)
            is_return = best_is_result.get("total_return", 0)
            oos_return = oos_result.get("total_return", 0)

            sharpe_deg = (
                ((oos_sharpe - is_sharpe) / abs(is_sharpe) * 100)
                if is_sharpe != 0
                else 0
            )
            return_deg = (
                ((oos_return - is_return) / abs(is_return) * 100)
                if is_return != 0
                else 0
            )

            window_result = WalkForwardWindow(
                window_idx=idx,
                in_sample_start=is_start,
                in_sample_end=is_end,
                out_sample_start=oos_start,
                out_sample_end=oos_end,
                best_params=best_params,
                in_sample_sharpe=is_sharpe,
                in_sample_return=is_return,
                in_sample_trades=best_is_result.get("total_trades", 0),
                out_sample_sharpe=oos_sharpe,
                out_sample_return=oos_return,
                out_sample_trades=oos_result.get("total_trades", 0),
                sharpe_degradation=sharpe_deg,
                return_degradation=return_deg,
            )
            results.append(window_result)

        # === AGGREGATE RESULTS ===
        if not results:
            return WalkForwardResult(
                strategy_name=strategy_name,
                total_windows=0,
                windows=[],
            )

        # Calculate aggregated metrics
        avg_is_sharpe = float(np.mean([w.in_sample_sharpe for w in results]))
        avg_oos_sharpe = float(np.mean([w.out_sample_sharpe for w in results]))
        avg_sharpe_deg = float(np.mean([w.sharpe_degradation for w in results]))
        avg_is_return = float(np.mean([w.in_sample_return for w in results]))
        avg_oos_return = float(np.mean([w.out_sample_return for w in results]))
        avg_return_deg = float(np.mean([w.return_degradation for w in results]))
        total_is_trades = sum([w.in_sample_trades for w in results])
        total_oos_trades = sum([w.out_sample_trades for w in results])

        # OOS win rate (% of profitable OOS periods)
        oos_wins = sum([1 for w in results if w.out_sample_return > 0])
        oos_win_rate = oos_wins / len(results) * 100

        # Parameter stability (how much do optimal params vary?)
        param_stability = self._calculate_param_stability(all_params_used)

        return WalkForwardResult(
            strategy_name=strategy_name,
            total_windows=len(results),
            windows=results,
            avg_is_sharpe=avg_is_sharpe,
            avg_oos_sharpe=avg_oos_sharpe,
            avg_sharpe_degradation=avg_sharpe_deg,
            avg_is_return=avg_is_return,
            avg_oos_return=avg_oos_return,
            avg_return_degradation=avg_return_deg,
            total_is_trades=total_is_trades,
            total_oos_trades=total_oos_trades,
            oos_win_rate=oos_win_rate,
            parameter_stability=param_stability,
            combined_oos_sharpe=avg_oos_sharpe,
            combined_oos_return=sum([w.out_sample_return for w in results]),
        )

    def _generate_param_combinations(
        self, param_grid: Dict[str, List[Any]]
    ) -> List[Dict[str, Any]]:
        """Generate all combinations of parameters from grid."""
        import itertools

        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(itertools.product(*values))

        return [dict(zip(keys, combo)) for combo in combinations]

    def _calculate_param_stability(self, all_params: List[Dict[str, Any]]) -> float:
        """
        Calculate parameter stability across windows.

        Returns 0-100%, where 100% = same params in all windows.
        """
        if len(all_params) <= 1:
            return 100.0

        # For each parameter, calculate coefficient of variation
        param_variations: list[float] = []

        # Get all parameter names
        all_keys: set[str] = set()
        for p in all_params:
            all_keys.update(p.keys())

        for key in all_keys:
            values = [p.get(key, 0) for p in all_params if key in p]
            if len(values) > 1:
                # For numeric values
                try:
                    values = [float(v) for v in values]
                    mean_val = float(np.mean(values))
                    std_val = float(np.std(values))
                    if mean_val != 0:
                        cv = std_val / abs(mean_val)
                        param_variations.append(cv)
                except (ValueError, TypeError):
                    # Non-numeric, check if all same
                    unique = len(set(str(v) for v in values))
                    param_variations.append(0 if unique == 1 else 1)

        if not param_variations:
            return 100.0

        # Average CV, convert to stability (1 - CV, clamped to 0-100%)
        avg_cv = float(np.mean(param_variations))
        stability = max(0, min(100, (1 - avg_cv) * 100))

        return stability

    def print_report(self, result: WalkForwardResult) -> str:
        """Generate human-readable report."""
        lines = []
        lines.append("=" * 70)
        lines.append(f"WALK-FORWARD OPTIMIZATION REPORT: {result.strategy_name}")
        lines.append("=" * 70)
        lines.append(f"Mode: {self.mode}, Windows: {result.total_windows}")
        lines.append(
            f"IS Ratio: {self.in_sample_ratio:.0%}, Min Trades: {self.min_trades_per_window}"
        )
        lines.append("")

        # Summary table
        lines.append("-" * 70)
        lines.append(f"{'Metric':<30} {'In-Sample':>15} {'Out-of-Sample':>15}")
        lines.append("-" * 70)
        lines.append(
            f"{'Avg Sharpe Ratio':<30} {result.avg_is_sharpe:>15.2f} {result.avg_oos_sharpe:>15.2f}"
        )
        lines.append(
            f"{'Avg Return':<30} {result.avg_is_return:>14.1%} {result.avg_oos_return:>14.1%}"
        )
        lines.append(
            f"{'Total Trades':<30} {result.total_is_trades:>15} {result.total_oos_trades:>15}"
        )
        lines.append("-" * 70)

        # Robustness metrics
        lines.append("")
        lines.append("ROBUSTNESS METRICS:")
        lines.append(f"  Sharpe Degradation: {result.avg_sharpe_degradation:+.1f}%")
        lines.append(f"  Return Degradation: {result.avg_return_degradation:+.1f}%")
        lines.append(f"  OOS Win Rate: {result.oos_win_rate:.1f}%")
        lines.append(f"  Parameter Stability: {result.parameter_stability:.1f}%")

        # Per-window details
        lines.append("")
        lines.append("PER-WINDOW DETAILS:")
        lines.append("-" * 70)
        lines.append(
            f"{'#':<3} {'IS Sharpe':>10} {'OOS Sharpe':>11} {'IS Return':>10} {'OOS Return':>11} {'Degradation':>12}"
        )
        lines.append("-" * 70)

        for w in result.windows:
            lines.append(
                f"{w.window_idx:<3} {w.in_sample_sharpe:>10.2f} {w.out_sample_sharpe:>11.2f} "
                f"{w.in_sample_return:>9.1%} {w.out_sample_return:>10.1%} {w.sharpe_degradation:>+11.1f}%"
            )

        lines.append("-" * 70)

        # Verdict
        lines.append("")
        if result.avg_sharpe_degradation > -30 and result.oos_win_rate >= 60:
            lines.append(
                "✅ VERDICT: Strategy appears ROBUST (low degradation, high OOS win rate)"
            )
        elif result.avg_sharpe_degradation > -50 and result.oos_win_rate >= 50:
            lines.append(
                "⚠️ VERDICT: Strategy shows MODERATE robustness (some degradation)"
            )
        else:
            lines.append(
                "❌ VERDICT: Strategy may be OVERFIT (high degradation or low OOS win rate)"
            )

        lines.append("=" * 70)

        return "\n".join(lines)
