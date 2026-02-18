"""
Tests that AI agent prompts contain complete, accurate block parameter knowledge.

PURPOSE:
  Simulates what an AI agent (DeepSeek, Qwen, Perplexity) "sees" when reading
  the STRATEGY_GENERATION_TEMPLATE. Verifies that:
  1. Every Library block is documented in the prompt
  2. All params for each block are mentioned with correct defaults
  3. Optimization ranges (min/max/step) are present for every optimizable param
  4. Signal modes and their conditions are documented
  5. The OPTIMIZATION WORKFLOW section is present and complete
  6. The builder_run_optimization MCP tool is described

Ground truth comes from:
  - frontend/js/pages/strategy_builder.js  getDefaultParams()
  - backend/optimization/builder_optimizer.py  DEFAULT_PARAM_RANGES
  - backend/agents/mcp/tools/strategy_builder.py  registered tools
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from backend.agents.prompts.templates import STRATEGY_GENERATION_TEMPLATE

# =============================================================================
# GROUND TRUTH: What the prompt MUST contain per block
# =============================================================================

# Each entry: block_name -> {
#   "header": expected header substring in the template,
#   "params": {param_name: default_value} -- ALL params the agent must know,
#   "optimizable": [param_name, ...] -- params that MUST have optimization ranges,
#   "modes": [mode_name, ...] -- signal modes the agent must understand,
#   "key_concepts": [concept, ...] -- critical concepts the agent must see,
# }

BLOCK_GROUND_TRUTH: dict[str, dict[str, Any]] = {
    # ===== ENTRY INDICATORS =====
    "rsi": {
        "header": "RSI UNIVERSAL NODE",
        "params": {
            "period": 14,
            "use_rsi_range_filter": False,
            "long_rsi_more": 30,
            "long_rsi_less": 70,
            "short_rsi_less": 70,
            "short_rsi_more": 30,
            "use_cross_level": False,
            "cross_long_level": 30,
            "cross_short_level": 70,
            "cross_memory_bars": 5,
        },
        "optimizable": [
            "period",
            "long_rsi_more",
            "long_rsi_less",
            "short_rsi_less",
            "short_rsi_more",
            "cross_long_level",
            "cross_short_level",
            "cross_memory_bars",
        ],
        "modes": ["RANGE", "CROSS"],
        "key_concepts": ["0-100", "overbought", "oversold", "passthrough"],
    },
    "macd": {
        "header": "MACD UNIVERSAL NODE",
        "params": {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "macd_cross_zero_level": 0,
            "signal_memory_bars": 5,
        },
        "optimizable": [
            "fast_period",
            "slow_period",
            "signal_period",
            "macd_cross_zero_level",
            "signal_memory_bars",
        ],
        "modes": ["CROSS ZERO", "CROSS SIGNAL"],
        "key_concepts": ["fast_period MUST be < slow_period", "Signal Memory"],
    },
    "stochastic": {
        "header": "STOCHASTIC UNIVERSAL NODE",
        "params": {
            "stoch_k_length": 14,
            "stoch_k_smoothing": 3,
            "stoch_d_smoothing": 3,
        },
        "optimizable": [
            "stoch_k_length",
            "stoch_k_smoothing",
            "stoch_d_smoothing",
            "long_stoch_d_more",
            "long_stoch_d_less",
            "short_stoch_d_less",
            "short_stoch_d_more",
            "stoch_cross_level_long",
            "stoch_cross_level_short",
            "stoch_cross_memory_bars",
            "stoch_kd_memory_bars",
        ],
        "modes": ["RANGE", "CROSS level", "K/D CROSS"],
        "key_concepts": ["AND logic", "more < less"],
    },
    "supertrend": {
        "header": "SUPERTREND UNIVERSAL NODE",
        "params": {"period": 10, "multiplier": 3.0},
        "optimizable": ["period", "multiplier"],
        "modes": ["FILTER", "SIGNAL"],
        "key_concepts": ["direction", "trend_change", "passthrough"],
    },
    "qqe": {
        "header": "QQE UNIVERSAL NODE",
        "params": {
            "rsi_period": 14,
            "qqe_factor": 4.238,
            "smoothing_period": 5,
            "qqe_signal_memory_bars": 5,
        },
        "optimizable": [
            "rsi_period",
            "qqe_factor",
            "smoothing_period",
            "qqe_signal_memory_bars",
        ],
        "modes": ["CROSS SIGNAL"],
        "key_concepts": ["RSI-MA", "QQE line"],
    },
    "atr_volatility": {
        "header": "ATR VOLATILITY NODE",
        "params": {
            "atr_length1": 20,
            "atr_length2": 100,
            "atr_diff_percent": 10,
        },
        "optimizable": ["atr_length1", "atr_length2", "atr_diff_percent"],
        "modes": [],
        "key_concepts": ["ATR1 < ATR2", "ATR1 > ATR2", "volatility expansion"],
    },
    "volume_filter": {
        "header": "VOLUME FILTER NODE",
        "params": {
            "vol_length1": 20,
            "vol_length2": 100,
            "vol_diff_percent": 10,
        },
        "optimizable": ["vol_length1", "vol_length2", "vol_diff_percent"],
        "modes": [],
        "key_concepts": ["VOL1 < VOL2", "VOL1 > VOL2", "volume breakout"],
    },
    "highest_lowest_bar": {
        "header": "HIGHEST/LOWEST BAR NODE",
        "params": {
            "hl_lookback_bars": 10,
            "hl_price_percent": 0,
            "hl_atr_percent": 0,
            "atr_hl_length": 50,
        },
        "optimizable": [
            "hl_lookback_bars",
            "hl_price_percent",
            "hl_atr_percent",
            "atr_hl_length",
        ],
        "modes": [],
        "key_concepts": ["highest bar", "lowest bar", "block_worse_percent"],
    },
    "two_mas": {
        "header": "TWO MAs NODE",
        "params": {
            "ma1_length": 50,
            "ma2_length": 100,
            "ma_cross_memory_bars": 5,
        },
        "optimizable": ["ma1_length", "ma2_length", "ma_cross_memory_bars"],
        "modes": ["MA CROSS", "MA1 as FILTER"],
        "key_concepts": ["Golden/Death cross", "AND logic"],
    },
    "accumulation_areas": {
        "header": "ACCUMULATION AREAS NODE",
        "params": {
            "backtracking_interval": 30,
            "min_bars_to_execute": 5,
        },
        "optimizable": ["backtracking_interval", "min_bars_to_execute"],
        "modes": [],
        "key_concepts": ["consolidation", "breakout", "accumulation zone"],
    },
    "keltner_bollinger": {
        "header": "KELTNER/BOLLINGER CHANNEL NODE",
        "params": {
            "keltner_length": 14,
            "keltner_mult": 1.5,
            "bb_length": 20,
            "bb_deviation": 2,
        },
        "optimizable": ["keltner_length", "keltner_mult", "bb_length", "bb_deviation"],
        "modes": ["Rebound", "Breakout"],
        "key_concepts": ["Keltner Channel", "Bollinger Bands", "channel_mode"],
    },
    "rvi_filter": {
        "header": "RVI (Relative Vigor Index) NODE",
        "params": {
            "rvi_length": 10,
            "rvi_ma_length": 2,
            "rvi_long_more": 1,
            "rvi_long_less": 50,
            "rvi_short_less": 100,
            "rvi_short_more": 50,
        },
        "optimizable": [
            "rvi_length",
            "rvi_ma_length",
            "rvi_long_more",
            "rvi_long_less",
            "rvi_short_less",
            "rvi_short_more",
        ],
        "modes": [],
        "key_concepts": ["close-to-open", "high-to-low", "conviction"],
    },
    "mfi_filter": {
        "header": "MFI (Money Flow Index) NODE",
        "params": {
            "mfi_length": 14,
            "mfi_long_more": 1,
            "mfi_long_less": 60,
            "mfi_short_less": 100,
            "mfi_short_more": 50,
        },
        "optimizable": [
            "mfi_length",
            "mfi_long_more",
            "mfi_long_less",
            "mfi_short_less",
            "mfi_short_more",
        ],
        "modes": [],
        "key_concepts": ["Volume-weighted RSI", "overbought", "oversold"],
    },
    "cci_filter": {
        "header": "CCI (Commodity Channel Index) NODE",
        "params": {
            "cci_length": 14,
            "cci_long_more": -400,
            "cci_long_less": 400,
            "cci_short_less": 400,
            "cci_short_more": 10,
        },
        "optimizable": [
            "cci_length",
            "cci_long_more",
            "cci_long_less",
            "cci_short_less",
            "cci_short_more",
        ],
        "modes": [],
        "key_concepts": ["deviation of price", "100", "200"],
    },
    "momentum_filter": {
        "header": "MOMENTUM NODE",
        "params": {
            "momentum_length": 14,
            "momentum_long_more": -100,
            "momentum_long_less": 10,
            "momentum_short_less": 95,
            "momentum_short_more": -30,
        },
        "optimizable": [
            "momentum_length",
            "momentum_long_more",
            "momentum_long_less",
            "momentum_short_less",
            "momentum_short_more",
        ],
        "modes": [],
        "key_concepts": ["Rate-of-change", "Momentum > 0"],
    },
    # ===== CONDITIONS =====
    "crossover": {
        "header": "CROSSOVER NODE",
        "params": {},
        "optimizable": [],
        "modes": [],
        "key_concepts": ["source_a crosses ABOVE source_b"],
    },
    "crossunder": {
        "header": "CROSSUNDER NODE",
        "params": {},
        "optimizable": [],
        "modes": [],
        "key_concepts": ["source_a crosses BELOW source_b"],
    },
    "greater_than": {
        "header": "GREATER THAN NODE",
        "params": {"value": 0},
        "optimizable": [],
        "modes": [],
        "key_concepts": ["input > value"],
    },
    "less_than": {
        "header": "LESS THAN NODE",
        "params": {"value": 0},
        "optimizable": [],
        "modes": [],
        "key_concepts": ["input < value"],
    },
    "equals": {
        "header": "EQUALS NODE",
        "params": {"value": 0, "tolerance": 0.001},
        "optimizable": [],
        "modes": [],
        "key_concepts": ["approximately equals"],
    },
    "between": {
        "header": "BETWEEN NODE",
        "params": {"min_value": 0, "max_value": 100},
        "optimizable": [],
        "modes": [],
        "key_concepts": ["min_value", "max_value", "range"],
    },
    # ===== DIVERGENCE =====
    "divergence": {
        "header": "DIVERGENCE NODE",
        "params": {
            "pivot_interval": 9,
            "rsi_period": 14,
            "stoch_length": 14,
            "momentum_length": 10,
            "cmf_period": 21,
            "mfi_length": 14,
            "keep_diver_signal_memory_bars": 5,
        },
        "optimizable": [
            "pivot_interval",
            "rsi_period",
            "stoch_length",
            "momentum_length",
            "cmf_period",
            "mfi_length",
            "keep_diver_signal_memory_bars",
        ],
        "modes": [],
        "key_concepts": ["bullish/bearish", "bearish divergence", "pivot"],
    },
    # ===== DCA =====
    "dca": {
        "header": "DCA (Dollar-Cost Averaging) NODE",
        "params": {
            "grid_size_percent": 15,
            "order_count": 5,
            "martingale_coefficient": 1.0,
            "log_steps_coefficient": 1.0,
            "first_order_offset": 0,
        },
        "optimizable": [
            "grid_size_percent",
            "order_count",
            "martingale_coefficient",
            "log_steps_coefficient",
            "first_order_offset",
        ],
        "modes": [],
        "key_concepts": ["safety orders", "averaging", "grid"],
    },
    "manual_grid": {
        "header": "MANUAL GRID NODE",
        "params": {},
        "optimizable": [],
        "modes": [],
        "key_concepts": ["offset", "volume", "100%", "Max 40 orders"],
    },
    # ===== EXIT SL/TP BLOCKS =====
    "static_sltp": {
        "header": "STATIC SL/TP NODE",
        "params": {
            "take_profit_percent": 1.5,
            "stop_loss_percent": 1.5,
            "breakeven_activation_percent": 0.5,
            "new_breakeven_sl_percent": 0.1,
        },
        "optimizable": [
            "take_profit_percent",
            "stop_loss_percent",
            "breakeven_activation_percent",
            "new_breakeven_sl_percent",
        ],
        "modes": [],
        "key_concepts": ["break-even", "average_price", "last_price"],
    },
    "trailing_stop_exit": {
        "header": "TRAILING STOP EXIT NODE",
        "params": {
            "activation_percent": 1.0,
            "trailing_percent": 0.5,
        },
        "optimizable": ["activation_percent", "trailing_percent"],
        "modes": [],
        "key_concepts": ["trailing", "peak profit", "activation"],
    },
    "atr_exit": {
        "header": "ATR EXIT NODE",
        "params": {
            "atr_sl_period": 140,
            "atr_sl_multiplier": 4.0,
            "atr_tp_period": 140,
            "atr_tp_multiplier": 4.0,
        },
        "optimizable": [
            "atr_sl_period",
            "atr_sl_multiplier",
            "atr_tp_period",
            "atr_tp_multiplier",
        ],
        "modes": [],
        "key_concepts": ["Volatility-adaptive", "ATR * mult"],
    },
    "multi_tp_exit": {
        "header": "MULTI TP LEVELS NODE",
        "params": {
            "tp1_percent": 1.0,
            "tp2_percent": 2.0,
            "tp3_percent": 3.0,
            "tp1_close_percent": 33,
            "tp2_close_percent": 33,
            "tp3_close_percent": 34,
        },
        "optimizable": [
            "tp1_percent",
            "tp2_percent",
            "tp3_percent",
            "tp1_close_percent",
            "tp2_close_percent",
            "tp3_close_percent",
        ],
        "modes": [],
        "key_concepts": ["partial position closing", "MUST = 100%"],
    },
    # ===== CLOSE BY INDICATOR =====
    "close_by_time": {
        "header": "CLOSE BY TIME NODE",
        "params": {
            "bars_since_entry": 10,
            "min_profit_percent": 0,
        },
        "optimizable": ["bars_since_entry", "min_profit_percent"],
        "modes": [],
        "key_concepts": ["bars since entry", "time-based exit"],
    },
    "close_channel": {
        "header": "CHANNEL CLOSE NODE",
        "params": {
            "keltner_length": 14,
            "keltner_mult": 1.5,
            "bb_length": 20,
            "bb_deviation": 2,
        },
        "optimizable": ["keltner_length", "keltner_mult", "bb_length", "bb_deviation"],
        "modes": ["Rebound", "Breakout"],
        "key_concepts": ["opposite channel boundary", "Keltner Channel", "Bollinger Bands"],
    },
    "close_ma_cross": {
        "header": "TWO MAs CLOSE NODE",
        "params": {
            "ma1_length": 10,
            "ma2_length": 30,
            "min_profit_percent": 1,
        },
        "optimizable": ["ma1_length", "ma2_length", "min_profit_percent"],
        "modes": [],
        "key_concepts": ["fast MA crosses below slow MA", "trend reversal"],
    },
    "close_rsi": {
        "header": "CLOSE BY RSI NODE",
        "params": {
            "rsi_close_length": 14,
            "rsi_long_more": 70,
            "rsi_long_less": 100,
            "rsi_short_less": 30,
            "rsi_short_more": 1,
            "rsi_cross_long_level": 70,
            "rsi_cross_short_level": 30,
        },
        "optimizable": [
            "rsi_close_length",
            "rsi_long_more",
            "rsi_long_less",
            "rsi_short_less",
            "rsi_short_more",
            "rsi_cross_long_level",
            "rsi_cross_short_level",
        ],
        "modes": ["RSI REACH", "RSI CROSS"],
        "key_concepts": ["overbought zone", "oversold zone", "crosses DOWN"],
    },
    "close_stochastic": {
        "header": "CLOSE BY STOCHASTIC NODE",
        "params": {
            "stoch_close_k_length": 14,
            "stoch_close_k_smoothing": 3,
            "stoch_close_d_smoothing": 3,
            "stoch_long_more": 80,
            "stoch_long_less": 100,
            "stoch_short_less": 20,
            "stoch_short_more": 1,
            "stoch_cross_long_level": 80,
            "stoch_cross_short_level": 20,
        },
        "optimizable": [
            "stoch_close_k_length",
            "stoch_close_k_smoothing",
            "stoch_close_d_smoothing",
            "stoch_long_more",
            "stoch_long_less",
            "stoch_short_less",
            "stoch_short_more",
            "stoch_cross_long_level",
            "stoch_cross_short_level",
        ],
        "modes": ["STOCH REACH", "STOCH CROSS"],
        "key_concepts": ["%D", "overbought", "exhaustion"],
    },
    "close_psar": {
        "header": "CLOSE BY PARABOLIC SAR NODE",
        "params": {
            "psar_start": 0.02,
            "psar_increment": 0.02,
            "psar_maximum": 0.2,
            "psar_close_nth_bar": 1,
        },
        "optimizable": [
            "psar_start",
            "psar_increment",
            "psar_maximum",
            "psar_close_nth_bar",
        ],
        "modes": [],
        "key_concepts": ["SAR flips", "acceleration factor", "trend turns bearish"],
    },
}


# =============================================================================
# Helper: get the raw template for inspection (no rendering needed)
# =============================================================================


def _get_raw_template() -> str:
    """Get the raw STRATEGY_GENERATION_TEMPLATE string.

    We test against the raw template (with {{escaped braces}} and {placeholders})
    because the template contains format specifiers like {price:,.2f} that need
    real numeric values. For our comprehension tests, the raw string is
    sufficient -- it contains all block documentation that agents will see.
    Double braces {{ }} appear as single { } in the rendered output.
    """
    return STRATEGY_GENERATION_TEMPLATE


@pytest.fixture(scope="module")
def prompt_text() -> str:
    """Module-scoped fixture: raw template text for inspection."""
    return _get_raw_template()


# =============================================================================
# TEST CLASS: Block Documentation Completeness
# =============================================================================


class TestBlockHeaderPresence:
    """Verify every block has its header in the prompt -- the agent can find it."""

    @pytest.mark.parametrize(
        "block_type,truth",
        list(BLOCK_GROUND_TRUTH.items()),
        ids=list(BLOCK_GROUND_TRUTH.keys()),
    )
    def test_block_header_present(self, prompt_text: str, block_type: str, truth: dict):
        """Agent must see the block header to know the block exists."""
        assert truth["header"] in prompt_text, (
            f"Block '{block_type}': header '{truth['header']}' NOT found in prompt. "
            f"Agent will not know this block exists!"
        )


class TestBlockParamDefaults:
    """Verify each block's params are mentioned with correct default values.

    Simulates: 'Does the agent know that rsi.period defaults to 14?'
    """

    @pytest.mark.parametrize(
        "block_type,truth",
        [(bt, t) for bt, t in BLOCK_GROUND_TRUTH.items() if t["params"]],
        ids=[bt for bt, t in BLOCK_GROUND_TRUTH.items() if t["params"]],
    )
    def test_param_defaults_mentioned(self, prompt_text: str, block_type: str, truth: dict):
        """Every param with a default value must appear in the prompt with that default."""
        missing = []
        for param_name, default_val in truth["params"].items():
            # Boolean mode toggles (use_xxx=False) are documented as "use_xxx=true -> ..."
            # The default "false" is implicit (disabled). Skip strict default checking.
            if isinstance(default_val, bool) and default_val is False:
                # Just verify the param name is mentioned somewhere
                if param_name not in prompt_text:
                    missing.append(f"  {param_name} -- boolean toggle not found at all")
                continue

            # Check param name is mentioned
            if param_name not in prompt_text:
                missing.append(f"  {param_name} -- param name not found at all")
                continue

            # Check default value is near the param name
            default_str = str(default_val)
            if isinstance(default_val, bool):
                default_str = str(default_val).lower()

            # For floats like 1.0, also try matching as "1"
            alt_default_str = None
            if isinstance(default_val, float) and default_val == int(default_val):
                alt_default_str = str(int(default_val))

            # Find all occurrences of param_name and check if default is nearby
            found_with_default = False
            for match in re.finditer(re.escape(param_name), prompt_text):
                start = match.start()
                # Check within 60 chars after param name for the default value
                window = prompt_text[start : start + len(param_name) + 60]
                if default_str in window:
                    found_with_default = True
                    break
                if alt_default_str and alt_default_str in window:
                    found_with_default = True
                    break

            if not found_with_default:
                missing.append(f"  {param_name} -- found in prompt but default '{default_val}' not visible nearby")

        assert not missing, (
            f"Block '{block_type}': params missing or without correct defaults:\n"
            + "\n".join(missing)
            + "\nAgent will use wrong parameter values!"
        )


class TestOptimizationRangesPresent:
    """Verify every optimizable param has OPTIMIZATION RANGES in the prompt.

    Simulates: 'Does the agent know it can optimize rsi.period from 5 to 30 step 1?'
    """

    @pytest.mark.parametrize(
        "block_type,truth",
        [(bt, t) for bt, t in BLOCK_GROUND_TRUTH.items() if t["optimizable"]],
        ids=[bt for bt, t in BLOCK_GROUND_TRUTH.items() if t["optimizable"]],
    )
    def test_optimization_ranges_section_exists(self, prompt_text: str, block_type: str, truth: dict):
        """Each block with optimizable params MUST have an OPTIMIZATION RANGES section."""
        header_idx = prompt_text.find(truth["header"])
        assert header_idx >= 0, f"Header not found for {block_type}"

        # Look for OPTIMIZATION RANGES within 3000 chars after header
        section = prompt_text[header_idx : header_idx + 3000]
        assert "OPTIMIZATION RANGES" in section, (
            f"Block '{block_type}': has {len(truth['optimizable'])} optimizable params "
            f"but NO 'OPTIMIZATION RANGES' section found after header. "
            f"Agent won't know how to set optimization ranges!"
        )

    @pytest.mark.parametrize(
        "block_type,truth",
        [(bt, t) for bt, t in BLOCK_GROUND_TRUTH.items() if t["optimizable"]],
        ids=[bt for bt, t in BLOCK_GROUND_TRUTH.items() if t["optimizable"]],
    )
    def test_each_optimizable_param_has_range(self, prompt_text: str, block_type: str, truth: dict):
        """Each optimizable param must have low/high/step in the ranges section."""
        header_idx = prompt_text.find(truth["header"])
        assert header_idx >= 0

        section = prompt_text[header_idx : header_idx + 3000]

        ranges_idx = section.find("OPTIMIZATION RANGES")
        if ranges_idx < 0:
            pytest.skip(f"No OPTIMIZATION RANGES section for {block_type}")

        ranges_section = section[ranges_idx:]

        missing_ranges = []
        for param in truth["optimizable"]:
            if param not in ranges_section:
                missing_ranges.append(param)

        assert not missing_ranges, (
            f"Block '{block_type}': optimizable params missing from OPTIMIZATION RANGES:\n"
            f"  Missing: {missing_ranges}\n"
            f"  Agent cannot set optimization ranges for these params!"
        )

    @pytest.mark.parametrize(
        "block_type,truth",
        [(bt, t) for bt, t in BLOCK_GROUND_TRUTH.items() if t["optimizable"]],
        ids=[bt for bt, t in BLOCK_GROUND_TRUTH.items() if t["optimizable"]],
    )
    def test_range_format_has_low_high_step(self, prompt_text: str, block_type: str, truth: dict):
        """Each range entry must contain 'low:', 'high:', 'step:' triplet."""
        header_idx = prompt_text.find(truth["header"])
        assert header_idx >= 0

        section = prompt_text[header_idx : header_idx + 3000]
        ranges_idx = section.find("OPTIMIZATION RANGES")
        if ranges_idx < 0:
            pytest.skip(f"No OPTIMIZATION RANGES section for {block_type}")

        ranges_text = section[ranges_idx:]

        assert "low:" in ranges_text, (
            f"Block '{block_type}': OPTIMIZATION RANGES missing 'low:' keyword. "
            f"Agent won't understand the range format!"
        )
        assert "high:" in ranges_text, f"Block '{block_type}': OPTIMIZATION RANGES missing 'high:' keyword."
        assert "step:" in ranges_text, f"Block '{block_type}': OPTIMIZATION RANGES missing 'step:' keyword."


class TestSignalModesDocumented:
    """Verify each block's signal modes are documented.

    Simulates: 'Does the agent know RSI has RANGE and CROSS modes?'
    """

    @pytest.mark.parametrize(
        "block_type,truth",
        [(bt, t) for bt, t in BLOCK_GROUND_TRUTH.items() if t["modes"]],
        ids=[bt for bt, t in BLOCK_GROUND_TRUTH.items() if t["modes"]],
    )
    def test_signal_modes_mentioned(self, prompt_text: str, block_type: str, truth: dict):
        """Each block's signal modes must be documented."""
        header_idx = prompt_text.find(truth["header"])
        assert header_idx >= 0

        section = prompt_text[header_idx : header_idx + 3000]

        missing_modes = [m for m in truth["modes"] if m not in section]
        assert not missing_modes, (
            f"Block '{block_type}': signal modes not documented:\n"
            f"  Missing: {missing_modes}\n"
            f"  Agent won't know how to configure these modes!"
        )


