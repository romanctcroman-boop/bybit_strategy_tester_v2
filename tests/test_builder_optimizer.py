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
                "params": {"stop_loss_percent": 1.5, "take_profit_percent": 2.0},
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
                "params": {"stop_loss_percent": 1.5, "take_profit_percent": 2.5},
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
        combos, total = generate_builder_param_combinations(specs)
        # 10, 11, 12, 13, 14 = 5 values
        assert total == 5
        assert len(combos) == 5

    def test_grid_search_two_params(self):
        """Grid search with two params produces cartesian product."""
        specs = [
            {"param_path": "rsi_1.period", "type": "int", "low": 10, "high": 12, "step": 1},
            {"param_path": "rsi_1.overbought", "type": "int", "low": 70, "high": 75, "step": 5},
        ]
        combos, total = generate_builder_param_combinations(specs)
        # 3 x 2 = 6
        assert total == 6
        assert len(combos) == 6

    def test_random_search_limits_count(self):
        """Random search limits to max_iterations."""
        specs = [
            {"param_path": "rsi_1.period", "type": "int", "low": 5, "high": 30, "step": 1},
        ]
        combos, total = generate_builder_param_combinations(
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
        combos1, _ = generate_builder_param_combinations(
            specs,
            search_method="random",
            max_iterations=5,
            random_seed=42,
        )
        combos2, _ = generate_builder_param_combinations(
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
        combos, total = generate_builder_param_combinations(specs)
        # 1.5, 2.0, 2.5 = 3 values
        assert total == 3
        values = [c["boll_1.std_dev"] for c in combos]
        assert 1.5 in values
        assert 2.0 in values
        assert 2.5 in values

    def test_empty_specs_returns_single_empty_combo(self):
        """Empty param specs returns one empty combo (no optimization)."""
        combos, total = generate_builder_param_combinations([])
        assert total == 1
        assert len(combos) == 1
        assert combos[0] == {}

    def test_combo_dict_has_param_paths_as_keys(self):
        """Each combo dict uses param_path as keys."""
        specs = [
            {"param_path": "rsi_1.period", "type": "int", "low": 10, "high": 12, "step": 1},
        ]
        combos, _ = generate_builder_param_combinations(specs)
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
        _combos, total = generate_builder_param_combinations(specs, custom_ranges=custom)
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
        _combos, total = generate_builder_param_combinations(specs, custom_ranges=custom)
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
        combos, total = generate_builder_param_combinations(all_params, custom_ranges=custom)
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
        combos, total = generate_builder_param_combinations(
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
        combos, total = generate_builder_param_combinations(specs)
        assert total == 1
        assert combos[0]["rsi_1.period"] == 14
