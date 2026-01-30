"""
Signal Generators for V2 Engines
================================

Trading signal generators using unified indicators library.
All V2 engines require ready signal arrays (long_entries, short_entries, etc.)
"""

import numpy as np
import pandas as pd

from backend.core.indicators import calculate_rsi, calculate_sma


def generate_rsi_signals(
    candles: pd.DataFrame,
    period: int = 14,
    overbought: int = 70,
    oversold: int = 30,
    direction: str = "both",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate RSI signals for V2 engines.

    Args:
        candles: DataFrame with OHLCV data
        period: RSI period
        overbought: Overbought level
        oversold: Oversold level
        direction: "long", "short", or "both"

    Returns:
        Tuple[long_entries, long_exits, short_entries, short_exits]
        Each element is a numpy boolean array
    """
    n = len(candles)
    close = candles["close"].values

    # Calculate RSI using unified library
    rsi = calculate_rsi(close, period)

    # Initialize signal arrays
    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    # RSI warmup period
    warmup_bars = period * 4  # 56 bars for RSI(14)

    # Generate signals with TradingView crossover/crossunder logic
    for i in range(1, n - 1):
        if i < warmup_bars:
            continue

        prev_rsi = rsi[i - 1]
        curr_rsi = rsi[i]

        # Skip if NaN
        if np.isnan(prev_rsi) or np.isnan(curr_rsi):
            continue

        # Long entry: crossover(RSI, oversold)
        if direction in ("long", "both"):
            if prev_rsi <= oversold and curr_rsi > oversold:
                long_entries[i + 1] = True

        # Short entry: crossunder(RSI, overbought)
        if direction in ("short", "both"):
            if prev_rsi >= overbought and curr_rsi < overbought:
                short_entries[i + 1] = True

    return long_entries, long_exits, short_entries, short_exits


def generate_sma_crossover_signals(
    candles: pd.DataFrame,
    fast_period: int = 10,
    slow_period: int = 20,
    direction: str = "both",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate SMA Crossover signals for V2 engines.

    Args:
        candles: DataFrame with OHLCV data
        fast_period: Fast SMA period
        slow_period: Slow SMA period
        direction: "long", "short", or "both"

    Returns:
        Tuple[long_entries, long_exits, short_entries, short_exits]
    """
    n = len(candles)
    close = candles["close"].values

    # Calculate SMAs using unified library
    fast_sma = calculate_sma(close, fast_period)
    slow_sma = calculate_sma(close, slow_period)

    # Initialize signal arrays
    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    # Generate signals
    for i in range(1, n):
        prev_fast = fast_sma[i - 1]
        curr_fast = fast_sma[i]
        prev_slow = slow_sma[i - 1]
        curr_slow = slow_sma[i]

        # Skip if NaN
        if np.isnan(curr_fast) or np.isnan(curr_slow):
            continue

        # Golden cross (fast crosses above slow)
        if direction in ("long", "both"):
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                long_entries[i] = True
            if prev_fast >= prev_slow and curr_fast < curr_slow:
                long_exits[i] = True

        # Death cross (fast crosses below slow)
        if direction in ("short", "both"):
            if prev_fast >= prev_slow and curr_fast < curr_slow:
                short_entries[i] = True
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                short_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits
