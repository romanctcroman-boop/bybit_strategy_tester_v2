"""
Centralized Metrics Calculator

Single source of truth for all backtesting metrics.
All metric calculations MUST use this module.

Usage:
    from backend.core.metrics_calculator import MetricsCalculator, calculate_sharpe

    # Полный расчёт всех метрик
    metrics = MetricsCalculator.calculate_all(trades, equity_curve, initial_capital, ...)

    # Отдельные метрики
    sharpe = calculate_sharpe(returns, frequency='hourly')
    win_rate = calculate_win_rate(winning_trades, total_trades)

TradingView Compliance:
- Sharpe Ratio: uses MONTHLY returns (as per TV docs)
- Win Rate: percentage (0-100)
- Profit Factor: gross_profit / gross_loss
- Max Drawdown: peak-to-trough in percentage
"""

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np

try:
    from numba import jit

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

    def jit(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


# =============================================================================
# SAFE DIVISION UTILITY
# =============================================================================


def safe_divide(
    numerator: float,
    denominator: float,
    default: float = 0.0,
    epsilon: float = 1e-10,
) -> float:
    """
    Safe division that handles zero and near-zero denominators.

    Args:
        numerator: The dividend
        denominator: The divisor
        default: Value to return if denominator is zero/near-zero
        epsilon: Threshold for considering denominator as zero

    Returns:
        Result of division or default if denominator is too small

    Examples:
        >>> safe_divide(10, 2)
        5.0
        >>> safe_divide(10, 0)
        0.0
        >>> safe_divide(10, 0, default=float('inf'))
        inf
    """
    if abs(denominator) < epsilon:
        return default
    return numerator / denominator


class TimeFrequency(str, Enum):
    """Data frequency for annualization"""

    MINUTELY = "minutely"  # 1 minute bars
    HOURLY = "hourly"  # 1 hour bars (default for crypto)
    DAILY = "daily"  # 1 day bars
    WEEKLY = "weekly"  # 1 week bars
    MONTHLY = "monthly"  # 1 month bars


# Annualization factors (periods per year)
ANNUALIZATION_FACTORS = {
    TimeFrequency.MINUTELY: 525600,  # 365.25 * 24 * 60
    TimeFrequency.HOURLY: 8766,  # 365.25 * 24
    TimeFrequency.DAILY: 365.25,
    TimeFrequency.WEEKLY: 52.18,
    TimeFrequency.MONTHLY: 12,
}


@dataclass
class TradeMetrics:
    """Metrics for a single trade or group of trades"""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0

    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0
    total_commission: float = 0.0

    win_rate: float = 0.0
    profit_factor: float = 0.0

    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade: float = 0.0

    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    avg_trade_pct: float = 0.0

    largest_win: float = 0.0
    largest_loss: float = 0.0
    largest_win_pct: float = 0.0
    largest_loss_pct: float = 0.0

    payoff_ratio: float = 0.0

    max_consec_wins: int = 0
    max_consec_losses: int = 0

    avg_bars_held: float = 0.0
    avg_win_bars: float = 0.0
    avg_loss_bars: float = 0.0


@dataclass
class RiskMetrics:
    """Risk-adjusted performance metrics"""

    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    max_drawdown: float = 0.0
    max_drawdown_value: float = 0.0
    avg_drawdown: float = 0.0
    max_drawdown_duration_bars: int = 0
    avg_drawdown_duration_bars: float = 0.0

    max_runup: float = 0.0
    max_runup_value: float = 0.0
    avg_runup: float = 0.0
    avg_runup_duration_bars: float = 0.0

    recovery_factor: float = 0.0
    expectancy: float = 0.0
    expectancy_ratio: float = 0.0

    volatility: float = 0.0

    cagr: float = 0.0

    margin_efficiency: float = 0.0
    ulcer_index: float = 0.0
    stability: float = 0.0
    sqn: float = 0.0


@dataclass
class LongShortMetrics:
    """Separate metrics for long and short trades"""

    # Long
    long_trades: int = 0
    long_winning: int = 0
    long_losing: int = 0
    long_breakeven: int = 0

    long_gross_profit: float = 0.0
    long_gross_loss: float = 0.0
    long_net_profit: float = 0.0
    long_commission: float = 0.0

    long_win_rate: float = 0.0
    long_profit_factor: float = 0.0
    long_avg_win: float = 0.0
    long_avg_loss: float = 0.0
    long_avg_trade: float = 0.0
    long_avg_win_pct: float = 0.0
    long_avg_loss_pct: float = 0.0
    long_avg_trade_pct: float = 0.0
    long_largest_win: float = 0.0
    long_largest_loss: float = 0.0
    long_largest_win_pct: float = 0.0
    long_largest_loss_pct: float = 0.0
    long_payoff_ratio: float = 0.0

    long_max_consec_wins: int = 0
    long_max_consec_losses: int = 0
    long_avg_bars: float = 0.0
    long_avg_win_bars: float = 0.0
    long_avg_loss_bars: float = 0.0
    long_cagr: float = 0.0

    # Short
    short_trades: int = 0
    short_winning: int = 0
    short_losing: int = 0
    short_breakeven: int = 0

    short_gross_profit: float = 0.0
    short_gross_loss: float = 0.0
    short_net_profit: float = 0.0
    short_commission: float = 0.0

    short_win_rate: float = 0.0
    short_profit_factor: float = 0.0
    short_avg_win: float = 0.0
    short_avg_loss: float = 0.0
    short_avg_trade: float = 0.0
    short_avg_win_pct: float = 0.0
    short_avg_loss_pct: float = 0.0
    short_avg_trade_pct: float = 0.0
    short_largest_win: float = 0.0
    short_largest_loss: float = 0.0
    short_largest_win_pct: float = 0.0
    short_largest_loss_pct: float = 0.0
    short_payoff_ratio: float = 0.0

    short_max_consec_wins: int = 0
    short_max_consec_losses: int = 0
    short_avg_bars: float = 0.0
    short_avg_win_bars: float = 0.0
    short_avg_loss_bars: float = 0.0
    short_cagr: float = 0.0


# =============================================================================
# PURE CALCULATION FUNCTIONS (can be used standalone)
# =============================================================================


def calculate_win_rate(winning_trades: int, total_trades: int) -> float:
    """
    Calculate win rate as percentage.

    Formula: (winning_trades / total_trades) * 100

    Returns: float in range [0, 100]
    """
    if total_trades <= 0:
        return 0.0
    return (winning_trades / total_trades) * 100.0


def calculate_profit_factor(gross_profit: float, gross_loss: float) -> float:
    """
    Calculate profit factor.

    Formula: gross_profit / gross_loss

    Returns: float, capped at 100.0 for practical display (TradingView limit)
    """
    if gross_loss <= 0:
        return 100.0 if gross_profit > 0 else 0.0
    return min(100.0, gross_profit / gross_loss)


def calculate_margin_efficiency(net_profit: float, avg_margin_used: float) -> float:
    """
    Calculate Efficiency Ratio (Margin Efficiency).

    Formula: Net Profit / (Avg Margin Used * 0.7) * 100

    Args:
        net_profit: Total net profit
        avg_margin_used: Average margin used in trades

    Returns: Efficiency as percentage
    """
    if avg_margin_used <= 0:
        return 0.0
    # The 0.7 factor is a TradingView standard constant for margin calculation
    return (net_profit / (avg_margin_used * 0.7)) * 100.0


def calculate_ulcer_index(drawdowns: np.ndarray) -> float:
    """
    Calculate Ulcer Index.

    Formula: Sqrt(Mean(Drawdown^2)) * 100

    Args:
        drawdowns: Array of drawdown values as fractions (e.g. 0.1 = 10% drawdown,
                   NOT already multiplied by 100)

    Returns:
        Ulcer Index as percentage (already multiplied by 100).
        Callers should NOT multiply the result again.

    Example:
        >>> calculate_ulcer_index(np.array([0.05, 0.10, 0.03]))
        6.48...  # Already a percentage
    """
    if len(drawdowns) == 0:
        return 0.0

    # Ensure we use the squared sum mean
    sum_sq = np.sum(np.square(drawdowns))
    mean_sq = sum_sq / len(drawdowns)
    return np.sqrt(mean_sq) * 100.0


def calculate_sharpe(
    returns: np.ndarray,
    frequency: TimeFrequency = TimeFrequency.HOURLY,
    risk_free_rate: float = 0.02,  # 2% annual
    tradingview_mode: bool = True,
) -> float:
    """
    Calculate Sharpe Ratio.

    TradingView Formula (uses MONTHLY returns):
        Sharpe = (Mean_Monthly_Return - RFR_Monthly) / Std_Monthly_Return

    SPECIAL CASE: If returns array reflects trade-by-trade returns (not periodic),
    TradingView uses a non-annualized formula: Mean / Std.

    Args:
        returns: Array of period returns
        frequency: Data frequency
        risk_free_rate: Annual risk-free rate
        tradingview_mode: If True, uses specific TV logic for short series

    Returns: Annualized (or raw) Sharpe Ratio
    """
    if len(returns) < 2:
        return 0.0

    returns = np.asarray(returns)
    returns = returns[np.isfinite(returns)]

    if len(returns) < 2:
        return 0.0

    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1)  # Sample std

    if std_return <= 1e-10:
        return 0.0

    # If simple trade returns (not periodic time series), strict TV mode might not annualize
    # But for periodic series (Hourly/Daily), we should annualize.

    periods_per_year = ANNUALIZATION_FACTORS.get(frequency, 365.25)

    if tradingview_mode and frequency == TimeFrequency.HOURLY and len(returns) < 24:
        # For very short backtests, don't annualize excessively or return 0
        # Fallback to simple mean/std
        return float(mean_return / std_return)

    # Convert annual RFR to period RFR
    period_rfr = risk_free_rate / periods_per_year

    # Sharpe = (mean - rfr) / std * sqrt(periods)
    sharpe = (mean_return - period_rfr) / std_return * np.sqrt(periods_per_year)

    # Sanity check
    return float(np.clip(sharpe, -100, 100))


