"""
Indicator handler functions - backward compatibility wrapper.

Этот файл обеспечивает обратную совместимость для кода, который импортирует
handler-функции из старого модуля `indicator_handlers`.

Весь функционал теперь находится в пакете `backend.backtesting.indicators`.
Этот модуль делает редирект импортов на новую структуру.

Для нового кода используйте прямой импорт:
    from backend.backtesting.indicators import BLOCK_REGISTRY, INDICATOR_DISPATCH
    from backend.backtesting.indicators.trend import _handle_ema
    from backend.backtesting.indicators.oscillators import _handle_rsi

Warning:
    Этот файл может быть удалён в будущей версии после миграции всего кода.
"""

from __future__ import annotations

# Re-export everything from the new indicators package
from backend.backtesting.indicators import (
    _TF_RESAMPLE_MAP,
    BLOCK_REGISTRY,
    INDICATOR_DISPATCH,
    _calc_ma,
    _handle_accumulation_areas,
    _handle_ad_line,
    _handle_adx,
    _handle_aroon,
    _handle_atr,
    _handle_atr_volatility,
    _handle_atrp,
    # Volatility handlers
    _handle_bollinger,
    _handle_cci,
    _handle_cci_filter,
    _handle_cmf,
    _handle_cmo,
    _handle_dema,
    _handle_donchian,
    # Trend handlers
    _handle_ema,
    _handle_highest_lowest_bar,
    _handle_hull_ma,
    _handle_ichimoku,
    _handle_keltner,
    _handle_keltner_bollinger,
    _handle_macd,
    _handle_mfi,
    _handle_mfi_filter,
    _handle_momentum_filter,
    _handle_mtf,
    # Volume handlers
    _handle_obv,
    _handle_parabolic_sar,
    # Other handlers
    _handle_pivot_points,
    _handle_pvt,
    _handle_qqe,
    _handle_roc,
    # Oscillator handlers
    _handle_rsi,
    _handle_rvi_filter,
    _handle_sma,
    _handle_stddev,
    _handle_stoch_rsi,
    _handle_stochastic,
    _handle_supertrend,
    _handle_tema,
    _handle_two_mas,
    _handle_volume_filter,
    _handle_vwap,
    _handle_williams_r,
    _handle_wma,
    _require_vbt,
    _resample_ohlcv,
)
from backend.backtesting.indicators.oscillators import (
    BLOCK_REGISTRY as OSCILLATORS_REGISTRY,
)
from backend.backtesting.indicators.oscillators import (
    INDICATOR_DISPATCH as OSCILLATORS_DISPATCH,
)
from backend.backtesting.indicators.other import (
    BLOCK_REGISTRY as OTHER_REGISTRY,
)
from backend.backtesting.indicators.other import (
    INDICATOR_DISPATCH as OTHER_DISPATCH,
)

# Also import from submodules for more granular access
from backend.backtesting.indicators.trend import (
    BLOCK_REGISTRY as TREND_REGISTRY,
)
from backend.backtesting.indicators.trend import (
    INDICATOR_DISPATCH as TREND_DISPATCH,
)
from backend.backtesting.indicators.volatility import (
    BLOCK_REGISTRY as VOLATILITY_REGISTRY,
)
from backend.backtesting.indicators.volatility import (
    INDICATOR_DISPATCH as VOLATILITY_DISPATCH,
)
from backend.backtesting.indicators.volume import (
    BLOCK_REGISTRY as VOLUME_REGISTRY,
)
from backend.backtesting.indicators.volume import (
    INDICATOR_DISPATCH as VOLUME_DISPATCH,
)

# Module metadata
__all__ = [
    # Registries
    "BLOCK_REGISTRY",
    "INDICATOR_DISPATCH",
    "TREND_REGISTRY",
    "TREND_DISPATCH",
    "OSCILLATORS_REGISTRY",
    "OSCILLATORS_DISPATCH",
    "VOLATILITY_REGISTRY",
    "VOLATILITY_DISPATCH",
    "VOLUME_REGISTRY",
    "VOLUME_DISPATCH",
    "OTHER_REGISTRY",
    "OTHER_DISPATCH",
    # Helper functions
    "_require_vbt",
    "_calc_ma",
    "_resample_ohlcv",
    "_TF_RESAMPLE_MAP",
    # All handlers
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
    "_handle_bollinger",
    "_handle_keltner",
    "_handle_donchian",
    "_handle_atr",
    "_handle_atrp",
    "_handle_stddev",
    "_handle_atr_volatility",
    "_handle_obv",
    "_handle_vwap",
    "_handle_ad_line",
    "_handle_pvt",
    "_handle_volume_filter",
    "_handle_pivot_points",
    "_handle_mtf",
    "_handle_highest_lowest_bar",
    "_handle_accumulation_areas",
    "_handle_keltner_bollinger",
    "_handle_mfi_filter",
    "_handle_cci_filter",
    "_handle_momentum_filter",
]
