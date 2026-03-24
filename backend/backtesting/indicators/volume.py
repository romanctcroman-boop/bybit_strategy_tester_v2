"""
Volume indicators - объёмные индикаторы.

Этот модуль содержит обработчики для объёмных индикаторов:
- obv, vwap, cmf, ad_line, pvt
- volume_filter (handler)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from loguru import logger

from backend.backtesting.strategy_builder_adapter import _clamp_period
from backend.core.indicators import (
    calculate_ad_line,
    calculate_cmf,
    calculate_mfi,
    calculate_obv,
    calculate_pvt,
    calculate_vwap,
)

if TYPE_CHECKING:
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter


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
    """Handle OBV (On-Balance Volume) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with OBV values.
    """
    result = calculate_obv(close.values, ohlcv["volume"].values)
    return {"value": pd.Series(result, index=ohlcv.index)}


def _handle_vwap(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle VWAP (Volume Weighted Average Price) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with VWAP values.
    """
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


def _handle_ad_line(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle AD Line (Accumulation/Distribution Line) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with AD Line values.
    """
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
    """Handle PVT (Price Volume Trend) indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with PVT values.
    """
    result = calculate_pvt(close.values, ohlcv["volume"].values)
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


# ═══════════════════════════════════════════════════════════════════════════
# Volume filter
# ═══════════════════════════════════════════════════════════════════════════


def _handle_volume_filter(
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
    close: pd.Series,
    inputs: dict[str, pd.Series],
    adapter: StrategyBuilderAdapter,
) -> dict[str, pd.Series]:
    """Handle Volume Filter indicator.

    Args:
        params: Indicator parameters.
        ohlcv: OHLCV DataFrame.
        close: Close price series.
        inputs: Input series.
        adapter: Strategy builder adapter.

    Returns:
        Dictionary with long/short filter signals.
    """
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


# ═══════════════════════════════════════════════════════════════════════════
# Block Registry
# ═══════════════════════════════════════════════════════════════════════════

BLOCK_REGISTRY: dict[str, dict[str, Any]] = {
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
    "mfi": {
        "handler": _handle_mfi,
        "outputs": ["value"],
        "param_aliases": {},
    },
    # ── Universal filters ────────────────────────────────────────────────
    "volume_filter": {
        "handler": _handle_volume_filter,
        "outputs": ["long", "short"],
        "param_aliases": {},
    },
}

# Backward-compatible dispatch table for this module
INDICATOR_DISPATCH: dict[str, Any] = {k: v["handler"] for k, v in BLOCK_REGISTRY.items()}