def calculate_sortino(
    returns: np.ndarray,
    frequency: TimeFrequency = TimeFrequency.HOURLY,
    risk_free_rate: float = 0.02,
    mar: float = 0.0,  # Minimum Acceptable Return
) -> float:
    """
    Calculate Sortino Ratio (uses downside deviation).

    Formula: (Mean_Return - MAR) / Downside_Deviation * sqrt(periods)
    """
    if len(returns) < 2:
        return 0.0

    returns = np.asarray(returns)
    returns = returns[np.isfinite(returns)]

    if len(returns) < 2:
        return 0.0

    mean_return = np.mean(returns)

    # TradingView considers 0 as the threshold usually, effectively MAR=0

    # TradingView Sortino Denominator: sqrt( sum(min(0, r)^2) / N )
    # This is different from standard std dev of negative returns!
    # They divide by TOTAL N, not count of negative returns.

    # Let's implement rigorous TradingView formula:
    negative_returns = np.minimum(0, returns - mar)
    downside_variance = np.sum(np.square(negative_returns)) / len(returns)
    downside_dev = np.sqrt(downside_variance)

    if downside_dev <= 1e-10:
        # No downside deviation = perfect one-sided returns.
        # Return clip-cap (100) so this strategy ranks above all finite Sortino values.
        return 100.0 if mean_return > mar else 0.0

    periods_per_year = ANNUALIZATION_FACTORS.get(frequency, 365.25)

    # TV typically annualizes
    sortino = (mean_return - mar) / downside_dev * np.sqrt(periods_per_year)

    return float(np.clip(sortino, -100, 100))


def calculate_calmar(
    total_return_pct: float,
    max_drawdown_pct: float,
    years: float = 1.0,
) -> float:
    """
    Calculate Calmar Ratio.
    Formula: CAGR / |Max_Drawdown|

    Uses compound annual growth rate (CAGR) for multi-year periods.
    For single year (years <= 1), total_return_pct is used directly as CAGR.
    """
    if abs(max_drawdown_pct) <= 1.0:
        return 10.0 if total_return_pct > 0 else 0.0

    # Use compound CAGR for multi-year periods
    if years > 1.0:
        # CAGR = ((1 + total_return_fraction) ^ (1/years) - 1) * 100
        total_return_frac = total_return_pct / 100
        cagr = -100.0 if total_return_frac <= -1.0 else (pow(1 + total_return_frac, 1 / years) - 1) * 100
    else:
        cagr = total_return_pct

    return float(np.clip(cagr / abs(max_drawdown_pct), -100, 100))


def calculate_max_drawdown(equity: np.ndarray) -> tuple[float, float, int]:
    """
    Calculate Maximum Drawdown.

    Returns: (max_dd_pct, max_dd_value, max_dd_duration_bars)
    """
    if len(equity) < 2:
        return 0.0, 0.0, 0

    equity = np.asarray(equity)

    # Running maximum
    peak = np.maximum.accumulate(equity)

    # Drawdown at each point (as fraction)
    # Protect against div by zero if peak is 0 (bankruptcy)
    drawdown = (peak - equity) / np.where(peak > 0, peak, 1)

    max_dd_fraction = np.max(drawdown)
    max_dd_pct = float(max_dd_fraction) * 100  # As percentage

    # Max DD value
    # We find the index of max percentage drawdown
    max_dd_idx = np.argmax(drawdown)
    # Value is Peak - Equity at that point
    max_dd_value = float(peak[max_dd_idx] - equity[max_dd_idx])

    # Duration
    # Find start of drawdown (last new high)
    peak_idx = max_dd_idx
    while peak_idx > 0 and equity[peak_idx] < peak[peak_idx]:
        peak_idx -= 1

    duration = max_dd_idx - peak_idx

    return max_dd_pct, max_dd_value, int(duration)


