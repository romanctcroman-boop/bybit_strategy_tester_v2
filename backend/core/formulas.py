"""
📊 Centralized Metrics Formulas

Single source of truth for all metric calculations.

This module provides centralized implementations of all trading metrics
to ensure consistency between MetricsCalculator and Numba engine.

@version: 1.0.0
@date: 2026-02-26
"""

import warnings
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ============================================================================
# PERFORMANCE METRICS
# ============================================================================


def calculate_total_return(equity_curve: Union[pd.Series, List[float]]) -> float:
    """
    Calculate total return.

    Args:
        equity_curve: Equity curve series or list

    Returns:
        Total return as decimal (e.g., 0.25 for 25%)
    """
    if len(equity_curve) < 2:
        return 0.0

    if isinstance(equity_curve, (list, np.ndarray)):
        equity_curve = pd.Series(equity_curve)

    initial = equity_curve.iloc[0]
    final = equity_curve.iloc[-1]

    if initial == 0:
        return 0.0

    return (final - initial) / initial


def calculate_cagr(equity_curve: Union[pd.Series, List[float]], periods_per_year: int = 252) -> float:
    """
    Calculate Compound Annual Growth Rate.

    Args:
        equity_curve: Equity curve series
        periods_per_year: Trading periods per year (252 for daily)

    Returns:
        CAGR as decimal
    """
    total_return = calculate_total_return(equity_curve)
    n_periods = len(equity_curve)

    if n_periods < 2 or total_return <= -1:
        return 0.0

    years = n_periods / periods_per_year

    if years <= 0:
        return 0.0

    return (1 + total_return) ** (1 / years) - 1


def calculate_volatility(returns: Union[pd.Series, List[float]], periods_per_year: int = 252) -> float:
    """
    Calculate annualized volatility.

    Args:
        returns: Returns series
        periods_per_year: Trading periods per year

    Returns:
        Annualized volatility
    """
    if len(returns) < 2:
        return 0.0

    if isinstance(returns, (list, np.ndarray)):
        returns = pd.Series(returns)

    return returns.std() * np.sqrt(periods_per_year)


def calculate_sharpe_ratio(
    returns: Union[pd.Series, List[float]], risk_free_rate: float = 0.0, periods_per_year: int = 252
) -> float:
    """
    Calculate Sharpe ratio.

    The Sharpe ratio measures risk-adjusted return.
    Higher values indicate better risk-adjusted performance.

    Formula:
        Sharpe = (R_p - R_f) / σ_p

    where:
        R_p = Portfolio return
        R_f = Risk-free rate
        σ_p = Portfolio volatility

    Args:
        returns: Returns series (as decimals, e.g., 0.01 for 1%)
        risk_free_rate: Annual risk-free rate (as decimal)
        periods_per_year: Trading periods per year

    Returns:
        Annualized Sharpe ratio

    Example:
        >>> returns = [0.01, 0.02, -0.01, 0.03]
        >>> calculate_sharpe_ratio(returns)
        1.23
    """
    if len(returns) < 2:
        return 0.0

    if isinstance(returns, (list, np.ndarray)):
        returns = pd.Series(returns)

    # Remove NaN values
    returns = returns.dropna()

    if len(returns) < 2:
        return 0.0

    # Excess returns
    daily_rf = risk_free_rate / periods_per_year
    excess_returns = returns - daily_rf

    # Mean and std
    mean_excess = excess_returns.mean()
    std = excess_returns.std()

    if std == 0:
        return 0.0

    # Annualize
    sharpe = mean_excess / std * np.sqrt(periods_per_year)

    return sharpe


