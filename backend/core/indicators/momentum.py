"""
Momentum Indicators
===================

RSI, Stochastic, Williams %R, ROC, CMO, MFI, Stoch RSI.

All functions accept numpy arrays and return numpy arrays.
Optimized for performance with optional Numba JIT compilation.
"""


import numpy as np

# Try to import numba for JIT compilation
try:
    from numba import jit, prange

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

    # Fallback decorator that does nothing
    def jit(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    prange = range


# =============================================================================
# RSI (Relative Strength Index)
# =============================================================================


def calculate_rsi(
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """
    Calculate RSI using Wilder's smoothing (EMA-based).

    This is the standard RSI calculation matching TradingView.

    Args:
        close: Array of closing prices
        period: RSI period (default: 14)

    Returns:
        Array of RSI values (0-100). First `period` values are NaN.

    Example:
        >>> close = np.array([44, 44.34, 44.09, 43.61, 44.33, ...])
        >>> rsi = calculate_rsi(close, period=14)
    """
    n = len(close)
    rsi = np.full(n, np.nan)

    if n < period + 1:
        return rsi

    # Price changes
    deltas = np.diff(close)

    # Separate gains and losses
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # Initial averages (SMA for first period)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    # First RSI value
    if avg_loss < 1e-10:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))

    # Wilder's smoothing for remaining values
    # Formula: avg = (prev_avg * (period - 1) + current) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss < 1e-10:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))

    return rsi


@jit(nopython=True, cache=True)
def _calculate_rsi_numba(
    close: np.ndarray,
    period: int,
) -> np.ndarray:
    """Numba-optimized RSI calculation (internal)."""
    n = len(close)
    rsi = np.full(n, np.nan)

    if n < period + 1:
        return rsi

    # Price changes
    gains = np.zeros(n - 1)
    losses = np.zeros(n - 1)

    for i in range(n - 1):
        delta = close[i + 1] - close[i]
        if delta > 0:
            gains[i] = delta
        else:
            losses[i] = -delta

    # Initial averages
    avg_gain = 0.0
    avg_loss = 0.0
    for i in range(period):
        avg_gain += gains[i]
        avg_loss += losses[i]
    avg_gain /= period
    avg_loss /= period

    # First RSI
    if avg_loss < 1e-10:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))

    # Wilder's smoothing
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss < 1e-10:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))

    return rsi


def calculate_rsi_fast(
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """
    Calculate RSI with Numba optimization (if available).

    Falls back to standard implementation if Numba is not installed.

    Args:
        close: Array of closing prices
        period: RSI period (default: 14)

    Returns:
        Array of RSI values (0-100)
    """
    if NUMBA_AVAILABLE:
        return _calculate_rsi_numba(close, period)
    return calculate_rsi(close, period)


# =============================================================================
# Stochastic Oscillator
# =============================================================================


def calculate_stochastic(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    k_period: int = 14,
    d_period: int = 3,
    smooth_k: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculate Stochastic Oscillator (%K and %D).

    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of closing prices
        k_period: Lookback period for %K (default: 14)
        d_period: Smoothing period for %D (default: 3)
        smooth_k: Smoothing period for %K (default: 3)

    Returns:
        Tuple of (%K, %D) arrays
    """
    n = len(close)
    raw_k = np.full(n, np.nan)

    # Calculate raw %K
    for i in range(k_period - 1, n):
        highest_high = np.max(high[i - k_period + 1 : i + 1])
        lowest_low = np.min(low[i - k_period + 1 : i + 1])

        if highest_high - lowest_low > 1e-10:
            raw_k[i] = (close[i] - lowest_low) / (highest_high - lowest_low) * 100
        else:
            raw_k[i] = 50.0  # Default when no range

    # Smooth %K
    k = _sma(raw_k, smooth_k)

    # Calculate %D (SMA of %K)
    d = _sma(k, d_period)

    return k, d


# =============================================================================
# Stochastic RSI
# =============================================================================


def calculate_stoch_rsi(
    close: np.ndarray,
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_period: int = 3,
    d_period: int = 3,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Stochastic RSI.

    Args:
        close: Array of closing prices
        rsi_period: RSI calculation period (default: 14)
        stoch_period: Stochastic lookback period (default: 14)
        k_period: %K smoothing period (default: 3)
        d_period: %D smoothing period (default: 3)

    Returns:
        Tuple of (stoch_rsi, %K, %D) arrays
    """
    # Calculate RSI first
    rsi = calculate_rsi(close, rsi_period)

    n = len(close)
    stoch_rsi = np.full(n, np.nan)

    # Apply Stochastic formula to RSI values
    for i in range(stoch_period - 1, n):
        window = rsi[i - stoch_period + 1 : i + 1]
        if np.all(np.isnan(window)):
            continue

        min_rsi = np.nanmin(window)
        max_rsi = np.nanmax(window)

        if max_rsi - min_rsi > 1e-10:
            stoch_rsi[i] = (rsi[i] - min_rsi) / (max_rsi - min_rsi) * 100
        else:
            stoch_rsi[i] = 50.0

    # Smooth with SMA
    k = _sma(stoch_rsi, k_period)
    d = _sma(k, d_period)

    return stoch_rsi, k, d


# =============================================================================
# Williams %R
# =============================================================================


def calculate_williams_r(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """
    Calculate Williams %R.

    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of closing prices
        period: Lookback period (default: 14)

    Returns:
        Array of Williams %R values (-100 to 0)
    """
    n = len(close)
    williams_r = np.full(n, np.nan)

    for i in range(period - 1, n):
        highest_high = np.max(high[i - period + 1 : i + 1])
        lowest_low = np.min(low[i - period + 1 : i + 1])

        if highest_high - lowest_low > 1e-10:
            williams_r[i] = (highest_high - close[i]) / (highest_high - lowest_low) * -100
        else:
            williams_r[i] = -50.0

    return williams_r


# =============================================================================
# Rate of Change (ROC)
# =============================================================================


def calculate_roc(
    close: np.ndarray,
    period: int = 12,
) -> np.ndarray:
    """
    Calculate Rate of Change (ROC).

    Args:
        close: Array of closing prices
        period: Lookback period (default: 12)

    Returns:
        Array of ROC values (percentage)
    """
    n = len(close)
    roc = np.full(n, np.nan)

    for i in range(period, n):
        if close[i - period] > 1e-10:
            roc[i] = (close[i] - close[i - period]) / close[i - period] * 100
        else:
            roc[i] = 0.0

    return roc


# =============================================================================
# Chande Momentum Oscillator (CMO)
# =============================================================================


def calculate_cmo(
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """
    Calculate Chande Momentum Oscillator (CMO).

    Args:
        close: Array of closing prices
        period: Lookback period (default: 14)

    Returns:
        Array of CMO values (-100 to +100)
    """
    n = len(close)
    cmo = np.full(n, np.nan)

    if n < period + 1:
        return cmo

    # Price changes
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    for i in range(period, n):
        sum_gains = np.sum(gains[i - period : i])
        sum_losses = np.sum(losses[i - period : i])

        if sum_gains + sum_losses > 1e-10:
            cmo[i] = 100 * (sum_gains - sum_losses) / (sum_gains + sum_losses)
        else:
            cmo[i] = 0.0

    return cmo


# =============================================================================
# Money Flow Index (MFI)
# =============================================================================


def calculate_mfi(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """
    Calculate Money Flow Index (MFI).

    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of closing prices
        volume: Array of volume
        period: Lookback period (default: 14)

    Returns:
        Array of MFI values (0-100)
    """
    n = len(close)
    mfi = np.full(n, np.nan)

    if n < period + 1:
        return mfi

    # Typical price
    tp = (high + low + close) / 3

    # Raw money flow
    raw_mf = tp * volume

    # Money flow direction
    pos_mf = np.zeros(n)
    neg_mf = np.zeros(n)

    for i in range(1, n):
        if tp[i] > tp[i - 1]:
            pos_mf[i] = raw_mf[i]
        elif tp[i] < tp[i - 1]:
            neg_mf[i] = raw_mf[i]

    # Calculate MFI
    for i in range(period, n):
        sum_pos = np.sum(pos_mf[i - period + 1 : i + 1])
        sum_neg = np.sum(neg_mf[i - period + 1 : i + 1])

        if sum_neg > 1e-10:
            mf_ratio = sum_pos / sum_neg
            mfi[i] = 100 - (100 / (1 + mf_ratio))
        else:
            mfi[i] = 100.0

    return mfi


# =============================================================================
# Helper Functions
# =============================================================================


def _sma(values: np.ndarray, period: int) -> np.ndarray:
    """Calculate Simple Moving Average (internal helper)."""
    n = len(values)
    result = np.full(n, np.nan)

    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        if not np.all(np.isnan(window)):
            result[i] = np.nanmean(window)

    return result