def calculate_cagr(
    initial_capital: float,
    final_capital: float,
    years: float,
) -> float:
    """
    Calculate Compound Annual Growth Rate.

    Formula: (Final / Initial)^(1/Years) - 1

    For periods < 30 days (0.082 years), use simple annualized return
    to avoid extreme CAGR values.

    Returns: CAGR as percentage
    """
    if years <= 0 or initial_capital <= 0:
        return 0.0

    if final_capital <= 0:
        return -100.0  # Total loss

    try:
        ratio = final_capital / initial_capital

        # For very short periods (< 30 days), use simple annualized return
        # This avoids extreme compounding effects
        if years < 0.082:  # ~30 days
            simple_return = (ratio - 1) * 100  # As percentage
            # Annualize using simple scaling (not compound)
            annualized = simple_return * (1 / years) if years > 0 else 0
            return float(np.clip(annualized, -999, 999999))

        if ratio > 1e10:  # Overflow protection
            return 999999.0

        cagr = (pow(ratio, 1 / years) - 1) * 100
        return float(np.clip(cagr, -100, 999999))
    except (OverflowError, ValueError):
        return 999999.0 if final_capital > initial_capital else -100.0


def calculate_expectancy(
    win_rate: float,  # As fraction (0-1)
    avg_win: float,
    avg_loss: float,
) -> tuple[float, float]:
    """
    Calculate Mathematical Expectancy.

    Formula: Expectancy = (Win% * Avg_Win) - (Loss% * |Avg_Loss|)

    Returns: (expectancy, expectancy_ratio)
    """
    if avg_loss == 0:
        return (avg_win * win_rate, 0.0)

    loss_rate = 1 - win_rate
    expectancy = (win_rate * avg_win) - (loss_rate * abs(avg_loss))
    expectancy_ratio = expectancy / abs(avg_loss) if avg_loss != 0 else 0.0

    return (expectancy, expectancy_ratio)


def calculate_consecutive_streaks(pnl_list: list[float]) -> tuple[int, int]:
    """
    Calculate max consecutive wins and losses.

    Returns: (max_consec_wins, max_consec_losses)
    """
    if not pnl_list:
        return 0, 0

    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0

    for pnl in pnl_list:
        if pnl > 0:
            current_wins += 1
            current_losses = 0
            max_wins = max(max_wins, current_wins)
        elif pnl < 0:
            current_losses += 1
            current_wins = 0
            max_losses = max(max_losses, current_losses)
        else:
            # Breakeven resets streaks
            current_wins = 0
            current_losses = 0

    return max_wins, max_losses


def calculate_stability_r2(equity_curve: np.ndarray) -> float:
    """
    Calculate R-squared (Stability) of the equity curve.

    A value of 1.0 means a perfectly straight (stable) line.

    Args:
        equity_curve: Array of equity values

    Returns:
        float: R-squared value [0, 1]
    """
    if len(equity_curve) < 2:
        return 0.0

    y = np.asarray(equity_curve, dtype=np.float64)
    x = np.arange(len(y), dtype=np.float64)

    # Linear regression (use float64 to prevent overflow)
    n = float(len(y))
    sum_x = np.sum(x)
    sum_y = np.sum(y)
    sum_xy = np.sum(x * y)
    sum_xx = np.sum(x * x)

    # Slope (m) and Intercept (b)
    denominator = n * sum_xx - sum_x * sum_x
    if denominator == 0:
        return 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / n

    # Predicted values
    y_pred = slope * x + intercept

    # R-squared
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)

    if ss_tot == 0:
        return 0.0

    r2 = 1 - (ss_res / ss_tot)
    return float(np.clip(r2, 0.0, 1.0))


def calculate_sqn(total_trades: int, avg_trade_profit: float, std_trade_profit: float) -> float:
    """
    Calculate System Quality Number (SQN).

    Formula: sqrt(N) * (Mean / Std)
    """
    if total_trades < 2 or std_trade_profit == 0:
        return 0.0

    return math.sqrt(total_trades) * (avg_trade_profit / std_trade_profit)


# =============================================================================
# NUMBA-OPTIMIZED FUNCTIONS (for fast_optimizer, gpu_optimizer)
# =============================================================================


@jit(nopython=True, cache=True)
def calculate_metrics_numba(
    pnl_array: np.ndarray,
    equity_array: np.ndarray,
    daily_returns: np.ndarray,
    initial_capital: float,
) -> tuple[float, float, float, float, int, float, float]:
    """
    Numba-optimized metrics calculation.

    Returns: (total_return, sharpe, max_dd, win_rate, n_trades, profit_factor, calmar)

    USE THIS in fast_optimizer.py and gpu_optimizer.py for consistency!
    """
    n_trades = len(pnl_array)

    if n_trades == 0:
        return 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0

    # Total return
    total_pnl = 0.0
    for i in range(n_trades):
        total_pnl += pnl_array[i]
    total_return = (total_pnl / initial_capital) * 100

    # Win rate
    wins = 0
    gross_profit = 0.0
    gross_loss = 0.0

    for i in range(n_trades):
        if pnl_array[i] > 0:
            wins += 1
            gross_profit += pnl_array[i]
        else:
            gross_loss += abs(pnl_array[i])

    win_rate = wins / n_trades if n_trades > 0 else 0.0

    # Profit factor
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (100.0 if gross_profit > 0 else 0.0)

    # Max drawdown
    max_dd = 0.0
    peak = initial_capital

    for i in range(len(equity_array)):
        if equity_array[i] > peak:
            peak = equity_array[i]
        dd = (peak - equity_array[i]) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    max_dd *= 100  # As percentage

    # Sharpe ratio (using daily returns, matching standard calculator: ddof=1 + RFR)
    # Filter out NaN/inf values from daily_returns before computing stats
    n_returns = len(daily_returns)
    valid_count = 0
    mean_return = 0.0
    for i in range(n_returns):
        v = daily_returns[i]
        if not (np.isnan(v) or np.isinf(v)):
            mean_return += v
            valid_count += 1

    if valid_count > 1:
        mean_return /= valid_count

        variance = 0.0
        for i in range(n_returns):
            v = daily_returns[i]
            if not (np.isnan(v) or np.isinf(v)):
                variance += (v - mean_return) ** 2
        std_return = np.sqrt(variance / (valid_count - 1))  # Sample std (ddof=1)

        # Risk-free rate per period (annual 2% / 8766 hours)
        period_rfr = 0.02 / 8766.0

        # Annualize: sqrt(8766) for hourly data ~= 93.6
        sharpe = ((mean_return - period_rfr) / std_return) * 93.6 if std_return > 1e-10 else 0.0
    else:
        sharpe = 0.0

    # Calmar ratio
    calmar = total_return / max_dd if max_dd > 0.01 else (total_return * 10 if total_return > 0 else 0.0)

    return total_return, sharpe, max_dd, win_rate, n_trades, profit_factor, calmar