def calculate_sortino_ratio(
    returns: Union[pd.Series, List[float]],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
    target_return: float = 0.0,
) -> float:
    """
    Calculate Sortino ratio.

    Similar to Sharpe ratio but uses downside deviation instead of total volatility.
    Better for strategies with asymmetric return distributions.

    Formula:
        Sortino = (R_p - R_f) / σ_downside

    Args:
        returns: Returns series
        risk_free_rate: Annual risk-free rate
        periods_per_year: Trading periods per year
        target_return: Target return (default 0)

    Returns:
        Annualized Sortino ratio
    """
    if len(returns) < 2:
        return 0.0

    if isinstance(returns, (list, np.ndarray)):
        returns = pd.Series(returns)

    returns = returns.dropna()

    if len(returns) < 2:
        return 0.0

    # Excess returns
    daily_rf = risk_free_rate / periods_per_year
    excess_returns = returns - daily_rf

    # Downside returns (only negative)
    downside_returns = excess_returns[excess_returns < target_return]

    if len(downside_returns) < 2:
        return 0.0

    # Downside deviation
    downside_deviation = np.sqrt(np.mean(downside_returns**2)) * np.sqrt(periods_per_year)

    if downside_deviation == 0:
        return 0.0

    # Annualized return
    annual_return = excess_returns.mean() * periods_per_year

    sortino = annual_return / downside_deviation

    return sortino


def calculate_calmar_ratio(equity_curve: Union[pd.Series, List[float]], periods_per_year: int = 252) -> float:
    """
    Calculate Calmar ratio.

    Ratio of CAGR to maximum drawdown.
    Good for assessing return per unit of worst-case risk.

    Formula:
        Calmar = CAGR / |Max DD|

    Args:
        equity_curve: Equity curve series
        periods_per_year: Trading periods per year

    Returns:
        Calmar ratio
    """
    cagr = calculate_cagr(equity_curve, periods_per_year)
    max_dd = calculate_max_drawdown(equity_curve)

    if max_dd == 0:
        return 0.0

    return cagr / abs(max_dd)


# ============================================================================
# DRAWDOWN METRICS
# ============================================================================


def calculate_max_drawdown(equity_curve: Union[pd.Series, List[float]]) -> float:
    """
    Calculate maximum drawdown.

    The largest peak-to-trough decline in portfolio value.

    Formula:
        Max DD = min((Equity - Running Max) / Running Max)

    Args:
        equity_curve: Equity curve series

    Returns:
        Maximum drawdown as negative decimal (e.g., -0.25 for -25%)
    """
    if len(equity_curve) < 2:
        return 0.0

    if isinstance(equity_curve, (list, np.ndarray)):
        equity_curve = pd.Series(equity_curve)

    # Running maximum
    running_max = equity_curve.cummax()

    # Drawdown series
    drawdown = (equity_curve - running_max) / running_max

    # Maximum drawdown
    max_dd = drawdown.min()

    return max_dd


def calculate_avg_drawdown(equity_curve: Union[pd.Series, List[float]]) -> float:
    """
    Calculate average drawdown.

    Average of all drawdown periods.

    Args:
        equity_curve: Equity curve series

    Returns:
        Average drawdown as negative decimal
    """
    if len(equity_curve) < 2:
        return 0.0

    if isinstance(equity_curve, (list, np.ndarray)):
        equity_curve = pd.Series(equity_curve)

    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max

    # Average of drawdown periods (excluding zeros)
    drawdown_periods = drawdown[drawdown < 0]

    if len(drawdown_periods) == 0:
        return 0.0

    return drawdown_periods.mean()


def calculate_drawdown_duration(equity_curve: Union[pd.Series, List[float]]) -> int:
    """
    Calculate longest drawdown duration.

    Number of periods from peak to recovery.

    Args:
        equity_curve: Equity curve series

    Returns:
        Longest drawdown duration in periods
    """
    if len(equity_curve) < 2:
        return 0

    if isinstance(equity_curve, (list, np.ndarray)):
        equity_curve = pd.Series(equity_curve)

    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max

    # Find drawdown periods
    in_drawdown = drawdown < 0

    # Calculate durations
    durations = []
    current_duration = 0

    for in_dd in in_drawdown:
        if in_dd:
            current_duration += 1
        else:
            if current_duration > 0:
                durations.append(current_duration)
            current_duration = 0

    if current_duration > 0:
        durations.append(current_duration)

    if len(durations) == 0:
        return 0

    return max(durations)


# ============================================================================
# TRADE STATISTICS
# ============================================================================


def calculate_win_rate(trades: List[Dict]) -> float:
    """
    Calculate win rate.

    Percentage of winning trades.

    Args:
        trades: List of trade dictionaries with 'pnl' key

    Returns:
        Win rate as decimal (0.0 to 1.0)
    """
    if len(trades) == 0:
        return 0.0

    winning_trades = [t for t in trades if t.get("pnl", 0) > 0]

    return len(winning_trades) / len(trades)


