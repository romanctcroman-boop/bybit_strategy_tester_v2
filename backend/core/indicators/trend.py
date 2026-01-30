"""
Trend Indicators
================

SMA, EMA, WMA, DEMA, TEMA, Hull MA, MACD, Supertrend.

All functions accept numpy arrays and return numpy arrays.
"""

import math

import numpy as np

# =============================================================================
# Simple Moving Average (SMA)
# =============================================================================


def calculate_sma(
    source: np.ndarray,
    period: int = 20,
) -> np.ndarray:
    """
    Calculate Simple Moving Average.

    Args:
        source: Array of values (typically close prices)
        period: Lookback period (default: 20)

    Returns:
        Array of SMA values. First `period-1` values are NaN.
    """
    n = len(source)
    sma = np.full(n, np.nan)

    if n < period:
        return sma

    # Use cumsum for efficient calculation
    cumsum = np.cumsum(source)
    sma[period - 1 :] = (cumsum[period - 1 :] - np.concatenate([[0], cumsum[:-period]])) / period

    return sma


# =============================================================================
# Exponential Moving Average (EMA)
# =============================================================================


def calculate_ema(
    source: np.ndarray,
    period: int = 20,
) -> np.ndarray:
    """
    Calculate Exponential Moving Average.

    Args:
        source: Array of values (typically close prices)
        period: Lookback period (default: 20)

    Returns:
        Array of EMA values
    """
    n = len(source)

    if n < period:
        return np.full(n, np.nan)

    alpha = 2 / (period + 1)
    ema = np.zeros(n, dtype=float)

    # Initialize with first value
    ema[0] = source[0]

    # EMA calculation
    for i in range(1, n):
        ema[i] = alpha * source[i] + (1 - alpha) * ema[i - 1]

    return ema


# =============================================================================
# Weighted Moving Average (WMA)
# =============================================================================


def calculate_wma(
    source: np.ndarray,
    period: int = 20,
) -> np.ndarray:
    """
    Calculate Weighted Moving Average.

    Args:
        source: Array of values
        period: Lookback period (default: 20)

    Returns:
        Array of WMA values
    """
    n = len(source)
    wma = np.full(n, np.nan)

    if n < period:
        return wma

    weights = np.arange(1, period + 1, dtype=float)
    weights_sum = weights.sum()

    for i in range(period - 1, n):
        wma[i] = np.sum(weights * source[i - period + 1 : i + 1]) / weights_sum

    return wma


# =============================================================================
# Double Exponential Moving Average (DEMA)
# =============================================================================


def calculate_dema(
    source: np.ndarray,
    period: int = 20,
) -> np.ndarray:
    """
    Calculate Double Exponential Moving Average.

    DEMA = 2 * EMA(source) - EMA(EMA(source))

    Args:
        source: Array of values
        period: Lookback period (default: 20)

    Returns:
        Array of DEMA values
    """
    ema1 = calculate_ema(source, period)
    ema2 = calculate_ema(ema1, period)
    return 2 * ema1 - ema2


# =============================================================================
# Triple Exponential Moving Average (TEMA)
# =============================================================================


def calculate_tema(
    source: np.ndarray,
    period: int = 20,
) -> np.ndarray:
    """
    Calculate Triple Exponential Moving Average.

    TEMA = 3 * EMA1 - 3 * EMA2 + EMA3

    Args:
        source: Array of values
        period: Lookback period (default: 20)

    Returns:
        Array of TEMA values
    """
    ema1 = calculate_ema(source, period)
    ema2 = calculate_ema(ema1, period)
    ema3 = calculate_ema(ema2, period)
    return 3 * ema1 - 3 * ema2 + ema3


# =============================================================================
# Hull Moving Average (HMA)
# =============================================================================


def calculate_hull_ma(
    source: np.ndarray,
    period: int = 20,
) -> np.ndarray:
    """
    Calculate Hull Moving Average.

    HMA = WMA(2 * WMA(n/2) - WMA(n), sqrt(n))

    Args:
        source: Array of values
        period: Lookback period (default: 20)

    Returns:
        Array of HMA values
    """
    half_period = max(1, period // 2)
    sqrt_period = max(1, int(math.sqrt(period)))

    wma_half = calculate_wma(source, half_period)
    wma_full = calculate_wma(source, period)

    raw_hma = 2 * wma_half - wma_full
    hma = calculate_wma(raw_hma, sqrt_period)

    return hma


# =============================================================================
# MACD (Moving Average Convergence Divergence)
# =============================================================================


def calculate_macd(
    source: np.ndarray,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Args:
        source: Array of values (typically close prices)
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)

    Returns:
        Tuple of (macd_line, signal_line, histogram)
    """
    fast_ema = calculate_ema(source, fast_period)
    slow_ema = calculate_ema(source, slow_period)

    macd_line = fast_ema - slow_ema
    signal_line = calculate_ema(macd_line, signal_period)
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


# =============================================================================
# Supertrend
# =============================================================================


def calculate_supertrend(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 10,
    multiplier: float = 3.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculate Supertrend indicator.

    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of closing prices
        period: ATR period (default: 10)
        multiplier: ATR multiplier (default: 3.0)

    Returns:
        Tuple of (supertrend_line, direction)
        direction: 1 for uptrend, -1 for downtrend
    """
    from backend.core.indicators.volatility import calculate_atr

    n = len(close)
    supertrend = np.zeros(n)
    direction = np.zeros(n)

    # Calculate ATR
    atr = calculate_atr(high, low, close, period)

    # Calculate basic upper and lower bands
    hl2 = (high + low) / 2
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    # Initialize
    final_upper = np.copy(basic_upper)
    final_lower = np.copy(basic_lower)

    for i in range(1, n):
        # Final upper band
        if basic_upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i - 1]

        # Final lower band
        if basic_lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i - 1]

    # Calculate Supertrend
    for i in range(1, n):
        if i == 1:
            if close[i] <= final_upper[i]:
                supertrend[i] = final_upper[i]
                direction[i] = -1
            else:
                supertrend[i] = final_lower[i]
                direction[i] = 1
        else:
            if direction[i - 1] == -1:  # Previous was downtrend
                if close[i] > final_upper[i]:
                    supertrend[i] = final_lower[i]
                    direction[i] = 1
                else:
                    supertrend[i] = final_upper[i]
                    direction[i] = -1
            else:  # Previous was uptrend
                if close[i] < final_lower[i]:
                    supertrend[i] = final_upper[i]
                    direction[i] = -1
                else:
                    supertrend[i] = final_lower[i]
                    direction[i] = 1

    return supertrend, direction
