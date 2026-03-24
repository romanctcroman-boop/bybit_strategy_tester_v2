"""
Indicators package - модули индикаторов.

Этот пакет содержит обработчики индикаторов, разбитые по категориям:
- trend: трендовые индикаторы и MA (sma, ema, adx, supertrend, ichimoku, ...)
- oscillators: осцилляторы (rsi, macd, stochastic, cci, mfi, ...)
- volatility: волатильность (atr, bollinger, keltner, donchian, ...)
- volume: объёмные (obv, vwap, cmf, ad_line, pvt, ...)
- other: остальные (pivot_points, mtf, filters, ...)

Пример использования:
    from backend.backtesting.indicators import BLOCK_REGISTRY, INDICATOR_DISPATCH

    # Получить все зарегистрированные индикаторы
    all_indicators = list(BLOCK_REGISTRY.keys())

    # Получить handler для конкретного индикатора
    handler = INDICATOR_DISPATCH["rsi"]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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


# Import all BLOCK_REGISTRY from submodules
from .oscillators import BLOCK_REGISTRY as OSCILLATORS_REGISTRY
from .other import _TF_RESAMPLE_MAP, _resample_ohlcv
from .other import BLOCK_REGISTRY as OTHER_REGISTRY
from .trend import BLOCK_REGISTRY as TREND_REGISTRY

# Import helper functions that may be needed by other modules
from .trend import _calc_ma
from .volatility import BLOCK_REGISTRY as VOLATILITY_REGISTRY
from .volume import BLOCK_REGISTRY as VOLUME_REGISTRY

# Combine all registries into one master registry
# Order matters for potential key conflicts (later modules override earlier ones)
BLOCK_REGISTRY: dict[str, dict[str, Any]] = {}
BLOCK_REGISTRY.update(TREND_REGISTRY)
BLOCK_REGISTRY.update(OSCILLATORS_REGISTRY)
BLOCK_REGISTRY.update(VOLATILITY_REGISTRY)
BLOCK_REGISTRY.update(VOLUME_REGISTRY)
BLOCK_REGISTRY.update(OTHER_REGISTRY)

# Backward-compatible dispatch table — generated automatically from the registry.
# New code should use BLOCK_REGISTRY; INDICATOR_DISPATCH is kept for compatibility.
INDICATOR_DISPATCH: dict[str, Any] = {k: v["handler"] for k, v in BLOCK_REGISTRY.items()}

# Export all handler functions for direct import if needed
from .oscillators import (
    _handle_cci,
    _handle_cmf,
    _handle_cmo,
    _handle_macd,
    _handle_mfi,
    _handle_qqe,
    _handle_roc,
    _handle_rsi,
    _handle_rvi_filter,
    _handle_stoch_rsi,
    _handle_stochastic,
    _handle_williams_r,
)
from .other import (
    _handle_accumulation_areas,
    _handle_cci_filter,
    _handle_highest_lowest_bar,
    _handle_keltner_bollinger,
    _handle_mfi_filter,
    _handle_momentum_filter,
    _handle_mtf,
    _handle_pivot_points,
)
from .trend import (
    _handle_adx,
    _handle_aroon,
    _handle_dema,
    _handle_ema,
    _handle_hull_ma,
    _handle_ichimoku,
    _handle_parabolic_sar,
    _handle_sma,
    _handle_supertrend,
    _handle_tema,
    _handle_two_mas,
    _handle_wma,
)
from .volatility import (
    _handle_atr,
    _handle_atr_volatility,
    _handle_atrp,
    _handle_bollinger,
    _handle_donchian,
    _handle_keltner,
    _handle_stddev,
)
from .volume import (
    _handle_ad_line,
    _handle_cmf,
    _handle_obv,
    _handle_pvt,
    _handle_volume_filter,
    _handle_vwap,
)

# Public API - what gets imported with "from backend.backtesting.indicators import *"
__all__ = [
    # Registries
    "BLOCK_REGISTRY",
    "INDICATOR_DISPATCH",
    # Helper functions
    "_require_vbt",
    "_calc_ma",
    "_resample_ohlcv",
    "_TF_RESAMPLE_MAP",
    # Trend handlers
    "_handle_ema",
    "_handle_sma",
    "_handle_wma",
    "_handle_dema",
    "_handle_tema",
    "_handle_hull_ma",
    "_handle_adx",
    "_handle_supertrend",
    "_handle_ichimoku",
    "_handle_parabolic_sar",
    "_handle_aroon",
    "_handle_two_mas",
    # Oscillator handlers
    "_handle_rsi",
    "_handle_macd",
    "_handle_stochastic",
    "_handle_qqe",
    "_handle_stoch_rsi",
    "_handle_williams_r",
    "_handle_roc",
    "_handle_mfi",
    "_handle_cmo",
    "_handle_cci",
    "_handle_cmf",
    "_handle_rvi_filter",
    # Volatility handlers
    "_handle_bollinger",
    "_handle_keltner",
    "_handle_donchian",
    "_handle_atr",
    "_handle_atrp",
    "_handle_stddev",
    "_handle_atr_volatility",
    # Volume handlers
    "_handle_obv",
    "_handle_vwap",
    "_handle_cmf",
    "_handle_ad_line",
    "_handle_pvt",
    "_handle_volume_filter",
    # Other handlers
    "_handle_pivot_points",
    "_handle_mtf",
    "_handle_highest_lowest_bar",
    "_handle_accumulation_areas",
    "_handle_keltner_bollinger",
    "_handle_mfi_filter",
    "_handle_cci_filter",
    "_handle_momentum_filter",
]