def calculate_profit_factor(trades: List[Dict]) -> float:
    """
    Calculate profit factor.

    Ratio of gross profit to gross loss.

    Formula:
        Profit Factor = Gross Profit / |Gross Loss|

    Args:
        trades: List of trade dictionaries with 'pnl' key

    Returns:
        Profit factor (undefined = 0 if no losses)
    """
    if len(trades) == 0:
        return 0.0

    gross_profit = sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0)
    gross_loss = abs(sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) < 0))

    if gross_loss == 0:
        return 0.0 if gross_profit == 0 else float("inf")

    return gross_profit / gross_loss


def calculate_avg_win(trades: List[Dict]) -> float:
    """
    Calculate average winning trade.

    Args:
        trades: List of trade dictionaries with 'pnl' key

    Returns:
        Average profit of winning trades
    """
    winning_trades = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0]

    if len(winning_trades) == 0:
        return 0.0

    return np.mean(winning_trades)


def calculate_avg_loss(trades: List[Dict]) -> float:
    """
    Calculate average losing trade.

    Args:
        trades: List of trade dictionaries with 'pnl' key

    Returns:
        Average loss of losing trades (as negative number)
    """
    losing_trades = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) < 0]

    if len(losing_trades) == 0:
        return 0.0

    return np.mean(losing_trades)


def calculate_expectancy(trades: List[Dict]) -> float:
    """
    Calculate trade expectancy.

    Expected profit per trade.

    Formula:
        Expectancy = (Win% × Avg Win) - (Loss% × Avg Loss)

    Args:
        trades: List of trade dictionaries with 'pnl' key

    Returns:
        Expectancy per trade
    """
    if len(trades) == 0:
        return 0.0

    win_rate = calculate_win_rate(trades)
    avg_win = calculate_avg_win(trades)
    avg_loss = calculate_avg_loss(trades)
    loss_rate = 1 - win_rate

    expectancy = (win_rate * avg_win) - (loss_rate * abs(avg_loss))

    return expectancy


def calculate_avg_trade_duration(trades: List[Dict]) -> float:
    """
    Calculate average trade duration.

    Args:
        trades: List of trade dictionaries with 'duration' or 'bars' key

    Returns:
        Average duration in periods
    """
    durations = []

    for trade in trades:
        if "duration" in trade:
            durations.append(trade["duration"])
        elif "bars" in trade:
            durations.append(trade["bars"])

    if len(durations) == 0:
        return 0.0

    return np.mean(durations)


# ============================================================================
# RISK METRICS
# ============================================================================


def calculate_var(returns: Union[pd.Series, List[float]], confidence_level: float = 0.95) -> float:
    """
    Calculate Value at Risk (VaR).

    Maximum expected loss at given confidence level.

    Args:
        returns: Returns series
        confidence_level: Confidence level (0.95 = 95%)

    Returns:
        VaR as negative decimal
    """
    if len(returns) < 10:
        return 0.0

    if isinstance(returns, (list, np.ndarray)):
        returns = pd.Series(returns)

    returns = returns.dropna()

    if len(returns) < 10:
        return 0.0

    var = returns.quantile(1 - confidence_level)

    return var


def calculate_cvar(returns: Union[pd.Series, List[float]], confidence_level: float = 0.95) -> float:
    """
    Calculate Conditional Value at Risk (CVaR / Expected Shortfall).

    Expected loss given that loss exceeds VaR.

    Args:
        returns: Returns series
        confidence_level: Confidence level

    Returns:
        CVaR as negative decimal
    """
    if len(returns) < 10:
        return 0.0

    if isinstance(returns, (list, np.ndarray)):
        returns = pd.Series(returns)

    returns = returns.dropna()

    if len(returns) < 10:
        return 0.0

    var = calculate_var(returns, confidence_level)

    # Average of returns below VaR
    tail_returns = returns[returns <= var]

    if len(tail_returns) == 0:
        return var

    cvar = tail_returns.mean()

    return cvar