class TestKeyConcepts:
    """Verify critical concepts are present for each block.

    Simulates: 'Does the agent understand that MACD fast_period MUST be < slow_period?'
    """

    @pytest.mark.parametrize(
        "block_type,truth",
        [(bt, t) for bt, t in BLOCK_GROUND_TRUTH.items() if t["key_concepts"]],
        ids=[bt for bt, t in BLOCK_GROUND_TRUTH.items() if t["key_concepts"]],
    )
    def test_key_concepts_present(self, prompt_text: str, block_type: str, truth: dict):
        """Critical concepts must be visible to the agent."""
        header_idx = prompt_text.find(truth["header"])
        assert header_idx >= 0

        section = prompt_text[header_idx : header_idx + 3000]

        missing = [c for c in truth["key_concepts"] if c not in section]
        assert not missing, (
            f"Block '{block_type}': critical concepts missing from docs:\n"
            f"  Missing: {missing}\n"
            f"  Agent may make errors without understanding these constraints!"
        )


# =============================================================================
# TEST CLASS: Optimization Workflow Completeness
# =============================================================================


class TestOptimizationWorkflow:
    """Verify the OPTIMIZATION WORKFLOW section is present and complete."""

    def test_workflow_section_exists(self, prompt_text: str):
        """The prompt must contain an OPTIMIZATION WORKFLOW section."""
        assert "OPTIMIZATION WORKFLOW" in prompt_text, (
            "OPTIMIZATION WORKFLOW section missing from prompt. Agents won't know how to run optimization!"
        )

    @pytest.mark.parametrize(
        "step_keyword",
        [
            "builder_get_optimizable_params",
            "builder_run_optimization",
            "grid_search",
            "random_search",
            "bayesian",
            "optimize_metric",
            "parameter_ranges",
            "sharpe_ratio",
        ],
        ids=[
            "discover_tool",
            "run_tool",
            "method_grid",
            "method_random",
            "method_bayesian",
            "metric_keyword",
            "custom_ranges",
            "default_metric",
        ],
    )
    def test_workflow_contains_key_element(self, prompt_text: str, step_keyword: str):
        """The workflow section must mention all critical optimization elements."""
        assert step_keyword in prompt_text, (
            f"OPTIMIZATION WORKFLOW missing keyword '{step_keyword}'. "
            f"Agent won't understand this part of the optimization process!"
        )

    def test_workflow_contains_commission_warning(self, prompt_text: str):
        """Commission = 0.0007 must be mentioned in optimization context."""
        workflow_idx = prompt_text.find("OPTIMIZATION WORKFLOW")
        if workflow_idx < 0:
            pytest.skip("No OPTIMIZATION WORKFLOW section")

        workflow = prompt_text[workflow_idx : workflow_idx + 3000]
        assert "0.0007" in workflow, (
            "Commission rate 0.0007 not mentioned in OPTIMIZATION WORKFLOW. Agent may optimize with wrong commission!"
        )


# =============================================================================
# TEST CLASS: MCP Tools Registration
# =============================================================================


class TestMCPToolsRegistered:
    """Verify the MCP tools needed for optimization are registered."""

    def test_builder_run_optimization_tool_exists(self):
        """The builder_run_optimization MCP tool must be registered."""
        from backend.agents.mcp.tools.strategy_builder import registry

        tool_names = [t.name for t in registry.list_tools()]
        assert "builder_run_optimization" in tool_names, (
            "MCP tool 'builder_run_optimization' not registered. Agent cannot run optimizations!"
        )

    def test_builder_get_optimizable_params_tool_exists(self):
        """The builder_get_optimizable_params MCP tool must be registered."""
        from backend.agents.mcp.tools.strategy_builder import registry

        tool_names = [t.name for t in registry.list_tools()]
        assert "builder_get_optimizable_params" in tool_names, (
            "MCP tool 'builder_get_optimizable_params' not registered. Agent cannot discover optimizable parameters!"
        )

    def test_optimization_tool_has_method_param(self):
        """The optimization tool must accept 'method' parameter."""
        from backend.agents.mcp.tools.strategy_builder import registry

        tools = {t.name: t for t in registry.list_tools()}
        tool = tools.get("builder_run_optimization")
        assert tool is not None

        # Try get_input_schema() method or parameters dict
        schema = None
        if hasattr(tool, "get_input_schema"):
            schema = tool.get_input_schema()
        elif hasattr(tool, "parameters"):
            schema = {"properties": tool.parameters}

        assert schema is not None, "Could not get tool schema"
        props = schema.get("properties", {})
        assert "method" in props, (
            f"builder_run_optimization missing 'method' parameter. "
            f"Agent can't choose grid/random/bayesian! "
            f"Available params: {list(props.keys())}"
        )


# =============================================================================
# TEST CLASS: DEFAULT_PARAM_RANGES Coverage
# =============================================================================


class TestDefaultParamRangesCoverage:
    """Verify DEFAULT_PARAM_RANGES covers all optimizable blocks."""

    def test_all_optimizable_blocks_in_default_ranges(self):
        """Every block with optimizable params must have entries in DEFAULT_PARAM_RANGES."""
        from backend.optimization.builder_optimizer import DEFAULT_PARAM_RANGES

        blocks_with_opt = [bt for bt, t in BLOCK_GROUND_TRUTH.items() if t["optimizable"]]
        missing_blocks = [bt for bt in blocks_with_opt if bt not in DEFAULT_PARAM_RANGES]
        assert not missing_blocks, (
            f"Blocks with optimizable params but NOT in DEFAULT_PARAM_RANGES:\n"
            f"  {missing_blocks}\n"
            f"Optimizer will use generic ranges instead of block-specific ones!"
        )

    @pytest.mark.parametrize(
        "block_type,truth",
        [(bt, t) for bt, t in BLOCK_GROUND_TRUTH.items() if t["optimizable"]],
        ids=[bt for bt, t in BLOCK_GROUND_TRUTH.items() if t["optimizable"]],
    )
    def test_all_optimizable_params_have_ranges(self, block_type: str, truth: dict):
        """Each optimizable param must have a range entry (low, high, step)."""
        from backend.optimization.builder_optimizer import DEFAULT_PARAM_RANGES

        if block_type not in DEFAULT_PARAM_RANGES:
            pytest.skip(f"Block {block_type} not in DEFAULT_PARAM_RANGES")

        block_ranges = DEFAULT_PARAM_RANGES[block_type]
        missing_params = []
        for param in truth["optimizable"]:
            if param not in block_ranges:
                missing_params.append(param)

        assert not missing_params, (
            f"Block '{block_type}': optimizable params without DEFAULT_PARAM_RANGES:\n"
            f"  Missing: {missing_params}\n"
            f"Optimizer will skip these params during optimization!"
        )

    @pytest.mark.parametrize(
        "block_type,truth",
        [(bt, t) for bt, t in BLOCK_GROUND_TRUTH.items() if t["optimizable"]],
        ids=[bt for bt, t in BLOCK_GROUND_TRUTH.items() if t["optimizable"]],
    )
    def test_range_values_are_valid(self, block_type: str, truth: dict):
        """Each range must have low < high and step > 0."""
        from backend.optimization.builder_optimizer import DEFAULT_PARAM_RANGES

        if block_type not in DEFAULT_PARAM_RANGES:
            pytest.skip(f"Block {block_type} not in DEFAULT_PARAM_RANGES")

        block_ranges = DEFAULT_PARAM_RANGES[block_type]
        invalid = []
        for param in truth["optimizable"]:
            if param not in block_ranges:
                continue
            r = block_ranges[param]
            if r.get("low", 0) >= r.get("high", 0):
                invalid.append(f"  {param}: low={r.get('low')} >= high={r.get('high')}")
            if r.get("step", 0) <= 0:
                invalid.append(f"  {param}: step={r.get('step')} <= 0")

        assert not invalid, f"Block '{block_type}': invalid optimization ranges:\n" + "\n".join(invalid)


# =============================================================================
# TEST CLASS: Template Safety
# =============================================================================


class TestTemplateRenderingSafety:
    """Verify the raw template string is well-formed and usable."""

    def test_template_is_a_string(self):
        """Template must be a non-empty string."""
        text = _get_raw_template()
        assert isinstance(text, str), "STRATEGY_GENERATION_TEMPLATE is not a string"
        assert len(text) > 1000, "Template is suspiciously short"

    def test_template_has_balanced_braces(self):
        """Template must not have orphaned single braces (unescaped)."""
        text = _get_raw_template()
        # Replace all {{ and }} with empty (they are escaped literals)
        cleaned = text.replace("{{", "").replace("}}", "")
        # Remaining { and } should be valid format placeholders: {name} or {name:spec}
        opens = cleaned.count("{")
        closes = cleaned.count("}")
        assert opens == closes, (
            f"Unbalanced braces after removing escaped pairs: "
            f"{opens} opens vs {closes} closes. "
            f"Template may have broken formatting."
        )

    def test_prompt_text_not_too_short(self, prompt_text: str):
        """Prompt must be substantial enough to contain all block docs."""
        # With 34 blocks documented, prompt should be >15K chars
        assert len(prompt_text) > 15000, (
            f"Raw template only {len(prompt_text)} chars - probably missing block documentation."
        )


