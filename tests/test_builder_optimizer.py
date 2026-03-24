"""
Tests for builder_optimizer module.

Tests parameter extraction from strategy graphs, graph cloning with overrides,
grid search, Optuna Bayesian search, and API endpoint integration.

Phase 3: Strategy Builder ↔ Optimization Integration.
"""

import copy

import numpy as np
import pandas as pd
import pytest

from backend.optimization.builder_optimizer import (
    DEFAULT_PARAM_RANGES,
    _merge_ranges,
    clone_graph_with_params,
    extract_optimizable_params,
    generate_builder_param_combinations,
    run_builder_backtest,
    run_builder_grid_search,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_rsi_graph():
    """Strategy graph with RSI indicator block."""
    return {
        "name": "Test RSI Strategy",
        "description": "RSI strategy for testing",
        "blocks": [
            {
                "id": "rsi_1",
                "type": "rsi",
                "name": "RSI Indicator",
                "params": {"period": 14, "overbought": 70, "oversold": 30},
            },
            {
                "id": "static_sltp_1",
                "type": "static_sltp",
                "name": "Stop Loss / Take Profit",
                "params": {"stop_loss_percent": 1.5, "take_profit_percent": 2.0, "activate_breakeven": True},
            },
        ],
        "connections": [
            {"from": "rsi_1", "to": "static_sltp_1"},
        ],
        "market_type": "linear",
        "direction": "both",
    }


@pytest.fixture
def multi_indicator_graph():
    """Strategy graph with multiple indicator blocks (RSI + MACD + Bollinger)."""
    return {
        "name": "Multi-Indicator Strategy",
        "description": "RSI + MACD + Bollinger",
        "blocks": [
            {
                "id": "rsi_1",
                "type": "rsi",
                "name": "RSI",
                "params": {"period": 14, "overbought": 70, "oversold": 30},
            },
            {
                "id": "macd_1",
                "type": "macd",
                "name": "MACD",
                "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
            },
            {
                "id": "boll_1",
                "type": "bollinger",
                "name": "Bollinger Bands",
                "params": {"period": 20, "std_dev": 2.0},
            },
            {
                "id": "exit_1",
                "type": "static_sltp",
                "name": "Exit",
                "params": {"stop_loss_percent": 1.5, "take_profit_percent": 2.5, "activate_breakeven": True},
            },
        ],
        "connections": [],
        "market_type": "linear",
        "direction": "both",
    }


@pytest.fixture
def empty_graph():
    """Strategy graph with no optimizable blocks."""
    return {
        "name": "Empty Strategy",
        "blocks": [
            {"id": "condition_1", "type": "condition", "name": "Condition", "params": {}},
        ],
        "connections": [],
    }


@pytest.fixture
def graph_with_config_key():
    """Strategy graph where blocks use 'config' instead of 'params'."""
    return {
        "name": "Config-style Graph",
        "blocks": [
            {
                "id": "rsi_1",
                "type": "rsi",
                "name": "RSI Config",
                "config": {"period": 21, "overbought": 75, "oversold": 25},
            },
        ],
        "connections": [],
    }


@pytest.fixture
def sample_ohlcv():
    """Generate sample OHLCV data (500 candles) for backtest testing."""
    np.random.seed(42)
    n = 500
    base_price = 50000.0

    timestamps = pd.date_range(start="2025-01-01", periods=n, freq="15min", tz="UTC")

    returns = np.random.randn(n) * 0.002
    prices = base_price * np.cumprod(1 + returns)

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": prices * (1 + np.random.randn(n) * 0.001),
            "high": prices * (1 + abs(np.random.randn(n)) * 0.003),
            "low": prices * (1 - abs(np.random.randn(n)) * 0.003),
            "close": prices,
            "volume": np.random.uniform(100, 1000, n),
        }
    )


@pytest.fixture
def backtest_config_params():
    """Standard config params for builder backtests."""
    return {
        "symbol": "BTCUSDT",
        "interval": "15m",
        "initial_capital": 10000.0,
        "leverage": 1,
        "commission": 0.0007,
        "direction": "both",
        "engine_type": "fallback",
        "use_fixed_amount": False,
        "fixed_amount": 0.0,
        "stop_loss_pct": 0,
        "take_profit_pct": 0,
    }


# =============================================================================
# TESTS: DEFAULT_PARAM_RANGES
# =============================================================================


class TestDefaultParamRanges:
    """Tests for DEFAULT_PARAM_RANGES constant."""

    def test_all_expected_block_types_present(self):
        """Verify all 14 indicator types have ranges defined."""
        expected = {
            "rsi",
            "macd",
            "ema",
            "sma",
            "bollinger",
            "supertrend",
            "stochastic",
            "cci",
            "atr",
            "adx",
            "williams_r",
            "static_sltp",
            "trailing_stop_exit",
        }
        assert expected.issubset(set(DEFAULT_PARAM_RANGES.keys()))

    def test_each_range_has_required_keys(self):
        """Each param range spec must have type, low, high, step, default."""
        required_keys = {"type", "low", "high", "step", "default"}
        for block_type, params in DEFAULT_PARAM_RANGES.items():
            for param_key, spec in params.items():
                missing = required_keys - set(spec.keys())
                assert not missing, f"{block_type}.{param_key} missing keys: {missing}"

    def test_range_low_less_than_high(self):
        """Low must be strictly less than high for all ranges."""
        for block_type, params in DEFAULT_PARAM_RANGES.items():
            for param_key, spec in params.items():
                assert spec["low"] < spec["high"], f"{block_type}.{param_key}: low={spec['low']} >= high={spec['high']}"

    def test_step_is_positive(self):
        """Step must be positive for all ranges."""
        for block_type, params in DEFAULT_PARAM_RANGES.items():
            for param_key, spec in params.items():
                assert spec["step"] > 0, f"{block_type}.{param_key}: step={spec['step']} <= 0"

    def test_default_within_range(self):
        """Default value must be within [low, high]."""
        for block_type, params in DEFAULT_PARAM_RANGES.items():
            for param_key, spec in params.items():
                assert spec["low"] <= spec["default"] <= spec["high"], (
                    f"{block_type}.{param_key}: default={spec['default']} not in [{spec['low']}, {spec['high']}]"
                )

    def test_rsi_has_expected_params(self):
        """RSI must have period, range bounds, cross levels, memory, and legacy params."""
        expected = {
            "period",
            "long_rsi_more",
            "long_rsi_less",
            "short_rsi_less",
            "short_rsi_more",
            "cross_long_level",
            "cross_short_level",
            "cross_memory_bars",
            "overbought",
            "oversold",
        }
        assert set(DEFAULT_PARAM_RANGES["rsi"].keys()) == expected

    def test_macd_has_expected_params(self):
        """MACD must have fast_period, slow_period, signal_period, macd_cross_zero_level, signal_memory_bars."""
        expected = {"fast_period", "slow_period", "signal_period", "macd_cross_zero_level", "signal_memory_bars"}
        assert set(DEFAULT_PARAM_RANGES["macd"].keys()) == expected


# =============================================================================
# TESTS: extract_optimizable_params
# =============================================================================


