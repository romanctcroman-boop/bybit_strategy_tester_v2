"""
Volume Indicators
=================

OBV, VWAP, PVT, A/D Line, CMF.

All functions accept numpy arrays and return numpy arrays.
"""

import numpy as np

# =============================================================================
# On-Balance Volume (OBV)
# =============================================================================


def calculate_obv(
    close: np.ndarray,
    volume: np.ndarray,
) -> np.ndarray:
    """
    Calculate On-Balance Volume (OBV).

    Args:
        close: Array of closing prices
        volume: Array of volume

    Returns:
        Array of OBV values
    """
    n = len(close)
    obv = np.zeros(n)

    obv[0] = volume[0]

    for i in range(1, n):
        if close[i] > close[i - 1]:
            obv[i] = obv[i - 1] + volume[i]
        elif close[i] < close[i - 1]:
            obv[i] = obv[i - 1] - volume[i]
        else:
            obv[i] = obv[i - 1]

    return obv


# =============================================================================
# Volume Weighted Average Price (VWAP)
# =============================================================================


def calculate_vwap(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
) -> np.ndarray:
    """
    Calculate Volume Weighted Average Price (VWAP).

    Note: This is a cumulative VWAP from the start of the data.
    For intraday VWAP, reset at each session start.

    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of closing prices
        volume: Array of volume

    Returns:
        Array of VWAP values
    """
    # Typical price
    tp = (high + low + close) / 3

    # Cumulative typical price * volume
    cum_tp_vol = np.cumsum(tp * volume)
    cum_vol = np.cumsum(volume)

    # Avoid division by zero
    vwap = np.where(cum_vol > 0, cum_tp_vol / cum_vol, tp)

    return vwap


# =============================================================================
# Price Volume Trend (PVT)
# =============================================================================


def calculate_pvt(
    close: np.ndarray,
    volume: np.ndarray,
) -> np.ndarray:
    """
    Calculate Price Volume Trend (PVT).

    Args:
        close: Array of closing prices
        volume: Array of volume

    Returns:
        Array of PVT values
    """
    n = len(close)
    pvt = np.zeros(n)

    for i in range(1, n):
        if close[i - 1] > 1e-10:
            price_change_pct = (close[i] - close[i - 1]) / close[i - 1]
            pvt[i] = pvt[i - 1] + volume[i] * price_change_pct
        else:
            pvt[i] = pvt[i - 1]

    return pvt


# =============================================================================
# Accumulation/Distribution Line (A/D Line)
# =============================================================================


def calculate_ad_line(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
) -> np.ndarray:
    """
    Calculate Accumulation/Distribution Line.

    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of closing prices
        volume: Array of volume

    Returns:
        Array of A/D Line values
    """
    n = len(close)
    ad = np.zeros(n)

    for i in range(n):
        hl_range = high[i] - low[i]

        if hl_range > 1e-10:
            # Money Flow Multiplier
            mfm = ((close[i] - low[i]) - (high[i] - close[i])) / hl_range
            # Money Flow Volume
            mfv = mfm * volume[i]
        else:
            mfv = 0.0

        if i == 0:
            ad[i] = mfv
        else:
            ad[i] = ad[i - 1] + mfv

    return ad


# =============================================================================
# Chaikin Money Flow (CMF)
# =============================================================================


def calculate_cmf(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    period: int = 20,
) -> np.ndarray:
    """
    Calculate Chaikin Money Flow (CMF).

    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of closing prices
        volume: Array of volume
        period: Lookback period (default: 20)

    Returns:
        Array of CMF values (-1 to +1)
    """
    n = len(close)
    cmf = np.full(n, np.nan)

    # Money Flow Multiplier for each bar
    hl_range = high - low
    mfm = np.where(
        hl_range > 1e-10,
        ((close - low) - (high - close)) / hl_range,
        0.0,
    )

    # Money Flow Volume
    mfv = mfm * volume

    for i in range(period - 1, n):
        sum_mfv = np.sum(mfv[i - period + 1 : i + 1])
        sum_vol = np.sum(volume[i - period + 1 : i + 1])

        if sum_vol > 1e-10:
            cmf[i] = sum_mfv / sum_vol
        else:
            cmf[i] = 0.0

    return cmf
