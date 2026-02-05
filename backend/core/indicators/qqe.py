"""
QQE Indicator (Quantitative Qualitative Estimation)
====================================================

QQE is a momentum-based indicator that combines RSI smoothing with
ATR-based volatility bands. Developed by Roman Ignatov.

The indicator provides:
- QQE Line (smoothed RSI)
- Upper and Lower bands (ATR-based)
- Histogram showing momentum
- Cross signals for entries

Based on TradingView's QQE indicator implementation.
"""


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


def calculate_qqe(
    close: np.ndarray,
    rsi_period: int = 14,
    smoothing_factor: int = 5,
    qqe_factor: float = 4.236,
) -> dict[str, np.ndarray]:
    """
    Calculate QQE (Quantitative Qualitative Estimation) indicator.

    QQE combines RSI smoothing with ATR-based volatility bands to provide
    momentum signals with reduced noise.

    Args:
        close: Array of closing prices
        rsi_period: RSI period (default: 14)
        smoothing_factor: EMA smoothing factor for RSI (default: 5)
        qqe_factor: Multiplier for ATR bands (default: 4.236)

    Returns:
        Dictionary containing:
            - qqe_line: Main QQE line (smoothed RSI)
            - rsi_ma: RSI moving average
            - upper_band: Upper volatility band
            - lower_band: Lower volatility band
            - histogram: QQE histogram (qqe_line - 50)
            - trend: Trend direction (1 = bullish, -1 = bearish)

    Example:
        >>> close = np.array([100, 101, 102, 101, 103, ...])
        >>> qqe = calculate_qqe(close, rsi_period=14, smoothing_factor=5)
        >>> qqe_line = qqe['qqe_line']
        >>> histogram = qqe['histogram']
    """
    n = len(close)

    # Initialize output arrays
    result = {
        "qqe_line": np.full(n, np.nan),
        "rsi_ma": np.full(n, np.nan),
        "upper_band": np.full(n, np.nan),
        "lower_band": np.full(n, np.nan),
        "histogram": np.full(n, np.nan),
        "trend": np.zeros(n),
    }

    if n < rsi_period + smoothing_factor + 1:
        return result

    # Step 1: Calculate RSI
    rsi = _calculate_rsi(close, rsi_period)

    # Step 2: Apply EMA smoothing to RSI
    rsi_ma = _ema(rsi, smoothing_factor)

    # Step 3: Calculate ATR of RSI for bands
    rsi_atr = _calculate_rsi_atr(rsi_ma, smoothing_factor)

    # Step 4: Calculate QQE lines
    qqe_line = np.full(n, np.nan)
    upper_band = np.full(n, np.nan)
    lower_band = np.full(n, np.nan)
    trend = np.zeros(n)

    # Initialize
    start_idx = rsi_period + smoothing_factor
    if start_idx < n:
        qqe_line[start_idx] = rsi_ma[start_idx]
        upper_band[start_idx] = rsi_ma[start_idx] + qqe_factor * rsi_atr[start_idx]
        lower_band[start_idx] = rsi_ma[start_idx] - qqe_factor * rsi_atr[start_idx]

    # Main loop
    for i in range(start_idx + 1, n):
        if np.isnan(rsi_ma[i]) or np.isnan(rsi_atr[i]):
            continue

        new_upper = rsi_ma[i] + qqe_factor * rsi_atr[i]
        new_lower = rsi_ma[i] - qqe_factor * rsi_atr[i]

        # Trailing stop logic for bands
        if rsi_ma[i - 1] > upper_band[i - 1]:
            upper_band[i] = max(new_upper, upper_band[i - 1])
        else:
            upper_band[i] = new_upper

        if rsi_ma[i - 1] < lower_band[i - 1]:
            lower_band[i] = min(new_lower, lower_band[i - 1])
        else:
            lower_band[i] = new_lower

        # QQE line follows RSI MA with band constraints
        if rsi_ma[i] > upper_band[i - 1]:
            qqe_line[i] = lower_band[i]
            trend[i] = 1  # Bullish
        elif rsi_ma[i] < lower_band[i - 1]:
            qqe_line[i] = upper_band[i]
            trend[i] = -1  # Bearish
        else:
            qqe_line[i] = qqe_line[i - 1]
            trend[i] = trend[i - 1]

    result["qqe_line"] = qqe_line
    result["rsi_ma"] = rsi_ma
    result["upper_band"] = upper_band
    result["lower_band"] = lower_band
    result["histogram"] = rsi_ma - 50  # Distance from neutral line
    result["trend"] = trend

    return result