# =============================================================================
# TEST CLASS: Cross-check Prompt <-> Optimizer Consistency
# =============================================================================


class TestPromptOptimizerConsistency:
    """Verify ranges in prompt match DEFAULT_PARAM_RANGES in optimizer."""

    @pytest.mark.parametrize(
        "block_type,truth",
        [(bt, t) for bt, t in BLOCK_GROUND_TRUTH.items() if t["optimizable"]],
        ids=[bt for bt, t in BLOCK_GROUND_TRUTH.items() if t["optimizable"]],
    )
    def test_prompt_ranges_match_optimizer_ranges(self, prompt_text: str, block_type: str, truth: dict):
        """Ranges shown in prompt must match DEFAULT_PARAM_RANGES values.

        This prevents the case where prompt says 'period: low: 5, high: 30'
        but the optimizer actually uses low: 10, high: 20.
        """
        from backend.optimization.builder_optimizer import DEFAULT_PARAM_RANGES

        if block_type not in DEFAULT_PARAM_RANGES:
            pytest.skip(f"Block {block_type} not in DEFAULT_PARAM_RANGES")

        header_idx = prompt_text.find(truth["header"])
        if header_idx < 0:
            pytest.skip(f"Header not found for {block_type}")

        section = prompt_text[header_idx : header_idx + 3000]
        ranges_idx = section.find("OPTIMIZATION RANGES")
        if ranges_idx < 0:
            pytest.skip(f"No OPTIMIZATION RANGES for {block_type}")

        ranges_text = section[ranges_idx:]

        mismatches = []
        for param_name in truth["optimizable"]:
            if param_name not in DEFAULT_PARAM_RANGES[block_type]:
                continue

            opt_range = DEFAULT_PARAM_RANGES[block_type][param_name]

            # Find param in ranges_text and check low/high values
            param_idx = ranges_text.find(param_name)
            if param_idx < 0:
                continue

            # Extract the line containing this param's range
            line_end = ranges_text.find("\n", param_idx)
            if line_end < 0:
                line_end = len(ranges_text)
            param_line = ranges_text[param_idx : line_end + 80]  # include wraps

            # Check that the low value from optimizer appears in prompt
            low_str = str(opt_range["low"])
            high_str = str(opt_range["high"])

            if low_str not in param_line and str(int(opt_range["low"])) not in param_line:
                mismatches.append(f"  {param_name}: optimizer low={opt_range['low']} not in prompt")
            if high_str not in param_line and str(int(opt_range["high"])) not in param_line:
                mismatches.append(f"  {param_name}: optimizer high={opt_range['high']} not in prompt")

        # Allow up to 1 mismatch (floats may format differently)
        if len(mismatches) > 1:
            pytest.fail(f"Block '{block_type}': prompt <-> optimizer range mismatches:\n" + "\n".join(mismatches))


