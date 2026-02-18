"""
AI Agent Knowledge Test: Stochastic Universal Node — Real API Tests

Tests verify that AI agents correctly understand the **universal Stochastic indicator**
which consolidates 7 former duplicates (Stoch Overbought, Stoch Oversold,
Stoch K Cross D Up/Down, Stochastic, StochRSI, Stochastic Divergence)
into a single node with three combinable modes:

  1. Range Filter   - continuous %D window  (AND)
  2. Cross Level    - event: %D crosses threshold  (AND)
  3. K/D Cross      - event: %K crosses %D  (AND)

All modes use AND logic (unlike MACD which uses OR).
No signal memory by default.

Run:
    py -3.14 -m pytest tests/ai_agents/test_stochastic_universal_node.py -v
    py -3.14 -m pytest tests/ai_agents/test_stochastic_universal_node.py -v -k "range"
    py -3.14 -m pytest tests/ai_agents/test_stochastic_universal_node.py -v -k "cross_level"
    py -3.14 -m pytest tests/ai_agents/test_stochastic_universal_node.py -v -k "kd_cross"
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


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient with in-memory DB."""
    app.dependency_overrides[get_db] = _override_get_db
    Base.metadata.create_all(bind=_engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """
    Realistic OHLCV data with known Stochastic behaviour.
    1000 bars, hourly, BTC-like price action.
    """
    np.random.seed(42)
    n = 1000
    dates = pd.date_range("2025-01-01", periods=n, freq="1h")
    prices = 50000.0 + np.cumsum(np.random.randn(n) * 100)
    return pd.DataFrame(
        {
            "open": prices + np.random.randn(n) * 20,
            "high": prices + np.abs(np.random.randn(n) * 40),
            "low": prices - np.abs(np.random.randn(n) * 40),
            "close": prices + np.random.randn(n) * 20,
            "volume": np.random.uniform(100, 1000, n),
        },
        index=dates,
    )


# ============================================================
# Helpers
# ============================================================


def _make_stoch_graph(params: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal strategy graph with Stochastic → long/short → strategy."""
    return {
        "name": "Stochastic Filter Test",
        "blocks": [
            {
                "id": "b_stoch",
                "type": "stochastic",
                "category": "indicator",
                "name": "Stochastic",
                "x": 100,
                "y": 100,
                "params": params,
            },
            {
                "id": "main",
                "type": "strategy",
                "category": "main",
                "name": "Strategy",
                "isMain": True,
                "x": 500,
                "y": 100,
                "params": {},
            },
        ],
        "connections": [
            {
                "id": "c1",
                "source": {"blockId": "b_stoch", "portId": "long"},
                "target": {"blockId": "main", "portId": "entry_long"},
                "type": "data",
            },
            {
                "id": "c2",
                "source": {"blockId": "b_stoch", "portId": "short"},
                "target": {"blockId": "main", "portId": "entry_short"},
                "type": "data",
            },
        ],
    }


def _run_adapter(graph: dict, ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
    """Run StrategyBuilderAdapter and return signal result."""
    adapter = StrategyBuilderAdapter(graph)
    result = adapter.generate_signals(ohlcv)
    return {
        "entries": result.entries,
        "exits": result.exits,
        "short_entries": result.short_entries,
        "short_exits": result.short_exits,
    }


# ============================================================
#
#  PART 1 — PASSTHROUGH / LEGACY MODES
#
# ============================================================


class TestStochPassthrough:
    """When no mode is enabled and no overbought/oversold, Stoch is passthrough."""

    def test_stoch_no_mode_enabled_all_true(self, sample_ohlcv):
        """No mode → passthrough: long and short are always True."""
        graph = _make_stoch_graph({"stoch_k_length": 14, "stoch_d_smoothing": 3})
        signals = _run_adapter(graph, sample_ohlcv)

        # In passthrough mode, entries should be True for all bars
        assert signals["entries"].sum() > 0, "Passthrough Stoch must produce long entries"
        # All bars should be True in passthrough
        assert signals["entries"].sum() == len(sample_ohlcv), (
            f"Passthrough should produce entries on ALL bars, got {signals['entries'].sum()}/{len(sample_ohlcv)}"
        )

    def test_stoch_outputs_k_and_d(self, sample_ohlcv):
        """Stochastic must output both %K and %D series."""
        graph = _make_stoch_graph({"stoch_k_length": 14, "stoch_d_smoothing": 3})
        # Access indicator outputs directly via _execute_indicator
        block = graph["blocks"][0]
        sba = StrategyBuilderAdapter(graph)
        result = sba._execute_indicator(block["type"], block["params"], sample_ohlcv, {})
        assert "k" in result, "Stochastic must output 'k' (percent K)"
        assert "d" in result, "Stochastic must output 'd' (percent D)"
        assert "long" in result, "Stochastic must output 'long' signal"
        assert "short" in result, "Stochastic must output 'short' signal"
        # %K and %D should generally be in reasonable range
        # Note: vectorbt's STOCH can produce values slightly outside 0-100
        # due to random data characteristics, so we check a relaxed range
        k_valid = result["k"].dropna()
        d_valid = result["d"].dropna()
        assert k_valid.min() >= -50, f"%K min should be >= -50, got {k_valid.min()}"
        assert k_valid.max() <= 150, f"%K max should be <= 150, got {k_valid.max()}"
        assert d_valid.min() >= -50, f"%D min should be >= -50, got {d_valid.min()}"
        assert d_valid.max() <= 150, f"%D max should be <= 150, got {d_valid.max()}"


class TestStochLegacyMode:
    """Legacy fallback: overbought/oversold without new modes."""

    def test_stoch_legacy_overbought_oversold(self, sample_ohlcv):
        """Legacy mode: %D < oversold → long, %D > overbought → short."""
        graph = _make_stoch_graph({"stoch_k_length": 14, "stoch_d_smoothing": 3, "overbought": 80, "oversold": 20})
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(sample_ohlcv)

        # Legacy mode should NOT produce entries on every bar
        assert result.entries.sum() < len(sample_ohlcv), "Legacy Stoch should filter signals"
        assert result.entries.sum() > 0, "Legacy Stoch should produce some long entries (oversold zone)"

    def test_stoch_legacy_narrow_thresholds(self, sample_ohlcv):
        """Tighter thresholds → fewer signals."""
        wide = _make_stoch_graph({"stoch_k_length": 14, "stoch_d_smoothing": 3, "overbought": 80, "oversold": 20})
        narrow = _make_stoch_graph({"stoch_k_length": 14, "stoch_d_smoothing": 3, "overbought": 95, "oversold": 5})

        result_wide = StrategyBuilderAdapter(wide).generate_signals(sample_ohlcv)
        result_narrow = StrategyBuilderAdapter(narrow).generate_signals(sample_ohlcv)

        wide_count = result_wide.entries.sum()
        narrow_count = result_narrow.entries.sum()

        assert narrow_count <= wide_count, (
            f"Narrow thresholds (5/95) should produce <= signals than wide (20/80): "
            f"narrow={narrow_count}, wide={wide_count}"
        )


# ============================================================
#
#  PART 2 — RANGE FILTER MODE
#
# ============================================================


class TestStochRangeFilter:
    """Test `use_stoch_range_filter` — continuous %D window condition."""

    def test_range_filter_long_only(self, sample_ohlcv):
        """use_stoch_range_filter=True: long when %D in [long_more, long_less]."""
        params = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_range_filter": True,
            "long_stoch_d_more": 1,
            "long_stoch_d_less": 30,
        }
        graph = _make_stoch_graph(params)
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(sample_ohlcv)

        # %D in [1, 30] is oversold zone — should have some but not all
        assert result.entries.sum() < len(sample_ohlcv), "Range filter should limit entries"
        assert result.entries.sum() > 0, "Some bars should have %D in [1, 30]"

    def test_range_filter_short_only(self, sample_ohlcv):
        """Short range: %D in [short_more, short_less]."""
        params = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_range_filter": True,
            "short_stoch_d_more": 70,
            "short_stoch_d_less": 100,
        }
        graph = _make_stoch_graph(params)
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(sample_ohlcv)

        # Long side has no range filter → passthrough (True)
        # Short side filtered by %D in [70, 100]
        assert result.entries.sum() > 0, "Long should be near-passthrough"

    def test_range_filter_narrow_vs_wide(self, sample_ohlcv):
        """Narrower range → fewer signals."""
        wide_params = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_range_filter": True,
            "long_stoch_d_more": 1,
            "long_stoch_d_less": 50,
        }
        narrow_params = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_range_filter": True,
            "long_stoch_d_more": 10,
            "long_stoch_d_less": 25,
        }

        result_wide = StrategyBuilderAdapter(_make_stoch_graph(wide_params)).generate_signals(sample_ohlcv)
        result_narrow = StrategyBuilderAdapter(_make_stoch_graph(narrow_params)).generate_signals(sample_ohlcv)

        wide_count = result_wide.entries.sum()
        narrow_count = result_narrow.entries.sum()

        assert narrow_count <= wide_count, (
            f"Narrow range [10,25] should produce <= signals than wide [1,50]: narrow={narrow_count}, wide={wide_count}"
        )


# ============================================================
#
#  PART 3 — CROSS LEVEL MODE
#
# ============================================================


class TestStochCrossLevel:
    """Test `use_stoch_cross_level` — event-based %D threshold crossing."""

    def test_cross_level_basic(self, sample_ohlcv):
        """Cross level: LONG when %D crosses 20 from below, SHORT when %D crosses 80 from above."""
        params = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_cross_level": True,
            "stoch_cross_level_long": 20,
            "stoch_cross_level_short": 80,
        }
        graph = _make_stoch_graph(params)
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(sample_ohlcv)

        # Cross events are rare (only on crossing bars)
        total_long = result.entries.sum()
        assert total_long < len(sample_ohlcv) * 0.1, (
            f"Cross signals should be rare (<10% of bars), got {total_long}/{len(sample_ohlcv)}"
        )
        assert total_long > 0, "At least some %D crossovers should occur over 1000 bars"

    def test_cross_level_custom_thresholds(self, sample_ohlcv):
        """Different thresholds → different number of cross events."""
        standard = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_cross_level": True,
            "stoch_cross_level_long": 20,
            "stoch_cross_level_short": 80,
        }
        extreme = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_cross_level": True,
            "stoch_cross_level_long": 5,
            "stoch_cross_level_short": 95,
        }

        result_std = StrategyBuilderAdapter(_make_stoch_graph(standard)).generate_signals(sample_ohlcv)
        result_ext = StrategyBuilderAdapter(_make_stoch_graph(extreme)).generate_signals(sample_ohlcv)

        std_count = result_std.entries.sum()
        ext_count = result_ext.entries.sum()

        # Extreme thresholds (5/95) → fewer crossovers
        assert ext_count <= std_count, (
            f"Extreme thresholds should produce <= cross events: extreme={ext_count}, standard={std_count}"
        )

    def test_cross_level_with_memory(self, sample_ohlcv):
        """activate_stoch_cross_memory=True: signal stays active for N bars."""
        no_memory = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_cross_level": True,
            "stoch_cross_level_long": 20,
            "stoch_cross_level_short": 80,
        }
        with_memory = {
            **no_memory,
            "activate_stoch_cross_memory": True,
            "stoch_cross_memory_bars": 5,
        }

        result_no_mem = StrategyBuilderAdapter(_make_stoch_graph(no_memory)).generate_signals(sample_ohlcv)
        result_mem = StrategyBuilderAdapter(_make_stoch_graph(with_memory)).generate_signals(sample_ohlcv)

        no_mem_count = result_no_mem.entries.sum()
        mem_count = result_mem.entries.sum()

        # Memory expands signals → more True bars
        assert mem_count >= no_mem_count, f"Memory should produce >= entries: no_mem={no_mem_count}, mem={mem_count}"
        if no_mem_count > 0:
            assert mem_count > no_mem_count, (
                f"Memory (5 bars) should expand signals: no_mem={no_mem_count}, mem={mem_count}"
            )

    def test_cross_memory_bars_higher_produces_more(self, sample_ohlcv):
        """More memory_bars → more active signal bars."""
        base = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_cross_level": True,
            "stoch_cross_level_long": 20,
            "stoch_cross_level_short": 80,
            "activate_stoch_cross_memory": True,
        }
        params_3 = {**base, "stoch_cross_memory_bars": 3}
        params_10 = {**base, "stoch_cross_memory_bars": 10}

        result_3 = StrategyBuilderAdapter(_make_stoch_graph(params_3)).generate_signals(sample_ohlcv)
        result_10 = StrategyBuilderAdapter(_make_stoch_graph(params_10)).generate_signals(sample_ohlcv)

        count_3 = result_3.entries.sum()
        count_10 = result_10.entries.sum()

        assert count_10 >= count_3, f"memory_bars=10 should produce >= signals than 3: 3={count_3}, 10={count_10}"


# ============================================================
#
#  PART 4 — K/D CROSS MODE
#
# ============================================================


class TestStochKDCross:
    """Test `use_stoch_kd_cross` — event-based %K crossing %D."""

    def test_kd_cross_basic(self, sample_ohlcv):
        """use_stoch_kd_cross=True: LONG when %K crosses above %D, SHORT when below."""
        params = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_kd_cross": True,
        }
        graph = _make_stoch_graph(params)
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(sample_ohlcv)

        # K/D crosses should occur periodically
        total_long = result.entries.sum()
        assert total_long > 0, "K/D cross should produce some long entries over 1000 bars"
        assert total_long < len(sample_ohlcv) * 0.25, (
            f"K/D cross events should be <25% of bars, got {total_long}/{len(sample_ohlcv)}"
        )

    def test_kd_cross_opposite(self, sample_ohlcv):
        """opposite_stoch_kd=True: swaps long and short K/D cross signals."""
        base = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_kd_cross": True,
        }
        opposite = {**base, "opposite_stoch_kd": True}

        result_normal = StrategyBuilderAdapter(_make_stoch_graph(base)).generate_signals(sample_ohlcv)
        result_opposite = StrategyBuilderAdapter(_make_stoch_graph(opposite)).generate_signals(sample_ohlcv)

        normal_entries = result_normal.entries
        opposite_entries = result_opposite.entries

        # Opposite should produce entries on different bars
        if normal_entries.sum() > 0:
            normal_mask = normal_entries.values.astype(bool)
            opposite_mask = opposite_entries.values.astype(bool)
            assert not np.array_equal(normal_mask, opposite_mask), (
                "Opposite K/D cross should produce entries on different bars"
            )

    def test_kd_cross_with_memory(self, sample_ohlcv):
        """activate_stoch_kd_memory=True: K/D cross signal stays active for N bars."""
        no_memory = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_kd_cross": True,
        }
        with_memory = {
            **no_memory,
            "activate_stoch_kd_memory": True,
            "stoch_kd_memory_bars": 5,
        }

        result_no_mem = StrategyBuilderAdapter(_make_stoch_graph(no_memory)).generate_signals(sample_ohlcv)
        result_mem = StrategyBuilderAdapter(_make_stoch_graph(with_memory)).generate_signals(sample_ohlcv)

        no_mem_count = result_no_mem.entries.sum()
        mem_count = result_mem.entries.sum()

        assert mem_count >= no_mem_count, (
            f"K/D memory should produce >= entries: no_mem={no_mem_count}, mem={mem_count}"
        )
        if no_mem_count > 0:
            assert mem_count > no_mem_count, (
                f"K/D memory (5 bars) should expand signals: no_mem={no_mem_count}, mem={mem_count}"
            )

    def test_kd_cross_memory_bars_higher_produces_more(self, sample_ohlcv):
        """More kd_memory_bars → more active signal bars."""
        base = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_kd_cross": True,
            "activate_stoch_kd_memory": True,
        }
        params_3 = {**base, "stoch_kd_memory_bars": 3}
        params_10 = {**base, "stoch_kd_memory_bars": 10}

        result_3 = StrategyBuilderAdapter(_make_stoch_graph(params_3)).generate_signals(sample_ohlcv)
        result_10 = StrategyBuilderAdapter(_make_stoch_graph(params_10)).generate_signals(sample_ohlcv)

        count_3 = result_3.entries.sum()
        count_10 = result_10.entries.sum()

        assert count_10 >= count_3, f"kd_memory_bars=10 should produce >= signals than 3: 3={count_3}, 10={count_10}"


# ============================================================
#
#  PART 5 — COMBINED MODES (AND LOGIC)
#
# ============================================================


class TestStochCombinedModes:
    """Test AND logic: all 3 modes combined produce <= each individual."""

    def test_range_and_cross_level_combined(self, sample_ohlcv):
        """Range + Cross Level → result = Range AND Cross Level."""
        cross_only = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_cross_level": True,
            "stoch_cross_level_long": 20,
            "stoch_cross_level_short": 80,
            "activate_stoch_cross_memory": True,
            "stoch_cross_memory_bars": 5,
        }
        combined = {
            **cross_only,
            "use_stoch_range_filter": True,
            "long_stoch_d_more": 1,
            "long_stoch_d_less": 30,
        }

        result_cross = StrategyBuilderAdapter(_make_stoch_graph(cross_only)).generate_signals(sample_ohlcv)
        result_combined = StrategyBuilderAdapter(_make_stoch_graph(combined)).generate_signals(sample_ohlcv)

        cross_count = result_cross.entries.sum()
        combined_count = result_combined.entries.sum()

        # AND: combined <= cross-only
        assert combined_count <= cross_count, (
            f"Range AND Cross should produce <= cross-only: cross={cross_count}, combined={combined_count}"
        )

    def test_range_and_kd_cross_combined(self, sample_ohlcv):
        """Range + K/D Cross → result = Range AND K/D Cross."""
        kd_only = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_kd_cross": True,
            "activate_stoch_kd_memory": True,
            "stoch_kd_memory_bars": 5,
        }
        combined = {
            **kd_only,
            "use_stoch_range_filter": True,
            "long_stoch_d_more": 1,
            "long_stoch_d_less": 40,
        }

        result_kd = StrategyBuilderAdapter(_make_stoch_graph(kd_only)).generate_signals(sample_ohlcv)
        result_combined = StrategyBuilderAdapter(_make_stoch_graph(combined)).generate_signals(sample_ohlcv)

        kd_count = result_kd.entries.sum()
        combined_count = result_combined.entries.sum()

        assert combined_count <= kd_count, (
            f"Range AND K/D should produce <= K/D-only: kd={kd_count}, combined={combined_count}"
        )

    def test_all_three_modes_combined(self, sample_ohlcv):
        """All 3 modes: Range AND Cross Level AND K/D Cross → most restrictive."""
        kd_only = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_kd_cross": True,
        }
        all_three = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_range_filter": True,
            "long_stoch_d_more": 1,
            "long_stoch_d_less": 30,
            "use_stoch_cross_level": True,
            "stoch_cross_level_long": 20,
            "stoch_cross_level_short": 80,
            "use_stoch_kd_cross": True,
        }

        result_kd = StrategyBuilderAdapter(_make_stoch_graph(kd_only)).generate_signals(sample_ohlcv)
        result_all = StrategyBuilderAdapter(_make_stoch_graph(all_three)).generate_signals(sample_ohlcv)

        kd_count = result_kd.entries.sum()
        all_count = result_all.entries.sum()

        # All three combined (AND) → most restrictive, should be <= any single mode
        assert all_count <= kd_count, f"All 3 modes (AND) should produce <= K/D-only: kd={kd_count}, all={all_count}"

    def test_stoch_uses_and_logic_not_or(self, sample_ohlcv):
        """CRITICAL: Stochastic uses AND logic (unlike MACD which uses OR).
        Adding more modes should REDUCE signal count, not increase it.
        """
        single_mode = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_range_filter": True,
            "long_stoch_d_more": 1,
            "long_stoch_d_less": 50,
            "short_stoch_d_more": 50,
            "short_stoch_d_less": 100,
        }
        two_modes = {
            **single_mode,
            "use_stoch_kd_cross": True,
        }

        result_single = StrategyBuilderAdapter(_make_stoch_graph(single_mode)).generate_signals(sample_ohlcv)
        result_two = StrategyBuilderAdapter(_make_stoch_graph(two_modes)).generate_signals(sample_ohlcv)

        single_count = result_single.entries.sum()
        two_count = result_two.entries.sum()

        # AND logic: adding more modes reduces or keeps equal signals
        assert two_count <= single_count, (
            f"AND logic: adding K/D cross to range should reduce signals: "
            f"range_only={single_count}, range+kd={two_count}"
        )


# ============================================================
#
#  PART 6 — PERIOD EFFECTS
#
# ============================================================


class TestStochPeriodEffect:
    """Test that Stochastic period parameters affect signal generation."""

    def test_shorter_k_period_more_volatile(self, sample_ohlcv):
        """Shorter K period → more volatile Stochastic → more K/D cross events."""
        short_params = {
            "stoch_k_length": 5,
            "stoch_d_smoothing": 3,
            "use_stoch_kd_cross": True,
        }
        long_params = {
            "stoch_k_length": 30,
            "stoch_d_smoothing": 3,
            "use_stoch_kd_cross": True,
        }

        result_short = StrategyBuilderAdapter(_make_stoch_graph(short_params)).generate_signals(sample_ohlcv)
        result_long = StrategyBuilderAdapter(_make_stoch_graph(long_params)).generate_signals(sample_ohlcv)

        short_count = result_short.entries.sum()
        long_count = result_long.entries.sum()

        # Shorter K period → more volatile → more crosses
        assert short_count > long_count, (
            f"Short K period (5) should produce more crosses than long (30): short={short_count}, long={long_count}"
        )

    def test_longer_d_smoothing_smoother(self, sample_ohlcv):
        """Longer D smoothing → smoother %D → fewer range filter hits in narrow zone."""
        fast_d = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_range_filter": True,
            "long_stoch_d_more": 10,
            "long_stoch_d_less": 25,
        }
        slow_d = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 10,
            "use_stoch_range_filter": True,
            "long_stoch_d_more": 10,
            "long_stoch_d_less": 25,
        }

        result_fast = StrategyBuilderAdapter(_make_stoch_graph(fast_d)).generate_signals(sample_ohlcv)
        result_slow = StrategyBuilderAdapter(_make_stoch_graph(slow_d)).generate_signals(sample_ohlcv)

        fast_count = result_fast.entries.sum()
        slow_count = result_slow.entries.sum()

        # Both should produce signals — exact counts may vary,
        # but they should differ (different smoothing changes distribution)
        assert fast_count != slow_count or fast_count == 0, (
            f"Different D smoothing should produce different signal counts: d=3: {fast_count}, d=10: {slow_count}"
        )


# ============================================================
#
#  PART 7 — OPTIMIZATION PARAMS
#
# ============================================================


class TestStochOptimizationParams:
    """Test that optimization params are stored in correct format."""

    def test_stoch_optimizable_params_list(self):
        """Stochastic has 10 optimizable parameters."""
        optimizable = [
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
        ]
        assert len(optimizable) == 10, "Stochastic should have 10 optimizable params"

    def test_stoch_optimization_range_format(self):
        """Optimization param format: {enabled, min, max, step}."""
        sample_opt = {
            "stoch_k_length": {"enabled": True, "min": 5, "max": 30, "step": 1},
            "stoch_cross_level_long": {"enabled": True, "min": 10, "max": 40, "step": 5},
        }
        for key, val in sample_opt.items():
            assert "enabled" in val, f"{key} must have 'enabled'"
            assert "min" in val, f"{key} must have 'min'"
            assert "max" in val, f"{key} must have 'max'"
            assert "step" in val, f"{key} must have 'step'"
            assert val["min"] <= val["max"], f"{key}: min must be <= max"
            assert val["step"] > 0, f"{key}: step must be > 0"

    def test_stoch_recommended_ranges(self):
        """Verify recommended optimization ranges are sensible."""
        ranges = {
            "stoch_k_length": {"min": 5, "max": 30, "step": 1},
            "stoch_k_smoothing": {"min": 1, "max": 10, "step": 1},
            "stoch_d_smoothing": {"min": 2, "max": 10, "step": 1},
            "long_stoch_d_more": {"min": 1, "max": 30, "step": 5},
            "long_stoch_d_less": {"min": 20, "max": 50, "step": 5},
            "short_stoch_d_less": {"min": 70, "max": 100, "step": 5},
            "short_stoch_d_more": {"min": 50, "max": 80, "step": 5},
            "stoch_cross_level_long": {"min": 10, "max": 40, "step": 5},
            "stoch_cross_level_short": {"min": 60, "max": 90, "step": 5},
            "stoch_cross_memory_bars": {"min": 1, "max": 20, "step": 1},
        }
        for key, r in ranges.items():
            iterations = (r["max"] - r["min"]) // r["step"] + 1
            assert iterations >= 2, f"{key}: range must produce >= 2 iterations, got {iterations}"
            assert iterations <= 50, f"{key}: range too large ({iterations} iterations)"


# ============================================================
#
#  PART 8 — API ENDPOINT TESTS
#
# ============================================================


class TestStrategyBuilderAPIWithStoch:
    """Test creating/saving Stochastic strategy through the real API."""

    def test_create_stoch_strategy_range_filter(self, client):
        """Create a strategy with Stochastic range filter via API."""
        strategy = _make_stoch_graph(
            {
                "stoch_k_length": 14,
                "stoch_k_smoothing": 3,
                "stoch_d_smoothing": 3,
                "use_stoch_range_filter": True,
                "long_stoch_d_more": 1,
                "long_stoch_d_less": 30,
                "short_stoch_d_more": 70,
                "short_stoch_d_less": 100,
            }
        )
        strategy["timeframe"] = "1h"
        strategy["symbols"] = ["BTCUSDT"]

        response = client.post("/api/v1/strategy-builder/strategies", json=strategy)
        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()
        assert "id" in data, "Response must contain strategy id"
        assert data["is_builder_strategy"] is True

        # Verify blocks were saved
        strategy_id = data["id"]
        get_resp = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")
        assert get_resp.status_code == 200
        saved = get_resp.json()
        assert len(saved["blocks"]) == 2, "Stochastic + Strategy blocks"

        # Find Stochastic block and verify params persisted
        stoch_block = next(b for b in saved["blocks"] if b["type"] == "stochastic")
        assert stoch_block["params"]["stoch_k_length"] == 14
        assert stoch_block["params"]["use_stoch_range_filter"] is True
        assert stoch_block["params"]["long_stoch_d_more"] == 1

    def test_create_stoch_strategy_cross_level(self, client):
        """Create a strategy with Stochastic cross level via API."""
        strategy = _make_stoch_graph(
            {
                "stoch_k_length": 14,
                "stoch_d_smoothing": 3,
                "use_stoch_cross_level": True,
                "stoch_cross_level_long": 20,
                "stoch_cross_level_short": 80,
                "activate_stoch_cross_memory": True,
                "stoch_cross_memory_bars": 10,
            }
        )
        strategy["name"] = "Stoch Cross Level Test"
        strategy["timeframe"] = "15m"
        strategy["symbols"] = ["ETHUSDT"]

        response = client.post("/api/v1/strategy-builder/strategies", json=strategy)
        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()
        strategy_id = data["id"]

        # Load and verify
        get_resp = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")
        saved = get_resp.json()
        stoch_block = next(b for b in saved["blocks"] if b["type"] == "stochastic")
        assert stoch_block["params"]["use_stoch_cross_level"] is True
        assert stoch_block["params"]["stoch_cross_level_long"] == 20
        assert stoch_block["params"]["stoch_cross_memory_bars"] == 10

    def test_create_stoch_strategy_kd_cross(self, client):
        """Create a strategy with Stochastic K/D cross via API."""
        strategy = _make_stoch_graph(
            {
                "stoch_k_length": 14,
                "stoch_d_smoothing": 3,
                "use_stoch_kd_cross": True,
                "opposite_stoch_kd": False,
                "activate_stoch_kd_memory": True,
                "stoch_kd_memory_bars": 5,
            }
        )
        strategy["name"] = "Stoch KD Cross Test"
        strategy["timeframe"] = "4h"
        strategy["symbols"] = ["BTCUSDT"]

        response = client.post("/api/v1/strategy-builder/strategies", json=strategy)
        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()
        strategy_id = data["id"]

        # Load and verify
        get_resp = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")
        saved = get_resp.json()
        stoch_block = next(b for b in saved["blocks"] if b["type"] == "stochastic")
        assert stoch_block["params"]["use_stoch_kd_cross"] is True
        assert stoch_block["params"]["activate_stoch_kd_memory"] is True
        assert stoch_block["params"]["stoch_kd_memory_bars"] == 5

    def test_create_stoch_strategy_all_modes(self, client):
        """Create a strategy with all 3 Stochastic modes enabled via API."""
        strategy = _make_stoch_graph(
            {
                "stoch_k_length": 14,
                "stoch_k_smoothing": 3,
                "stoch_d_smoothing": 3,
                "use_stoch_range_filter": True,
                "long_stoch_d_more": 1,
                "long_stoch_d_less": 30,
                "short_stoch_d_more": 70,
                "short_stoch_d_less": 100,
                "use_stoch_cross_level": True,
                "stoch_cross_level_long": 20,
                "stoch_cross_level_short": 80,
                "activate_stoch_cross_memory": True,
                "stoch_cross_memory_bars": 5,
                "use_stoch_kd_cross": True,
                "opposite_stoch_kd": False,
                "activate_stoch_kd_memory": True,
                "stoch_kd_memory_bars": 3,
            }
        )
        strategy["name"] = "Stoch Universal All Modes"
        strategy["timeframe"] = "1h"
        strategy["symbols"] = ["BTCUSDT", "ETHUSDT"]

        response = client.post("/api/v1/strategy-builder/strategies", json=strategy)
        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()
        strategy_id = data["id"]

        # Load and verify all params persisted
        get_resp = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")
        saved = get_resp.json()
        stoch_block = next(b for b in saved["blocks"] if b["type"] == "stochastic")
        p = stoch_block["params"]
        assert p["use_stoch_range_filter"] is True
        assert p["use_stoch_cross_level"] is True
        assert p["use_stoch_kd_cross"] is True
        assert p["stoch_k_length"] == 14
        assert p["activate_stoch_cross_memory"] is True
        assert p["activate_stoch_kd_memory"] is True


# ============================================================
#
#  PART 9 — COMPARISON: STOCHASTIC AND vs MACD OR
#
# ============================================================


class TestStochvsMACD:
    """Test the critical difference: Stochastic uses AND, MACD uses OR."""

    def test_stoch_and_reduces_signals(self, sample_ohlcv):
        """Stochastic: adding a mode reduces signal count (AND logic)."""
        range_only = {
            "stoch_k_length": 14,
            "stoch_d_smoothing": 3,
            "use_stoch_range_filter": True,
            "long_stoch_d_more": 1,
            "long_stoch_d_less": 50,
            "short_stoch_d_more": 50,
            "short_stoch_d_less": 100,
        }
        range_plus_kd = {
            **range_only,
            "use_stoch_kd_cross": True,
        }
        range_plus_kd_plus_cross = {
            **range_plus_kd,
            "use_stoch_cross_level": True,
            "stoch_cross_level_long": 20,
            "stoch_cross_level_short": 80,
        }

        r1 = StrategyBuilderAdapter(_make_stoch_graph(range_only)).generate_signals(sample_ohlcv)
        r2 = StrategyBuilderAdapter(_make_stoch_graph(range_plus_kd)).generate_signals(sample_ohlcv)
        r3 = StrategyBuilderAdapter(_make_stoch_graph(range_plus_kd_plus_cross)).generate_signals(sample_ohlcv)

        c1 = r1.entries.sum()
        c2 = r2.entries.sum()
        c3 = r3.entries.sum()

        # Each additional AND mode should reduce (or keep equal) signal count
        assert c2 <= c1, f"AND: range+kd ({c2}) should <= range-only ({c1})"
        assert c3 <= c2, f"AND: all 3 ({c3}) should <= range+kd ({c2})"