def calculate_qqe_cross(
    close: np.ndarray,
    rsi_period: int = 14,
    smoothing_factor: int = 5,
    qqe_factor: float = 4.236,
    threshold: float = 10.0,
) -> dict[str, np.ndarray]:
    """
    Calculate QQE with cross signals.

    Args:
        close: Array of closing prices
        rsi_period: RSI period (default: 14)
        smoothing_factor: EMA smoothing factor for RSI (default: 5)
        qqe_factor: Multiplier for ATR bands (default: 4.236)
        threshold: Threshold for signal zone (default: 10)

    Returns:
        Dictionary containing:
            - All outputs from calculate_qqe()
            - buy_signal: Boolean array for buy signals
            - sell_signal: Boolean array for sell signals
    """
    qqe = calculate_qqe(close, rsi_period, smoothing_factor, qqe_factor)
    n = len(close)

    buy_signal = np.zeros(n, dtype=bool)
    sell_signal = np.zeros(n, dtype=bool)

    rsi_ma = qqe["rsi_ma"]
    qqe_line = qqe["qqe_line"]

    for i in range(1, n):
        if np.isnan(rsi_ma[i]) or np.isnan(qqe_line[i]):
            continue
        if np.isnan(rsi_ma[i - 1]) or np.isnan(qqe_line[i - 1]):
            continue

        # Buy signal: RSI MA crosses above QQE line
        if rsi_ma[i - 1] <= qqe_line[i - 1] and rsi_ma[i] > qqe_line[i]:
            buy_signal[i] = True

        # Sell signal: RSI MA crosses below QQE line
        if rsi_ma[i - 1] >= qqe_line[i - 1] and rsi_ma[i] < qqe_line[i]:
            sell_signal[i] = True

    qqe["buy_signal"] = buy_signal
    qqe["sell_signal"] = sell_signal

    return qqe


def _calculate_rsi(close: np.ndarray, period: int) -> np.ndarray:
    """Calculate RSI using Wilder's smoothing."""
    n = len(close)
    rsi = np.full(n, np.nan)

    if n < period + 1:
        return rsi

    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss < 1e-10:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss < 1e-10:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))

    return rsi


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Calculate EMA with NaN handling."""
    n = len(data)
    ema = np.full(n, np.nan)

    # Find first non-NaN value
    first_valid = 0
    for i in range(n):
        if not np.isnan(data[i]):
            first_valid = i
            break
    else:
        return ema

    # Need enough data for EMA
    if first_valid + period > n:
        return ema

    # Initial SMA
    ema[first_valid + period - 1] = np.nanmean(data[first_valid : first_valid + period])

    # EMA calculation
    multiplier = 2.0 / (period + 1)
    for i in range(first_valid + period, n):
        if np.isnan(data[i]):
            ema[i] = ema[i - 1]
        else:
            ema[i] = (data[i] - ema[i - 1]) * multiplier + ema[i - 1]

    return ema


def _calculate_rsi_atr(rsi_ma: np.ndarray, period: int) -> np.ndarray:
    """Calculate ATR-like volatility measure for RSI."""
    n = len(rsi_ma)
    atr = np.full(n, np.nan)

    if n < period + 1:
        return atr

    # True Range equivalent for RSI: absolute change
    tr = np.abs(np.diff(rsi_ma))
    tr = np.concatenate([[np.nan], tr])

    # Wilder's smoothing for ATR
    first_valid = 0
    for i in range(n):
        if not np.isnan(tr[i]):
            first_valid = i
            break

    if first_valid + period > n:
        return atr

    # Initial average
    atr[first_valid + period - 1] = np.nanmean(tr[first_valid : first_valid + period])

    # Wilder's smoothing
    for i in range(first_valid + period, n):
        if np.isnan(tr[i]):
            atr[i] = atr[i - 1]
        else:
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr


# Optimized version with Numba if available
if NUMBA_AVAILABLE:

    @jit(nopython=True, cache=True)
    def _calculate_rsi_numba(close: np.ndarray, period: int) -> np.ndarray:
        """Numba-optimized RSI calculation."""
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