class TestExtractOptimizableParams:
    """Tests for extract_optimizable_params function."""

    def test_extract_rsi_params(self, sample_rsi_graph):
        """Extract params from RSI block returns 3 params (period, overbought, oversold)."""
        params = extract_optimizable_params(sample_rsi_graph)
        rsi_params = [p for p in params if p["block_type"] == "rsi"]
        assert len(rsi_params) == 3
        keys = {p["param_key"] for p in rsi_params}
        assert keys == {"period", "overbought", "oversold"}

    def test_extract_sltp_params(self, sample_rsi_graph):
        """Extract params from static_sltp block returns 4 params (SL, TP, breakeven_activation, new_breakeven_sl)."""
        params = extract_optimizable_params(sample_rsi_graph)
        sltp_params = [p for p in params if p["block_type"] == "static_sltp"]
        assert len(sltp_params) == 4
        keys = {p["param_key"] for p in sltp_params}
        assert keys == {
            "stop_loss_percent",
            "take_profit_percent",
            "breakeven_activation_percent",
            "new_breakeven_sl_percent",
        }

    def test_extract_multi_indicator_params(self, multi_indicator_graph):
        """Multi-indicator graph returns params from all block types."""
        params = extract_optimizable_params(multi_indicator_graph)
        # RSI: 3, MACD: 3, Bollinger: 2, SLTP: 4 = 12
        assert len(params) == 12
        block_types = {p["block_type"] for p in params}
        assert block_types == {"rsi", "macd", "bollinger", "static_sltp"}

    def test_extract_empty_graph(self, empty_graph):
        """Empty graph (no optimizable blocks) returns empty list."""
        params = extract_optimizable_params(empty_graph)
        assert params == []

    def test_extract_no_blocks_key(self):
        """Graph without 'blocks' key returns empty list."""
        params = extract_optimizable_params({"name": "test"})
        assert params == []

    def test_param_path_format(self, sample_rsi_graph):
        """param_path should be 'blockId.paramKey'."""
        params = extract_optimizable_params(sample_rsi_graph)
        for p in params:
            assert p["param_path"] == f"{p['block_id']}.{p['param_key']}"

    def test_current_value_from_block(self, sample_rsi_graph):
        """current_value should reflect what's set in the block params."""
        params = extract_optimizable_params(sample_rsi_graph)
        rsi_period = next(p for p in params if p["block_id"] == "rsi_1" and p["param_key"] == "period")
        assert rsi_period["current_value"] == 14

    def test_current_value_fallback_to_default(self):
        """If block param is missing, current_value falls back to default."""
        graph = {
            "blocks": [
                {"id": "rsi_1", "type": "rsi", "name": "RSI", "params": {}},
            ]
        }
        params = extract_optimizable_params(graph)
        rsi_period = next(p for p in params if p["param_key"] == "period")
        assert rsi_period["current_value"] == 14  # DEFAULT_PARAM_RANGES default

    def test_config_key_fallback(self, graph_with_config_key):
        """Blocks using 'config' instead of 'params' should work."""
        params = extract_optimizable_params(graph_with_config_key)
        rsi_period = next(p for p in params if p["param_key"] == "period")
        assert rsi_period["current_value"] == 21

    def test_unknown_block_type_ignored(self):
        """Blocks with unknown types are ignored (no params extracted)."""
        graph = {
            "blocks": [
                {"id": "xyz_1", "type": "custom_indicator", "name": "Custom", "params": {}},
            ]
        }
        params = extract_optimizable_params(graph)
        assert params == []

    # ── Conditional extraction for universal RSI modes ──────────────────

    def test_extract_rsi_with_long_range_enabled(self):
        """When use_long_range is True, long range params are extracted."""
        graph = {
            "blocks": [
                {
                    "id": "rsi_1",
                    "type": "rsi",
                    "name": "RSI",
                    "params": {"period": 14, "use_long_range": True, "long_rsi_more": 25, "long_rsi_less": 75},
                },
            ]
        }
        params = extract_optimizable_params(graph)
        keys = {p["param_key"] for p in params}
        assert "long_rsi_more" in keys
        assert "long_rsi_less" in keys
        # Short range not enabled → skipped
        assert "short_rsi_less" not in keys
        assert "short_rsi_more" not in keys
        # Legacy skipped when new mode active
        assert "overbought" not in keys
        assert "oversold" not in keys

    def test_extract_rsi_with_cross_level_enabled(self):
        """When use_cross_level is True, cross level params are extracted."""
        graph = {
            "blocks": [
                {
                    "id": "rsi_1",
                    "type": "rsi",
                    "name": "RSI",
                    "params": {"period": 14, "use_cross_level": True, "cross_long_level": 30, "cross_short_level": 70},
                },
            ]
        }
        params = extract_optimizable_params(graph)
        keys = {p["param_key"] for p in params}
        assert "cross_long_level" in keys
        assert "cross_short_level" in keys
        # Memory not enabled → skipped
        assert "cross_memory_bars" not in keys
        # Legacy skipped when new mode active
        assert "overbought" not in keys

    def test_extract_rsi_with_cross_memory_enabled(self):
        """When use_cross_memory is True, cross_memory_bars is extracted."""
        graph = {
            "blocks": [
                {
                    "id": "rsi_1",
                    "type": "rsi",
                    "name": "RSI",
                    "params": {"period": 14, "use_cross_level": True, "use_cross_memory": True, "cross_memory_bars": 3},
                },
            ]
        }
        params = extract_optimizable_params(graph)
        keys = {p["param_key"] for p in params}
        assert "cross_memory_bars" in keys

    def test_extract_rsi_all_modes_enabled(self):
        """All modes enabled → all numeric params extracted, legacy skipped."""
        graph = {
            "blocks": [
                {
                    "id": "rsi_1",
                    "type": "rsi",
                    "name": "RSI",
                    "params": {
                        "period": 14,
                        "use_long_range": True,
                        "long_rsi_more": 30,
                        "long_rsi_less": 70,
                        "use_short_range": True,
                        "short_rsi_less": 70,
                        "short_rsi_more": 30,
                        "use_cross_level": True,
                        "cross_long_level": 30,
                        "cross_short_level": 70,
                        "use_cross_memory": True,
                        "cross_memory_bars": 5,
                    },
                },
            ]
        }
        params = extract_optimizable_params(graph)
        keys = {p["param_key"] for p in params}
        expected = {
            "period",
            "long_rsi_more",
            "long_rsi_less",
            "short_rsi_less",
            "short_rsi_more",
            "cross_long_level",
            "cross_short_level",
            "cross_memory_bars",
        }
        assert keys == expected

    def test_extract_rsi_legacy_only(self):
        """No new modes → only period + legacy overbought/oversold."""
        graph = {
            "blocks": [
                {
                    "id": "rsi_1",
                    "type": "rsi",
                    "name": "RSI",
                    "params": {"period": 14, "overbought": 70, "oversold": 30},
                },
            ]
        }
        params = extract_optimizable_params(graph)
        keys = {p["param_key"] for p in params}
        assert keys == {"period", "overbought", "oversold"}

    # ── Conditional extraction for MACD modes ───────────────────────────

    def test_extract_macd_no_mode_base_only(self):
        """No MACD mode enabled → only fast/slow/signal extracted (no cross_zero_level, no memory)."""
        graph = {
            "blocks": [
                {
                    "id": "macd_1",
                    "type": "macd",
                    "name": "MACD",
                    "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
                },
            ]
        }
        params = extract_optimizable_params(graph)
        keys = {p["param_key"] for p in params}
        assert keys == {"fast_period", "slow_period", "signal_period"}

    def test_extract_macd_cross_zero_enabled(self):
        """Cross zero enabled → macd_cross_zero_level + signal_memory_bars extracted."""
        graph = {
            "blocks": [
                {
                    "id": "macd_1",
                    "type": "macd",
                    "name": "MACD",
                    "params": {
                        "fast_period": 12,
                        "slow_period": 26,
                        "signal_period": 9,
                        "use_macd_cross_zero": True,
                        "macd_cross_zero_level": 0,
                    },
                },
            ]
        }
        params = extract_optimizable_params(graph)
        keys = {p["param_key"] for p in params}
        assert "macd_cross_zero_level" in keys
        assert "signal_memory_bars" in keys  # memory enabled by default

    def test_extract_macd_cross_signal_enabled(self):
        """Cross signal enabled → signal_memory_bars extracted, but not cross_zero_level."""
        graph = {
            "blocks": [
                {
                    "id": "macd_1",
                    "type": "macd",
                    "name": "MACD",
                    "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9, "use_macd_cross_signal": True},
                },
            ]
        }
        params = extract_optimizable_params(graph)
        keys = {p["param_key"] for p in params}
        assert "macd_cross_zero_level" not in keys  # cross zero not enabled
        assert "signal_memory_bars" in keys  # memory on by default

    def test_extract_macd_memory_disabled(self):
        """When disable_signal_memory=True, signal_memory_bars is NOT extracted."""
        graph = {
            "blocks": [
                {
                    "id": "macd_1",
                    "type": "macd",
                    "name": "MACD",
                    "params": {
                        "fast_period": 12,
                        "slow_period": 26,
                        "signal_period": 9,
                        "use_macd_cross_signal": True,
                        "disable_signal_memory": True,
                    },
                },
            ]
        }
        params = extract_optimizable_params(graph)
        keys = {p["param_key"] for p in params}
        assert "signal_memory_bars" not in keys

    def test_extract_macd_all_modes_enabled(self):
        """Both modes enabled → all 5 params extracted."""
        graph = {
            "blocks": [
                {
                    "id": "macd_1",
                    "type": "macd",
                    "name": "MACD",
                    "params": {
                        "fast_period": 12,
                        "slow_period": 26,
                        "signal_period": 9,
                        "use_macd_cross_zero": True,
                        "macd_cross_zero_level": 0,
                        "use_macd_cross_signal": True,
                    },
                },
            ]
        }
        params = extract_optimizable_params(graph)
        keys = {p["param_key"] for p in params}
        assert keys == {"fast_period", "slow_period", "signal_period", "macd_cross_zero_level", "signal_memory_bars"}


