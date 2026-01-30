"""
📊 ATR (Average True Range) Calculator
Расчёт ATR для использования в TP/SL.
"""

from typing import Union

import numpy as np
import pandas as pd


def calculate_atr(
    high: Union[np.ndarray, pd.Series],
    low: Union[np.ndarray, pd.Series],
    close: Union[np.ndarray, pd.Series],
    period: int = 14,
) -> np.ndarray:
    """
    Рассчитать ATR (Average True Range).

    ATR = SMA(True Range, period)
    True Range = max(high - low, |high - prev_close|, |low - prev_close|)

    Args:
        high: Массив максимумов
        low: Массив минимумов
        close: Массив закрытий
        period: Период усреднения (по умолчанию 14)

    Returns:
        np.ndarray с значениями ATR (первые period-1 значений = 0)
    """
    high = np.asarray(high, dtype=np.float64)
    low = np.asarray(low, dtype=np.float64)
    close = np.asarray(close, dtype=np.float64)

    n = len(close)
    if n < 2:
        return np.zeros(n, dtype=np.float64)

    # True Range
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = high[0] - low[0]  # Первый бар - просто диапазон

    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hc, lc)

    # ATR = SMA of True Range (for first period bars)
    # Then Wilder's smoothing (EMA-like)
    atr = np.zeros(n, dtype=np.float64)

    # First `period` bars - accumulate SMA
    if n >= period:
        atr[period - 1] = np.mean(tr[:period])

        # Wilder's smoothing: ATR = ((period-1) * prev_ATR + TR) / period
        # Equivalent to: ATR = prev_ATR * (1 - 1/period) + TR * (1/period)
        for i in range(period, n):
            atr[i] = ((period - 1) * atr[i - 1] + tr[i]) / period

    return atr


def calculate_atr_fast(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """
    Быстрый расчёт ATR с использованием векторизации numpy.

    Uses Wilder's smoothing (same as calculate_atr):
      ATR[i] = ATR[i-1] * (1 - 1/period) + TR[i] * (1/period)
             = ((period-1) * ATR[i-1] + TR[i]) / period

    Args:
        high: np.ndarray максимумов (float64)
        low: np.ndarray минимумов (float64)
        close: np.ndarray закрытий (float64)
        period: Период усреднения

    Returns:
        np.ndarray с значениями ATR
    """
    n = len(close)
    if n < 2:
        return np.zeros(n, dtype=np.float64)

    # True Range - векторизованный расчёт
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]

    hl = high - low
    hc = np.abs(high - prev_close)
    lc = np.abs(low - prev_close)

    tr = np.maximum(np.maximum(hl, hc), lc)
    tr[0] = high[0] - low[0]

    # ATR with Wilder's smoothing
    atr = np.zeros(n, dtype=np.float64)

    if n >= period:
        # First value = SMA
        atr[period - 1] = np.mean(tr[:period])

        # Wilder's EMA: ATR = prev * (1 - 1/period) + TR * (1/period)
        alpha = 1.0 / period
        for i in range(period, n):
            atr[i] = atr[i - 1] * (1 - alpha) + tr[i] * alpha

    return atr
