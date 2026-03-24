"""
Oscillator indicators - осцилляторы.

Этот модуль содержит обработчики для осцилляторов:
- rsi, macd, stochastic, stoch_rsi, cci, cmf, mfi, cmo
- williams_r, roc, qqe, rvi_filter
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from loguru import logger

try:
    import vectorbt as vbt
except ImportError:
    vbt = None

from backend.backtesting.strategy_builder_adapter import _clamp_period, _param
from backend.core.indicators import (
    calculate_cci,
    calculate_cmf,
    calculate_cmo,
    calculate_mfi,
    calculate_qqe_cross,
    calculate_roc,
    calculate_rsi,
    calculate_rvi,
    calculate_stoch_rsi,
    calculate_williams_r,
)

if TYPE_CHECKING:
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter


# ═══════════════════════════════════════════════════════════════════════════
# Momentum / Oscillator indicators
# ═══════════════════════════════════════════════════════════════════════════


def _handle_rsi(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle RSI (Relative Strength Index) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with RSI values and signals.
    """
    period = _clamp_period(params.get("period", 14))

    # ── use_btc_source: compute RSI on BTCUSDT close instead of the current symbol ──
    # TradingView "Use BTCUSDT as Source for RSI" passes BTC prices to the RSI formula
    # while trading/evaluating signals on the altcoin chart. When enabled, the adapter
    # must have been constructed with btcusdt_ohlcv that ideally includes warmup bars
    # before the strategy period so that Wilder's smoothed RSI is fully converged.
    rsi_source = close  # default: current symbol close
    rsi_full_series: pd.Series | None = None  # pre-computed RSI on full BTC (incl. warmup)
    btc_rsi_full: pd.Series | None = None  # full-index BTC RSI (with warmup, before reindex)
    btc_close_full: pd.Series | None = None  # BTC 30m close series (full, with warmup)

    if params.get("use_btc_source", False):
        btc_ohlcv = getattr(adapter, "_btcusdt_ohlcv", None)
        if btc_ohlcv is not None and len(btc_ohlcv) > 0:
            # Normalise timezone so the index comparison works.
            btc_close = btc_ohlcv["close"].copy()
            if close.index.tz is None and btc_close.index.tz is not None:
                btc_close.index = btc_close.index.tz_localize(None)
            elif close.index.tz is not None and btc_close.index.tz is None:
                btc_close.index = btc_close.index.tz_localize("UTC")

            # Store full BTC 30m close series (with warmup) for intra-bar Wilder state reconstruction
            btc_close_full = btc_close

            # Compute RSI on the FULL BTC series (may include warmup bars before strategy start).
            # This is the key step: Wilder's smoothing converges over the warmup period so that
            # RSI values at the strategy start match TradingView (which has years of history).
            btc_rsi_full_arr = calculate_rsi(btc_close.values, period=period)
            btc_rsi_full = pd.Series(btc_rsi_full_arr, index=btc_close.index)

            # Trim (reindex) the already-computed RSI to the strategy period.
            # forward-fill handles any minor timestamp gaps between BTC and ETH bars.
            rsi_trimmed = btc_rsi_full.reindex(close.index, method="ffill")
            na_ratio = rsi_trimmed.isna().mean()
            if na_ratio < 0.2:
                # Use this as the final RSI series — override the default rsi_arr computation below
                rsi_full_series = rsi_trimmed.fillna(
                    pd.Series(calculate_rsi(close.values, period=period), index=close.index)
                )
                logger.debug(
                    "RSI node | using BTCUSDT RSI source with {} warmup bars (na_ratio={:.1%})",
                    max(0, len(btc_close) - len(close)),
                    na_ratio,
                )
            else:
                logger.warning(
                    "RSI use_btc_source=True but alignment too poor (na_ratio={:.1%}) — falling back to main symbol",
                    na_ratio,
                )
        else:
            logger.warning(
                "RSI use_btc_source=True but btcusdt_ohlcv not provided to adapter — falling back to main symbol"
            )

    # Use Wilder's smoothed RSI (SMA seed + Wilder smoothing) which matches TradingView exactly.
    # vbt.RSI uses a different smoothing (pure EWM) that diverges from TV RSI values.
    if rsi_full_series is not None:
        # BTC-sourced RSI already computed above (with warmup)
        rsi = rsi_full_series
    else:
        rsi_arr = calculate_rsi(rsi_source.values, period=period)
        rsi = pd.Series(rsi_arr, index=close.index)

    use_long_range = params.get("use_long_range", False)
    use_short_range = params.get("use_short_range", False)
    use_cross_level = params.get("use_cross_level", False)

    logger.debug(
        "RSI node | period={} | modes: long_range={}, short_range={}, cross={}",
        period,
        use_long_range,
        use_short_range,
        use_cross_level,
    )

    # --- Range filter ---
    if use_long_range:
        long_more = float(params.get("long_rsi_more", 0))  # TV: longRSIMin=0  (>= lower bound)
        long_less = float(params.get("long_rsi_less", 50))  # TV: longRSIMax=50 (<= upper bound)
        if long_more > long_less:
            logger.warning(
                "RSI range inversion: long_more={} > long_less={} — swapping",
                long_more,
                long_less,
            )
            long_more, long_less = long_less, long_more
        long_range_condition = (rsi >= long_more) & (rsi <= long_less)
    else:
        long_range_condition = pd.Series(True, index=ohlcv.index)

    if use_short_range:
        short_less = float(params.get("short_rsi_less", 100))  # TV: shortRSIMax=100 (<= upper bound)
        short_more = float(params.get("short_rsi_more", 50))  # TV: shortRSIMin=50  (>= lower bound)
        if short_more > short_less:
            logger.warning(
                "RSI range inversion: short_more={} > short_less={} — swapping",
                short_more,
                short_less,
            )
            short_more, short_less = short_less, short_more
        short_range_condition = (rsi <= short_less) & (rsi >= short_more)
    else:
        short_range_condition = pd.Series(True, index=ohlcv.index)

    # --- Cross level ---
    if use_cross_level:
        cross_long_level = params.get("cross_long_level", 29)  # TV: crossLevelLong=29
        cross_short_level = params.get("cross_short_level", 55)  # TV: crossLevelShort=55

        # ── Validate cross+range compatibility ──────────────────────────────────────
        # When both cross_level AND range are active, they are evaluated as:
        #   long_signal = cross_long AND range_condition (both on the SAME bar)
        # This means:
        #   - cross_long fires when RSI crosses UP through cross_long_level (RSI ≈ cross_long_level)
        #   - range_condition requires RSI >= long_rsi_more
        # If cross_long_level < long_rsi_more, the cross happens below the range minimum,
        # so long_signal is ALWAYS False (0 signals). Warn the user.
        if use_long_range and "long_rsi_more" in params:
            _long_more = float(params["long_rsi_more"])
            _cross_l = float(cross_long_level)
            if _cross_l < _long_more:
                logger.warning(
                    "RSI CONFIG CONFLICT: cross_long_level={} < long_rsi_more={} — "
                    "when RSI crosses UP through {}, it is at ~{} which is BELOW the "
                    "range minimum {}. Combined condition (cross AND range) will produce "
                    "0 long signals unless RSI jumps > {} points in a single bar. "
                    "Fix: set cross_long_level >= long_rsi_more (e.g. cross_long_level={}) "
                    "OR reduce long_rsi_more to <= cross_long_level (e.g. long_rsi_more={}).",
                    _cross_l,
                    _long_more,
                    _cross_l,
                    _cross_l,
                    _long_more,
                    _long_more - _cross_l,
                    int(_long_more),
                    int(_cross_l),
                )
        if use_short_range and "short_rsi_less" in params:
            _short_less = float(params["short_rsi_less"])
            _cross_s = float(cross_short_level)
            if _cross_s > _short_less:
                logger.warning(
                    "RSI CONFIG CONFLICT: cross_short_level={} > short_rsi_less={} — "
                    "when RSI crosses DOWN through {}, it is at ~{} which is ABOVE the "
                    "range maximum {}. Combined condition (cross AND range) will produce "
                    "0 short signals. "
                    "Fix: set cross_short_level <= short_rsi_less (e.g. cross_short_level={}) "
                    "OR raise short_rsi_less to >= cross_short_level (e.g. short_rsi_less={}).",
                    _cross_s,
                    _short_less,
                    _cross_s,
                    _cross_s,
                    _short_less,
                    int(_short_less),
                    int(_cross_s),
                )

        rsi_prev = rsi.shift(1)
        # TradingView Pine Script ta.crossover(a, b) = a[1] < b  AND a >= b
        # TradingView Pine Script ta.crossunder(a, b) = a[1] > b AND a <= b
        # i.e. prev must be STRICTLY below/above the level (not equal).
        # Previously we used <= and >= for prev which included prev==level, producing
        # extra false signals when RSI was exactly at the level on the previous bar.
        cross_long = (rsi_prev < cross_long_level) & (rsi >= cross_long_level)
        cross_short = (rsi_prev > cross_short_level) & (rsi <= cross_short_level)

        if params.get("opposite_signal", False):
            cross_long, cross_short = cross_short, cross_long

        if params.get("use_cross_memory", False):
            memory_bars = int(params.get("cross_memory_bars", 5))
            cross_long = adapter._apply_signal_memory(cross_long, memory_bars)
            cross_short = adapter._apply_signal_memory(cross_short, memory_bars)

        long_cross_condition = cross_long
        short_cross_condition = cross_short
    else:
        long_cross_condition = pd.Series(True, index=ohlcv.index)
        short_cross_condition = pd.Series(True, index=ohlcv.index)

    # ── TRADINGVIEW PARITY FIX (2026-03-01) ──────────────────────────────────
    # After deep analysis of TV export a4.csv (154 trades) and bar-by-bar comparison:
    #
    # TV signal logic: cross AND range (both conditions must be true)
    # - RsiSE (Short Entry): RSI crosses DOWN through cross_short_level AND RSI in short_range
    # - RsiLE (Long Entry):  RSI crosses UP through cross_long_level AND RSI in long_range
    #
    # TV executes strategy.entry() on the NEXT bar's open after the signal bar.
    # The entry price in the trade log equals open[signal_bar + 1].
    # ──────────────────────────────────────────────────────────────────────────

    if use_long_range and use_cross_level:
        _cross_l = float(params.get("cross_long_level", 29))
        _long_more = float(params.get("long_rsi_more", 0))
        if _cross_l < _long_more:
            # Config conflict: cross below range minimum.
            # Extend cross condition: also fire when RSI crosses UP through long_rsi_more
            # (i.e. enters the range from below), in addition to the original cross trigger.
            rsi_prev_for_conflict = rsi.shift(1)
            cross_into_range = (rsi_prev_for_conflict < _long_more) & (rsi >= _long_more)
            long_cross_condition_extended = long_cross_condition | cross_into_range
            long_signal = long_cross_condition_extended & long_range_condition
            logger.debug(
                "RSI cross+range conflict resolved: cross_long_level={} < long_rsi_more={} "
                "→ added cross-into-range trigger (RSI crosses UP through {}). "
                "cross_only={} cross_into_range={} combined={}",
                _cross_l,
                _long_more,
                _long_more,
                int(long_cross_condition.sum()),
                int(cross_into_range.sum()),
                int(long_signal.sum()),
            )
        else:
            long_signal = long_cross_condition & long_range_condition
    elif use_long_range:
        long_signal = long_range_condition
    else:
        long_signal = long_cross_condition

    if use_short_range and use_cross_level:
        _cross_s = float(params.get("cross_short_level", 55))
        _short_less = float(params.get("short_rsi_less", 100))
        if _cross_s > _short_less:
            # Config conflict: cross above range maximum.
            # Extend cross condition: also fire when RSI crosses DOWN through short_rsi_less.
            rsi_prev_for_conflict = rsi.shift(1)
            cross_into_range_s = (rsi_prev_for_conflict > _short_less) & (rsi <= _short_less)
            short_cross_condition_extended = short_cross_condition | cross_into_range_s
            short_signal = short_cross_condition_extended & short_range_condition
            logger.debug(
                "RSI cross+range conflict resolved: cross_short_level={} > short_rsi_less={} "
                "→ added cross-into-range trigger (RSI crosses DOWN through {}). "
                "combined={}",
                _cross_s,
                _short_less,
                _short_less,
                int(short_signal.sum()),
            )
        else:
            short_signal = short_cross_condition & short_range_condition
    elif use_short_range:
        short_signal = short_range_condition
    else:
        short_signal = short_cross_condition

    # Legacy overbought/oversold mode: when no new modes are active, use oversold/overbought thresholds
    overbought = float(params.get("overbought", 0))
    oversold = float(params.get("oversold", 0))
    if overbought > 0 and oversold > 0 and not use_long_range and not use_short_range and not use_cross_level:
        long_signal = (rsi <= oversold).fillna(False)
        short_signal = (rsi >= overbought).fillna(False)

    # Apply memory in range-only mode (cross_level branch handles its own memory above)
    if params.get("use_cross_memory", False) and not use_cross_level:
        memory_bars = int(params.get("cross_memory_bars", 5))
        long_signal = adapter._apply_signal_memory(long_signal, memory_bars)
        short_signal = adapter._apply_signal_memory(short_signal, memory_bars)

    logger.debug(
        "RSI node | long_signals={}, short_signals={}",
        long_signal.sum(),
        short_signal.sum(),
    )
    return {"long": long_signal, "short": short_signal, "value": rsi}