# =============================================================================
# MAIN CALCULATOR CLASS
# =============================================================================

# Cache for calculate_all() — avoids recomputation for identical inputs.
# Key: hash of (trades_tuple, equity_bytes, capital, years, frequency, margin)
# Max size: 32 entries (typical optimizer run produces ~10-20 results)
_calculate_all_cache: dict[int, dict] = {}
_CALCULATE_ALL_CACHE_MAX = 32


def _build_cache_key(
    trades: list[dict],
    equity: np.ndarray,
    initial_capital: float,
    years: float,
    frequency: "TimeFrequency",
    margin_rate: float,
) -> int:
    """Build a fast hash key for calculate_all() cache."""
    import hashlib

    h = hashlib.md5(usedforsecurity=False)
    # Hash equity bytes (fast for numpy arrays)
    h.update(equity.tobytes())
    # Hash scalar params
    h.update(f"{initial_capital}:{years}:{frequency}:{margin_rate}".encode())
    # Hash trade count + first/last trade PnL (avoids O(n) full hash for large lists)
    h.update(f"n={len(trades)}".encode())
    if trades:
        first = trades[0]
        last = trades[-1]
        pnl_f = first.get("pnl", 0) if isinstance(first, dict) else getattr(first, "pnl", 0)
        pnl_l = last.get("pnl", 0) if isinstance(last, dict) else getattr(last, "pnl", 0)
        h.update(f"f={pnl_f}:l={pnl_l}".encode())
    return int.from_bytes(h.digest()[:8], "little")