def calculate_beta(returns: Union[pd.Series, List[float]], benchmark_returns: Union[pd.Series, List[float]]) -> float:
    """
    Calculate beta (market sensitivity).

    Args:
        returns: Strategy returns
        benchmark_returns: Benchmark returns

    Returns:
        Beta coefficient
    """
    if len(returns) < 10 or len(benchmark_returns) < 10:
        return 0.0

    if isinstance(returns, (list, np.ndarray)):
        returns = pd.Series(returns)
    if isinstance(benchmark_returns, list):
        benchmark_returns = pd.Series(benchmark_returns)

    # Align series
    aligned = pd.concat([returns, benchmark_returns], axis=1).dropna()

    if len(aligned) < 10:
        return 0.0

    # Calculate covariance and variance
    covariance = aligned.cov().iloc[0, 1]
    variance = aligned.iloc[:, 1].var()

    if variance == 0:
        return 0.0

    beta = covariance / variance

    return beta


def calculate_alpha(
    returns: Union[pd.Series, List[float]],
    benchmark_returns: Union[pd.Series, List[float]],
    risk_free_rate: float = 0.0,
) -> float:
    """
    Calculate Jensen's alpha.

    Excess return above what beta predicts.

    Args:
        returns: Strategy returns
        benchmark_returns: Benchmark returns
        risk_free_rate: Risk-free rate

    Returns:
        Alpha (annualized)
    """
    if len(returns) < 10 or len(benchmark_returns) < 10:
        return 0.0

    if isinstance(returns, (list, np.ndarray)):
        returns = pd.Series(returns)
    if isinstance(benchmark_returns, list):
        benchmark_returns = pd.Series(benchmark_returns)

    beta = calculate_beta(returns, benchmark_returns)

    # Annualized returns
    strategy_return = returns.mean() * 252
    benchmark_return = benchmark_returns.mean() * 252

    # CAPM expected return
    expected_return = risk_free_rate + beta * (benchmark_return - risk_free_rate)

    # Alpha
    alpha = strategy_return - expected_return

    return alpha


# ============================================================================
# DIVERSIFICATION METRICS
# ============================================================================


def calculate_diversification_ratio(
    weights: np.ndarray, volatilities: np.ndarray, correlation_matrix: np.ndarray
) -> float:
    """
    Calculate diversification ratio.

    Ratio of weighted average volatility to portfolio volatility.

    Formula:
        DR = (w' × σ) / σ_p

    Args:
        weights: Portfolio weights
        volatilities: Asset volatilities
        correlation_matrix: Correlation matrix

    Returns:
        Diversification ratio (>1 = diversified)
    """
    if len(weights) != len(volatilities):
        return 1.0

    # Weighted average volatility
    weighted_vol = np.dot(weights, volatilities)

    # Portfolio volatility
    cov_matrix = np.outer(volatilities, volatilities) * correlation_matrix
    portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

    if portfolio_vol == 0:
        return 1.0

    return weighted_vol / portfolio_vol


def calculate_turnover(positions: pd.DataFrame, prices: pd.Series) -> float:
    """
    Calculate portfolio turnover.

    Args:
        positions: DataFrame of positions over time
        prices: Series of prices

    Returns:
        Average turnover rate
    """
    if len(positions) < 2:
        return 0.0

    # Calculate position changes
    position_changes = positions.diff().abs()

    # Calculate trade values
    trade_values = position_changes.multiply(prices, axis=0)

    # Average turnover
    avg_turnover = trade_values.sum().mean()

    return avg_turnover


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def get_all_formulas() -> dict:
    """
    Get dictionary of all available formulas.

    Returns:
        Dictionary mapping formula names to functions
    """
    import inspect

    formulas = {}

    for name, obj in globals().items():
        if inspect.isfunction(obj) and not name.startswith("_"):
            formulas[name] = obj

    return formulas


def validate_returns(returns: Union[pd.Series, List[float]], min_length: int = 2) -> bool:
    """
    Validate returns series.

    Args:
        returns: Returns series
        min_length: Minimum required length

    Returns:
        True if valid
    """
    if len(returns) < min_length:
        return False

    if isinstance(returns, (list, np.ndarray)):
        returns = pd.Series(returns)

    if returns.isnull().all():
        return False

    return True
