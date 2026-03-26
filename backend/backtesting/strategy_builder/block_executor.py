"""
Block executor — pure block-execution functions.

Contains logic for executing specific block categories that require no
adapter instance state (pure computation on Series/params).

All functions here are called by StrategyBuilderAdapter._execute_*() methods
via thin wrappers, enabling isolated unit-testing.

Public functions:
    apply_signal_memory       — extend a single boolean signal for N bars
    extend_dual_signal_memory — extend buy+sell signals mutually cancelling
    execute_condition         — crossover/threshold/comparison conditions
    execute_logic             — AND/OR/NOT/delay/filter/comparison logic
    execute_input             — price/volume/constant input blocks
    execute_filter            — filter blocks (RSI, MACD, ADX, ATR, ...)
    execute_signal_block      — signal routing blocks (long_entry, etc.)
    execute_action            — action blocks (buy, sell, trailing_stop, ...)
    execute_exit              — exit condition blocks (static_sltp, atr_exit, ...)
    execute_position_sizing   — position sizing config blocks
    execute_time_filter       — time-based filter blocks
    execute_price_action      — candlestick pattern detection blocks
    execute_divergence        — price/indicator divergence detection
    execute_close_condition   — close-condition blocks (close_by_time, close_rsi, ...)
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

from backend.backtesting.strategy_builder.utils import _clamp_period, _param
from backend.core.indicators import (
    calculate_adx,
    calculate_atr,
    calculate_atr_smoothed,
    calculate_bollinger,
    calculate_cci,
    calculate_cmf,
    calculate_ema,
    calculate_keltner,
    calculate_macd,
    calculate_mfi,
    calculate_obv,
    calculate_parabolic_sar,
    calculate_roc,
    calculate_rsi,
    calculate_sma,
    calculate_stochastic,
)

# ---------------------------------------------------------------------------
# apply_signal_memory — single signal persistence helper
# ---------------------------------------------------------------------------


def apply_signal_memory(signal: pd.Series, bars: int) -> pd.Series:
    """Keep a boolean signal active for ``bars`` bars after it fires.

    Args:
        signal: Boolean Series where ``True`` = signal fired.
        bars: Number of bars to keep the signal active.

    Returns:
        Boolean Series with extended signal memory.
    """
    if bars <= 0:
        return signal
    result = signal.copy()
    for i in range(1, bars + 1):
        result = result | signal.shift(i).fillna(False).astype(bool)
    return result


# ---------------------------------------------------------------------------
# extend_dual_signal_memory — dual buy/sell signal memory with cancellation
# ---------------------------------------------------------------------------


def extend_dual_signal_memory(
    buy_events: np.ndarray,
    sell_events: np.ndarray,
    memory_bars: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Extend buy/sell signals for N bars after each event; opposite signal cancels.

    If a buy occurs at bar i, buy is True for bars i..i+N unless a sell occurs
    in that window (then buy memory stops at that bar). Same for sell.

    Args:
        buy_events: Boolean ndarray of buy signal events.
        sell_events: Boolean ndarray of sell signal events.
        memory_bars: Number of bars to extend each signal.

    Returns:
        Tuple of (buy_out, sell_out) boolean ndarrays.
    """
    n = len(buy_events)
    buy_out = np.zeros(n, dtype=bool)
    sell_out = np.zeros(n, dtype=bool)
    active_buy_until = -1
    active_sell_until = -1
    for i in range(n):
        if sell_events[i]:
            active_buy_until = -1
        if buy_events[i]:
            active_buy_until = i + memory_bars
        buy_out[i] = active_buy_until >= i
        if buy_events[i]:
            active_sell_until = -1
        if sell_events[i]:
            active_sell_until = i + memory_bars
        sell_out[i] = active_sell_until >= i
    return buy_out, sell_out


# ---------------------------------------------------------------------------
# execute_condition — crossover / threshold / comparison conditions
# ---------------------------------------------------------------------------


def execute_condition(
    condition_type: str,
    params: dict[str, Any],
    inputs: dict[str, pd.Series],
) -> dict[str, pd.Series]:
    """Execute a condition block.

    Supports port name variants from different frontend versions:

    - ``'a'`` / ``'b'`` (legacy)
    - ``'left'`` / ``'right'`` (current frontend port IDs for greater_than/less_than)

    Args:
        condition_type: Block type string (e.g. ``"crossover"``, ``"greater_than"``).
        params: Block parameter dict.
        inputs: Upstream Series values keyed by port name.

    Returns:
        Dict with ``"result"`` key containing a boolean Series.
    """
    # Infer series shape from inputs
    ref = next(iter(inputs.values()), None) if inputs else None

    def _empty_bool() -> pd.Series:
        if ref is not None:
            return pd.Series([False] * len(ref), index=ref.index)
        return pd.Series([False], dtype=bool)

    def _empty_numeric() -> pd.Series:
        if ref is not None:
            return pd.Series([0.0] * len(ref), index=ref.index)
        return pd.Series([0.0])

    if condition_type == "crossover":
        a = inputs.get("a", inputs.get("left", _empty_bool()))
        b = inputs.get("b", inputs.get("right", _empty_bool()))
        return {"result": (a > b) & (a.shift(1) <= b.shift(1))}

    if condition_type == "crossunder":
        a = inputs.get("a", inputs.get("left", _empty_bool()))
        b = inputs.get("b", inputs.get("right", _empty_bool()))
        return {"result": (a < b) & (a.shift(1) >= b.shift(1))}

    if condition_type == "greater_than":
        a = inputs.get("a", inputs.get("left", _empty_numeric()))
        # Fall back to threshold_b param when no "b" input is wired (graph_converter Cat B)
        if "b" not in inputs and "right" not in inputs and "threshold_b" in params:
            b_val = float(params["threshold_b"])
            b = pd.Series([b_val] * len(a), index=a.index) if ref is not None else _empty_numeric()
        else:
            b = inputs.get("b", inputs.get("right", _empty_numeric()))
        return {"result": a > b}

    if condition_type == "less_than":
        a = inputs.get("a", inputs.get("left", _empty_numeric()))
        if "b" not in inputs and "right" not in inputs and "threshold_b" in params:
            b_val = float(params["threshold_b"])
            b = pd.Series([b_val] * len(a), index=a.index) if ref is not None else _empty_numeric()
        else:
            b = inputs.get("b", inputs.get("right", _empty_numeric()))
        return {"result": a < b}

    if condition_type == "equals":
        a = inputs.get("a", inputs.get("left", _empty_numeric()))
        b = inputs.get("b", inputs.get("right", _empty_numeric()))
        tolerance = float(params.get("tolerance", 0.0001))
        return {"result": (a - b).abs() <= tolerance}

    if condition_type == "between":
        value = inputs.get("value", _empty_numeric())
        min_val = inputs.get("min", _empty_numeric())
        max_val = inputs.get("max", _empty_numeric())
        return {"result": (value >= min_val) & (value <= max_val)}

    logger.warning(f"Unknown condition type: {condition_type}")
    return {"result": _empty_bool()}


# ---------------------------------------------------------------------------
# execute_logic — AND / OR / NOT / delay / filter / comparison
# ---------------------------------------------------------------------------


def execute_logic(
    logic_type: str,
    params: dict[str, Any],
    inputs: dict[str, pd.Series],
) -> dict[str, pd.Series]:
    """Execute a logic block.

    Args:
        logic_type: Block type (``"and"``, ``"or"``, ``"not"``, ``"delay"``,
            ``"filter"``, ``"comparison"``).
        params: Block parameter dict.
        inputs: Upstream Series keyed by port name.

    Returns:
        Dict with ``"result"`` key.
    """
    ref = next(iter(inputs.values()), None) if inputs else None

    def _default_bool(fill: bool = False) -> pd.Series:
        if ref is not None:
            return pd.Series([fill] * len(ref), index=ref.index)
        return pd.Series([fill], dtype=bool)

    def _default_numeric(fill: float = 0.0) -> pd.Series:
        if ref is not None:
            return pd.Series([fill] * len(ref), index=ref.index)
        return pd.Series([fill])

    if logic_type == "and":
        a = inputs.get("a", _default_bool())
        b = inputs.get("b", _default_bool())
        result = a & b
        if "c" in inputs:
            result = result & inputs["c"]
        return {"result": result}

    if logic_type == "or":
        a = inputs.get("a", _default_bool())
        b = inputs.get("b", _default_bool())
        result = a | b
        if "c" in inputs:
            result = result | inputs["c"]
        return {"result": result}

    if logic_type == "not":
        return {"result": ~inputs.get("input", _default_bool())}

    if logic_type == "delay":
        bars = params.get("bars", 1)
        input_val = inputs.get("input", _default_bool())
        return {"result": input_val.shift(bars).fillna(False).astype(bool)}

    if logic_type == "filter":
        signal = inputs.get("signal", _default_bool())
        filter_val = inputs.get("filter", _default_bool(fill=True))
        return {"result": signal & filter_val}

    if logic_type == "comparison":
        a = inputs.get("value_a", inputs.get("a", _default_numeric()))
        b = inputs.get("value_b", inputs.get("b", _default_numeric()))
        op = params.get("operator", "==")

        if len(a) != len(b):
            if len(a) == 1:
                a = pd.Series([float(a.iloc[0])] * len(b), index=b.index)
            elif len(b) == 1:
                b = pd.Series([float(b.iloc[0])] * len(a), index=a.index)

        ops = {
            ">": a > b,
            "<": a < b,
            ">=": a >= b,
            "<=": a <= b,
            "==": a == b,
            "!=": a != b,
        }
        if op in ops:
            return {"result": ops[op]}

        if op == "crosses_above":
            result = (a > b) & (a.shift(1) <= b.shift(1))
            return {"result": result.fillna(False)}

        if op == "crosses_below":
            result = (a < b) & (a.shift(1) >= b.shift(1))
            return {"result": result.fillna(False)}

        logger.warning(f"Unknown comparison operator: {op}")
        return {"result": pd.Series([False] * len(a), index=a.index)}

    logger.warning(f"Unknown logic type: {logic_type}")
    return {"result": _default_bool()}


# ---------------------------------------------------------------------------
# execute_input — price / volume / constant input blocks
# ---------------------------------------------------------------------------


