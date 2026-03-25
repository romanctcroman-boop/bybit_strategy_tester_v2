"""
📈 MTF Signal Generators Module

Signal generators with Multi-Timeframe (HTF) filtering support.

These generators enhance basic signals by filtering them through
HTF trend context, ensuring trades align with higher timeframe direction.

Example:
    # RSI signals filtered by 1H SMA200
    long_entries, long_exits, short_entries, short_exits = generate_mtf_rsi_signals(
        ltf_candles=candles_5m,
        htf_candles=candles_1h,
        htf_index_map=htf_map,
        htf_indicator=htf_sma200,
        rsi_period=14,
        overbought=70,
        oversold=30,
    )
"""

import logging

import numpy as np
import pandas as pd

from backend.backtesting.mtf.filters import HTFTrendFilter, calculate_htf_indicator
from backend.core.indicators import calculate_rsi, calculate_sma

logger = logging.getLogger(__name__)


def generate_mtf_rsi_signals(
    ltf_candles: pd.DataFrame,
    htf_candles: pd.DataFrame,
    htf_index_map: np.ndarray,
    htf_indicator: np.ndarray = None,
    # RSI parameters
    rsi_period: int = 14,
    overbought: int = 70,
    oversold: int = 30,
    # HTF filter parameters
    htf_filter_type: str = "sma",
    htf_filter_period: int = 200,
    neutral_zone_pct: float = 0.0,
    # Direction
    direction: str = "both",
    # Entry timing
    warmup_bars: int | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate RSI signals filtered by HTF trend.

    This is the core MTF strategy implementation:
    - RSI crossover/crossunder generates base signals on LTF
    - HTF trend filter allows only aligned signals

    Example (Dav1zoN style):
        RSI oversold on 5m → LONG signal
        But only if 5m close > 15m SMA200 (bullish HTF)

    Args:
        ltf_candles: LTF OHLCV DataFrame
        htf_candles: HTF OHLCV DataFrame
        htf_index_map: Mapping from LTF bar → visible HTF bar
        htf_indicator: Pre-calculated HTF indicator (optional)
        rsi_period: RSI period
        overbought: RSI overbought level
        oversold: RSI oversold level
        htf_filter_type: "sma" or "ema"
        htf_filter_period: HTF indicator period
        neutral_zone_pct: Neutral zone percentage
        direction: "long", "short", or "both"
        warmup_bars: Number of warmup bars (default: rsi_period * 4)

    Returns:
        Tuple of (long_entries, long_exits, short_entries, short_exits)
        Each is a boolean numpy array
    """
    n = len(ltf_candles)

    # Initialize signal arrays
    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    if n == 0:
        return long_entries, long_exits, short_entries, short_exits

    # Get LTF close prices
    ltf_close = ltf_candles["close"].values

    # Calculate LTF RSI (use unified library)
    rsi = calculate_rsi(ltf_close, rsi_period)

    # Calculate or use provided HTF indicator
    htf_close = htf_candles["close"].values
    if htf_indicator is None:
        htf_indicator = calculate_htf_indicator(htf_close, htf_filter_period, htf_filter_type)

    # Create HTF filter
    htf_filter = HTFTrendFilter(
        period=htf_filter_period,
        filter_type=htf_filter_type,
        neutral_zone_pct=neutral_zone_pct,
    )

    # Warmup period
    if warmup_bars is None:
        warmup_bars = rsi_period * 4

    # Generate signals
    for i in range(1, n - 1):  # n-1 for next bar entry
        # Skip warmup
        if i < warmup_bars:
            continue

        # Get visible HTF bar
        htf_idx = htf_index_map[i]
        if htf_idx < 0:
            continue  # No HTF data available yet

        # Get HTF values
        htf_close_val = htf_close[htf_idx]
        htf_ind_val = htf_indicator[htf_idx] if htf_idx < len(htf_indicator) else 0.0

        # Skip if HTF indicator not ready
        if np.isnan(htf_ind_val) or htf_ind_val <= 0:
            continue

        # Check HTF filter
        allow_long, allow_short = htf_filter.check(htf_close_val, htf_ind_val)

        # RSI values
        prev_rsi = rsi[i - 1]
        curr_rsi = rsi[i]

        # LONG signal: RSI crossover oversold + HTF bullish
        if direction in ("long", "both") and prev_rsi <= oversold and curr_rsi > oversold and allow_long:
            long_entries[i + 1] = True  # Entry on next bar

        # SHORT signal: RSI crossunder overbought + HTF bearish
        if direction in ("short", "both") and prev_rsi >= overbought and curr_rsi < overbought and allow_short:
            short_entries[i + 1] = True  # Entry on next bar

    # Log statistics
    n_long = np.sum(long_entries)
    n_short = np.sum(short_entries)
    logger.debug(
        f"MTF RSI signals generated: {n_long} long, {n_short} short "
        f"(HTF filter: {htf_filter_type.upper()}{htf_filter_period})"
    )

    return long_entries, long_exits, short_entries, short_exits


def generate_mtf_sma_crossover_signals(
    ltf_candles: pd.DataFrame,
    htf_candles: pd.DataFrame,
    htf_index_map: np.ndarray,
    htf_indicator: np.ndarray = None,
    # SMA parameters
    fast_period: int = 10,
    slow_period: int = 20,
    # HTF filter parameters
    htf_filter_type: str = "sma",
    htf_filter_period: int = 200,
    neutral_zone_pct: float = 0.0,
    # Direction
    direction: str = "both",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate SMA crossover signals filtered by HTF trend.

    Golden cross / Death cross with HTF trend confirmation.

    Args:
        ltf_candles: LTF OHLCV DataFrame
        htf_candles: HTF OHLCV DataFrame
        htf_index_map: Mapping from LTF bar → visible HTF bar
        htf_indicator: Pre-calculated HTF indicator (optional)
        fast_period: Fast SMA period
        slow_period: Slow SMA period
        htf_filter_type: "sma" or "ema"
        htf_filter_period: HTF indicator period
        neutral_zone_pct: Neutral zone percentage
        direction: "long", "short", or "both"

    Returns:
        Tuple of (long_entries, long_exits, short_entries, short_exits)
    """
    n = len(ltf_candles)

    # Initialize signal arrays
    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    if n == 0:
        return long_entries, long_exits, short_entries, short_exits

    # Get LTF close prices
    ltf_close = ltf_candles["close"].values

    # Calculate LTF SMAs (use unified library)
    fast_sma = calculate_sma(ltf_close, fast_period)
    slow_sma = calculate_sma(ltf_close, slow_period)

    # Calculate or use provided HTF indicator
    htf_close = htf_candles["close"].values
    if htf_indicator is None:
        htf_indicator = calculate_htf_indicator(htf_close, htf_filter_period, htf_filter_type)

    # Create HTF filter
    htf_filter = HTFTrendFilter(
        period=htf_filter_period,
        filter_type=htf_filter_type,
        neutral_zone_pct=neutral_zone_pct,
    )

    # Generate signals
    warmup = max(fast_period, slow_period) + 1
    for i in range(warmup, n):
        # Get visible HTF bar
        htf_idx = htf_index_map[i]
        if htf_idx < 0:
            continue

        # Get HTF values
        htf_close_val = htf_close[htf_idx]
        htf_ind_val = htf_indicator[htf_idx] if htf_idx < len(htf_indicator) else 0.0

        # Skip if HTF indicator not ready
        if np.isnan(htf_ind_val) or htf_ind_val <= 0:
            continue

        # Check HTF filter
        allow_long, allow_short = htf_filter.check(htf_close_val, htf_ind_val)

        # SMA values
        prev_fast = fast_sma[i - 1]
        curr_fast = fast_sma[i]
        prev_slow = slow_sma[i - 1]
        curr_slow = slow_sma[i]

        # Skip if SMAs not ready
        if curr_fast == 0 or curr_slow == 0:
            continue

        # Golden cross: fast crosses above slow + HTF bullish
        if direction in ("long", "both"):
            if prev_fast <= prev_slow and curr_fast > curr_slow and allow_long:
                long_entries[i] = True
            # Death cross for exit
            if prev_fast >= prev_slow and curr_fast < curr_slow:
                long_exits[i] = True

        # Death cross: fast crosses below slow + HTF bearish
        if direction in ("short", "both"):
            if prev_fast >= prev_slow and curr_fast < curr_slow and allow_short:
                short_entries[i] = True
            # Golden cross for exit
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                short_exits[i] = True

    # Log statistics
    n_long = np.sum(long_entries)
    n_short = np.sum(short_entries)
    logger.debug(f"MTF SMA crossover signals generated: {n_long} long, {n_short} short")

    return long_entries, long_exits, short_entries, short_exits


def generate_mtf_signals_with_btc(
    ltf_candles: pd.DataFrame,
    htf_candles: pd.DataFrame,
    htf_index_map: np.ndarray,
    btc_candles: pd.DataFrame,
    btc_index_map: np.ndarray,
    # Strategy parameters
    strategy_type: str = "rsi",
    strategy_params: dict | None = None,
    # HTF filter parameters
    htf_filter_type: str = "sma",
    htf_filter_period: int = 200,
    # BTC filter parameters
    btc_filter_period: int = 50,
    require_btc_alignment: bool = True,
    # Direction
    direction: str = "both",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate signals with both HTF trend and BTC correlation filtering.

    Double filter:
    1. HTF trend filter (e.g., 1H SMA200)
    2. BTC correlation filter (e.g., BTC D50 SMA)

    Only signals that pass BOTH filters are allowed.

    Args:
        ltf_candles: LTF OHLCV DataFrame
        htf_candles: HTF OHLCV DataFrame
        htf_index_map: LTF → HTF mapping
        btc_candles: BTC OHLCV DataFrame
        btc_index_map: LTF → BTC mapping
        strategy_type: "rsi" or "sma_crossover"
        strategy_params: Strategy-specific parameters
        htf_filter_type: "sma" or "ema"
        htf_filter_period: HTF indicator period
        btc_filter_period: BTC SMA period
        require_btc_alignment: If True, require BTC confirmation
        direction: "long", "short", or "both"

    Returns:
        Tuple of (long_entries, long_exits, short_entries, short_exits)
    """
    n = len(ltf_candles)
    strategy_params = strategy_params or {}

    # Generate base signals based on strategy type
    if strategy_type == "rsi":
        long_entries, long_exits, short_entries, short_exits = generate_mtf_rsi_signals(
            ltf_candles=ltf_candles,
            htf_candles=htf_candles,
            htf_index_map=htf_index_map,
            htf_filter_type=htf_filter_type,
            htf_filter_period=htf_filter_period,
            direction=direction,
            **strategy_params,
        )
    elif strategy_type == "sma_crossover":
        long_entries, long_exits, short_entries, short_exits = generate_mtf_sma_crossover_signals(
            ltf_candles=ltf_candles,
            htf_candles=htf_candles,
            htf_index_map=htf_index_map,
            htf_filter_type=htf_filter_type,
            htf_filter_period=htf_filter_period,
            direction=direction,
            **strategy_params,
        )
    else:
        raise ValueError(f"Unknown strategy type: {strategy_type}")

    # Apply BTC filter if required
    if require_btc_alignment and btc_candles is not None and btc_index_map is not None:
        btc_close = btc_candles["close"].values
        btc_sma = calculate_htf_indicator(btc_close, btc_filter_period, "sma")

        # Filter signals by BTC alignment
        for i in range(n):
            if not (long_entries[i] or short_entries[i]):
                continue

            btc_idx = btc_index_map[i]
            if btc_idx < 0 or btc_idx >= len(btc_close):
                # No BTC data - remove signal
                long_entries[i] = False
                short_entries[i] = False
                continue

            btc_close_val = btc_close[btc_idx]
            btc_sma_val = btc_sma[btc_idx] if btc_idx < len(btc_sma) else 0.0

            if np.isnan(btc_sma_val) or btc_sma_val <= 0:
                continue

            btc_bullish = btc_close_val > btc_sma_val
            btc_bearish = btc_close_val < btc_sma_val

            # Filter: LONG only if BTC bullish
            if long_entries[i] and not btc_bullish:
                long_entries[i] = False

            # Filter: SHORT only if BTC bearish
            if short_entries[i] and not btc_bearish:
                short_entries[i] = False

    # Log final statistics
    n_long = np.sum(long_entries)
    n_short = np.sum(short_entries)
    logger.info(
        f"MTF+BTC signals generated: {n_long} long, {n_short} short "
        f"(strategy={strategy_type}, btc_filter={require_btc_alignment})"
    )

    return long_entries, long_exits, short_entries, short_exits
