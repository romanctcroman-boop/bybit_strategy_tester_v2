"""
Trend indicators - трендовые индикаторы и скользящие средние.

Этот модуль содержит обработчики для трендовых индикаторов:
- MA family: sma, ema, wma, dema, tema, hull_ma
- Trend: adx, supertrend, ichimoku, parabolic_sar, aroon
- Filter: two_mas (трендовый фильтр)
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
    calculate_adx,
    calculate_aroon,
    calculate_dema,
    calculate_hull_ma,
    calculate_ichimoku,
    calculate_parabolic_sar,
    calculate_supertrend,
    calculate_tema,
    calculate_wma,
)

if TYPE_CHECKING:
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter


# ---------------------------------------------------------------------------
# Helper функции
# ---------------------------------------------------------------------------
def _calc_ma(src: pd.Series, length: int, ma_type: str) -> pd.Series:
    """Calculate a moving average of the given type.

    Args:
        src: Source price series.
        length: MA period length.
        ma_type: Type of MA - "SMA", "EMA", "WMA", or "RMA".

    Returns:
        Moving average series.
    """
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
# Trend indicators (MA family)
# ═══════════════════════════════════════════════════════════════════════════


def _handle_ema(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle EMA indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with EMA values.
    """
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
    """Handle SMA indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with SMA values.
    """
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
    """Handle WMA indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with WMA values.
    """
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
    """Handle DEMA (Double Exponential Moving Average) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with DEMA values.
    """
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
    """Handle TEMA (Triple Exponential Moving Average) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with TEMA values.
    """
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
    """Handle Hull Moving Average indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with Hull MA values.
    """
    period = _clamp_period(params.get("period", 20))
    result = calculate_hull_ma(close.values, period)
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
    """Handle ADX (Average Directional Index) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with ADX values.
    """
    period = _clamp_period(params.get("period", 14))
    adx_result = calculate_adx(ohlcv["high"].values, ohlcv["low"].values, close.values, period)
    adx = pd.Series(adx_result.adx, index=ohlcv.index)
    return {"value": adx}


def _handle_supertrend(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle Supertrend indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with Supertrend values and signals.
    """
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
        # Default behaviour: use trend direction (direction==1 = uptrend = long allowed)
        # This makes SuperTrend behave as a trend-following filter even without
        # explicit use_supertrend=True. Previously this returned pd.Series(True, …)
        # which caused entry on every bar when wired to entry_long port.
        long_signal = (direction == 1).fillna(False)
        short_signal = (direction == -1).fillna(False)
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
    """Handle Ichimoku Cloud indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with Ichimoku components.
    """
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
    """Handle Parabolic SAR indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with Parabolic SAR values.
    """
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
    """Handle Aroon indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with Aroon components.
    """
    period = _clamp_period(params.get("period", 25))
    aroon_result = calculate_aroon(ohlcv["high"].values, ohlcv["low"].values, period)
    return {
        "up": pd.Series(aroon_result.aroon_up, index=ohlcv.index),
        "down": pd.Series(aroon_result.aroon_down, index=ohlcv.index),
        "oscillator": pd.Series(aroon_result.aroon_osc, index=ohlcv.index),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Trend filter - two_mas
# ═══════════════════════════════════════════════════════════════════════════


def _handle_two_mas(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle Two MAs trend filter.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with MA values and signals.
    """
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


# ═══════════════════════════════════════════════════════════════════════════
# Block Registry
# ═══════════════════════════════════════════════════════════════════════════

BLOCK_REGISTRY: dict[str, dict[str, Any]] = {
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
    # Alias: LLM agents sometimes hallucinate "supertrend_filter" — map to same handler
    "supertrend_filter": {
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
    # ── Trend filter ─────────────────────────────────────────────────────
    "two_mas": {
        "handler": _handle_two_mas,
        "outputs": ["long", "short", "ma1", "ma2"],
        "param_aliases": {},
    },
}

# Backward-compatible dispatch table for this module
INDICATOR_DISPATCH: dict[str, Any] = {k: v["handler"] for k, v in BLOCK_REGISTRY.items()}