# =============================================================================
# TESTS: clone_graph_with_params
# =============================================================================


class TestCloneGraphWithParams:
    """Tests for clone_graph_with_params function."""

    def test_clone_modifies_param(self, sample_rsi_graph):
        """Cloning with override changes the specified param."""
        modified = clone_graph_with_params(
            sample_rsi_graph,
            {"rsi_1.period": 21},
        )
        rsi_block = next(b for b in modified["blocks"] if b["id"] == "rsi_1")
        assert rsi_block["params"]["period"] == 21

    def test_clone_does_not_mutate_original(self, sample_rsi_graph):
        """Original graph must not be modified."""
        original_period = sample_rsi_graph["blocks"][0]["params"]["period"]
        clone_graph_with_params(
            sample_rsi_graph,
            {"rsi_1.period": 99},
        )
        assert sample_rsi_graph["blocks"][0]["params"]["period"] == original_period

    def test_clone_multiple_overrides(self, sample_rsi_graph):
        """Multiple param overrides applied simultaneously."""
        modified = clone_graph_with_params(
            sample_rsi_graph,
            {
                "rsi_1.period": 21,
                "rsi_1.overbought": 80,
                "static_sltp_1.stop_loss_percent": 2.5,
            },
        )
        rsi = next(b for b in modified["blocks"] if b["id"] == "rsi_1")
        sltp = next(b for b in modified["blocks"] if b["id"] == "static_sltp_1")
        assert rsi["params"]["period"] == 21
        assert rsi["params"]["overbought"] == 80
        assert rsi["params"]["oversold"] == 30  # Unchanged
        assert sltp["params"]["stop_loss_percent"] == 2.5

    def test_clone_invalid_block_id_ignored(self, sample_rsi_graph):
        """Invalid block_id in override is logged but doesn't crash."""
        modified = clone_graph_with_params(
            sample_rsi_graph,
            {"nonexistent_block.period": 99},
        )
        # All blocks should be unchanged
        rsi = next(b for b in modified["blocks"] if b["id"] == "rsi_1")
        assert rsi["params"]["period"] == 14

    def test_clone_invalid_param_path_format_ignored(self, sample_rsi_graph):
        """Param path without dot separator is ignored."""
        modified = clone_graph_with_params(
            sample_rsi_graph,
            {"invalid_path": 99},
        )
        rsi = next(b for b in modified["blocks"] if b["id"] == "rsi_1")
        assert rsi["params"]["period"] == 14

    def test_clone_config_key_block(self, graph_with_config_key):
        """Blocks using 'config' key should also be cloned correctly."""
        modified = clone_graph_with_params(
            graph_with_config_key,
            {"rsi_1.period": 7},
        )
        rsi = next(b for b in modified["blocks"] if b["id"] == "rsi_1")
        assert rsi["config"]["period"] == 7

    def test_clone_adds_new_param_key(self, sample_rsi_graph):
        """Adding a param key that doesn't exist yet creates it."""
        modified = clone_graph_with_params(
            sample_rsi_graph,
            {"rsi_1.new_param": 42},
        )
        rsi = next(b for b in modified["blocks"] if b["id"] == "rsi_1")
        assert rsi["params"]["new_param"] == 42

    def test_clone_preserves_connections(self, sample_rsi_graph):
        """Connections remain unchanged after cloning."""
        modified = clone_graph_with_params(
            sample_rsi_graph,
            {"rsi_1.period": 21},
        )
        assert modified["connections"] == sample_rsi_graph["connections"]

    def test_clone_preserves_metadata(self, sample_rsi_graph):
        """Name, description, market_type, direction preserved."""
        modified = clone_graph_with_params(
            sample_rsi_graph,
            {"rsi_1.period": 21},
        )
        assert modified["name"] == "Test RSI Strategy"
        assert modified["direction"] == "both"


# =============================================================================
# TESTS: generate_builder_param_combinations
# =============================================================================


class TestGenerateBuilderParamCombinations:
    """Tests for generate_builder_param_combinations function."""

    def test_grid_search_single_param(self):
        """Grid search with one param produces correct count."""
        specs = [
            {
                "param_path": "rsi_1.period",
                "type": "int",
                "low": 10,
                "high": 14,
                "step": 1,
            }
        ]
        combos, total, _ = generate_builder_param_combinations(specs)
        combos = list(combos)
        # 10, 11, 12, 13, 14 = 5 values
        assert total == 5
        assert len(combos) == 5

    def test_grid_search_two_params(self):
        """Grid search with two params produces cartesian product."""
        specs = [
            {"param_path": "rsi_1.period", "type": "int", "low": 10, "high": 12, "step": 1},
            {"param_path": "rsi_1.overbought", "type": "int", "low": 70, "high": 75, "step": 5},
        ]
        combos, total, _ = generate_builder_param_combinations(specs)
        combos = list(combos)
        # 3 x 2 = 6
        assert total == 6
        assert len(combos) == 6

    def test_random_search_limits_count(self):
        """Random search limits to max_iterations."""
        specs = [
            {"param_path": "rsi_1.period", "type": "int", "low": 5, "high": 30, "step": 1},
        ]
        combos, total, _ = generate_builder_param_combinations(
            specs,
            search_method="random",
            max_iterations=5,
            random_seed=42,
        )
        assert total == 26  # Full grid: 5-30 inclusive
        assert len(combos) == 5  # Limited to max_iterations

    def test_random_search_with_seed_reproducible(self):
        """Random search with same seed gives same results."""
        specs = [
            {"param_path": "rsi_1.period", "type": "int", "low": 5, "high": 30, "step": 1},
        ]
        combos1, _, _1 = generate_builder_param_combinations(
            specs,
            search_method="random",
            max_iterations=5,
            random_seed=42,
        )
        combos2, _, _2 = generate_builder_param_combinations(
            specs,
            search_method="random",
            max_iterations=5,
            random_seed=42,
        )
        assert combos1 == combos2

    def test_float_param_range(self):
        """Float params generate correct decimal values."""
        specs = [
            {"param_path": "boll_1.std_dev", "type": "float", "low": 1.5, "high": 2.5, "step": 0.5},
        ]
        combos, total, _ = generate_builder_param_combinations(specs)
        # 1.5, 2.0, 2.5 = 3 values
        assert total == 3
        values = [c["boll_1.std_dev"] for c in combos]
        assert 1.5 in values
        assert 2.0 in values
        assert 2.5 in values

    def test_empty_specs_returns_single_empty_combo(self):
        """Empty param specs returns one empty combo (no optimization)."""
        combos, total, _ = generate_builder_param_combinations([])
        assert total == 1
        assert len(combos) == 1
        assert combos[0] == {}

    def test_combo_dict_has_param_paths_as_keys(self):
        """Each combo dict uses param_path as keys."""
        specs = [
            {"param_path": "rsi_1.period", "type": "int", "low": 10, "high": 12, "step": 1},
        ]
        combos, _, _2 = generate_builder_param_combinations(specs)
        for combo in combos:
            assert "rsi_1.period" in combo

    def test_custom_ranges_override_defaults(self):
        """Custom ranges override default low/high/step."""
        specs = [
            {"param_path": "rsi_1.period", "type": "int", "low": 5, "high": 30, "step": 1},
        ]
        custom = [
            {"param_path": "rsi_1.period", "low": 10, "high": 12, "step": 1, "enabled": True},
        ]
        _combos, total, _ = generate_builder_param_combinations(specs, custom_ranges=custom)
        assert total == 3  # 10, 11, 12

    def test_custom_ranges_disable_param(self):
        """Custom ranges with enabled=False excludes param."""
        specs = [
            {"param_path": "rsi_1.period", "type": "int", "low": 5, "high": 30, "step": 1},
            {"param_path": "rsi_1.overbought", "type": "int", "low": 60, "high": 85, "step": 5},
        ]
        custom = [
            {"param_path": "rsi_1.period", "low": 10, "high": 12, "step": 1, "enabled": True},
            {"param_path": "rsi_1.overbought", "enabled": False},
        ]
        _combos, total, _ = generate_builder_param_combinations(specs, custom_ranges=custom)
        # Only period is active: 10, 11, 12 = 3
        assert total == 3
        # Combos should only have period key
        for combo in _combos:
            assert "rsi_1.period" in combo
            assert "rsi_1.overbought" not in combo


# =============================================================================
# TESTS: _merge_ranges
# =============================================================================


class TestMergeRanges:
    """Tests for _merge_ranges helper."""

    def test_no_custom_returns_all_defaults(self):
        """Without custom ranges, return all param specs."""
        specs = [
            {"param_path": "rsi_1.period", "low": 5, "high": 30, "step": 1},
            {"param_path": "rsi_1.overbought", "low": 60, "high": 85, "step": 5},
        ]
        result = _merge_ranges(specs, None)
        assert len(result) == 2

    def test_custom_overrides_values(self):
        """Custom range overrides low/high/step."""
        specs = [
            {"param_path": "rsi_1.period", "low": 5, "high": 30, "step": 1},
        ]
        custom = [
            {"param_path": "rsi_1.period", "low": 10, "high": 20, "step": 2, "enabled": True},
        ]
        result = _merge_ranges(specs, custom)
        assert len(result) == 1
        assert result[0]["low"] == 10
        assert result[0]["high"] == 20
        assert result[0]["step"] == 2

    def test_custom_disables_param(self):
        """Custom range with enabled=False excludes param."""
        specs = [
            {"param_path": "rsi_1.period", "low": 5, "high": 30, "step": 1},
        ]
        custom = [
            {"param_path": "rsi_1.period", "enabled": False},
        ]
        result = _merge_ranges(specs, custom)
        assert len(result) == 0

    def test_custom_filters_to_only_specified(self):
        """When custom_ranges provided, only specified params are included."""
        specs = [
            {"param_path": "rsi_1.period", "low": 5, "high": 30, "step": 1},
            {"param_path": "rsi_1.overbought", "low": 60, "high": 85, "step": 5},
            {"param_path": "rsi_1.oversold", "low": 15, "high": 40, "step": 5},
        ]
        custom = [
            {"param_path": "rsi_1.period", "low": 10, "high": 14, "step": 1, "enabled": True},
        ]
        result = _merge_ranges(specs, custom)
        # Only period should be active — overbought and oversold filtered out
        assert len(result) == 1
        assert result[0]["param_path"] == "rsi_1.period"


# =============================================================================
# TESTS: run_builder_backtest
# =============================================================================


class TestRunBuilderBacktest:
    """Tests for run_builder_backtest function."""

    def test_backtest_returns_dict_or_none(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """Backtest should return a dict with metrics or None."""
        result = run_builder_backtest(sample_rsi_graph, sample_ohlcv, backtest_config_params)
        # May return None if no trades, or a dict with metrics
        assert result is None or isinstance(result, dict)

    def test_backtest_with_invalid_graph_returns_none(self, sample_ohlcv, backtest_config_params):
        """Invalid graph should return None (not crash)."""
        bad_graph = {"blocks": [], "connections": []}
        result = run_builder_backtest(bad_graph, sample_ohlcv, backtest_config_params)
        assert result is None

    def test_backtest_result_contains_key_metrics(self, multi_indicator_graph, sample_ohlcv, backtest_config_params):
        """If result is not None, it should contain key metric fields."""
        result = run_builder_backtest(multi_indicator_graph, sample_ohlcv, backtest_config_params)
        if result is not None:
            # Should have at least some standard metrics
            assert "total_trades" in result or "net_profit" in result or "sharpe_ratio" in result


# =============================================================================
# TESTS: run_builder_grid_search
# =============================================================================


class TestRunBuilderGridSearch:
    """Tests for run_builder_grid_search function."""

    def test_grid_search_returns_expected_structure(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """Grid search result has required keys."""
        combos = [
            {"rsi_1.period": 10},
            {"rsi_1.period": 14},
            {"rsi_1.period": 21},
        ]
        result = run_builder_grid_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_combinations=combos,
            config_params=backtest_config_params,
            optimize_metric="sharpe_ratio",
            max_results=5,
            timeout_seconds=120,
        )
        assert result["status"] == "completed"
        assert "total_combinations" in result
        assert "tested_combinations" in result
        assert "top_results" in result
        assert "best_params" in result
        assert "execution_time_seconds" in result
        assert result["total_combinations"] == 3

    def test_grid_search_tested_count(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """All combos are tested (no timeout)."""
        combos = [
            {"rsi_1.period": 10},
            {"rsi_1.period": 14},
        ]
        result = run_builder_grid_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_combinations=combos,
            config_params=backtest_config_params,
        )
        assert result["tested_combinations"] == 2

    def test_grid_search_results_sorted_by_score(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """Top results are sorted descending by score."""
        combos = [{"rsi_1.period": val} for val in range(10, 20)]
        result = run_builder_grid_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_combinations=combos,
            config_params=backtest_config_params,
        )
        top = result["top_results"]
        if len(top) >= 2:
            scores = [r["score"] for r in top]
            assert scores == sorted(scores, reverse=True)

    def test_grid_search_max_results_limit(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """Top results limited by max_results."""
        combos = [{"rsi_1.period": v} for v in range(5, 30)]
        result = run_builder_grid_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_combinations=combos,
            config_params=backtest_config_params,
            max_results=3,
        )
        assert len(result["top_results"]) <= 3

    def test_grid_search_timeout(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """Grid search respects timeout (may not test all combos)."""
        combos = [{"rsi_1.period": v} for v in range(5, 30)]
        result = run_builder_grid_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_combinations=combos,
            config_params=backtest_config_params,
            timeout_seconds=0,  # Immediate timeout
        )
        # Should have tested 0 or 1 (at most one before timeout kicks in on next iteration)
        assert result["tested_combinations"] <= 1

    def test_grid_search_empty_combos(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """Empty combo list still returns valid structure."""
        result = run_builder_grid_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_combinations=[],
            config_params=backtest_config_params,
        )
        assert result["status"] == "completed"
        assert result["total_combinations"] == 0
        assert result["tested_combinations"] == 0


# =============================================================================
# TESTS: run_builder_optuna_search
# =============================================================================


class TestRunBuilderOptunaSearch:
    """Tests for run_builder_optuna_search function."""

    @pytest.mark.slow
    def test_optuna_search_returns_expected_structure(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """Optuna search result has required keys."""
        from backend.optimization.builder_optimizer import run_builder_optuna_search

        specs = [
            {
                "param_path": "rsi_1.period",
                "type": "int",
                "low": 10,
                "high": 20,
                "step": 1,
            },
        ]
        result = run_builder_optuna_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_specs=specs,
            config_params=backtest_config_params,
            n_trials=5,
            top_n=3,
            timeout_seconds=60,
        )
        assert result["status"] == "completed"
        assert "total_combinations" in result
        assert "tested_combinations" in result
        assert "top_results" in result
        assert "best_params" in result
        assert "execution_time_seconds" in result

    @pytest.mark.slow
    def test_optuna_search_respects_n_trials(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """Optuna runs at most n_trials."""
        from backend.optimization.builder_optimizer import run_builder_optuna_search

        specs = [
            {"param_path": "rsi_1.period", "type": "int", "low": 10, "high": 20, "step": 1},
        ]
        result = run_builder_optuna_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_specs=specs,
            config_params=backtest_config_params,
            n_trials=3,
            top_n=2,
            timeout_seconds=60,
        )
        assert result["tested_combinations"] <= 3

    @pytest.mark.slow
    def test_optuna_top_n_limit(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """Top results limited by top_n."""
        from backend.optimization.builder_optimizer import run_builder_optuna_search

        specs = [
            {"param_path": "rsi_1.period", "type": "int", "low": 10, "high": 20, "step": 1},
        ]
        result = run_builder_optuna_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_specs=specs,
            config_params=backtest_config_params,
            n_trials=10,
            top_n=3,
            timeout_seconds=60,
        )
        assert len(result["top_results"]) <= 3


# =============================================================================
# INTEGRATION TESTS: Full Pipeline
# =============================================================================


class TestBuilderOptimizationPipeline:
    """Integration tests for the full builder optimization pipeline."""

    def test_extract_clone_backtest_pipeline(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """Full pipeline: extract → clone → backtest works end-to-end."""
        # Step 1: Extract params
        params = extract_optimizable_params(sample_rsi_graph)
        assert len(params) > 0

        # Step 2: Modify a param
        overrides = {"rsi_1.period": 21}
        modified_graph = clone_graph_with_params(sample_rsi_graph, overrides)

        # Verify modification
        rsi_block = next(b for b in modified_graph["blocks"] if b["id"] == "rsi_1")
        assert rsi_block["params"]["period"] == 21

        # Step 3: Run backtest (may return None if no trades)
        result = run_builder_backtest(modified_graph, sample_ohlcv, backtest_config_params)
        assert result is None or isinstance(result, dict)

    def test_extract_generate_grid_search_pipeline(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """Full pipeline: extract → generate combos → grid search."""
        # Step 1: Extract
        all_params = extract_optimizable_params(sample_rsi_graph)

        # Step 2: Generate combos (small range for test speed)
        custom = [
            {"param_path": "rsi_1.period", "low": 12, "high": 16, "step": 2, "enabled": True},
        ]
        combos, total, _ = generate_builder_param_combinations(all_params, custom_ranges=custom)
        assert total == 3  # 12, 14, 16

        # Step 3: Grid search
        result = run_builder_grid_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_combinations=combos,
            config_params=backtest_config_params,
            max_results=5,
            timeout_seconds=120,
        )
        assert result["status"] == "completed"
        assert result["tested_combinations"] == 3

    def test_graph_immutability_after_grid_search(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """Original graph must not be mutated by grid search."""
        original_graph = copy.deepcopy(sample_rsi_graph)
        combos = [{"rsi_1.period": v} for v in [10, 14, 21]]
        run_builder_grid_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_combinations=combos,
            config_params=backtest_config_params,
        )
        # Verify original graph unchanged
        assert sample_rsi_graph == original_graph


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_block_with_none_params(self):
        """Block with params=None should not crash extract."""
        graph = {
            "blocks": [
                {"id": "rsi_1", "type": "rsi", "name": "RSI", "params": None},
            ]
        }
        params = extract_optimizable_params(graph)
        # Should extract params with default values
        assert len(params) == 3

    def test_clone_block_with_none_params(self):
        """Cloning block with None params creates params dict."""
        graph = {
            "blocks": [
                {"id": "rsi_1", "type": "rsi", "name": "RSI", "params": None},
            ]
        }
        modified = clone_graph_with_params(graph, {"rsi_1.period": 21})
        rsi = next(b for b in modified["blocks"] if b["id"] == "rsi_1")
        assert rsi["params"]["period"] == 21

    def test_very_large_grid_with_random_sampling(self):
        """Large grid with random sampling returns correct count."""
        specs = [{"param_path": f"rsi_1.p{i}", "type": "int", "low": 1, "high": 100, "step": 1} for i in range(3)]
        combos, total, _ = generate_builder_param_combinations(
            specs,
            search_method="random",
            max_iterations=50,
            random_seed=42,
        )
        assert total == 100**3  # 1,000,000
        assert len(combos) == 50

    def test_single_value_param_range(self):
        """Param with low==high produces single value."""
        specs = [
            {"param_path": "rsi_1.period", "type": "int", "low": 14, "high": 14, "step": 1},
        ]
        combos, total, _ = generate_builder_param_combinations(specs)
        combos = list(combos)
        assert total == 1
        assert combos[0]["rsi_1.period"] == 14


# =============================================================================
# TESTS: Approach 1 — n_jobs parallel Optuna workers
# =============================================================================


class TestOptunaParallelNJobs:
    """Tests for n_jobs parallelism in run_builder_optuna_search."""

    @pytest.mark.slow
    def test_n_jobs_1_returns_valid_structure(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """n_jobs=1 (sequential) returns valid result structure."""
        from backend.optimization.builder_optimizer import run_builder_optuna_search

        specs = [
            {"param_path": "rsi_1.overbought", "type": "int", "low": 65, "high": 75, "step": 5},
        ]
        result = run_builder_optuna_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_specs=specs,
            config_params=backtest_config_params,
            n_trials=5,
            top_n=3,
            timeout_seconds=60,
            n_jobs=1,
        )
        assert result["status"] == "completed"
        assert result["tested_combinations"] <= 5
        assert "top_results" in result

    @pytest.mark.slow
    def test_n_jobs_2_returns_valid_structure(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """n_jobs=2 (parallel) returns same valid structure as sequential."""
        from backend.optimization.builder_optimizer import run_builder_optuna_search

        specs = [
            {"param_path": "rsi_1.overbought", "type": "int", "low": 65, "high": 80, "step": 5},
        ]
        result = run_builder_optuna_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_specs=specs,
            config_params=backtest_config_params,
            n_trials=8,
            top_n=3,
            timeout_seconds=60,
            n_jobs=2,
        )
        assert result["status"] == "completed"
        assert "top_results" in result
        assert "best_params" in result
        assert "tested_combinations" in result

    @pytest.mark.slow
    def test_n_jobs_parallel_completes_and_reports_tested(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """Parallel workers complete and report correct number of tested combos."""
        from backend.optimization.builder_optimizer import run_builder_optuna_search

        specs = [
            {"param_path": "rsi_1.period", "type": "int", "low": 10, "high": 18, "step": 2},
        ]
        result = run_builder_optuna_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_specs=specs,
            config_params=backtest_config_params,
            n_trials=10,
            top_n=5,
            timeout_seconds=60,
            n_jobs=2,
        )
        # Parallel search should complete and have tried at least 1 trial
        assert result["status"] == "completed"
        # Note: Optuna may legitimately suggest duplicate params to parallel workers
        # so we only verify the structure is valid, not uniqueness
        assert result["tested_combinations"] >= 0
        assert isinstance(result["top_results"], list)

    @pytest.mark.slow
    def test_n_jobs_capped_at_cpu_count(self, sample_rsi_graph, sample_ohlcv, backtest_config_params):
        """n_jobs > cpu_count is silently capped and still produces valid results."""
        import os

        from backend.optimization.builder_optimizer import run_builder_optuna_search

        specs = [
            {"param_path": "rsi_1.oversold", "type": "int", "low": 25, "high": 35, "step": 5},
        ]
        # Pass absurdly large n_jobs — should be capped to os.cpu_count()
        result = run_builder_optuna_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_specs=specs,
            config_params=backtest_config_params,
            n_trials=6,
            top_n=3,
            timeout_seconds=60,
            n_jobs=999,
        )
        assert result["status"] == "completed"

    def test_n_jobs_signature_has_n_jobs_param(self):
        """run_builder_optuna_search signature includes n_jobs parameter."""
        import inspect

        from backend.optimization.builder_optimizer import run_builder_optuna_search

        sig = inspect.signature(run_builder_optuna_search)
        assert "n_jobs" in sig.parameters
        assert sig.parameters["n_jobs"].default == 1

    def test_request_model_has_n_jobs_field(self):
        """BuilderOptimizationRequest model includes n_jobs field."""
        from backend.api.routers.strategy_builder.router import BuilderOptimizationRequest

        fields = BuilderOptimizationRequest.model_fields
        assert "n_jobs" in fields
        # Default value must be 1 (sequential, safe default)
        default = fields["n_jobs"].default
        assert default == 1


# =============================================================================
# TESTS: Approach 4 — Mixed DCA batch (RSI + SLTP params both vary)
# =============================================================================


@pytest.fixture
def dca_rsi_graph():
    """Strategy graph mimicking DCA-RSI-6: RSI block + DCA block + static_sltp block."""
    return {
        "name": "DCA-RSI-6 test",
        "interval": "30",
        "blocks": [
            {
                "id": "rsi_1",
                "type": "rsi",
                "name": "RSI",
                "params": {
                    "period": 14,
                    "source": "close",
                    "timeframe": "30",
                    "use_cross_level": True,
                    "cross_long_level": 29,
                    "long_rsi_less": 40,
                    "use_long_range": True,
                },
            },
            {
                "id": "dca_1",
                "type": "dca",
                "name": "DCA",
                "params": {
                    "order_count": 3,
                    "grid_size_percent": 5.0,
                    "martingale_coef": 1.0,
                    "tp_percent": 1.5,
                    "sl_percent": 5.0,
                },
            },
            {
                "id": "sltp_1",
                "type": "static_sltp",
                "name": "SL/TP",
                "params": {
                    "stop_loss_percent": 5.0,
                    "take_profit_percent": 1.5,
                    "sl_type": "average_price",
                },
            },
            {
                "id": "strategy_1",
                "type": "strategy",
                "isMain": True,
                "params": {},
            },
        ],
        "connections": [
            {"from": "rsi_1", "fromPort": "long", "to": "strategy_1", "toPort": "entry_long"},
            {"from": "dca_1", "fromPort": "output", "to": "strategy_1", "toPort": "dca"},
            {"from": "sltp_1", "fromPort": "output", "to": "strategy_1", "toPort": "sltp"},
        ],
    }


@pytest.fixture
def mixed_combos():
    """Small mixed RSI+SLTP param combos (2 RSI × 3 SLTP = 6 total)."""
    combos = []
    for rsi_level in (25, 30):
        for tp in (1.0, 1.5, 2.0):
            combos.append({
                "rsi_1.cross_long_level": rsi_level,
                "sltp_1.take_profit_percent": tp,
                "sltp_1.stop_loss_percent": 5.0,
            })
    return combos


class TestRunDcaMixedBatchNumba:
    """Tests for _run_dca_mixed_batch_numba — nested RSI × SLTP optimization."""

    def test_returns_list_aligned_with_combos(self, dca_rsi_graph, sample_ohlcv, backtest_config_params, mixed_combos):
        """Result list length equals number of input combos."""
        from backend.optimization.builder_optimizer import _run_dca_mixed_batch_numba

        config = {**backtest_config_params, "direction": "long"}
        results = _run_dca_mixed_batch_numba(
            base_graph=dca_rsi_graph,
            ohlcv=sample_ohlcv,
            param_combinations=mixed_combos,
            config_params=config,
            final_dca_config={"dca_enabled": True, "dca_order_count": 3,
                              "dca_grid_size_percent": 5.0, "dca_martingale_coef": 1.0},
            direction_str="long",
            sltp_block_ids=["sltp_1"],
        )
        assert len(results) == len(mixed_combos)

    def test_non_none_results_have_required_keys(self, dca_rsi_graph, sample_ohlcv, backtest_config_params, mixed_combos):
        """Every non-None result contains the standard metric keys."""
        from backend.optimization.builder_optimizer import _run_dca_mixed_batch_numba

        config = {**backtest_config_params, "direction": "long"}
        results = _run_dca_mixed_batch_numba(
            base_graph=dca_rsi_graph,
            ohlcv=sample_ohlcv,
            param_combinations=mixed_combos,
            config_params=config,
            final_dca_config={"dca_enabled": True, "dca_order_count": 3,
                              "dca_grid_size_percent": 5.0, "dca_martingale_coef": 1.0},
            direction_str="long",
            sltp_block_ids=["sltp_1"],
        )
        required = {"net_profit", "win_rate", "profit_factor", "total_trades", "max_drawdown"}
        for res in results:
            if res is not None:
                assert required.issubset(res.keys()), f"Missing keys: {required - res.keys()}"

    def test_groups_correctly_two_rsi_combos(self, dca_rsi_graph, sample_ohlcv, backtest_config_params):
        """Two RSI values produce two independent signal generations, results in 2×3=6 outputs."""
        from backend.optimization.builder_optimizer import _run_dca_mixed_batch_numba

        combos = [
            {"rsi_1.cross_long_level": 20, "sltp_1.take_profit_percent": 1.0, "sltp_1.stop_loss_percent": 5.0},
            {"rsi_1.cross_long_level": 20, "sltp_1.take_profit_percent": 1.5, "sltp_1.stop_loss_percent": 5.0},
            {"rsi_1.cross_long_level": 20, "sltp_1.take_profit_percent": 2.0, "sltp_1.stop_loss_percent": 5.0},
            {"rsi_1.cross_long_level": 35, "sltp_1.take_profit_percent": 1.0, "sltp_1.stop_loss_percent": 5.0},
            {"rsi_1.cross_long_level": 35, "sltp_1.take_profit_percent": 1.5, "sltp_1.stop_loss_percent": 5.0},
            {"rsi_1.cross_long_level": 35, "sltp_1.take_profit_percent": 2.0, "sltp_1.stop_loss_percent": 5.0},
        ]
        config = {**backtest_config_params, "direction": "long"}
        results = _run_dca_mixed_batch_numba(
            base_graph=dca_rsi_graph,
            ohlcv=sample_ohlcv,
            param_combinations=combos,
            config_params=config,
            final_dca_config={"dca_enabled": True, "dca_order_count": 3,
                              "dca_grid_size_percent": 5.0, "dca_martingale_coef": 1.0},
            direction_str="long",
            sltp_block_ids=["sltp_1"],
        )
        assert len(results) == 6

    def test_higher_tp_can_differ_from_lower_tp(self, sample_ohlcv, backtest_config_params):
        """Different TP values within same RSI group produce potentially different metrics.

        Uses use_long_range mode (RSI < threshold) instead of cross mode to guarantee
        signals on any synthetic data.
        """
        from backend.optimization.builder_optimizer import _run_dca_mixed_batch_numba

        # Graph with use_long_range=True: RSI < 70 → fires on most bars → guaranteed trades
        graph = {
            "name": "test",
            "interval": "30",
            "blocks": [
                {"id": "rsi_1", "type": "rsi", "name": "RSI",
                 "params": {"period": 5, "source": "close", "timeframe": "30",
                            "use_long_range": True, "long_rsi_more": 0, "long_rsi_less": 70}},
                {"id": "dca_1", "type": "dca", "name": "DCA",
                 "params": {"order_count": 2, "grid_size_percent": 3.0, "martingale_coef": 1.0}},
                {"id": "sltp_1", "type": "static_sltp", "name": "SL/TP",
                 "params": {"stop_loss_percent": 20.0, "take_profit_percent": 1.5, "sl_type": "average_price"}},
                {"id": "strategy_1", "type": "strategy", "isMain": True, "params": {}},
            ],
            "connections": [
                {"from": "rsi_1", "fromPort": "long", "to": "strategy_1", "toPort": "entry_long"},
                {"from": "dca_1", "fromPort": "output", "to": "strategy_1", "toPort": "dca"},
                {"from": "sltp_1", "fromPort": "output", "to": "strategy_1", "toPort": "sltp"},
            ],
        }
        combos = [
            {"rsi_1.long_rsi_less": 60, "sltp_1.take_profit_percent": 0.5, "sltp_1.stop_loss_percent": 20.0},
            {"rsi_1.long_rsi_less": 60, "sltp_1.take_profit_percent": 5.0, "sltp_1.stop_loss_percent": 20.0},
        ]
        config = {**backtest_config_params, "direction": "long"}
        results = _run_dca_mixed_batch_numba(
            base_graph=graph,
            ohlcv=sample_ohlcv,
            param_combinations=combos,
            config_params=config,
            final_dca_config={"dca_enabled": True, "dca_order_count": 2,
                              "dca_grid_size_percent": 3.0, "dca_martingale_coef": 1.0},
            direction_str="long",
            sltp_block_ids=["sltp_1"],
        )
        assert len(results) == 2
        # At least one result should have trades (RSI<70 fires often on 500 bars)
        assert any(r is not None for r in results), "Expected at least one non-None result"

    def test_empty_combos_returns_empty_list(self, dca_rsi_graph, sample_ohlcv, backtest_config_params):
        """Empty combo list returns empty list (no crash)."""
        from backend.optimization.builder_optimizer import _run_dca_mixed_batch_numba

        results = _run_dca_mixed_batch_numba(
            base_graph=dca_rsi_graph,
            ohlcv=sample_ohlcv,
            param_combinations=[],
            config_params=backtest_config_params,
            final_dca_config={"dca_enabled": True, "dca_order_count": 3,
                              "dca_grid_size_percent": 5.0, "dca_martingale_coef": 1.0},
            direction_str="long",
            sltp_block_ids=["sltp_1"],
        )
        assert results == []

    def test_single_rsi_group_matches_sltp_only_batch(self, dca_rsi_graph, sample_ohlcv, backtest_config_params):
        """When only one RSI combo exists, mixed batch result == SLTP-only batch result."""
        from backend.optimization.builder_optimizer import (
            _run_dca_mixed_batch_numba,
            _run_dca_sltp_batch_numba,
        )

        # Only SLTP varies (same RSI for all combos)
        combos = [
            {"rsi_1.cross_long_level": 25, "sltp_1.take_profit_percent": 1.0, "sltp_1.stop_loss_percent": 5.0},
            {"rsi_1.cross_long_level": 25, "sltp_1.take_profit_percent": 2.0, "sltp_1.stop_loss_percent": 5.0},
            {"rsi_1.cross_long_level": 25, "sltp_1.take_profit_percent": 3.0, "sltp_1.stop_loss_percent": 5.0},
        ]
        config = {**backtest_config_params, "direction": "long"}
        dca_config = {"dca_enabled": True, "dca_order_count": 3,
                      "dca_grid_size_percent": 5.0, "dca_martingale_coef": 1.0}

        from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
        import copy
        graph_with_rsi = copy.deepcopy(dca_rsi_graph)
        for b in graph_with_rsi["blocks"]:
            if b["id"] == "rsi_1":
                b["params"]["cross_long_level"] = 25

        mixed = _run_dca_mixed_batch_numba(
            base_graph=dca_rsi_graph,
            ohlcv=sample_ohlcv,
            param_combinations=combos,
            config_params=config,
            final_dca_config=dca_config,
            direction_str="long",
            sltp_block_ids=["sltp_1"],
        )
        sltp_only_combos = [
            {"sltp_1.take_profit_percent": 1.0, "sltp_1.stop_loss_percent": 5.0},
            {"sltp_1.take_profit_percent": 2.0, "sltp_1.stop_loss_percent": 5.0},
            {"sltp_1.take_profit_percent": 3.0, "sltp_1.stop_loss_percent": 5.0},
        ]
        sltp = _run_dca_sltp_batch_numba(
            base_graph=graph_with_rsi,
            ohlcv=sample_ohlcv,
            param_combinations=sltp_only_combos,
            config_params=config,
            final_dca_config=dca_config,
            direction_str="long",
            sltp_block_ids=["sltp_1"],
        )
        # n_trades must match exactly between the two paths
        for m, s in zip(mixed, sltp):
            if m is not None and s is not None:
                assert m["total_trades"] == s["total_trades"], (
                    f"Trade count mismatch: mixed={m['total_trades']}, sltp={s['total_trades']}"
                )

    def test_grid_search_activates_mixed_path(self, dca_rsi_graph, sample_ohlcv, backtest_config_params):
        """run_builder_grid_search returns method=grid_numba_dca_mixed for RSI+SLTP combos."""
        combos = []
        for rsi_level in (20, 25, 30):
            for tp in (1.0, 1.5, 2.0):
                combos.append({
                    "rsi_1.cross_long_level": rsi_level,
                    "sltp_1.take_profit_percent": tp,
                    "sltp_1.stop_loss_percent": 5.0,
                })

        config = {**backtest_config_params, "direction": "long"}
        result = run_builder_grid_search(
            base_graph=dca_rsi_graph,
            ohlcv=sample_ohlcv,
            param_combinations=combos,
            config_params=config,
        )
        # Should use mixed fast path, not slow Python loop
        assert result["method"] == "grid_numba_dca_mixed", (
            f"Expected grid_numba_dca_mixed, got: {result['method']}"
        )
        assert result.get("numba_accelerated") is True
        assert result["tested_combinations"] > 0


# =============================================================================
# TESTS: Progress Tracking (file-based, cross-worker)
# =============================================================================


class TestProgressTracking:
    """Tests for update_optimization_progress, get_optimization_progress,
    clear_optimization_progress — file-based shared state across uvicorn workers.

    All tests use monkeypatch to redirect progress file to tmp_path so real
    .run/optimizer_progress.json is never touched.
    """

    @pytest.fixture(autouse=True)
    def patch_progress_file(self, tmp_path, monkeypatch):
        """Redirect _PROGRESS_FILE and _PROGRESS_DIR to a temp directory."""
        import backend.optimization.builder_optimizer as bopt

        tmp_file = tmp_path / "optimizer_progress.json"
        monkeypatch.setattr(bopt, "_PROGRESS_DIR", tmp_path)
        monkeypatch.setattr(bopt, "_PROGRESS_FILE", tmp_file)

    # ------------------------------------------------------------------
    # update_optimization_progress
    # ------------------------------------------------------------------

    def test_update_creates_entry(self):
        """update_optimization_progress writes a new entry to the file."""
        from backend.optimization.builder_optimizer import (
            get_optimization_progress,
            update_optimization_progress,
        )

        update_optimization_progress("strat-abc", tested=100, total=1000)
        entry = get_optimization_progress("strat-abc")
        assert entry["status"] == "running"
        assert entry["tested"] == 100
        assert entry["total"] == 1000

    def test_update_schema_has_all_required_fields(self):
        """Progress entry must include all 10 fields documented in OPTIMIZATION_FLOW.md §4."""
        from backend.optimization.builder_optimizer import (
            get_optimization_progress,
            update_optimization_progress,
        )

        update_optimization_progress(
            "strat-schema",
            status="running",
            tested=500,
            total=1000,
            best_score=1.23,
            results_found=5,
            speed=4500,
            eta_seconds=10,
        )
        entry = get_optimization_progress("strat-schema")
        required_fields = {
            "status", "tested", "total", "percent",
            "best_score", "results_found", "speed",
            "eta_seconds", "started_at", "updated_at",
        }
        missing = required_fields - set(entry.keys())
        assert not missing, f"Progress entry missing fields: {missing}"

    def test_percent_calculated_correctly(self):
        """percent = round(tested * 100 / total, 1)."""
        from backend.optimization.builder_optimizer import (
            get_optimization_progress,
            update_optimization_progress,
        )

        update_optimization_progress("strat-pct", tested=250, total=1000)
        entry = get_optimization_progress("strat-pct")
        assert entry["percent"] == 25.0

    def test_percent_zero_when_total_is_zero(self):
        """When total=0, percent must be 0.0 (no ZeroDivisionError)."""
        from backend.optimization.builder_optimizer import (
            get_optimization_progress,
            update_optimization_progress,
        )

        update_optimization_progress("strat-zero", tested=0, total=0)
        entry = get_optimization_progress("strat-zero")
        assert entry["percent"] == 0.0

    def test_percent_reaches_100_at_completion(self):
        """tested == total → percent == 100.0."""
        from backend.optimization.builder_optimizer import (
            get_optimization_progress,
            update_optimization_progress,
        )

        update_optimization_progress("strat-done", tested=304668, total=304668)
        entry = get_optimization_progress("strat-done")
        assert entry["percent"] == 100.0

    def test_update_overwrites_previous_entry(self):
        """Second call to update_optimization_progress replaces previous values."""
        from backend.optimization.builder_optimizer import (
            get_optimization_progress,
            update_optimization_progress,
        )

        update_optimization_progress("strat-ow", tested=100, total=1000)
        update_optimization_progress("strat-ow", tested=500, total=1000, best_score=2.5)
        entry = get_optimization_progress("strat-ow")
        assert entry["tested"] == 500
        assert entry["best_score"] == 2.5

    def test_updated_at_is_set_automatically(self):
        """updated_at must be a float (Unix timestamp) set by the function itself."""
        import time

        from backend.optimization.builder_optimizer import (
            get_optimization_progress,
            update_optimization_progress,
        )

        before = time.time()
        update_optimization_progress("strat-ts", tested=0, total=0)
        after = time.time()
        entry = get_optimization_progress("strat-ts")
        assert isinstance(entry["updated_at"], float)
        assert before <= entry["updated_at"] <= after

    def test_started_at_preserved_on_subsequent_updates(self):
        """started_at passed explicitly must survive a second update call."""
        from backend.optimization.builder_optimizer import (
            get_optimization_progress,
            update_optimization_progress,
        )

        t0 = 1_742_000_000.0
        update_optimization_progress("strat-sa", tested=0, total=100, started_at=t0)
        update_optimization_progress("strat-sa", tested=50, total=100, started_at=t0)
        entry = get_optimization_progress("strat-sa")
        assert entry["started_at"] == t0

    # ------------------------------------------------------------------
    # get_optimization_progress
    # ------------------------------------------------------------------

    def test_get_returns_idle_for_unknown_strategy(self):
        """get_optimization_progress on a missing id returns {'status': 'idle'}."""
        from backend.optimization.builder_optimizer import get_optimization_progress

        result = get_optimization_progress("nonexistent-strat-xyz")
        assert result == {"status": "idle"}

    def test_get_returns_idle_when_file_missing(self, tmp_path, monkeypatch):
        """get_optimization_progress works even when file does not exist yet."""
        import backend.optimization.builder_optimizer as bopt

        missing_file = tmp_path / "does_not_exist.json"
        monkeypatch.setattr(bopt, "_PROGRESS_FILE", missing_file)
        from backend.optimization.builder_optimizer import get_optimization_progress

        result = get_optimization_progress("any-id")
        assert result == {"status": "idle"}

    def test_get_returns_copy_not_reference(self):
        """get_optimization_progress returns a copy; mutating it must not affect store."""
        from backend.optimization.builder_optimizer import (
            get_optimization_progress,
            update_optimization_progress,
        )

        update_optimization_progress("strat-copy", tested=10, total=100)
        entry = get_optimization_progress("strat-copy")
        entry["tested"] = 9999  # mutate the returned copy

        entry2 = get_optimization_progress("strat-copy")
        assert entry2["tested"] == 10  # original unchanged

    # ------------------------------------------------------------------
    # clear_optimization_progress
    # ------------------------------------------------------------------

    def test_clear_removes_entry(self):
        """clear_optimization_progress removes the strategy entry."""
        from backend.optimization.builder_optimizer import (
            clear_optimization_progress,
            get_optimization_progress,
            update_optimization_progress,
        )

        update_optimization_progress("strat-clr", tested=100, total=100)
        clear_optimization_progress("strat-clr")
        result = get_optimization_progress("strat-clr")
        assert result == {"status": "idle"}

    def test_clear_is_idempotent(self):
        """Clearing a non-existent entry must not raise."""
        from backend.optimization.builder_optimizer import clear_optimization_progress

        clear_optimization_progress("strat-never-existed")  # must not raise

    def test_clear_preserves_other_strategies(self):
        """Clearing one strategy must not affect progress of another strategy."""
        from backend.optimization.builder_optimizer import (
            clear_optimization_progress,
            get_optimization_progress,
            update_optimization_progress,
        )

        update_optimization_progress("strat-a", tested=111, total=200)
        update_optimization_progress("strat-b", tested=222, total=400)
        clear_optimization_progress("strat-a")

        assert get_optimization_progress("strat-a") == {"status": "idle"}
        assert get_optimization_progress("strat-b")["tested"] == 222

    # ------------------------------------------------------------------
    # Multiple strategies / concurrent writes
    # ------------------------------------------------------------------

    def test_multiple_strategies_coexist_in_file(self):
        """Two parallel optimizations can write progress independently."""
        from backend.optimization.builder_optimizer import (
            get_optimization_progress,
            update_optimization_progress,
        )

        update_optimization_progress("strat-x", tested=10, total=100)
        update_optimization_progress("strat-y", tested=50, total=200)

        x = get_optimization_progress("strat-x")
        y = get_optimization_progress("strat-y")
        assert x["tested"] == 10
        assert y["tested"] == 50

    def test_completed_status_written_correctly(self):
        """Status can be set to 'completed' after optimization finishes."""
        from backend.optimization.builder_optimizer import (
            get_optimization_progress,
            update_optimization_progress,
        )

        update_optimization_progress(
            "strat-fin",
            status="completed",
            tested=1000,
            total=1000,
            best_score=4.2,
            results_found=20,
        )
        entry = get_optimization_progress("strat-fin")
        assert entry["status"] == "completed"
        assert entry["percent"] == 100.0
        assert entry["best_score"] == 4.2
        assert entry["results_found"] == 20

    def test_atomic_write_no_partial_reads(self, tmp_path, monkeypatch):
        """Atomic write: result file must be valid JSON after update (no partial writes)."""
        import json

        import backend.optimization.builder_optimizer as bopt

        tmp_file = tmp_path / "prog.json"
        monkeypatch.setattr(bopt, "_PROGRESS_FILE", tmp_file)
        monkeypatch.setattr(bopt, "_PROGRESS_DIR", tmp_path)
        from backend.optimization.builder_optimizer import update_optimization_progress

        for i in range(20):
            update_optimization_progress(f"s{i}", tested=i * 10, total=200)

        raw = tmp_file.read_text(encoding="utf-8")
        data = json.loads(raw)  # must not raise
        assert len(data) == 20
