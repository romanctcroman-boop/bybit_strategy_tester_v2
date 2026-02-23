"""
Signal Generators for V2 Engines
================================

Trading signal generators using unified indicators library.
All V2 engines require ready signal arrays (long_entries, short_entries, etc.)

Supported strategies:
- RSI (generate_rsi_signals)
- SMA Crossover (generate_sma_crossover_signals)
- EMA Crossover (generate_ema_crossover_signals)
- MACD (generate_macd_signals)
- Bollinger Bands (generate_bollinger_signals)

Universal dispatcher: generate_signals_for_strategy()
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from backend.core.indicators import (
    calculate_bollinger,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
)

logger = logging.getLogger(__name__)


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
        if direction in ("long", "both") and prev_rsi <= oversold and curr_rsi > oversold:
            long_entries[i + 1] = True

        # Short entry: crossunder(RSI, overbought)
        if direction in ("short", "both") and prev_rsi >= overbought and curr_rsi < overbought:
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


def generate_ema_crossover_signals(
    candles: pd.DataFrame,
    fast_period: int = 9,
    slow_period: int = 21,
    direction: str = "both",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate EMA Crossover signals for V2 engines.

    Args:
        candles: DataFrame with OHLCV data.
        fast_period: Fast EMA period.
        slow_period: Slow EMA period.
        direction: "long", "short", or "both".

    Returns:
        Tuple[long_entries, long_exits, short_entries, short_exits]
    """
    n = len(candles)
    close = candles["close"].values

    fast_ema = calculate_ema(close, fast_period)
    slow_ema = calculate_ema(close, slow_period)

    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    for i in range(1, n):
        prev_fast = fast_ema[i - 1]
        curr_fast = fast_ema[i]
        prev_slow = slow_ema[i - 1]
        curr_slow = slow_ema[i]

        if np.isnan(curr_fast) or np.isnan(curr_slow):
            continue

        if direction in ("long", "both"):
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                long_entries[i] = True
            if prev_fast >= prev_slow and curr_fast < curr_slow:
                long_exits[i] = True

        if direction in ("short", "both"):
            if prev_fast >= prev_slow and curr_fast < curr_slow:
                short_entries[i] = True
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                short_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits


def generate_macd_signals(
    candles: pd.DataFrame,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    direction: str = "both",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate MACD signals for V2 engines.

    Entry: MACD line crosses signal line.
    Exit: Reverse crossover.

    Args:
        candles: DataFrame with OHLCV data.
        fast_period: Fast EMA period for MACD.
        slow_period: Slow EMA period for MACD.
        signal_period: Signal line EMA period.
        direction: "long", "short", or "both".

    Returns:
        Tuple[long_entries, long_exits, short_entries, short_exits]
    """
    n = len(candles)
    close = candles["close"].values

    # calculate_macd returns (macd_line, signal_line, histogram)
    macd_line, signal_line, _histogram = calculate_macd(close, fast_period, slow_period, signal_period)

    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    warmup = slow_period + signal_period

    for i in range(1, n):
        if i < warmup:
            continue

        prev_macd = macd_line[i - 1]
        curr_macd = macd_line[i]
        prev_signal = signal_line[i - 1]
        curr_signal = signal_line[i]

        if np.isnan(prev_macd) or np.isnan(curr_macd) or np.isnan(prev_signal) or np.isnan(curr_signal):
            continue

        # Bullish cross: MACD crosses above signal
        if direction in ("long", "both"):
            if prev_macd <= prev_signal and curr_macd > curr_signal:
                long_entries[i] = True
            if prev_macd >= prev_signal and curr_macd < curr_signal:
                long_exits[i] = True

        # Bearish cross: MACD crosses below signal
        if direction in ("short", "both"):
            if prev_macd >= prev_signal and curr_macd < curr_signal:
                short_entries[i] = True
            if prev_macd <= prev_signal and curr_macd > curr_signal:
                short_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits


def generate_bollinger_signals(
    candles: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
    direction: str = "both",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate Bollinger Bands mean-reversion signals for V2 engines.

    Long entry: price crosses below lower band (oversold).
    Long exit: price crosses above middle band.
    Short entry: price crosses above upper band (overbought).
    Short exit: price crosses below middle band.

    Args:
        candles: DataFrame with OHLCV data.
        period: Bollinger Bands period.
        std_dev: Standard deviation multiplier.
        direction: "long", "short", or "both".

    Returns:
        Tuple[long_entries, long_exits, short_entries, short_exits]
    """
    n = len(candles)
    close = candles["close"].values

    # calculate_bollinger returns (middle, upper, lower)
    middle, upper, lower = calculate_bollinger(close, period, std_dev)

    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    for i in range(1, n):
        if np.isnan(middle[i]) or np.isnan(upper[i]) or np.isnan(lower[i]):
            continue

        prev_close = close[i - 1]
        curr_close = close[i]

        # Long: price crosses below lower → oversold → buy
        if direction in ("long", "both"):
            if prev_close >= lower[i - 1] and curr_close < lower[i]:
                long_entries[i] = True
            if prev_close <= middle[i - 1] and curr_close > middle[i]:
                long_exits[i] = True

        # Short: price crosses above upper → overbought → sell
        if direction in ("short", "both"):
            if prev_close <= upper[i - 1] and curr_close > upper[i]:
                short_entries[i] = True
            if prev_close >= middle[i - 1] and curr_close < middle[i]:
                short_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits


# =============================================================================
# UNIVERSAL SIGNAL DISPATCHER
# =============================================================================


def generate_signals_for_strategy(
    candles: pd.DataFrame,
    strategy_type: str,
    params: dict,
    direction: str = "both",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Universal signal generator — dispatches to strategy-specific function.

    This is the single entry point for all optimization paths.

    Args:
        candles: DataFrame with OHLCV data.
        strategy_type: Strategy type string (rsi, sma_crossover, ema_crossover, macd, bollinger_bands).
        params: Dict of strategy-specific parameters.
        direction: "long", "short", or "both".

    Returns:
        Tuple[long_entries, long_exits, short_entries, short_exits]

    Raises:
        ValueError: If strategy_type is not supported.
    """
    st = strategy_type.lower().strip()

    if st == "rsi":
        return generate_rsi_signals(
            candles=candles,
            period=int(params.get("rsi_period", params.get("period", 14))),
            overbought=int(params.get("rsi_overbought", params.get("overbought", 70))),
            oversold=int(params.get("rsi_oversold", params.get("oversold", 30))),
            direction=direction,
        )

    if st == "sma_crossover":
        return generate_sma_crossover_signals(
            candles=candles,
            fast_period=int(params.get("sma_fast_period", params.get("fast_period", 10))),
            slow_period=int(params.get("sma_slow_period", params.get("slow_period", 20))),
            direction=direction,
        )

    if st == "ema_crossover":
        return generate_ema_crossover_signals(
            candles=candles,
            fast_period=int(params.get("ema_fast_period", params.get("fast_period", 9))),
            slow_period=int(params.get("ema_slow_period", params.get("slow_period", 21))),
            direction=direction,
        )

    if st == "macd":
        return generate_macd_signals(
            candles=candles,
            fast_period=int(params.get("macd_fast_period", params.get("fast_period", 12))),
            slow_period=int(params.get("macd_slow_period", params.get("slow_period", 26))),
            signal_period=int(params.get("macd_signal_period", params.get("signal_period", 9))),
            direction=direction,
        )

    if st == "bollinger_bands":
        return generate_bollinger_signals(
            candles=candles,
            period=int(params.get("bb_period", params.get("period", 20))),
            std_dev=float(params.get("bb_std_dev", params.get("std_dev", 2.0))),
            direction=direction,
        )

    raise ValueError(
        f"Unsupported strategy_type '{strategy_type}'. "
        f"Supported: rsi, sma_crossover, ema_crossover, macd, bollinger_bands"
    )
