"""
Advanced Indicators
===================

ADX, CCI, Ichimoku Cloud, Parabolic SAR, Pivot Points.

All functions accept numpy arrays and return numpy arrays.
"""

from typing import NamedTuple

import numpy as np

# =============================================================================
# Average Directional Index (ADX)
# =============================================================================


class ADXResult(NamedTuple):
    """ADX calculation result."""

    adx: np.ndarray  # ADX line (trend strength)
    plus_di: np.ndarray  # +DI (bullish directional indicator)
    minus_di: np.ndarray  # -DI (bearish directional indicator)


def calculate_adx(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> ADXResult:
    """
    Calculate Average Directional Index (ADX).

    Measures trend strength (not direction).
    - ADX > 25: Strong trend
    - ADX < 20: Weak/no trend
    - +DI > -DI: Bullish
    - -DI > +DI: Bearish

    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of close prices
        period: Lookback period (default: 14)

    Returns:
        ADXResult with adx, plus_di, minus_di arrays
    """
    n = len(close)

    adx = np.full(n, np.nan)
    plus_di = np.full(n, np.nan)
    minus_di = np.full(n, np.nan)

    if n < period + 1:
        return ADXResult(adx, plus_di, minus_di)

    # True Range
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))

    # Directional Movement
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        up_move = high[i] - high[i - 1]
        down_move = low[i - 1] - low[i]

        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    # Smoothed averages (Wilder's smoothing)
    atr = np.zeros(n)
    smooth_plus_dm = np.zeros(n)
    smooth_minus_dm = np.zeros(n)

    # Initial sum
    atr[period] = np.sum(tr[1 : period + 1])
    smooth_plus_dm[period] = np.sum(plus_dm[1 : period + 1])
    smooth_minus_dm[period] = np.sum(minus_dm[1 : period + 1])

    # Wilder's smoothing
    for i in range(period + 1, n):
        atr[i] = atr[i - 1] - (atr[i - 1] / period) + tr[i]
        smooth_plus_dm[i] = smooth_plus_dm[i - 1] - (smooth_plus_dm[i - 1] / period) + plus_dm[i]
        smooth_minus_dm[i] = smooth_minus_dm[i - 1] - (smooth_minus_dm[i - 1] / period) + minus_dm[i]

    # +DI and -DI
    for i in range(period, n):
        if atr[i] != 0:
            plus_di[i] = 100 * smooth_plus_dm[i] / atr[i]
            minus_di[i] = 100 * smooth_minus_dm[i] / atr[i]

    # DX and ADX
    dx = np.zeros(n)
    for i in range(period, n):
        di_sum = plus_di[i] + minus_di[i]
        if di_sum != 0:
            dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / di_sum

    # Smooth DX to get ADX
    adx[2 * period - 1] = np.mean(dx[period : 2 * period])
    for i in range(2 * period, n):
        adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period

    return ADXResult(adx, plus_di, minus_di)


# =============================================================================
# Commodity Channel Index (CCI)
# =============================================================================


def calculate_cci(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 20,
    constant: float = 0.015,
) -> np.ndarray:
    """
    Calculate Commodity Channel Index (CCI).

    Measures price deviation from statistical mean.
    - CCI > 100: Overbought
    - CCI < -100: Oversold

    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of close prices
        period: Lookback period (default: 20)
        constant: Scaling constant (default: 0.015)

    Returns:
        Array of CCI values
    """
    n = len(close)
    cci = np.full(n, np.nan)

    if n < period:
        return cci

    # Typical Price
    tp = (high + low + close) / 3

    for i in range(period - 1, n):
        # SMA of Typical Price
        tp_slice = tp[i - period + 1 : i + 1]
        sma_tp = np.mean(tp_slice)

        # Mean Deviation
        mean_dev = np.mean(np.abs(tp_slice - sma_tp))

        if mean_dev != 0:
            cci[i] = (tp[i] - sma_tp) / (constant * mean_dev)

    return cci


# =============================================================================
# Ichimoku Cloud
# =============================================================================


class IchimokuResult(NamedTuple):
    """Ichimoku Cloud calculation result."""

    tenkan_sen: np.ndarray  # Conversion Line (9-period)
    kijun_sen: np.ndarray  # Base Line (26-period)
    senkou_span_a: np.ndarray  # Leading Span A (shifted forward 26)
    senkou_span_b: np.ndarray  # Leading Span B (shifted forward 26)
    chikou_span: np.ndarray  # Lagging Span (shifted back 26)


