"""
Extended Indicators for Strategy Builder.

Includes:
- RVI (Relative Volatility Index)
- Linear Regression Channel
- Levels Break (Support/Resistance)
- Accumulation Areas

Session 5.5 Implementation.
"""

from dataclasses import dataclass

import numpy as np

# =============================================================================
# RVI - RELATIVE VOLATILITY INDEX
# =============================================================================

def calculate_rvi(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                  length: int = 10, ma_type: str = "WMA", ma_length: int = 14) -> np.ndarray:
    """
    Calculate Relative Volatility Index (RVI).
    
    RVI measures the direction of volatility on a scale of 0 to 100.
    - Above 50: Volatility is increasing in upward direction
    - Below 50: Volatility is increasing in downward direction
    
    Args:
        close: Close prices
        high: High prices
        low: Low prices
        length: Lookback period for standard deviation
        ma_type: Moving average type (WMA, RMA, SMA, EMA)
        ma_length: MA smoothing period
    
    Returns:
        RVI values (0-100)
    """
    # Calculate standard deviation
    std_dev = np.zeros_like(close)
    for i in range(length - 1, len(close)):
        std_dev[i] = np.std(close[i - length + 1:i + 1])

    # Calculate up and down volatility
    up_vol = np.zeros_like(close)
    down_vol = np.zeros_like(close)

    for i in range(1, len(close)):
        if close[i] > close[i - 1]:
            up_vol[i] = std_dev[i]
            down_vol[i] = 0
        elif close[i] < close[i - 1]:
            up_vol[i] = 0
            down_vol[i] = std_dev[i]
        else:
            up_vol[i] = 0
            down_vol[i] = 0

    # Smooth with selected MA
    if ma_type == "WMA":
        up_smooth = _wma(up_vol, ma_length)
        down_smooth = _wma(down_vol, ma_length)
    elif ma_type == "RMA":
        up_smooth = _rma(up_vol, ma_length)
        down_smooth = _rma(down_vol, ma_length)
    elif ma_type == "SMA":
        up_smooth = _sma(up_vol, ma_length)
        down_smooth = _sma(down_vol, ma_length)
    else:  # EMA
        up_smooth = _ema(up_vol, ma_length)
        down_smooth = _ema(down_vol, ma_length)

    # Calculate RVI
    total = up_smooth + down_smooth
    rvi = np.where(total != 0, 100 * up_smooth / total, 50)

    return rvi


# =============================================================================
# LINEAR REGRESSION CHANNEL
# =============================================================================

def calculate_linear_regression_channel(close: np.ndarray, length: int = 100,
                                         deviation: float = 2.0) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Linear Regression Channel.
    
    Args:
        close: Close prices
        length: Regression period
        deviation: Channel width multiplier
    
    Returns:
        Tuple of (middle_line, upper_channel, lower_channel, slope)
    """
    n = len(close)
    middle = np.zeros(n)
    upper = np.zeros(n)
    lower = np.zeros(n)
    slope = np.zeros(n)

    for i in range(length - 1, n):
        # Get window
        y = close[i - length + 1:i + 1]
        x = np.arange(length)

        # Linear regression
        x_mean = np.mean(x)
        y_mean = np.mean(y)

        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)

        if denominator != 0:
            m = numerator / denominator
            b = y_mean - m * x_mean

            # Calculate regression value at current point
            middle[i] = m * (length - 1) + b
            slope[i] = m

            # Calculate standard deviation from regression line
            predicted = m * x + b
            std = np.std(y - predicted)

            upper[i] = middle[i] + deviation * std
            lower[i] = middle[i] - deviation * std
        else:
            middle[i] = close[i]
            upper[i] = close[i]
            lower[i] = close[i]

    return middle, upper, lower, slope


def linear_regression_filter(close: np.ndarray, config: dict) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply Linear Regression Channel filter.
    
    Args:
        close: Close prices
        config: Configuration with linreg settings
    
    Returns:
        Tuple of (long_signals, short_signals) boolean arrays
    """
    length = config.get('linreg_length', 100)
    deviation = config.get('channel_mult', 2.0)
    breakout_rebound = config.get('linreg_breakout_rebound', 'Breakout')
    slope_direction = config.get('linreg_slope_direction', 'Allow_Any')

    middle, upper, lower, slope = calculate_linear_regression_channel(close, length, deviation)

    n = len(close)
    long_signals = np.zeros(n, dtype=bool)
    short_signals = np.zeros(n, dtype=bool)

    for i in range(length, n):
        # Slope filter
        if slope_direction == 'Follow':
            if slope[i] <= 0:
                continue  # Skip if slope not positive for longs
        elif slope_direction == 'Opposite':
            if slope[i] >= 0:
                continue

        # Breakout or Rebound
        if breakout_rebound == 'Breakout':
            if close[i] > upper[i]:
                long_signals[i] = True
            elif close[i] < lower[i]:
                short_signals[i] = True
        else:  # Rebound
            if close[i] < lower[i]:
                long_signals[i] = True
            elif close[i] > upper[i]:
                short_signals[i] = True

    return long_signals, short_signals


# =============================================================================
# LEVELS BREAK (SUPPORT/RESISTANCE)
# =============================================================================

@dataclass
class PivotLevel:
    """Represents a support/resistance level."""
    price: float
    type: str  # 'support' or 'resistance'
    strength: int  # Number of tests
    bar_index: int  # When it was formed


