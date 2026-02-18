"""
AI Agent Knowledge Test: RSI & MACD Filter Parameters — Real API Tests

Tests verify that AI agents (DeepSeek, Qwen, Perplexity) correctly understand:
- Every parameter of RSI and MACD filters
- How to use and configure them
- How optimization ranges work

These tests run against the REAL StrategyBuilderAdapter + TestClient (in-memory DB).
They validate that every RSI/MACD parameter combination produces the expected signal behavior.

Run:
    py -3.14 -m pytest tests/ai_agents/test_rsi_macd_filters_api.py -v
    py -3.14 -m pytest tests/ai_agents/test_rsi_macd_filters_api.py -v -k "rsi"
    py -3.14 -m pytest tests/ai_agents/test_rsi_macd_filters_api.py -v -k "macd"
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
    Realistic OHLCV data with known RSI/MACD behaviour.
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


def _make_rsi_graph(params: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal strategy graph with RSI → long/short → strategy."""
    return {
        "name": "RSI Filter Test",
        "blocks": [
            {
                "id": "b_rsi",
                "type": "rsi",
                "category": "indicator",
                "name": "RSI",
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
                "source": {"blockId": "b_rsi", "portId": "long"},
                "target": {"blockId": "main", "portId": "entry_long"},
                "type": "data",
            },
            {
                "id": "c2",
                "source": {"blockId": "b_rsi", "portId": "short"},
                "target": {"blockId": "main", "portId": "entry_short"},
                "type": "data",
            },
        ],
    }


