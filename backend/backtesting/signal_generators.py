"""
Signal Generators for V2 Engines
================================

Генераторы торговых сигналов для унифицированного интерфейса BacktestInput.
Все движки V2 требуют готовые массивы сигналов (long_entries, short_entries, etc.)
"""

import numpy as np
import pandas as pd
from typing import Tuple


def generate_rsi_signals(
    candles: pd.DataFrame,
    period: int = 14,
    overbought: int = 70,
    oversold: int = 30,
    direction: str = "both",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Генерация сигналов RSI для V2 движков.

    Args:
        candles: DataFrame с OHLCV данными
        period: Период RSI
        overbought: Уровень перекупленности
        oversold: Уровень перепроданности
        direction: "long", "short", или "both"

    Returns:
        Tuple[long_entries, long_exits, short_entries, short_exits]
        Каждый элемент — numpy boolean array
    """
    n = len(candles)

    # Рассчитываем RSI
    close = candles["close"].values
    rsi = _calculate_rsi(close, period)

    # Инициализируем массивы сигналов
    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    # RSI warmup period - игнорируем первые N баров для стабилизации RSI
    # TV использует больше истории, поэтому нужен warmup
    warmup_bars = period * 4  # 56 баров для RSI(14)

    # Генерируем сигналы
    # TradingView crossover/crossunder точная логика:
    # - crossover(source, level): prev <= level AND curr > level
    # - crossunder(source, level): prev >= level AND curr < level
    # Важно: TV использует <= и >= для prev, и строгое < или > для curr
    #
    # TV ENTRY TIMING: сигнал генерируется на close свечи [i],
    # но вход происходит на OPEN следующей свечи [i+1]
    # Поэтому мы ставим флаг на [i+1] чтобы движок входил на правильной свече

    for i in range(1, n - 1):  # n-1 чтобы i+1 не вышел за границы
        # Пропускаем warmup период
        if i < warmup_bars:
            continue

        prev_rsi = rsi[i - 1]
        curr_rsi = rsi[i]

        # Long entry: crossover(RSI, oversold) - RSI пересекает oversold СНИЗУ ВВЕРХ
        # TradingView: prev <= oversold AND curr > oversold
        # Сигнал на свече [i], вход на свече [i+1]
        if direction in ("long", "both"):
            if prev_rsi <= oversold and curr_rsi > oversold:
                long_entries[i + 1] = True  # +1 для входа на следующей свече

        # Short entry: crossunder(RSI, overbought) - RSI пересекает overbought СВЕРХУ ВНИЗ
        # TradingView: prev >= overbought AND curr < overbought
        # Сигнал на свече [i], вход на свече [i+1]
        if direction in ("short", "both"):
            if prev_rsi >= overbought and curr_rsi < overbought:
                short_entries[i + 1] = True  # +1 для входа на следующей свече

    return long_entries, long_exits, short_entries, short_exits


def _calculate_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Расчёт RSI с использованием EMA (Wilder's smoothing).

    Args:
        close: Массив цен закрытия
        period: Период RSI

    Returns:
        numpy array с RSI значениями
    """
    n = len(close)
    rsi = np.zeros(n)

    if n < period + 1:
        return rsi

    # Изменения цен
    deltas = np.diff(close)

    # Разделяем на gains и losses
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    # Начальные средние (SMA для первого периода)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    # Первое значение RSI
    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))

    # Wilder's smoothing для остальных значений
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))

    return rsi


def generate_sma_crossover_signals(
    candles: pd.DataFrame,
    fast_period: int = 10,
    slow_period: int = 20,
    direction: str = "both",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Генерация сигналов SMA Crossover для V2 движков.

    Args:
        candles: DataFrame с OHLCV данными
        fast_period: Период быстрой SMA
        slow_period: Период медленной SMA
        direction: "long", "short", или "both"

    Returns:
        Tuple[long_entries, long_exits, short_entries, short_exits]
    """
    n = len(candles)
    close = candles["close"].values

    # Рассчитываем SMA
    fast_sma = _calculate_sma(close, fast_period)
    slow_sma = _calculate_sma(close, slow_period)

    # Инициализируем массивы сигналов
    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    # Генерируем сигналы
    for i in range(1, n):
        prev_fast = fast_sma[i - 1]
        curr_fast = fast_sma[i]
        prev_slow = slow_sma[i - 1]
        curr_slow = slow_sma[i]

        # Пропускаем если SMA ещё не рассчитаны
        if curr_fast == 0 or curr_slow == 0:
            continue

        # Golden cross (fast crosses above slow)
        if direction in ("long", "both"):
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                long_entries[i] = True
            # Death cross для выхода из long
            if prev_fast >= prev_slow and curr_fast < curr_slow:
                long_exits[i] = True

        # Death cross (fast crosses below slow)
        if direction in ("short", "both"):
            if prev_fast >= prev_slow and curr_fast < curr_slow:
                short_entries[i] = True
            # Golden cross для выхода из short
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                short_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits


def _calculate_sma(values: np.ndarray, period: int) -> np.ndarray:
    """Расчёт Simple Moving Average."""
    n = len(values)
    sma = np.zeros(n)

    for i in range(period - 1, n):
        sma[i] = np.mean(values[i - period + 1 : i + 1])

    return sma
