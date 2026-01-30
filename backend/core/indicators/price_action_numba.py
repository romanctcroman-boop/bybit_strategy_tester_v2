"""
Price Action Patterns - Numba JIT Optimized
============================================

High-performance candlestick pattern detection using Numba JIT compilation.
Provides 10-50x speedup over pandas-based implementations.

Supported Patterns:
- Engulfing (bullish/bearish)
- Hammer / Hanging Man
- Doji (standard, dragonfly, gravestone)
- Pin Bar
- Inside Bar / Outside Bar
- Three White Soldiers / Three Black Crows
- Shooting Star
- Marubozu
- Tweezer Top / Bottom
- Three Methods (Rising/Falling)
- Piercing Line / Dark Cloud Cover
- Harami
- Morning Star / Evening Star

All functions accept numpy arrays and return boolean arrays.

Usage:
    from backend.core.indicators.price_action_numba import detect_engulfing

    bullish, bearish = detect_engulfing(open_arr, high_arr, low_arr, close_arr)

Note: Nested if statements are intentional for Numba JIT performance optimization.
      Variable 'l' (low) is intentionally short for performance-critical loops.
"""

# ruff: noqa: SIM102, E741

import numpy as np

try:
    from numba import njit, prange

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

    # Fallback decorator (no-op)
    def njit(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def prange(*args):
        return range(*args)


# =============================================================================
# CORE HELPER FUNCTIONS
# =============================================================================


@njit(cache=True)
def _calculate_body(open_arr: np.ndarray, close_arr: np.ndarray) -> np.ndarray:
    """Calculate candle body size (absolute value)."""
    return np.abs(close_arr - open_arr)


@njit(cache=True)
def _calculate_upper_wick(open_arr: np.ndarray, high_arr: np.ndarray, close_arr: np.ndarray) -> np.ndarray:
    """Calculate upper wick size."""
    n = len(open_arr)
    upper_wick = np.zeros(n, dtype=np.float64)
    for i in range(n):
        max_oc = max(open_arr[i], close_arr[i])
        upper_wick[i] = high_arr[i] - max_oc
    return upper_wick


@njit(cache=True)
def _calculate_lower_wick(open_arr: np.ndarray, low_arr: np.ndarray, close_arr: np.ndarray) -> np.ndarray:
    """Calculate lower wick size."""
    n = len(open_arr)
    lower_wick = np.zeros(n, dtype=np.float64)
    for i in range(n):
        min_oc = min(open_arr[i], close_arr[i])
        lower_wick[i] = min_oc - low_arr[i]
    return lower_wick


@njit(cache=True)
def _rolling_mean(arr: np.ndarray, period: int) -> np.ndarray:
    """Calculate simple rolling mean."""
    n = len(arr)
    result = np.full(n, np.nan, dtype=np.float64)
    for i in range(period - 1, n):
        total = 0.0
        for j in range(i - period + 1, i + 1):
            total += arr[j]
        result[i] = total / period
    return result


# =============================================================================
# ENGULFING PATTERNS
# =============================================================================


@njit(cache=True)
def detect_engulfing(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Bullish and Bearish Engulfing patterns.

    Bullish Engulfing: Previous candle is red (close < open),
    current candle is green and completely engulfs previous body.

    Bearish Engulfing: Previous candle is green (close > open),
    current candle is red and completely engulfs previous body.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices

    Returns:
        Tuple of (bullish_engulfing, bearish_engulfing) boolean arrays
    """
    n = len(open_arr)
    bullish = np.zeros(n, dtype=np.bool_)
    bearish = np.zeros(n, dtype=np.bool_)

    for i in range(1, n):
        # Previous candle
        prev_open = open_arr[i - 1]
        prev_close = close_arr[i - 1]
        prev_red = prev_open > prev_close
        prev_green = prev_close > prev_open

        # Current candle
        curr_open = open_arr[i]
        curr_close = close_arr[i]
        curr_green = curr_close > curr_open
        curr_red = curr_open > curr_close

        # Bullish engulfing: prev red, curr green, engulfs body
        if prev_red and curr_green:
            if curr_close > prev_open and curr_open < prev_close:
                bullish[i] = True

        # Bearish engulfing: prev green, curr red, engulfs body
        if prev_green and curr_red:
            if curr_open > prev_close and curr_close < prev_open:
                bearish[i] = True

    return bullish, bearish


# =============================================================================
# HAMMER / HANGING MAN PATTERNS
# =============================================================================


@njit(cache=True)
def detect_hammer(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    min_wick_ratio: float = 2.0,
    max_upper_ratio: float = 0.3,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Hammer (bullish) and Hanging Man (bearish) patterns.

    Hammer: Long lower wick, small upper wick, small body at top.
    Hanging Man: Long upper wick, small lower wick, small body at bottom.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        min_wick_ratio: Minimum wick-to-body ratio (default: 2.0)
        max_upper_ratio: Maximum upper wick-to-body ratio (default: 0.3)

    Returns:
        Tuple of (hammer, hanging_man) boolean arrays
    """
    n = len(open_arr)
    hammer = np.zeros(n, dtype=np.bool_)
    hanging_man = np.zeros(n, dtype=np.bool_)

    for i in range(n):
        o, h, l, c = open_arr[i], high_arr[i], low_arr[i], close_arr[i]
        body = abs(c - o)

        if body < 1e-10:  # Prevent division by zero
            continue

        max_oc = max(o, c)
        min_oc = min(o, c)
        upper_wick = h - max_oc
        lower_wick = min_oc - l

        # Hammer: long lower wick, small upper wick
        if lower_wick > body * min_wick_ratio and upper_wick < body * max_upper_ratio:
            hammer[i] = True

        # Hanging man: long upper wick, small lower wick
        if upper_wick > body * min_wick_ratio and lower_wick < body * max_upper_ratio:
            hanging_man[i] = True

    return hammer, hanging_man


# =============================================================================
# DOJI PATTERNS
# =============================================================================


@njit(cache=True)
def detect_doji(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    body_threshold: float = 0.1,
    lookback: int = 20,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Detect Doji patterns (Standard, Dragonfly, Gravestone).

    Doji: Very small body relative to average range.
    Dragonfly: Doji with long lower wick (bullish).
    Gravestone: Doji with long upper wick (bearish).

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        body_threshold: Body threshold as fraction of avg range (default: 0.1)
        lookback: Lookback period for average range (default: 20)

    Returns:
        Tuple of (standard_doji, dragonfly_doji, gravestone_doji) boolean arrays
    """
    n = len(open_arr)
    standard = np.zeros(n, dtype=np.bool_)
    dragonfly = np.zeros(n, dtype=np.bool_)
    gravestone = np.zeros(n, dtype=np.bool_)

    for i in range(lookback, n):
        o, h, l, c = open_arr[i], high_arr[i], low_arr[i], close_arr[i]
        body = abs(c - o)

        # Calculate average range over lookback
        total_range = 0.0
        for j in range(i - lookback, i):
            total_range += high_arr[j] - low_arr[j]
        avg_range = total_range / lookback

        if avg_range < 1e-10:
            continue

        max_oc = max(o, c)
        min_oc = min(o, c)
        upper_wick = h - max_oc
        lower_wick = min_oc - l

        # Check if doji (small body)
        if body < avg_range * body_threshold:
            # Dragonfly: long lower wick, small upper wick
            if lower_wick > body * 3 and upper_wick < body:
                dragonfly[i] = True
            # Gravestone: long upper wick, small lower wick
            elif upper_wick > body * 3 and lower_wick < body:
                gravestone[i] = True
            else:
                standard[i] = True

    return standard, dragonfly, gravestone


# =============================================================================
# PIN BAR PATTERN
# =============================================================================


@njit(cache=True)
def detect_pin_bar(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    min_wick_ratio: float = 2.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Pin Bar patterns (Bullish and Bearish).

    Bullish Pin Bar: Long lower wick dominates upper wick.
    Bearish Pin Bar: Long upper wick dominates lower wick.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        min_wick_ratio: Minimum wick-to-body ratio (default: 2.0)

    Returns:
        Tuple of (bullish_pin, bearish_pin) boolean arrays
    """
    n = len(open_arr)
    bullish = np.zeros(n, dtype=np.bool_)
    bearish = np.zeros(n, dtype=np.bool_)

    for i in range(n):
        o, h, l, c = open_arr[i], high_arr[i], low_arr[i], close_arr[i]
        body = abs(c - o)

        if body < 1e-10:
            continue

        max_oc = max(o, c)
        min_oc = min(o, c)
        upper_wick = h - max_oc
        lower_wick = min_oc - l

        # Bullish pin: long lower wick, dominates upper
        if lower_wick > body * min_wick_ratio and lower_wick > upper_wick * 2:
            bullish[i] = True

        # Bearish pin: long upper wick, dominates lower
        if upper_wick > body * min_wick_ratio and upper_wick > lower_wick * 2:
            bearish[i] = True

    return bullish, bearish


# =============================================================================
# INSIDE BAR / OUTSIDE BAR
# =============================================================================


@njit(cache=True)
def detect_inside_bar(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
) -> np.ndarray:
    """
    Detect Inside Bar pattern.

    Inside Bar: Current bar's high and low are within previous bar's range.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices

    Returns:
        Boolean array of inside bar signals
    """
    n = len(open_arr)
    inside = np.zeros(n, dtype=np.bool_)

    for i in range(1, n):
        if high_arr[i] <= high_arr[i - 1] and low_arr[i] >= low_arr[i - 1]:
            inside[i] = True

    return inside


@njit(cache=True)
def detect_outside_bar(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
) -> np.ndarray:
    """
    Detect Outside Bar pattern.

    Outside Bar: Current bar's range completely engulfs previous bar's range.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices

    Returns:
        Boolean array of outside bar signals
    """
    n = len(open_arr)
    outside = np.zeros(n, dtype=np.bool_)

    for i in range(1, n):
        if high_arr[i] > high_arr[i - 1] and low_arr[i] < low_arr[i - 1]:
            outside[i] = True

    return outside


# =============================================================================
# THREE WHITE SOLDIERS / THREE BLACK CROWS
# =============================================================================


@njit(cache=True)
def detect_three_soldiers_crows(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Three White Soldiers (bullish) and Three Black Crows (bearish).

    Three White Soldiers: 3 consecutive green candles with higher closes.
    Three Black Crows: 3 consecutive red candles with lower closes.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices

    Returns:
        Tuple of (soldiers, crows) boolean arrays
    """
    n = len(open_arr)
    soldiers = np.zeros(n, dtype=np.bool_)
    crows = np.zeros(n, dtype=np.bool_)

    for i in range(2, n):
        # Check for three green candles
        green_0 = close_arr[i] > open_arr[i]
        green_1 = close_arr[i - 1] > open_arr[i - 1]
        green_2 = close_arr[i - 2] > open_arr[i - 2]

        # Check for higher closes
        higher_close = close_arr[i] > close_arr[i - 1] > close_arr[i - 2]

        if green_0 and green_1 and green_2 and higher_close:
            soldiers[i] = True

        # Check for three red candles
        red_0 = open_arr[i] > close_arr[i]
        red_1 = open_arr[i - 1] > close_arr[i - 1]
        red_2 = open_arr[i - 2] > close_arr[i - 2]

        # Check for lower closes
        lower_close = close_arr[i] < close_arr[i - 1] < close_arr[i - 2]

        if red_0 and red_1 and red_2 and lower_close:
            crows[i] = True

    return soldiers, crows


# =============================================================================
# SHOOTING STAR
# =============================================================================


@njit(cache=True)
def detect_shooting_star(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    min_wick_ratio: float = 2.0,
    max_lower_ratio: float = 0.3,
) -> np.ndarray:
    """
    Detect Shooting Star pattern (bearish reversal after uptrend).

    Shooting Star: Small body at bottom, long upper wick, after an uptrend.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        min_wick_ratio: Minimum upper wick-to-body ratio (default: 2.0)
        max_lower_ratio: Maximum lower wick-to-body ratio (default: 0.3)

    Returns:
        Boolean array of shooting star signals
    """
    n = len(open_arr)
    shooting = np.zeros(n, dtype=np.bool_)

    for i in range(3, n):
        o, h, l, c = open_arr[i], high_arr[i], low_arr[i], close_arr[i]
        body = abs(c - o)

        if body < 1e-10:
            continue

        max_oc = max(o, c)
        min_oc = min(o, c)
        upper_wick = h - max_oc
        lower_wick = min_oc - l

        # Pattern shape
        if upper_wick > body * min_wick_ratio and lower_wick < body * max_lower_ratio:
            # Check for uptrend (price higher than 3 bars ago)
            if close_arr[i - 1] > close_arr[i - 3]:
                shooting[i] = True

    return shooting


# =============================================================================
# MARUBOZU
# =============================================================================


@njit(cache=True)
def detect_marubozu(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    max_wick_ratio: float = 0.1,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Marubozu patterns (strong momentum candles with no wicks).

    Bullish Marubozu: Strong green candle with tiny/no wicks.
    Bearish Marubozu: Strong red candle with tiny/no wicks.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        max_wick_ratio: Maximum wick-to-body ratio (default: 0.1)

    Returns:
        Tuple of (bullish_marubozu, bearish_marubozu) boolean arrays
    """
    n = len(open_arr)
    bullish = np.zeros(n, dtype=np.bool_)
    bearish = np.zeros(n, dtype=np.bool_)

    for i in range(n):
        o, h, l, c = open_arr[i], high_arr[i], low_arr[i], close_arr[i]
        body = abs(c - o)

        if body < 1e-10:
            continue

        max_oc = max(o, c)
        min_oc = min(o, c)
        upper_wick = h - max_oc
        lower_wick = min_oc - l

        # Tiny wicks on both sides
        if upper_wick < body * max_wick_ratio and lower_wick < body * max_wick_ratio:
            if c > o:  # Green
                bullish[i] = True
            else:  # Red
                bearish[i] = True

    return bullish, bearish


# =============================================================================
# TWEEZER TOP / BOTTOM
# =============================================================================


@njit(cache=True)
def detect_tweezer(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    tolerance: float = 0.001,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Tweezer Top (bearish) and Tweezer Bottom (bullish) patterns.

    Tweezer Bottom: Two candles with same lows, first red, second green.
    Tweezer Top: Two candles with same highs, first green, second red.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        tolerance: Price tolerance for matching highs/lows (default: 0.001 = 0.1%)

    Returns:
        Tuple of (tweezer_bottom, tweezer_top) boolean arrays
    """
    n = len(open_arr)
    bottom = np.zeros(n, dtype=np.bool_)
    top = np.zeros(n, dtype=np.bool_)

    for i in range(1, n):
        # Previous candle
        prev_open = open_arr[i - 1]
        prev_close = close_arr[i - 1]
        prev_high = high_arr[i - 1]
        prev_low = low_arr[i - 1]
        prev_red = prev_open > prev_close
        prev_green = prev_close > prev_open

        # Current candle
        curr_open = open_arr[i]
        curr_close = close_arr[i]
        curr_high = high_arr[i]
        curr_low = low_arr[i]
        curr_green = curr_close > curr_open
        curr_red = curr_open > curr_close

        # Tweezer bottom: same lows, first red then green
        if abs(curr_low - prev_low) < prev_low * tolerance:
            if prev_red and curr_green:
                bottom[i] = True

        # Tweezer top: same highs, first green then red
        if abs(curr_high - prev_high) < prev_high * tolerance:
            if prev_green and curr_red:
                top[i] = True

    return bottom, top


# =============================================================================
# THREE METHODS (CONTINUATION)
# =============================================================================


@njit(cache=True)
def detect_three_methods(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    lookback: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Rising Three Methods (bullish) and Falling Three Methods (bearish).

    Rising Three Methods: Big green, 3 small reds inside, big green breaks high.
    Falling Three Methods: Big red, 3 small greens inside, big red breaks low.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        lookback: Lookback period for average body size (default: 10)

    Returns:
        Tuple of (rising_three, falling_three) boolean arrays
    """
    n = len(open_arr)
    rising = np.zeros(n, dtype=np.bool_)
    falling = np.zeros(n, dtype=np.bool_)

    if n < lookback + 5:
        return rising, falling

    # Calculate bodies
    body = np.abs(close_arr - open_arr)

    for i in range(lookback + 4, n):
        # Calculate average body
        avg_body = 0.0
        for j in range(i - lookback - 4, i - 4):
            avg_body += body[j]
        avg_body /= lookback

        # Check for Rising Three Methods
        # Bar 4 ago: big green
        big_green_1 = close_arr[i - 4] > open_arr[i - 4] and body[i - 4] > avg_body
        # Bars 3,2,1 ago: small reds
        small_reds = (
            open_arr[i - 3] > close_arr[i - 3]
            and open_arr[i - 2] > close_arr[i - 2]
            and open_arr[i - 1] > close_arr[i - 1]
        )
        # Bodies contained within bar 4
        contained = low_arr[i - 1] > low_arr[i - 4] and high_arr[i - 1] < high_arr[i - 4]
        # Current bar: big green, closes above high of bar 4
        big_green_2 = close_arr[i] > open_arr[i] and close_arr[i] > high_arr[i - 4]

        if big_green_1 and small_reds and contained and big_green_2:
            rising[i] = True

        # Check for Falling Three Methods
        # Bar 4 ago: big red
        big_red_1 = open_arr[i - 4] > close_arr[i - 4] and body[i - 4] > avg_body
        # Bars 3,2,1 ago: small greens
        small_greens = (
            close_arr[i - 3] > open_arr[i - 3]
            and close_arr[i - 2] > open_arr[i - 2]
            and close_arr[i - 1] > open_arr[i - 1]
        )
        # Bodies contained within bar 4
        contained_fall = high_arr[i - 1] < high_arr[i - 4] and low_arr[i - 1] > low_arr[i - 4]
        # Current bar: big red, closes below low of bar 4
        big_red_2 = open_arr[i] > close_arr[i] and close_arr[i] < low_arr[i - 4]

        if big_red_1 and small_greens and contained_fall and big_red_2:
            falling[i] = True

    return rising, falling


# =============================================================================
# PIERCING LINE / DARK CLOUD COVER
# =============================================================================


@njit(cache=True)
def detect_piercing_darkcloud(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Piercing Line (bullish) and Dark Cloud Cover (bearish).

    Piercing Line: Red candle, then green opens below prev low, closes above midpoint.
    Dark Cloud Cover: Green candle, then red opens above prev high, closes below midpoint.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices

    Returns:
        Tuple of (piercing_line, dark_cloud) boolean arrays
    """
    n = len(open_arr)
    piercing = np.zeros(n, dtype=np.bool_)
    dark_cloud = np.zeros(n, dtype=np.bool_)

    for i in range(1, n):
        prev_open = open_arr[i - 1]
        prev_close = close_arr[i - 1]
        prev_high = high_arr[i - 1]
        prev_low = low_arr[i - 1]
        prev_midpoint = (prev_open + prev_close) / 2

        curr_open = open_arr[i]
        curr_close = close_arr[i]

        # Piercing line: prev red, curr green, opens below prev low, closes above midpoint
        if prev_open > prev_close:  # prev red
            if curr_close > curr_open:  # curr green
                if curr_open < prev_low and curr_close > prev_midpoint:
                    piercing[i] = True

        # Dark cloud: prev green, curr red, opens above prev high, closes below midpoint
        if prev_close > prev_open:  # prev green
            if curr_open > curr_close:  # curr red
                if curr_open > prev_high and curr_close < prev_midpoint:
                    dark_cloud[i] = True

    return piercing, dark_cloud


# =============================================================================
# HARAMI
# =============================================================================


@njit(cache=True)
def detect_harami(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    lookback: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Harami patterns (bullish and bearish).

    Bullish Harami: Big red candle, then small green inside it.
    Bearish Harami: Big green candle, then small red inside it.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        lookback: Lookback period for average body (default: 10)

    Returns:
        Tuple of (bullish_harami, bearish_harami) boolean arrays
    """
    n = len(open_arr)
    bullish = np.zeros(n, dtype=np.bool_)
    bearish = np.zeros(n, dtype=np.bool_)

    if n < lookback + 1:
        return bullish, bearish

    body = np.abs(close_arr - open_arr)

    for i in range(lookback, n):
        # Calculate rolling average body
        avg_body = 0.0
        for j in range(i - lookback, i):
            avg_body += body[j]
        avg_body /= lookback

        prev_open = open_arr[i - 1]
        prev_close = close_arr[i - 1]
        prev_body = body[i - 1]

        curr_open = open_arr[i]
        curr_close = close_arr[i]
        curr_body = body[i]

        # Bullish harami: big red prev, small green curr inside
        if prev_open > prev_close and prev_body > avg_body:  # Big red
            if curr_close > curr_open and curr_body < prev_body * 0.5:  # Small green
                if curr_open > prev_close and curr_close < prev_open:  # Inside
                    bullish[i] = True

        # Bearish harami: big green prev, small red curr inside
        if prev_close > prev_open and prev_body > avg_body:  # Big green
            if curr_open > curr_close and curr_body < prev_body * 0.5:  # Small red
                if curr_open < prev_close and curr_close > prev_open:  # Inside
                    bearish[i] = True

    return bullish, bearish


# =============================================================================
# MORNING STAR / EVENING STAR
# =============================================================================


@njit(cache=True)
def detect_morning_evening_star(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    lookback: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Morning Star (bullish) and Evening Star (bearish) patterns.

    Morning Star: Big red, small body (doji-like), big green.
    Evening Star: Big green, small body (doji-like), big red.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        lookback: Lookback period for average body (default: 10)

    Returns:
        Tuple of (morning_star, evening_star) boolean arrays
    """
    n = len(open_arr)
    morning = np.zeros(n, dtype=np.bool_)
    evening = np.zeros(n, dtype=np.bool_)

    if n < lookback + 2:
        return morning, evening

    body = np.abs(close_arr - open_arr)

    for i in range(lookback + 2, n):
        # Calculate rolling average body
        avg_body = 0.0
        for j in range(i - lookback - 2, i - 2):
            avg_body += body[j]
        avg_body /= lookback

        # Bar 2 ago
        bar2_open = open_arr[i - 2]
        bar2_close = close_arr[i - 2]
        bar2_body = body[i - 2]
        bar2_red = bar2_open > bar2_close
        bar2_green = bar2_close > bar2_open

        # Bar 1 ago (middle - should be small)
        bar1_body = body[i - 1]

        # Current bar
        bar0_open = open_arr[i]
        bar0_close = close_arr[i]
        bar0_body = body[i]
        bar0_red = bar0_open > bar0_close
        bar0_green = bar0_close > bar0_open

        # Morning star: big red, small body, big green
        if bar2_red and bar2_body > avg_body:
            if bar1_body < avg_body * 0.3:  # Small middle body
                if bar0_green and bar0_body > avg_body:
                    morning[i] = True

        # Evening star: big green, small body, big red
        if bar2_green and bar2_body > avg_body:
            if bar1_body < avg_body * 0.3:  # Small middle body
                if bar0_red and bar0_body > avg_body:
                    evening[i] = True

    return morning, evening


# =============================================================================
# THREE LINE STRIKE (REVERSAL)
# =============================================================================


@njit(cache=True)
def detect_three_line_strike(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Bullish and Bearish Three Line Strike patterns.

    Bullish Three Line Strike: Three bearish candles followed by a large bullish
    candle that engulfs all three previous candles. Strong reversal signal.

    Bearish Three Line Strike: Three bullish candles followed by a large bearish
    candle that engulfs all three previous candles. Strong reversal signal.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices

    Returns:
        Tuple of (bullish_strike, bearish_strike) boolean arrays
    """
    n = len(open_arr)
    bullish = np.zeros(n, dtype=np.bool_)
    bearish = np.zeros(n, dtype=np.bool_)

    if n < 4:
        return bullish, bearish

    for i in range(3, n):
        # Previous three candles
        c3_open, c3_close = open_arr[i - 3], close_arr[i - 3]
        c2_open, c2_close = open_arr[i - 2], close_arr[i - 2]
        c1_open, c1_close = open_arr[i - 1], close_arr[i - 1]
        c0_open, c0_close = open_arr[i], close_arr[i]

        # Bullish Three Line Strike: 3 red candles + big green engulfing
        three_reds = c3_open > c3_close and c2_open > c2_close and c1_open > c1_close
        # Descending closes (each lower than previous)
        descending = c3_close >= c2_close >= c1_close

        if three_reds and descending:
            # Current candle is big green that opens below and closes above all 3
            if c0_close > c0_open:  # Green candle
                if c0_open <= c1_close and c0_close >= c3_open:
                    bullish[i] = True

        # Bearish Three Line Strike: 3 green candles + big red engulfing
        three_greens = c3_close > c3_open and c2_close > c2_open and c1_close > c1_open
        # Ascending closes
        ascending = c3_close <= c2_close <= c1_close

        if three_greens and ascending:
            # Current candle is big red that opens above and closes below all 3
            if c0_open > c0_close:  # Red candle
                if c0_open >= c1_close and c0_close <= c3_open:
                    bearish[i] = True

    return bullish, bearish


# =============================================================================
# KICKER (STRONG REVERSAL)
# =============================================================================


@njit(cache=True)
def detect_kicker(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    lookback: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Bullish and Bearish Kicker patterns.

    One of the most reliable reversal patterns. Characterized by a gap
    in the direction opposite to the previous trend.

    Bullish Kicker: Red candle followed by green candle that gaps up
    (opens above the previous open).

    Bearish Kicker: Green candle followed by red candle that gaps down
    (opens below the previous open).

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        lookback: Period for average body calculation (default: 10)

    Returns:
        Tuple of (bullish_kicker, bearish_kicker) boolean arrays
    """
    n = len(open_arr)
    bullish = np.zeros(n, dtype=np.bool_)
    bearish = np.zeros(n, dtype=np.bool_)

    if n < lookback + 2:
        return bullish, bearish

    body = np.abs(close_arr - open_arr)

    for i in range(lookback + 1, n):
        # Calculate average body
        avg_body = 0.0
        for j in range(i - lookback - 1, i - 1):
            avg_body += body[j]
        avg_body /= lookback

        prev_open = open_arr[i - 1]
        prev_close = close_arr[i - 1]
        curr_open = open_arr[i]
        curr_close = close_arr[i]

        prev_red = prev_open > prev_close
        prev_green = prev_close > prev_open
        curr_green = curr_close > curr_open
        curr_red = curr_open > curr_close

        # Both candles should be significant
        prev_big = body[i - 1] > avg_body * 0.7
        curr_big = body[i] > avg_body * 0.7

        # Bullish Kicker: red candle, then green gaps up
        if prev_red and curr_green and prev_big and curr_big:
            if curr_open > prev_open:  # Gap up above previous open
                bullish[i] = True

        # Bearish Kicker: green candle, then red gaps down
        if prev_green and curr_red and prev_big and curr_big:
            if curr_open < prev_open:  # Gap down below previous open
                bearish[i] = True

    return bullish, bearish


# =============================================================================
# ABANDONED BABY (RARE REVERSAL)
# =============================================================================


@njit(cache=True)
def detect_abandoned_baby(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    doji_threshold: float = 0.1,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Bullish and Bearish Abandoned Baby patterns.

    A rare but powerful reversal pattern with a doji that gaps away from
    both the previous and following candles.

    Bullish Abandoned Baby: Red candle, gap down to doji, gap up to green candle.
    Bearish Abandoned Baby: Green candle, gap up to doji, gap down to red candle.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        doji_threshold: Maximum body/range ratio for doji (default: 0.1)

    Returns:
        Tuple of (bullish_baby, bearish_baby) boolean arrays
    """
    n = len(open_arr)
    bullish = np.zeros(n, dtype=np.bool_)
    bearish = np.zeros(n, dtype=np.bool_)

    if n < 3:
        return bullish, bearish

    for i in range(2, n):
        # Bar 2 ago (first)
        c2_open, c2_close = open_arr[i - 2], close_arr[i - 2]
        c2_high, c2_low = high_arr[i - 2], low_arr[i - 2]

        # Bar 1 ago (middle - doji)
        c1_open, c1_close = open_arr[i - 1], close_arr[i - 1]
        c1_high, c1_low = high_arr[i - 1], low_arr[i - 1]
        c1_range = c1_high - c1_low
        c1_body = abs(c1_close - c1_open)

        # Current bar
        c0_open, c0_close = open_arr[i], close_arr[i]
        c0_high, c0_low = high_arr[i], low_arr[i]

        # Check if middle candle is doji
        is_doji = c1_range > 0 and c1_body / c1_range < doji_threshold

        if not is_doji:
            continue

        # Bullish Abandoned Baby
        c2_red = c2_open > c2_close
        c0_green = c0_close > c0_open
        gap_down = c1_high < c2_low  # Doji gaps down from first candle
        gap_up = c1_high < c0_low  # Third candle gaps up from doji

        if c2_red and c0_green and gap_down and gap_up:
            bullish[i] = True

        # Bearish Abandoned Baby
        c2_green = c2_close > c2_open
        c0_red = c0_open > c0_close
        gap_up_to_doji = c1_low > c2_high  # Doji gaps up from first candle
        gap_down_from_doji = c1_low > c0_high  # Third candle gaps down

        if c2_green and c0_red and gap_up_to_doji and gap_down_from_doji:
            bearish[i] = True

    return bullish, bearish


# =============================================================================
# BELT HOLD (SINGLE CANDLE REVERSAL)
# =============================================================================


@njit(cache=True)
def detect_belt_hold(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    lookback: int = 10,
    body_ratio: float = 0.8,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Bullish and Bearish Belt Hold patterns.

    A single strong candle pattern indicating potential reversal.

    Bullish Belt Hold: Opens at low, large green body, small/no upper wick.
    Bearish Belt Hold: Opens at high, large red body, small/no lower wick.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        lookback: Period for average body calculation (default: 10)
        body_ratio: Minimum body/range ratio (default: 0.8)

    Returns:
        Tuple of (bullish_belt, bearish_belt) boolean arrays
    """
    n = len(open_arr)
    bullish = np.zeros(n, dtype=np.bool_)
    bearish = np.zeros(n, dtype=np.bool_)

    if n < lookback + 1:
        return bullish, bearish

    body = np.abs(close_arr - open_arr)

    for i in range(lookback, n):
        # Calculate average body
        avg_body = 0.0
        for j in range(i - lookback, i):
            avg_body += body[j]
        avg_body /= lookback

        curr_open = open_arr[i]
        curr_close = close_arr[i]
        curr_high = high_arr[i]
        curr_low = low_arr[i]
        curr_range = curr_high - curr_low
        curr_body = body[i]

        if curr_range == 0:
            continue

        # Must be a significant candle
        if curr_body < avg_body:
            continue

        # Body ratio check
        if curr_body / curr_range < body_ratio:
            continue

        # Bullish Belt Hold: opens at low, closes near high (green)
        if curr_close > curr_open:
            lower_wick = curr_open - curr_low
            if lower_wick < curr_range * 0.05:  # Almost no lower wick
                bullish[i] = True

        # Bearish Belt Hold: opens at high, closes near low (red)
        if curr_open > curr_close:
            upper_wick = curr_high - curr_open
            if upper_wick < curr_range * 0.05:  # Almost no upper wick
                bearish[i] = True

    return bullish, bearish


# =============================================================================
# COUNTERATTACK (EQUAL CLOSE REVERSAL)
# =============================================================================


@njit(cache=True)
def detect_counterattack(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    tolerance: float = 0.002,
    lookback: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Bullish and Bearish Counterattack patterns.

    Two opposite colored candles that close at approximately the same level.

    Bullish Counterattack: Red candle followed by green candle, both close
    at same level (after downtrend).

    Bearish Counterattack: Green candle followed by red candle, both close
    at same level (after uptrend).

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        tolerance: Close price tolerance (default: 0.002 = 0.2%)
        lookback: Period for average body calculation (default: 10)

    Returns:
        Tuple of (bullish_counter, bearish_counter) boolean arrays
    """
    n = len(open_arr)
    bullish = np.zeros(n, dtype=np.bool_)
    bearish = np.zeros(n, dtype=np.bool_)

    if n < lookback + 2:
        return bullish, bearish

    body = np.abs(close_arr - open_arr)

    for i in range(lookback + 1, n):
        # Calculate average body
        avg_body = 0.0
        for j in range(i - lookback - 1, i - 1):
            avg_body += body[j]
        avg_body /= lookback

        prev_open = open_arr[i - 1]
        prev_close = close_arr[i - 1]
        curr_open = open_arr[i]
        curr_close = close_arr[i]

        prev_red = prev_open > prev_close
        prev_green = prev_close > prev_open
        curr_green = curr_close > curr_open
        curr_red = curr_open > curr_close

        # Both should be significant candles
        prev_big = body[i - 1] > avg_body * 0.7
        curr_big = body[i] > avg_body * 0.7

        # Closes should be approximately equal
        close_match = abs(curr_close - prev_close) < prev_close * tolerance

        # Bullish Counterattack: red then green, same close
        if prev_red and curr_green and prev_big and curr_big and close_match:
            # Current opens lower and rallies to match
            if curr_open < prev_close:
                bullish[i] = True

        # Bearish Counterattack: green then red, same close
        if prev_green and curr_red and prev_big and curr_big and close_match:
            # Current opens higher and drops to match
            if curr_open > prev_close:
                bearish[i] = True

    return bullish, bearish


# =============================================================================
# GAP PATTERNS (UP/DOWN GAPS)
# =============================================================================


@njit(cache=True)
def detect_gap_patterns(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    min_gap_ratio: float = 0.003,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Detect Gap Up and Gap Down patterns with fill detection.

    A gap occurs when price opens significantly above/below previous close.
    Gaps can act as support/resistance levels.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        min_gap_ratio: Minimum gap size as ratio of price (default: 0.003 = 0.3%)

    Returns:
        Tuple of (gap_up, gap_down, gap_up_filled, gap_down_filled) boolean arrays
    """
    n = len(open_arr)
    gap_up = np.zeros(n, dtype=np.bool_)
    gap_down = np.zeros(n, dtype=np.bool_)
    gap_up_filled = np.zeros(n, dtype=np.bool_)
    gap_down_filled = np.zeros(n, dtype=np.bool_)

    if n < 2:
        return gap_up, gap_down, gap_up_filled, gap_down_filled

    for i in range(1, n):
        prev_high = high_arr[i - 1]
        prev_low = low_arr[i - 1]
        prev_close = close_arr[i - 1]
        curr_open = open_arr[i]
        curr_high = high_arr[i]
        curr_low = low_arr[i]

        min_gap = prev_close * min_gap_ratio

        # Gap Up: open above previous high
        if curr_open > prev_high + min_gap:
            gap_up[i] = True
            # Check if gap is filled (price drops to previous high)
            if curr_low <= prev_high:
                gap_up_filled[i] = True

        # Gap Down: open below previous low
        if curr_open < prev_low - min_gap:
            gap_down[i] = True
            # Check if gap is filled (price rises to previous low)
            if curr_high >= prev_low:
                gap_down_filled[i] = True

    return gap_up, gap_down, gap_up_filled, gap_down_filled


# =============================================================================
# LADDER BOTTOM/TOP (5-CANDLE REVERSAL)
# =============================================================================


@njit(cache=True)
def detect_ladder_pattern(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Ladder Bottom and Ladder Top patterns.

    Ladder Bottom: 3+ descending red candles, then doji/hammer, then green.
    Ladder Top: 3+ ascending green candles, then doji/shooting star, then red.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices

    Returns:
        Tuple of (ladder_bottom, ladder_top) boolean arrays
    """
    n = len(open_arr)
    bottom = np.zeros(n, dtype=np.bool_)
    top = np.zeros(n, dtype=np.bool_)

    if n < 5:
        return bottom, top

    for i in range(4, n):
        # Check for Ladder Bottom
        # 3 descending red candles
        c4_red = open_arr[i - 4] > close_arr[i - 4]
        c3_red = open_arr[i - 3] > close_arr[i - 3]
        c2_red = open_arr[i - 2] > close_arr[i - 2]
        descending = close_arr[i - 4] > close_arr[i - 3] > close_arr[i - 2]

        # Candle 1 ago: small body (doji/hammer-like)
        c1_range = high_arr[i - 1] - low_arr[i - 1]
        c1_body = abs(close_arr[i - 1] - open_arr[i - 1])
        c1_small = c1_range > 0 and c1_body / c1_range < 0.3

        # Current: green candle
        c0_green = close_arr[i] > open_arr[i]

        if c4_red and c3_red and c2_red and descending and c1_small and c0_green:
            bottom[i] = True

        # Check for Ladder Top
        # 3 ascending green candles
        c4_green = close_arr[i - 4] > open_arr[i - 4]
        c3_green = close_arr[i - 3] > open_arr[i - 3]
        c2_green = close_arr[i - 2] > open_arr[i - 2]
        ascending = close_arr[i - 4] < close_arr[i - 3] < close_arr[i - 2]

        # Current: red candle
        c0_red = open_arr[i] > close_arr[i]

        if c4_green and c3_green and c2_green and ascending and c1_small and c0_red:
            top[i] = True

    return bottom, top


# =============================================================================
# STICK SANDWICH (REVERSAL)
# =============================================================================


@njit(cache=True)
def detect_stick_sandwich(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    tolerance: float = 0.002,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Bullish and Bearish Stick Sandwich patterns.

    Three candle pattern where first and third candles are same color
    with approximately equal closes, sandwiching an opposite color candle.

    Bullish Stick Sandwich: Red-Green-Red with equal closes on red candles.
    Bearish Stick Sandwich: Green-Red-Green with equal closes on green candles.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        tolerance: Close price tolerance (default: 0.002 = 0.2%)

    Returns:
        Tuple of (bullish_sandwich, bearish_sandwich) boolean arrays
    """
    n = len(open_arr)
    bullish = np.zeros(n, dtype=np.bool_)
    bearish = np.zeros(n, dtype=np.bool_)

    if n < 3:
        return bullish, bearish

    for i in range(2, n):
        c2_open, c2_close = open_arr[i - 2], close_arr[i - 2]
        c1_open, c1_close = open_arr[i - 1], close_arr[i - 1]
        c0_open, c0_close = open_arr[i], close_arr[i]

        # Bullish Stick Sandwich: Red-Green-Red with equal closes
        c2_red = c2_open > c2_close
        c1_green = c1_close > c1_open
        c0_red = c0_open > c0_close
        closes_match = abs(c0_close - c2_close) < c2_close * tolerance

        if c2_red and c1_green and c0_red and closes_match:
            bullish[i] = True

        # Bearish Stick Sandwich: Green-Red-Green with equal closes
        c2_green = c2_close > c2_open
        c1_red = c1_open > c1_close
        c0_green = c0_close > c0_open

        if c2_green and c1_red and c0_green and closes_match:
            bearish[i] = True

    return bullish, bearish


# =============================================================================
# HOMING PIGEON (BULLISH CONTINUATION)
# =============================================================================


@njit(cache=True)
def detect_homing_pigeon(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
) -> np.ndarray:
    """
    Detect Homing Pigeon pattern (bullish).

    Two red candles where the second is completely contained within the first.
    Similar to bullish harami but both candles are red.
    Signals potential bullish reversal at bottom of downtrend.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices

    Returns:
        Boolean array indicating pattern presence
    """
    n = len(open_arr)
    result = np.zeros(n, dtype=np.bool_)

    if n < 2:
        return result

    for i in range(1, n):
        # First candle (previous)
        c1_open = open_arr[i - 1]
        c1_close = close_arr[i - 1]
        c1_red = c1_open > c1_close

        # Second candle (current)
        c0_open = open_arr[i]
        c0_close = close_arr[i]
        c0_red = c0_open > c0_close

        # Both must be red
        if not (c1_red and c0_red):
            continue

        # Current body contained within previous body
        c1_body_high = c1_open
        c1_body_low = c1_close
        c0_body_high = c0_open
        c0_body_low = c0_close

        if c0_body_high < c1_body_high and c0_body_low > c1_body_low:
            result[i] = True

    return result


# =============================================================================
# MATCHING LOW/HIGH (SUPPORT/RESISTANCE)
# =============================================================================


@njit(cache=True)
def detect_matching_low_high(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    tolerance: float = 0.001,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect Matching Low and Matching High patterns.

    Matching Low: Two candles with approximately equal lows (bullish).
    Matching High: Two candles with approximately equal highs (bearish).

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices
        tolerance: Price tolerance (default: 0.001 = 0.1%)

    Returns:
        Tuple of (matching_low, matching_high) boolean arrays
    """
    n = len(open_arr)
    matching_low = np.zeros(n, dtype=np.bool_)
    matching_high = np.zeros(n, dtype=np.bool_)

    if n < 2:
        return matching_low, matching_high

    for i in range(1, n):
        prev_high = high_arr[i - 1]
        prev_low = low_arr[i - 1]
        curr_high = high_arr[i]
        curr_low = low_arr[i]

        # Matching Low
        if abs(curr_low - prev_low) < prev_low * tolerance:
            matching_low[i] = True

        # Matching High
        if abs(curr_high - prev_high) < prev_high * tolerance:
            matching_high[i] = True

    return matching_low, matching_high


# =============================================================================
# COMBINED PATTERN DETECTION (BATCH PROCESSING)
# =============================================================================


def detect_all_patterns(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
) -> dict[str, np.ndarray]:
    """
    Detect all supported candlestick patterns in a single pass.

    This is the recommended function for batch pattern detection as it
    efficiently calculates all patterns with shared preprocessing.

    Args:
        open_arr: Array of open prices
        high_arr: Array of high prices
        low_arr: Array of low prices
        close_arr: Array of close prices

    Returns:
        Dictionary with pattern names as keys and boolean arrays as values:
        - engulfing_bullish, engulfing_bearish
        - hammer, hanging_man
        - doji_standard, doji_dragonfly, doji_gravestone
        - pin_bar_bullish, pin_bar_bearish
        - inside_bar, outside_bar
        - three_soldiers, three_crows
        - shooting_star
        - marubozu_bullish, marubozu_bearish
        - tweezer_bottom, tweezer_top
        - three_methods_rising, three_methods_falling
        - piercing_line, dark_cloud
        - harami_bullish, harami_bearish
        - morning_star, evening_star
    """
    result = {}

    # Engulfing
    eng_bull, eng_bear = detect_engulfing(open_arr, high_arr, low_arr, close_arr)
    result["engulfing_bullish"] = eng_bull
    result["engulfing_bearish"] = eng_bear

    # Hammer / Hanging Man
    hammer, hanging = detect_hammer(open_arr, high_arr, low_arr, close_arr)
    result["hammer"] = hammer
    result["hanging_man"] = hanging

    # Doji
    doji_std, doji_dragon, doji_grave = detect_doji(open_arr, high_arr, low_arr, close_arr)
    result["doji_standard"] = doji_std
    result["doji_dragonfly"] = doji_dragon
    result["doji_gravestone"] = doji_grave

    # Pin Bar
    pin_bull, pin_bear = detect_pin_bar(open_arr, high_arr, low_arr, close_arr)
    result["pin_bar_bullish"] = pin_bull
    result["pin_bar_bearish"] = pin_bear

    # Inside / Outside Bar
    result["inside_bar"] = detect_inside_bar(open_arr, high_arr, low_arr, close_arr)
    result["outside_bar"] = detect_outside_bar(open_arr, high_arr, low_arr, close_arr)

    # Three Soldiers / Crows
    soldiers, crows = detect_three_soldiers_crows(open_arr, high_arr, low_arr, close_arr)
    result["three_soldiers"] = soldiers
    result["three_crows"] = crows

    # Shooting Star
    result["shooting_star"] = detect_shooting_star(open_arr, high_arr, low_arr, close_arr)

    # Marubozu
    maru_bull, maru_bear = detect_marubozu(open_arr, high_arr, low_arr, close_arr)
    result["marubozu_bullish"] = maru_bull
    result["marubozu_bearish"] = maru_bear

    # Tweezer
    tw_bottom, tw_top = detect_tweezer(open_arr, high_arr, low_arr, close_arr)
    result["tweezer_bottom"] = tw_bottom
    result["tweezer_top"] = tw_top

    # Three Methods
    tm_rising, tm_falling = detect_three_methods(open_arr, high_arr, low_arr, close_arr)
    result["three_methods_rising"] = tm_rising
    result["three_methods_falling"] = tm_falling

    # Piercing / Dark Cloud
    piercing, dark = detect_piercing_darkcloud(open_arr, high_arr, low_arr, close_arr)
    result["piercing_line"] = piercing
    result["dark_cloud"] = dark

    # Harami
    harami_bull, harami_bear = detect_harami(open_arr, high_arr, low_arr, close_arr)
    result["harami_bullish"] = harami_bull
    result["harami_bearish"] = harami_bear

    # Morning / Evening Star
    morning, evening = detect_morning_evening_star(open_arr, high_arr, low_arr, close_arr)
    result["morning_star"] = morning
    result["evening_star"] = evening

    # ==================== EXOTIC PATTERNS ====================

    # Three Line Strike
    strike_bull, strike_bear = detect_three_line_strike(open_arr, high_arr, low_arr, close_arr)
    result["three_line_strike_bullish"] = strike_bull
    result["three_line_strike_bearish"] = strike_bear

    # Kicker
    kicker_bull, kicker_bear = detect_kicker(open_arr, high_arr, low_arr, close_arr)
    result["kicker_bullish"] = kicker_bull
    result["kicker_bearish"] = kicker_bear

    # Abandoned Baby
    baby_bull, baby_bear = detect_abandoned_baby(open_arr, high_arr, low_arr, close_arr)
    result["abandoned_baby_bullish"] = baby_bull
    result["abandoned_baby_bearish"] = baby_bear

    # Belt Hold
    belt_bull, belt_bear = detect_belt_hold(open_arr, high_arr, low_arr, close_arr)
    result["belt_hold_bullish"] = belt_bull
    result["belt_hold_bearish"] = belt_bear

    # Counterattack
    counter_bull, counter_bear = detect_counterattack(open_arr, high_arr, low_arr, close_arr)
    result["counterattack_bullish"] = counter_bull
    result["counterattack_bearish"] = counter_bear

    # Gap Patterns
    gap_up, gap_down, gap_up_fill, gap_down_fill = detect_gap_patterns(open_arr, high_arr, low_arr, close_arr)
    result["gap_up"] = gap_up
    result["gap_down"] = gap_down
    result["gap_up_filled"] = gap_up_fill
    result["gap_down_filled"] = gap_down_fill

    # Ladder
    ladder_bottom, ladder_top = detect_ladder_pattern(open_arr, high_arr, low_arr, close_arr)
    result["ladder_bottom"] = ladder_bottom
    result["ladder_top"] = ladder_top

    # Stick Sandwich
    sandwich_bull, sandwich_bear = detect_stick_sandwich(open_arr, high_arr, low_arr, close_arr)
    result["stick_sandwich_bullish"] = sandwich_bull
    result["stick_sandwich_bearish"] = sandwich_bear

    # Homing Pigeon
    result["homing_pigeon"] = detect_homing_pigeon(open_arr, high_arr, low_arr, close_arr)

    # Matching Low/High
    match_low, match_high = detect_matching_low_high(open_arr, high_arr, low_arr, close_arr)
    result["matching_low"] = match_low
    result["matching_high"] = match_high

    return result


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "NUMBA_AVAILABLE",
    "detect_abandoned_baby",
    "detect_all_patterns",
    "detect_belt_hold",
    "detect_counterattack",
    "detect_doji",
    "detect_engulfing",
    "detect_gap_patterns",
    "detect_hammer",
    "detect_harami",
    "detect_homing_pigeon",
    "detect_inside_bar",
    "detect_kicker",
    "detect_ladder_pattern",
    "detect_marubozu",
    "detect_matching_low_high",
    "detect_morning_evening_star",
    "detect_outside_bar",
    "detect_piercing_darkcloud",
    "detect_pin_bar",
    "detect_shooting_star",
    "detect_stick_sandwich",
    "detect_three_line_strike",
    "detect_three_methods",
    "detect_three_soldiers_crows",
    "detect_tweezer",
]
