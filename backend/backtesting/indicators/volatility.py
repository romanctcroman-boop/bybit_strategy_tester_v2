"""
Volatility indicators - индикаторы волатильности.

Этот модуль содержит обработчики для индикаторов волатильности:
- atr, atrp, stddev, bollinger, keltner, donchian
- atr_volatility (handler)
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
    calculate_atr_smoothed,
    calculate_atrp,
    calculate_bollinger,
    calculate_donchian,
    calculate_keltner,
    calculate_stddev,
)

if TYPE_CHECKING:
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter


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
    """Handle Bollinger Bands indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with Bollinger Bands (upper, middle, lower).
    """
    period = _clamp_period(params.get("period", 20))
    std_dev = _param(params, 2.0, "std_dev", "stdDev")
    middle, upper, lower = calculate_bollinger(close.values, period, std_dev)
    return {
        "upper": pd.Series(upper, index=close.index),
        "middle": pd.Series(middle, index=close.index),
        "lower": pd.Series(lower, index=close.index),
    }


def _handle_keltner(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle Keltner Channel indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with Keltner Channel (upper, middle, lower).
    """
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
    """Handle Donchian Channel indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with Donchian Channel (upper, middle, lower).
    """
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
    """Handle ATR (Average True Range) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with ATR values.
    """
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
    """Handle ATRP (ATR Percentage) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with ATRP values.
    """
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
    """Handle Standard Deviation indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with standard deviation values.
    """
    period = _clamp_period(params.get("period", 20))
    result = calculate_stddev(close.values, period)
    return {"value": pd.Series(result, index=ohlcv.index)}


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
    """Handle ATR Volatility filter.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with long/short filter signals.
    """
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


# ═══════════════════════════════════════════════════════════════════════════
# Block Registry
# ═══════════════════════════════════════════════════════════════════════════

BLOCK_REGISTRY: dict[str, dict[str, Any]] = {
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
    # ── Universal filters ────────────────────────────────────────────────
    "atr_volatility": {
        "handler": _handle_atr_volatility,
        "outputs": ["long", "short"],
        "param_aliases": {},
    },
}

# Backward-compatible dispatch table for this module
INDICATOR_DISPATCH: dict[str, Any] = {k: v["handler"] for k, v in BLOCK_REGISTRY.items()}
