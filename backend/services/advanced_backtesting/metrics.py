"""
Custom Metrics Module

Provides extended metrics for backtesting:
- Risk-adjusted returns (Sharpe, Sortino, Calmar, etc.)
- Custom performance metrics
- Benchmark comparison
- Rolling metrics analysis
- Tail risk metrics

Usage:
    from backend.services.advanced_backtesting.metrics import (
        CustomMetrics,
        RiskAdjustedMetrics,
        BenchmarkComparison,
        RollingMetrics,
    )

    metrics = CustomMetrics(equity_curve, trades)
    report = metrics.calculate_all()
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RiskAdjustedMetrics:
    """Risk-adjusted performance metrics."""

    # Standard metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Extended metrics
    omega_ratio: float = 0.0
    information_ratio: float = 0.0
    treynor_ratio: float = 0.0

    # Tail risk
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0

    # Downside metrics
    downside_deviation: float = 0.0
    ulcer_index: float = 0.0
    pain_index: float = 0.0

    # Stability
    skewness: float = 0.0
    kurtosis: float = 0.0
    tail_ratio: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "standard": {
                "sharpe_ratio": round(self.sharpe_ratio, 3),
                "sortino_ratio": round(self.sortino_ratio, 3),
                "calmar_ratio": round(self.calmar_ratio, 3),
            },
            "extended": {
                "omega_ratio": round(self.omega_ratio, 3),
                "information_ratio": round(self.information_ratio, 3),
                "treynor_ratio": round(self.treynor_ratio, 3),
            },
            "tail_risk": {
                "var_95_pct": round(self.var_95 * 100, 2),
                "var_99_pct": round(self.var_99 * 100, 2),
                "cvar_95_pct": round(self.cvar_95 * 100, 2),
                "cvar_99_pct": round(self.cvar_99 * 100, 2),
            },
            "downside": {
                "downside_deviation": round(self.downside_deviation * 100, 2),
                "ulcer_index": round(self.ulcer_index * 100, 2),
                "pain_index": round(self.pain_index * 100, 2),
            },
            "stability": {
                "skewness": round(self.skewness, 3),
                "kurtosis": round(self.kurtosis, 3),
                "tail_ratio": round(self.tail_ratio, 3),
            },
        }


@dataclass
class BenchmarkComparison:
    """Benchmark comparison metrics."""

    # Benchmark info
    benchmark_name: str = ""
    benchmark_return: float = 0.0

    # Relative performance
    alpha: float = 0.0
    beta: float = 0.0
    correlation: float = 0.0
    tracking_error: float = 0.0

    # Outperformance
    excess_return: float = 0.0
    win_rate_vs_benchmark: float = 0.0
    up_capture: float = 0.0
    down_capture: float = 0.0

    # Time-based
    periods_outperforming: int = 0
    total_periods: int = 0
    longest_outperformance_streak: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "benchmark": {
                "name": self.benchmark_name,
                "return_pct": round(self.benchmark_return * 100, 2),
            },
            "relative": {
                "alpha": round(self.alpha * 100, 2),
                "beta": round(self.beta, 3),
                "correlation": round(self.correlation, 3),
                "tracking_error_pct": round(self.tracking_error * 100, 2),
            },
            "outperformance": {
                "excess_return_pct": round(self.excess_return * 100, 2),
                "win_rate_vs_benchmark_pct": round(self.win_rate_vs_benchmark * 100, 2),
                "up_capture_pct": round(self.up_capture * 100, 2),
                "down_capture_pct": round(self.down_capture * 100, 2),
            },
            "periods": {
                "outperforming": self.periods_outperforming,
                "total": self.total_periods,
                "longest_streak": self.longest_outperformance_streak,
            },
        }


@dataclass
class RollingMetrics:
    """Rolling window metrics."""

    window_size: int = 30

    # Rolling returns
    rolling_returns: list[float] = field(default_factory=list)
    rolling_volatility: list[float] = field(default_factory=list)
    rolling_sharpe: list[float] = field(default_factory=list)

    # Rolling drawdown
    rolling_max_drawdown: list[float] = field(default_factory=list)

    # Statistics
    sharpe_stability: float = 0.0  # Std of rolling sharpe
    return_consistency: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "window_size": self.window_size,
            "statistics": {
                "sharpe_stability": round(self.sharpe_stability, 3),
                "return_consistency": round(self.return_consistency, 3),
            },
            "current_values": {
                "rolling_return": round(self.rolling_returns[-1] * 100, 2)
                if self.rolling_returns
                else 0,
                "rolling_volatility": round(self.rolling_volatility[-1] * 100, 2)
                if self.rolling_volatility
                else 0,
                "rolling_sharpe": round(self.rolling_sharpe[-1], 3)
                if self.rolling_sharpe
                else 0,
            },
            # Truncate series for API response
            "series": {
                "returns": [round(r * 100, 2) for r in self.rolling_returns[-100:]],
                "volatility": [
                    round(v * 100, 2) for v in self.rolling_volatility[-100:]
                ],
                "sharpe": [round(s, 3) for s in self.rolling_sharpe[-100:]],
            },
        }


class CustomMetrics:
    """
    Custom metrics calculator.

    Provides comprehensive performance analysis including:
    - All standard risk-adjusted metrics
    - Custom metrics
    - Rolling analysis
    - Benchmark comparison
    """

    def __init__(
        self,
        equity_curve: list[float],
        trades: list[dict] | None = None,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 365,
    ):
        """
        Initialize metrics calculator.

        Args:
            equity_curve: List of portfolio values
            trades: List of trade dictionaries
            risk_free_rate: Annual risk-free rate
            periods_per_year: Number of periods per year (365 for daily)
        """
        self.equity_curve = np.array(equity_curve) if equity_curve else np.array([])
        self.trades = trades or []
        self.risk_free_rate = risk_free_rate
        self.periods_per_year = periods_per_year

        # Calculate returns
        self.returns = self._calculate_returns()

    def _calculate_returns(self) -> np.ndarray:
        """Calculate period returns."""
        if len(self.equity_curve) < 2:
            return np.array([])

        returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
        return returns

    def calculate_risk_adjusted(self) -> RiskAdjustedMetrics:
        """Calculate all risk-adjusted metrics."""
        metrics = RiskAdjustedMetrics()

        if len(self.returns) < 2:
            return metrics

        returns = self.returns
        rf_period = self.risk_free_rate / self.periods_per_year

        # Standard metrics
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        # Sharpe Ratio
        if std_return > 0:
            metrics.sharpe_ratio = (
                (mean_return - rf_period) / std_return * np.sqrt(self.periods_per_year)
            )

        # Sortino Ratio - TradingView formula: DD = sqrt(sum(min(0, Xi - T))^2 / N)
        downside_sq = np.minimum(0, returns - rf_period) ** 2
        downside_dev = np.sqrt(downside_sq.sum() / len(returns))
        metrics.downside_deviation = downside_dev
        if downside_dev > 0:
            metrics.sortino_ratio = (
                (mean_return - rf_period)
                / downside_dev
                * np.sqrt(self.periods_per_year)
            )

        # Calmar Ratio
        max_dd = self._calculate_max_drawdown()
        total_return = (self.equity_curve[-1] / self.equity_curve[0]) - 1
        annualized_return = (1 + total_return) ** (
            self.periods_per_year / len(returns)
        ) - 1
        if max_dd > 0:
            metrics.calmar_ratio = annualized_return / max_dd

        # Omega Ratio
        threshold = rf_period
        gains = np.sum(np.maximum(returns - threshold, 0))
        losses = np.sum(np.maximum(threshold - returns, 0))
        if losses > 0:
            metrics.omega_ratio = 1 + gains / losses

        # VaR and CVaR
        sorted_returns = np.sort(returns)
        n = len(sorted_returns)

        var_95_idx = int(0.05 * n)
        var_99_idx = int(0.01 * n)

        metrics.var_95 = (
            sorted_returns[var_95_idx] if var_95_idx < n else sorted_returns[0]
        )
        metrics.var_99 = (
            sorted_returns[var_99_idx] if var_99_idx < n else sorted_returns[0]
        )
        metrics.cvar_95 = np.mean(sorted_returns[: max(1, var_95_idx)])
        metrics.cvar_99 = np.mean(sorted_returns[: max(1, var_99_idx)])

        # Ulcer Index (root mean square of drawdowns)
        drawdowns = self._calculate_drawdown_series()
        metrics.ulcer_index = np.sqrt(np.mean(drawdowns**2))

        # Pain Index (mean drawdown)
        metrics.pain_index = np.mean(drawdowns)

        # Skewness and Kurtosis
        if std_return > 0:
            metrics.skewness = float(
                np.mean(((returns - mean_return) / std_return) ** 3)
            )
            metrics.kurtosis = float(
                np.mean(((returns - mean_return) / std_return) ** 4) - 3
            )

        # Tail Ratio (right tail / left tail)
        right_tail = np.percentile(returns, 95)
        left_tail = np.abs(np.percentile(returns, 5))
        if left_tail > 0:
            metrics.tail_ratio = right_tail / left_tail

        return metrics

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown."""
        if len(self.equity_curve) < 2:
            return 0.0

        running_max = np.maximum.accumulate(self.equity_curve)
        drawdowns = (running_max - self.equity_curve) / running_max
        return float(np.max(drawdowns))

    def _calculate_drawdown_series(self) -> np.ndarray:
        """Calculate drawdown series."""
        if len(self.equity_curve) < 2:
            return np.array([])

        running_max = np.maximum.accumulate(self.equity_curve)
        drawdowns = (running_max - self.equity_curve) / running_max
        return drawdowns

    def compare_to_benchmark(
        self,
        benchmark_returns: list[float],
        benchmark_name: str = "Benchmark",
    ) -> BenchmarkComparison:
        """Compare strategy to benchmark."""
        comparison = BenchmarkComparison(benchmark_name=benchmark_name)

        if len(self.returns) < 2 or len(benchmark_returns) < 2:
            return comparison

        # Align lengths
        min_len = min(len(self.returns), len(benchmark_returns))
        strategy_returns = self.returns[:min_len]
        bench_returns = np.array(benchmark_returns[:min_len])

        # Basic metrics
        comparison.benchmark_return = float(np.prod(1 + bench_returns) - 1)
        strategy_return = float(np.prod(1 + strategy_returns) - 1)
        comparison.excess_return = strategy_return - comparison.benchmark_return

        # Beta and Alpha
        covariance = np.cov(strategy_returns, bench_returns)
        if covariance.shape == (2, 2):
            variance = covariance[1, 1]
            if variance > 0:
                comparison.beta = covariance[0, 1] / variance

        rf = self.risk_free_rate / self.periods_per_year
        comparison.alpha = (
            np.mean(strategy_returns)
            - rf
            - comparison.beta * (np.mean(bench_returns) - rf)
        )

        # Correlation
        if np.std(strategy_returns) > 0 and np.std(bench_returns) > 0:
            comparison.correlation = float(
                np.corrcoef(strategy_returns, bench_returns)[0, 1]
            )

        # Tracking Error
        tracking_diff = strategy_returns - bench_returns
        comparison.tracking_error = float(
            np.std(tracking_diff) * np.sqrt(self.periods_per_year)
        )

        # Information Ratio
        if comparison.tracking_error > 0:
            comparison.information_ratio = (
                comparison.excess_return / comparison.tracking_error
            )

        # Win rate vs benchmark
        outperforming = strategy_returns > bench_returns
        comparison.win_rate_vs_benchmark = float(np.mean(outperforming))
        comparison.periods_outperforming = int(np.sum(outperforming))
        comparison.total_periods = len(outperforming)

        # Up/Down capture
        up_periods = bench_returns > 0
        down_periods = bench_returns < 0

        if np.sum(up_periods) > 0:
            up_strategy = np.mean(strategy_returns[up_periods])
            up_bench = np.mean(bench_returns[up_periods])
            if up_bench > 0:
                comparison.up_capture = up_strategy / up_bench

        if np.sum(down_periods) > 0:
            down_strategy = np.mean(strategy_returns[down_periods])
            down_bench = np.mean(bench_returns[down_periods])
            if down_bench < 0:
                comparison.down_capture = down_strategy / down_bench

        # Longest outperformance streak
        streak = 0
        max_streak = 0
        for is_outperforming in outperforming:
            if is_outperforming:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        comparison.longest_outperformance_streak = max_streak

        return comparison

    def calculate_rolling(self, window: int = 30) -> RollingMetrics:
        """Calculate rolling metrics."""
        rolling = RollingMetrics(window_size=window)

        if len(self.returns) < window:
            return rolling

        returns = self.returns
        n = len(returns)

        for i in range(window, n + 1):
            window_returns = returns[i - window : i]

            # Rolling return
            rolling_ret = np.prod(1 + window_returns) - 1
            rolling.rolling_returns.append(float(rolling_ret))

            # Rolling volatility
            rolling_vol = np.std(window_returns) * np.sqrt(self.periods_per_year)
            rolling.rolling_volatility.append(float(rolling_vol))

            # Rolling Sharpe
            mean_ret = np.mean(window_returns)
            std_ret = np.std(window_returns)
            sharpe = mean_ret / std_ret * np.sqrt(self.periods_per_year) if std_ret > 0 else 0.0
            rolling.rolling_sharpe.append(float(sharpe))

        # Calculate stability metrics
        if rolling.rolling_sharpe:
            rolling.sharpe_stability = 1 / (1 + np.std(rolling.rolling_sharpe))

        if rolling.rolling_returns:
            positive_periods = sum(1 for r in rolling.rolling_returns if r > 0)
            rolling.return_consistency = positive_periods / len(rolling.rolling_returns)

        return rolling

    def calculate_trade_metrics(self) -> dict[str, Any]:
        """Calculate trade-specific metrics."""
        if not self.trades:
            return {}

        pnls = [t.get("pnl", 0) for t in self.trades]
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p < 0]

        metrics = {
            "total_trades": len(self.trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": len(winning) / len(pnls) if pnls else 0,
            "avg_win": np.mean(winning) if winning else 0,
            "avg_loss": np.mean(losing) if losing else 0,
            "largest_win": max(winning) if winning else 0,
            "largest_loss": min(losing) if losing else 0,
        }

        # Profit factor
        gross_profit = sum(winning)
        gross_loss = abs(sum(losing))
        metrics["profit_factor"] = (
            gross_profit / gross_loss if gross_loss > 0 else float("inf")
        )

        # Expectancy
        metrics["expectancy"] = metrics["win_rate"] * metrics["avg_win"] - (
            1 - metrics["win_rate"]
        ) * abs(metrics["avg_loss"])

        # Kelly Criterion
        if metrics["avg_loss"] != 0:
            win_loss_ratio = metrics["avg_win"] / abs(metrics["avg_loss"])
            metrics["kelly_fraction"] = (
                metrics["win_rate"] - (1 - metrics["win_rate"]) / win_loss_ratio
            )
        else:
            metrics["kelly_fraction"] = 0

        return metrics

    def calculate_all(self) -> dict[str, Any]:
        """Calculate all metrics."""
        return {
            "risk_adjusted": self.calculate_risk_adjusted().to_dict(),
            "rolling": self.calculate_rolling().to_dict(),
            "trade_metrics": self.calculate_trade_metrics(),
            "calculated_at": datetime.now(UTC).isoformat(),
        }


def calculate_metrics(
    equity_curve: list[float],
    trades: list[dict] | None = None,
    benchmark_returns: list[float] | None = None,
    benchmark_name: str = "Benchmark",
) -> dict[str, Any]:
    """
    Convenience function to calculate all metrics.

    Args:
        equity_curve: Portfolio value series
        trades: List of trades
        benchmark_returns: Benchmark return series
        benchmark_name: Name of benchmark

    Returns:
        Complete metrics dictionary
    """
    calculator = CustomMetrics(equity_curve, trades)
    result = calculator.calculate_all()

    if benchmark_returns:
        comparison = calculator.compare_to_benchmark(benchmark_returns, benchmark_name)
        result["benchmark_comparison"] = comparison.to_dict()

    return result
