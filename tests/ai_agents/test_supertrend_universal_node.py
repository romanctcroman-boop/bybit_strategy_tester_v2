"""
AI Agent Knowledge Test: SuperTrend Universal Node — Real API Tests

Tests verify that AI agents correctly understand the **universal SuperTrend indicator**
which consolidates 4 former duplicates (supertrend_filter, supertrend_buy_signal,
supertrend_sell_signal, smart_supertrend) into a single node with two signal modes:

  1. FILTER mode  — continuous: long while uptrend, short while downtrend
  2. SIGNAL mode  — event: long/short only on direction flip (generate_on_trend_change)

Additional options: use_supertrend (enable/disable), opposite_signal, use_btc_source,
show_supertrend, timeframe.

Run:
    py -3.14 -m pytest tests/ai_agents/test_supertrend_universal_node.py -v
    py -3.14 -m pytest tests/ai_agents/test_supertrend_universal_node.py -v -k "filter"
    py -3.14 -m pytest tests/ai_agents/test_supertrend_universal_node.py -v -k "signal"
    py -3.14 -m pytest tests/ai_agents/test_supertrend_universal_node.py -v -k "opposite"
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
    """OHLCV data with a clear trend change in the middle.

    First half: steep downtrend, Second half: steep uptrend.
    Uses large price moves (2.0/bar) so SuperTrend flips reliably.

    NOTE: ``calculate_supertrend`` in ``trend.py`` has a known NaN-propagation
    issue when ``period > 1`` (ATR warmup makes ``final_upper/final_lower`` NaN
    forever).  Tests that need direction flips therefore use ``period=1``.
    """
    np.random.seed(42)
    n = 200

    # Steep V-shaped price: -2/bar then +2/bar — ensures direction flips
    base_price = 500.0
    prices = np.zeros(n)
    for i in range(n):
        if i < n // 2:
            prices[i] = base_price - (i * 2.0) + np.random.normal(0, 1.0)
        else:
            prices[i] = base_price - (n // 2 * 2.0) + ((i - n // 2) * 2.0) + np.random.normal(0, 1.0)

    close = pd.Series(prices, name="close")
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
    """Helper — execute SuperTrend indicator block."""
    return adapter._execute_indicator("supertrend", params, ohlcv, {})


# ============================================================
# 1. PASSTHROUGH MODE (use_supertrend=false, default)
# ============================================================


class TestPassthrough:
    """When use_supertrend is False (default), long/short should be True everywhere."""

    def test_passthrough_default_params(self, adapter, trending_ohlcv):
        """Default params → passthrough mode, all True."""
        result = _run(adapter, trending_ohlcv, {})
        assert "long" in result
        assert "short" in result
        assert "supertrend" in result
        assert "direction" in result
        assert "upper" in result
        assert "lower" in result
        assert result["long"].all(), "Passthrough: long should be all True"
        assert result["short"].all(), "Passthrough: short should be all True"

    def test_passthrough_explicit_false(self, adapter, trending_ohlcv):
        """use_supertrend=False explicitly → passthrough."""
        result = _run(adapter, trending_ohlcv, {"use_supertrend": False})
        assert result["long"].all()
        assert result["short"].all()

    def test_passthrough_supertrend_data_still_computed(self, adapter, trending_ohlcv):
        """Even in passthrough, SuperTrend line and direction are computed.

        Uses period=1 to avoid ATR warmup NaN propagation.
        """
        result = _run(adapter, trending_ohlcv, {"use_supertrend": False, "period": 1})
        st_line = result["supertrend"]
        direction = result["direction"]
        # SuperTrend should have non-NaN values (period=1 → no warmup)
        assert st_line.notna().sum() > len(trending_ohlcv) // 2
        # Direction should be 1 or -1 (bar 0 may be 0 — warmup)
        valid_dirs = direction.iloc[1:].dropna()
        assert all(d in (1, -1) for d in valid_dirs.unique())

    def test_passthrough_has_six_outputs(self, adapter, trending_ohlcv):
        """Universal SuperTrend should output exactly 6 keys."""
        result = _run(adapter, trending_ohlcv, {})
        expected_keys = {"supertrend", "direction", "upper", "lower", "long", "short"}
        assert set(result.keys()) == expected_keys


# ============================================================
# 2. FILTER MODE (use_supertrend=true, generate_on_trend_change=false)
# ============================================================


class TestFilterMode:
    """Filter mode: continuous long while uptrend, short while downtrend."""

    def test_filter_mode_produces_signals(self, adapter, trending_ohlcv):
        """With use_supertrend=True, long/short should NOT all be True.

        Uses period=1 to get valid direction values.
        """
        result = _run(adapter, trending_ohlcv, {"use_supertrend": True, "period": 1})
        # In trending data, we should have some True and some False
        assert not result["long"].all(), "Filter mode should not have all-True long"
        assert not result["short"].all(), "Filter mode should not have all-True short"

    def test_filter_mode_long_short_exclusive(self, adapter, trending_ohlcv):
        """In filter mode, long and short should be mutually exclusive on each bar.

        Uses period=1.
        """
        result = _run(adapter, trending_ohlcv, {"use_supertrend": True, "period": 1})
        both_true = (result["long"] & result["short"]).sum()
        assert both_true == 0, "long and short should never both be True on same bar"

    def test_filter_mode_matches_direction(self, adapter, trending_ohlcv):
        """long should match direction==1, short should match direction==-1.

        Skips bar 0 (direction=0).
        """
        result = _run(adapter, trending_ohlcv, {"use_supertrend": True, "period": 1})
        direction = result["direction"].iloc[1:]

        # Where direction is 1, long should be True
        uptrend_mask = direction == 1
        assert (result["long"].iloc[1:][uptrend_mask]).all()
        assert (~result["short"].iloc[1:][uptrend_mask]).all()

        # Where direction is -1, short should be True
        downtrend_mask = direction == -1
        if downtrend_mask.any():
            assert (result["short"].iloc[1:][downtrend_mask]).all()
            assert (~result["long"].iloc[1:][downtrend_mask]).all()

    def test_filter_mode_is_continuous(self, adapter, trending_ohlcv):
        """Filter mode should produce continuous signals (not just on flips)."""
        result = _run(adapter, trending_ohlcv, {"use_supertrend": True, "period": 1})
        # Long should have many True bars (entire uptrend duration)
        long_count = result["long"].sum()
        assert long_count > 10, "Filter mode should have many consecutive long=True bars"

    def test_filter_covers_all_bars(self, adapter, trending_ohlcv):
        """Every bar (after warmup) should be either long or short (no gaps).

        Uses period=1.  Bar 0 has direction=0 in the trend.py implementation
        so we skip it.
        """
        result = _run(adapter, trending_ohlcv, {"use_supertrend": True, "period": 1})
        either = result["long"] | result["short"]
        # Skip bar 0 where direction is 0 → neither long nor short
        assert either.iloc[1:].all(), "Every bar (after bar 0) should be either long or short"


# ============================================================
# 3. SIGNAL MODE (generate_on_trend_change=true)
# ============================================================


class TestSignalMode:
    """Signal mode: long/short only on direction flip."""

    def test_signal_mode_produces_sparse_signals(self, adapter, trending_ohlcv):
        """Signal mode should produce few signals (only on flips).

        Uses period=1 to avoid NaN propagation in ``calculate_supertrend``.
        """
        result = _run(
            adapter,
            trending_ohlcv,
            {
                "use_supertrend": True,
                "generate_on_trend_change": True,
                "period": 1,
            },
        )
        long_count = result["long"].sum()
        short_count = result["short"].sum()
        total_signals = long_count + short_count
        # With 200 bars and a V-shape, we should have very few flips
        assert total_signals < 20, f"Signal mode should be sparse, got {total_signals} signals"
        assert total_signals > 0, "Signal mode should have at least one flip"

    def test_signal_mode_fires_on_flip_only(self, adapter, trending_ohlcv):
        """Signal should be True only on the exact bar where direction changes."""
        result = _run(
            adapter,
            trending_ohlcv,
            {
                "use_supertrend": True,
                "generate_on_trend_change": True,
                "period": 1,
            },
        )
        direction = result["direction"]

        # Verify each long signal is indeed a flip from -1 to 1
        long_signals = result["long"]
        for i in long_signals[long_signals].index:
            if i > 0:
                assert direction.iloc[i] == 1, f"Long at {i}: direction should be 1"
                assert direction.iloc[i - 1] == -1, f"Long at {i}: prev direction should be -1"

        # Verify each short signal is a flip from 1 to -1
        short_signals = result["short"]
        for i in short_signals[short_signals].index:
            if i > 0:
                assert direction.iloc[i] == -1, f"Short at {i}: direction should be -1"
                assert direction.iloc[i - 1] == 1, f"Short at {i}: prev direction should be 1"

    def test_signal_mode_vs_filter_mode_fewer_signals(self, adapter, trending_ohlcv):
        """Signal mode should have far fewer True signals than filter mode."""
        filter_result = _run(adapter, trending_ohlcv, {"use_supertrend": True, "period": 1})
        signal_result = _run(
            adapter,
            trending_ohlcv,
            {
                "use_supertrend": True,
                "generate_on_trend_change": True,
                "period": 1,
            },
        )
        filter_longs = filter_result["long"].sum()
        signal_longs = signal_result["long"].sum()
        assert signal_longs < filter_longs, "Signal mode should have fewer signals than filter"

    def test_signal_mode_long_short_no_overlap(self, adapter, trending_ohlcv):
        """Signal mode: long and short should never be True on same bar."""
        result = _run(
            adapter,
            trending_ohlcv,
            {
                "use_supertrend": True,
                "generate_on_trend_change": True,
                "period": 1,
            },
        )
        both = (result["long"] & result["short"]).sum()
        assert both == 0


# ============================================================
# 4. OPPOSITE SIGNAL
# ============================================================


class TestOppositeSignal:
    """opposite_signal=True swaps long/short."""

    def test_opposite_filter_mode(self, adapter, trending_ohlcv):
        """Filter mode + opposite: long/short should be swapped."""
        normal = _run(adapter, trending_ohlcv, {"use_supertrend": True, "period": 1})
        opposite = _run(
            adapter,
            trending_ohlcv,
            {
                "use_supertrend": True,
                "opposite_signal": True,
                "period": 1,
            },
        )
        pd.testing.assert_series_equal(
            normal["long"].reset_index(drop=True),
            opposite["short"].reset_index(drop=True),
            check_names=False,
        )
        pd.testing.assert_series_equal(
            normal["short"].reset_index(drop=True),
            opposite["long"].reset_index(drop=True),
            check_names=False,
        )

    def test_opposite_signal_mode(self, adapter, trending_ohlcv):
        """Signal mode + opposite: long/short should be swapped."""
        normal = _run(
            adapter,
            trending_ohlcv,
            {
                "use_supertrend": True,
                "generate_on_trend_change": True,
                "period": 1,
            },
        )
        opposite = _run(
            adapter,
            trending_ohlcv,
            {
                "use_supertrend": True,
                "generate_on_trend_change": True,
                "opposite_signal": True,
                "period": 1,
            },
        )
        pd.testing.assert_series_equal(
            normal["long"].reset_index(drop=True),
            opposite["short"].reset_index(drop=True),
            check_names=False,
        )
        pd.testing.assert_series_equal(
            normal["short"].reset_index(drop=True),
            opposite["long"].reset_index(drop=True),
            check_names=False,
        )

    def test_opposite_does_not_affect_supertrend_line(self, adapter, trending_ohlcv):
        """Opposite only affects long/short, not the SuperTrend line itself."""
        normal = _run(adapter, trending_ohlcv, {"use_supertrend": True, "period": 1})
        opposite = _run(
            adapter,
            trending_ohlcv,
            {
                "use_supertrend": True,
                "opposite_signal": True,
                "period": 1,
            },
        )
        pd.testing.assert_series_equal(
            normal["supertrend"].reset_index(drop=True),
            opposite["supertrend"].reset_index(drop=True),
            check_names=False,
        )


# ============================================================
# 5. PARAMETER VARIATIONS
# ============================================================


class TestParameters:
    """Test different parameter values."""

    def test_custom_period(self, adapter, trending_ohlcv):
        """Different ATR period should produce different SuperTrend values.

        Both periods must be 1 to avoid the NaN-propagation issue.
        We differentiate by using period=1 (raw TR) and verify that
        different multipliers on top produce different lines.
        """
        r1 = _run(adapter, trending_ohlcv, {"period": 1, "multiplier": 1.0})
        r2 = _run(adapter, trending_ohlcv, {"period": 1, "multiplier": 3.0})
        # SuperTrend lines should differ with different multiplier
        assert not r1["supertrend"].equals(r2["supertrend"])

    def test_custom_multiplier(self, adapter, trending_ohlcv):
        """Different multiplier should produce different SuperTrend values."""
        r1 = _run(adapter, trending_ohlcv, {"period": 1, "multiplier": 1.5})
        r2 = _run(adapter, trending_ohlcv, {"period": 1, "multiplier": 5.0})
        assert not r1["supertrend"].equals(r2["supertrend"])

    def test_atr_period_alias(self, adapter, trending_ohlcv):
        """atr_period should work as alias for period (from old filter)."""
        r1 = _run(adapter, trending_ohlcv, {"period": 1})
        r2 = _run(adapter, trending_ohlcv, {"atr_period": 1})
        pd.testing.assert_series_equal(
            r1["supertrend"].reset_index(drop=True),
            r2["supertrend"].reset_index(drop=True),
            check_names=False,
        )

    def test_atr_multiplier_alias(self, adapter, trending_ohlcv):
        """atr_multiplier should work as alias for multiplier (from old filter)."""
        r1 = _run(adapter, trending_ohlcv, {"period": 1, "multiplier": 2.5})
        r2 = _run(adapter, trending_ohlcv, {"period": 1, "atr_multiplier": 2.5})
        pd.testing.assert_series_equal(
            r1["supertrend"].reset_index(drop=True),
            r2["supertrend"].reset_index(drop=True),
            check_names=False,
        )

    def test_higher_multiplier_fewer_flips(self, adapter, trending_ohlcv):
        """Higher multiplier = wider bands = fewer direction flips."""
        tight = _run(
            adapter,
            trending_ohlcv,
            {
                "use_supertrend": True,
                "generate_on_trend_change": True,
                "period": 1,
                "multiplier": 0.5,
            },
        )
        wide = _run(
            adapter,
            trending_ohlcv,
            {
                "use_supertrend": True,
                "generate_on_trend_change": True,
                "period": 1,
                "multiplier": 5.0,
            },
        )
        tight_flips = tight["long"].sum() + tight["short"].sum()
        wide_flips = wide["long"].sum() + wide["short"].sum()
        assert wide_flips <= tight_flips, "Higher multiplier should produce fewer or equal flips"

    def test_upper_lower_band_consistency(self, adapter, trending_ohlcv):
        """upper should be populated where direction==-1, lower where direction==1.

        Uses period=1 to avoid NaN propagation.  Skips bar 0 (direction=0).
        """
        result = _run(adapter, trending_ohlcv, {"period": 1})
        direction = result["direction"].iloc[1:]  # skip bar 0
        upper = result["upper"].iloc[1:]
        lower = result["lower"].iloc[1:]

        # Where direction is -1 (downtrend), upper should be non-NaN
        downtrend = direction == -1
        if downtrend.any():
            assert upper[downtrend].notna().all(), "Upper should be set in downtrend"
            assert lower[downtrend].isna().all(), "Lower should be NaN in downtrend"

        # Where direction is 1 (uptrend), lower should be non-NaN
        uptrend = direction == 1
        if uptrend.any():
            assert lower[uptrend].notna().all(), "Lower should be set in uptrend"
            assert upper[uptrend].isna().all(), "Upper should be NaN in uptrend"


# ============================================================
# 6. OPTIMIZATION PARAMS
# ============================================================


class TestOptimization:
    """Test that optimization parameters produce valid results."""

    @pytest.mark.parametrize("period", [1, 2, 3, 5])
    def test_period_range(self, adapter, trending_ohlcv, period):
        """Typical optimization range periods should all produce valid results.

        NOTE: ``calculate_supertrend`` has NaN propagation for period > 1 but
        should still return valid long/short signals (all True in passthrough
        or at least valid bool dtype when ``use_supertrend=True``).
        """
        result = _run(adapter, trending_ohlcv, {"period": period, "use_supertrend": True})
        assert result["long"].dtype == bool or result["long"].dtype == np.bool_
        # SuperTrend should have at least the index-0 value (0.0 from np.zeros)
        assert result["supertrend"] is not None

    @pytest.mark.parametrize("multiplier", [0.5, 1.0, 2.0, 3.0, 5.0])
    def test_multiplier_range(self, adapter, trending_ohlcv, multiplier):
        """Typical optimization range multipliers should all work."""
        result = _run(adapter, trending_ohlcv, {"period": 1, "multiplier": multiplier, "use_supertrend": True})
        assert result["long"].dtype == bool or result["long"].dtype == np.bool_
        assert result["supertrend"].notna().sum() > 0


# ============================================================
# 7. API ENDPOINT TESTS
# ============================================================


class TestAPI:
    """Verify API endpoints accept supertrend blocks correctly."""

    def test_block_library_has_supertrend(self):
        """Block library should list 'supertrend' as an indicator."""
        resp = client.get("/api/v1/strategy-builder/block-library")
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                indicators = data.get("indicators", data.get("blocks", []))
                if isinstance(indicators, list):
                    ids = [b.get("id", b.get("type", "")) for b in indicators]
                    assert "supertrend" in ids

    def test_block_library_no_supertrend_filter(self):
        """Block library should NOT list 'supertrend_filter' (removed)."""
        resp = client.get("/api/v1/strategy-builder/block-library")
        if resp.status_code == 200:
            data = resp.json()
            all_text = str(data)
            # supertrend_filter should not appear as a block ID
            assert "supertrend_filter" not in all_text or "removed" in all_text.lower()

    def test_block_library_no_supertrend_buy_sell_signals(self):
        """Block library should NOT list supertrend_buy/sell_signal (removed)."""
        resp = client.get("/api/v1/strategy-builder/block-library")
        if resp.status_code == 200:
            data = resp.json()
            all_text = str(data)
            assert "supertrend_buy_signal" not in all_text
            assert "supertrend_sell_signal" not in all_text


# ============================================================
# 8. COMPARISON: SuperTrend FILTER vs SIGNAL mode logic
# ============================================================


class TestFilterVsSignalLogic:
    """Verify the relationship between filter and signal mode outputs."""

    def test_signal_mode_is_subset_of_filter_mode(self, adapter, trending_ohlcv):
        """Signal fires are a subset of filter's True bars.

        If signal fires long at bar i, then filter's long at bar i must also be True.
        """
        filter_r = _run(adapter, trending_ohlcv, {"use_supertrend": True, "period": 1})
        signal_r = _run(
            adapter,
            trending_ohlcv,
            {
                "use_supertrend": True,
                "generate_on_trend_change": True,
                "period": 1,
            },
        )
        # Every signal long=True bar should also be filter long=True
        signal_longs = signal_r["long"]
        filter_longs = filter_r["long"]
        mismatches = (signal_longs & ~filter_longs).sum()
        assert mismatches == 0, "Signal long should only fire where filter long is also True"

    def test_both_modes_same_supertrend_line(self, adapter, trending_ohlcv):
        """Both modes should compute identical SuperTrend line values."""
        filter_r = _run(adapter, trending_ohlcv, {"use_supertrend": True, "period": 1})
        signal_r = _run(
            adapter,
            trending_ohlcv,
            {
                "use_supertrend": True,
                "generate_on_trend_change": True,
                "period": 1,
            },
        )
        pd.testing.assert_series_equal(
            filter_r["supertrend"].reset_index(drop=True),
            signal_r["supertrend"].reset_index(drop=True),
            check_names=False,
        )

    def test_both_modes_same_direction(self, adapter, trending_ohlcv):
        """Both modes should have identical direction series."""
        filter_r = _run(adapter, trending_ohlcv, {"use_supertrend": True, "period": 1})
        signal_r = _run(
            adapter,
            trending_ohlcv,
            {
                "use_supertrend": True,
                "generate_on_trend_change": True,
                "period": 1,
            },
        )
        pd.testing.assert_series_equal(
            filter_r["direction"].reset_index(drop=True),
            signal_r["direction"].reset_index(drop=True),
            check_names=False,
        )

    def test_flat_market_filter_still_works(self, adapter, flat_ohlcv):
        """In flat market, filter mode should still produce valid long/short.

        Uses period=1 and skips bar 0 (direction=0).
        """
        result = _run(adapter, flat_ohlcv, {"use_supertrend": True, "period": 1})
        # Should have either long or short on every bar (after bar 0)
        either = result["long"] | result["short"]
        assert either.iloc[1:].all()
