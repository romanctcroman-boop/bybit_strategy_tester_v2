"""
🚀 Extended Risk Metrics Module
Implements Sortino, Calmar, Omega and other advanced risk metrics
Based on world best practices 2024-2026
"""

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class ExtendedMetricsResult:
    """Extended metrics result container"""

    # Standard metrics
    sharpe_ratio: float
    max_drawdown: float
    total_return: float

    # Extended metrics (NEW)
    sortino_ratio: float
    calmar_ratio: float
    omega_ratio: float
    profit_factor: float
    recovery_factor: float
    ulcer_index: float
    tail_ratio: float
    information_ratio: float | None = None

    # Detailed stats
    downside_deviation: float = 0.0
    upside_potential_ratio: float = 0.0
    gain_to_pain_ratio: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "sortino_ratio": round(self.sortino_ratio, 4),
            "calmar_ratio": round(self.calmar_ratio, 4),
            "omega_ratio": round(self.omega_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "total_return": round(self.total_return, 4),
            "profit_factor": round(self.profit_factor, 4),
            "recovery_factor": round(self.recovery_factor, 4),
            "ulcer_index": round(self.ulcer_index, 4),
            "tail_ratio": round(self.tail_ratio, 4),
            "downside_deviation": round(self.downside_deviation, 6),
            "upside_potential_ratio": round(self.upside_potential_ratio, 4),
            "gain_to_pain_ratio": round(self.gain_to_pain_ratio, 4),
        }