def find_pivot_points(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                       pivot_bars: int = 10) -> tuple[np.ndarray, np.ndarray]:
    """
    Find pivot highs and lows.
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        pivot_bars: Bars left and right to confirm pivot
    
    Returns:
        Tuple of (pivot_highs, pivot_lows) with prices (0 where no pivot)
    """
    n = len(high)
    pivot_highs = np.zeros(n)
    pivot_lows = np.zeros(n)

    for i in range(pivot_bars, n - pivot_bars):
        # Check pivot high
        is_pivot_high = True
        for j in range(i - pivot_bars, i + pivot_bars + 1):
            if j != i and high[j] >= high[i]:
                is_pivot_high = False
                break

        if is_pivot_high:
            pivot_highs[i] = high[i]

        # Check pivot low
        is_pivot_low = True
        for j in range(i - pivot_bars, i + pivot_bars + 1):
            if j != i and low[j] <= low[i]:
                is_pivot_low = False
                break

        if is_pivot_low:
            pivot_lows[i] = low[i]

    return pivot_highs, pivot_lows


def levels_break_filter(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                        config: dict) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply Levels Break filter for S/R breakouts.
    
    Args:
        high, low, close: Price arrays
        config: Configuration with levels settings
    
    Returns:
        Tuple of (long_signals, short_signals) boolean arrays
    """
    pivot_bars = config.get('levels_pivot_bars', 10)
    search_period = config.get('levels_search_period', 100)
    channel_width = config.get('levels_channel_width', 0.5) / 100  # Convert to decimal
    test_count = config.get('levels_test_count', 2)

    n = len(close)
    long_signals = np.zeros(n, dtype=bool)
    short_signals = np.zeros(n, dtype=bool)

    pivot_highs, pivot_lows = find_pivot_points(high, low, close, pivot_bars)

    for i in range(search_period, n):
        # Find resistance levels in the search window
        for j in range(i - search_period, i):
            if pivot_highs[j] > 0:
                level = pivot_highs[j]
                level_range = level * channel_width

                # Count tests
                tests = 0
                for k in range(j, i):
                    if abs(high[k] - level) <= level_range:
                        tests += 1

                # Check breakout
                if tests >= test_count and close[i] > level + level_range:
                    long_signals[i] = True
                    break

        # Find support levels
        for j in range(i - search_period, i):
            if pivot_lows[j] > 0:
                level = pivot_lows[j]
                level_range = level * channel_width

                tests = 0
                for k in range(j, i):
                    if abs(low[k] - level) <= level_range:
                        tests += 1

                if tests >= test_count and close[i] < level - level_range:
                    short_signals[i] = True
                    break

    return long_signals, short_signals


# =============================================================================
# ACCUMULATION AREAS
# =============================================================================

def find_accumulation_areas(close: np.ndarray, volume: np.ndarray,
                             config: dict) -> tuple[np.ndarray, np.ndarray]:
    """
    Find accumulation/distribution areas.
    
    Accumulation areas are periods of consolidation with high volume,
    typically preceding breakouts.
    
    Args:
        close: Close prices
        volume: Volume data
        config: Configuration with accumulation settings
    
    Returns:
        Tuple of (long_signals, short_signals) on breakout from accumulation
    """
    backtrack = config.get('acc_backtrack_interval', 50)
    min_bars = config.get('acc_min_bars', 3)
    volume_threshold = config.get('volume_threshold', 2.0)
    price_range_pct = config.get('price_range_percent', 1.0) / 100

    n = len(close)
    long_signals = np.zeros(n, dtype=bool)
    short_signals = np.zeros(n, dtype=bool)

    # Calculate average volume
    avg_volume = np.zeros(n)
    for i in range(20, n):
        avg_volume[i] = np.mean(volume[i - 20:i])

    for i in range(backtrack, n):
        # Look for consolidation with high volume
        window_close = close[i - backtrack:i]
        window_volume = volume[i - backtrack:i]

        # Check for consolidation (price in range)
        high_price = np.max(window_close)
        low_price = np.min(window_close)
        mid_price = (high_price + low_price) / 2

        if mid_price == 0:
            continue

        range_pct = (high_price - low_price) / mid_price

        # Check for high volume
        high_vol_bars = np.sum(window_volume > volume_threshold * avg_volume[i - backtrack:i])

        # If consolidation with high volume, check for breakout
        if range_pct <= price_range_pct and high_vol_bars >= min_bars:
            # Breakout detection
            if close[i] > high_price:
                long_signals[i] = True
            elif close[i] < low_price:
                short_signals[i] = True

    return long_signals, short_signals


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _sma(data: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average."""
    result = np.zeros_like(data)
    for i in range(period - 1, len(data)):
        result[i] = np.mean(data[i - period + 1:i + 1])
    return result


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    result = np.zeros_like(data)
    multiplier = 2 / (period + 1)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def _wma(data: np.ndarray, period: int) -> np.ndarray:
    """Weighted Moving Average."""
    result = np.zeros_like(data)
    weights = np.arange(1, period + 1)
    weight_sum = weights.sum()
    for i in range(period - 1, len(data)):
        result[i] = np.sum(data[i - period + 1:i + 1] * weights) / weight_sum
    return result


def _rma(data: np.ndarray, period: int) -> np.ndarray:
    """Running Moving Average (Wilder's smoothing)."""
    result = np.zeros_like(data)
    result[0] = data[0]
    alpha = 1.0 / period
    for i in range(1, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
    return result
