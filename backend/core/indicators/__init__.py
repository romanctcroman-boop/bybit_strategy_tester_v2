"""
Unified Technical Indicators Library
=====================================

Single source of truth for all technical indicators in the project.

Usage:
    from backend.core.indicators import calculate_rsi, calculate_sma, calculate_ema
    from backend.core.indicators import calculate_macd, calculate_bollinger
    from backend.core.indicators import calculate_atr, calculate_stochastic
    from backend.core.indicators import calculate_adx, calculate_cci, calculate_ichimoku

    # Advanced RSI Filter (TradingView parity)
    from backend.core.indicators import RSIAdvancedFilter, RSIAdvancedConfig

All functions accept numpy arrays and return numpy arrays.
Optimized for performance with optional Numba JIT compilation.
"""

from backend.core.indicators.advanced import (
    ADXResult,
    AroonResult,
    IchimokuResult,
    PivotResult,
    calculate_adx,
    calculate_aroon,
    calculate_atrp,
    calculate_cci,
    calculate_ichimoku,
    calculate_parabolic_sar,
    calculate_pivot_points,
    calculate_pivot_points_array,
)
from backend.core.indicators.momentum import (
    calculate_cmo,
    calculate_mfi,
    calculate_roc,
    calculate_rsi,
    calculate_rsi_fast,
    calculate_stoch_rsi,
    calculate_stochastic,
    calculate_williams_r,
)

# Price Action Patterns (Numba JIT Optimized)
from backend.core.indicators.price_action_numba import (
    NUMBA_AVAILABLE as PRICE_ACTION_NUMBA_AVAILABLE,
)
from backend.core.indicators.price_action_numba import (
    detect_all_patterns,
    detect_doji,
    detect_engulfing,
    detect_hammer,
    detect_harami,
    detect_inside_bar,
    detect_marubozu,
    detect_morning_evening_star,
    detect_outside_bar,
    detect_piercing_darkcloud,
    detect_pin_bar,
    detect_shooting_star,
    detect_three_methods,
    detect_three_soldiers_crows,
    detect_tweezer,
)
from backend.core.indicators.qqe import (
    calculate_qqe,
    calculate_qqe_cross,
)
from backend.core.indicators.rsi_advanced import (
    RSIAdvancedConfig,
    RSIAdvancedFilter,
    RSIFilterMode,
    RSIFilterResult,
    apply_rsi_combined_filter,
    apply_rsi_cross_filter,
    apply_rsi_range_filter,
    create_btc_rsi_filter,
)
from backend.core.indicators.trend import (
    calculate_dema,
    calculate_ema,
    calculate_hull_ma,
    calculate_macd,
    calculate_sma,
    calculate_supertrend,
    calculate_tema,
    calculate_wma,
)
from backend.core.indicators.volatility import (
    calculate_atr,
    calculate_bollinger,
    calculate_donchian,
    calculate_keltner,
    calculate_stddev,
)
from backend.core.indicators.volume import (
    calculate_ad_line,
    calculate_cmf,
    calculate_obv,
    calculate_pvt,
    calculate_vwap,
)

__all__ = [
    # Price Action Patterns (Numba JIT Optimized)
    "PRICE_ACTION_NUMBA_AVAILABLE",
    # Advanced (ADX, CCI, Ichimoku, etc.)
    "ADXResult",
    "AroonResult",
    "IchimokuResult",
    "PivotResult",
    # Advanced RSI Filter (TradingView parity)
    "RSIAdvancedConfig",
    "RSIAdvancedFilter",
    "RSIFilterMode",
    "RSIFilterResult",
    "apply_rsi_combined_filter",
    "apply_rsi_cross_filter",
    "apply_rsi_range_filter",
    # Volume
    "calculate_ad_line",
    "calculate_adx",
    "calculate_aroon",
    # Volatility
    "calculate_atr",
    "calculate_atrp",
    "calculate_bollinger",
    "calculate_cci",
    "calculate_cmf",
    # Momentum
    "calculate_cmo",
    # Trend
    "calculate_dema",
    "calculate_donchian",
    "calculate_ema",
    "calculate_hull_ma",
    "calculate_ichimoku",
    "calculate_keltner",
    "calculate_macd",
    "calculate_mfi",
    "calculate_obv",
    "calculate_parabolic_sar",
    "calculate_pivot_points",
    "calculate_pivot_points_array",
    "calculate_pvt",
    "calculate_qqe",
    "calculate_qqe_cross",
    "calculate_roc",
    "calculate_rsi",
    "calculate_rsi_fast",
    "calculate_sma",
    "calculate_stddev",
    "calculate_stoch_rsi",
    "calculate_stochastic",
    "calculate_supertrend",
    "calculate_tema",
    "calculate_vwap",
    "calculate_williams_r",
    "calculate_wma",
    "create_btc_rsi_filter",
    "detect_all_patterns",
    "detect_doji",
    "detect_engulfing",
    "detect_hammer",
    "detect_harami",
    "detect_inside_bar",
    "detect_marubozu",
    "detect_morning_evening_star",
    "detect_outside_bar",
    "detect_piercing_darkcloud",
    "detect_pin_bar",
    "detect_shooting_star",
    "detect_three_methods",
    "detect_three_soldiers_crows",
    "detect_tweezer",
]