def calculate_ichimoku(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
    displacement: int = 26,
) -> IchimokuResult:
    """
    Calculate Ichimoku Cloud (Ichimoku Kinko Hyo).

    Components:
    - Tenkan-sen (Conversion): (9-high + 9-low) / 2
    - Kijun-sen (Base): (26-high + 26-low) / 2
    - Senkou Span A: (Tenkan + Kijun) / 2, shifted 26 forward
    - Senkou Span B: (52-high + 52-low) / 2, shifted 26 forward
    - Chikou Span: Close, shifted 26 back

    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of close prices
        tenkan_period: Tenkan-sen period (default: 9)
        kijun_period: Kijun-sen period (default: 26)
        senkou_b_period: Senkou Span B period (default: 52)
        displacement: Forward/back shift (default: 26)

    Returns:
        IchimokuResult with all five components
    """
    n = len(close)

    tenkan_sen = np.full(n, np.nan)
    kijun_sen = np.full(n, np.nan)
    senkou_span_a = np.full(n, np.nan)
    senkou_span_b = np.full(n, np.nan)
    chikou_span = np.full(n, np.nan)

    # Tenkan-sen (Conversion Line)
    for i in range(tenkan_period - 1, n):
        period_high = np.max(high[i - tenkan_period + 1 : i + 1])
        period_low = np.min(low[i - tenkan_period + 1 : i + 1])
        tenkan_sen[i] = (period_high + period_low) / 2

    # Kijun-sen (Base Line)
    for i in range(kijun_period - 1, n):
        period_high = np.max(high[i - kijun_period + 1 : i + 1])
        period_low = np.min(low[i - kijun_period + 1 : i + 1])
        kijun_sen[i] = (period_high + period_low) / 2

    # Senkou Span A (Leading Span A) - shifted forward
    for i in range(kijun_period - 1, n):
        if i + displacement < n:
            senkou_span_a[i + displacement] = (tenkan_sen[i] + kijun_sen[i]) / 2

    # Senkou Span B (Leading Span B) - shifted forward
    for i in range(senkou_b_period - 1, n):
        period_high = np.max(high[i - senkou_b_period + 1 : i + 1])
        period_low = np.min(low[i - senkou_b_period + 1 : i + 1])
        if i + displacement < n:
            senkou_span_b[i + displacement] = (period_high + period_low) / 2

    # Chikou Span (Lagging Span) - shifted back
    for i in range(displacement, n):
        chikou_span[i - displacement] = close[i]

    return IchimokuResult(tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span)


# =============================================================================
# Parabolic SAR
# =============================================================================