class MetricsCalculator:
    """
    Centralized metrics calculator.

    Usage:
        from backend.core.metrics_calculator import MetricsCalculator

        result = MetricsCalculator.calculate_all(
            trades=trades_list,
            equity=equity_array,
            initial_capital=10000,
            frequency=TimeFrequency.HOURLY
        )
    """

    @staticmethod
    def calculate_trade_metrics(
        trades: list[dict],
        include_commission: bool = True,
    ) -> TradeMetrics:
        """Calculate all trade-related metrics from a list of trades."""

        if not trades:
            return TradeMetrics()

        metrics = TradeMetrics()
        metrics.total_trades = len(trades)

        pnl_list = []
        pnl_pct_list = []
        win_pnl = []
        win_pnl_pct = []
        loss_pnl = []
        loss_pnl_pct = []
        bars_list = []
        win_bars = []
        loss_bars = []

        n_trades = len(trades)
        for i, t in enumerate(trades):
            # Support multiple possible trade dict shapes and object attributes
            if isinstance(t, dict):
                pnl = t.get("pnl", t.get("profit", t.get("realized_pnl", 0)))
                pnl_pct = t.get(
                    "pnl_pct",
                    t.get("profit_percent", t.get("profit_pct", t.get("profitPerc", 0))),
                )
                # fees may be stored under 'fees' or 'commission'
                fees = t.get("fees", t.get("commission", t.get("commissions", 0)))
                bars = t.get("bars_in_trade", t.get("bars", t.get("bars_in_position", 0)))
            else:
                pnl = getattr(t, "pnl", getattr(t, "profit", 0))
                pnl_pct = getattr(t, "pnl_pct", getattr(t, "profit_percent", 0))
                fees = getattr(t, "fees", getattr(t, "commission", 0))
                bars = getattr(t, "bars_in_trade", getattr(t, "bars", 0))

            pnl_list.append(pnl)
            pnl_pct_list.append(pnl_pct)
            bars_list.append(bars)
            metrics.total_commission += fees

            if i < 5 or i > n_trades - 5:
                # Log first and last few trades for debugging
                from loguru import logger

                logger.debug(f"Process trade {i}: side={getattr(t, 'side', 'N/A')}, pnl={pnl}, fees={fees}")

            # Gross profit/loss — TV definition: sum of net trade PnL (fees already deducted in pnl).
            # Do NOT add fees back: that would inflate gross_profit by double-counting commissions.
            # TV: gross_profit = sum(t.pnl for winning trades), gross_loss = sum(abs(t.pnl) for losing trades)
            gross_pnl = pnl

            if pnl > 0:
                metrics.winning_trades += 1
                metrics.gross_profit += gross_pnl
                win_pnl.append(pnl)
                win_pnl_pct.append(pnl_pct)
                win_bars.append(bars)
                if pnl > metrics.largest_win:
                    metrics.largest_win = pnl
                if pnl_pct > metrics.largest_win_pct:
                    metrics.largest_win_pct = pnl_pct
            elif pnl < 0:
                metrics.losing_trades += 1
                metrics.gross_loss += abs(gross_pnl)
                loss_pnl.append(pnl)
                loss_pnl_pct.append(pnl_pct)
                loss_bars.append(bars)
                if pnl < metrics.largest_loss:
                    metrics.largest_loss = pnl
                if pnl_pct < metrics.largest_loss_pct:
                    metrics.largest_loss_pct = pnl_pct
            else:
                metrics.breakeven_trades += 1

        metrics.net_profit = sum(pnl_list)

        # Derived metrics (win rate excludes breakeven trades from denominator)
        meaningful_trades = metrics.winning_trades + metrics.losing_trades
        metrics.win_rate = calculate_win_rate(metrics.winning_trades, meaningful_trades)
        metrics.profit_factor = calculate_profit_factor(metrics.gross_profit, metrics.gross_loss)

        # Averages
        metrics.avg_win = float(np.mean(win_pnl)) if win_pnl else 0.0
        metrics.avg_loss = float(np.mean(loss_pnl)) if loss_pnl else 0.0
        metrics.avg_trade = float(np.mean(pnl_list)) if pnl_list else 0.0

        metrics.avg_win_pct = float(np.mean(win_pnl_pct)) if win_pnl_pct else 0.0
        metrics.avg_loss_pct = float(np.mean(loss_pnl_pct)) if loss_pnl_pct else 0.0
        metrics.avg_trade_pct = float(np.mean(pnl_pct_list)) if pnl_pct_list else 0.0

        # Payoff ratio
        if metrics.avg_loss != 0:
            metrics.payoff_ratio = abs(metrics.avg_win / metrics.avg_loss)
        else:
            metrics.payoff_ratio = float("inf") if metrics.avg_win > 0 else 0.0

        # Bars
        metrics.avg_bars_held = np.mean(bars_list) if bars_list else 0.0
        metrics.avg_win_bars = np.mean(win_bars) if win_bars else 0.0
        metrics.avg_loss_bars = np.mean(loss_bars) if loss_bars else 0.0

        # Streaks
        metrics.max_consec_wins, metrics.max_consec_losses = calculate_consecutive_streaks(pnl_list)

        return metrics

    @staticmethod
    def calculate_risk_metrics(
        equity: np.ndarray,
        returns: np.ndarray,
        initial_capital: float,
        years: float = 1.0,
        frequency: TimeFrequency = TimeFrequency.HOURLY,
        margin_used: float = 0.0,
    ) -> RiskMetrics:
        """Calculate all risk-adjusted metrics."""

        metrics = RiskMetrics()

        if len(equity) < 2:
            return metrics

        final_capital = equity[-1]
        total_return_pct = (final_capital - initial_capital) / initial_capital * 100

        # Drawdown
        (
            metrics.max_drawdown,
            metrics.max_drawdown_value,
            metrics.max_drawdown_duration_bars,
        ) = calculate_max_drawdown(equity)

        # Drawdown average
        peak = np.maximum.accumulate(equity)
        # Protect div zero
        with np.errstate(divide="ignore", invalid="ignore"):
            dd_series = (peak - equity) / np.where(peak > 0, peak, 1)

        metrics.avg_drawdown = float(np.mean(dd_series)) * 100

        # Calculate avg_drawdown_duration_bars
        # Find all drawdown periods (where dd > 0) and average their duration
        in_drawdown = dd_series > 0
        if np.any(in_drawdown):
            # Find transitions into and out of drawdown
            dd_starts = []
            dd_ends = []
            was_in_dd = False
            dd_start_idx = 0
            for i, in_dd in enumerate(in_drawdown):
                if in_dd and not was_in_dd:
                    dd_start_idx = i
                    was_in_dd = True
                elif not in_dd and was_in_dd:
                    dd_starts.append(dd_start_idx)
                    dd_ends.append(i)
                    was_in_dd = False
            # Handle if still in drawdown at end
            if was_in_dd:
                dd_starts.append(dd_start_idx)
                dd_ends.append(len(in_drawdown))

            if dd_starts:
                durations = [dd_ends[i] - dd_starts[i] for i in range(len(dd_starts))]
                metrics.avg_drawdown_duration_bars = float(np.mean(durations))
            else:
                metrics.avg_drawdown_duration_bars = 0.0
        else:
            metrics.avg_drawdown_duration_bars = 0.0

        # Ulcer Index
        metrics.ulcer_index = calculate_ulcer_index(dd_series)

        # Runup (opposite of drawdown - growth from trough)
        trough = np.minimum.accumulate(equity)
        runup = (equity - trough) / np.where(trough > 0, trough, 1)
        metrics.max_runup = float(np.max(runup)) * 100
        metrics.max_runup_value = float(np.max(equity - trough))
        metrics.avg_runup = float(np.mean(runup)) * 100

        # Calculate avg_runup_duration_bars
        # Find all runup periods (where equity > trough) and average their duration
        in_runup = runup > 0
        if np.any(in_runup):
            ru_starts = []
            ru_ends = []
            was_in_ru = False
            ru_start_idx = 0
            for i, in_ru in enumerate(in_runup):
                if in_ru and not was_in_ru:
                    ru_start_idx = i
                    was_in_ru = True
                elif not in_ru and was_in_ru:
                    ru_starts.append(ru_start_idx)
                    ru_ends.append(i)
                    was_in_ru = False
            if was_in_ru:
                ru_starts.append(ru_start_idx)
                ru_ends.append(len(in_runup))

            if ru_starts:
                durations = [ru_ends[i] - ru_starts[i] for i in range(len(ru_starts))]
                metrics.avg_runup_duration_bars = float(np.mean(durations))
            else:
                metrics.avg_runup_duration_bars = 0.0
        else:
            metrics.avg_runup_duration_bars = 0.0

        # Risk ratios
        metrics.sharpe_ratio = calculate_sharpe(returns, frequency)
        metrics.sortino_ratio = calculate_sortino(returns, frequency)
        metrics.calmar_ratio = calculate_calmar(total_return_pct, metrics.max_drawdown, years)

        # CAGR
        metrics.cagr = calculate_cagr(initial_capital, final_capital, years)

        # Stability R-squared
        metrics.stability = calculate_stability_r2(equity)

        # Recovery factor
        if metrics.max_drawdown_value > 0:
            net_profit = final_capital - initial_capital
            metrics.recovery_factor = net_profit / metrics.max_drawdown_value
        else:
            net_profit = final_capital - initial_capital
            metrics.recovery_factor = float("inf") if net_profit > 0 else 0.0

        # Margin Efficiency
        if margin_used > 0:
            net_profit = final_capital - initial_capital
            metrics.margin_efficiency = calculate_margin_efficiency(net_profit, margin_used)

        # Volatility (annualized) — filter NaN/inf before computing std
        if len(returns) > 1:
            valid_returns = returns[np.isfinite(returns)]
            if len(valid_returns) > 1:
                periods_per_year = ANNUALIZATION_FACTORS.get(frequency, 365.25)
                metrics.volatility = float(np.std(valid_returns, ddof=1) * np.sqrt(periods_per_year)) * 100

        return metrics

    @staticmethod
    def calculate_long_short_metrics(
        trades: list[dict],
        initial_capital: float,
        years: float = 1.0,
    ) -> LongShortMetrics:
        """Calculate separate metrics for long and short trades."""

        metrics = LongShortMetrics()

        if not trades:
            return metrics

        # Separate by side
        long_trades: list[dict] = []
        short_trades: list[dict] = []
        unknown_sides: set[str] = set()  # Track unknown values for single log

        for t in trades:
            try:
                if len(long_trades) == 0 and len(short_trades) == 0 and len(unknown_sides) == 0:
                    # Log first trade sample only once (debug mode)
                    # Note: In production, consider disabling or using proper logging
                    from pathlib import Path

                    log_dir = Path(__file__).resolve().parents[2] / "logs"
                    log_dir.mkdir(parents=True, exist_ok=True)
                    log_path = log_dir / "debug_metrics_explicit.log"
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(f"Trades sample (first trade): {t}\n")
            except Exception:
                # Silently skip debug logging on failure (non-critical)
                pass
            side = t.get("side", "") if isinstance(t, dict) else getattr(t, "side", "")
            # Also check 'direction' field as fallback (used by GPU optimizer)
            if not side:
                side = t.get("direction", "") if isinstance(t, dict) else getattr(t, "direction", "")

            # Normalize side to string
            if hasattr(side, "value"):
                side_str = str(side.value).lower()
            elif hasattr(side, "name"):
                side_str = str(side.name).lower()
            else:
                side_str = str(side).lower().strip()

            # Expanded matching for various formats
            if side_str in (
                "buy",
                "long",
                "entry",
                "1",
                "tradeside.buy",
                "tradedirection.long",
            ):
                long_trades.append(t)
            elif side_str in (
                "sell",
                "short",
                "exit",
                "-1",
                "tradeside.sell",
                "tradedirection.short",
            ):
                short_trades.append(t)
            elif side_str:  # Only log if side is non-empty
                unknown_sides.add(side_str)

        # Log unknown sides once (not per trade)
        if unknown_sides:
            from loguru import logger

            logger.warning(f"Unknown trade sides encountered: {unknown_sides}")

        # Helper to process side metrics
        def process_side(side_trades):
            if not side_trades:
                return None

            # Use the unified trade metrics calculation
            m = MetricsCalculator.calculate_trade_metrics(side_trades)

            # Calculate CAGR specific to this side (using net profit contribution)
            side_net_profit = m.net_profit
            side_final = initial_capital + side_net_profit
            cagr = calculate_cagr(initial_capital, side_final, years)

            return m, cagr

        # Process Longs
        from loguru import logger

        logger.debug(
            f"[metrics_calc] Processing Longs: {len(long_trades)} trades identified. Sample: {long_trades[0] if long_trades else 'None'}"
        )

        long_res = process_side(long_trades)
        if long_res:
            long_m, long_cagr = long_res
            logger.debug(f"[metrics_calc] Long metrics raw: avg_loss={long_m.avg_loss}, avg_win={long_m.avg_win}")

            metrics.long_trades = long_m.total_trades
            metrics.long_winning = long_m.winning_trades
            metrics.long_losing = long_m.losing_trades
            metrics.long_breakeven = long_m.breakeven_trades
            metrics.long_gross_profit = long_m.gross_profit
            metrics.long_gross_loss = long_m.gross_loss
            metrics.long_net_profit = long_m.net_profit
            metrics.long_commission = long_m.total_commission
            metrics.long_win_rate = long_m.win_rate
            metrics.long_profit_factor = long_m.profit_factor
            metrics.long_avg_win = long_m.avg_win
            metrics.long_avg_loss = long_m.avg_loss
            metrics.long_avg_trade = long_m.avg_trade
            metrics.long_avg_win_pct = long_m.avg_win_pct
            metrics.long_avg_loss_pct = long_m.avg_loss_pct
            metrics.long_avg_trade_pct = long_m.avg_trade_pct
            metrics.long_largest_win = long_m.largest_win
            metrics.long_largest_loss = long_m.largest_loss
            metrics.long_largest_win_pct = long_m.largest_win_pct
            metrics.long_largest_loss_pct = long_m.largest_loss_pct
            metrics.long_payoff_ratio = long_m.payoff_ratio
            metrics.long_max_consec_wins = long_m.max_consec_wins
            metrics.long_max_consec_losses = long_m.max_consec_losses
            metrics.long_avg_bars = long_m.avg_bars_held
            metrics.long_avg_win_bars = long_m.avg_win_bars
            metrics.long_avg_loss_bars = long_m.avg_loss_bars
            metrics.long_cagr = long_cagr

        # Process Shorts
        short_res = process_side(short_trades)
        if short_res:
            short_m, short_cagr = short_res
            metrics.short_trades = short_m.total_trades
            metrics.short_winning = short_m.winning_trades
            metrics.short_losing = short_m.losing_trades
            metrics.short_breakeven = short_m.breakeven_trades
            metrics.short_gross_profit = short_m.gross_profit
            metrics.short_gross_loss = short_m.gross_loss
            metrics.short_net_profit = short_m.net_profit
            metrics.short_commission = short_m.total_commission
            metrics.short_win_rate = short_m.win_rate
            metrics.short_profit_factor = short_m.profit_factor
            metrics.short_avg_win = short_m.avg_win
            metrics.short_avg_loss = short_m.avg_loss
            metrics.short_avg_trade = short_m.avg_trade
            metrics.short_avg_win_pct = short_m.avg_win_pct
            metrics.short_avg_loss_pct = short_m.avg_loss_pct
            metrics.short_avg_trade_pct = short_m.avg_trade_pct
            metrics.short_largest_win = short_m.largest_win
            metrics.short_largest_loss = short_m.largest_loss
            metrics.short_largest_win_pct = short_m.largest_win_pct
            metrics.short_largest_loss_pct = short_m.largest_loss_pct
            metrics.short_payoff_ratio = short_m.payoff_ratio
            metrics.short_max_consec_wins = short_m.max_consec_wins
            metrics.short_max_consec_losses = short_m.max_consec_losses
            metrics.short_avg_bars = short_m.avg_bars_held
            metrics.short_avg_win_bars = short_m.avg_win_bars
            metrics.short_avg_loss_bars = short_m.avg_loss_bars
            metrics.short_cagr = short_cagr

        return metrics

    @staticmethod
    def calculate_all(
        trades: list[dict],
        equity: np.ndarray,
        initial_capital: float,
        years: float = 1.0,
        frequency: TimeFrequency = TimeFrequency.HOURLY,
        margin_rate: float = 1.0,  # 1.0 = 1x leverage (100% margin), 0.5 for 2x, etc.
    ) -> dict:
        """
        Calculate ALL metrics in one call.

        Results are cached by content hash to avoid recomputation
        for identical inputs (e.g. during optimizer result display).

        Returns a dictionary with all metrics ready for PerformanceMetrics model.
        """
        # Check cache first
        equity = np.asarray(equity)
        cache_key = _build_cache_key(trades, equity, initial_capital, years, frequency, margin_rate)
        if cache_key in _calculate_all_cache:
            return _calculate_all_cache[cache_key].copy()

        # Calculate returns from equity
        if len(equity) > 1:
            # Shift to get returns ensuring no nan/inf
            with np.errstate(divide="ignore", invalid="ignore"):
                returns = np.diff(equity) / equity[:-1]
            returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)
        else:
            returns = np.array([0.0])

        # Trade metrics
        trade_m = MetricsCalculator.calculate_trade_metrics(trades)
        from loguru import logger

        logger.debug(
            f"Calculated trade metrics: total={trade_m.total_trades}, net_profit={trade_m.net_profit}, gross_profit={trade_m.gross_profit}"
        )

        # Calculate Margin Used for Efficiency
        avg_margin_used = 0.0
        if trades:
            # Heuristic: try to get size * entry_price
            margins = []
            for t in trades:
                # Support both dict and object access
                if isinstance(t, dict):
                    size = t.get("size", 0)
                    price = t.get("entry_price", 0)
                else:
                    size = getattr(t, "size", 0)
                    price = getattr(t, "entry_price", 0)
                if size and price:
                    # Margin used = Position Value * Margin Rate (if rate is e.g. 0.01 for 100x)
                    # Use margin_rate param which usually denotes 'initial margin ratio'
                    # E.g. 50x leverage -> margin_rate = 0.02
                    # However, typical TV formula assumes we want avg position value?
                    # TV Formula: Efficiency = Net Profit / (Avg Margin * 0.7)
                    # Let's assume margin_rate passed here defines how much capital is locked.
                    margins.append(size * price * margin_rate)

            if margins:
                avg_margin_used = np.mean(margins)

        # Risk metrics
        risk_m = MetricsCalculator.calculate_risk_metrics(
            equity,
            returns,
            initial_capital,
            years,
            frequency,
            margin_used=avg_margin_used,
        )

        # Long/Short metrics
        ls_m = MetricsCalculator.calculate_long_short_metrics(trades, initial_capital, years)

        # Expectancy and SQN
        kelly_percent = 0.0
        kelly_percent_long = 0.0
        kelly_percent_short = 0.0
        if trade_m.total_trades > 0:
            win_frac = trade_m.winning_trades / trade_m.total_trades
            expectancy, expectancy_ratio = calculate_expectancy(win_frac, trade_m.avg_win, trade_m.avg_loss)
            # expectancy_pct: uses percent avg_win/avg_loss for a normalised "R" representation
            expectancy_pct, expectancy_pct_ratio = calculate_expectancy(
                win_frac, trade_m.avg_win_pct, trade_m.avg_loss_pct
            )

            # SQN (System Quality Number) calculation
            # Extract PnLs from trades again to compute StdDev
            # (Optimization: calculate_trade_metrics could return this, but for now we do it here)
            pnl_values = []
            for t in trades:
                pnl = t.get("pnl", 0) if isinstance(t, dict) else getattr(t, "pnl", 0)
                pnl_values.append(pnl)

            if len(pnl_values) > 1:
                std_pnl = float(np.std(pnl_values, ddof=1))
                risk_m.sqn = calculate_sqn(trade_m.total_trades, trade_m.avg_trade, std_pnl)

            # Kelly Criterion: K% = W - (1 - W) / R
            # W = win rate (as fraction), R = payoff ratio (avg_win / avg_loss)
            if trade_m.payoff_ratio > 0:
                kelly_percent = win_frac - (1 - win_frac) / trade_m.payoff_ratio
                kelly_percent = max(0.0, min(1.0, kelly_percent))
            else:
                kelly_percent = 0.0

            # Kelly per direction
            if ls_m.long_trades > 0 and ls_m.long_payoff_ratio > 0:
                long_win_frac = ls_m.long_winning / ls_m.long_trades
                kelly_percent_long = long_win_frac - (1 - long_win_frac) / ls_m.long_payoff_ratio
                kelly_percent_long = max(0.0, min(1.0, kelly_percent_long))

            if ls_m.short_trades > 0 and ls_m.short_payoff_ratio > 0:
                short_win_frac = ls_m.short_winning / ls_m.short_trades
                kelly_percent_short = short_win_frac - (1 - short_win_frac) / ls_m.short_payoff_ratio
                kelly_percent_short = max(0.0, min(1.0, kelly_percent_short))

        else:
            expectancy, expectancy_ratio = 0.0, 0.0
            expectancy_pct, expectancy_pct_ratio = 0.0, 0.0

        # Combine into dictionary
        result = {
            # Trade stats
            "total_trades": trade_m.total_trades,
            "winning_trades": trade_m.winning_trades,
            "losing_trades": trade_m.losing_trades,
            "breakeven_trades": trade_m.breakeven_trades,
            "gross_profit": trade_m.gross_profit,
            "gross_loss": trade_m.gross_loss,
            "net_profit": trade_m.net_profit,
            "total_commission": trade_m.total_commission,
            "win_rate": trade_m.win_rate,
            "profit_factor": trade_m.profit_factor,
            "avg_win": trade_m.avg_win_pct,
            "avg_win_pct": trade_m.avg_win_pct,  # Explicit alias — avg_win == avg_win_pct (percentage)
            "avg_loss": trade_m.avg_loss_pct,
            "avg_loss_pct": trade_m.avg_loss_pct,  # Explicit alias
            "avg_trade": trade_m.avg_trade_pct,
            "avg_trade_pct": trade_m.avg_trade_pct,  # Alias for frontend compatibility
            "largest_win": trade_m.largest_win_pct,
            "largest_loss": trade_m.largest_loss_pct,
            "avg_win_value": trade_m.avg_win,
            "avg_loss_value": trade_m.avg_loss,
            "avg_trade_value": trade_m.avg_trade,
            "largest_win_value": trade_m.largest_win,
            "largest_loss_value": trade_m.largest_loss,
            "avg_win_loss_ratio": trade_m.payoff_ratio,
            "max_consecutive_wins": trade_m.max_consec_wins,
            "max_consecutive_losses": trade_m.max_consec_losses,
            "avg_bars_in_trade": trade_m.avg_bars_held,
            "avg_bars_in_winning": trade_m.avg_win_bars,
            "avg_bars_in_losing": trade_m.avg_loss_bars,
            # Risk metrics
            "sharpe_ratio": risk_m.sharpe_ratio,
            "sortino_ratio": risk_m.sortino_ratio,
            "calmar_ratio": risk_m.calmar_ratio,
            "max_drawdown": risk_m.max_drawdown,
            "max_drawdown_value": risk_m.max_drawdown_value,
            "avg_drawdown": risk_m.avg_drawdown,
            "max_drawdown_duration_bars": risk_m.max_drawdown_duration_bars,
            "avg_drawdown_duration_bars": risk_m.avg_drawdown_duration_bars,
            "max_runup": risk_m.max_runup,
            "max_runup_value": risk_m.max_runup_value,
            "avg_runup": risk_m.avg_runup,
            "avg_runup_duration_bars": risk_m.avg_runup_duration_bars,
            "recovery_factor": risk_m.recovery_factor,
            "ulcer_index": risk_m.ulcer_index,
            "margin_efficiency": risk_m.margin_efficiency,
            "stability": risk_m.stability,
            "sqn": risk_m.sqn,
            "kelly_percent": kelly_percent,
            "kelly_percent_long": kelly_percent_long,
            "kelly_percent_short": kelly_percent_short,
            "open_trades": 0,  # All trades are closed in backtests
            "expectancy": expectancy,
            "expectancy_ratio": expectancy_ratio,
            "expectancy_pct": expectancy_pct,
            "expectancy_pct_ratio": expectancy_pct_ratio,
            "cagr": risk_m.cagr,
            "volatility": risk_m.volatility,
            # Long/Short metrics
            "long_trades": ls_m.long_trades,
            "long_winning_trades": ls_m.long_winning,
            "long_losing_trades": ls_m.long_losing,
            "long_breakeven_trades": ls_m.long_breakeven,
            "long_gross_profit": ls_m.long_gross_profit,
            "long_gross_loss": ls_m.long_gross_loss,
            "long_net_profit": ls_m.long_net_profit,
            "long_commission": ls_m.long_commission,
            "long_win_rate": ls_m.long_win_rate,
            "long_profit_factor": ls_m.long_profit_factor,
            "long_avg_win": ls_m.long_avg_win,
            "long_avg_loss": ls_m.long_avg_loss,
            "long_avg_trade": ls_m.long_avg_trade,
            "long_largest_win": ls_m.long_largest_win,
            "long_largest_loss": ls_m.long_largest_loss,
            "long_payoff_ratio": ls_m.long_payoff_ratio,
            "long_max_consec_wins": ls_m.long_max_consec_wins,
            "long_max_consec_losses": ls_m.long_max_consec_losses,
            "long_avg_bars": ls_m.long_avg_bars,
            "long_avg_win_bars": ls_m.long_avg_win_bars,
            "long_avg_loss_bars": ls_m.long_avg_loss_bars,
            "long_avg_win_pct": ls_m.long_avg_win_pct,
            "long_avg_loss_pct": ls_m.long_avg_loss_pct,
            "long_avg_trade_pct": ls_m.long_avg_trade_pct,
            "long_largest_win_pct": ls_m.long_largest_win_pct,
            "long_largest_loss_pct": ls_m.long_largest_loss_pct,
            "cagr_long": ls_m.long_cagr,
            "short_trades": ls_m.short_trades,
            "short_winning_trades": ls_m.short_winning,
            "short_losing_trades": ls_m.short_losing,
            "short_breakeven_trades": ls_m.short_breakeven,
            "short_gross_profit": ls_m.short_gross_profit,
            "short_gross_loss": ls_m.short_gross_loss,
            "short_net_profit": ls_m.short_net_profit,
            "short_commission": ls_m.short_commission,
            "short_win_rate": ls_m.short_win_rate,
            "short_profit_factor": ls_m.short_profit_factor,
            "short_avg_win": ls_m.short_avg_win,
            "short_avg_loss": ls_m.short_avg_loss,
            "short_avg_trade": ls_m.short_avg_trade,
            "short_largest_win": ls_m.short_largest_win,
            "short_largest_loss": ls_m.short_largest_loss,
            "short_payoff_ratio": ls_m.short_payoff_ratio,
            "short_max_consec_wins": ls_m.short_max_consec_wins,
            "short_max_consec_losses": ls_m.short_max_consec_losses,
            "short_avg_bars": ls_m.short_avg_bars,
            "short_avg_win_bars": ls_m.short_avg_win_bars,
            "short_avg_loss_bars": ls_m.short_avg_loss_bars,
            "short_avg_win_pct": ls_m.short_avg_win_pct,
            "short_avg_loss_pct": ls_m.short_avg_loss_pct,
            "short_avg_trade_pct": ls_m.short_avg_trade_pct,
            "short_largest_win_pct": ls_m.short_largest_win_pct,
            "short_largest_loss_pct": ls_m.short_largest_loss_pct,
            "cagr_short": ls_m.short_cagr,
        }

        # Store in cache (evict oldest if full)
        if len(_calculate_all_cache) >= _CALCULATE_ALL_CACHE_MAX:
            # Remove oldest entry (first key in insertion order)
            oldest = next(iter(_calculate_all_cache))
            del _calculate_all_cache[oldest]
        _calculate_all_cache[cache_key] = result.copy()

        return result


