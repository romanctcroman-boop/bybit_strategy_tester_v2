"""
Other indicators - остальные индикаторы.

Этот модуль содержит обработчики для остальных индикаторов:
- pivot_points, mtf
- highest_lowest_bar, accumulation_areas, keltner_bollinger
- mfi_filter, cci_filter, momentum_filter
- momentum (alias)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from loguru import logger

from backend.backtesting.strategy_builder_adapter import _clamp_period
from backend.core.indicators import (
    calculate_atr,
    calculate_bollinger,
    calculate_cci,
    calculate_keltner,
    calculate_mfi,
    calculate_pivot_points_array,
)

if TYPE_CHECKING:
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter


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

    Args:
        ohlcv: OHLCV DataFrame to resample.
        timeframe: Target timeframe.

    Returns:
        Resampled DataFrame or None.
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
    """Handle Multi-Timeframe indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with MTF indicator values.
    """
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
            from backend.core.indicators import calculate_rsi

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
            from backend.core.indicators import calculate_rsi

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
# Support / Resistance
# ═══════════════════════════════════════════════════════════════════════════


def _handle_pivot_points(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle Pivot Points indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with pivot points (pp, r1, r2, r3, s1, s2, s3).
    """
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
# Other indicators
# ═══════════════════════════════════════════════════════════════════════════


def _handle_highest_lowest_bar(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle Highest/Lowest Bar indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with long/short signals.
    """
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


def _handle_accumulation_areas(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle Accumulation Areas indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with long/short signals.
    """
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
    """Handle Keltner/Bollinger Channel indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with long/short signals.
    """
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


def _handle_mfi_filter(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle MFI Filter indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with long/short signals and MFI values.
    """
    mfi_len = int(params.get("mfi_length", 14))
    mfi_tf = params.get("mfi_timeframe", "Chart")

    # Determine working OHLCV: main, HTF-resampled, or BTCUSDT proxy
    working_ohlcv = ohlcv
    main_tf = str(getattr(adapter, "main_interval", ""))
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
    """Handle CCI Filter indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with long/short signals and CCI values.
    """
    cci_len = int(params.get("cci_length", 14))
    cci_tf = params.get("cci_timeframe", "Chart")

    # Determine working OHLCV: main or HTF-resampled
    working_ohlcv = ohlcv
    main_tf = str(getattr(adapter, "main_interval", ""))
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
    """Handle Momentum Filter indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with long/short signals and momentum values.
    """
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

BLOCK_REGISTRY: dict[str, dict[str, Any]] = {
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
    # ── Other indicators ─────────────────────────────────────────────────
    "highest_lowest_bar": {
        "handler": _handle_highest_lowest_bar,
        "outputs": ["long", "short"],
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

# Backward-compatible dispatch table for this module
INDICATOR_DISPATCH: dict[str, Any] = {k: v["handler"] for k, v in BLOCK_REGISTRY.items()}