def _handle_macd(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle MACD (Moving Average Convergence Divergence) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with MACD components and signals.
    """
    fast = _clamp_period(_param(params, 12, "fast_period", "fastPeriod"))
    slow = _clamp_period(_param(params, 26, "slow_period", "slowPeriod"))
    signal_p = _clamp_period(_param(params, 9, "signal_period", "signalPeriod"))

    # Use ewm(adjust=False) to match TradingView ta.ema() / ta.macd() exactly.
    # vbt.MACD.run() uses a different EMA seed that produces significantly
    # different values (max diff ~22 USDT on ETHUSDT 30m), causing ~10x more
    # crossovers and breaking TV parity.  See CLAUDE.md §5 and DECISIONS.md.
    fast_ema = close.ewm(span=fast, adjust=False).mean()
    slow_ema = close.ewm(span=slow, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal_p, adjust=False).mean()
    histogram = macd_line - signal_line

    # Support both old keys (use_macd_cross / use_zero_cross) and new frontend keys
    # (use_macd_cross_signal / use_macd_cross_zero).
    use_cross = params.get("use_macd_cross_signal", params.get("use_macd_cross", False))
    use_histogram = params.get("use_histogram", False)
    use_zero_cross = params.get("use_macd_cross_zero", params.get("use_zero_cross", False))

    # MACD uses OR logic: signals from ANY active mode are combined with |
    # When no mode is active → data-only mode (all False)
    long_signal = pd.Series(False, index=ohlcv.index)
    short_signal = pd.Series(False, index=ohlcv.index)

    # Default fresh-signal masks (populated inside each mode block).
    fresh_cross_long = pd.Series(False, index=ohlcv.index)
    fresh_cross_short = pd.Series(False, index=ohlcv.index)
    fresh_zero_cross_long = pd.Series(False, index=ohlcv.index)
    fresh_zero_cross_short = pd.Series(False, index=ohlcv.index)
    cross_long_mem = pd.Series(False, index=ohlcv.index)
    cross_short_mem = pd.Series(False, index=ohlcv.index)

    if use_cross:
        macd_prev = macd_line.shift(1)
        signal_prev = signal_line.shift(1)
        cross_long = (macd_prev <= signal_prev) & (macd_line > signal_line)
        cross_short = (macd_prev >= signal_prev) & (macd_line < signal_line)

        if params.get("opposite_macd_cross_signal", params.get("opposite_signal", False)):
            cross_long, cross_short = cross_short, cross_long

        # signal_only_if_macd_positive:
        #   long only when MACD > 0 (MACD line above zero — positive momentum)
        #   short only when MACD < 0 (MACD line below zero — negative momentum)
        # Matches TradingView label: "Filter by Zero (LONG if MACD>0, SHORT if MACD<0)"
        if params.get("signal_only_if_macd_positive", False):
            cross_long = cross_long & (macd_line > 0)
            cross_short = cross_short & (macd_line < 0)

        # Keep track of fresh (raw, non-memory) cross signals for conflict resolution.
        fresh_cross_long = cross_long.copy()
        fresh_cross_short = cross_short.copy()

        # Memory: frontend sends disable_signal_memory (default False = memory ON) + signal_memory_bars.
        # Legacy path: use_cross_memory + cross_memory_bars.
        disable_memory = params.get("disable_signal_memory", False)
        if not disable_memory or params.get("use_cross_memory", False):
            memory_bars = int(params.get("signal_memory_bars", params.get("cross_memory_bars", 5)))
            cross_long = adapter._apply_signal_memory(cross_long, memory_bars)
            cross_short = adapter._apply_signal_memory(cross_short, memory_bars)

        # Store memory-extended cross signals for potential AND combination with zero_cross.
        cross_long_mem = cross_long.fillna(False)
        cross_short_mem = cross_short.fillna(False)

    if use_histogram:
        hist_threshold = float(params.get("histogram_threshold", 0))
        long_signal = long_signal | (histogram > hist_threshold)
        short_signal = short_signal | (histogram < -hist_threshold)

    if use_zero_cross:
        zero_level = float(params.get("macd_cross_zero_level", params.get("zero_level", 0.0)))
        macd_prev = macd_line.shift(1)
        zero_cross_long = (macd_prev <= zero_level) & (macd_line > zero_level)
        zero_cross_short = (macd_prev >= zero_level) & (macd_line < zero_level)

        if params.get("opposite_macd_cross_zero", params.get("opposite_signal", False)):
            zero_cross_long, zero_cross_short = zero_cross_short, zero_cross_long

        # Track fresh zero-cross signals before memory extension.
        fresh_zero_cross_long = zero_cross_long.copy()
        fresh_zero_cross_short = zero_cross_short.copy()

        disable_memory = params.get("disable_signal_memory", False)
        if not disable_memory or params.get("use_zero_cross_memory", False):
            memory_bars = int(params.get("signal_memory_bars", params.get("zero_cross_memory_bars", 5)))
            zero_cross_long = adapter._apply_signal_memory(zero_cross_long, memory_bars)
            zero_cross_short = adapter._apply_signal_memory(zero_cross_short, memory_bars)

        zero_cross_long_mem = zero_cross_long.fillna(False)
        zero_cross_short_mem = zero_cross_short.fillna(False)

        if use_cross:
            # Both cross_signal AND cross_zero are enabled: TV uses AND logic —
            # a trade fires only when BOTH conditions trigger on the SAME bar (fresh AND).
            # Memory is then applied to that combined signal.
            # This is the key TradingView parity fix: OR (or AND of memory-extended signals)
            # produces too many signals; the AND must be on the raw/fresh signals.
            both_long_raw = fresh_cross_long.fillna(False) & fresh_zero_cross_long.fillna(False)
            both_short_raw = fresh_cross_short.fillna(False) & fresh_zero_cross_short.fillna(False)
            # Apply memory to the combined signal so position can be held.
            disable_memory = params.get("disable_signal_memory", False)
            if not disable_memory:
                memory_bars = int(params.get("signal_memory_bars", params.get("cross_memory_bars", 5)))
                both_long_mem = adapter._apply_signal_memory(both_long_raw, memory_bars)
                both_short_mem = adapter._apply_signal_memory(both_short_raw, memory_bars)
            else:
                both_long_mem = both_long_raw
                both_short_mem = both_short_raw
            long_signal = long_signal | both_long_mem.fillna(False)
            short_signal = short_signal | both_short_mem.fillna(False)
        else:
            # Only zero_cross is enabled: plain OR (additive).
            long_signal = long_signal | zero_cross_long_mem
            short_signal = short_signal | zero_cross_short_mem
    elif use_cross:
        # Only cross_signal is enabled (no zero_cross): apply directly.
        long_signal = long_signal | cross_long_mem
        short_signal = short_signal | cross_short_mem

    # Conflict resolution: when both long and short are simultaneously active,
    # prefer the direction with a FRESH (non-memory) signal.  This matches
    # TradingView behaviour where a new cross in one direction cancels the
    # memory extension of the opposite direction.
    #
    # Build a combined "fresh signal" mask from all active modes.
    fresh_long = pd.Series(False, index=ohlcv.index)
    fresh_short = pd.Series(False, index=ohlcv.index)
    if use_cross:
        fresh_long = fresh_long | fresh_cross_long.fillna(False)
        fresh_short = fresh_short | fresh_cross_short.fillna(False)
    if use_zero_cross:
        fresh_long = fresh_long | fresh_zero_cross_long.fillna(False)
        fresh_short = fresh_short | fresh_zero_cross_short.fillna(False)

    conflict = long_signal & short_signal  # bars where both are active
    if conflict.any():
        # Where both fire and SHORT is fresh → suppress LONG (memory-only)
        long_signal = long_signal & ~(conflict & fresh_short & ~fresh_long)
        # Where both fire and LONG is fresh → suppress SHORT (memory-only)
        short_signal = short_signal & ~(conflict & fresh_long & ~fresh_short)

    logger.debug(
        "MACD node | fast={} slow={} signal={} | cross={} hist={} zero={} | long={} short={}",
        fast,
        slow,
        signal_p,
        use_cross,
        use_histogram,
        use_zero_cross,
        long_signal.sum(),
        short_signal.sum(),
    )
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
        "long": long_signal,
        "short": short_signal,
    }


def _handle_stochastic(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle Stochastic Oscillator indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with Stochastic %K and %D lines and signals.
    """
    k_period = _clamp_period(_param(params, 14, "stoch_k_length", "k_period", "k"))
    k_smooth = _clamp_period(_param(params, 3, "stoch_k_smoothing", "smooth_k"))
    d_smooth = _clamp_period(_param(params, 3, "stoch_d_smoothing", "d_period", "d"))
    high = ohlcv["high"]
    low = ohlcv["low"]
    stoch = vbt.STOCH.run(high, low, close, k_window=k_period, d_window=d_smooth, d_ewm=False)

    k_line = stoch.percent_k
    d_line = stoch.percent_d
    if k_smooth > 1:
        k_line = k_line.rolling(k_smooth).mean()

    # Support both old and new param names
    use_long_range = params.get("use_long_range", params.get("use_stoch_range_filter", False))
    use_short_range = params.get("use_short_range", params.get("use_stoch_range_filter", False))
    use_cross_level = params.get("use_cross_level", params.get("use_stoch_cross_level", False))
    use_kd_cross = params.get("use_kd_cross", params.get("use_stoch_kd_cross", False))

    long_signal = pd.Series(True, index=ohlcv.index)
    short_signal = pd.Series(True, index=ohlcv.index)

    # Legacy overbought/oversold mode: treat as range filter
    overbought = float(params.get("overbought", 0))
    oversold = float(params.get("oversold", 0))
    if (
        overbought > 0
        and oversold > 0
        and not use_long_range
        and not use_short_range
        and not use_cross_level
        and not use_kd_cross
    ):
        # Legacy: use %D for range (oversold = entry for long, overbought = entry for short)
        long_signal = long_signal & (d_line <= oversold).fillna(False)
        short_signal = short_signal & (d_line >= overbought).fillna(False)
    else:
        if use_long_range:
            # Support both old (long_stoch_more) and new (long_stoch_d_more) param names
            # When param names contain "_d_" (e.g. long_stoch_d_more), filter by %D line
            long_more = float(
                params.get("long_stoch_d_more", params.get("long_stoch_more", params.get("long_more", 20)))
            )
            long_less = float(
                params.get("long_stoch_d_less", params.get("long_stoch_less", params.get("long_less", 80)))
            )
            if long_more > long_less:
                logger.warning(
                    "Stochastic range inversion: long swapping {} > {}",
                    long_more,
                    long_less,
                )
                long_more, long_less = long_less, long_more
            # Use d_line when params explicitly reference %D (e.g. long_stoch_d_more/long_stoch_d_less)
            use_d_for_long = "long_stoch_d_more" in params or "long_stoch_d_less" in params
            filter_line_long = d_line if use_d_for_long else k_line
            long_signal = long_signal & (filter_line_long >= long_more) & (filter_line_long <= long_less)

        if use_short_range:
            short_more = float(
                params.get("short_stoch_d_more", params.get("short_stoch_more", params.get("short_more", 20)))
            )
            short_less = float(
                params.get("short_stoch_d_less", params.get("short_stoch_less", params.get("short_less", 80)))
            )
            if short_more > short_less:
                logger.warning(
                    "Stochastic range inversion: short swapping {} > {}",
                    short_more,
                    short_less,
                )
                short_more, short_less = short_less, short_more
            # Use d_line when params explicitly reference %D (e.g. short_stoch_d_more/short_stoch_d_less)
            use_d_for_short = "short_stoch_d_more" in params or "short_stoch_d_less" in params
            filter_line_short = d_line if use_d_for_short else k_line
            short_signal = short_signal & (filter_line_short <= short_less) & (filter_line_short >= short_more)

        if use_cross_level:
            # Support both old (cross_long_level) and new (stoch_cross_level_long) param names
            cross_long_level = float(params.get("stoch_cross_level_long", params.get("cross_long_level", 20)))
            cross_short_level = float(params.get("stoch_cross_level_short", params.get("cross_short_level", 80)))
            k_prev = k_line.shift(1)
            cross_long = (k_prev <= cross_long_level) & (k_line > cross_long_level)
            cross_short = (k_prev >= cross_short_level) & (k_line < cross_short_level)

            if params.get("opposite_signal", False):
                cross_long, cross_short = cross_short, cross_long

            # Support both old (use_cross_memory) and new (activate_stoch_cross_memory) param names
            use_cross_mem = params.get("use_cross_memory", params.get("activate_stoch_cross_memory", False))
            if use_cross_mem:
                memory_bars = int(params.get("stoch_cross_memory_bars", params.get("cross_memory_bars", 5)))
                cross_long = adapter._apply_signal_memory(cross_long, memory_bars)
                cross_short = adapter._apply_signal_memory(cross_short, memory_bars)

            long_signal = long_signal & cross_long.fillna(False)
            short_signal = short_signal & cross_short.fillna(False)

        if use_kd_cross:
            k_prev = k_line.shift(1)
            d_prev = d_line.shift(1)
            kd_cross_long = (k_prev <= d_prev) & (k_line > d_line)
            kd_cross_short = (k_prev >= d_prev) & (k_line < d_line)

            # Support both old (opposite_kd_cross) and new (opposite_stoch_kd) param names
            if params.get("opposite_stoch_kd", params.get("opposite_kd_cross", False)):
                kd_cross_long, kd_cross_short = kd_cross_short, kd_cross_long

            # Support both old (use_kd_cross_memory) and new (activate_stoch_kd_memory) param names
            use_kd_mem = params.get("use_kd_cross_memory", params.get("activate_stoch_kd_memory", False))
            if use_kd_mem:
                memory_bars = int(params.get("stoch_kd_memory_bars", params.get("kd_cross_memory_bars", 5)))
                kd_cross_long = adapter._apply_signal_memory(kd_cross_long, memory_bars)
                kd_cross_short = adapter._apply_signal_memory(kd_cross_short, memory_bars)

            long_signal = long_signal & kd_cross_long.fillna(False)
            short_signal = short_signal & kd_cross_short.fillna(False)

    long_signal = long_signal.fillna(False)
    short_signal = short_signal.fillna(False)

    logger.debug(
        "STOCH node | k={} d={} | range/cross/kd | long={} short={}",
        k_period,
        d_smooth,
        long_signal.sum(),
        short_signal.sum(),
    )
    return {"k": k_line, "d": d_line, "long": long_signal, "short": short_signal}


def _handle_qqe(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle QQE (Quantitative Qualitative Estimation) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with QQE components and signals.
    """
    rsi_period = _clamp_period(_param(params, 14, "rsi_period", "rsiPeriod", "qqe_rsi_length"))
    smoothing = _clamp_period(_param(params, 5, "smoothing_period", "smoothing", "qqe_rsi_smoothing"))
    qqe_factor = _param(params, 4.236, "qqe_factor", "qqeFactor", "qqe_delta_multiplier")

    qqe_result = calculate_qqe_cross(
        close.values, rsi_period=rsi_period, smoothing_factor=smoothing, qqe_factor=qqe_factor
    )

    qqe_line = pd.Series(qqe_result["qqe_line"], index=ohlcv.index)
    rsi_ma = pd.Series(qqe_result["rsi_ma"], index=ohlcv.index)
    upper_band = pd.Series(qqe_result["upper_band"], index=ohlcv.index)
    lower_band = pd.Series(qqe_result["lower_band"], index=ohlcv.index)
    histogram = pd.Series(qqe_result["histogram"], index=ohlcv.index)
    trend = pd.Series(qqe_result["trend"], index=ohlcv.index)

    use_qqe = params.get("use_qqe", False)

    if not use_qqe:
        n = len(ohlcv)
        long_sig = pd.Series(np.ones(n, dtype=bool), index=ohlcv.index)
        short_sig = pd.Series(np.ones(n, dtype=bool), index=ohlcv.index)
    else:
        buy_raw = pd.Series(qqe_result["buy_signal"], index=ohlcv.index)
        sell_raw = pd.Series(qqe_result["sell_signal"], index=ohlcv.index)

        disable_memory = params.get("disable_qqe_signal_memory", False)
        if not disable_memory:
            memory_bars = int(params.get("qqe_signal_memory_bars", 5))
            long_sig = adapter._apply_signal_memory(buy_raw, memory_bars)
            short_sig = adapter._apply_signal_memory(sell_raw, memory_bars)
        else:
            long_sig = buy_raw.astype(bool)
            short_sig = sell_raw.astype(bool)

        opposite = params.get("opposite_qqe", params.get("opposite_signal", False))
        if opposite:
            long_sig, short_sig = short_sig, long_sig

    return {
        "qqe_line": qqe_line,
        "rsi_ma": rsi_ma,
        "upper_band": upper_band,
        "lower_band": lower_band,
        "histogram": histogram,
        "trend": trend,
        "long": long_sig,
        "short": short_sig,
    }


def _handle_stoch_rsi(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle StochRSI (Stochastic RSI) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with StochRSI %K and %D lines.
    """
    rsi_period = _clamp_period(_param(params, 14, "rsi_period", "rsiPeriod"))
    stoch_period = _clamp_period(_param(params, 14, "stoch_period", "stochPeriod"))
    k_period = _clamp_period(_param(params, 3, "k_period", "kPeriod"))
    d_period = _clamp_period(_param(params, 3, "d_period", "dPeriod"))
    _stoch_rsi_vals, k_vals, d_vals = calculate_stoch_rsi(close.values, rsi_period, stoch_period, k_period, d_period)
    return {
        "k": pd.Series(k_vals, index=ohlcv.index),
        "d": pd.Series(d_vals, index=ohlcv.index),
    }


def _handle_williams_r(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle Williams %R indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with Williams %R values.
    """
    period = _clamp_period(params.get("period", 14))
    result = calculate_williams_r(ohlcv["high"].values, ohlcv["low"].values, close.values, period)
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_roc(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle ROC (Rate of Change) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with ROC values.
    """
    period = _clamp_period(params.get("period", 10))
    result = calculate_roc(close.values, period)
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_mfi(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle MFI (Money Flow Index) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with MFI values.
    """
    period = _clamp_period(params.get("period", 14))
    result = calculate_mfi(
        ohlcv["high"].values,
        ohlcv["low"].values,
        close.values,
        ohlcv["volume"].values,
        period,
    )
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_cmo(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle CMO (Chande Momentum Oscillator) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with CMO values.
    """
    period = _clamp_period(params.get("period", 14))
    result = calculate_cmo(close.values, period)
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_cci(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle CCI (Commodity Channel Index) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with CCI values.
    """
    period = _clamp_period(params.get("period", 20))
    result = calculate_cci(ohlcv["high"].values, ohlcv["low"].values, close.values, period)
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_cmf(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle CMF (Chaikin Money Flow) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with CMF values.
    """
    period = _clamp_period(params.get("period", 20))
    result = calculate_cmf(
        ohlcv["high"].values,
        ohlcv["low"].values,
        close.values,
        ohlcv["volume"].values,
        period,
    )
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_rvi_filter(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle RVI (Relative Vigor Index) filter.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with RVI values and signals.
    """
    rvi_len = int(params.get("rvi_length", 10))
    ma_type = str(params.get("rvi_ma_type", "WMA")).upper()
    ma_len = int(params.get("rvi_ma_length", 2))

    rvi_vals = pd.Series(
        calculate_rvi(
            close.values,
            ohlcv["high"].values,
            ohlcv["low"].values,
            length=rvi_len,
            ma_type=ma_type,
            ma_length=ma_len,
        ),
        index=ohlcv.index,
    )

    long_signal = pd.Series(True, index=ohlcv.index)
    short_signal = pd.Series(True, index=ohlcv.index)

    if params.get("use_rvi_long_range", False):
        lo = float(params.get("rvi_long_more", 1))
        hi = float(params.get("rvi_long_less", 50))
        long_signal = long_signal & (rvi_vals >= lo) & (rvi_vals <= hi)
        long_signal = long_signal.fillna(False)

    if params.get("use_rvi_short_range", False):
        hi_s = float(params.get("rvi_short_less", 100))
        lo_s = float(params.get("rvi_short_more", 50))
        short_signal = short_signal & (rvi_vals <= hi_s) & (rvi_vals >= lo_s)
        short_signal = short_signal.fillna(False)

    logger.debug(
        "RVI filter | len={} | long={} short={}",
        rvi_len,
        long_signal.sum(),
        short_signal.sum(),
    )
    return {"long": long_signal, "short": short_signal, "rvi": rvi_vals}


# ═══════════════════════════════════════════════════════════════════════════
# Block Registry
# ═══════════════════════════════════════════════════════════════════════════

BLOCK_REGISTRY: dict[str, dict[str, Any]] = {
    # ── Momentum / Oscillators ───────────────────────────────────────────
    "rsi": {
        "handler": _handle_rsi,
        "outputs": ["value", "long", "short"],
        "param_aliases": {},
    },
    "macd": {
        "handler": _handle_macd,
        "outputs": ["macd", "signal", "histogram", "long", "short"],
        "param_aliases": {
            # Frontend has used multiple names for these bool switches
            "use_macd_cross": "use_macd_cross_signal",
            "use_zero_cross": "use_macd_cross_zero",
            "cross_memory_bars": "signal_memory_bars",
            "opposite_signal": "opposite_macd_cross_signal",
        },
    },
    "stochastic": {
        "handler": _handle_stochastic,
        "outputs": ["k", "d", "long", "short"],
        "param_aliases": {},
    },
    "qqe": {
        "handler": _handle_qqe,
        "outputs": ["qqe_line", "rsi_ma", "upper_band", "lower_band", "histogram", "trend", "long", "short"],
        "param_aliases": {},
    },
    "stoch_rsi": {
        "handler": _handle_stoch_rsi,
        # NOTE: stoch_rsi does NOT return long/short — wire to a condition block first
        "outputs": ["k", "d"],
        "param_aliases": {},
    },
    "williams_r": {
        "handler": _handle_williams_r,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "roc": {
        "handler": _handle_roc,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "mfi": {
        "handler": _handle_mfi,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "cmo": {
        "handler": _handle_cmo,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "cci": {
        "handler": _handle_cci,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "cmf": {
        "handler": _handle_cmf,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "rvi_filter": {
        "handler": _handle_rvi_filter,
        "outputs": ["long", "short", "rvi"],
        "param_aliases": {},
    },
}

# Backward-compatible dispatch table for this module
INDICATOR_DISPATCH: dict[str, Any] = {k: v["handler"] for k, v in BLOCK_REGISTRY.items()}
