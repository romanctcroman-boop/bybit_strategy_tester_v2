"""
Volatility Indicators
=====================

ATR, Bollinger Bands, Keltner Channels, Donchian Channels, Standard Deviation.

All functions accept numpy arrays and return numpy arrays.
"""

import numpy as np

# =============================================================================
# Average True Range (ATR)
# =============================================================================


def calculate_atr(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """
    Calculate Average True Range (ATR).

    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of closing prices
        period: ATR period (default: 14)

    Returns:
        Array of ATR values
    """
    n = len(close)
    atr = np.full(n, np.nan)

    if n < period + 1:
        return atr

    # True Range components
    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))

    # First TR is just high - low
    tr2[0] = tr1[0]
    tr3[0] = tr1[0]

    # True Range = max of all three
    tr = np.maximum(np.maximum(tr1, tr2), tr3)

    # First ATR is simple average
    atr[period - 1] = np.mean(tr[:period])

    # Wilder's smoothing for subsequent values
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr


# =============================================================================
# Bollinger Bands
# =============================================================================


def calculate_bollinger(
    source: np.ndarray,
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Bollinger Bands.

    Args:
        source: Array of values (typically close prices)
        period: SMA period (default: 20)
        std_dev: Standard deviation multiplier (default: 2.0)

    Returns:
        Tuple of (middle_band, upper_band, lower_band)
    """
    n = len(source)
    middle = np.full(n, np.nan)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)

    if n < period:
        return middle, upper, lower

    for i in range(period - 1, n):
        window = source[i - period + 1 : i + 1]
        sma = np.mean(window)
        std = np.std(window, ddof=0)

        middle[i] = sma
        upper[i] = sma + std_dev * std
        lower[i] = sma - std_dev * std

    return middle, upper, lower


# =============================================================================
# Keltner Channels
# =============================================================================


def calculate_keltner(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 20,
    atr_period: int = 10,
    multiplier: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Keltner Channels.

    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of closing prices
        period: EMA period (default: 20)
        atr_period: ATR period (default: 10)
        multiplier: ATR multiplier (default: 2.0)

    Returns:
        Tuple of (middle_band, upper_band, lower_band)
    """
    from backend.core.indicators.trend import calculate_ema

    # Middle line is EMA of close
    middle = calculate_ema(close, period)

    # ATR for channel width
    atr = calculate_atr(high, low, close, atr_period)

    upper = middle + multiplier * atr
    lower = middle - multiplier * atr

    return middle, upper, lower


# =============================================================================
# Donchian Channels
# =============================================================================


def calculate_donchian(
    high: np.ndarray,
    low: np.ndarray,
    period: int = 20,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Donchian Channels.

    Args:
        high: Array of high prices
        low: Array of low prices
        period: Lookback period (default: 20)

    Returns:
        Tuple of (middle_band, upper_band, lower_band)
    """
    n = len(high)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    middle = np.full(n, np.nan)

    for i in range(period - 1, n):
        upper[i] = np.max(high[i - period + 1 : i + 1])
        lower[i] = np.min(low[i - period + 1 : i + 1])
        middle[i] = (upper[i] + lower[i]) / 2

    return middle, upper, lower


# =============================================================================
# Standard Deviation
# =============================================================================


def calculate_stddev(
    source: np.ndarray,
    period: int = 20,
) -> np.ndarray:
    """
    Calculate Rolling Standard Deviation.

    Args:
        source: Array of values
        period: Lookback period (default: 20)

    Returns:
        Array of standard deviation values
    """
    n = len(source)
    stddev = np.full(n, np.nan)

    for i in range(period - 1, n):
        window = source[i - period + 1 : i + 1]
        stddev[i] = np.std(window, ddof=0)

    return stddev