# =============================================================================
# METRICS ENRICHMENT - SINGLE SOURCE OF TRUTH FOR ALL PERCENTAGES
# =============================================================================


def enrich_metrics_with_percentages(metrics: dict, initial_capital: float) -> dict:
    """
    Enrich metrics dictionary with percentage values.

    ЕДИНЫЙ ИСТОЧНИК ПРАВДЫ для всех процентных метрик.
    Вызывать перед отправкой метрик на фронтенд!

    Args:
        metrics: Raw metrics dictionary
        initial_capital: Initial capital for percentage calculations

    Returns:
        Enriched metrics dictionary with all _pct fields
    """
    if initial_capital <= 0:
        return metrics

    result = dict(metrics)  # Create a copy

    # List of fields to convert to percentages (value / initial_capital * 100)
    VALUE_FIELDS = [
        # Long metrics
        "long_net_profit",
        "long_gross_profit",
        "long_gross_loss",
        "long_commission",
        "long_largest_win",
        "long_largest_loss",
        "long_avg_win",
        "long_avg_loss",
        "avg_trade_long",
        # Short metrics
        "short_net_profit",
        "short_gross_profit",
        "short_gross_loss",
        "short_commission",
        "short_largest_win",
        "short_largest_loss",
        "short_avg_win",
        "short_avg_loss",
        "avg_trade_short",
        # General metrics
        "gross_profit",
        "gross_loss",
        "largest_win_value",
        "largest_loss_value",
        "avg_win_value",
        "avg_loss_value",
        "expectancy",
        "max_drawdown_value",
        "max_runup_value",
        "avg_drawdown_value",
        "avg_runup_value",
        "buy_hold_return",
        "open_pnl",
    ]

    for field in VALUE_FIELDS:
        value = metrics.get(field, 0)
        if value is not None and value != 0:
            pct_field = f"{field}_pct"
            # Only add if not already present
            if pct_field not in result:
                result[pct_field] = (value / initial_capital) * 100

    # Handle special cases where the pct field has a different name
    # long_net_profit -> long_return_pct (for consistency with UI)
    if "long_net_profit" in metrics and metrics["long_net_profit"] is not None:
        result["long_return_pct"] = (metrics["long_net_profit"] / initial_capital) * 100

    if "short_net_profit" in metrics and metrics["short_net_profit"] is not None:
        result["short_return_pct"] = (metrics["short_net_profit"] / initial_capital) * 100

    # Strategy outperformance vs Buy & Hold
    strategy_return = result.get("net_profit_pct", result.get("total_return", 0))
    buy_hold_pct = result.get("buy_hold_return_pct", 0)
    if buy_hold_pct == 0 and "buy_hold_return" in metrics:
        buy_hold_pct = (metrics["buy_hold_return"] / initial_capital) * 100
        result["buy_hold_return_pct"] = buy_hold_pct

    result["strategy_outperformance"] = strategy_return - buy_hold_pct

    # Ensure all key percentage fields exist (with 0 default)
    REQUIRED_PCT_FIELDS = [
        "net_profit_pct",
        "gross_profit_pct",
        "gross_loss_pct",
        "long_net_profit_pct",
        "short_net_profit_pct",
        "long_gross_profit_pct",
        "short_gross_profit_pct",
        "long_gross_loss_pct",
        "short_gross_loss_pct",
        "long_return_pct",
        "short_return_pct",
        "buy_hold_return_pct",
        "strategy_outperformance",
        "open_pnl_pct",
    ]

    for field in REQUIRED_PCT_FIELDS:
        if field not in result:
            result[field] = 0.0

    return result