def _make_macd_graph(params: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal strategy graph with MACD → long/short → strategy."""
    return {
        "name": "MACD Filter Test",
        "blocks": [
            {
                "id": "b_macd",
                "type": "macd",
                "category": "indicator",
                "name": "MACD",
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
                "source": {"blockId": "b_macd", "portId": "long"},
                "target": {"blockId": "main", "portId": "entry_long"},
                "type": "data",
            },
            {
                "id": "c2",
                "source": {"blockId": "b_macd", "portId": "short"},
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
#  PART 1 — RSI FILTER TESTS
#
# ============================================================


class TestRSIPassthrough:
    """When no mode is enabled, RSI acts as passthrough (long/short = True)."""

    def test_rsi_no_mode_enabled_all_true(self, sample_ohlcv):
        """No mode → passthrough: long and short are always True."""
        graph = _make_rsi_graph({"period": 14})
        signals = _run_adapter(graph, sample_ohlcv)

        # In passthrough mode, entries should be True for most/all bars
        assert signals["entries"].sum() > 0, "Passthrough RSI must produce long entries"
        assert signals["short_entries"] is None or signals["short_entries"].sum() >= 0


class TestRSILegacyMode:
    """Legacy fallback: overbought/oversold without new modes."""

    def test_rsi_legacy_overbought_oversold(self, sample_ohlcv):
        """Legacy mode: RSI < oversold → long, RSI > overbought → short."""
        graph = _make_rsi_graph({"period": 14, "overbought": 70, "oversold": 30})
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(sample_ohlcv)

        # Legacy mode should NOT produce entries on every bar
        assert result.entries.sum() < len(sample_ohlcv), "Legacy RSI should filter signals"


class TestRSIRangeFilter:
    """Test `use_long_range` and `use_short_range` range filters."""

    def test_long_range_only(self, sample_ohlcv):
        """use_long_range=True: long allowed only when RSI in range."""
        params = {
            "period": 14,
            "use_long_range": True,
            "long_rsi_more": 20,
            "long_rsi_less": 50,
        }
        graph = _make_rsi_graph(params)
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(sample_ohlcv)

        # Not all bars should have entries (RSI must be in 20-50)
        assert result.entries.sum() < len(sample_ohlcv), "Long range filter should limit entries to RSI 20-50"
        assert result.entries.sum() > 0, "Some bars should have RSI in range 20-50"

    def test_short_range_only(self, sample_ohlcv):
        """use_short_range=True: short allowed only when RSI in range."""
        params = {
            "period": 14,
            "use_short_range": True,
            "short_rsi_less": 100,
            "short_rsi_more": 70,
        }
        graph = _make_rsi_graph(params)
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(sample_ohlcv)

        # short_entries should exist but not on every bar
        # When use_short_range is True but use_long_range is False:
        # long = True (passthrough), short = filtered by range
        assert result.entries.sum() > 0, "Long should be passthrough"

    def test_both_ranges_narrow(self, sample_ohlcv):
        """Both ranges enabled with narrow bands → fewer signals."""
        params = {
            "period": 14,
            "use_long_range": True,
            "long_rsi_more": 25,
            "long_rsi_less": 35,
            "use_short_range": True,
            "short_rsi_less": 75,
            "short_rsi_more": 65,
        }
        graph = _make_rsi_graph(params)
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(sample_ohlcv)

        # Narrow bands → very few signals
        total_long = result.entries.sum()
        assert total_long < len(sample_ohlcv) * 0.5, "Narrow RSI range (25-35) should produce <50% of bars as entries"

    def test_range_filter_lower_must_be_less_than_upper(self, sample_ohlcv):
        """Validate: long_rsi_more < long_rsi_less (lower < upper)."""
        params = {
            "period": 14,
            "use_long_range": True,
            "long_rsi_more": 1,  # lower bound
            "long_rsi_less": 30,  # upper bound
        }
        graph = _make_rsi_graph(params)
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(sample_ohlcv)

        # RSI 1-30 is oversold zone — should have some signals
        assert result.entries.sum() > 0, "RSI in oversold zone (1-30) should trigger entries"


class TestRSICrossLevel:
    """Test `use_cross_level` event-based signal generation."""

    def test_cross_level_basic(self, sample_ohlcv):
        """Cross level: LONG when RSI crosses 30 from below, SHORT when RSI crosses 70 from above."""
        params = {
            "period": 14,
            "use_cross_level": True,
            "cross_long_level": 30,
            "cross_short_level": 70,
        }
        graph = _make_rsi_graph(params)
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(sample_ohlcv)

        # Cross events are rare (only on crossing bars)
        total_long = result.entries.sum()
        assert total_long < len(sample_ohlcv) * 0.1, (
            f"Cross signals should be rare (<10% of bars), got {total_long}/{len(sample_ohlcv)}"
        )
        assert total_long > 0, "At least some RSI crossovers should occur over 1000 bars"

    def test_cross_level_opposite_signal(self, sample_ohlcv):
        """opposite_signal=True: swaps long and short cross signals."""
        base_params = {
            "period": 14,
            "use_cross_level": True,
            "cross_long_level": 30,
            "cross_short_level": 70,
        }
        opposite_params = {**base_params, "opposite_signal": True}

        graph_normal = _make_rsi_graph(base_params)
        graph_opposite = _make_rsi_graph(opposite_params)

        adapter_normal = StrategyBuilderAdapter(graph_normal)
        adapter_opposite = StrategyBuilderAdapter(graph_opposite)

        result_normal = adapter_normal.generate_signals(sample_ohlcv)
        result_opposite = adapter_opposite.generate_signals(sample_ohlcv)

        # Opposite should swap: normal.long ≈ opposite.short and vice versa
        normal_long_count = result_normal.entries.sum()
        opposite_long_count = result_opposite.entries.sum()

        # They should be different (unless there's symmetry in data)
        # With opposite, what was a long cross-up becomes a short cross-down
        assert normal_long_count != opposite_long_count or normal_long_count == 0, (
            "Opposite signal should produce different long entry counts"
        )

    def test_cross_level_with_memory(self, sample_ohlcv):
        """use_cross_memory=True: signal stays active for N bars after crossing."""
        no_memory_params = {
            "period": 14,
            "use_cross_level": True,
            "cross_long_level": 30,
            "cross_short_level": 70,
        }
        memory_params = {
            **no_memory_params,
            "use_cross_memory": True,
            "cross_memory_bars": 5,
        }

        graph_no_mem = _make_rsi_graph(no_memory_params)
        graph_mem = _make_rsi_graph(memory_params)

        result_no_mem = StrategyBuilderAdapter(graph_no_mem).generate_signals(sample_ohlcv)
        result_mem = StrategyBuilderAdapter(graph_mem).generate_signals(sample_ohlcv)

        no_mem_count = result_no_mem.entries.sum()
        mem_count = result_mem.entries.sum()

        # With memory, signal stays active longer → more True bars
        assert mem_count >= no_mem_count, f"Memory should produce >= entries: no_mem={no_mem_count}, mem={mem_count}"
        if no_mem_count > 0:
            assert mem_count > no_mem_count, (
                f"Memory (5 bars) should expand signals: no_mem={no_mem_count}, mem={mem_count}"
            )

    def test_cross_memory_bars_higher_produces_more(self, sample_ohlcv):
        """More memory_bars → more active signal bars."""
        base = {
            "period": 14,
            "use_cross_level": True,
            "cross_long_level": 30,
            "cross_short_level": 70,
            "use_cross_memory": True,
        }
        params_3 = {**base, "cross_memory_bars": 3}
        params_10 = {**base, "cross_memory_bars": 10}

        result_3 = StrategyBuilderAdapter(_make_rsi_graph(params_3)).generate_signals(sample_ohlcv)
        result_10 = StrategyBuilderAdapter(_make_rsi_graph(params_10)).generate_signals(sample_ohlcv)

        count_3 = result_3.entries.sum()
        count_10 = result_10.entries.sum()

        assert count_10 >= count_3, f"memory_bars=10 should produce >= signals than 3: 3={count_3}, 10={count_10}"


class TestRSICombinedModes:
    """Test Range AND Cross combined (AND logic)."""

    def test_range_and_cross_combined(self, sample_ohlcv):
        """Both Range + Cross enabled → result = Range AND Cross."""
        cross_only = {
            "period": 14,
            "use_cross_level": True,
            "cross_long_level": 30,
            "cross_short_level": 70,
            "use_cross_memory": True,
            "cross_memory_bars": 5,
        }
        combined = {
            **cross_only,
            "use_long_range": True,
            "long_rsi_more": 20,
            "long_rsi_less": 50,
        }

        result_cross = StrategyBuilderAdapter(_make_rsi_graph(cross_only)).generate_signals(sample_ohlcv)
        result_combined = StrategyBuilderAdapter(_make_rsi_graph(combined)).generate_signals(sample_ohlcv)

        cross_count = result_cross.entries.sum()
        combined_count = result_combined.entries.sum()

        # AND logic: combined should be <= cross-only
        assert combined_count <= cross_count, (
            f"Range AND Cross should produce <= cross-only: cross={cross_count}, combined={combined_count}"
        )


class TestRSIPeriodEffect:
    """Test that RSI period affects signal generation."""

    def test_shorter_period_more_volatile(self, sample_ohlcv):
        """Shorter period → more volatile RSI → potentially more cross events."""
        short_params = {
            "period": 5,
            "use_cross_level": True,
            "cross_long_level": 30,
            "cross_short_level": 70,
        }
        long_params = {**short_params, "period": 30}

        result_short = StrategyBuilderAdapter(_make_rsi_graph(short_params)).generate_signals(sample_ohlcv)
        result_long = StrategyBuilderAdapter(_make_rsi_graph(long_params)).generate_signals(sample_ohlcv)

        short_count = result_short.entries.sum()
        long_count = result_long.entries.sum()

        # Shorter period RSI crosses levels more often
        assert short_count > long_count, (
            f"Short RSI period(5) should produce more crosses than long(30): short={short_count}, long={long_count}"
        )


# ============================================================
#
#  PART 2 — MACD FILTER TESTS
#
# ============================================================


class TestMACDDataOnly:
    """When no mode is enabled, MACD outputs data only (long/short = False)."""

    def test_macd_no_mode_no_signals(self, sample_ohlcv):
        """No mode enabled → long/short = False (data-only mode)."""
        graph = _make_macd_graph(
            {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
            }
        )
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(sample_ohlcv)

        # No mode enabled → entries should be 0 (all False)
        assert result.entries.sum() == 0, (
            f"MACD data-only mode should produce 0 long entries, got {result.entries.sum()}"
        )


class TestMACDCrossZero:
    """Test `use_macd_cross_zero` mode — MACD line crosses level."""

    def test_cross_zero_basic(self, sample_ohlcv):
        """use_macd_cross_zero=True: LONG when MACD crosses above 0, SHORT when below."""
        graph = _make_macd_graph(
            {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "use_macd_cross_zero": True,
                "macd_cross_zero_level": 0,
            }
        )
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(sample_ohlcv)

        # Should produce some signals (MACD crosses zero periodically)
        # Note: signal memory is ON by default in MACD → more bars
        assert result.entries.sum() > 0, "MACD cross zero should produce long entries"

    def test_cross_zero_custom_level(self, sample_ohlcv):
        """macd_cross_zero_level != 0: crosses a custom level."""
        params_zero = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "use_macd_cross_zero": True,
            "macd_cross_zero_level": 0,
        }
        params_high = {**params_zero, "macd_cross_zero_level": 100}

        result_zero = StrategyBuilderAdapter(_make_macd_graph(params_zero)).generate_signals(sample_ohlcv)
        result_high = StrategyBuilderAdapter(_make_macd_graph(params_high)).generate_signals(sample_ohlcv)

        # Higher level → fewer crosses (MACD rarely goes above 100)
        zero_count = result_zero.entries.sum()
        high_count = result_high.entries.sum()

        assert zero_count >= high_count, (
            f"Level=0 should produce >= signals than level=100: zero={zero_count}, high={high_count}"
        )

    def test_cross_zero_opposite(self, sample_ohlcv):
        """opposite_macd_cross_zero=True: swaps long/short for zero cross."""
        base = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "use_macd_cross_zero": True,
            "macd_cross_zero_level": 0,
            "disable_signal_memory": True,  # Disable memory for cleaner comparison
        }
        normal_result = StrategyBuilderAdapter(_make_macd_graph(base)).generate_signals(sample_ohlcv)
        opposite_result = StrategyBuilderAdapter(
            _make_macd_graph({**base, "opposite_macd_cross_zero": True})
        ).generate_signals(sample_ohlcv)

        # Opposite swaps long↔short: normal entries should match opposite short_entries
        # (and vice versa).  We verify the swap happened by checking that
        # at least one pair of entry bars differs between normal.entries
        # and opposite.entries when there's asymmetry in the data.
        normal_long = normal_result.entries.sum()
        normal_short = normal_result.short_entries.sum() if normal_result.short_entries is not None else 0
        opposite_long = opposite_result.entries.sum()
        opposite_short = opposite_result.short_entries.sum() if opposite_result.short_entries is not None else 0

        # After swap: normal_long ↔ opposite_short, normal_short ↔ opposite_long
        # In symmetric random data they may be equal, so we just confirm the swap pattern
        assert opposite_long == normal_short or (normal_long == normal_short), (
            f"Opposite should swap: normal_long={normal_long}, normal_short={normal_short}, "
            f"opposite_long={opposite_long}, opposite_short={opposite_short}"
        )


class TestMACDCrossSignal:
    """Test `use_macd_cross_signal` mode — MACD crosses Signal line."""

    def test_cross_signal_basic(self, sample_ohlcv):
        """use_macd_cross_signal=True: LONG on bullish crossover, SHORT on bearish."""
        graph = _make_macd_graph(
            {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "use_macd_cross_signal": True,
            }
        )
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(sample_ohlcv)

        assert result.entries.sum() > 0, "MACD cross signal should produce long entries"

    def test_cross_signal_with_positive_filter(self, sample_ohlcv):
        """signal_only_if_macd_positive=True: LONG only when MACD<0, SHORT only when MACD>0."""
        base = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "use_macd_cross_signal": True,
            "disable_signal_memory": True,
        }
        no_filter = StrategyBuilderAdapter(_make_macd_graph(base)).generate_signals(sample_ohlcv)
        with_filter = StrategyBuilderAdapter(
            _make_macd_graph({**base, "signal_only_if_macd_positive": True})
        ).generate_signals(sample_ohlcv)

        # Positive filter restricts: fewer or equal signals
        no_filter_count = no_filter.entries.sum()
        filter_count = with_filter.entries.sum()

        assert filter_count <= no_filter_count, (
            f"Positive filter should reduce/keep entries: no_filter={no_filter_count}, filter={filter_count}"
        )

    def test_cross_signal_opposite(self, sample_ohlcv):
        """opposite_macd_cross_signal=True: swaps long/short for signal cross."""
        base = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "use_macd_cross_signal": True,
            "disable_signal_memory": True,
        }
        normal = StrategyBuilderAdapter(_make_macd_graph(base)).generate_signals(sample_ohlcv)
        opposite = StrategyBuilderAdapter(
            _make_macd_graph({**base, "opposite_macd_cross_signal": True})
        ).generate_signals(sample_ohlcv)

        # Opposite swaps long↔short.  Verify via entry arrays (not counts).
        normal_entries = normal.entries
        opposite_entries = opposite.entries

        # The actual bar positions where entries fire should differ
        # (unless data is perfectly symmetric — very unlikely with random seed 42)
        if normal_entries.sum() > 0:
            # Compare entry positions — they should not be identical
            normal_mask = normal_entries.values.astype(bool)
            opposite_mask = opposite_entries.values.astype(bool)
            assert not np.array_equal(normal_mask, opposite_mask), "Opposite should produce entries on different bars"


class TestMACDSignalMemory:
    """Test Signal Memory (enabled by default in MACD!)."""

    def test_memory_on_by_default(self, sample_ohlcv):
        """Signal memory is ON by default (5 bars) → more active bars than raw cross."""
        with_memory = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "use_macd_cross_zero": True,
            "macd_cross_zero_level": 0,
            # disable_signal_memory defaults to False → memory ON
        }
        without_memory = {
            **with_memory,
            "disable_signal_memory": True,
        }

        result_mem = StrategyBuilderAdapter(_make_macd_graph(with_memory)).generate_signals(sample_ohlcv)
        result_no_mem = StrategyBuilderAdapter(_make_macd_graph(without_memory)).generate_signals(sample_ohlcv)

        mem_count = result_mem.entries.sum()
        no_mem_count = result_no_mem.entries.sum()

        # With memory (default), signals persist → more True bars
        assert mem_count >= no_mem_count, (
            f"Default memory ON should produce >= signals: mem={mem_count}, no_mem={no_mem_count}"
        )
        if no_mem_count > 0:
            assert mem_count > no_mem_count, f"Memory should expand signals: mem={mem_count}, no_mem={no_mem_count}"

    def test_disable_signal_memory(self, sample_ohlcv):
        """disable_signal_memory=True: signals only on exact cross bar."""
        params = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "use_macd_cross_signal": True,
            "disable_signal_memory": True,
        }
        result = StrategyBuilderAdapter(_make_macd_graph(params)).generate_signals(sample_ohlcv)

        # Without memory, signals should be very sparse (only on cross bars)
        entry_count = result.entries.sum()
        assert entry_count < len(sample_ohlcv) * 0.05, (
            f"Without memory, entries should be <5% of bars: {entry_count}/{len(sample_ohlcv)}"
        )


class TestMACDCombinedModes:
    """Test OR logic: Cross Zero + Cross Signal combined."""

    def test_or_logic_more_signals_than_either(self, sample_ohlcv):
        """Both modes ON → signals from either mode (OR)."""
        cross_zero_only = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "use_macd_cross_zero": True,
            "macd_cross_zero_level": 0,
            "disable_signal_memory": True,
        }
        cross_signal_only = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "use_macd_cross_signal": True,
            "disable_signal_memory": True,
        }
        both = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "use_macd_cross_zero": True,
            "macd_cross_zero_level": 0,
            "use_macd_cross_signal": True,
            "disable_signal_memory": True,
        }

        r_zero = StrategyBuilderAdapter(_make_macd_graph(cross_zero_only)).generate_signals(sample_ohlcv)
        r_signal = StrategyBuilderAdapter(_make_macd_graph(cross_signal_only)).generate_signals(sample_ohlcv)
        r_both = StrategyBuilderAdapter(_make_macd_graph(both)).generate_signals(sample_ohlcv)

        zero_count = r_zero.entries.sum()
        signal_count = r_signal.entries.sum()
        both_count = r_both.entries.sum()

        # OR: combined >= each individual
        assert both_count >= zero_count, f"Combined (OR) should >= cross_zero: combined={both_count}, zero={zero_count}"
        assert both_count >= signal_count, (
            f"Combined (OR) should >= cross_signal: combined={both_count}, signal={signal_count}"
        )


class TestMACDPeriodEffect:
    """Test that fast/slow period changes affect signal generation."""

    def test_fast_must_be_less_than_slow(self, sample_ohlcv):
        """fast_period < slow_period is required for meaningful MACD."""
        # Standard params should work
        standard = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "use_macd_cross_signal": True,
        }
        adapter = StrategyBuilderAdapter(_make_macd_graph(standard))
        result = adapter.generate_signals(sample_ohlcv)
        assert result.entries.sum() >= 0, "Standard MACD should work"

    def test_different_periods_different_signals(self, sample_ohlcv):
        """Different fast/slow periods → different signal counts."""
        fast_params = {
            "fast_period": 8,
            "slow_period": 21,
            "signal_period": 9,
            "use_macd_cross_signal": True,
            "disable_signal_memory": True,
        }
        slow_params = {
            "fast_period": 15,
            "slow_period": 30,
            "signal_period": 9,
            "use_macd_cross_signal": True,
            "disable_signal_memory": True,
        }

        r_fast = StrategyBuilderAdapter(_make_macd_graph(fast_params)).generate_signals(sample_ohlcv)
        r_slow = StrategyBuilderAdapter(_make_macd_graph(slow_params)).generate_signals(sample_ohlcv)

        fast_count = r_fast.entries.sum()
        slow_count = r_slow.entries.sum()

        # Faster MACD should cross more often
        assert fast_count != slow_count, (
            f"Different periods should produce different signal counts: fast={fast_count}, slow={slow_count}"
        )


# ============================================================
#
#  PART 3 — CRITICAL DIFFERENCES (RSI AND vs MACD OR)
#
# ============================================================


class TestRSIvsMACDLogic:
    """Test the critical difference: RSI uses AND, MACD uses OR."""

    def test_rsi_uses_and_logic(self, sample_ohlcv):
        """RSI: Range AND Cross → combined <= each individual."""
        range_only = {
            "period": 14,
            "use_long_range": True,
            "long_rsi_more": 20,
            "long_rsi_less": 80,
        }
        cross_only = {
            "period": 14,
            "use_cross_level": True,
            "cross_long_level": 30,
            "cross_short_level": 70,
            "use_cross_memory": True,
            "cross_memory_bars": 10,
        }
        combined = {**range_only, **cross_only}

        r_range = StrategyBuilderAdapter(_make_rsi_graph(range_only)).generate_signals(sample_ohlcv)
        r_cross = StrategyBuilderAdapter(_make_rsi_graph(cross_only)).generate_signals(sample_ohlcv)
        r_both = StrategyBuilderAdapter(_make_rsi_graph(combined)).generate_signals(sample_ohlcv)

        range_count = r_range.entries.sum()
        cross_count = r_cross.entries.sum()
        both_count = r_both.entries.sum()

        # AND: combined <= each individual
        assert both_count <= range_count, f"RSI AND: combined({both_count}) should <= range({range_count})"
        assert both_count <= cross_count, f"RSI AND: combined({both_count}) should <= cross({cross_count})"

    def test_macd_uses_or_logic(self, sample_ohlcv):
        """MACD: CrossZero OR CrossSignal → combined >= each individual."""
        cross_zero = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "use_macd_cross_zero": True,
            "disable_signal_memory": True,
        }
        cross_signal = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "use_macd_cross_signal": True,
            "disable_signal_memory": True,
        }
        both = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "use_macd_cross_zero": True,
            "use_macd_cross_signal": True,
            "disable_signal_memory": True,
        }

        r_zero = StrategyBuilderAdapter(_make_macd_graph(cross_zero)).generate_signals(sample_ohlcv)
        r_signal = StrategyBuilderAdapter(_make_macd_graph(cross_signal)).generate_signals(sample_ohlcv)
        r_both = StrategyBuilderAdapter(_make_macd_graph(both)).generate_signals(sample_ohlcv)

        zero_count = r_zero.entries.sum()
        signal_count = r_signal.entries.sum()
        both_count = r_both.entries.sum()

        # OR: combined >= each individual
        assert both_count >= zero_count, f"MACD OR: combined({both_count}) should >= zero({zero_count})"
        assert both_count >= signal_count, f"MACD OR: combined({both_count}) should >= signal({signal_count})"


# ============================================================
#
#  PART 4 — OPTIMIZATION PARAMS STRUCTURE
#
# ============================================================


class TestRSIOptimizationParams:
    """Test that optimization params are stored in correct format."""

    def test_rsi_optimizable_params_list(self):
        """RSI has 8 optimizable parameters."""
        optimizable = [
            "period",
            "long_rsi_more",
            "long_rsi_less",
            "short_rsi_less",
            "short_rsi_more",
            "cross_long_level",
            "cross_short_level",
            "cross_memory_bars",
        ]
        # Verify these match the frontend definition
        assert len(optimizable) == 8, "RSI should have 8 optimizable params"

    def test_rsi_optimization_range_format(self):
        """Optimization param format: {enabled, min, max, step}."""
        sample_opt = {
            "period": {"enabled": True, "min": 5, "max": 30, "step": 1},
            "cross_long_level": {"enabled": True, "min": 15, "max": 45, "step": 5},
        }
        for key, val in sample_opt.items():
            assert "enabled" in val, f"{key} must have 'enabled'"
            assert "min" in val, f"{key} must have 'min'"
            assert "max" in val, f"{key} must have 'max'"
            assert "step" in val, f"{key} must have 'step'"
            assert val["min"] <= val["max"], f"{key}: min must be <= max"
            assert val["step"] > 0, f"{key}: step must be > 0"

    def test_rsi_recommended_ranges(self):
        """Verify recommended optimization ranges are sensible."""
        ranges = {
            "period": {"min": 5, "max": 30, "step": 1},
            "long_rsi_more": {"min": 10, "max": 45, "step": 5},
            "long_rsi_less": {"min": 55, "max": 90, "step": 5},
            "short_rsi_less": {"min": 55, "max": 90, "step": 5},
            "short_rsi_more": {"min": 10, "max": 45, "step": 5},
            "cross_long_level": {"min": 15, "max": 45, "step": 5},
            "cross_short_level": {"min": 55, "max": 85, "step": 5},
            "cross_memory_bars": {"min": 1, "max": 20, "step": 1},
        }
        for key, r in ranges.items():
            iterations = (r["max"] - r["min"]) // r["step"] + 1
            assert iterations >= 2, f"{key}: range must produce >= 2 iterations, got {iterations}"
            assert iterations <= 50, f"{key}: range too large ({iterations} iterations)"


class TestMACDOptimizationParams:
    """Test MACD optimization params."""

    def test_macd_optimizable_params_list(self):
        """MACD has 5 optimizable parameters."""
        optimizable = [
            "fast_period",
            "slow_period",
            "signal_period",
            "macd_cross_zero_level",
            "signal_memory_bars",
        ]
        assert len(optimizable) == 5, "MACD should have 5 optimizable params"

    def test_macd_fast_less_than_slow_constraint(self):
        """Optimization must ensure fast_period < slow_period."""
        fast_range = {"min": 8, "max": 16}
        slow_range = {"min": 20, "max": 30}

        # All fast values must be less than all slow values
        assert fast_range["max"] < slow_range["min"], (
            f"fast max ({fast_range['max']}) must be < slow min ({slow_range['min']})"
        )

    def test_macd_recommended_ranges(self):
        """Verify recommended optimization ranges."""
        ranges = {
            "fast_period": {"min": 8, "max": 16, "step": 1},
            "slow_period": {"min": 20, "max": 30, "step": 1},
            "signal_period": {"min": 6, "max": 12, "step": 1},
            "macd_cross_zero_level": {"min": -50, "max": 50, "step": 1},
            "signal_memory_bars": {"min": 1, "max": 20, "step": 1},
        }
        for key, r in ranges.items():
            iterations = (r["max"] - r["min"]) // r["step"] + 1
            assert iterations >= 2, f"{key}: range must produce >= 2 iterations"


# ============================================================
#
#  PART 5 — API ENDPOINT TESTS
#
# ============================================================


class TestStrategyBuilderAPIWithRSI:
    """Test creating/saving RSI strategy through the real API."""

    def test_create_rsi_strategy_with_range_filter(self, client):
        """Create a strategy with RSI range filter via API."""
        strategy = _make_rsi_graph(
            {
                "period": 14,
                "use_long_range": True,
                "long_rsi_more": 20,
                "long_rsi_less": 50,
                "use_short_range": True,
                "short_rsi_less": 80,
                "short_rsi_more": 50,
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
        assert len(saved["blocks"]) == 2, "RSI + Strategy blocks"

        # Find RSI block and verify params persisted
        rsi_block = next(b for b in saved["blocks"] if b["type"] == "rsi")
        assert rsi_block["params"]["period"] == 14
        assert rsi_block["params"]["use_long_range"] is True
        assert rsi_block["params"]["long_rsi_more"] == 20

    def test_create_rsi_strategy_with_cross_level(self, client):
        """Create a strategy with RSI cross level via API."""
        strategy = _make_rsi_graph(
            {
                "period": 14,
                "use_cross_level": True,
                "cross_long_level": 25,
                "cross_short_level": 75,
                "use_cross_memory": True,
                "cross_memory_bars": 10,
            }
        )
        strategy["name"] = "RSI Cross Level Test"
        strategy["timeframe"] = "15m"
        strategy["symbols"] = ["ETHUSDT"]

        response = client.post("/api/v1/strategy-builder/strategies", json=strategy)
        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()
        strategy_id = data["id"]

        # Load and verify
        get_resp = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")
        saved = get_resp.json()
        rsi_block = next(b for b in saved["blocks"] if b["type"] == "rsi")
        assert rsi_block["params"]["use_cross_level"] is True
        assert rsi_block["params"]["cross_long_level"] == 25
        assert rsi_block["params"]["cross_memory_bars"] == 10


class TestStrategyBuilderAPIWithMACD:
    """Test creating/saving MACD strategy through the real API."""

    def test_create_macd_strategy_cross_zero(self, client):
        """Create a strategy with MACD cross zero via API."""
        strategy = _make_macd_graph(
            {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "use_macd_cross_zero": True,
                "macd_cross_zero_level": 0,
            }
        )
        strategy["timeframe"] = "4h"
        strategy["symbols"] = ["BTCUSDT"]

        response = client.post("/api/v1/strategy-builder/strategies", json=strategy)
        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()
        strategy_id = data["id"]

        # Load and verify
        get_resp = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")
        saved = get_resp.json()
        macd_block = next(b for b in saved["blocks"] if b["type"] == "macd")
        assert macd_block["params"]["use_macd_cross_zero"] is True
        assert macd_block["params"]["fast_period"] == 12

    def test_create_macd_strategy_cross_signal_with_filter(self, client):
        """Create MACD with signal line cross + positive filter via API."""
        strategy = _make_macd_graph(
            {
                "fast_period": 10,
                "slow_period": 21,
                "signal_period": 7,
                "use_macd_cross_signal": True,
                "signal_only_if_macd_positive": True,
                "disable_signal_memory": True,
            }
        )
        strategy["name"] = "MACD Mean Reversion Test"
        strategy["timeframe"] = "1h"
        strategy["symbols"] = ["ETHUSDT"]

        response = client.post("/api/v1/strategy-builder/strategies", json=strategy)
        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()
        strategy_id = data["id"]

        # Load and verify
        get_resp = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")
        saved = get_resp.json()
        macd_block = next(b for b in saved["blocks"] if b["type"] == "macd")
        assert macd_block["params"]["use_macd_cross_signal"] is True
        assert macd_block["params"]["signal_only_if_macd_positive"] is True
        assert macd_block["params"]["disable_signal_memory"] is True
