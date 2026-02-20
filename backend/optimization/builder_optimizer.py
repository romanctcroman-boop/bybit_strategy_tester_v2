"""
Builder Strategy Optimizer.

Enables optimization of visual node-based strategies from Strategy Builder.
Extracts optimizable parameters from graph blocks, clones graphs with modified params,
runs backtests via StrategyBuilderAdapter, and supports Grid Search + Optuna Bayesian.

Architecture:
    Strategy Builder Graph (blocks + connections)
        → extract_optimizable_params()  → discover param ranges
        → clone_graph_with_params()     → create modified graph
        → StrategyBuilderAdapter(graph) → generate signals
        → BacktestEngine.run()          → metrics
        → scoring + filtering           → ranked results
"""

from __future__ import annotations

import copy
import logging
import time
from itertools import product
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from optuna.samplers import BaseSampler
import pandas as pd

from backend.optimization.filters import passes_filters
from backend.optimization.scoring import calculate_composite_score

logger = logging.getLogger(__name__)

# =============================================================================
# PARAMETER EXTRACTION FROM GRAPH
# =============================================================================

# Default optimization ranges per indicator block type
DEFAULT_PARAM_RANGES: dict[str, dict[str, dict[str, Any]]] = {
    "rsi": {
        "period": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        # Range filter bounds (long)
        "long_rsi_more": {"type": "float", "low": 10, "high": 45, "step": 5, "default": 30},
        "long_rsi_less": {"type": "float", "low": 55, "high": 90, "step": 5, "default": 70},
        # Range filter bounds (short)
        "short_rsi_less": {"type": "float", "low": 55, "high": 90, "step": 5, "default": 70},
        "short_rsi_more": {"type": "float", "low": 10, "high": 45, "step": 5, "default": 30},
        # Cross levels
        "cross_long_level": {"type": "float", "low": 15, "high": 45, "step": 5, "default": 30},
        "cross_short_level": {"type": "float", "low": 55, "high": 85, "step": 5, "default": 70},
        # Cross memory
        "cross_memory_bars": {"type": "int", "low": 1, "high": 20, "step": 1, "default": 5},
        # Legacy (backward compatibility — only used when no new mode is enabled)
        "overbought": {"type": "int", "low": 60, "high": 85, "step": 5, "default": 70},
        "oversold": {"type": "int", "low": 15, "high": 40, "step": 5, "default": 30},
    },
    "macd": {
        "fast_period": {"type": "int", "low": 8, "high": 16, "step": 1, "default": 12},
        "slow_period": {"type": "int", "low": 20, "high": 30, "step": 1, "default": 26},
        "signal_period": {"type": "int", "low": 6, "high": 12, "step": 1, "default": 9},
        # Cross with Level (Zero Line)
        "macd_cross_zero_level": {"type": "float", "low": -50.0, "high": 50.0, "step": 1.0, "default": 0},
        # Signal Memory
        "signal_memory_bars": {"type": "int", "low": 1, "high": 20, "step": 1, "default": 5},
    },
    "ema": {
        "period": {"type": "int", "low": 5, "high": 50, "step": 1, "default": 20},
    },
    "sma": {
        "period": {"type": "int", "low": 5, "high": 100, "step": 5, "default": 50},
    },
    "bollinger": {
        "period": {"type": "int", "low": 10, "high": 30, "step": 1, "default": 20},
        "std_dev": {"type": "float", "low": 1.5, "high": 3.0, "step": 0.25, "default": 2.0},
    },
    "supertrend": {
        "period": {"type": "int", "low": 5, "high": 20, "step": 1, "default": 10},
        "multiplier": {"type": "float", "low": 1.0, "high": 5.0, "step": 0.5, "default": 3.0},
    },
    "stochastic": {
        "stoch_k_length": {"type": "int", "low": 5, "high": 21, "step": 1, "default": 14},
        "stoch_k_smoothing": {"type": "int", "low": 1, "high": 5, "step": 1, "default": 3},
        "stoch_d_smoothing": {"type": "int", "low": 1, "high": 5, "step": 1, "default": 3},
        "long_stoch_d_more": {"type": "int", "low": 5, "high": 30, "step": 5, "default": 20},
        "long_stoch_d_less": {"type": "int", "low": 30, "high": 50, "step": 5, "default": 40},
        "short_stoch_d_less": {"type": "int", "low": 60, "high": 90, "step": 5, "default": 80},
        "short_stoch_d_more": {"type": "int", "low": 50, "high": 80, "step": 5, "default": 60},
        "stoch_cross_level_long": {"type": "int", "low": 10, "high": 30, "step": 5, "default": 20},
        "stoch_cross_level_short": {"type": "int", "low": 70, "high": 90, "step": 5, "default": 80},
        "stoch_cross_memory_bars": {"type": "int", "low": 1, "high": 20, "step": 1, "default": 5},
        "stoch_kd_memory_bars": {"type": "int", "low": 1, "high": 20, "step": 1, "default": 5},
    },
    "cci": {
        "period": {"type": "int", "low": 10, "high": 30, "step": 1, "default": 20},
    },
    "atr": {
        "period": {"type": "int", "low": 7, "high": 21, "step": 1, "default": 14},
    },
    "adx": {
        "period": {"type": "int", "low": 7, "high": 21, "step": 1, "default": 14},
    },
    "williams_r": {
        "period": {"type": "int", "low": 7, "high": 21, "step": 1, "default": 14},
    },
    "static_sltp": {
        "stop_loss_percent": {"type": "float", "low": 0.5, "high": 5.0, "step": 0.5, "default": 1.5},
        "take_profit_percent": {"type": "float", "low": 0.5, "high": 5.0, "step": 0.5, "default": 1.5},
        "breakeven_activation_percent": {"type": "float", "low": 0.1, "high": 2.0, "step": 0.1, "default": 0.5},
        "new_breakeven_sl_percent": {"type": "float", "low": 0.01, "high": 0.5, "step": 0.01, "default": 0.1},
    },
    "trailing_stop_exit": {
        "activation_percent": {"type": "float", "low": 0.5, "high": 3.0, "step": 0.25, "default": 1.0},
        "trailing_percent": {"type": "float", "low": 0.25, "high": 2.0, "step": 0.25, "default": 0.5},
    },
    # --- Extended indicator ranges ---
    "ichimoku": {
        "tenkan_period": {"type": "int", "low": 5, "high": 20, "step": 1, "default": 9},
        "kijun_period": {"type": "int", "low": 15, "high": 40, "step": 1, "default": 26},
        "senkou_b_period": {"type": "int", "low": 30, "high": 65, "step": 1, "default": 52},
    },
    "parabolic_sar": {
        "start": {"type": "float", "low": 0.01, "high": 0.05, "step": 0.005, "default": 0.02},
        "increment": {"type": "float", "low": 0.01, "high": 0.05, "step": 0.005, "default": 0.02},
        "max_value": {"type": "float", "low": 0.1, "high": 0.4, "step": 0.05, "default": 0.2},
    },
    "aroon": {
        "period": {"type": "int", "low": 10, "high": 50, "step": 5, "default": 25},
    },
    "qqe": {
        "rsi_period": {"type": "int", "low": 5, "high": 25, "step": 1, "default": 14},
        "qqe_factor": {"type": "float", "low": 2.0, "high": 6.0, "step": 0.5, "default": 4.238},
        "smoothing_period": {"type": "int", "low": 3, "high": 10, "step": 1, "default": 5},
        "qqe_signal_memory_bars": {"type": "int", "low": 1, "high": 20, "step": 1, "default": 5},
    },
    "keltner": {
        "ema_period": {"type": "int", "low": 10, "high": 40, "step": 5, "default": 20},
        "atr_period": {"type": "int", "low": 5, "high": 20, "step": 1, "default": 10},
        "multiplier": {"type": "float", "low": 1.0, "high": 4.0, "step": 0.5, "default": 2.0},
    },
    "donchian": {
        "period": {"type": "int", "low": 10, "high": 50, "step": 5, "default": 20},
    },
    "cmf": {
        "period": {"type": "int", "low": 10, "high": 30, "step": 5, "default": 20},
    },
    # --- DCA / Entry Refinement ---
    "dca": {
        "grid_size_percent": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 15},
        "order_count": {"type": "int", "low": 3, "high": 15, "step": 1, "default": 5},
        "martingale_coefficient": {"type": "float", "low": 1.0, "high": 1.8, "step": 0.1, "default": 1.0},
        "log_steps_coefficient": {"type": "float", "low": 0.5, "high": 2.0, "step": 0.1, "default": 1.0},
        "first_order_offset": {"type": "float", "low": 0, "high": 5, "step": 0.5, "default": 0},
    },
    # --- Universal filter/indicator blocks ---
    "atr_volatility": {
        "atr_length1": {"type": "int", "low": 5, "high": 50, "step": 5, "default": 20},
        "atr_length2": {"type": "int", "low": 50, "high": 200, "step": 10, "default": 100},
        "atr_diff_percent": {"type": "float", "low": 0, "high": 50, "step": 5, "default": 10},
    },
    "volume_filter": {
        "vol_length1": {"type": "int", "low": 5, "high": 50, "step": 5, "default": 20},
        "vol_length2": {"type": "int", "low": 50, "high": 200, "step": 10, "default": 100},
        "vol_diff_percent": {"type": "float", "low": 0, "high": 50, "step": 5, "default": 10},
    },
    "highest_lowest_bar": {
        "hl_lookback_bars": {"type": "int", "low": 5, "high": 50, "step": 5, "default": 10},
        "hl_price_percent": {"type": "float", "low": 0, "high": 5, "step": 0.5, "default": 0},
        "hl_atr_percent": {"type": "float", "low": 0, "high": 10, "step": 1, "default": 0},
        "atr_hl_length": {"type": "int", "low": 10, "high": 100, "step": 10, "default": 50},
    },
    "two_mas": {
        "ma1_length": {"type": "int", "low": 10, "high": 100, "step": 5, "default": 50},
        "ma2_length": {"type": "int", "low": 50, "high": 200, "step": 10, "default": 100},
        "ma_cross_memory_bars": {"type": "int", "low": 1, "high": 20, "step": 1, "default": 5},
    },
    "accumulation_areas": {
        "backtracking_interval": {"type": "int", "low": 10, "high": 100, "step": 5, "default": 30},
        "min_bars_to_execute": {"type": "int", "low": 2, "high": 20, "step": 1, "default": 5},
    },
    "keltner_bollinger": {
        "keltner_length": {"type": "int", "low": 5, "high": 50, "step": 5, "default": 14},
        "keltner_mult": {"type": "float", "low": 0.5, "high": 5.0, "step": 0.5, "default": 1.5},
        "bb_length": {"type": "int", "low": 10, "high": 50, "step": 5, "default": 20},
        "bb_deviation": {"type": "float", "low": 1.0, "high": 4.0, "step": 0.5, "default": 2.0},
    },
    "rvi_filter": {
        "rvi_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 10},
        "rvi_ma_length": {"type": "int", "low": 1, "high": 10, "step": 1, "default": 2},
        "rvi_long_more": {"type": "float", "low": -50, "high": 30, "step": 5, "default": 1},
        "rvi_long_less": {"type": "float", "low": 20, "high": 80, "step": 5, "default": 50},
        "rvi_short_less": {"type": "float", "low": 50, "high": 100, "step": 5, "default": 100},
        "rvi_short_more": {"type": "float", "low": 20, "high": 80, "step": 5, "default": 50},
    },
    "mfi_filter": {
        "mfi_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "mfi_long_more": {"type": "float", "low": 0, "high": 40, "step": 5, "default": 1},
        "mfi_long_less": {"type": "float", "low": 20, "high": 80, "step": 5, "default": 60},
        "mfi_short_less": {"type": "float", "low": 60, "high": 100, "step": 5, "default": 100},
        "mfi_short_more": {"type": "float", "low": 20, "high": 80, "step": 5, "default": 50},
    },
    "cci_filter": {
        "cci_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "cci_long_more": {"type": "float", "low": -400, "high": 0, "step": 50, "default": -400},
        "cci_long_less": {"type": "float", "low": 0, "high": 400, "step": 50, "default": 400},
        "cci_short_less": {"type": "float", "low": 0, "high": 400, "step": 50, "default": 400},
        "cci_short_more": {"type": "float", "low": -400, "high": 200, "step": 50, "default": 10},
    },
    "momentum_filter": {
        "momentum_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "momentum_long_more": {"type": "float", "low": -200, "high": 0, "step": 10, "default": -100},
        "momentum_long_less": {"type": "float", "low": 0, "high": 100, "step": 10, "default": 10},
        "momentum_short_less": {"type": "float", "low": 0, "high": 200, "step": 10, "default": 95},
        "momentum_short_more": {"type": "float", "low": -100, "high": 50, "step": 10, "default": -30},
    },
    "divergence": {
        "pivot_interval": {"type": "int", "low": 3, "high": 20, "step": 1, "default": 9},
        "rsi_period": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "stoch_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "momentum_length": {"type": "int", "low": 5, "high": 20, "step": 1, "default": 10},
        "cmf_period": {"type": "int", "low": 10, "high": 40, "step": 5, "default": 21},
        "mfi_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "keep_diver_signal_memory_bars": {"type": "int", "low": 1, "high": 20, "step": 1, "default": 5},
    },
    # --- Filter ranges ---
    "rsi_filter": {
        "rsi_period": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
    },
    "supertrend_filter": {
        "atr_period": {"type": "int", "low": 5, "high": 20, "step": 1, "default": 10},
        "atr_multiplier": {"type": "float", "low": 1.0, "high": 5.0, "step": 0.5, "default": 3.0},
    },
    "macd_filter": {
        "macd_fast_length": {"type": "int", "low": 8, "high": 16, "step": 1, "default": 12},
        "macd_slow_length": {"type": "int", "low": 20, "high": 30, "step": 1, "default": 26},
        "macd_signal_smoothing": {"type": "int", "low": 6, "high": 12, "step": 1, "default": 9},
    },
    "stochastic_filter": {
        "stoch_k_length": {"type": "int", "low": 5, "high": 21, "step": 1, "default": 14},
        "stoch_k_smoothing": {"type": "int", "low": 1, "high": 5, "step": 1, "default": 3},
        "stoch_d_smoothing": {"type": "int", "low": 1, "high": 5, "step": 1, "default": 3},
    },
    "two_ma_filter": {
        "ma1_length": {"type": "int", "low": 10, "high": 100, "step": 5, "default": 50},
        "ma2_length": {"type": "int", "low": 50, "high": 200, "step": 10, "default": 100},
    },
    "qqe_filter": {
        "qqe_rsi_length": {"type": "int", "low": 5, "high": 25, "step": 1, "default": 14},
        "qqe_rsi_smoothing": {"type": "int", "low": 3, "high": 10, "step": 1, "default": 5},
        "qqe_delta_multiplier": {"type": "float", "low": 2.0, "high": 8.0, "step": 0.5, "default": 5.1},
    },
    # --- Exit ranges ---
    "atr_exit": {
        "atr_sl_period": {"type": "int", "low": 50, "high": 200, "step": 10, "default": 140},
        "atr_sl_multiplier": {"type": "float", "low": 1.0, "high": 8.0, "step": 0.5, "default": 4.0},
        "atr_tp_period": {"type": "int", "low": 50, "high": 200, "step": 10, "default": 140},
        "atr_tp_multiplier": {"type": "float", "low": 1.0, "high": 8.0, "step": 0.5, "default": 4.0},
    },
    "multi_tp_exit": {
        "tp1_percent": {"type": "float", "low": 0.5, "high": 3.0, "step": 0.25, "default": 1.0},
        "tp2_percent": {"type": "float", "low": 1.0, "high": 5.0, "step": 0.5, "default": 2.0},
        "tp3_percent": {"type": "float", "low": 2.0, "high": 10.0, "step": 0.5, "default": 3.0},
        "tp1_close_percent": {"type": "int", "low": 20, "high": 50, "step": 5, "default": 33},
        "tp2_close_percent": {"type": "int", "low": 20, "high": 50, "step": 5, "default": 33},
        "tp3_close_percent": {"type": "int", "low": 20, "high": 50, "step": 5, "default": 34},
    },
    # --- Close-by-Indicator exit ranges ---
    "close_by_time": {
        "bars_since_entry": {"type": "int", "low": 3, "high": 50, "step": 1, "default": 10},
        "min_profit_percent": {"type": "float", "low": 0, "high": 5, "step": 0.5, "default": 0},
    },
    "close_channel": {
        "keltner_length": {"type": "int", "low": 5, "high": 50, "step": 5, "default": 14},
        "keltner_mult": {"type": "float", "low": 0.5, "high": 5.0, "step": 0.5, "default": 1.5},
        "bb_length": {"type": "int", "low": 10, "high": 50, "step": 5, "default": 20},
        "bb_deviation": {"type": "float", "low": 1.0, "high": 4.0, "step": 0.5, "default": 2.0},
    },
    "close_ma_cross": {
        "ma1_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 10},
        "ma2_length": {"type": "int", "low": 15, "high": 60, "step": 5, "default": 30},
        "min_profit_percent": {"type": "float", "low": 0, "high": 5, "step": 0.5, "default": 1},
    },
    "close_rsi": {
        "rsi_close_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "rsi_long_more": {"type": "float", "low": 60, "high": 85, "step": 5, "default": 70},
        "rsi_long_less": {"type": "float", "low": 90, "high": 100, "step": 5, "default": 100},
        "rsi_short_less": {"type": "float", "low": 15, "high": 40, "step": 5, "default": 30},
        "rsi_short_more": {"type": "float", "low": 0, "high": 10, "step": 1, "default": 1},
        "rsi_cross_long_level": {"type": "float", "low": 60, "high": 85, "step": 5, "default": 70},
        "rsi_cross_short_level": {"type": "float", "low": 15, "high": 40, "step": 5, "default": 30},
    },
    "close_stochastic": {
        "stoch_close_k_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "stoch_close_k_smoothing": {"type": "int", "low": 1, "high": 5, "step": 1, "default": 3},
        "stoch_close_d_smoothing": {"type": "int", "low": 1, "high": 5, "step": 1, "default": 3},
        "stoch_long_more": {"type": "float", "low": 70, "high": 90, "step": 5, "default": 80},
        "stoch_long_less": {"type": "float", "low": 90, "high": 100, "step": 5, "default": 100},
        "stoch_short_less": {"type": "float", "low": 10, "high": 30, "step": 5, "default": 20},
        "stoch_short_more": {"type": "float", "low": 0, "high": 10, "step": 1, "default": 1},
        "stoch_cross_long_level": {"type": "float", "low": 70, "high": 90, "step": 5, "default": 80},
        "stoch_cross_short_level": {"type": "float", "low": 10, "high": 30, "step": 5, "default": 20},
    },
    "close_psar": {
        "psar_start": {"type": "float", "low": 0.01, "high": 0.05, "step": 0.005, "default": 0.02},
        "psar_increment": {"type": "float", "low": 0.01, "high": 0.05, "step": 0.005, "default": 0.02},
        "psar_maximum": {"type": "float", "low": 0.1, "high": 0.4, "step": 0.05, "default": 0.2},
        "psar_close_nth_bar": {"type": "int", "low": 1, "high": 10, "step": 1, "default": 1},
    },
    "chandelier_exit": {
        "atr_period": {"type": "int", "low": 10, "high": 30, "step": 1, "default": 22},
        "atr_multiplier": {"type": "float", "low": 1.5, "high": 5.0, "step": 0.5, "default": 3.0},
    },
    "break_even_exit": {
        "activation_profit_percent": {"type": "float", "low": 0.5, "high": 3.0, "step": 0.25, "default": 1.0},
        "move_to_profit_percent": {"type": "float", "low": 0.0, "high": 0.5, "step": 0.05, "default": 0.1},
    },
}


def extract_optimizable_params(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract all optimizable parameters from a strategy graph.

    Scans blocks for indicator/exit types and returns parameter specs
    with default ranges based on block type.

    Args:
        graph: Strategy graph dict with 'blocks' key.

    Returns:
        List of parameter specs, each containing:
            - block_id: ID of the block
            - block_type: Type of the block (rsi, macd, etc.)
            - block_name: Display name of the block
            - param_key: Parameter name within the block
            - param_path: Full path "blockId.paramKey" for graph modification
            - type: "int" or "float"
            - low: Minimum value
            - high: Maximum value
            - step: Step size
            - default: Default value
            - current_value: Currently set value in the graph
    """
    blocks = graph.get("blocks", [])
    params = []

    for block in blocks:
        block_id = block.get("id", "")
        block_type = block.get("type", "")
        block_name = block.get("name", block_type)
        block_params = block.get("params") or block.get("config") or {}

        # User-provided optimization overrides from the UI (block.optimizationParams)
        user_opt_params: dict[str, dict[str, Any]] = block.get("optimizationParams") or {}

        # Validate user-provided optimizationParams format
        if user_opt_params:
            _validated: dict[str, dict[str, Any]] = {}
            for pk, pv in user_opt_params.items():
                if not isinstance(pv, dict):
                    logger.warning(
                        f"[OptExtract] Invalid optimizationParams format for block '{block_id}' "
                        f"param '{pk}': expected dict with {{low, high, step}}, got {type(pv).__name__}. Skipping."
                    )
                    continue
                required_keys = {"low", "high"}
                if not required_keys.issubset(pv.keys()):
                    logger.warning(
                        f"[OptExtract] optimizationParams for block '{block_id}' param '{pk}' "
                        f"missing required keys {required_keys - pv.keys()}. Skipping."
                    )
                    continue
                if pv["low"] > pv["high"]:
                    logger.warning(
                        f"[OptExtract] optimizationParams for block '{block_id}' param '{pk}': "
                        f"low ({pv['low']}) > high ({pv['high']}). Swapping."
                    )
                    pv["low"], pv["high"] = pv["high"], pv["low"]
                _validated[pk] = pv
            user_opt_params = _validated

        # Check if this block type has known optimizable params
        type_ranges = DEFAULT_PARAM_RANGES.get(block_type, {})
        if not type_ranges and not user_opt_params:
            continue

        for param_key, range_spec in type_ranges.items():
            current_value = block_params.get(param_key, range_spec["default"])

            # Skip RSI params for disabled modes to avoid wasted optimization iterations
            if block_type == "rsi":
                if param_key in ("long_rsi_more", "long_rsi_less") and not block_params.get("use_long_range", False):
                    continue
                if param_key in ("short_rsi_less", "short_rsi_more") and not block_params.get("use_short_range", False):
                    continue
                if param_key in ("cross_long_level", "cross_short_level") and not block_params.get(
                    "use_cross_level", False
                ):
                    continue
                if param_key == "cross_memory_bars" and not block_params.get("use_cross_memory", False):
                    continue
                # Skip legacy overbought/oversold if new modes are active
                has_new_mode = (
                    block_params.get("use_long_range", False)
                    or block_params.get("use_short_range", False)
                    or block_params.get("use_cross_level", False)
                )
                if param_key in ("overbought", "oversold") and has_new_mode:
                    continue

            # Skip MACD params for disabled modes to avoid wasted optimization iterations
            if block_type == "macd":
                if param_key == "macd_cross_zero_level" and not block_params.get("use_macd_cross_zero", False):
                    continue
                if param_key == "signal_memory_bars" and block_params.get("disable_signal_memory", False):
                    continue
                # Skip signal_memory_bars if no signal mode is enabled
                has_signal_mode = block_params.get("use_macd_cross_zero", False) or block_params.get(
                    "use_macd_cross_signal", False
                )
                if param_key == "signal_memory_bars" and not has_signal_mode:
                    continue

            # Merge user-provided optimizationParams over defaults
            user_override = user_opt_params.get(param_key, {})
            effective_low = user_override.get("low", range_spec["low"])
            effective_high = user_override.get("high", range_spec["high"])
            effective_step = user_override.get("step", range_spec["step"])
            effective_type = user_override.get("type", range_spec["type"])

            params.append(
                {
                    "block_id": block_id,
                    "block_type": block_type,
                    "block_name": block_name,
                    "param_key": param_key,
                    "param_path": f"{block_id}.{param_key}",
                    "type": effective_type,
                    "low": effective_low,
                    "high": effective_high,
                    "step": effective_step,
                    "default": range_spec["default"],
                    "current_value": current_value,
                }
            )

    return params


# =============================================================================
# GRAPH CLONING WITH PARAMETER SUBSTITUTION
# =============================================================================


def clone_graph_with_params(
    base_graph: dict[str, Any],
    param_overrides: dict[str, Any],
) -> dict[str, Any]:
    """
    Deep-clone a strategy graph and apply parameter overrides.

    Args:
        base_graph: Original strategy graph.
        param_overrides: Dict mapping param_path ("blockId.paramKey") to new value.

    Returns:
        Modified copy of the graph with updated block parameters.
    """
    graph = copy.deepcopy(base_graph)
    blocks = graph.get("blocks", [])

    # Build block lookup by ID
    block_map = {b["id"]: b for b in blocks}

    for param_path, value in param_overrides.items():
        parts = param_path.split(".", 1)
        if len(parts) != 2:
            logger.warning(f"Invalid param_path: {param_path}")
            continue

        block_id, param_key = parts
        block = block_map.get(block_id)
        if not block:
            logger.warning(f"Block {block_id} not found in graph")
            continue

        # Ensure params dict exists (handle both 'params' and 'config' keys)
        params_key = "params" if "params" in block else "config"
        if params_key not in block or block[params_key] is None:
            block[params_key] = {}
        block[params_key][param_key] = value

    return graph


# =============================================================================
# PARAMETER COMBINATION GENERATION FOR BUILDER STRATEGIES
# =============================================================================


def generate_builder_param_combinations(
    param_specs: list[dict[str, Any]],
    custom_ranges: list[dict[str, Any]] | None = None,
    search_method: str = "grid",
    max_iterations: int = 0,
    random_seed: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """
    Generate parameter combinations for builder strategy optimization.

    Args:
        param_specs: List of optimizable params from extract_optimizable_params().
        custom_ranges: User-defined ranges overriding defaults. Each dict has:
                       - param_path: "blockId.paramKey"
                       - low, high, step (optional overrides)
                       - enabled: bool (whether to optimize this param)
        search_method: "grid" or "random".
        max_iterations: Max combos for random search.
        random_seed: Seed for reproducibility.

    Returns:
        Tuple of (list_of_param_override_dicts, total_count_before_sampling).
    """
    import random as rng_module

    # Merge custom ranges with defaults
    active_specs = _merge_ranges(param_specs, custom_ranges)

    if not active_specs:
        logger.warning("No active parameters to optimize")
        return [{}], 1

    # Generate value ranges for each param
    param_paths: list[str] = []
    value_ranges: list[list] = []

    for spec in active_specs:
        param_paths.append(spec["param_path"])
        low = spec["low"]
        high = spec["high"]
        step = spec["step"]

        if spec["type"] == "int":
            values = list(range(int(low), int(high) + 1, int(step)))
        else:
            # Float range with numpy
            values = list(np.arange(float(low), float(high) + float(step) / 2, float(step)))
            values = [round(v, 4) for v in values]

        value_ranges.append(values)

    # Generate all combinations
    all_combos = list(product(*value_ranges))
    total_before_sampling = len(all_combos)

    if search_method == "random" and max_iterations > 0 and max_iterations < total_before_sampling:
        if random_seed is not None:
            rng_module.seed(random_seed)
        all_combos = rng_module.sample(all_combos, max_iterations)
        logger.info(f"🎲 Builder Random Search: {max_iterations} from {total_before_sampling}")
    else:
        logger.info(f"🔢 Builder Grid Search: {total_before_sampling} combinations")

    # Convert tuples to param_override dicts
    result = []
    for combo in all_combos:
        overrides = dict(zip(param_paths, combo, strict=False))
        result.append(overrides)

    return result, total_before_sampling


def _merge_ranges(
    param_specs: list[dict[str, Any]],
    custom_ranges: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """
    Merge default param specs with user-defined custom ranges.

    Custom ranges can override low/high/step and enable/disable params.
    """
    if not custom_ranges:
        # Use all defaults as-is
        return param_specs

    # Build lookup by param_path
    custom_map = {cr["param_path"]: cr for cr in custom_ranges}

    active = []
    for spec in param_specs:
        path = spec["param_path"]
        custom = custom_map.get(path)

        if custom is not None:
            # User explicitly configured this param
            if not custom.get("enabled", True):
                continue  # User disabled this param

            # Override ranges
            merged = {**spec}
            if "low" in custom:
                merged["low"] = custom["low"]
            if "high" in custom:
                merged["high"] = custom["high"]
            if "step" in custom:
                merged["step"] = custom["step"]
            active.append(merged)
        else:
            # Default: include if not custom_ranges present (means user didn't filter)
            # If custom_ranges is provided, only include params that are in it
            pass  # Skip — user selected specific params to optimize

    return active


# =============================================================================
# SINGLE BACKTEST WITH BUILDER ADAPTER
# =============================================================================


def run_builder_backtest(
    graph: dict[str, Any],
    ohlcv: pd.DataFrame,
    config_params: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Run a single backtest using StrategyBuilderAdapter.

    Args:
        graph: Strategy graph (already cloned with modified params).
        ohlcv: OHLCV DataFrame.
        config_params: Dict with symbol, interval, initial_capital, leverage,
                       commission, direction, stop_loss, take_profit, etc.

    Returns:
        Result dict with metrics, or None on failure.
    """
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    try:
        adapter = StrategyBuilderAdapter(graph)
        signals = adapter.generate_signals(ohlcv)

        # Convert SignalResult to numpy arrays
        long_entries = np.asarray(signals.entries.values, dtype=bool)
        long_exits = np.asarray(signals.exits.values, dtype=bool)
        short_entries = (
            np.asarray(signals.short_entries.values, dtype=bool)
            if signals.short_entries is not None
            else np.zeros(len(ohlcv), dtype=bool)
        )
        short_exits = (
            np.asarray(signals.short_exits.values, dtype=bool)
            if signals.short_exits is not None
            else np.zeros(len(ohlcv), dtype=bool)
        )

        # Build BacktestInput
        from backend.optimization.utils import build_backtest_input, extract_metrics_from_output, parse_trade_direction

        direction_str = config_params.get("direction", "both")
        trade_direction = parse_trade_direction(direction_str)

        bt_input = build_backtest_input(
            candles=ohlcv,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            request_params=config_params,
            trade_direction=trade_direction,
            stop_loss_pct=config_params.get("stop_loss_pct", 0),
            take_profit_pct=config_params.get("take_profit_pct", 0),
        )

        # Get engine
        from backend.backtesting.engine_selector import get_engine

        engine_type = config_params.get("engine_type", "numba")
        engine = get_engine(engine_type=engine_type)

        bt_output = engine.run(bt_input)

        if not bt_output.is_valid:
            return None

        result = extract_metrics_from_output(bt_output, win_rate_as_pct=True)
        return result

    except Exception as e:
        logger.warning(f"Builder backtest failed: {e}")
        return None


# =============================================================================
# GRID SEARCH FOR BUILDER STRATEGIES
# =============================================================================


def run_builder_grid_search(
    base_graph: dict[str, Any],
    ohlcv: pd.DataFrame,
    param_combinations: list[dict[str, Any]],
    config_params: dict[str, Any],
    optimize_metric: str = "sharpe_ratio",
    weights: dict[str, float] | None = None,
    max_results: int = 20,
    early_stopping: bool = False,
    early_stopping_patience: int = 20,
    timeout_seconds: int = 3600,
) -> dict[str, Any]:
    """
    Run grid search optimization for a builder strategy.

    Args:
        base_graph: Base strategy graph to clone.
        ohlcv: OHLCV DataFrame.
        param_combinations: List of param_override dicts.
        config_params: Backtest config params.
        optimize_metric: Metric to optimize.
        weights: Metric weights for composite scoring.
        max_results: Max results to return.
        early_stopping: Enable early stopping.
        early_stopping_patience: Patience for early stopping.
        timeout_seconds: Total timeout.

    Returns:
        Dict with optimization results.
    """
    start_time = time.time()
    results: list[dict[str, Any]] = []
    best_score = float("-inf")
    no_improvement_count = 0

    total = len(param_combinations)
    tested = 0

    for i, overrides in enumerate(param_combinations):
        # Timeout check
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            logger.info(f"⏱️ Builder optimization timeout after {elapsed:.0f}s at combo {i}/{total}")
            break

        # Clone graph and apply param overrides
        modified_graph = clone_graph_with_params(base_graph, overrides)

        # Run backtest
        result = run_builder_backtest(modified_graph, ohlcv, config_params)
        tested += 1

        if result is None:
            continue

        # Apply filters
        if not passes_filters(result, config_params):
            continue

        # Calculate score
        score = calculate_composite_score(result, optimize_metric, weights)

        # Build result entry
        entry = {
            "params": overrides,
            "score": score,
            **result,
        }
        results.append(entry)

        # Early stopping
        if score > best_score:
            best_score = score
            no_improvement_count = 0
        else:
            no_improvement_count += 1

        if early_stopping and no_improvement_count >= early_stopping_patience:
            logger.info(f"⏹️ Builder early stopping at combo {i}/{total} (patience={early_stopping_patience})")
            break

    # Sort results
    results.sort(key=lambda r: r["score"], reverse=True)
    top_results = results[:max_results]

    execution_time = time.time() - start_time
    speed = int(tested / max(execution_time, 0.001))

    return {
        "status": "completed",
        "total_combinations": total,
        "tested_combinations": tested,
        "results_found": len(results),
        "top_results": top_results,
        "best_params": top_results[0]["params"] if top_results else {},
        "best_score": top_results[0]["score"] if top_results else 0.0,
        "best_metrics": {k: v for k, v in top_results[0].items() if k not in ("params", "score")}
        if top_results
        else {},
        "execution_time_seconds": round(execution_time, 2),
        "speed_combinations_per_sec": speed,
        "early_stopped": early_stopping and no_improvement_count >= early_stopping_patience,
    }


# =============================================================================
# OPTUNA BAYESIAN SEARCH FOR BUILDER STRATEGIES
# =============================================================================


def run_builder_optuna_search(
    base_graph: dict[str, Any],
    ohlcv: pd.DataFrame,
    param_specs: list[dict[str, Any]],
    config_params: dict[str, Any],
    optimize_metric: str = "sharpe_ratio",
    weights: dict[str, float] | None = None,
    n_trials: int = 100,
    sampler_type: str = "tpe",
    top_n: int = 10,
    timeout_seconds: int = 3600,
) -> dict[str, Any]:
    """
    Run Optuna Bayesian optimization for a builder strategy.

    Args:
        base_graph: Base strategy graph.
        ohlcv: OHLCV DataFrame.
        param_specs: Active param specs with ranges.
        config_params: Backtest config params.
        optimize_metric: Metric to maximize.
        weights: Metric weights for composite scoring.
        n_trials: Number of Optuna trials.
        sampler_type: "tpe", "random", or "cmaes".
        top_n: Number of top results to re-run for full metrics.
        timeout_seconds: Total timeout.

    Returns:
        Dict with optimization results.
    """
    try:
        import optuna
        from optuna.samplers import CmaEsSampler, RandomSampler, TPESampler
    except ImportError:
        logger.error("Optuna not installed. Install with: pip install optuna")
        return {
            "status": "error",
            "error": "Optuna not installed",
            "total_combinations": 0,
            "tested_combinations": 0,
            "top_results": [],
            "best_params": {},
            "best_score": 0.0,
            "best_metrics": {},
            "execution_time_seconds": 0.0,
        }

    start_time = time.time()

    # Choose sampler
    sampler: BaseSampler
    if sampler_type == "random":
        sampler = RandomSampler(seed=42)
    elif sampler_type == "cmaes":
        sampler = CmaEsSampler(seed=42)  # type: ignore[assignment]
    else:
        sampler = TPESampler(seed=42, n_startup_trials=min(10, n_trials // 3))  # type: ignore[assignment]

    # Suppress Optuna logging
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    # Create study
    study = optuna.create_study(
        direction="maximize",
        sampler=sampler,
        study_name=f"builder_opt_{int(time.time())}",
    )

    def objective(trial: optuna.Trial) -> float:
        """Optuna objective function for builder strategy."""
        # Suggest parameters
        overrides: dict[str, Any] = {}
        for spec in param_specs:
            path = spec["param_path"]
            if spec["type"] == "int":
                val: int | float = trial.suggest_int(path, int(spec["low"]), int(spec["high"]), step=int(spec["step"]))
                overrides[path] = val
            else:
                val = trial.suggest_float(path, float(spec["low"]), float(spec["high"]), step=float(spec["step"]))
                overrides[path] = val

        # Clone graph and run backtest
        modified_graph = clone_graph_with_params(base_graph, overrides)
        result = run_builder_backtest(modified_graph, ohlcv, config_params)

        if result is None:
            return float("-inf")

        if not passes_filters(result, config_params):
            return float("-inf")

        return calculate_composite_score(result, optimize_metric, weights)

    # Run optimization
    study.optimize(
        objective,
        n_trials=n_trials,
        timeout=timeout_seconds,
        show_progress_bar=False,
    )

    # Collect top-N trials
    completed_trials = [
        t
        for t in study.trials
        if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None and t.value > float("-inf")
    ]
    completed_trials.sort(key=lambda t: t.value if t.value is not None else 0.0, reverse=True)  # type: ignore[arg-type]
    top_trials = completed_trials[:top_n]

    # Re-run top-N for full metrics
    top_results: list[dict[str, Any]] = []
    for trial in top_trials:
        overrides = trial.params
        modified_graph = clone_graph_with_params(base_graph, overrides)
        result = run_builder_backtest(modified_graph, ohlcv, config_params)

        if result is not None:
            score = calculate_composite_score(result, optimize_metric, weights)
            top_results.append(
                {
                    "params": overrides,
                    "score": score,
                    "trial_number": trial.number,
                    **result,
                }
            )

    # Sort by score
    top_results.sort(key=lambda r: r["score"], reverse=True)

    execution_time = time.time() - start_time

    return {
        "status": "completed",
        "method": "optuna",
        "sampler": sampler_type,
        "total_combinations": n_trials,
        "tested_combinations": len(completed_trials),
        "results_found": len(top_results),
        "top_results": top_results,
        "best_params": top_results[0]["params"] if top_results else {},
        "best_score": top_results[0]["score"] if top_results else 0.0,
        "best_metrics": {k: v for k, v in top_results[0].items() if k not in ("params", "score", "trial_number")}
        if top_results
        else {},
        "execution_time_seconds": round(execution_time, 2),
        "speed_combinations_per_sec": int(len(completed_trials) / max(execution_time, 0.001)),
        "early_stopped": False,
    }