def execute_input(input_type: str, params: dict[str, Any], ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
    """Execute an input block.

    Args:
        input_type: One of ``"price"``, ``"volume"``, ``"constant"``.
        params: Block parameter dict.
        ohlcv: OHLCV DataFrame.

    Returns:
        Dict of output Series keyed by port name.
    """
    if input_type == "price":
        return {
            "open": ohlcv["open"],
            "high": ohlcv["high"],
            "low": ohlcv["low"],
            "close": ohlcv["close"],
            "value": ohlcv["close"],  # Alias for compatibility with connections
        }
    if input_type == "volume":
        return {"value": ohlcv["volume"]}
    if input_type == "constant":
        value = params.get("value", 0)
        n = len(ohlcv)
        return {"value": pd.Series([value] * n, index=ohlcv.index)}

    logger.warning(f"Unknown input type: {input_type}")
    return {}


# ---------------------------------------------------------------------------
# execute_filter — filter blocks (RSI, MACD, ADX, ATR, volume, ...)
# ---------------------------------------------------------------------------


def execute_filter(
    filter_type: str,
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    inputs: dict[str, pd.Series],
) -> dict[str, pd.Series]:
    """Execute a filter block — generates buy/sell signals based on indicator conditions.

    Filters are self-contained signal generators that compute indicators internally
    and return buy/sell boolean series.

    Args:
        filter_type: Block type string (e.g. ``"rsi_filter"``, ``"macd_filter"``).
        params: Block parameter dict.
        ohlcv: OHLCV DataFrame.
        inputs: Upstream Series values keyed by port name.

    Returns:
        Dict of output Series (``"buy"``, ``"sell"``, and indicator value ports).
    """
    n = len(ohlcv)
    close = ohlcv["close"].values
    high = ohlcv["high"].values
    low = ohlcv["low"].values
    volume = ohlcv["volume"].values

    # Helper for crossover detection (using shift to avoid np.roll wraparound)
    def crossover(a, b):
        a_prev = pd.Series(a).shift(1).fillna(a[0] if len(a) > 0 else 0).values
        b_prev = pd.Series(b).shift(1).fillna(b[0] if len(b) > 0 else 0).values
        return (a > b) & (a_prev <= b_prev)

    def crossunder(a, b):
        a_prev = pd.Series(a).shift(1).fillna(a[0] if len(a) > 0 else 0).values
        b_prev = pd.Series(b).shift(1).fillna(b[0] if len(b) > 0 else 0).values
        return (a < b) & (a_prev >= b_prev)

    # ========== RSI Filter ==========
    if filter_type == "rsi_filter":
        period = params.get("period", 14)
        oversold = params.get("oversold", 30)
        overbought = params.get("overbought", 70)
        mode = params.get("mode", "range")  # range, cross

        rsi = calculate_rsi(close, period)

        if mode == "range":
            buy = rsi < oversold
            sell = rsi > overbought
        else:  # cross
            buy = crossunder(rsi, np.full(n, oversold))
            sell = crossover(rsi, np.full(n, overbought))

        mem_bars = int(params.get("signal_memory_bars", 0))
        if mem_bars > 0 and (params.get("signal_memory_enable", False) or params.get("use_signal_memory", False)):
            buy, sell = extend_dual_signal_memory(np.asarray(buy, dtype=bool), np.asarray(sell, dtype=bool), mem_bars)

        return {
            "buy": pd.Series(buy, index=ohlcv.index),
            "sell": pd.Series(sell, index=ohlcv.index),
            "value": pd.Series(rsi, index=ohlcv.index),
        }

    # (QQE Filter removed — consolidated into universal QQE indicator block)

    # (SuperTrend Filter removed — consolidated into universal SuperTrend indicator block)

    # ========== Two MA Filter ==========
    elif filter_type == "two_ma_filter":
        fast_period = _param(params, 9, "fast_period", "fastPeriod")
        slow_period = _param(params, 21, "slow_period", "slowPeriod")
        ma_type = _param(params, "ema", "ma_type", "maType")

        if ma_type == "ema":
            fast = calculate_ema(close, fast_period)
            slow = calculate_ema(close, slow_period)
        else:
            fast = calculate_sma(close, fast_period)
            slow = calculate_sma(close, slow_period)

        buy = crossover(fast, slow)
        sell = crossunder(fast, slow)

        mem_bars = int(params.get("ma_cross_memory_bars", 0))
        if mem_bars > 0:
            buy, sell = extend_dual_signal_memory(np.asarray(buy, dtype=bool), np.asarray(sell, dtype=bool), mem_bars)

        return {
            "buy": pd.Series(buy, index=ohlcv.index),
            "sell": pd.Series(sell, index=ohlcv.index),
            "fast": pd.Series(fast, index=ohlcv.index),
            "slow": pd.Series(slow, index=ohlcv.index),
        }

    # (Stochastic Filter removed — consolidated into universal Stochastic indicator block)

    # ========== MACD Filter ==========
    elif filter_type == "macd_filter":
        macd_fast_p: int = int(_param(params, 12, "fast_period", "fast"))
        macd_slow_p: int = int(_param(params, 26, "slow_period", "slow"))
        signal_period: int = int(_param(params, 9, "signal_period", "signal"))
        mode = params.get("mode", "signal_cross")  # signal_cross, zero_cross, histogram

        macd_line, signal_line, histogram = calculate_macd(close, macd_fast_p, macd_slow_p, signal_period)

        if mode == "zero_cross":
            buy = crossover(macd_line, np.zeros(n))
            sell = crossunder(macd_line, np.zeros(n))
        elif mode == "histogram":
            hist_prev = pd.Series(histogram).shift(1).fillna(0).values
            buy = (histogram > 0) & (hist_prev <= 0)
            sell = (histogram < 0) & (hist_prev >= 0)
        else:  # signal_cross
            buy = crossover(macd_line, signal_line)
            sell = crossunder(macd_line, signal_line)

        mem_bars = int(params.get("macd_signal_memory_bars", 0))
        if mem_bars > 0 and not params.get("disable_macd_signal_memory", True):
            buy, sell = extend_dual_signal_memory(np.asarray(buy, dtype=bool), np.asarray(sell, dtype=bool), mem_bars)

        return {
            "buy": pd.Series(buy, index=ohlcv.index),
            "sell": pd.Series(sell, index=ohlcv.index),
            "macd": pd.Series(macd_line, index=ohlcv.index),
            "signal": pd.Series(signal_line, index=ohlcv.index),
            "histogram": pd.Series(histogram, index=ohlcv.index),
        }

    # ========== CCI Filter ==========
    elif filter_type == "cci_filter":
        period = params.get("period", 20)
        oversold = params.get("oversold", -100)
        overbought = params.get("overbought", 100)

        cci = calculate_cci(high, low, close, period)

        buy = crossunder(cci, np.full(n, oversold))
        sell = crossover(cci, np.full(n, overbought))

        return {
            "buy": pd.Series(buy, index=ohlcv.index),
            "sell": pd.Series(sell, index=ohlcv.index),
            "value": pd.Series(cci, index=ohlcv.index),
        }

    # ========== DMI/ADX Filter ==========
    elif filter_type == "dmi_filter":
        period = params.get("period", 14)
        adx_threshold = _param(params, 25, "threshold", "adxThreshold")

        adx_result = calculate_adx(high, low, close, period)
        adx = adx_result.adx
        plus_di = adx_result.plus_di
        minus_di = adx_result.minus_di

        # Buy when +DI crosses above -DI and ADX > threshold
        buy = crossover(plus_di, minus_di) & (adx > adx_threshold)
        sell = crossunder(plus_di, minus_di) & (adx > adx_threshold)

        return {
            "buy": pd.Series(buy, index=ohlcv.index),
            "sell": pd.Series(sell, index=ohlcv.index),
            "adx": pd.Series(adx, index=ohlcv.index),
            "plus_di": pd.Series(plus_di, index=ohlcv.index),
            "minus_di": pd.Series(minus_di, index=ohlcv.index),
        }

    # ========== ADX Filter ==========
    elif filter_type == "adx_filter":
        period = params.get("period", 14)
        threshold = _param(params, 25, "threshold", "adxThreshold")

        adx_result = calculate_adx(high, low, close, period)
        adx = adx_result.adx

        # True when ADX > threshold (trending market)
        trending = adx > threshold

        return {
            "buy": pd.Series(trending, index=ohlcv.index),
            "sell": pd.Series(trending, index=ohlcv.index),
            "pass": pd.Series(trending, index=ohlcv.index),
            "value": pd.Series(adx, index=ohlcv.index),
        }

    # ========== ATR Filter ==========
    elif filter_type == "atr_filter":
        period = params.get("period", 14)
        threshold = params.get("threshold", 1.5)  # ATR multiplier

        atr = calculate_atr(high, low, close, period)
        atr_ma = pd.Series(atr).rolling(period).mean().values

        # High volatility when ATR > threshold * average ATR
        high_volatility = atr > (threshold * atr_ma)

        return {
            "pass": pd.Series(high_volatility, index=ohlcv.index),
            "value": pd.Series(atr, index=ohlcv.index),
        }

    # ========== Volume Filter ==========
    elif filter_type == "volume_filter":
        period = params.get("period", 20)
        multiplier = params.get("multiplier", 1.5)

        volume_ma = pd.Series(volume).rolling(period).mean().values
        high_volume = volume > (multiplier * volume_ma)

        return {
            "pass": pd.Series(high_volume, index=ohlcv.index),
            "value": pd.Series(volume, index=ohlcv.index),
            "ma": pd.Series(volume_ma, index=ohlcv.index),
        }

    # ========== Volume Compare Filter ==========
    elif filter_type == "volume_compare_filter":
        period = params.get("period", 20)
        multiplier = params.get("multiplier", 2.0)

        volume_ma = pd.Series(volume).rolling(period).mean().values
        above_avg = volume > (multiplier * volume_ma)

        return {
            "pass": pd.Series(above_avg, index=ohlcv.index),
            "ratio": pd.Series(volume / np.maximum(volume_ma, 1), index=ohlcv.index),
        }

    # ========== CMF Filter ==========
    elif filter_type == "cmf_filter":
        period = params.get("period", 20)
        threshold = params.get("threshold", 0.05)

        cmf = calculate_cmf(high, low, close, volume, period)

        buy = cmf > threshold
        sell = cmf < -threshold

        return {
            "buy": pd.Series(buy, index=ohlcv.index),
            "sell": pd.Series(sell, index=ohlcv.index),
            "value": pd.Series(cmf, index=ohlcv.index),
        }

    # ========== Trend Filter ==========
    elif filter_type == "trend_filter":
        ema_period = params.get("emaPeriod", 50)
        adx_period = params.get("adxPeriod", 14)
        adx_threshold = _param(params, 25, "threshold", "adxThreshold")

        ema = calculate_ema(close, ema_period)
        adx_result = calculate_adx(high, low, close, adx_period)

        uptrend = (close > ema) & (adx_result.adx > adx_threshold)
        downtrend = (close < ema) & (adx_result.adx > adx_threshold)

        return {
            "uptrend": pd.Series(uptrend, index=ohlcv.index),
            "downtrend": pd.Series(downtrend, index=ohlcv.index),
            "ema": pd.Series(ema, index=ohlcv.index),
            "adx": pd.Series(adx_result.adx, index=ohlcv.index),
        }

    # ========== Price Filter ==========
    elif filter_type == "price_filter":
        level = params.get("level", 0)
        mode = params.get("mode", "above")  # above, below
        result = close > level if mode == "above" else close < level

        return {"pass": pd.Series(result, index=ohlcv.index)}

    # ========== Volatility Filter ==========
    elif filter_type == "volatility_filter":
        period = params.get("period", 20)
        mode = params.get("mode", "atr")  # atr, bb_width
        threshold = params.get("threshold", 1.0)

        if mode == "bb_width":
            bb_mid, bb_upper, bb_lower = calculate_bollinger(close, period, 2.0)
            bb_width = (bb_upper - bb_lower) / np.where(bb_mid != 0, bb_mid, 1.0)
            bb_width_ma = pd.Series(bb_width).rolling(period).mean().values
            high_vol = bb_width > (threshold * bb_width_ma)
            return {"pass": pd.Series(high_vol, index=ohlcv.index), "value": pd.Series(bb_width, index=ohlcv.index)}
        else:
            atr = calculate_atr(high, low, close, period)
            atr_ma = pd.Series(atr).rolling(period).mean().values
            high_vol = atr > (threshold * atr_ma)
            return {"pass": pd.Series(high_vol, index=ohlcv.index), "value": pd.Series(atr, index=ohlcv.index)}

    # ========== Highest/Lowest Filter ==========
    elif filter_type == "highest_lowest_filter":
        period = params.get("period", 20)

        highest = pd.Series(high).rolling(period).max().values
        lowest = pd.Series(low).rolling(period).min().values

        breakout_up = close >= highest
        breakout_down = close <= lowest

        return {
            "buy": pd.Series(breakout_up, index=ohlcv.index),
            "sell": pd.Series(breakout_down, index=ohlcv.index),
            "highest": pd.Series(highest, index=ohlcv.index),
            "lowest": pd.Series(lowest, index=ohlcv.index),
        }

    # ========== Momentum Filter ==========
    elif filter_type == "momentum_filter":
        period = params.get("period", 10)
        threshold = params.get("threshold", 0)

        momentum = close - pd.Series(close).shift(period).fillna(0).values

        buy = momentum > threshold
        sell = momentum < -threshold

        return {
            "buy": pd.Series(buy, index=ohlcv.index),
            "sell": pd.Series(sell, index=ohlcv.index),
            "value": pd.Series(momentum, index=ohlcv.index),
        }

    # ========== Time Filter ==========
    elif filter_type == "time_filter":
        start_hour = params.get("startHour", 9)
        end_hour = params.get("endHour", 17)

        hours = ohlcv.index.hour if hasattr(ohlcv.index, "hour") else np.zeros(n)
        in_session = (hours >= start_hour) & (hours < end_hour)

        return {"pass": pd.Series(in_session, index=ohlcv.index)}

    # ========== Accumulation Filter ==========
    elif filter_type == "accumulation_filter":
        # Detect volume accumulation zones
        period = params.get("period", 20)
        volume_mult = params.get("volume_multiplier", 1.5)
        range_threshold = params.get("range_threshold", 0.5)  # ATR multiplier

        vol_series = ohlcv["volume"]
        avg_volume = vol_series.rolling(period).mean()
        high_volume = vol_series > avg_volume * volume_mult

        # Price range compression (consolidation)
        atr = pd.Series(
            calculate_atr(ohlcv["high"].values, ohlcv["low"].values, ohlcv["close"].values, period),
            index=ohlcv.index,
        )
        price_range = ohlcv["high"] - ohlcv["low"]
        avg_range = price_range.rolling(period).mean()
        tight_range = price_range < avg_range * range_threshold

        # Accumulation: high volume + tight range
        accumulation = high_volume & tight_range

        # Distribution: high volume + wide range
        distribution = high_volume & ~tight_range

        return {
            "accumulation": accumulation.fillna(False),
            "distribution": distribution.fillna(False),
            "buy": accumulation.fillna(False),
            "sell": distribution.fillna(False),
        }

    # ========== Linear Regression Filter ==========
    elif filter_type == "linreg_filter":
        # Linear regression channel filter
        period = params.get("period", 20)
        dev_mult = params.get("deviation", 2.0)
        mode = params.get("mode", "trend")  # trend, channel_break, slope

        close_s = ohlcv["close"]

        # Calculate linear regression
        def linreg(series, length):
            """Calculate linear regression value."""
            x = np.arange(length)
            res = np.full(len(series), np.nan)
            for i in range(length - 1, len(series)):
                y = series.iloc[i - length + 1 : i + 1].values
                if len(y) == length:
                    slope, intercept = np.polyfit(x, y, 1)
                    res[i] = intercept + slope * (length - 1)
            return res

        def linreg_slope(series, length):
            """Calculate linear regression slope."""
            x = np.arange(length)
            res = np.full(len(series), np.nan)
            for i in range(length - 1, len(series)):
                y = series.iloc[i - length + 1 : i + 1].values
                if len(y) == length:
                    slope, _ = np.polyfit(x, y, 1)
                    res[i] = slope
            return res

        linreg_val = pd.Series(linreg(close_s, period), index=ohlcv.index)
        slope = pd.Series(linreg_slope(close_s, period), index=ohlcv.index)

        # Standard deviation for channel
        residuals = close_s - linreg_val
        std = residuals.rolling(period).std()
        upper = linreg_val + dev_mult * std
        lower = linreg_val - dev_mult * std

        if mode == "trend":
            # Uptrend: positive slope, price above linreg
            buy = (slope > 0) & (close_s > linreg_val)
            sell = (slope < 0) & (close_s < linreg_val)
        elif mode == "channel_break":
            # Buy on upper break, sell on lower break
            buy = close_s > upper
            sell = close_s < lower
        else:  # slope
            # Buy on positive slope, sell on negative
            buy = slope > 0
            sell = slope < 0

        return {
            "buy": buy.fillna(False),
            "sell": sell.fillna(False),
            "linreg": linreg_val,
            "slope": slope,
            "upper": upper,
            "lower": lower,
        }

    # (divergence_filter removed — old divergence blocks cleared)

    # ========== Balance of Power Filter ==========
    elif filter_type == "bop_filter":
        # Balance of Power indicator filter
        period = params.get("period", 14)
        threshold = params.get("threshold", 0.0)
        mode = params.get("mode", "level")  # level, cross, trend

        # BOP = (Close - Open) / (High - Low)
        high_s = ohlcv["high"]
        low_s = ohlcv["low"]
        open_price = ohlcv["open"]
        close_s = ohlcv["close"]

        bop = (close_s - open_price) / (high_s - low_s + 1e-10)
        bop_smooth = bop.rolling(period).mean()

        if mode == "level":
            # Buy when BOP above threshold, sell when below
            buy = bop_smooth > threshold
            sell = bop_smooth < -threshold
        elif mode == "cross":
            # Buy on cross above zero, sell on cross below
            buy = (bop_smooth > 0) & (bop_smooth.shift(1) <= 0)
            sell = (bop_smooth < 0) & (bop_smooth.shift(1) >= 0)
        else:  # trend
            # Buy on rising BOP, sell on falling
            buy = bop_smooth > bop_smooth.shift(1)
            sell = bop_smooth < bop_smooth.shift(1)

        return {
            "buy": buy.fillna(False),
            "sell": sell.fillna(False),
            "value": bop_smooth,
        }

    # ========== Levels Break Filter ==========
    elif filter_type == "levels_filter":
        # Pivot/Support/Resistance break filter
        period = params.get("period", 20)
        level_type = params.get("level_type", "pivot")  # pivot, swing, fixed

        high_s = ohlcv["high"]
        low_s = ohlcv["low"]
        close_s = ohlcv["close"]

        if level_type == "pivot":
            # Use pivot points
            pp = (high_s.shift(1) + low_s.shift(1) + close_s.shift(1)) / 3
            r1 = 2 * pp - low_s.shift(1)
            s1 = 2 * pp - high_s.shift(1)

            buy = close_s > r1  # Break above R1
            sell = close_s < s1  # Break below S1

            return {
                "buy": buy.fillna(False),
                "sell": sell.fillna(False),
                "pivot": pp,
                "r1": r1,
                "s1": s1,
            }
        else:  # swing
            # Swing high/low breaks
            swing_high = high_s.rolling(period).max()
            swing_low = low_s.rolling(period).min()

            buy = close_s > swing_high.shift(1)  # Break above swing high
            sell = close_s < swing_low.shift(1)  # Break below swing low

            return {
                "buy": buy.fillna(False),
                "sell": sell.fillna(False),
                "swing_high": swing_high,
                "swing_low": swing_low,
            }

    # ========== Price Action Filter ==========
    elif filter_type == "price_action_filter":
        # Candlestick pattern filter
        pattern = params.get("pattern", "engulfing")

        o = ohlcv["open"]
        h = ohlcv["high"]
        low_s = ohlcv["low"]
        c = ohlcv["close"]
        body = abs(c - o)

        if pattern == "engulfing":
            # Bullish engulfing
            prev_red = o.shift(1) > c.shift(1)
            curr_green = c > o
            engulfs = (c > o.shift(1)) & (o < c.shift(1))
            bullish = prev_red & curr_green & engulfs

            # Bearish engulfing
            prev_green = c.shift(1) > o.shift(1)
            curr_red = o > c
            engulfs_bear = (o > c.shift(1)) & (c < o.shift(1))
            bearish = prev_green & curr_red & engulfs_bear

        elif pattern == "doji":
            # Doji: small body
            avg_body = body.rolling(20).mean()
            doji = body < avg_body * 0.1
            bullish = doji & (c > o)
            bearish = doji & (c < o)

        elif pattern == "hammer":
            # Hammer: long lower wick
            lower_wick = pd.concat([o, c], axis=1).min(axis=1) - low_s
            upper_wick = h - pd.concat([o, c], axis=1).max(axis=1)
            bullish = (lower_wick > body * 2) & (upper_wick < body * 0.5)
            bearish = (upper_wick > body * 2) & (lower_wick < body * 0.5)

        else:
            bullish = pd.Series([False] * n, index=ohlcv.index)
            bearish = pd.Series([False] * n, index=ohlcv.index)

        return {
            "buy": bullish.fillna(False),
            "sell": bearish.fillna(False),
        }

    # ========== Default: Unknown filter ==========
    else:
        logger.warning(f"Unknown filter type: {filter_type}")
        return {
            "buy": pd.Series([False] * n, index=ohlcv.index),
            "sell": pd.Series([False] * n, index=ohlcv.index),
        }


# ---------------------------------------------------------------------------
# execute_signal_block — signal routing blocks (long_entry, etc.)
# ---------------------------------------------------------------------------


def execute_signal_block(
    signal_type: str,
    params: dict[str, Any],
    inputs: dict[str, pd.Series],
) -> dict[str, pd.Series]:
    """Execute signal blocks (long_entry, short_entry, long_exit, short_exit, signal).

    Signal blocks receive a boolean condition and output it as the appropriate
    signal type. They act as the terminal nodes that define entry/exit signals.

    Supported signal types:
        - long_entry: Generate long entry signal
        - short_entry: Generate short entry signal
        - long_exit: Generate long exit signal
        - short_exit: Generate short exit signal
        - signal: Universal signal block that receives signals on multiple ports
                  (entry_long, exit_long, entry_short, exit_short)

    Args:
        signal_type: Type of signal block
        params: Block parameters
        inputs: Input values from connected blocks

    Returns:
        Dictionary with signal output
    """
    result: dict[str, pd.Series] = {}

    # Handle universal "signal" block type that receives multiple signal inputs
    if signal_type == "signal":
        # Universal signal block - each input port maps directly to output
        n = len(next(iter(inputs.values()))) if inputs else 100

        # Check for entry_long input
        if "entry_long" in inputs:
            sig = inputs["entry_long"]
            if sig.dtype != bool:
                sig = sig.astype(bool)
            result["entry_long"] = sig

        # Check for exit_long input
        if "exit_long" in inputs:
            sig = inputs["exit_long"]
            if sig.dtype != bool:
                sig = sig.astype(bool)
            result["exit_long"] = sig

        # Check for entry_short input
        if "entry_short" in inputs:
            sig = inputs["entry_short"]
            if sig.dtype != bool:
                sig = sig.astype(bool)
            result["entry_short"] = sig

        # Check for exit_short input
        if "exit_short" in inputs:
            sig = inputs["exit_short"]
            if sig.dtype != bool:
                sig = sig.astype(bool)
            result["exit_short"] = sig

        # Also support generic "signal" or "condition" input for backwards compat
        for key in ["signal", "condition", "result", "input", "output"]:
            if key in inputs and key not in ["entry_long", "exit_long", "entry_short", "exit_short"]:
                sig = inputs[key]
                if sig.dtype != bool:
                    sig = sig.astype(bool)
                result["signal"] = sig
                break

        # If no outputs generated, return empty signals
        if not result:
            empty = pd.Series([False] * n)
            result = {"signal": empty}

        return result

    # Handle specific signal types (long_entry, short_entry, etc.)
    # Get input signal (from condition, result, or signal port)
    input_signal = None
    for key in ["condition", "result", "signal", "input", "output"]:
        if key in inputs:
            input_signal = inputs[key]
            break

    if input_signal is None:
        # No input - return empty signal
        n = len(next(iter(inputs.values()))) if inputs else 100
        return {"signal": pd.Series([False] * n)}

    # Ensure it's a boolean series
    if input_signal.dtype != bool:
        input_signal = input_signal.astype(bool)

    result = {"signal": input_signal}

    if signal_type in ["long_entry", "entry_long", "buy_signal"]:
        result["entry_long"] = input_signal
    elif signal_type in ["short_entry", "entry_short", "sell_signal"]:
        result["entry_short"] = input_signal
    elif signal_type in ["long_exit", "exit_long", "close_long"]:
        result["exit_long"] = input_signal
    elif signal_type in ["short_exit", "exit_short", "close_short"]:
        result["exit_short"] = input_signal
    else:
        logger.warning(f"Unknown signal type: {signal_type}")

    return result


# ---------------------------------------------------------------------------
# execute_action — action blocks (buy, sell, trailing_stop, ...)
# ---------------------------------------------------------------------------


def execute_action(
    action_type: str,
    params: dict[str, Any],
    inputs: dict[str, pd.Series],
) -> dict[str, pd.Series]:
    """Execute action blocks (buy, sell, close, etc.).

    Action blocks generate entry/exit signals based on input conditions.

    Supported action types:
        - buy, buy_market, buy_limit: Long entry
        - sell, sell_market, sell_limit: Short entry
        - close_long, close_short, close_all: Exit signals
        - stop_loss, take_profit: Exit with price levels
        - trailing_stop: Exit with trailing

    Args:
        action_type: Block type string.
        params: Block parameter dict.
        inputs: Upstream Series keyed by port name.

    Returns:
        Dict of output Series.
    """
    # Get input signal (from condition or filter block)
    input_signal = None
    for key in ["signal", "condition", "output"]:
        if key in inputs:
            input_signal = inputs[key]
            break

    if input_signal is None:
        # No input - action doesn't trigger
        n = len(next(iter(inputs.values()))) if inputs else 0
        empty_signal = pd.Series([False] * n)
        return {"signal": empty_signal}

    # Pass through signal based on action type
    result: dict[str, pd.Series] = {}

    if action_type in ["buy", "buy_market", "buy_limit"]:
        result["entry_long"] = input_signal
        result["signal"] = input_signal

    elif action_type in ["sell", "sell_market", "sell_limit"]:
        result["entry_short"] = input_signal
        result["signal"] = input_signal

    elif action_type == "close_long":
        result["exit_long"] = input_signal
        result["signal"] = input_signal

    elif action_type == "close_short":
        result["exit_short"] = input_signal
        result["signal"] = input_signal

    elif action_type == "close_all":
        result["exit_long"] = input_signal
        result["exit_short"] = input_signal
        result["signal"] = input_signal

    elif action_type == "stop_loss":
        percent = params.get("percent", 2.0)
        result["exit"] = input_signal
        result["signal"] = input_signal
        result["stop_loss_percent"] = percent

    elif action_type == "take_profit":
        percent = params.get("percent", 3.0)
        result["exit"] = input_signal
        result["signal"] = input_signal
        result["take_profit_percent"] = percent

    elif action_type == "trailing_stop":
        percent = params.get("percent", 1.5)
        activation = params.get("activation", 1.0)
        result["exit"] = input_signal
        result["signal"] = input_signal
        result["trailing_percent"] = percent
        result["trailing_activation"] = activation

    elif action_type == "atr_stop":
        period = params.get("period", 14)
        multiplier = params.get("multiplier", 2.0)
        result["exit"] = input_signal
        result["signal"] = input_signal
        result["atr_period"] = period
        result["atr_multiplier"] = multiplier

    elif action_type == "chandelier_stop":
        period = params.get("period", 22)
        multiplier = params.get("multiplier", 3.0)
        result["exit"] = input_signal
        result["signal"] = input_signal
        result["chandelier_period"] = period
        result["chandelier_multiplier"] = multiplier

    elif action_type == "break_even":
        trigger = params.get("trigger_percent", 1.0)
        offset = params.get("offset", 0.0)
        result["signal"] = input_signal
        result["breakeven_trigger"] = trigger
        result["breakeven_offset"] = offset

    elif action_type == "profit_lock":
        trigger = params.get("trigger_percent", 2.0)
        lock = params.get("lock_percent", 1.0)
        result["signal"] = input_signal
        result["profit_lock_trigger"] = trigger
        result["profit_lock_amount"] = lock

    elif action_type == "scale_out":
        percent = params.get("close_percent", 50.0)
        at_profit = params.get("at_profit", 1.0)
        result["exit"] = input_signal
        result["signal"] = input_signal
        result["scale_out_percent"] = percent
        result["scale_out_at_profit"] = at_profit

    elif action_type == "multi_tp":
        tp1 = params.get("tp1_percent", 1.0)
        tp1_close = params.get("tp1_close", 30.0)
        tp2 = params.get("tp2_percent", 2.0)
        tp2_close = params.get("tp2_close", 30.0)
        tp3 = params.get("tp3_percent", 3.0)
        tp3_close = params.get("tp3_close", 40.0)
        result["signal"] = input_signal
        result["multi_tp_levels"] = [
            {"percent": tp1, "close": tp1_close},
            {"percent": tp2, "close": tp2_close},
            {"percent": tp3, "close": tp3_close},
        ]

    elif action_type == "limit_entry":
        price = params.get("price", 0)
        offset = params.get("offset_percent", 0)
        result["entry_long"] = input_signal
        result["signal"] = input_signal
        result["limit_price"] = price
        result["limit_offset"] = offset
        result["order_type"] = "limit"

    elif action_type == "stop_entry":
        price = params.get("price", 0)
        offset = params.get("offset_percent", 0)
        result["entry_long"] = input_signal
        result["signal"] = input_signal
        result["stop_price"] = price
        result["stop_offset"] = offset
        result["order_type"] = "stop"

    elif action_type == "close":
        result["exit_long"] = input_signal
        result["exit_short"] = input_signal
        result["signal"] = input_signal

    else:
        result["signal"] = input_signal

    return result


# ---------------------------------------------------------------------------
# execute_exit — exit condition blocks (static_sltp, atr_exit, ...)
# ---------------------------------------------------------------------------


def execute_exit(
    exit_type: str,
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    inputs: dict[str, pd.Series],
) -> dict[str, pd.Series]:
    """Execute exit condition blocks.

    Exit blocks generate exit signals based on price conditions or indicators.

    Supported exit types:
        - static_sltp: Unified fixed % SL/TP with breakeven
        - tp_percent, sl_percent: Legacy fixed % take profit / stop loss
        - trailing_stop_exit: Trailing stop
        - atr_stop, atr_tp: ATR-based exits
        - time_exit: Exit after N bars
        - breakeven_exit: Move stop to breakeven
        - chandelier_exit: Chandelier exit

    Args:
        exit_type: Block type string.
        params: Block parameter dict.
        ohlcv: OHLCV DataFrame.
        inputs: Upstream Series keyed by port name.

    Returns:
        Dict of output Series.
    """
    n = len(ohlcv)
    result: dict[str, pd.Series] = {}

    if exit_type == "static_sltp":
        # Unified static SL/TP — config-only block, engine handles execution
        result["exit"] = pd.Series([False] * n, index=ohlcv.index)
        # Pass SL/TP values for engine config extraction
        result["stop_loss_percent"] = params.get("stop_loss_percent", 1.5)
        result["take_profit_percent"] = params.get("take_profit_percent", 1.5)
        result["close_only_in_profit"] = params.get("close_only_in_profit", False)
        result["activate_breakeven"] = params.get("activate_breakeven", False)
        result["breakeven_activation_percent"] = params.get("breakeven_activation_percent", 0.5)
        result["new_breakeven_sl_percent"] = params.get("new_breakeven_sl_percent", 0.1)

    elif exit_type in ("tp_percent", "sl_percent"):
        # Legacy blocks — kept for backward compatibility
        result["exit"] = pd.Series([False] * n, index=ohlcv.index)

    elif exit_type == "trailing_stop_exit":
        # Trailing stop is config-only — engine handles bar-by-bar execution.
        result["exit"] = pd.Series([False] * n, index=ohlcv.index)
        result["trailing_activation_percent"] = params.get("activation_percent", 1.0)
        result["trailing_percent"] = params.get("trailing_percent", 0.5)
        result["trail_type"] = params.get("trail_type", "percent")

    elif exit_type == "atr_stop":
        # ATR-based stop loss — wire as use_atr_sl so engine picks it up via extra_data
        period = max(1, min(150, int(params.get("period", 14))))
        multiplier = max(0.1, min(4.0, float(params.get("multiplier", 2.0))))
        smoothing = params.get("smoothing", "RMA")
        if smoothing not in ("WMA", "RMA", "SMA", "EMA"):
            smoothing = "RMA"
        on_wicks = params.get("on_wicks", False)
        atr = pd.Series(
            calculate_atr_smoothed(
                ohlcv["high"].values,
                ohlcv["low"].values,
                ohlcv["close"].values,
                period=period,
                method=smoothing,
            ),
            index=ohlcv.index,
        )
        result["exit"] = pd.Series([False] * n, index=ohlcv.index)
        result["use_atr_sl"] = True
        result["atr_sl"] = atr
        result["atr_sl_mult"] = multiplier
        result["atr_sl_on_wicks"] = on_wicks

    elif exit_type == "time_exit":
        bars = params.get("bars", 10)
        result["exit"] = pd.Series([False] * n, index=ohlcv.index)
        result["max_bars"] = pd.Series([bars] * n, index=ohlcv.index)

    elif exit_type in ("breakeven_exit", "break_even_exit"):
        trigger_pct = params.get("trigger_percent", 1.0)
        result["exit"] = pd.Series([False] * n, index=ohlcv.index)
        result["breakeven_trigger"] = trigger_pct

    elif exit_type == "chandelier_exit":
        period = params.get("period", 22)
        multiplier = params.get("multiplier", 3.0)
        atr = pd.Series(
            calculate_atr(ohlcv["high"].values, ohlcv["low"].values, ohlcv["close"].values, period),
            index=ohlcv.index,
        )
        high_n = ohlcv["high"].rolling(period).max()
        low_n = ohlcv["low"].rolling(period).min()

        # Long exit: close below highest high - ATR*mult
        long_exit_level = high_n - atr * multiplier
        # Short exit: close above lowest low + ATR*mult
        short_exit_level = low_n + atr * multiplier

        result["exit_long"] = ohlcv["close"] < long_exit_level
        result["exit_short"] = ohlcv["close"] > short_exit_level
        result["exit"] = result["exit_long"] | result["exit_short"]

    elif exit_type == "atr_exit":
        # ATR-based TP/SL exit with separate smoothing methods and periods
        use_atr_sl = params.get("use_atr_sl", False)
        use_atr_tp = params.get("use_atr_tp", False)

        high_arr = ohlcv["high"].values
        low_arr = ohlcv["low"].values
        close_arr = ohlcv["close"].values

        result["exit"] = pd.Series([False] * n, index=ohlcv.index)
        result["use_atr_sl"] = use_atr_sl
        result["use_atr_tp"] = use_atr_tp

        if use_atr_sl:
            sl_period = max(1, min(150, int(params.get("atr_sl_period", 150))))
            sl_smoothing = params.get("atr_sl_smoothing", "WMA")
            if sl_smoothing not in ("WMA", "RMA", "SMA", "EMA"):
                sl_smoothing = "RMA"
            sl_mult = max(0.1, min(4.0, float(params.get("atr_sl_multiplier", 4.0))))
            sl_on_wicks = params.get("atr_sl_on_wicks", False)
            atr_sl = pd.Series(
                calculate_atr_smoothed(high_arr, low_arr, close_arr, period=sl_period, method=sl_smoothing),
                index=ohlcv.index,
            )
            result["atr_sl"] = atr_sl
            result["atr_sl_mult"] = sl_mult
            result["atr_sl_on_wicks"] = sl_on_wicks

        if use_atr_tp:
            tp_period = max(1, min(150, int(params.get("atr_tp_period", 150))))
            tp_smoothing = params.get("atr_tp_smoothing", "WMA")
            if tp_smoothing not in ("WMA", "RMA", "SMA", "EMA"):
                tp_smoothing = "RMA"
            tp_mult = max(0.1, min(4.0, float(params.get("atr_tp_multiplier", 4.0))))
            tp_on_wicks = params.get("atr_tp_on_wicks", False)
            atr_tp = pd.Series(
                calculate_atr_smoothed(high_arr, low_arr, close_arr, period=tp_period, method=tp_smoothing),
                index=ohlcv.index,
            )
            result["atr_tp"] = atr_tp
            result["atr_tp_mult"] = tp_mult
            result["atr_tp_on_wicks"] = tp_on_wicks

    elif exit_type == "session_exit":
        exit_hour = params.get("exit_hour", 21)
        idx = ohlcv.index
        hours = idx.hour if hasattr(idx, "hour") else pd.to_datetime(idx).hour
        at_session_end = hours == exit_hour
        result["exit"] = pd.Series(at_session_end, index=ohlcv.index)

    elif exit_type == "signal_exit":
        result["exit"] = pd.Series([False] * n, index=ohlcv.index)
        result["signal_exit_mode"] = True

    elif exit_type == "indicator_exit":
        indicator = params.get("indicator", "rsi")
        threshold = params.get("threshold", 50)
        mode = params.get("mode", "above")  # above, below, cross_above, cross_below
        period = _clamp_period(params.get("period", 14))

        close = ohlcv["close"].values
        high = ohlcv["high"].values
        low = ohlcv["low"].values
        vol = ohlcv["volume"].values if "volume" in ohlcv.columns else np.ones(len(close))

        if indicator == "rsi":
            ind_val = pd.Series(calculate_rsi(close, period), index=ohlcv.index)
        elif indicator == "cci":
            ind_val = pd.Series(calculate_cci(high, low, close, period), index=ohlcv.index)
        elif indicator == "mfi":
            ind_val = pd.Series(calculate_mfi(high, low, close, vol, period), index=ohlcv.index)
        elif indicator == "roc":
            ind_val = pd.Series(calculate_roc(close, period), index=ohlcv.index)
        elif indicator == "obv":
            ind_val = pd.Series(calculate_obv(close, vol), index=ohlcv.index)
        elif indicator == "macd":
            _m = calculate_macd(close, 12, 26, 9)
            ind_val = pd.Series(_m[2], index=ohlcv.index)  # histogram
        elif indicator == "stochastic":
            _s = calculate_stochastic(high, low, close, period, 3)
            ind_val = pd.Series(_s[0], index=ohlcv.index)  # %K
        else:
            logger.warning("indicator_exit: unknown indicator '{}', falling back to RSI", indicator)
            ind_val = pd.Series(calculate_rsi(close, period), index=ohlcv.index)

        if mode == "above":
            exit_signal = ind_val > threshold
        elif mode == "below":
            exit_signal = ind_val < threshold
        elif mode == "cross_above":
            exit_signal = (ind_val > threshold) & (ind_val.shift(1) <= threshold)
        else:  # cross_below
            exit_signal = (ind_val < threshold) & (ind_val.shift(1) >= threshold)

        result["exit"] = exit_signal.fillna(False)

    elif exit_type == "partial_close":
        targets = params.get("targets", [{"profit": 1.0, "close_pct": 50}])
        result["exit"] = pd.Series([False] * n, index=ohlcv.index)
        result["partial_targets"] = targets

    elif exit_type == "multi_tp_exit":
        tp1 = params.get("tp1_percent", 1.0)
        tp1_alloc = params.get("tp1_allocation", 30)
        tp2 = params.get("tp2_percent", 2.0)
        tp2_alloc = params.get("tp2_allocation", 30)
        tp3 = params.get("tp3_percent", 3.0)
        tp3_alloc = params.get("tp3_allocation", 40)

        total_alloc = tp1_alloc + tp2_alloc + tp3_alloc
        if not (99.0 <= total_alloc <= 101.0):
            logger.warning("Multi-TP allocations sum to {}%, expected 100%", total_alloc)

        if tp1 >= tp2 or tp2 >= tp3:
            logger.warning(
                "Multi-TP levels not ascending: TP1={}% TP2={}% TP3={}% — execution order may be incorrect",
                tp1,
                tp2,
                tp3,
            )

        result["exit"] = pd.Series([False] * n, index=ohlcv.index)
        result["multi_tp_config"] = [
            {"percent": tp1, "allocation": tp1_alloc},
            {"percent": tp2, "allocation": tp2_alloc},
            {"percent": tp3, "allocation": tp3_alloc},
        ]

    else:
        result["exit"] = pd.Series([False] * n, index=ohlcv.index)

    return result


# ---------------------------------------------------------------------------
# execute_position_sizing — position sizing config blocks
# ---------------------------------------------------------------------------


def execute_position_sizing(sizing_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """Execute position sizing blocks.

    Sizing blocks are config-only and return sizing parameters.

    Supported sizing types:
        - fixed_size: Fixed position size
        - percent_equity: % of equity
        - risk_based: Risk % per trade
        - kelly_criterion: Kelly formula
        - volatility_sized: ATR-based sizing

    Args:
        sizing_type: Block type string.
        params: Block parameter dict.

    Returns:
        Dict of sizing config values.
    """
    result: dict[str, Any] = {}

    if sizing_type == "fixed_size":
        result["size"] = params.get("size", 1.0)
        result["sizing_mode"] = "fixed"

    elif sizing_type == "percent_equity":
        result["equity_percent"] = params.get("percent", 10.0)
        result["sizing_mode"] = "percent"

    elif sizing_type == "risk_based":
        result["risk_percent"] = params.get("risk_percent", 1.0)
        result["sizing_mode"] = "risk"

    elif sizing_type == "kelly_criterion":
        result["kelly_fraction"] = params.get("fraction", 0.5)
        result["sizing_mode"] = "kelly"

    elif sizing_type == "volatility_sized":
        result["atr_period"] = params.get("period", 14)
        result["target_risk"] = params.get("target_risk", 1.0)
        result["sizing_mode"] = "volatility"

    return result


# ---------------------------------------------------------------------------
# execute_time_filter — time-based filter blocks
# ---------------------------------------------------------------------------


def execute_time_filter(time_type: str, params: dict[str, Any], ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
    """Execute time-based filter blocks.

    Time filters return boolean series based on time conditions.

    Supported time filter types:
        - trading_hours: Filter by time of day
        - trading_days: Filter by day of week
        - session_filter: Trading sessions (Asia, London, NY)
        - date_range: Filter by date range
        - exclude_news: Avoid news times

    Args:
        time_type: Block type string.
        params: Block parameter dict.
        ohlcv: OHLCV DataFrame.

    Returns:
        Dict with ``"allow"`` key containing a boolean Series.
    """
    n = len(ohlcv)
    idx = ohlcv.index
    result: dict[str, pd.Series] = {}

    if time_type == "trading_hours":
        start_hour = params.get("start_hour", 9)
        end_hour = params.get("end_hour", 17)
        hours = idx.hour if hasattr(idx, "hour") else pd.to_datetime(idx).hour

        result["allow"] = pd.Series((hours >= start_hour) & (hours < end_hour), index=idx)

    elif time_type == "trading_days":
        allowed_days = params.get("days", [0, 1, 2, 3, 4])  # Mon-Fri
        dow = idx.dayofweek if hasattr(idx, "dayofweek") else pd.to_datetime(idx).dayofweek

        result["allow"] = pd.Series([d in allowed_days for d in dow], index=idx)

    elif time_type == "session_filter":
        session = params.get("session", "all")
        hours = idx.hour if hasattr(idx, "hour") else pd.to_datetime(idx).hour

        if session == "asia":
            result["allow"] = pd.Series((hours >= 0) & (hours < 9), index=idx)
        elif session == "london":
            result["allow"] = pd.Series((hours >= 8) & (hours < 17), index=idx)
        elif session == "ny":
            result["allow"] = pd.Series((hours >= 13) & (hours < 22), index=idx)
        else:
            result["allow"] = pd.Series([True] * n, index=idx)

    elif time_type == "date_range":
        start_date = params.get("start_date")
        end_date = params.get("end_date")

        dates = pd.to_datetime(idx)
        allow = pd.Series([True] * n, index=idx)

        if start_date:
            allow = allow & (dates >= pd.to_datetime(start_date))
        if end_date:
            allow = allow & (dates <= pd.to_datetime(end_date))

        result["allow"] = allow

    else:
        result["allow"] = pd.Series([True] * n, index=idx)

    return result


# ---------------------------------------------------------------------------
# execute_price_action — candlestick pattern detection blocks
# ---------------------------------------------------------------------------


def execute_price_action(pattern_type: str, params: dict[str, Any], ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
    """Execute price action pattern detection blocks.

    Returns signals when specific candlestick patterns are detected.

    Supported pattern types:
        - engulfing: Bullish/bearish engulfing
        - hammer: Hammer/hanging man
        - doji: Doji patterns
        - pin_bar: Pin bar / rejection
        - inside_bar: Inside bar
        - outside_bar: Outside bar
        - three_white_soldiers: 3 white soldiers / black crows
        - morning_star: Morning/evening star

    Args:
        pattern_type: Block type string.
        params: Block parameter dict.
        ohlcv: OHLCV DataFrame.

    Returns:
        Dict of signal Series (``"bullish"``, ``"bearish"``, ``"signal"``, etc.).
    """
    n = len(ohlcv)
    idx = ohlcv.index
    result: dict[str, pd.Series] = {}

    o = ohlcv["open"]
    h = ohlcv["high"]
    low = ohlcv["low"]
    c = ohlcv["close"]
    body = abs(c - o)
    upper_wick = h - pd.concat([o, c], axis=1).max(axis=1)
    lower_wick = pd.concat([o, c], axis=1).min(axis=1) - low

    if pattern_type == "engulfing":
        # Bullish engulfing: prev red, current green, current body > prev body
        prev_red = o.shift(1) > c.shift(1)
        curr_green = c > o
        engulfs = (c > o.shift(1)) & (o < c.shift(1))
        bullish = prev_red & curr_green & engulfs

        prev_green = c.shift(1) > o.shift(1)
        curr_red = o > c
        engulfs_bear = (o > c.shift(1)) & (c < o.shift(1))
        bearish = prev_green & curr_red & engulfs_bear

        result["bullish"] = bullish.fillna(False)
        result["bearish"] = bearish.fillna(False)
        result["signal"] = bullish.fillna(False)

    elif pattern_type == "hammer":
        min_wick_ratio = params.get("min_wick_ratio", 2.0)
        max_upper_ratio = params.get("max_upper_ratio", 0.3)

        hammer = (lower_wick > body * min_wick_ratio) & (upper_wick < body * max_upper_ratio)
        hanging = (upper_wick > body * min_wick_ratio) & (lower_wick < body * max_upper_ratio)

        result["hammer"] = hammer.fillna(False)
        result["hanging_man"] = hanging.fillna(False)
        result["signal"] = hammer.fillna(False)

    elif pattern_type == "doji":
        threshold = params.get("body_threshold", 0.1)
        avg_range = (h - low).rolling(20).mean()

        doji = body < avg_range * threshold
        result["doji"] = doji.fillna(False)
        result["signal"] = doji.fillna(False)

    elif pattern_type == "pin_bar":
        min_wick = params.get("min_wick_ratio", 2.0)

        bull_pin = (lower_wick > body * min_wick) & (lower_wick > upper_wick * 2)
        bear_pin = (upper_wick > body * min_wick) & (upper_wick > lower_wick * 2)

        result["bullish"] = bull_pin.fillna(False)
        result["bearish"] = bear_pin.fillna(False)
        result["signal"] = bull_pin.fillna(False)

    elif pattern_type == "inside_bar":
        inside = (h <= h.shift(1)) & (low >= low.shift(1))
        result["inside"] = inside.fillna(False)
        result["signal"] = inside.fillna(False)

    elif pattern_type == "outside_bar":
        outside = (h > h.shift(1)) & (low < low.shift(1))
        result["outside"] = outside.fillna(False)
        result["signal"] = outside.fillna(False)

    elif pattern_type == "three_white_soldiers":
        green = c > o
        three_green = green & green.shift(1) & green.shift(2)
        higher_close = (c > c.shift(1)) & (c.shift(1) > c.shift(2))
        soldiers = three_green & higher_close

        red = o > c
        three_red = red & red.shift(1) & red.shift(2)
        lower_close = (c < c.shift(1)) & (c.shift(1) < c.shift(2))
        crows = three_red & lower_close

        result["soldiers"] = soldiers.fillna(False)
        result["crows"] = crows.fillna(False)
        result["signal"] = soldiers.fillna(False)

    elif pattern_type == "hammer_hangman":
        min_wick_ratio = params.get("min_wick_ratio", 2.0)
        max_upper_ratio = params.get("max_upper_ratio", 0.3)

        hammer = (lower_wick > body * min_wick_ratio) & (upper_wick < body * max_upper_ratio)
        hanging = (upper_wick > body * min_wick_ratio) & (lower_wick < body * max_upper_ratio)

        result["bullish"] = hammer.fillna(False)
        result["bearish"] = hanging.fillna(False)
        result["signal"] = hammer.fillna(False)

    elif pattern_type == "doji_patterns":
        threshold = params.get("body_threshold", 0.1)
        avg_range = (h - low).rolling(20).mean()

        small_body = body < avg_range * threshold
        dragonfly = small_body & (lower_wick > body * 3) & (upper_wick < body)
        gravestone = small_body & (upper_wick > body * 3) & (lower_wick < body)

        result["dragonfly"] = dragonfly.fillna(False)
        result["gravestone"] = gravestone.fillna(False)
        result["doji"] = small_body.fillna(False)
        result["signal"] = dragonfly.fillna(False)

    elif pattern_type == "morning_star":
        # Morning star: big red, small body, big green
        big_red = (o.shift(2) > c.shift(2)) & (body.shift(2) > body.shift(2).rolling(10).mean())
        small_body_mid = body.shift(1) < body.shift(1).rolling(10).mean() * 0.5
        big_green = (c > o) & (body > body.rolling(10).mean())
        morning = big_red & small_body_mid & big_green

        # Evening star
        big_green_first = (c.shift(2) > o.shift(2)) & (body.shift(2) > body.shift(2).rolling(10).mean())
        evening = big_green_first & small_body_mid & (o > c) & (body > body.rolling(10).mean())

        result["bullish"] = morning.fillna(False)
        result["bearish"] = evening.fillna(False)
        result["signal"] = morning.fillna(False)

    elif pattern_type == "piercing_dark_cloud":
        # Piercing line (bullish) and dark cloud cover (bearish)
        prev_red = o.shift(1) > c.shift(1)
        curr_green = c > o
        gap_down = o < c.shift(1)
        closes_above_mid = c > (o.shift(1) + c.shift(1)) / 2
        piercing = prev_red & curr_green & gap_down & closes_above_mid

        prev_green = c.shift(1) > o.shift(1)
        curr_red_dcc = o > c
        gap_up = o > c.shift(1)
        closes_below_mid = c < (o.shift(1) + c.shift(1)) / 2
        dark_cloud = prev_green & curr_red_dcc & gap_up & closes_below_mid

        result["bullish"] = piercing.fillna(False)
        result["bearish"] = dark_cloud.fillna(False)
        result["signal"] = piercing.fillna(False)

    elif pattern_type == "harami":
        big_red = (o.shift(1) > c.shift(1)) & (body.shift(1) > body.shift(1).rolling(10).mean())
        small_green = (c > o) & (body < body.shift(1) * 0.5)
        inside_prev = (o > c.shift(1)) & (c < o.shift(1))
        bullish_harami = big_red & small_green & inside_prev

        big_green = (c.shift(1) > o.shift(1)) & (body.shift(1) > body.shift(1).rolling(10).mean())
        small_red = (o > c) & (body < body.shift(1) * 0.5)
        inside_prev_bear = (o < c.shift(1)) & (c > o.shift(1))
        bearish_harami = big_green & small_red & inside_prev_bear

        result["bullish"] = bullish_harami.fillna(False)
        result["bearish"] = bearish_harami.fillna(False)
        result["signal"] = bullish_harami.fillna(False)

    else:
        result["signal"] = pd.Series([False] * n, index=idx)

    return result


# ---------------------------------------------------------------------------
# execute_divergence — price/indicator divergence detection
# ---------------------------------------------------------------------------


def execute_divergence(div_type: str, params: dict[str, Any], ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
    """Execute unified divergence detection block.

    Detects divergences between price and one or more indicators.
    Supports RSI, Stochastic, Momentum (ROC), CMF, OBV, MFI.

    Divergence logic:
        - Bullish divergence: price makes lower low, indicator makes higher low
        - Bearish divergence: price makes higher high, indicator makes lower high

    Pivot detection uses pivot_interval to find swing highs/lows.

    Note: The first and last ``pivot_interval`` bars of the data are excluded from
    pivot detection (boundary effect). For default pivot_interval=9, this means
    the first 9 and last 9 bars will never generate divergence signals.

    Args:
        div_type: Block type string.
        params: Block parameter dict.
        ohlcv: OHLCV DataFrame.

    Returns:
        Dict with ``"long"``, ``"short"``, ``"bullish"``, ``"bearish"``, ``"signal"`` keys.
    """
    n = len(ohlcv)
    idx = ohlcv.index

    close = ohlcv["close"].values.astype(float)
    high = ohlcv["high"].values.astype(float)
    low = ohlcv["low"].values.astype(float)
    volume = ohlcv["volume"].values.astype(float)

    pivot_interval = int(_param(params, 9, "pivot_interval"))
    act_without_confirmation = bool(_param(params, False, "act_without_confirmation"))
    activate_memory = bool(_param(params, False, "activate_diver_signal_memory"))
    memory_bars = int(_param(params, 5, "keep_diver_signal_memory_bars"))

    # Collect all enabled indicator series
    indicator_series: list[np.ndarray] = []

    if _param(params, False, "use_divergence_rsi"):
        rsi_period = int(_param(params, 14, "rsi_period"))
        indicator_series.append(calculate_rsi(close, rsi_period))

    if _param(params, False, "use_divergence_stochastic"):
        stoch_length = int(_param(params, 14, "stoch_length"))
        stoch_k, _ = calculate_stochastic(high, low, close, k_period=stoch_length)
        indicator_series.append(stoch_k)

    if _param(params, False, "use_divergence_momentum"):
        momentum_length = int(_param(params, 10, "momentum_length"))
        indicator_series.append(calculate_roc(close, momentum_length))

    if _param(params, False, "use_divergence_cmf"):
        cmf_period = int(_param(params, 21, "cmf_period"))
        indicator_series.append(calculate_cmf(high, low, close, volume, cmf_period))

    if _param(params, False, "use_obv"):
        indicator_series.append(calculate_obv(close, volume))

    if _param(params, False, "use_mfi"):
        mfi_length = int(_param(params, 14, "mfi_length"))
        indicator_series.append(calculate_mfi(high, low, close, volume, mfi_length))

    # If no indicator enabled — return empty signals
    if not indicator_series:
        return {
            "signal": pd.Series([False] * n, index=idx),
            "bullish": pd.Series([False] * n, index=idx),
            "bearish": pd.Series([False] * n, index=idx),
        }

    # Detect pivot highs and lows using pivot_interval
    pivot_highs = np.full(n, np.nan)
    pivot_lows = np.full(n, np.nan)
    for i in range(pivot_interval, n - pivot_interval):
        window_high = high[i - pivot_interval : i + pivot_interval + 1]
        if high[i] >= np.max(window_high):
            pivot_highs[i] = high[i]
        window_low = low[i - pivot_interval : i + pivot_interval + 1]
        if low[i] <= np.min(window_low):
            pivot_lows[i] = low[i]

    # For each indicator, detect divergence
    bullish_raw = np.zeros(n, dtype=bool)
    bearish_raw = np.zeros(n, dtype=bool)

    for ind_values in indicator_series:
        ind_pivot_highs = np.full(n, np.nan)
        ind_pivot_lows = np.full(n, np.nan)
        for i in range(pivot_interval, n - pivot_interval):
            if not np.isnan(pivot_highs[i]) and not np.isnan(ind_values[i]):
                ind_pivot_highs[i] = ind_values[i]
            if not np.isnan(pivot_lows[i]) and not np.isnan(ind_values[i]):
                ind_pivot_lows[i] = ind_values[i]

        last_pivot_high_idx = -1
        last_pivot_low_idx = -1

        for i in range(pivot_interval, n):
            if not np.isnan(pivot_highs[i]) and not np.isnan(ind_pivot_highs[i]):
                if (
                    last_pivot_high_idx >= 0
                    and pivot_highs[i] > pivot_highs[last_pivot_high_idx]
                    and ind_pivot_highs[i] < ind_pivot_highs[last_pivot_high_idx]
                ):
                    # Price makes higher high, indicator makes lower high => bearish
                    signal_bar = min(i + pivot_interval, n - 1)
                    bearish_raw[signal_bar] = True
                last_pivot_high_idx = i

            if not np.isnan(pivot_lows[i]) and not np.isnan(ind_pivot_lows[i]):
                if (
                    last_pivot_low_idx >= 0
                    and pivot_lows[i] < pivot_lows[last_pivot_low_idx]
                    and ind_pivot_lows[i] > ind_pivot_lows[last_pivot_low_idx]
                ):
                    # Price makes lower low, indicator makes higher low => bullish
                    signal_bar = min(i + pivot_interval, n - 1)
                    bullish_raw[signal_bar] = True
                last_pivot_low_idx = i

    # Apply confirmation filter if act_without_confirmation is False
    if not act_without_confirmation:
        bullish_confirmed = np.zeros(n, dtype=bool)
        bearish_confirmed = np.zeros(n, dtype=bool)
        for i in range(1, n):
            if bullish_raw[i] and close[i] > close[i - 1]:
                bullish_confirmed[i] = True
            if bearish_raw[i] and close[i] < close[i - 1]:
                bearish_confirmed[i] = True
        bullish = bullish_confirmed
        bearish = bearish_confirmed
    else:
        bullish = bullish_raw
        bearish = bearish_raw

    # Apply signal memory: if enabled, signals persist for N bars (vectorized)
    if activate_memory and memory_bars > 1:
        bullish_s = pd.Series(bullish, index=idx)
        bearish_s = pd.Series(bearish, index=idx)
        bullish = bullish_s.rolling(window=memory_bars, min_periods=1).max().fillna(0).astype(bool).values
        bearish = bearish_s.rolling(window=memory_bars, min_periods=1).max().fillna(0).astype(bool).values

    signal = bullish | bearish

    # Return with port IDs matching frontend: "long" (bullish) and "short" (bearish)
    return {
        "signal": pd.Series(signal, index=idx),
        "long": pd.Series(bullish, index=idx),
        "short": pd.Series(bearish, index=idx),
        # Keep aliases for backward compatibility with tests/API consumers
        "bullish": pd.Series(bullish, index=idx),
        "bearish": pd.Series(bearish, index=idx),
    }


# ---------------------------------------------------------------------------
# execute_close_condition — close-condition blocks
# ---------------------------------------------------------------------------


def execute_close_condition(
    close_type: str,
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    inputs: dict[str, pd.Series],
) -> dict[str, pd.Series]:
    """Execute close condition blocks from frontend close_conditions category.

    These blocks define when to close positions based on indicators or time.

    Supported close types:
        - close_by_time: Close after N bars
        - close_channel: Close on Keltner/Bollinger band touch
        - close_ma_cross: Close on MA1/MA2 cross
        - close_rsi: Close on RSI reach/cross level
        - close_stochastic: Close on Stochastic reach/cross level
        - close_psar: Close on Parabolic SAR signal reversal

    Args:
        close_type: Block type string.
        params: Block parameter dict.
        ohlcv: OHLCV DataFrame.
        inputs: Upstream Series keyed by port name.

    Returns:
        Dict of output Series (``"exit_long"``, ``"exit_short"``, ``"exit"``, etc.).
    """
    n = len(ohlcv)
    idx = ohlcv.index
    close = ohlcv["close"]
    result: dict[str, pd.Series] = {}

    if close_type == "close_by_time":
        # Close after N bars since entry - needs position tracking
        # Bug fix: frontend stores key as "bars_since_entry", not "bars"
        bars = int(params.get("bars_since_entry", params.get("bars", 10)))
        profit_only = bool(params.get("profit_only", False))
        # Frontend stores key as "min_profit_percent" (confirmed from DB)
        min_profit = float(params.get("min_profit_percent", params.get("min_profit", 0.0)))
        # Return config, actual implementation in engine
        result["exit"] = pd.Series([False] * n, index=idx)
        result["max_bars"] = pd.Series([bars] * n, index=idx)
        if profit_only:
            result["profit_only"] = pd.Series([True] * n, index=idx)
            result["min_profit"] = pd.Series([min_profit] * n, index=idx)

    elif close_type == "close_channel":
        channel_type = params.get("channel_type", "Keltner Channel")
        band_to_close = params.get("band_to_close", "Rebound")
        close_condition = params.get("close_condition", "Wick out of band")
        keltner_length = int(params.get("keltner_length", 14))
        keltner_mult = float(params.get("keltner_mult", 1.5))
        bb_length = int(params.get("bb_length", 20))
        bb_deviation = float(params.get("bb_deviation", 2.0))

        high = ohlcv["high"]
        low = ohlcv["low"]

        if channel_type == "Keltner Channel":
            _kc_mid, kc_upper, kc_lower = calculate_keltner(
                high.values,
                low.values,
                close.values,
                keltner_length,
                keltner_length,
                keltner_mult,
            )
            upper = pd.Series(kc_upper, index=idx)
            lower = pd.Series(kc_lower, index=idx)
        else:
            # Bollinger Bands
            middle = close.rolling(bb_length).mean()
            std = close.rolling(bb_length).std()
            upper = middle + bb_deviation * std
            lower = middle - bb_deviation * std

        if close_condition == "Out-of-band closure":
            if band_to_close == "Rebound":
                exit_long = close >= upper
                exit_short = close <= lower
            else:  # Breakout
                exit_long = close <= lower
                exit_short = close >= upper
        elif close_condition == "Wick out of band":
            if band_to_close == "Rebound":
                exit_long = high >= upper
                exit_short = low <= lower
            else:
                exit_long = low <= lower
                exit_short = high >= upper
        elif close_condition == "Wick out of the band then close in":
            if band_to_close == "Rebound":
                exit_long = (high.shift(1) >= upper.shift(1)) & (close < upper)
                exit_short = (low.shift(1) <= lower.shift(1)) & (close > lower)
            else:
                exit_long = (low.shift(1) <= lower.shift(1)) & (close > lower)
                exit_short = (high.shift(1) >= upper.shift(1)) & (close < upper)
        else:
            # "Close out of the band then close in"
            if band_to_close == "Rebound":
                exit_long = (close.shift(1) >= upper.shift(1)) & (close < upper)
                exit_short = (close.shift(1) <= lower.shift(1)) & (close > lower)
            else:
                exit_long = (close.shift(1) <= lower.shift(1)) & (close > lower)
                exit_short = (close.shift(1) >= upper.shift(1)) & (close < upper)

        result["exit_long"] = exit_long.fillna(False)
        result["exit_short"] = exit_short.fillna(False)
        result["exit"] = (exit_long | exit_short).fillna(False)
        result["signal"] = result["exit"]

    elif close_type == "close_ma_cross":
        ma1_length = int(params.get("ma1_length", 10))
        ma2_length = int(params.get("ma2_length", 30))
        profit_only = params.get("profit_only", False)
        min_profit = float(params.get("min_profit_percent", 1.0))

        fast_ma = close.ewm(span=ma1_length, adjust=False).mean()
        slow_ma = close.ewm(span=ma2_length, adjust=False).mean()

        # Long exit: fast MA crosses below slow MA (bearish cross)
        exit_long = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
        # Short exit: fast MA crosses above slow MA (bullish cross)
        exit_short = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))

        result["exit_long"] = exit_long.fillna(False)
        result["exit_short"] = exit_short.fillna(False)
        result["exit"] = (exit_long | exit_short).fillna(False)
        result["signal"] = result["exit"]
        if profit_only:
            result["profit_only"] = pd.Series([True] * n, index=idx)
            result["min_profit"] = pd.Series([min_profit] * n, index=idx)

    elif close_type == "close_rsi":
        rsi_length = int(params.get("rsi_close_length", 14))
        rsi_profit_only = params.get("rsi_close_profit_only", False)
        rsi_min_profit = float(params.get("rsi_close_min_profit", 1.0))
        activate_reach = params.get("activate_rsi_reach", False)
        activate_cross = params.get("activate_rsi_cross", False)

        rsi_values = pd.Series(calculate_rsi(close.values, rsi_length), index=idx)

        exit_long = pd.Series([False] * n, index=idx)
        exit_short = pd.Series([False] * n, index=idx)

        if activate_reach:
            long_more = float(params.get("rsi_long_more", 70))
            long_less = float(params.get("rsi_long_less", 100))
            if long_more > long_less:
                logger.warning(
                    "Close RSI range inversion: long_more={} > long_less={} — swapping to prevent always-False exit",
                    long_more,
                    long_less,
                )
                long_more, long_less = long_less, long_more
            short_less = float(params.get("rsi_short_less", 30))
            short_more = float(params.get("rsi_short_more", 1))
            if short_more > short_less:
                logger.warning(
                    "Close RSI range inversion: short_more={} > short_less={} — swapping to prevent always-False exit",
                    short_more,
                    short_less,
                )
                short_more, short_less = short_less, short_more
            exit_long = exit_long | ((rsi_values >= long_more) & (rsi_values <= long_less))
            exit_short = exit_short | ((rsi_values <= short_less) & (rsi_values >= short_more))

        if activate_cross:
            cross_long_level = float(params.get("rsi_cross_long_level", 70))
            cross_short_level = float(params.get("rsi_cross_short_level", 30))
            exit_long = exit_long | ((rsi_values < cross_long_level) & (rsi_values.shift(1) >= cross_long_level))
            exit_short = exit_short | ((rsi_values > cross_short_level) & (rsi_values.shift(1) <= cross_short_level))

        result["exit_long"] = exit_long.fillna(False)
        result["exit_short"] = exit_short.fillna(False)
        result["exit"] = (exit_long | exit_short).fillna(False)
        result["signal"] = result["exit"]
        if rsi_profit_only:
            result["profit_only"] = pd.Series([True] * n, index=idx)
            result["min_profit"] = pd.Series([rsi_min_profit] * n, index=idx)

    elif close_type == "close_stochastic":
        k_length = int(params.get("stoch_close_k_length", 14))
        k_smooth = int(params.get("stoch_close_k_smoothing", 3))
        d_smooth = int(params.get("stoch_close_d_smoothing", 3))
        stoch_profit_only = params.get("stoch_close_profit_only", False)
        stoch_min_profit = float(params.get("stoch_close_min_profit", 1.0))
        activate_reach = params.get("activate_stoch_reach", False)
        activate_cross = params.get("activate_stoch_cross", False)

        high = ohlcv["high"]
        low = ohlcv["low"]
        stoch_k, _stoch_d = calculate_stochastic(high.values, low.values, close.values, k_length, k_smooth, d_smooth)
        stoch_values = pd.Series(stoch_k, index=idx)

        exit_long = pd.Series([False] * n, index=idx)
        exit_short = pd.Series([False] * n, index=idx)

        if activate_reach:
            long_more = float(params.get("stoch_long_more", 80))
            long_less = float(params.get("stoch_long_less", 100))
            if long_more > long_less:
                logger.warning(
                    "Close Stochastic range inversion: long_more={} > long_less={} — swapping to prevent always-False exit",
                    long_more,
                    long_less,
                )
                long_more, long_less = long_less, long_more
            short_less = float(params.get("stoch_short_less", 20))
            short_more = float(params.get("stoch_short_more", 1))
            if short_more > short_less:
                logger.warning(
                    "Close Stochastic range inversion: short_more={} > short_less={} — swapping to prevent always-False exit",
                    short_more,
                    short_less,
                )
                short_more, short_less = short_less, short_more
            exit_long = exit_long | ((stoch_values >= long_more) & (stoch_values <= long_less))
            exit_short = exit_short | ((stoch_values <= short_less) & (stoch_values >= short_more))

        if activate_cross:
            cross_long = float(params.get("stoch_cross_long_level", 80))
            cross_short = float(params.get("stoch_cross_short_level", 20))
            exit_long = exit_long | ((stoch_values < cross_long) & (stoch_values.shift(1) >= cross_long))
            exit_short = exit_short | ((stoch_values > cross_short) & (stoch_values.shift(1) <= cross_short))

        result["exit_long"] = exit_long.fillna(False)
        result["exit_short"] = exit_short.fillna(False)
        result["exit"] = (exit_long | exit_short).fillna(False)
        result["signal"] = result["exit"]
        if stoch_profit_only:
            result["profit_only"] = pd.Series([True] * n, index=idx)
            result["min_profit"] = pd.Series([stoch_min_profit] * n, index=idx)

    elif close_type == "close_psar":
        psar_start = float(params.get("psar_start", 0.02))
        psar_increment = float(params.get("psar_increment", 0.02))
        psar_maximum = float(params.get("psar_maximum", 0.2))
        psar_opposite = params.get("psar_opposite", False)
        psar_profit_only = params.get("psar_close_profit_only", False)
        psar_min_profit = float(params.get("psar_close_min_profit", 1.0))
        nth_bar = int(params.get("psar_close_nth_bar", 1))

        high = ohlcv["high"]
        low = ohlcv["low"]
        psar_arr, psar_trend = calculate_parabolic_sar(
            high.values, low.values, psar_start, psar_increment, psar_maximum
        )
        _psar_values = pd.Series(psar_arr, index=idx)  # kept for future overlay

        trend_series = pd.Series(psar_trend, index=idx)
        trend_change_bull = (trend_series == 1) & (trend_series.shift(1) == -1)
        trend_change_bear = (trend_series == -1) & (trend_series.shift(1) == 1)

        if nth_bar <= 1:
            if psar_opposite:
                exit_long = trend_change_bull
                exit_short = trend_change_bear
            else:
                exit_long = trend_change_bear
                exit_short = trend_change_bull
        else:
            if psar_opposite:
                bull_counter = trend_change_bull.cumsum()
                bars_since_bull = bull_counter.groupby(bull_counter).cumcount() + 1
                bear_counter = trend_change_bear.cumsum()
                bars_since_bear = bear_counter.groupby(bear_counter).cumcount() + 1
                exit_long = bars_since_bull == nth_bar
                exit_short = bars_since_bear == nth_bar
            else:
                bear_counter = trend_change_bear.cumsum()
                bars_since_bear = bear_counter.groupby(bear_counter).cumcount() + 1
                bull_counter = trend_change_bull.cumsum()
                bars_since_bull = bull_counter.groupby(bull_counter).cumcount() + 1
                exit_long = bars_since_bear == nth_bar
                exit_short = bars_since_bull == nth_bar

        result["exit_long"] = exit_long.fillna(False)
        result["exit_short"] = exit_short.fillna(False)
        result["exit"] = (exit_long | exit_short).fillna(False)
        result["signal"] = result["exit"]
        if psar_profit_only:
            result["profit_only"] = pd.Series([True] * n, index=idx)
            result["min_profit"] = pd.Series([psar_min_profit] * n, index=idx)

    else:
        result["exit"] = pd.Series([False] * n, index=idx)
        result["signal"] = pd.Series([False] * n, index=idx)

    return result