def calculate_parabolic_sar(
    high: np.ndarray,
    low: np.ndarray,
    af_start: float = 0.02,
    af_increment: float = 0.02,
    af_max: float = 0.2,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculate Parabolic Stop and Reverse (SAR).

    Trend-following indicator that provides potential entry/exit points.

    Args:
        high: Array of high prices
        low: Array of low prices
        af_start: Initial acceleration factor (default: 0.02)
        af_increment: AF increment on new extreme (default: 0.02)
        af_max: Maximum AF (default: 0.2)

    Returns:
        Tuple of (sar_values, trend_direction)
        trend_direction: 1 = uptrend, -1 = downtrend
    """
    n = len(high)

    sar = np.zeros(n)
    trend = np.zeros(n)

    if n < 2:
        return sar, trend

    # Initialize
    trend[0] = 1  # Start with uptrend
    sar[0] = low[0]
    ep = high[0]  # Extreme Point
    af = af_start

    for i in range(1, n):
        # Calculate SAR
        sar[i] = sar[i - 1] + af * (ep - sar[i - 1])

        if trend[i - 1] == 1:  # Uptrend
            # SAR cannot be above prior two lows
            sar[i] = min(sar[i], low[i - 1])
            if i >= 2:
                sar[i] = min(sar[i], low[i - 2])

            # Check for reversal
            if low[i] < sar[i]:
                trend[i] = -1
                sar[i] = ep
                ep = low[i]
                af = af_start
            else:
                trend[i] = 1
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + af_increment, af_max)
        else:  # Downtrend
            # SAR cannot be below prior two highs
            sar[i] = max(sar[i], high[i - 1])
            if i >= 2:
                sar[i] = max(sar[i], high[i - 2])

            # Check for reversal
            if high[i] > sar[i]:
                trend[i] = 1
                sar[i] = ep
                ep = high[i]
                af = af_start
            else:
                trend[i] = -1
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + af_increment, af_max)

    return sar, trend


# =============================================================================
# Pivot Points (Standard/Classic)
# =============================================================================


class PivotResult(NamedTuple):
    """Pivot Points calculation result."""

    pivot: float  # Pivot Point (PP)
    r1: float  # Resistance 1
    r2: float  # Resistance 2
    r3: float  # Resistance 3
    s1: float  # Support 1
    s2: float  # Support 2
    s3: float  # Support 3


def calculate_pivot_points(
    high: float,
    low: float,
    close: float,
    method: str = "standard",
) -> PivotResult:
    """
    Calculate Pivot Points for a single period.

    Methods:
    - 'standard': Classic pivot points
    - 'fibonacci': Fibonacci-based levels
    - 'woodie': Woodie's pivot points
    - 'camarilla': Camarilla pivot points

    Args:
        high: Period high price
        low: Period low price
        close: Period close price
        method: Calculation method (default: 'standard')

    Returns:
        PivotResult with PP, R1-R3, S1-S3
    """
    if method == "standard":
        pp = (high + low + close) / 3
        r1 = 2 * pp - low
        s1 = 2 * pp - high
        r2 = pp + (high - low)
        s2 = pp - (high - low)
        r3 = high + 2 * (pp - low)
        s3 = low - 2 * (high - pp)

    elif method == "fibonacci":
        pp = (high + low + close) / 3
        diff = high - low
        r1 = pp + 0.382 * diff
        r2 = pp + 0.618 * diff
        r3 = pp + diff
        s1 = pp - 0.382 * diff
        s2 = pp - 0.618 * diff
        s3 = pp - diff

    elif method == "woodie":
        pp = (high + low + 2 * close) / 4
        r1 = 2 * pp - low
        s1 = 2 * pp - high
        r2 = pp + (high - low)
        s2 = pp - (high - low)
        r3 = r1 + (high - low)
        s3 = s1 - (high - low)

    elif method == "camarilla":
        pp = (high + low + close) / 3
        diff = high - low
        r1 = close + diff * 1.1 / 12
        r2 = close + diff * 1.1 / 6
        r3 = close + diff * 1.1 / 4
        s1 = close - diff * 1.1 / 12
        s2 = close - diff * 1.1 / 6
        s3 = close - diff * 1.1 / 4
    else:
        raise ValueError(f"Unknown pivot method: {method}")

    return PivotResult(pp, r1, r2, r3, s1, s2, s3)


def calculate_pivot_points_array(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    method: str = "standard",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Pivot Points for array of data.

    Uses previous bar's HLC to calculate current bar's pivot levels.

    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of close prices
        method: Calculation method (default: 'standard')

    Returns:
        Tuple of (pp, r1, r2, r3, s1, s2, s3) arrays
    """
    n = len(close)

    pp = np.full(n, np.nan)
    r1 = np.full(n, np.nan)
    r2 = np.full(n, np.nan)
    r3 = np.full(n, np.nan)
    s1 = np.full(n, np.nan)
    s2 = np.full(n, np.nan)
    s3 = np.full(n, np.nan)

    for i in range(1, n):
        result = calculate_pivot_points(high[i - 1], low[i - 1], close[i - 1], method)
        pp[i] = result.pivot
        r1[i] = result.r1
        r2[i] = result.r2
        r3[i] = result.r3
        s1[i] = result.s1
        s2[i] = result.s2
        s3[i] = result.s3

    return pp, r1, r2, r3, s1, s2, s3


# =============================================================================
# Aroon Indicator
# =============================================================================


class AroonResult(NamedTuple):
    """Aroon calculation result."""

    aroon_up: np.ndarray  # Aroon Up
    aroon_down: np.ndarray  # Aroon Down
    aroon_osc: np.ndarray  # Aroon Oscillator (Up - Down)


def calculate_aroon(
    high: np.ndarray,
    low: np.ndarray,
    period: int = 25,
) -> AroonResult:
    """
    Calculate Aroon Indicator.

    Measures time since highest high / lowest low.
    - Aroon Up > 70 and Down < 30: Strong uptrend
    - Aroon Down > 70 and Up < 30: Strong downtrend

    Args:
        high: Array of high prices
        low: Array of low prices
        period: Lookback period (default: 25)

    Returns:
        AroonResult with aroon_up, aroon_down, aroon_osc
    """
    n = len(high)

    aroon_up = np.full(n, np.nan)
    aroon_down = np.full(n, np.nan)
    aroon_osc = np.full(n, np.nan)

    if n < period:
        return AroonResult(aroon_up, aroon_down, aroon_osc)

    for i in range(period, n):
        # Find bars since highest high
        period_high = high[i - period : i + 1]
        bars_since_high = period - np.argmax(period_high)
        aroon_up[i] = ((period - bars_since_high) / period) * 100

        # Find bars since lowest low
        period_low = low[i - period : i + 1]
        bars_since_low = period - np.argmin(period_low)
        aroon_down[i] = ((period - bars_since_low) / period) * 100

        # Oscillator
        aroon_osc[i] = aroon_up[i] - aroon_down[i]

    return AroonResult(aroon_up, aroon_down, aroon_osc)


# =============================================================================
# Average True Range Percent (ATRP)
# =============================================================================


def calculate_atrp(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """
    Calculate Average True Range Percent (ATR%).

    ATR normalized by close price for comparison across different price levels.

    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of close prices
        period: Lookback period (default: 14)

    Returns:
        Array of ATRP values (percentage)
    """
    from backend.core.indicators.volatility import calculate_atr

    atr = calculate_atr(high, low, close, period)
    atrp = (atr / close) * 100

    return atrp