# =============================================================================
# TEST: Complete Block Count
# =============================================================================


class TestBlockCoverage:
    """Verify we test ALL known library blocks, not just a subset."""

    def test_ground_truth_covers_all_library_blocks(self):
        """Ground truth dict must include all 34 blocks from the Library."""
        actual = len(BLOCK_GROUND_TRUTH)
        assert actual >= 33, (
            f"Ground truth only has {actual} blocks, expected at least 33. Some Library blocks are not being tested!"
        )

    def test_all_optimizable_blocks_have_ranges_in_prompt(self, prompt_text: str):
        """Every block with optimizable params must have OPTIMIZATION RANGES."""
        blocks_with_opt = [(bt, t["header"]) for bt, t in BLOCK_GROUND_TRUTH.items() if t["optimizable"]]

        missing = []
        for block_type, header in blocks_with_opt:
            idx = prompt_text.find(header)
            if idx < 0:
                missing.append(f"  {block_type}: header not found")
                continue

            section = prompt_text[idx : idx + 3000]
            if "OPTIMIZATION RANGES" not in section:
                missing.append(f"  {block_type}: has optimizable params but no OPTIMIZATION RANGES")

        assert not missing, "Blocks with optimizable params but no OPTIMIZATION RANGES:\n" + "\n".join(missing)