class ExtendedMetricsCalculator:
    """
    Extended risk metrics calculator implementing industry best practices.

    Metrics included:
    - Sortino Ratio: Downside risk-adjusted return
    - Calmar Ratio: CAGR / Max Drawdown
    - Omega Ratio: Probability-weighted gains vs losses
    - Profit Factor: Gross profit / Gross loss
    - Recovery Factor: Net profit / Max drawdown
    - Ulcer Index: Measures depth and duration of drawdowns
    - Tail Ratio: Right tail / Left tail at 95th percentile
    """

    def __init__(
        self,
        risk_free_rate: float = 0.02,
        periods_per_year: int = 8760,  # Hourly data
        target_return: float = 0.0,
    ):
        """
        Initialize calculator.

        Args:
            risk_free_rate: Annual risk-free rate (default 2%)
            periods_per_year: Number of periods per year (8760 for hourly)
            target_return: Minimum acceptable return for Sortino (default 0)
        """
        self.risk_free_rate = risk_free_rate
        self.periods_per_year = periods_per_year
        self.target_return = target_return
        self.period_rfr = risk_free_rate / periods_per_year

    def calculate_all(
        self,
        equity_curve: np.ndarray,
        trades: list | None = None,
        benchmark_returns: np.ndarray | None = None,
    ) -> ExtendedMetricsResult:
        """
        Calculate all extended metrics.

        Args:
            equity_curve: Array of equity values over time
            trades: Optional list of trade objects with pnl attribute
            benchmark_returns: Optional benchmark returns for Information Ratio

        Returns:
            ExtendedMetricsResult with all calculated metrics
        """
        if len(equity_curve) < 2:
            return self._empty_result()

        # Calculate returns
        returns = np.diff(equity_curve) / equity_curve[:-1]
        returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)

        # Basic metrics
        sharpe = self.calculate_sharpe(returns)
        max_dd, max_dd_pct = self.calculate_max_drawdown(equity_curve)
        total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]

        # Extended metrics
        sortino = self.calculate_sortino(returns)
        calmar = self.calculate_calmar(equity_curve)
        omega = self.calculate_omega(returns)
        ulcer = self.calculate_ulcer_index(equity_curve)
        tail = self.calculate_tail_ratio(returns)
        downside_dev = self.calculate_downside_deviation(returns)
        upr = self.calculate_upside_potential_ratio(returns)

        # Trade-based metrics
        profit_factor = 1.0
        recovery_factor = 0.0
        gain_to_pain = 0.0

        if trades:
            profit_factor = self.calculate_profit_factor(trades)
            recovery_factor = self.calculate_recovery_factor(equity_curve, trades)
            gain_to_pain = self.calculate_gain_to_pain(returns)

        # Information ratio (if benchmark provided)
        info_ratio = None
        if benchmark_returns is not None and len(benchmark_returns) == len(returns):
            info_ratio = self.calculate_information_ratio(returns, benchmark_returns)

        return ExtendedMetricsResult(
            sharpe_ratio=sharpe,
            max_drawdown=max_dd_pct,
            total_return=total_return,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            omega_ratio=omega,
            profit_factor=profit_factor,
            recovery_factor=recovery_factor,
            ulcer_index=ulcer,
            tail_ratio=tail,
            downside_deviation=downside_dev,
            upside_potential_ratio=upr,
            gain_to_pain_ratio=gain_to_pain,
            information_ratio=info_ratio,
        )

    def calculate_sharpe(self, returns: np.ndarray) -> float:
        """
        Calculate annualized Sharpe Ratio.

        Formula: (mean_return - rfr) / std * sqrt(periods_per_year)
        """
        if len(returns) < 2:
            return 0.0

        mean_ret = np.mean(returns)
        std_ret = np.std(returns, ddof=1)

        if std_ret < 1e-10:
            return 0.0

        return (mean_ret - self.period_rfr) / std_ret * np.sqrt(self.periods_per_year)

    def calculate_sortino(self, returns: np.ndarray) -> float:
        """
        Calculate Sortino Ratio - focuses only on downside risk.

        Formula: (mean_return - target) / downside_deviation * sqrt(periods_per_year)

        "Focuses solely on downside risk, particularly useful for
        investors concerned with avoiding losses" - Schwab
        """
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - self.target_return
        downside_returns = np.minimum(excess_returns, 0)

        # Only consider negative returns for downside deviation
        negative_returns = downside_returns[downside_returns < 0]

        if len(negative_returns) < 2:
            # No downside - infinite Sortino (return max practical value)
            return 10.0 if np.mean(returns) > self.target_return else 0.0

        downside_std = np.std(negative_returns, ddof=1)

        if downside_std < 1e-10:
            return 10.0 if np.mean(returns) > self.target_return else 0.0

        mean_excess = np.mean(returns) - self.target_return
        return mean_excess / downside_std * np.sqrt(self.periods_per_year)

    def calculate_calmar(self, equity_curve: np.ndarray) -> float:
        """
        Calculate Calmar Ratio - CAGR / Max Drawdown.

        "Comparing CAGR to Maximum Drawdown - valuable for strategies
        where minimizing deep losses is critical" - Corporate Finance Institute
        """
        if len(equity_curve) < 2:
            return 0.0

        # Calculate CAGR
        total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]
        n_periods = len(equity_curve)

        if n_periods <= 1:
            return 0.0

        # Annualized return
        cagr = (1 + total_return) ** (self.periods_per_year / n_periods) - 1

        # Max drawdown
        _, max_dd = self.calculate_max_drawdown(equity_curve)

        if max_dd < 1e-10:
            return 10.0 if cagr > 0 else 0.0

        return cagr / max_dd

    def calculate_omega(self, returns: np.ndarray, threshold: float = 0.0) -> float:
        """
        Calculate Omega Ratio - probability-weighted gains vs losses.

        "Considers the entire distribution of returns - addresses the
        shortcomings of Sharpe Ratio for non-normal distributions" - Wikipedia

        Formula: Σ(gains above threshold) / Σ(losses below threshold)
        """
        if len(returns) < 2:
            return 1.0

        gains = np.sum(np.maximum(returns - threshold, 0))
        losses = np.abs(np.sum(np.minimum(returns - threshold, 0)))

        if losses < 1e-10:
            return 10.0 if gains > 0 else 1.0

        return gains / losses

    def calculate_max_drawdown(self, equity_curve: np.ndarray) -> tuple:
        """
        Calculate maximum drawdown.

        Returns:
            (max_drawdown_value, max_drawdown_percentage)
        """
        if len(equity_curve) < 2:
            return 0.0, 0.0

        peak = np.maximum.accumulate(equity_curve)
        drawdown = peak - equity_curve
        drawdown_pct = drawdown / peak

        max_dd_idx = np.argmax(drawdown)
        max_dd_value = drawdown[max_dd_idx]
        max_dd_pct = drawdown_pct[max_dd_idx]

        return max_dd_value, max_dd_pct

    def calculate_profit_factor(self, trades: list) -> float:
        """
        Calculate Profit Factor - Gross Profit / Gross Loss.

        > 1.0 = profitable, > 1.5 = good, > 2.0 = excellent
        """
        if not trades:
            return 1.0

        pnls = [getattr(t, "pnl", t) if hasattr(t, "pnl") else t for t in trades]
        pnls = np.array(pnls)

        gross_profit = np.sum(pnls[pnls > 0])
        gross_loss = np.abs(np.sum(pnls[pnls < 0]))

        if gross_loss < 1e-10:
            return 10.0 if gross_profit > 0 else 1.0

        return gross_profit / gross_loss

    def calculate_recovery_factor(
        self, equity_curve: np.ndarray, trades: list
    ) -> float:
        """
        Calculate Recovery Factor - Net Profit / Max Drawdown.

        Measures how well the strategy recovers from drawdowns.
        """
        if len(equity_curve) < 2:
            return 0.0

        net_profit = equity_curve[-1] - equity_curve[0]
        max_dd, _ = self.calculate_max_drawdown(equity_curve)

        if max_dd < 1e-10:
            return 10.0 if net_profit > 0 else 0.0

        return net_profit / max_dd

    def calculate_ulcer_index(self, equity_curve: np.ndarray) -> float:
        """
        Calculate Ulcer Index - measures depth and duration of drawdowns.

        Lower values indicate less severe drawdowns.
        Formula: sqrt(mean(drawdown_pct^2))
        """
        if len(equity_curve) < 2:
            return 0.0

        peak = np.maximum.accumulate(equity_curve)
        drawdown_pct = (peak - equity_curve) / peak * 100  # As percentage

        return np.sqrt(np.mean(drawdown_pct**2))

    def calculate_tail_ratio(self, returns: np.ndarray) -> float:
        """
        Calculate Tail Ratio - right tail / left tail at 95th percentile.

        > 1.0 = positive skew (good), < 1.0 = negative skew (bad)
        """
        if len(returns) < 20:
            return 1.0

        right_tail = np.percentile(returns, 95)
        left_tail = np.abs(np.percentile(returns, 5))

        if left_tail < 1e-10:
            return 10.0 if right_tail > 0 else 1.0

        return right_tail / left_tail

    def calculate_downside_deviation(self, returns: np.ndarray) -> float:
        """
        Calculate downside deviation (semi-deviation below target).
        """
        if len(returns) < 2:
            return 0.0

        downside = returns[returns < self.target_return]

        if len(downside) < 2:
            return 0.0

        return np.std(downside, ddof=1)

    def calculate_upside_potential_ratio(self, returns: np.ndarray) -> float:
        """
        Calculate Upside Potential Ratio.

        Formula: upside_potential / downside_risk
        """
        if len(returns) < 2:
            return 1.0

        upside = returns[returns > self.target_return]
        downside = returns[returns < self.target_return]

        if len(upside) == 0:
            return 0.0

        upside_potential = np.mean(upside - self.target_return)

        if len(downside) < 2:
            return 10.0

        downside_risk = np.std(downside, ddof=1)

        if downside_risk < 1e-10:
            return 10.0

        return upside_potential / downside_risk

    def calculate_gain_to_pain(self, returns: np.ndarray) -> float:
        """
        Calculate Gain-to-Pain Ratio.

        Formula: sum(returns) / abs(sum(negative_returns))
        """
        if len(returns) < 2:
            return 0.0

        total_return = np.sum(returns)
        pain = np.abs(np.sum(returns[returns < 0]))

        if pain < 1e-10:
            return 10.0 if total_return > 0 else 0.0

        return total_return / pain

    def calculate_information_ratio(
        self, returns: np.ndarray, benchmark_returns: np.ndarray
    ) -> float:
        """
        Calculate Information Ratio - excess return / tracking error.

        Measures risk-adjusted return relative to a benchmark.
        """
        if len(returns) < 2 or len(benchmark_returns) != len(returns):
            return 0.0

        excess_returns = returns - benchmark_returns
        tracking_error = np.std(excess_returns, ddof=1)

        if tracking_error < 1e-10:
            return 0.0

        return np.mean(excess_returns) / tracking_error * np.sqrt(self.periods_per_year)

    def _empty_result(self) -> ExtendedMetricsResult:
        """Return empty metrics result"""
        return ExtendedMetricsResult(
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            total_return=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            omega_ratio=1.0,
            profit_factor=1.0,
            recovery_factor=0.0,
            ulcer_index=0.0,
            tail_ratio=1.0,
        )


# Convenience function
def calculate_extended_metrics(
    equity_curve: np.ndarray,
    trades: list | None = None,
    risk_free_rate: float = 0.02,
    periods_per_year: int = 8760,
) -> ExtendedMetricsResult:
    """
    Convenience function to calculate all extended metrics.

    Args:
        equity_curve: Array of equity values
        trades: Optional list of trades
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year

    Returns:
        ExtendedMetricsResult with all metrics
    """
    calculator = ExtendedMetricsCalculator(
        risk_free_rate=risk_free_rate, periods_per_year=periods_per_year
    )
    return calculator.calculate_all(equity_curve, trades)
