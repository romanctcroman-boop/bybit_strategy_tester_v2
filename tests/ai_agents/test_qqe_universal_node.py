"""
AI Agent Knowledge Test: QQE Universal Node — Real API Tests

Tests verify that AI agents correctly understand the **universal QQE indicator**
which consolidates 2 former duplicates (qqe indicator, qqe_filter) into a single
node with cross signal mode:

  CROSS SIGNAL mode — long when RSI-MA crosses above QQE line,
                      short when RSI-MA crosses below QQE line

Additional options: use_qqe (enable/disable), opposite_qqe, signal memory,
disable_qqe_signal_memory, qqe_signal_memory_bars, enable_qqe_visualization.

Run:
    py -3.14 -m pytest tests/ai_agents/test_qqe_universal_node.py -v
    py -3.14 -m pytest tests/ai_agents/test_qqe_universal_node.py -v -k "passthrough"
    py -3.14 -m pytest tests/ai_agents/test_qqe_universal_node.py -v -k "cross"
    py -3.14 -m pytest tests/ai_agents/test_qqe_universal_node.py -v -k "opposite"
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure project root is on sys.path
project_root = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.api.app import app
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.database import Base, get_db

# ============================================================
# Test DB setup (in-memory SQLite)
# ============================================================

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


Base.metadata.create_all(bind=_engine)
app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture()
def adapter():
    """Bare adapter — no data loaded, used for unit-level calls."""
    return StrategyBuilderAdapter.__new__(StrategyBuilderAdapter)


@pytest.fixture()
def trending_ohlcv() -> pd.DataFrame:
    """OHLCV data with multiple trend reversals (sinusoidal).

    QQE cross signals require RSI-MA to cross the QQE trailing line,
    which only happens during trend reversals. A sinusoidal price with
    multiple cycles ensures several crossover events.
    """
    np.random.seed(42)
    n = 400

    # Sinusoidal price: multiple up/down cycles for QQE crossovers
    t = np.arange(n)
    prices = 5000 + 300 * np.sin(2 * np.pi * t / 80) + np.random.normal(0, 2, n)

    close = pd.Series(prices, name="close")
    high = close + np.abs(np.random.normal(2.0, 0.5, n))
    low = close - np.abs(np.random.normal(2.0, 0.5, n))
    open_ = close + np.random.normal(0, 0.5, n)
    volume = pd.Series(np.random.randint(100, 10000, n), dtype=float, name="volume")

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


@pytest.fixture()
def flat_ohlcv() -> pd.DataFrame:
    """Flat/ranging OHLCV data — no clear trend."""
    np.random.seed(99)
    n = 100
    close = pd.Series(500 + np.random.normal(0, 2.0, n), name="close")
    high = close + np.abs(np.random.normal(1.0, 0.5, n))
    low = close - np.abs(np.random.normal(1.0, 0.5, n))
    open_ = close + np.random.normal(0, 0.5, n)
    volume = pd.Series(np.random.randint(100, 10000, n), dtype=float, name="volume")

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def _run(adapter: StrategyBuilderAdapter, ohlcv: pd.DataFrame, params: dict[str, Any]) -> dict:
    """Helper — execute QQE indicator block."""
    return adapter._execute_indicator("qqe", params, ohlcv, {})


# ============================================================
# 1. PASSTHROUGH MODE (use_qqe=false, default)
# ============================================================


class TestPassthrough:
    """When use_qqe is False (default), long/short should be True everywhere."""

    def test_passthrough_default_params(self, adapter, trending_ohlcv):
        """Default params → passthrough mode, all True."""
        result = _run(adapter, trending_ohlcv, {})
        assert "long" in result
        assert "short" in result
        assert "qqe_line" in result
        assert "rsi_ma" in result
        assert "upper_band" in result
        assert "lower_band" in result
        assert "histogram" in result
        assert "trend" in result
        assert result["long"].all(), "Passthrough: long should be all True"
        assert result["short"].all(), "Passthrough: short should be all True"

    def test_passthrough_explicit_false(self, adapter, trending_ohlcv):
        """use_qqe=False explicitly → passthrough."""
        result = _run(adapter, trending_ohlcv, {"use_qqe": False})
        assert result["long"].all()
        assert result["short"].all()

    def test_passthrough_qqe_data_still_computed(self, adapter, trending_ohlcv):
        """Even in passthrough, QQE line and RSI-MA are computed."""
        result = _run(adapter, trending_ohlcv, {"use_qqe": False})
        qqe_line = result["qqe_line"]
        rsi_ma = result["rsi_ma"]
        # QQE has warmup period (rsi_period + smoothing), so many early bars are NaN
        # Just verify SOME non-NaN values exist after warmup
        assert qqe_line.notna().sum() > 0, "QQE line should have some non-NaN values"
        assert rsi_ma.notna().sum() > len(trending_ohlcv) // 2, "RSI-MA should have many non-NaN values"

    def test_passthrough_has_eight_outputs(self, adapter, trending_ohlcv):
        """Universal QQE should output exactly 8 keys."""
        result = _run(adapter, trending_ohlcv, {})
        expected_keys = {"qqe_line", "rsi_ma", "upper_band", "lower_band", "histogram", "trend", "long", "short"}
        assert set(result.keys()) == expected_keys

    def test_passthrough_histogram_is_rsi_ma_minus_50(self, adapter, trending_ohlcv):
        """Histogram should be rsi_ma - 50."""
        result = _run(adapter, trending_ohlcv, {})
        hist = result["histogram"]
        rsi_ma = result["rsi_ma"]
        valid = hist.notna() & rsi_ma.notna()
        if valid.sum() > 0:
            np.testing.assert_allclose(hist[valid].values, (rsi_ma[valid] - 50).values, rtol=1e-5)

    def test_passthrough_trend_values(self, adapter, trending_ohlcv):
        """Trend should be 0, 1, or -1."""
        result = _run(adapter, trending_ohlcv, {})
        trend = result["trend"]
        valid_trends = trend.dropna()
        unique_vals = set(valid_trends.unique())
        assert unique_vals.issubset({0, 1, -1})


# ============================================================
# 2. CROSS SIGNAL MODE (use_qqe=true)
# ============================================================


class TestCrossSignalMode:
    """Cross signal: long when RSI-MA crosses above QQE line, short when below."""

    def test_cross_signal_produces_signals(self, adapter, trending_ohlcv):
        """With oscillating data, cross mode should produce at least one long and one short.

        Uses qqe_factor=2.0 (more sensitive) to ensure cross events fire.
        """
        result = _run(adapter, trending_ohlcv, {"use_qqe": True, "qqe_factor": 2.0})
        long_sig = result["long"]
        short_sig = result["short"]
        assert long_sig.any(), "Cross mode should produce at least one long signal on oscillating data"
        assert short_sig.any(), "Cross mode should produce at least one short signal on oscillating data"

    def test_cross_signal_not_all_true(self, adapter, trending_ohlcv):
        """Cross mode should NOT have all-True signals (unlike passthrough)."""
        result = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "disable_qqe_signal_memory": True,
            },
        )
        long_sig = result["long"]
        short_sig = result["short"]
        # At least some bars should be False
        assert not long_sig.all(), "Cross mode: not all bars should be long"
        assert not short_sig.all(), "Cross mode: not all bars should be short"

    def test_cross_signal_long_short_not_identical(self, adapter, trending_ohlcv):
        """Long and short signals should differ in cross mode."""
        result = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "disable_qqe_signal_memory": True,
            },
        )
        long_sig = result["long"]
        short_sig = result["short"]
        assert not long_sig.equals(short_sig), "Long and short should not be identical"

    def test_cross_signal_no_simultaneous_raw_fire(self, adapter, trending_ohlcv):
        """Raw cross signals should not fire both long and short at the same bar."""
        result = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "disable_qqe_signal_memory": True,
            },
        )
        both = result["long"] & result["short"]
        assert not both.any(), "Raw cross: long and short should not fire simultaneously"


# ============================================================
# 3. SIGNAL MEMORY
# ============================================================


class TestSignalMemory:
    """Signal memory extends a cross event for N bars."""

    def test_memory_default_enabled(self, adapter, trending_ohlcv):
        """Signal memory is enabled by default (disable_qqe_signal_memory=False)."""
        result_with_mem = _run(adapter, trending_ohlcv, {"use_qqe": True, "qqe_factor": 2.0})
        result_no_mem = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "disable_qqe_signal_memory": True,
            },
        )
        # With memory, more bars should be True
        assert result_with_mem["long"].sum() >= result_no_mem["long"].sum()

    def test_memory_disabled_fewer_signals(self, adapter, trending_ohlcv):
        """Disabling memory should produce fewer (or equal) signal bars."""
        result_mem = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "qqe_signal_memory_bars": 10,
            },
        )
        result_no = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "disable_qqe_signal_memory": True,
            },
        )
        assert result_mem["long"].sum() >= result_no["long"].sum()
        assert result_mem["short"].sum() >= result_no["short"].sum()

    def test_memory_bars_5_vs_1(self, adapter, trending_ohlcv):
        """More memory bars → more True bars (5 vs 1)."""
        result_5 = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "qqe_signal_memory_bars": 5,
            },
        )
        result_1 = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "qqe_signal_memory_bars": 1,
            },
        )
        assert result_5["long"].sum() >= result_1["long"].sum()

    def test_memory_bars_10_vs_5(self, adapter, trending_ohlcv):
        """10-bar memory vs 5-bar memory → 10-bar has more or equal True bars."""
        result_10 = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "qqe_signal_memory_bars": 10,
            },
        )
        result_5 = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "qqe_signal_memory_bars": 5,
            },
        )
        assert result_10["long"].sum() >= result_5["long"].sum()

    def test_memory_disabled_explicit(self, adapter, trending_ohlcv):
        """disable_qqe_signal_memory=True → raw cross events only."""
        result = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "disable_qqe_signal_memory": True,
            },
        )
        # Count raw cross events — should be small relative to total bars
        total_bars = len(trending_ohlcv)
        long_count = result["long"].sum()
        # Raw crosses are rare events — typically < 10% of bars
        assert long_count < total_bars * 0.5, f"Raw crosses should be sparse, got {long_count}/{total_bars}"


# ============================================================
# 4. OPPOSITE SIGNAL
# ============================================================


class TestOppositeSignal:
    """opposite_qqe swaps long ↔ short."""

    def test_opposite_swaps_signals(self, adapter, trending_ohlcv):
        """With opposite=True, long and short should swap."""
        normal = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "disable_qqe_signal_memory": True,
            },
        )
        opposite = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "disable_qqe_signal_memory": True,
                "opposite_qqe": True,
            },
        )
        pd.testing.assert_series_equal(normal["long"], opposite["short"], check_names=False)
        pd.testing.assert_series_equal(normal["short"], opposite["long"], check_names=False)

    def test_opposite_signal_alias(self, adapter, trending_ohlcv):
        """opposite_signal should also work as an alias for opposite_qqe."""
        normal = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "disable_qqe_signal_memory": True,
            },
        )
        opposite = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "disable_qqe_signal_memory": True,
                "opposite_signal": True,
            },
        )
        pd.testing.assert_series_equal(normal["long"], opposite["short"], check_names=False)
        pd.testing.assert_series_equal(normal["short"], opposite["long"], check_names=False)

    def test_opposite_passthrough_no_effect(self, adapter, trending_ohlcv):
        """In passthrough mode (use_qqe=False), opposite has no effect — still all True."""
        result = _run(adapter, trending_ohlcv, {"use_qqe": False, "opposite_qqe": True})
        assert result["long"].all()
        assert result["short"].all()

    def test_opposite_with_memory(self, adapter, trending_ohlcv):
        """Opposite + memory should swap after memory expansion."""
        normal = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "qqe_signal_memory_bars": 5,
            },
        )
        opposite = _run(
            adapter,
            trending_ohlcv,
            {
                "use_qqe": True,
                "qqe_factor": 2.0,
                "qqe_signal_memory_bars": 5,
                "opposite_qqe": True,
            },
        )
        pd.testing.assert_series_equal(normal["long"], opposite["short"], check_names=False)
        pd.testing.assert_series_equal(normal["short"], opposite["long"], check_names=False)


# ============================================================
# 5. PARAMETER ALIASES
# ============================================================


class TestParameterAliases:
    """QQE universal node supports multiple param name aliases for backward compat."""

    def test_rsi_period_alias_rsiPeriod(self, adapter, trending_ohlcv):
        """rsiPeriod should work the same as rsi_period."""
        r1 = _run(adapter, trending_ohlcv, {"rsi_period": 10})
        r2 = _run(adapter, trending_ohlcv, {"rsiPeriod": 10})
        pd.testing.assert_series_equal(r1["qqe_line"], r2["qqe_line"], check_names=False)

    def test_rsi_period_alias_qqe_rsi_length(self, adapter, trending_ohlcv):
        """qqe_rsi_length (filter alias) should work for rsi_period."""
        r1 = _run(adapter, trending_ohlcv, {"rsi_period": 10})
        r2 = _run(adapter, trending_ohlcv, {"qqe_rsi_length": 10})
        pd.testing.assert_series_equal(r1["qqe_line"], r2["qqe_line"], check_names=False)

    def test_smoothing_alias_qqe_rsi_smoothing(self, adapter, trending_ohlcv):
        """qqe_rsi_smoothing (filter alias) should work for smoothing_period."""
        r1 = _run(adapter, trending_ohlcv, {"smoothing_period": 3})
        r2 = _run(adapter, trending_ohlcv, {"qqe_rsi_smoothing": 3})
        pd.testing.assert_series_equal(r1["qqe_line"], r2["qqe_line"], check_names=False)

    def test_qqe_factor_alias_qqeFactor(self, adapter, trending_ohlcv):
        """qqeFactor should work the same as qqe_factor."""
        r1 = _run(adapter, trending_ohlcv, {"qqe_factor": 3.0})
        r2 = _run(adapter, trending_ohlcv, {"qqeFactor": 3.0})
        pd.testing.assert_series_equal(r1["qqe_line"], r2["qqe_line"], check_names=False)

    def test_qqe_factor_alias_qqe_delta_multiplier(self, adapter, trending_ohlcv):
        """qqe_delta_multiplier (filter alias) should work for qqe_factor."""
        r1 = _run(adapter, trending_ohlcv, {"qqe_factor": 3.0})
        r2 = _run(adapter, trending_ohlcv, {"qqe_delta_multiplier": 3.0})
        pd.testing.assert_series_equal(r1["qqe_line"], r2["qqe_line"], check_names=False)


# ============================================================
# 6. QQE DATA INTEGRITY
# ============================================================


class TestQQEDataIntegrity:
    """Verify QQE output values are reasonable."""

    def test_rsi_ma_in_range(self, adapter, trending_ohlcv):
        """RSI-MA should be in [0, 100] range (like RSI)."""
        result = _run(adapter, trending_ohlcv, {})
        rsi_ma = result["rsi_ma"]
        valid = rsi_ma.dropna()
        assert (valid >= 0).all() and (valid <= 100).all(), "RSI-MA should be in [0, 100]"

    def test_upper_band_above_lower_band(self, adapter, trending_ohlcv):
        """Upper band should be >= lower band."""
        result = _run(adapter, trending_ohlcv, {})
        ub = result["upper_band"]
        lb = result["lower_band"]
        valid = ub.notna() & lb.notna()
        if valid.sum() > 0:
            assert (ub[valid] >= lb[valid]).all(), "Upper band must be >= lower band"

    def test_different_rsi_period_changes_output(self, adapter, trending_ohlcv):
        """Changing rsi_period should produce different QQE output."""
        r14 = _run(adapter, trending_ohlcv, {"rsi_period": 14})
        r7 = _run(adapter, trending_ohlcv, {"rsi_period": 7})
        assert not r14["qqe_line"].equals(r7["qqe_line"]), "Different periods → different QQE lines"

    def test_different_qqe_factor_changes_bands(self, adapter, trending_ohlcv):
        """Changing qqe_factor should widen/narrow the bands."""
        r_small = _run(adapter, trending_ohlcv, {"qqe_factor": 2.0})
        r_large = _run(adapter, trending_ohlcv, {"qqe_factor": 6.0})
        # Larger factor → wider bands (upper - lower should be larger)
        ub_small = r_small["upper_band"]
        lb_small = r_small["lower_band"]
        ub_large = r_large["upper_band"]
        lb_large = r_large["lower_band"]
        valid = ub_small.notna() & lb_small.notna() & ub_large.notna() & lb_large.notna()
        if valid.sum() > 10:
            width_small = (ub_small[valid] - lb_small[valid]).mean()
            width_large = (ub_large[valid] - lb_large[valid]).mean()
            assert width_large > width_small, "Larger QQE factor should produce wider bands"

    def test_series_length_matches_input(self, adapter, trending_ohlcv):
        """All output series should match input length."""
        result = _run(adapter, trending_ohlcv, {})
        for key, series in result.items():
            assert len(series) == len(trending_ohlcv), f"{key} length mismatch"


# ============================================================
# 7. EDGE CASES
# ============================================================


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_minimal_data(self, adapter):
        """Very short data (< warmup) should not crash."""
        ohlcv = pd.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [102, 103, 104],
                "low": [99, 100, 101],
                "close": [101, 102, 103],
                "volume": [1000, 1100, 1200],
            }
        )
        result = _run(adapter, ohlcv, {})
        assert "long" in result
        assert "short" in result
        assert len(result["qqe_line"]) == 3

    def test_flat_data_no_crosses(self, adapter, flat_ohlcv):
        """Flat data may produce zero or very few cross signals."""
        result = _run(adapter, flat_ohlcv, {"use_qqe": True, "disable_qqe_signal_memory": True})
        # Flat data → RSI stays near 50, few crosses expected
        total_signals = result["long"].sum() + result["short"].sum()
        # Just ensure it doesn't crash — signal count depends on noise
        assert total_signals >= 0

    def test_large_memory_bars(self, adapter, trending_ohlcv):
        """Very large memory bars (50) should not crash."""
        result = _run(adapter, trending_ohlcv, {"use_qqe": True, "qqe_signal_memory_bars": 50})
        assert result["long"].sum() >= 0

    def test_smoothing_period_1(self, adapter, trending_ohlcv):
        """smoothing_period=1 → minimal smoothing, should still work."""
        result = _run(adapter, trending_ohlcv, {"smoothing_period": 1})
        assert result["qqe_line"].notna().sum() > 0

    def test_qqe_factor_very_small(self, adapter, trending_ohlcv):
        """Very small QQE factor → tight bands, more cross signals."""
        result = _run(adapter, trending_ohlcv, {"use_qqe": True, "qqe_factor": 0.5, "disable_qqe_signal_memory": True})
        assert result["long"].sum() >= 0  # Should not crash


# ============================================================
# 8. BLOCK CATEGORY MAP CLEANUP
# ============================================================


class TestBlockCategoryCleanup:
    """Verify old duplicate blocks are properly removed."""

    def test_qqe_cross_not_in_category_map(self):
        """qqe_cross should NOT be in _BLOCK_CATEGORY_MAP (consolidated)."""
        from backend.agents.mcp.tools.strategy_builder import _BLOCK_CATEGORY_MAP

        assert "qqe_cross" not in _BLOCK_CATEGORY_MAP, "qqe_cross should be removed"

    def test_qqe_in_category_map(self):
        """qqe should still be in _BLOCK_CATEGORY_MAP as indicator."""
        from backend.agents.mcp.tools.strategy_builder import _BLOCK_CATEGORY_MAP

        assert _BLOCK_CATEGORY_MAP.get("qqe") == "indicator"

    def test_qqe_filter_not_in_category_map(self):
        """qqe_filter should NOT be in _BLOCK_CATEGORY_MAP (consolidated)."""
        from backend.agents.mcp.tools.strategy_builder import _BLOCK_CATEGORY_MAP

        assert "qqe_filter" not in _BLOCK_CATEGORY_MAP, "qqe_filter should be removed"


# ============================================================
# 9. PROMPT COMPLETENESS
# ============================================================


class TestPromptCompleteness:
    """Verify QQE is documented in LLM prompt templates."""

    def test_qqe_in_available_indicators(self):
        """QQE should be listed in AVAILABLE INDICATORS."""
        from backend.agents.prompts.templates import STRATEGY_GENERATION_TEMPLATE

        assert "QQE" in STRATEGY_GENERATION_TEMPLATE

    def test_qqe_universal_node_section_exists(self):
        """QQE UNIVERSAL NODE section should exist in the prompt."""
        from backend.agents.prompts.templates import STRATEGY_GENERATION_TEMPLATE

        assert "QQE UNIVERSAL NODE" in STRATEGY_GENERATION_TEMPLATE

    def test_qqe_prompt_mentions_cross_signal(self):
        """Prompt should explain cross signal mode."""
        from backend.agents.prompts.templates import STRATEGY_GENERATION_TEMPLATE

        assert "cross" in STRATEGY_GENERATION_TEMPLATE.lower() or "RSI-MA" in STRATEGY_GENERATION_TEMPLATE

    def test_qqe_prompt_mentions_use_qqe(self):
        """Prompt should document use_qqe parameter."""
        from backend.agents.prompts.templates import STRATEGY_GENERATION_TEMPLATE

        assert "use_qqe" in STRATEGY_GENERATION_TEMPLATE

    def test_qqe_prompt_mentions_signal_memory(self):
        """Prompt should document signal memory."""
        from backend.agents.prompts.templates import STRATEGY_GENERATION_TEMPLATE

        assert "qqe_signal_memory_bars" in STRATEGY_GENERATION_TEMPLATE

    def test_qqe_prompt_mentions_opposite(self):
        """Prompt should document opposite_qqe."""
        from backend.agents.prompts.templates import STRATEGY_GENERATION_TEMPLATE

        assert "opposite_qqe" in STRATEGY_GENERATION_TEMPLATE

    def test_qqe_prompt_mentions_rsi_period(self):
        """Prompt should document rsi_period parameter."""
        from backend.agents.prompts.templates import STRATEGY_GENERATION_TEMPLATE

        assert "rsi_period" in STRATEGY_GENERATION_TEMPLATE

    def test_qqe_prompt_mentions_qqe_factor(self):
        """Prompt should document qqe_factor parameter."""
        from backend.agents.prompts.templates import STRATEGY_GENERATION_TEMPLATE

        assert "qqe_factor" in STRATEGY_GENERATION_TEMPLATE

    def test_qqe_prompt_optimization_ranges(self):
        """Prompt should include QQE optimization ranges."""
        from backend.agents.prompts.templates import STRATEGY_GENERATION_TEMPLATE

        assert "OPTIMIZATION RANGES (QQE)" in STRATEGY_GENERATION_TEMPLATE

    def test_qqe_few_shot_example_exists(self):
        """QQE few-shot example should exist."""
        from backend.agents.prompts.templates import STRATEGY_EXAMPLE_QQE_MOMENTUM

        assert "QQE" in STRATEGY_EXAMPLE_QQE_MOMENTUM
        assert "use_qqe" in STRATEGY_EXAMPLE_QQE_MOMENTUM


# ============================================================
# 10. FRONTEND CONSOLIDATION
# ============================================================


class TestFrontendConsolidation:
    """Verify frontend properly consolidated QQE blocks."""

    def test_frontend_qqe_filter_removed_from_list(self):
        """qqe_filter should be commented out in the filters list."""
        frontend_path = project_root / "frontend" / "js" / "pages" / "strategy_builder.js"
        content = frontend_path.read_text(encoding="utf-8")
        # Should NOT have an active qqe_filter entry in filters
        # Allow comment references but not active { id: 'qqe_filter' }
        lines = content.split("\n")
        active_qqe_filter_entries = [
            line for line in lines if "id: 'qqe_filter'" in line and not line.strip().startswith("//")
        ]
        assert len(active_qqe_filter_entries) == 0, "qqe_filter should be removed from filters list"

    def test_frontend_qqe_indicator_has_filter_params(self):
        """QQE indicator defaults should include filter params (use_qqe, etc.)."""
        frontend_path = project_root / "frontend" / "js" / "pages" / "strategy_builder.js"
        content = frontend_path.read_text(encoding="utf-8")
        assert "use_qqe" in content, "use_qqe should be in QQE indicator defaults"
        assert "opposite_qqe" in content, "opposite_qqe should be in QQE indicator defaults"
        assert "disable_qqe_signal_memory" in content
        assert "qqe_signal_memory_bars" in content


# ============================================================
# 11. API INTEGRATION
# ============================================================


class TestAPIIntegration:
    """Test QQE via the API endpoints."""

    def test_api_health(self):
        """API should respond to health check."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_api_block_types_includes_qqe(self):
        """Block types endpoint should include qqe as indicator."""
        response = client.get("/api/v1/strategy-builder/block-types")
        if response.status_code == 200:
            data = response.json()
            # Find qqe in the response (structure varies)
            text = str(data).lower()
            assert "qqe" in text, "qqe should be available as a block type"
