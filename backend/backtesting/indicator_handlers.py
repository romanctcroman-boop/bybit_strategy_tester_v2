"""
Indicator handler functions for StrategyBuilderAdapter.

Each handler has the signature:
    handler(params, ohlcv, close, inputs, adapter) -> dict[str, pd.Series]

The dispatch table ``INDICATOR_DISPATCH`` maps indicator_type strings to handlers.
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


def _require_vbt() -> None:
    """Raise ImportError if vectorbt is not installed.

    Call at the top of ``_execute_indicator`` (or any handler that needs vbt)
    to get a clean error instead of ``AttributeError: 'NoneType' object has no
    attribute 'MA'``.
    """
    if vbt is None:
        raise ImportError("vectorbt is required for indicator execution. Install it with: pip install vectorbt")


from backend.backtesting.strategy_builder_adapter import _clamp_period, _param
from backend.core.indicators import (
    calculate_ad_line,
    calculate_aroon,
    calculate_atr,
    calculate_atr_smoothed,
    calculate_atrp,
    calculate_bollinger,
    calculate_cci,
    calculate_cmf,
    calculate_cmo,
    calculate_dema,
    calculate_donchian,
    calculate_hull_ma,
    calculate_ichimoku,
    calculate_keltner,
    calculate_mfi,
    calculate_obv,
    calculate_parabolic_sar,
    calculate_pivot_points_array,
    calculate_pvt,
    calculate_qqe_cross,
    calculate_roc,
    calculate_rsi,
    calculate_rvi,
    calculate_stddev,
    calculate_stoch_rsi,
    calculate_supertrend,
    calculate_tema,
    calculate_vwap,
    calculate_williams_r,
    calculate_wma,
)

if TYPE_CHECKING:
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter


# ---------------------------------------------------------------------------
# Helper used by two_mas handler
# ---------------------------------------------------------------------------
def _calc_ma(src: pd.Series, length: int, ma_type: str) -> pd.Series:
    """Calculate a moving average of the given type."""
    if ma_type == "EMA":
        return src.ewm(span=length, adjust=False).mean()
    elif ma_type == "WMA":
        w = np.arange(1, length + 1, dtype=float)
        return src.rolling(length).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)
    elif ma_type == "RMA":
        return src.ewm(alpha=1 / length, adjust=False).mean()
    else:  # SMA
        return src.rolling(length).mean()


# ═══════════════════════════════════════════════════════════════════════════
# Momentum / Oscillator indicators
# ═══════════════════════════════════════════════════════════════════════════


def _detect_intrabar_rsi_crossings(
    btc_5m: pd.DataFrame,
    bar_index: pd.DatetimeIndex,
    btc_rsi_full: pd.Series,
    btc_30m_close: pd.Series,
    period: int,
    cross_short_level: float,
    cross_long_level: float,
) -> tuple[pd.Series, pd.Series]:
    """Detect RSI crossings that occur WITHIN a higher-timeframe bar using sub-TF ticks.

    TradingView's ``calc_on_every_tick`` evaluates the RSI on every tick (here: every 1m
    close) rather than only at the higher-TF bar close.  This can fire a signal on a bar
    where the bar-close RSI does NOT cross the level, because the RSI dipped/spiked intra-
    bar and then partially reverted.

    Algorithm (one-step hypothetical RSI — matches TradingView)
    -----------------------------------------------------------
    In Pine Script with ``calc_on_every_tick``, at each tick within bar ``k``:

        close    = tick_price          (current tick as the hypothetical bar close)
        close[1] = close of bar k-1   (FIXED for all ticks — previous completed bar)

    The RSI formula computes ``change = close - close[1]`` and applies one Wilder step
    from bar k-1's state.  Crucially, **each tick is computed independently** from the
    same base state — tick T's RSI does NOT depend on tick T-1's RSI.

    For cross detection (``ta.crossunder(rsi, level)``):
        rsi      = RSI at current tick  (one-step hypothetical from bar k-1 state)
        rsi[1]   = RSI at previous tick (also one-step hypothetical from bar k-1 state)

    Both are independent one-step computations from the SAME base.  The cross fires when
    two consecutive ticks straddle the level.

    Parameters
    ----------
    btc_5m : pd.DataFrame
        BTC sub-timeframe OHLCV data (1m or 5m).
    bar_index : pd.DatetimeIndex
        The 30m strategy bar index (ETH chart timestamps).
    btc_rsi_full : pd.Series
        Full BTC 30m RSI series (includes warmup bars, indexed by BTC 30m timestamps).
    btc_30m_close : pd.Series
        Actual BTC 30m close prices (same index as btc_rsi_full). Used to reconstruct
        Wilder avg_gain / avg_loss at each bar without resampling from sub-TF data.
    period : int
        RSI period (default 14).
    cross_short_level, cross_long_level : float
        RSI crossing levels.

    Returns
    -------
    cross_short_ib, cross_long_ib : pd.Series[bool]  indexed by ``bar_index``
        True where an intra-bar crossing was detected.  The caller ORs these with the
        existing bar-close cross signals.
    """
    cross_short_ib = pd.Series(False, index=bar_index)
    cross_long_ib = pd.Series(False, index=bar_index)

    if btc_5m is None or len(btc_5m) == 0 or len(bar_index) < 2:
        return cross_short_ib, cross_long_ib

    # Normalize 5m index timezone to match bar_index
    btc_5m_close = btc_5m["close"].copy()
    if bar_index.tz is None and btc_5m_close.index.tz is not None:
        btc_5m_close.index = btc_5m_close.index.tz_localize(None)
    elif bar_index.tz is not None and btc_5m_close.index.tz is None:
        btc_5m_close.index = btc_5m_close.index.tz_localize("UTC")

    # Normalize btc_30m_close timezone
    btc_30m_close_norm = btc_30m_close.copy()
    if bar_index.tz is None and btc_30m_close_norm.index.tz is not None:
        btc_30m_close_norm.index = btc_30m_close_norm.index.tz_localize(None)
    elif bar_index.tz is not None and btc_30m_close_norm.index.tz is None:
        btc_30m_close_norm.index = btc_30m_close_norm.index.tz_localize("UTC")

    btc_5m_arr = btc_5m_close.values
    btc_5m_idx_arr = np.array(btc_5m_close.index, dtype="datetime64[ns]")
    bar_idx_arr = np.array(bar_index, dtype="datetime64[ns]")
    n_bars = len(bar_index)

    # ── Rebuild Wilder state (avg_gain, avg_loss) for every 30m bar ───────────
    # Use the ACTUAL BTC 30m close prices (from btc_30m_close) rather than resampling
    # from 5m data, to ensure the Wilder state exactly matches btc_rsi_full.
    closes_30m = btc_30m_close_norm.values
    ts_30m = np.array(btc_30m_close_norm.index, dtype="datetime64[ns]")
    n_30m = len(closes_30m)

    if n_30m < period + 2:
        return cross_short_ib, cross_long_ib

    avg_gain_arr = np.zeros(n_30m)
    avg_loss_arr = np.zeros(n_30m)

    deltas = np.diff(closes_30m)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    if len(gains) < period:
        return cross_short_ib, cross_long_ib

    ag = np.mean(gains[:period])
    al = np.mean(losses[:period])
    avg_gain_arr[period] = ag
    avg_loss_arr[period] = al

    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
        avg_gain_arr[i + 1] = ag
        avg_loss_arr[i + 1] = al

    # Lookup: 30m timestamp → index in avg_gain_arr / avg_loss_arr / closes_30m
    ts_30m_map: dict[int, int] = {int(ts): idx for idx, ts in enumerate(ts_30m)}

    # Align btc_rsi_full (full BTC 30m RSI) to bar_index for the "previous RSI" seed
    rsi_full_aligned = btc_rsi_full.reindex(bar_index, method="ffill")

    # ── For each 30m bar k, compute hypothetical RSI at each 5m tick ─────────
    # Bar k's body contains 5m ticks with timestamps >= bar_idx[k] and < bar_idx[k+1].
    # The anchor for the hypothetical RSI is the Wilder state at bar k-1's close.
    for k in range(1, n_bars - 1):
        bar_open_ts = bar_idx_arr[k]  # bar k opens here (inclusive lower bound for 5m)
        bar_close_ts = bar_idx_arr[k + 1]  # bar k closes here (exclusive upper bound)

        # 5m ticks within bar k: open <= tick < close
        mask = (btc_5m_idx_arr >= bar_open_ts) & (btc_5m_idx_arr < bar_close_ts)
        if not np.any(mask):
            continue

        idxs = np.where(mask)[0]

        # Get Wilder state at end of bar k-1 (the bar BEFORE bar k).
        prev_bar_ts = int(bar_idx_arr[k - 1])
        state_idx = ts_30m_map.get(prev_bar_ts)
        if state_idx is None:
            continue
        ag_prev = avg_gain_arr[state_idx]
        al_prev = avg_loss_arr[state_idx]
        if ag_prev == 0.0 and al_prev == 0.0:
            # Not yet warmed up
            continue

        # close_prev_30m: BTC 30m close of bar k-1 (the anchor price for delta computation)
        close_prev_30m = closes_30m[state_idx]
        if np.isnan(close_prev_30m):
            continue

        # Seed: 30m RSI at bar k-1's close
        prev_rsi_hyp: float = float(rsi_full_aligned.iloc[k - 1])
        if np.isnan(prev_rsi_hyp):
            continue

        fired_short = False
        fired_long = False

        # One-step hypothetical: each tick independently computes RSI from the FIXED
        # bar k-1 state.  This matches TradingView where close[1] always refers to the
        # previous COMPLETED bar's close (not the previous tick's price).
        #
        # For each tick:  delta = tick_price - close_{k-1}  (constant anchor)
        #                 ag_hyp = (ag_prev * (P-1) + max(delta,0)) / P
        #                 al_hyp = (al_prev * (P-1) + max(-delta,0)) / P
        #                 rsi_hyp = 100 - 100 / (1 + ag_hyp / al_hyp)
        #
        # Cross detection: compare consecutive ticks' INDEPENDENT RSI values.
        # Seed the "previous RSI" with bar k-1's close RSI for the first tick.
        prev_rsi_hyp_tick = prev_rsi_hyp  # bar k-1 close RSI

        for i in idxs:
            tick_price = btc_5m_arr[i]
            # One-step from FIXED bar k-1 state (NOT from previous tick's state)
            delta = tick_price - close_prev_30m
            g = delta if delta > 0 else 0.0
            lo = -delta if delta < 0 else 0.0
            ag_h = (ag_prev * (period - 1) + g) / period
            al_h = (al_prev * (period - 1) + lo) / period
            cur_rsi_hyp = 100.0 if al_h < 1e-10 else 100.0 - 100.0 / (1.0 + ag_h / al_h)

            if not fired_short and prev_rsi_hyp_tick >= cross_short_level and cur_rsi_hyp < cross_short_level:
                fired_short = True
            if not fired_long and prev_rsi_hyp_tick <= cross_long_level and cur_rsi_hyp > cross_long_level:
                fired_long = True

            # Advance the "previous tick RSI" for cross comparison (NOT the Wilder state)
            prev_rsi_hyp_tick = cur_rsi_hyp

        if fired_short:
            cross_short_ib.iloc[k] = True  # signal on bar k (where the ticks occurred)
        if fired_long:
            cross_long_ib.iloc[k] = True

    return cross_short_ib, cross_long_ib


def _handle_rsi(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
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
                # Use this as the final RSI — override the default rsi_arr computation below
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
        rsi_prev = rsi.shift(1)
        cross_long = (rsi_prev <= cross_long_level) & (rsi > cross_long_level)
        cross_short = (rsi_prev >= cross_short_level) & (rsi < cross_short_level)

        # ── Intra-bar RSI cross detection (TradingView parity) ──────────────────────
        # TV evaluates the RSI on every tick (calc_on_every_tick).  When the RSI crosses
        # a level within a bar but then partially reverts, the bar-close cross check above
        # misses the signal.  If 5m BTC data is available we re-step the Wilder smoother
        # through each 5m tick inside the bar and detect such crossings.
        # This only applies when use_btc_source=True because that is the case where we have
        # a separate BTC RSI series that TV also computes tick-by-tick.
        btc_5m = getattr(adapter, "_btcusdt_5m_ohlcv", None)
        if (
            btc_5m is not None
            and params.get("use_btc_source", False)
            and rsi_full_series is not None
            and btc_rsi_full is not None
            and btc_close_full is not None
        ):
            # btc_rsi_full is the full-warmup BTC RSI series (before reindex to close.index)
            # btc_close_full is the full-warmup BTC 30m close series (same index as btc_rsi_full)
            # Both are in scope from the use_btc_source block above.
            cross_short_ib, cross_long_ib = _detect_intrabar_rsi_crossings(
                btc_5m=btc_5m,
                bar_index=close.index,
                btc_rsi_full=btc_rsi_full,  # full BTC 30m RSI (wider, with warmup)
                btc_30m_close=btc_close_full,  # full BTC 30m close prices (same index)
                period=period,
                cross_short_level=float(cross_short_level),
                cross_long_level=float(cross_long_level),
            )
            n_new_short = int((cross_short_ib & ~cross_short).sum())
            n_new_long = int((cross_long_ib & ~cross_long).sum())
            if n_new_short or n_new_long:
                logger.debug(
                    "RSI node | intra-bar crossings added: +{} short, +{} long",
                    n_new_short,
                    n_new_long,
                )
            cross_short = cross_short | cross_short_ib
            cross_long = cross_long | cross_long_ib

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

    # ── TRADINGVIEW PARITY FIX (2026-02-28) ──────────────────────────────────
    # After analyzing TV export a4.csv (154 trades):
    # - 0% of trades had actual RSI crosses (cross up 24 or cross down 52)
    # - 100% of trades were range-only entries (RSI in range without cross)
    #
    # This indicates TV uses "Range ONLY" logic when BOTH range and cross are enabled:
    # - If use_cross_level=True AND use_long_range=True: use ONLY range (ignore cross)
    # - If use_cross_level=True AND use_long_range=False: use ONLY cross
    # - If use_cross_level=False AND use_long_range=True: use ONLY range
    #
    # Previous (INCORRECT): AND logic
    #   long_signal = long_range_condition & long_cross_condition
    #
    # Also incorrect: OR logic (generates too many signals)
    #   long_signal = long_range_condition | long_cross_condition
    #
    # Correct (TV parity): Range takes precedence over cross
    #   if use_long_range: long_signal = long_range_condition
    #   else: long_signal = long_cross_condition
    # ──────────────────────────────────────────────────────────────────────────
    if use_long_range:
        long_signal = long_range_condition
    else:
        long_signal = long_cross_condition
    
    if use_short_range:
        short_signal = short_range_condition
    else:
        short_signal = short_cross_condition

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
    fast = _clamp_period(_param(params, 12, "fast_period", "fastPeriod"))
    slow = _clamp_period(_param(params, 26, "slow_period", "slowPeriod"))
    signal_p = _clamp_period(_param(params, 9, "signal_period", "signalPeriod"))

    macd_result = vbt.MACD.run(close, fast_window=fast, slow_window=slow, signal_window=signal_p)
    macd_line = macd_result.macd
    signal_line = macd_result.signal
    histogram = macd_result.hist

    # Support both old keys (use_macd_cross / use_zero_cross) and new frontend keys
    # (use_macd_cross_signal / use_macd_cross_zero).
    use_cross = params.get("use_macd_cross_signal", params.get("use_macd_cross", False))
    use_histogram = params.get("use_histogram", False)
    use_zero_cross = params.get("use_macd_cross_zero", params.get("use_zero_cross", False))

    long_signal = pd.Series(True, index=ohlcv.index)
    short_signal = pd.Series(True, index=ohlcv.index)

    if use_cross:
        macd_prev = macd_line.shift(1)
        signal_prev = signal_line.shift(1)
        cross_long = (macd_prev <= signal_prev) & (macd_line > signal_line)
        cross_short = (macd_prev >= signal_prev) & (macd_line < signal_line)

        if params.get("opposite_macd_cross_signal", params.get("opposite_signal", False)):
            cross_long, cross_short = cross_short, cross_long

        # Memory: frontend sends disable_signal_memory (default False = ON) + signal_memory_bars.
        # Legacy path: use_cross_memory + cross_memory_bars.
        disable_memory = params.get("disable_signal_memory", True)
        if not disable_memory or params.get("use_cross_memory", False):
            memory_bars = int(params.get("signal_memory_bars", params.get("cross_memory_bars", 5)))
            cross_long = adapter._apply_signal_memory(cross_long, memory_bars)
            cross_short = adapter._apply_signal_memory(cross_short, memory_bars)

        long_signal = long_signal & cross_long.fillna(False)
        short_signal = short_signal & cross_short.fillna(False)

    if use_histogram:
        hist_threshold = float(params.get("histogram_threshold", 0))
        long_signal = long_signal & (histogram > hist_threshold)
        short_signal = short_signal & (histogram < -hist_threshold)

    if use_zero_cross:
        macd_prev = macd_line.shift(1)
        zero_cross_long = (macd_prev <= 0) & (macd_line > 0)
        zero_cross_short = (macd_prev >= 0) & (macd_line < 0)

        if params.get("opposite_macd_cross_zero", params.get("opposite_signal", False)):
            zero_cross_long, zero_cross_short = zero_cross_short, zero_cross_long

        disable_memory = params.get("disable_signal_memory", True)
        if not disable_memory or params.get("use_zero_cross_memory", False):
            memory_bars = int(params.get("signal_memory_bars", params.get("zero_cross_memory_bars", 5)))
            zero_cross_long = adapter._apply_signal_memory(zero_cross_long, memory_bars)
            zero_cross_short = adapter._apply_signal_memory(zero_cross_short, memory_bars)

        long_signal = long_signal & zero_cross_long.fillna(False)
        short_signal = short_signal & zero_cross_short.fillna(False)

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

    use_long_range = params.get("use_long_range", False)
    use_short_range = params.get("use_short_range", False)
    use_cross_level = params.get("use_cross_level", False)
    use_kd_cross = params.get("use_kd_cross", False)

    long_signal = pd.Series(True, index=ohlcv.index)
    short_signal = pd.Series(True, index=ohlcv.index)

    if use_long_range:
        long_more = float(params.get("long_stoch_more", params.get("long_more", 20)))
        long_less = float(params.get("long_stoch_less", params.get("long_less", 80)))
        if long_more > long_less:
            logger.warning(
                "Stochastic range inversion: long swapping {} > {}",
                long_more,
                long_less,
            )
            long_more, long_less = long_less, long_more
        long_signal = long_signal & (k_line >= long_more) & (k_line <= long_less)

    if use_short_range:
        short_more = float(params.get("short_stoch_more", params.get("short_more", 20)))
        short_less = float(params.get("short_stoch_less", params.get("short_less", 80)))
        if short_more > short_less:
            logger.warning(
                "Stochastic range inversion: short swapping {} > {}",
                short_more,
                short_less,
            )
            short_more, short_less = short_less, short_more
        short_signal = short_signal & (k_line <= short_less) & (k_line >= short_more)

    if use_cross_level:
        cross_long_level = float(params.get("cross_long_level", 20))
        cross_short_level = float(params.get("cross_short_level", 80))
        k_prev = k_line.shift(1)
        cross_long = (k_prev <= cross_long_level) & (k_line > cross_long_level)
        cross_short = (k_prev >= cross_short_level) & (k_line < cross_short_level)

        if params.get("opposite_signal", False):
            cross_long, cross_short = cross_short, cross_long

        if params.get("use_cross_memory", False):
            memory_bars = int(params.get("cross_memory_bars", 5))
            cross_long = adapter._apply_signal_memory(cross_long, memory_bars)
            cross_short = adapter._apply_signal_memory(cross_short, memory_bars)

        long_signal = long_signal & cross_long.fillna(False)
        short_signal = short_signal & cross_short.fillna(False)

    if use_kd_cross:
        k_prev = k_line.shift(1)
        d_prev = d_line.shift(1)
        kd_cross_long = (k_prev <= d_prev) & (k_line > d_line)
        kd_cross_short = (k_prev >= d_prev) & (k_line < d_line)

        if params.get("opposite_kd_cross", False):
            kd_cross_long, kd_cross_short = kd_cross_short, kd_cross_long

        if params.get("use_kd_cross_memory", False):
            memory_bars = int(params.get("kd_cross_memory_bars", 5))
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
    period = _clamp_period(params.get("period", 20))
    result = calculate_cci(ohlcv["high"].values, ohlcv["low"].values, close.values, period)
    return {"value": pd.Series(result, index=ohlcv.index)}


# ═══════════════════════════════════════════════════════════════════════════
# Trend indicators (MA family)
# ═══════════════════════════════════════════════════════════════════════════


def _handle_ema(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(params.get("period", 20))
    ema = vbt.MA.run(close, window=period, ewm=True).ma
    return {"value": ema}


def _handle_sma(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(params.get("period", 50))
    sma = vbt.MA.run(close, window=period).ma
    return {"value": sma}


def _handle_wma(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(params.get("period", 20))
    result = calculate_wma(close.values, period)
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_dema(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(params.get("period", 20))
    result = calculate_dema(close.values, period)
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_tema(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(params.get("period", 20))
    result = calculate_tema(close.values, period)
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_hull_ma(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(params.get("period", 20))
    result = calculate_hull_ma(close.values, period)
    return {"value": pd.Series(result, index=ohlcv.index)}


# ═══════════════════════════════════════════════════════════════════════════
# Band / Channel indicators
# ═══════════════════════════════════════════════════════════════════════════


def _handle_bollinger(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(params.get("period", 20))
    std_dev = _param(params, 2.0, "std_dev", "stdDev")
    bb = vbt.BBANDS.run(close, window=period, num_std=std_dev)
    return {"upper": bb.upper, "middle": bb.middle, "lower": bb.lower}


def _handle_keltner(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(_param(params, 20, "ema_period", "period"))
    multiplier = params.get("multiplier", 2.0)
    atr_period = _clamp_period(_param(params, 10, "atr_period", "atrPeriod"))
    kc_mid, kc_upper, kc_lower = calculate_keltner(
        ohlcv["high"].values,
        ohlcv["low"].values,
        close.values,
        period,
        atr_period,
        multiplier,
    )
    return {
        "upper": pd.Series(kc_upper, index=ohlcv.index),
        "middle": pd.Series(kc_mid, index=ohlcv.index),
        "lower": pd.Series(kc_lower, index=ohlcv.index),
    }


def _handle_donchian(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(params.get("period", 20))
    dc_mid, dc_upper, dc_lower = calculate_donchian(
        ohlcv["high"].values,
        ohlcv["low"].values,
        period,
    )
    return {
        "upper": pd.Series(dc_upper, index=ohlcv.index),
        "middle": pd.Series(dc_mid, index=ohlcv.index),
        "lower": pd.Series(dc_lower, index=ohlcv.index),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Volatility indicators
# ═══════════════════════════════════════════════════════════════════════════


def _handle_atr(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(params.get("period", 14))
    atr = vbt.ATR.run(ohlcv["high"], ohlcv["low"], close, window=period).atr
    return {"value": atr}


def _handle_atrp(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(params.get("period", 14))
    result = calculate_atrp(ohlcv["high"].values, ohlcv["low"].values, close.values, period)
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_stddev(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(params.get("period", 20))
    result = calculate_stddev(close.values, period)
    return {"value": pd.Series(result, index=ohlcv.index)}


# ═══════════════════════════════════════════════════════════════════════════
# Trend indicators (non-MA)
# ═══════════════════════════════════════════════════════════════════════════


def _handle_adx(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(params.get("period", 14))
    adx = vbt.ADX.run(ohlcv["high"], ohlcv["low"], close, window=period).adx
    return {"value": adx}


def _handle_supertrend(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(_param(params, 10, "period", "atr_period"))
    multiplier = _param(params, 3.0, "multiplier", "atr_multiplier")
    use_supertrend = params.get("use_supertrend", False)
    generate_on_trend_change = params.get("generate_on_trend_change", False)
    opposite_signal = params.get("opposite_signal", False)

    st_line, st_direction = calculate_supertrend(
        ohlcv["high"].values,
        ohlcv["low"].values,
        close.values,
        period,
        multiplier,
    )
    direction = pd.Series(st_direction, index=ohlcv.index)

    st_upper = np.where(st_direction == -1, st_line, np.nan)
    st_lower = np.where(st_direction == 1, st_line, np.nan)

    if not use_supertrend:
        long_signal = pd.Series(True, index=ohlcv.index)
        short_signal = pd.Series(True, index=ohlcv.index)
    elif generate_on_trend_change:
        long_signal = (direction == 1) & (direction.shift(1) == -1)
        short_signal = (direction == -1) & (direction.shift(1) == 1)
        long_signal = long_signal.fillna(False)
        short_signal = short_signal.fillna(False)
    else:
        long_signal = direction == 1
        short_signal = direction == -1

    if opposite_signal:
        long_signal, short_signal = short_signal, long_signal

    return {
        "supertrend": pd.Series(st_line, index=ohlcv.index),
        "direction": direction,
        "upper": pd.Series(st_upper, index=ohlcv.index),
        "lower": pd.Series(st_lower, index=ohlcv.index),
        "long": long_signal,
        "short": short_signal,
    }


def _handle_ichimoku(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    tenkan = _clamp_period(_param(params, 9, "tenkan_period", "tenkan"))
    kijun = _clamp_period(_param(params, 26, "kijun_period", "kijun"))
    senkou_b = _clamp_period(_param(params, 52, "senkou_b_period", "senkouB"))
    ichi = calculate_ichimoku(
        ohlcv["high"].values,
        ohlcv["low"].values,
        close.values,
        tenkan,
        kijun,
        senkou_b,
    )
    return {
        "tenkan_sen": pd.Series(ichi.tenkan_sen, index=ohlcv.index),
        "kijun_sen": pd.Series(ichi.kijun_sen, index=ohlcv.index),
        "senkou_span_a": pd.Series(ichi.senkou_span_a, index=ohlcv.index),
        "senkou_span_b": pd.Series(ichi.senkou_span_b, index=ohlcv.index),
        "chikou_span": pd.Series(ichi.chikou_span, index=ohlcv.index),
    }


def _handle_parabolic_sar(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    af_start = _param(params, 0.02, "start", "afStart")
    af_step = _param(params, 0.02, "increment", "afStep")
    af_max = _param(params, 0.2, "max_value", "afMax")
    sar_values, _sar_trend = calculate_parabolic_sar(
        ohlcv["high"].values,
        ohlcv["low"].values,
        af_start,
        af_step,
        af_max,
    )
    return {"value": pd.Series(sar_values, index=ohlcv.index)}


def _handle_aroon(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(params.get("period", 25))
    aroon_result = calculate_aroon(ohlcv["high"].values, ohlcv["low"].values, period)
    return {
        "up": pd.Series(aroon_result.aroon_up, index=ohlcv.index),
        "down": pd.Series(aroon_result.aroon_down, index=ohlcv.index),
        "oscillator": pd.Series(aroon_result.aroon_osc, index=ohlcv.index),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Volume indicators
# ═══════════════════════════════════════════════════════════════════════════


def _handle_obv(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    result = calculate_obv(close.values, ohlcv["volume"].values)
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_vwap(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    result = calculate_vwap(
        ohlcv["high"].values,
        ohlcv["low"].values,
        close.values,
        ohlcv["volume"].values,
    )
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_cmf(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    period = _clamp_period(params.get("period", 20))
    result = calculate_cmf(
        ohlcv["high"].values,
        ohlcv["low"].values,
        close.values,
        ohlcv["volume"].values,
        period,
    )
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_ad_line(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    result = calculate_ad_line(
        ohlcv["high"].values,
        ohlcv["low"].values,
        close.values,
        ohlcv["volume"].values,
    )
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_pvt(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    result = calculate_pvt(close.values, ohlcv["volume"].values)
    return {"value": pd.Series(result, index=ohlcv.index)}


# ═══════════════════════════════════════════════════════════════════════════
# Support / Resistance
# ═══════════════════════════════════════════════════════════════════════════


def _handle_pivot_points(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    pp, r1, r2, r3, s1, s2, s3 = calculate_pivot_points_array(
        ohlcv["high"].values,
        ohlcv["low"].values,
        close.values,
    )
    return {
        "pp": pd.Series(pp, index=ohlcv.index),
        "r1": pd.Series(r1, index=ohlcv.index),
        "r2": pd.Series(r2, index=ohlcv.index),
        "r3": pd.Series(r3, index=ohlcv.index),
        "s1": pd.Series(s1, index=ohlcv.index),
        "s2": pd.Series(s2, index=ohlcv.index),
        "s3": pd.Series(s3, index=ohlcv.index),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Multi-Timeframe utilities
# ═══════════════════════════════════════════════════════════════════════════

# Maps Bybit API numeric TF strings ("1", "15", "60", "240", "D") and
# UI string aliases ("1m", "1h", "4h", "1d") to pandas resample rules.
_TF_RESAMPLE_MAP: dict[str, str] = {
    # Bybit API numeric format
    "1": "1min",
    "3": "3min",
    "5": "5min",
    "15": "15min",
    "30": "30min",
    "60": "1h",
    "120": "2h",
    "240": "4h",
    "D": "1D",
    "W": "1W",
    "M": "1ME",
    # UI string aliases
    "1m": "1min",
    "3m": "3min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "1d": "1D",
    "1w": "1W",
}


def _resample_ohlcv(ohlcv: pd.DataFrame, timeframe: str) -> pd.DataFrame | None:
    """Resample OHLCV to a higher timeframe and re-align to the original index.

    Returns a DataFrame with the same index as *ohlcv* (ffill applied), or
    ``None`` if the timeframe is unknown, produces fewer than 2 bars, or the
    resample fails for any reason.

    Supports both ``pd.DatetimeIndex`` (timezone-aware) and numeric
    (timestamp-in-milliseconds) indices transparently.
    """
    rule = _TF_RESAMPLE_MAP.get(str(timeframe))
    if rule is None:
        logger.warning("MTF _resample_ohlcv: unknown timeframe '{}', skipping", timeframe)
        return None

    # If the index is numeric (timestamp ms), temporarily convert to DatetimeIndex
    # so pandas resample works correctly, then restore afterwards.
    numeric_index = not isinstance(ohlcv.index, pd.DatetimeIndex)
    working = ohlcv
    if numeric_index:
        working = ohlcv.copy()
        working.index = pd.to_datetime(working.index, unit="ms", utc=True)

    try:
        htf = (
            working.resample(rule)
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna()
        )
        if len(htf) < 2:
            logger.warning(
                "MTF _resample_ohlcv: timeframe '{}' produced only {} HTF bar(s), falling back to main OHLCV",
                timeframe,
                len(htf),
            )
            return None
        # Re-align to original index: forward-fill each HTF bar value into the
        # LTF bars that belong to it.
        result = htf.reindex(working.index).ffill()
        if numeric_index:
            result.index = ohlcv.index  # restore original numeric index
        return result
    except Exception as exc:
        logger.warning("MTF _resample_ohlcv: resample error for tf='{}': {}", timeframe, exc)
        return None


def _handle_mtf(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    htf = params.get("timeframe", "1h")
    indicator = params.get("indicator", "ema")
    period = params.get("period", 20)
    source = params.get("source", "close")

    src = ohlcv[source] if source in ohlcv.columns else close

    # 'Chart' / 'chart' means current timeframe — no resampling
    if htf.lower() == "chart":
        if indicator == "ema":
            values = src.ewm(span=period, adjust=False).mean()
        elif indicator == "sma":
            values = src.rolling(period).mean()
        elif indicator == "rsi":
            values = pd.Series(calculate_rsi(src.values, period=period), index=ohlcv.index)
        elif indicator == "atr":
            values = pd.Series(
                calculate_atr(ohlcv["high"].values, ohlcv["low"].values, src.values, period),
                index=ohlcv.index,
            )
        else:
            values = src.rolling(period).mean()
        return {"value": values}

    tf_map = {
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "1d": "1D",
        "1w": "1W",
    }
    resample_rule = tf_map.get(htf, "1h")

    try:
        ohlcv_htf = (
            ohlcv.resample(resample_rule)
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna()
        )
        src_htf = ohlcv_htf["close"]

        if indicator == "ema":
            htf_values = src_htf.ewm(span=period, adjust=False).mean()
        elif indicator == "sma":
            htf_values = src_htf.rolling(period).mean()
        elif indicator == "rsi":
            htf_values = pd.Series(calculate_rsi(src_htf.values, period=period), index=src_htf.index)
        elif indicator == "atr":
            htf_values = pd.Series(
                calculate_atr(ohlcv_htf["high"].values, ohlcv_htf["low"].values, src_htf.values, period),
                index=ohlcv_htf.index,
            )
        else:
            htf_values = src_htf.rolling(period).mean()

        htf_reindexed = htf_values.reindex(ohlcv.index).ffill()
        return {"value": htf_reindexed.bfill()}

    except Exception as e:
        logger.warning(f"MTF calculation error: {e}")
        fallback = src.ewm(span=period, adjust=False).mean() if indicator == "ema" else src.rolling(period).mean()
        return {"value": fallback}


# ═══════════════════════════════════════════════════════════════════════════
# Universal filter indicators
# ═══════════════════════════════════════════════════════════════════════════


def _handle_atr_volatility(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    use = params.get("use_atr_volatility", False)
    if not use:
        return {
            "long": pd.Series(True, index=ohlcv.index),
            "short": pd.Series(True, index=ohlcv.index),
        }
    length1 = int(params.get("atr_length1", 20))
    length2 = int(params.get("atr_length2", 100))
    smoothing_method = str(params.get("atr_smoothing", "WMA")).upper()
    diff_pct = float(params.get("atr_diff_percent", 10))
    mode = params.get("atr1_to_atr2", "ATR1 < ATR2")

    high_arr = ohlcv["high"].values
    low_arr = ohlcv["low"].values
    close_arr = close.values
    atr1 = pd.Series(
        calculate_atr_smoothed(high_arr, low_arr, close_arr, period=length1, method=smoothing_method),
        index=ohlcv.index,
    )
    atr2 = pd.Series(
        calculate_atr_smoothed(high_arr, low_arr, close_arr, period=length2, method=smoothing_method),
        index=ohlcv.index,
    )
    pct_diff = ((atr1 - atr2).abs() / atr2.replace(0, np.nan)) * 100
    condition = (atr1 < atr2) & (pct_diff >= diff_pct) if "< ATR2" in mode else (atr1 > atr2) & (pct_diff >= diff_pct)
    condition = condition.fillna(False)
    logger.debug(
        "ATR Volatility filter | mode={} | diff>={}% | pass={}",
        mode,
        diff_pct,
        condition.sum(),
    )
    return {"long": condition, "short": condition}


def _handle_volume_filter(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    use = params.get("use_volume_filter", False)
    if not use:
        return {
            "long": pd.Series(True, index=ohlcv.index),
            "short": pd.Series(True, index=ohlcv.index),
        }
    length1 = _clamp_period(int(params.get("vol_length1", 20)))
    length2 = _clamp_period(int(params.get("vol_length2", 100)))
    smoothing_method = str(params.get("vol_smoothing", "WMA")).upper()
    diff_pct = float(params.get("vol_diff_percent", 10))
    mode = params.get("vol1_to_vol2", "VOL1 < VOL2")

    volume = ohlcv["volume"].astype(float)
    if smoothing_method == "EMA":
        vol1 = volume.ewm(span=length1, adjust=False).mean()
        vol2 = volume.ewm(span=length2, adjust=False).mean()
    elif smoothing_method == "SMA":
        vol1 = volume.rolling(length1).mean()
        vol2 = volume.rolling(length2).mean()
    elif smoothing_method == "WMA":
        w1 = np.arange(1, length1 + 1, dtype=float)
        vol1 = volume.rolling(length1).apply(lambda x: np.dot(x, w1) / w1.sum(), raw=True)
        w2 = np.arange(1, length2 + 1, dtype=float)
        vol2 = volume.rolling(length2).apply(lambda x: np.dot(x, w2) / w2.sum(), raw=True)
    else:  # RMA
        vol1 = volume.ewm(alpha=1 / length1, adjust=False).mean()
        vol2 = volume.ewm(alpha=1 / length2, adjust=False).mean()

    pct_diff = ((vol1 - vol2).abs() / vol2.replace(0, np.nan)) * 100
    condition = (vol1 < vol2) & (pct_diff >= diff_pct) if "< VOL2" in mode else (vol1 > vol2) & (pct_diff >= diff_pct)
    condition = condition.fillna(False)
    logger.debug(
        "Volume filter | mode={} | diff>={}% | pass={}",
        mode,
        diff_pct,
        condition.sum(),
    )
    return {"long": condition, "short": condition}


def _handle_highest_lowest_bar(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    long_signal = pd.Series(True, index=ohlcv.index)
    short_signal = pd.Series(True, index=ohlcv.index)

    if params.get("use_highest_lowest", False):
        lookback = _clamp_period(int(params.get("hl_lookback_bars", 10)))
        price_pct = float(params.get("hl_price_percent", 0))
        atr_pct = float(params.get("hl_atr_percent", 0))
        atr_len = _clamp_period(int(params.get("atr_hl_length", 50)))

        high_arr = ohlcv["high"]
        low_arr = ohlcv["low"]
        rolling_high = high_arr.rolling(lookback).max()
        rolling_low = low_arr.rolling(lookback).min()
        is_highest = high_arr >= rolling_high
        is_lowest = low_arr <= rolling_low

        if price_pct > 0:
            close_shifted = close.shift(lookback)
            price_up = ((close - close_shifted) / close_shifted.replace(0, np.nan)) * 100 >= price_pct
            price_down = ((close_shifted - close) / close_shifted.replace(0, np.nan)) * 100 >= price_pct
            is_highest = is_highest & price_up.fillna(False)
            is_lowest = is_lowest & price_down.fillna(False)

        if atr_pct > 0:
            atr_full = pd.Series(
                calculate_atr(ohlcv["high"].values, ohlcv["low"].values, close.values, atr_len),
                index=ohlcv.index,
            )
            atr_short = pd.Series(
                calculate_atr(ohlcv["high"].values, ohlcv["low"].values, close.values, 2),
                index=ohlcv.index,
            )
            atr_ratio = ((atr_short - atr_full) / atr_full.replace(0, np.nan)) * 100
            atr_up = atr_ratio >= atr_pct
            atr_down = atr_ratio <= -atr_pct
            is_highest = is_highest | atr_up.fillna(False)
            is_lowest = is_lowest | atr_down.fillna(False)

        long_signal = is_highest.fillna(False)
        short_signal = is_lowest.fillna(False)

    if params.get("use_block_worse_than", False):
        worse_pct = float(params.get("block_worse_percent", 1.1))
        prev_close = close.shift(1)
        price_change_pct = ((close - prev_close) / prev_close.replace(0, np.nan)) * 100
        long_ok = (price_change_pct >= 0) & (price_change_pct <= worse_pct)
        short_ok = (price_change_pct <= 0) & (price_change_pct.abs() <= worse_pct)
        long_signal = long_signal & long_ok.fillna(False)
        short_signal = short_signal & short_ok.fillna(False)

    logger.debug(
        "Highest/Lowest Bar | hl={} | worse={} | long={} short={}",
        params.get("use_highest_lowest"),
        params.get("use_block_worse_than"),
        long_signal.sum(),
        short_signal.sum(),
    )
    return {"long": long_signal, "short": short_signal}


def _handle_two_mas(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    ma1_len = int(params.get("ma1_length", 50))
    ma2_len = int(params.get("ma2_length", 100))
    ma1_type = str(params.get("ma1_smoothing", "SMA")).upper()
    ma2_type = str(params.get("ma2_smoothing", "EMA")).upper()
    ma1_src = str(params.get("ma1_source", "close"))
    ma2_src = str(params.get("ma2_source", "close"))

    src1 = ohlcv[ma1_src] if ma1_src in ohlcv.columns else close
    src2 = ohlcv[ma2_src] if ma2_src in ohlcv.columns else close

    ma1 = _calc_ma(src1, ma1_len, ma1_type)
    ma2 = _calc_ma(src2, ma2_len, ma2_type)

    long_signal = pd.Series(True, index=ohlcv.index)
    short_signal = pd.Series(True, index=ohlcv.index)

    if params.get("use_ma_cross", False):
        ma1_prev = ma1.shift(1)
        ma2_prev = ma2.shift(1)
        cross_long = (ma1_prev <= ma2_prev) & (ma1 > ma2)
        cross_short = (ma1_prev >= ma2_prev) & (ma1 < ma2)

        if params.get("opposite_ma_cross", False):
            cross_long, cross_short = cross_short, cross_long

        if params.get("activate_ma_cross_memory", False):
            memory_bars = int(params.get("ma_cross_memory_bars", 5))
            cross_long = adapter._apply_signal_memory(cross_long, memory_bars)
            cross_short = adapter._apply_signal_memory(cross_short, memory_bars)

        long_signal = long_signal & cross_long.fillna(False)
        short_signal = short_signal & cross_short.fillna(False)

    if params.get("use_ma1_filter", False):
        if params.get("opposite_ma1_filter", False):
            long_filter = close < ma1
            short_filter = close > ma1
        else:
            long_filter = close > ma1
            short_filter = close < ma1
        long_signal = long_signal & long_filter.fillna(False)
        short_signal = short_signal & short_filter.fillna(False)

    logger.debug(
        "TWO MAs | ma1={}({}) ma2={}({}) | long={} short={}",
        ma1_type,
        ma1_len,
        ma2_type,
        ma2_len,
        long_signal.sum(),
        short_signal.sum(),
    )
    return {"long": long_signal, "short": short_signal, "ma1": ma1, "ma2": ma2}


def _handle_accumulation_areas(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    use = params.get("use_accumulation", False)
    if not use:
        return {
            "long": pd.Series(True, index=ohlcv.index),
            "short": pd.Series(True, index=ohlcv.index),
        }
    interval = _clamp_period(int(params.get("backtracking_interval", 30)))
    min_bars = _clamp_period(int(params.get("min_bars_to_execute", 5)))
    signal_breakout = params.get("signal_on_breakout", False)
    signal_opposite = params.get("signal_on_opposite_breakout", False)

    high_arr = ohlcv["high"]
    low_arr = ohlcv["low"]
    rolling_high = high_arr.rolling(interval).max()
    rolling_low = low_arr.rolling(interval).min()
    price_range = ((rolling_high - rolling_low) / rolling_low.replace(0, np.nan)) * 100

    median_range = price_range.rolling(interval * 2).median()
    in_accumulation = price_range < median_range

    cumsum_reset = (~in_accumulation).cumsum()
    consecutive = in_accumulation.groupby(cumsum_reset).cumsum()
    accum_zone = consecutive >= min_bars

    if signal_breakout or signal_opposite:
        was_accum = accum_zone.shift(1).fillna(False)
        breakout_up = was_accum & (close > rolling_high.shift(1))
        breakout_down = was_accum & (close < rolling_low.shift(1))
        if signal_opposite:
            breakout_up, breakout_down = breakout_down, breakout_up
        long_signal = breakout_up.fillna(False)
        short_signal = breakout_down.fillna(False)
    else:
        long_signal = accum_zone.fillna(False)
        short_signal = accum_zone.fillna(False)

    logger.debug(
        "Accumulation | interval={} min_bars={} | long={} short={}",
        interval,
        min_bars,
        long_signal.sum(),
        short_signal.sum(),
    )
    return {"long": long_signal, "short": short_signal}


def _handle_keltner_bollinger(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    use = params.get("use_channel", False)
    if not use:
        return {
            "long": pd.Series(True, index=ohlcv.index),
            "short": pd.Series(True, index=ohlcv.index),
        }
    channel_type = str(params.get("channel_type", "Keltner Channel")).lower()
    mode = str(params.get("channel_mode", "Rebound")).lower()
    enter_cond = str(params.get("enter_conditions", "Wick out of band"))

    high_arr = ohlcv["high"].values
    low_arr = ohlcv["low"].values
    close_arr = close.values

    if "bollinger" in channel_type:
        bb_len = int(params.get("bb_length", 20))
        bb_dev = float(params.get("bb_deviation", 2.0))
        _mid, upper_band, lower_band = calculate_bollinger(close_arr, period=bb_len, std_dev=bb_dev)
    else:
        kc_len = int(params.get("keltner_length", 14))
        kc_mult = float(params.get("keltner_mult", 1.5))
        _mid, upper_band, lower_band = calculate_keltner(
            high_arr,
            low_arr,
            close_arr,
            period=kc_len,
            multiplier=kc_mult,
        )

    upper_s = pd.Series(upper_band, index=ohlcv.index)
    lower_s = pd.Series(lower_band, index=ohlcv.index)
    high_s = ohlcv["high"]
    low_s = ohlcv["low"]
    prev_close = close.shift(1)

    if enter_cond == "Out-of-band closure":
        above_upper = close > upper_s
        below_lower = close < lower_s
    elif enter_cond == "Wick out of band":
        above_upper = high_s > upper_s
        below_lower = low_s < lower_s
    elif enter_cond == "Wick out of the band then close in":
        above_upper = (high_s > upper_s) & (close <= upper_s)
        below_lower = (low_s < lower_s) & (close >= lower_s)
    else:  # "Close out of the band then close in"
        above_upper = (prev_close > upper_s.shift(1)) & (close <= upper_s)
        below_lower = (prev_close < lower_s.shift(1)) & (close >= lower_s)

    above_upper = above_upper.fillna(False)
    below_lower = below_lower.fillna(False)

    if mode == "rebound":
        long_signal = below_lower
        short_signal = above_upper
    else:
        long_signal = above_upper
        short_signal = below_lower

    logger.debug(
        "Keltner/Bollinger | type={} mode={} | long={} short={}",
        channel_type,
        mode,
        long_signal.sum(),
        short_signal.sum(),
    )
    return {"long": long_signal, "short": short_signal}


def _handle_rvi_filter(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
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


def _handle_mfi_filter(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    mfi_len = int(params.get("mfi_length", 14))
    mfi_tf = params.get("mfi_timeframe", "Chart")

    # Determine working OHLCV: main, HTF-resampled, or BTCUSDT proxy
    working_ohlcv = ohlcv
    main_tf = str(adapter.main_interval)
    resolved_tf = main_tf if str(mfi_tf).lower() == "chart" else str(mfi_tf)

    # Feature 3: use BTCUSDT as MFI source (market dominance proxy)
    use_btc = params.get("use_btcusdt_mfi", False)
    if use_btc:
        btcusdt_ohlcv = getattr(adapter, "_btcusdt_ohlcv", None)
        if btcusdt_ohlcv is not None:
            # Align BTCUSDT index to current OHLCV index
            working_ohlcv = btcusdt_ohlcv.reindex(ohlcv.index).ffill()
            logger.debug("MFI filter: using BTCUSDT OHLCV as MFI source")
        else:
            logger.warning(
                "MFI filter: use_btcusdt_mfi=True but BTCUSDT data not available "
                "(symbol may already be BTCUSDT, or router did not preload); "
                "falling back to current symbol."
            )
    elif resolved_tf != main_tf:
        # Feature 2: resample to higher timeframe
        htf_ohlcv = _resample_ohlcv(ohlcv, resolved_tf)
        if htf_ohlcv is not None:
            working_ohlcv = htf_ohlcv
            logger.debug("MFI filter: using HTF OHLCV tf='{}'", resolved_tf)
        else:
            logger.warning(
                "MFI filter: resample to '{}' failed, falling back to main tf='{}'",
                resolved_tf,
                main_tf,
            )

    mfi_vals = pd.Series(
        calculate_mfi(
            working_ohlcv["high"].values,
            working_ohlcv["low"].values,
            working_ohlcv["close"].values,
            working_ohlcv["volume"].values.astype(float),
            period=mfi_len,
        ),
        index=ohlcv.index,  # always align to the original index
    )

    long_signal = pd.Series(True, index=ohlcv.index)
    short_signal = pd.Series(True, index=ohlcv.index)

    if params.get("use_mfi_long_range", False):
        lo = float(params.get("mfi_long_more", 1))
        hi = float(params.get("mfi_long_less", 60))
        long_signal = long_signal & (mfi_vals >= lo) & (mfi_vals <= hi)
        long_signal = long_signal.fillna(False)

    if params.get("use_mfi_short_range", False):
        hi_s = float(params.get("mfi_short_less", 100))
        lo_s = float(params.get("mfi_short_more", 50))
        short_signal = short_signal & (mfi_vals <= hi_s) & (mfi_vals >= lo_s)
        short_signal = short_signal.fillna(False)

    logger.debug(
        "MFI filter | len={} | long={} short={}",
        mfi_len,
        long_signal.sum(),
        short_signal.sum(),
    )
    return {"long": long_signal, "short": short_signal, "mfi": mfi_vals}


def _handle_cci_filter(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    cci_len = int(params.get("cci_length", 14))
    cci_tf = params.get("cci_timeframe", "Chart")

    # Determine working OHLCV: main or HTF-resampled
    working_ohlcv = ohlcv
    main_tf = str(adapter.main_interval)
    resolved_tf = main_tf if str(cci_tf).lower() == "chart" else str(cci_tf)

    if resolved_tf != main_tf:
        htf_ohlcv = _resample_ohlcv(ohlcv, resolved_tf)
        if htf_ohlcv is not None:
            working_ohlcv = htf_ohlcv
            logger.debug("CCI filter: using HTF OHLCV tf='{}'", resolved_tf)
        else:
            logger.warning(
                "CCI filter: resample to '{}' failed, falling back to main tf='{}'",
                resolved_tf,
                main_tf,
            )

    cci_vals = pd.Series(
        calculate_cci(
            working_ohlcv["high"].values,
            working_ohlcv["low"].values,
            working_ohlcv["close"].values,
            period=cci_len,
        ),
        index=ohlcv.index,  # always align to the original index
    )

    long_signal = pd.Series(True, index=ohlcv.index)
    short_signal = pd.Series(True, index=ohlcv.index)

    if params.get("use_cci_long_range", False):
        lo = float(params.get("cci_long_more", -100))
        hi = float(params.get("cci_long_less", 100))
        long_signal = long_signal & (cci_vals >= lo) & (cci_vals <= hi)
        long_signal = long_signal.fillna(False)

    if params.get("use_cci_short_range", False):
        hi_s = float(params.get("cci_short_less", -10))
        lo_s = float(params.get("cci_short_more", -100))
        short_signal = short_signal & (cci_vals <= hi_s) & (cci_vals >= lo_s)
        short_signal = short_signal.fillna(False)

    logger.debug(
        "CCI filter | len={} | long={} short={}",
        cci_len,
        long_signal.sum(),
        short_signal.sum(),
    )
    return {"long": long_signal, "short": short_signal, "cci": cci_vals}


def _handle_momentum_filter(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    mom_len = int(params.get("momentum_length", 14))
    mom_src = str(params.get("momentum_source", "close"))
    src = ohlcv[mom_src] if mom_src in ohlcv.columns else close
    mom_vals = src - src.shift(mom_len)

    long_signal = pd.Series(True, index=ohlcv.index)
    short_signal = pd.Series(True, index=ohlcv.index)

    if params.get("use_momentum_long_range", False):
        lo = float(params.get("momentum_long_more", -100))
        hi = float(params.get("momentum_long_less", 10))
        long_signal = long_signal & (mom_vals >= lo) & (mom_vals <= hi)
        long_signal = long_signal.fillna(False)

    if params.get("use_momentum_short_range", False):
        hi_s = float(params.get("momentum_short_less", 95))
        lo_s = float(params.get("momentum_short_more", -30))
        short_signal = short_signal & (mom_vals <= hi_s) & (mom_vals >= lo_s)
        short_signal = short_signal.fillna(False)

    logger.debug(
        "Momentum filter | len={} src={} | long={} short={}",
        mom_len,
        mom_src,
        long_signal.sum(),
        short_signal.sum(),
    )
    return {"long": long_signal, "short": short_signal, "momentum": mom_vals}


# ═══════════════════════════════════════════════════════════════════════════
# Block Registry
# ═══════════════════════════════════════════════════════════════════════════
#
# Each entry has three fields:
#   handler       - callable that computes the indicator
#   outputs       - exhaustive list of keys the handler guarantees to return
#   param_aliases - {old_frontend_key: canonical_backend_key} applied before
#                   the handler is called so both old and new param names work
#
# Rules for maintaining this table:
#  1. When a handler's return dict changes, update `outputs` here.
#  2. When the frontend renames a param, add the old name as an alias here
#     (do NOT rename inside the handler — that breaks saved strategies).
#  3. `_execute_indicator` applies aliases and validates outputs against this
#     table so mismatches surface immediately as warnings instead of silent
#     bugs weeks later.
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
    # ── Trend — MA family ────────────────────────────────────────────────
    "ema": {
        "handler": _handle_ema,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "sma": {
        "handler": _handle_sma,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "wma": {
        "handler": _handle_wma,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "dema": {
        "handler": _handle_dema,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "tema": {
        "handler": _handle_tema,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "hull_ma": {
        "handler": _handle_hull_ma,
        "outputs": ["value"],
        "param_aliases": {},
    },
    # ── Band / Channel ───────────────────────────────────────────────────
    "bollinger": {
        "handler": _handle_bollinger,
        "outputs": ["upper", "middle", "lower"],
        "param_aliases": {},
    },
    "keltner": {
        "handler": _handle_keltner,
        "outputs": ["upper", "middle", "lower"],
        "param_aliases": {},
    },
    "donchian": {
        "handler": _handle_donchian,
        "outputs": ["upper", "middle", "lower"],
        "param_aliases": {},
    },
    # ── Volatility ───────────────────────────────────────────────────────
    "atr": {
        "handler": _handle_atr,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "atrp": {
        "handler": _handle_atrp,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "stddev": {
        "handler": _handle_stddev,
        "outputs": ["value"],
        "param_aliases": {},
    },
    # ── Trend — non-MA ───────────────────────────────────────────────────
    "adx": {
        "handler": _handle_adx,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "supertrend": {
        "handler": _handle_supertrend,
        "outputs": ["supertrend", "direction", "upper", "lower", "long", "short"],
        "param_aliases": {},
    },
    "ichimoku": {
        "handler": _handle_ichimoku,
        # NOTE: ichimoku does NOT return long/short — use cloud cross as condition
        "outputs": ["tenkan_sen", "kijun_sen", "senkou_span_a", "senkou_span_b", "chikou_span"],
        "param_aliases": {},
    },
    "parabolic_sar": {
        "handler": _handle_parabolic_sar,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "aroon": {
        "handler": _handle_aroon,
        "outputs": ["up", "down", "oscillator"],
        "param_aliases": {},
    },
    # ── Volume ───────────────────────────────────────────────────────────
    "obv": {
        "handler": _handle_obv,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "vwap": {
        "handler": _handle_vwap,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "cmf": {
        "handler": _handle_cmf,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "ad_line": {
        "handler": _handle_ad_line,
        "outputs": ["value"],
        "param_aliases": {},
    },
    "pvt": {
        "handler": _handle_pvt,
        "outputs": ["value"],
        "param_aliases": {},
    },
    # ── Support / Resistance ─────────────────────────────────────────────
    "pivot_points": {
        "handler": _handle_pivot_points,
        "outputs": ["pp", "r1", "r2", "r3", "s1", "s2", "s3"],
        "param_aliases": {},
    },
    # ── Multi-timeframe ──────────────────────────────────────────────────
    "mtf": {
        "handler": _handle_mtf,
        "outputs": ["value"],
        "param_aliases": {},
    },
    # ── Universal filters ────────────────────────────────────────────────
    "atr_volatility": {
        "handler": _handle_atr_volatility,
        "outputs": ["long", "short"],
        "param_aliases": {},
    },
    "volume_filter": {
        "handler": _handle_volume_filter,
        "outputs": ["long", "short"],
        "param_aliases": {},
    },
    "highest_lowest_bar": {
        "handler": _handle_highest_lowest_bar,
        "outputs": ["long", "short"],
        "param_aliases": {},
    },
    "two_mas": {
        "handler": _handle_two_mas,
        "outputs": ["long", "short", "ma1", "ma2"],
        "param_aliases": {},
    },
    "accumulation_areas": {
        "handler": _handle_accumulation_areas,
        "outputs": ["long", "short"],
        "param_aliases": {},
    },
    "keltner_bollinger": {
        "handler": _handle_keltner_bollinger,
        "outputs": ["long", "short"],
        "param_aliases": {},
    },
    "rvi_filter": {
        "handler": _handle_rvi_filter,
        "outputs": ["long", "short", "rvi"],
        "param_aliases": {},
    },
    "mfi_filter": {
        "handler": _handle_mfi_filter,
        "outputs": ["long", "short", "mfi"],
        "param_aliases": {},
    },
    "cci_filter": {
        "handler": _handle_cci_filter,
        "outputs": ["long", "short", "cci"],
        "param_aliases": {},
    },
    "momentum_filter": {
        "handler": _handle_momentum_filter,
        "outputs": ["long", "short", "momentum"],
        "param_aliases": {},
    },
    # Alias for legacy saved strategies that used block type "momentum" instead of
    # "momentum_filter".  Frontend now always sends "momentum_filter".
    "momentum": {
        "handler": _handle_momentum_filter,
        "outputs": ["long", "short", "momentum"],
        "param_aliases": {},
    },
}

# Backward-compatible dispatch table — generated automatically from the registry.
# New code should import BLOCK_REGISTRY directly; INDICATOR_DISPATCH is kept
# so that any external callers (tests, scripts) do not break.
INDICATOR_DISPATCH: dict[str, Any] = {k: v["handler"] for k, v in BLOCK_REGISTRY.items()}
