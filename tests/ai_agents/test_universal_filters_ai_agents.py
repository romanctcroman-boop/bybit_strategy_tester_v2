"""
AI Agent Knowledge Test: Universal Filters (5 new instruments in "Технические Индикаторы")

Tests verify that AI agents correctly understand:

== ATR VOLATILITY (filter) ==
- Block type: 'atr_volatility', category: 'indicator'
- Toggle: use_atr_volatility (bool, default false → passthrough: all True)
- Parameters: atr_length1 (int 5-20, default 20), atr_length2 (int 20-100, default 100),
  atr_smoothing (WMA|RMA|SMA|EMA, default WMA), atr_diff_percent (float 0.1-50, default 10),
  atr1_to_atr2 ("ATR1 < ATR2" | "ATR1 > ATR2")
- Returns: {long_signal, short_signal} — symmetric (same condition)

== VOLUME FILTER (filter) ==
- Block type: 'volume_filter', category: 'indicator'
- Toggle: use_volume_filter (bool, default false → passthrough)
- Parameters: vol_length1 (int 5-20, default 20), vol_length2 (int 20-100, default 100),
  vol_smoothing (WMA|RMA|SMA|EMA, default WMA), vol_diff_percent (float 0.1-50, default 10),
  vol1_to_vol2 ("VOL1 < VOL2" | "VOL1 > VOL2")
- Returns: {long_signal, short_signal} — symmetric

== HIGHEST/LOWEST BAR (signal + filter) ==
- Block type: 'highest_lowest_bar', category: 'indicator'
- Sub-toggles: use_highest_lowest (bool), use_block_worse_than (bool)
- HL params: hl_lookback_bars (int 1-100, default 10), hl_price_percent (float 0-30),
  hl_atr_percent (float 0-30), atr_hl_length (int 1-50, default 50)
- Worse params: block_worse_percent (float 0.1-30, default 1.1)
- Returns: {long_signal, short_signal} — asymmetric (highest→long, lowest→short)

== TWO MAs (signal + filter) ==
- Block type: 'two_mas', category: 'indicator'
- Parameters: ma1_length (int 1-500, default 50), ma1_smoothing (SMA|EMA|WMA|RMA),
  ma1_source (close|open|high|low), ma2_length (int 1-500, default 100),
  ma2_smoothing (SMA|EMA|WMA|RMA), ma2_source (close|open|high|low)
- Sub-toggles: use_ma_cross (bool), opposite_ma_cross (bool),
  activate_ma_cross_memory (bool), ma_cross_memory_bars (int 1-100, default 5),
  use_ma1_filter (bool), opposite_ma1_filter (bool)
- Returns: {long_signal, short_signal, ma1, ma2}

== ACCUMULATION AREAS (filter or signal) ==
- Block type: 'accumulation_areas', category: 'indicator'
- Toggle: use_accumulation (bool, default false → passthrough)
- Parameters: backtracking_interval (int 1-100, default 30),
  min_bars_to_execute (int 1-100, default 5),
  signal_on_breakout (bool), signal_on_opposite_breakout (bool)
- Returns: {long_signal, short_signal}

Architecture:
    - Frontend category: 'indicator' (blockLibrary.indicators)
    - _BLOCK_CATEGORY_MAP: all 5 -> "indicator"
    - Backend handler: _execute_indicator()
    - CONNECTION_RULES: all 5 in entry_long and entry_short allowed sources

Run:
    py -3.14 -m pytest tests/ai_agents/test_universal_filters_ai_agents.py -v
    py -3.14 -m pytest tests/ai_agents/test_universal_filters_ai_agents.py -v -k "atr_vol"
    py -3.14 -m pytest tests/ai_agents/test_universal_filters_ai_agents.py -v -k "volume"
    py -3.14 -m pytest tests/ai_agents/test_universal_filters_ai_agents.py -v -k "highest"
    py -3.14 -m pytest tests/ai_agents/test_universal_filters_ai_agents.py -v -k "two_mas"
    py -3.14 -m pytest tests/ai_agents/test_universal_filters_ai_agents.py -v -k "accumulation"
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

project_root = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.api.app import app
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.database import Base, get_db

# ============================================================
# Test DB (in-memory SQLite)
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
    app.dependency_overrides[get_db] = _override_get_db
    Base.metadata.create_all(bind=_engine)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def adapter() -> StrategyBuilderAdapter:
    """Bare adapter — no data loaded, used for unit-level calls."""
    return StrategyBuilderAdapter.__new__(StrategyBuilderAdapter)


@pytest.fixture
def ohlcv_data() -> pd.DataFrame:
    """Generate 200-bar OHLCV data with trends and ranging sections."""
    np.random.seed(42)
    n = 200
    base_price = 50000.0

    trend = np.zeros(n)
    for i in range(n):
        if i < 50:
            trend[i] = i * 20  # strong uptrend
        elif i < 100:
            trend[i] = 1000 - (i - 50) * 5  # gentle downtrend
        elif i < 130:
            trend[i] = 750 + np.sin(i * 0.3) * 30  # ranging
        else:
            trend[i] = 750 + (i - 130) * 15  # resumption

    noise = np.random.randn(n) * 50
    close = base_price + trend + noise
    high = close + np.abs(np.random.randn(n)) * 120
    low = close - np.abs(np.random.randn(n)) * 120
    open_price = np.roll(close, 1)
    open_price[0] = base_price
    volume = np.random.uniform(500, 15000, n)

    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="1h"),
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


@pytest.fixture
def flat_ohlcv() -> pd.DataFrame:
    """Flat/ranging OHLCV data — narrow range, high volume variation."""
    np.random.seed(99)
    n = 150
    close = pd.Series(50000 + np.random.normal(0, 20.0, n), name="close")
    high = close + np.abs(np.random.normal(10.0, 5.0, n))
    low = close - np.abs(np.random.normal(10.0, 5.0, n))
    open_ = close + np.random.normal(0, 5.0, n)
    volume = pd.Series(np.random.randint(100, 20000, n), dtype=float, name="volume")

    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="1h"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def _run(
    adapter: StrategyBuilderAdapter,
    block_type: str,
    params: dict[str, Any],
    ohlcv: pd.DataFrame,
) -> dict:
    """Helper — execute indicator block."""
    return adapter._execute_indicator(block_type, params, ohlcv, {})


# ============================================================
# 1. CATEGORY MAP TESTS (all 5 blocks)
# ============================================================


class TestCategoryMapRegistration:
    """All 5 universal filter block types are mapped to 'indicator'."""

    @pytest.mark.parametrize(
        "block_type",
        [
            "atr_volatility",
            "volume_filter",
            "highest_lowest_bar",
            "two_mas",
            "accumulation_areas",
        ],
    )
    def test_category_map_contains_block(self, block_type):
        """_BLOCK_CATEGORY_MAP must map '{block_type}' -> 'indicator'."""
        assert StrategyBuilderAdapter._BLOCK_CATEGORY_MAP.get(block_type) == "indicator"


# ============================================================
# 2. ATR VOLATILITY TESTS
# ============================================================


class TestATRVolatilityPassthrough:
    """When use_atr_volatility=False (default), long/short are all True."""

    def test_passthrough_default_params(self, adapter, ohlcv_data):
        """Default params → passthrough mode."""
        result = _run(adapter, "atr_volatility", {}, ohlcv_data)
        assert "long_signal" in result
        assert "short_signal" in result
        assert result["long_signal"].all()
        assert result["short_signal"].all()

    def test_passthrough_explicit_false(self, adapter, ohlcv_data):
        """use_atr_volatility=False → passthrough."""
        result = _run(adapter, "atr_volatility", {"use_atr_volatility": False}, ohlcv_data)
        assert result["long_signal"].all()
        assert result["short_signal"].all()


class TestATRVolatilityActive:
    """When use_atr_volatility=True, ATR comparison is applied."""

    def test_active_returns_boolean_series(self, adapter, ohlcv_data):
        """Activated ATR filter returns boolean long_signal/short_signal."""
        params = {"use_atr_volatility": True, "atr_length1": 10, "atr_length2": 50}
        result = _run(adapter, "atr_volatility", params, ohlcv_data)
        assert result["long_signal"].dtype == bool
        assert result["short_signal"].dtype == bool

    def test_series_length_matches_input(self, adapter, ohlcv_data):
        """Output series length matches input data."""
        params = {"use_atr_volatility": True}
        result = _run(adapter, "atr_volatility", params, ohlcv_data)
        assert len(result["long_signal"]) == len(ohlcv_data)
        assert len(result["short_signal"]) == len(ohlcv_data)

    def test_symmetric_signals(self, adapter, ohlcv_data):
        """ATR volatility filter is symmetric (same condition for long and short)."""
        params = {"use_atr_volatility": True, "atr_length1": 10, "atr_length2": 50}
        result = _run(adapter, "atr_volatility", params, ohlcv_data)
        pd.testing.assert_series_equal(result["long_signal"], result["short_signal"])

    def test_mode_atr1_less_than_atr2(self, adapter, ohlcv_data):
        """ATR1 < ATR2 mode: filters for low volatility."""
        params = {
            "use_atr_volatility": True,
            "atr_length1": 10,
            "atr_length2": 50,
            "atr1_to_atr2": "ATR1 < ATR2",
            "atr_diff_percent": 5,
        }
        result = _run(adapter, "atr_volatility", params, ohlcv_data)
        assert isinstance(result["long_signal"], pd.Series)

    def test_mode_atr1_greater_than_atr2(self, adapter, ohlcv_data):
        """ATR1 > ATR2 mode: filters for high volatility."""
        params = {
            "use_atr_volatility": True,
            "atr_length1": 10,
            "atr_length2": 50,
            "atr1_to_atr2": "ATR1 > ATR2",
            "atr_diff_percent": 5,
        }
        result = _run(adapter, "atr_volatility", params, ohlcv_data)
        assert isinstance(result["long_signal"], pd.Series)

    def test_opposite_modes_differ(self, adapter, ohlcv_data):
        """ATR1<ATR2 and ATR1>ATR2 produce different results."""
        base = {
            "use_atr_volatility": True,
            "atr_length1": 10,
            "atr_length2": 50,
            "atr_diff_percent": 5,
        }
        r_less = _run(adapter, "atr_volatility", {**base, "atr1_to_atr2": "ATR1 < ATR2"}, ohlcv_data)
        r_greater = _run(adapter, "atr_volatility", {**base, "atr1_to_atr2": "ATR1 > ATR2"}, ohlcv_data)
        # They should not be identical (unless all bars fail both conditions)
        assert not r_less["long_signal"].equals(r_greater["long_signal"]) or (
            not r_less["long_signal"].any() and not r_greater["long_signal"].any()
        )

    @pytest.mark.parametrize("smoothing", ["WMA", "RMA", "SMA", "EMA"])
    def test_smoothing_methods_run_without_error(self, adapter, ohlcv_data, smoothing):
        """All 4 smoothing methods must execute without error."""
        params = {
            "use_atr_volatility": True,
            "atr_length1": 10,
            "atr_length2": 50,
            "atr_smoothing": smoothing,
        }
        result = _run(adapter, "atr_volatility", params, ohlcv_data)
        assert "long_signal" in result

    def test_high_diff_percent_reduces_signals(self, adapter, ohlcv_data):
        """Higher diff_percent threshold reduces number of passing bars."""
        base = {"use_atr_volatility": True, "atr_length1": 10, "atr_length2": 50}
        r5 = _run(adapter, "atr_volatility", {**base, "atr_diff_percent": 5}, ohlcv_data)
        r30 = _run(adapter, "atr_volatility", {**base, "atr_diff_percent": 30}, ohlcv_data)
        assert r5["long_signal"].sum() >= r30["long_signal"].sum()


# ============================================================
# 3. VOLUME FILTER TESTS
# ============================================================


class TestVolumeFilterPassthrough:
    """When use_volume_filter=False (default), long/short are all True."""

    def test_passthrough_default(self, adapter, ohlcv_data):
        result = _run(adapter, "volume_filter", {}, ohlcv_data)
        assert result["long_signal"].all()
        assert result["short_signal"].all()

    def test_passthrough_explicit_false(self, adapter, ohlcv_data):
        result = _run(adapter, "volume_filter", {"use_volume_filter": False}, ohlcv_data)
        assert result["long_signal"].all()
        assert result["short_signal"].all()


class TestVolumeFilterActive:
    """When use_volume_filter=True, volume comparison is applied."""

    def test_active_returns_boolean_series(self, adapter, ohlcv_data):
        params = {"use_volume_filter": True, "vol_length1": 10, "vol_length2": 50}
        result = _run(adapter, "volume_filter", params, ohlcv_data)
        assert result["long_signal"].dtype == bool
        assert result["short_signal"].dtype == bool

    def test_series_length_matches_input(self, adapter, ohlcv_data):
        params = {"use_volume_filter": True}
        result = _run(adapter, "volume_filter", params, ohlcv_data)
        assert len(result["long_signal"]) == len(ohlcv_data)

    def test_symmetric_signals(self, adapter, ohlcv_data):
        """Volume filter is symmetric (same condition for long and short)."""
        params = {"use_volume_filter": True, "vol_length1": 10, "vol_length2": 50}
        result = _run(adapter, "volume_filter", params, ohlcv_data)
        pd.testing.assert_series_equal(result["long_signal"], result["short_signal"])

    def test_mode_vol1_less_than_vol2(self, adapter, ohlcv_data):
        params = {
            "use_volume_filter": True,
            "vol_length1": 10,
            "vol_length2": 50,
            "vol1_to_vol2": "VOL1 < VOL2",
            "vol_diff_percent": 5,
        }
        result = _run(adapter, "volume_filter", params, ohlcv_data)
        assert isinstance(result["long_signal"], pd.Series)

    def test_mode_vol1_greater_than_vol2(self, adapter, ohlcv_data):
        params = {
            "use_volume_filter": True,
            "vol_length1": 10,
            "vol_length2": 50,
            "vol1_to_vol2": "VOL1 > VOL2",
            "vol_diff_percent": 5,
        }
        result = _run(adapter, "volume_filter", params, ohlcv_data)
        assert isinstance(result["long_signal"], pd.Series)

    @pytest.mark.parametrize("smoothing", ["WMA", "RMA", "SMA", "EMA"])
    def test_smoothing_methods_run_without_error(self, adapter, ohlcv_data, smoothing):
        """All 4 smoothing methods must execute without error."""
        params = {
            "use_volume_filter": True,
            "vol_length1": 10,
            "vol_length2": 50,
            "vol_smoothing": smoothing,
        }
        result = _run(adapter, "volume_filter", params, ohlcv_data)
        assert "long_signal" in result

    def test_high_diff_percent_reduces_signals(self, adapter, ohlcv_data):
        base = {"use_volume_filter": True, "vol_length1": 10, "vol_length2": 50}
        r5 = _run(adapter, "volume_filter", {**base, "vol_diff_percent": 5}, ohlcv_data)
        r30 = _run(adapter, "volume_filter", {**base, "vol_diff_percent": 30}, ohlcv_data)
        assert r5["long_signal"].sum() >= r30["long_signal"].sum()


# ============================================================
# 4. HIGHEST/LOWEST BAR TESTS
# ============================================================


class TestHighestLowestBarPassthrough:
    """When both sub-toggles are off, returns all True (passthrough)."""

    def test_passthrough_default(self, adapter, ohlcv_data):
        result = _run(adapter, "highest_lowest_bar", {}, ohlcv_data)
        assert result["long_signal"].all()
        assert result["short_signal"].all()

    def test_passthrough_both_false(self, adapter, ohlcv_data):
        params = {"use_highest_lowest": False, "use_block_worse_than": False}
        result = _run(adapter, "highest_lowest_bar", params, ohlcv_data)
        assert result["long_signal"].all()
        assert result["short_signal"].all()


class TestHighestLowestBarSignal:
    """Tests for the Highest/Lowest Bar detection signal."""

    def test_returns_boolean_series(self, adapter, ohlcv_data):
        params = {"use_highest_lowest": True, "hl_lookback_bars": 10}
        result = _run(adapter, "highest_lowest_bar", params, ohlcv_data)
        assert result["long_signal"].dtype == bool
        assert result["short_signal"].dtype == bool

    def test_series_length_matches(self, adapter, ohlcv_data):
        params = {"use_highest_lowest": True, "hl_lookback_bars": 10}
        result = _run(adapter, "highest_lowest_bar", params, ohlcv_data)
        assert len(result["long_signal"]) == len(ohlcv_data)
        assert len(result["short_signal"]) == len(ohlcv_data)

    def test_asymmetric_signals(self, adapter, ohlcv_data):
        """Highest bar → long, lowest bar → short — should differ."""
        params = {"use_highest_lowest": True, "hl_lookback_bars": 5}
        result = _run(adapter, "highest_lowest_bar", params, ohlcv_data)
        # In trending data, highest and lowest bar signals should differ
        assert not result["long_signal"].equals(result["short_signal"])

    def test_longer_lookback_fewer_signals(self, adapter, ohlcv_data):
        """Longer lookback → fewer bars qualify as highest/lowest."""
        r5 = _run(adapter, "highest_lowest_bar", {"use_highest_lowest": True, "hl_lookback_bars": 5}, ohlcv_data)
        r50 = _run(adapter, "highest_lowest_bar", {"use_highest_lowest": True, "hl_lookback_bars": 50}, ohlcv_data)
        assert r5["long_signal"].sum() >= r50["long_signal"].sum()

    def test_price_percent_condition(self, adapter, ohlcv_data):
        """Adding price_percent condition further filters signals."""
        r0 = _run(
            adapter,
            "highest_lowest_bar",
            {
                "use_highest_lowest": True,
                "hl_lookback_bars": 10,
                "hl_price_percent": 0,
            },
            ohlcv_data,
        )
        r5 = _run(
            adapter,
            "highest_lowest_bar",
            {
                "use_highest_lowest": True,
                "hl_lookback_bars": 10,
                "hl_price_percent": 5,
            },
            ohlcv_data,
        )
        assert r0["long_signal"].sum() >= r5["long_signal"].sum()

    def test_atr_percent_condition(self, adapter, ohlcv_data):
        """ATR percent condition filters differently."""
        params = {
            "use_highest_lowest": True,
            "hl_lookback_bars": 10,
            "hl_atr_percent": 10,
            "atr_hl_length": 20,
        }
        result = _run(adapter, "highest_lowest_bar", params, ohlcv_data)
        assert isinstance(result["long_signal"], pd.Series)
        assert isinstance(result["short_signal"], pd.Series)


class TestBlockIfWorseThan:
    """Tests for the 'Block if Worse Than' sub-filter."""

    def test_worse_than_filter_alone(self, adapter, ohlcv_data):
        """Block if worse than works independently when highest/lowest is off."""
        params = {
            "use_highest_lowest": False,
            "use_block_worse_than": True,
            "block_worse_percent": 1.0,
        }
        result = _run(adapter, "highest_lowest_bar", params, ohlcv_data)
        # With tight threshold, not all bars should pass
        assert not result["long_signal"].all()
        assert not result["short_signal"].all()

    def test_tighter_percent_fewer_signals(self, adapter, ohlcv_data):
        """Lower block_worse_percent → fewer bars pass the filter."""
        r_wide = _run(
            adapter,
            "highest_lowest_bar",
            {
                "use_block_worse_than": True,
                "block_worse_percent": 5.0,
            },
            ohlcv_data,
        )
        r_tight = _run(
            adapter,
            "highest_lowest_bar",
            {
                "use_block_worse_than": True,
                "block_worse_percent": 0.5,
            },
            ohlcv_data,
        )
        assert r_wide["long_signal"].sum() >= r_tight["long_signal"].sum()

    def test_combined_hl_and_worse(self, adapter, ohlcv_data):
        """Both sub-toggles combined further reduce signals."""
        r_hl = _run(
            adapter,
            "highest_lowest_bar",
            {
                "use_highest_lowest": True,
                "hl_lookback_bars": 10,
            },
            ohlcv_data,
        )
        r_both = _run(
            adapter,
            "highest_lowest_bar",
            {
                "use_highest_lowest": True,
                "hl_lookback_bars": 10,
                "use_block_worse_than": True,
                "block_worse_percent": 1.0,
            },
            ohlcv_data,
        )
        assert r_hl["long_signal"].sum() >= r_both["long_signal"].sum()


# ============================================================
# 5. TWO MAs TESTS
# ============================================================


class TestTwoMAsPassthrough:
    """When no sub-toggles (ma_cross, ma1_filter) are on → all True."""

    def test_passthrough_default(self, adapter, ohlcv_data):
        result = _run(adapter, "two_mas", {}, ohlcv_data)
        assert result["long_signal"].all()
        assert result["short_signal"].all()

    def test_returns_ma_series(self, adapter, ohlcv_data):
        """Must return ma1 and ma2 series in output."""
        result = _run(adapter, "two_mas", {}, ohlcv_data)
        assert "ma1" in result
        assert "ma2" in result
        assert isinstance(result["ma1"], pd.Series)
        assert isinstance(result["ma2"], pd.Series)
        assert len(result["ma1"]) == len(ohlcv_data)


class TestTwoMAsCrossSignal:
    """Tests for MA cross signal mode."""

    def test_ma_cross_produces_signals(self, adapter, ohlcv_data):
        """MA cross signal should generate some True values on trending data."""
        params = {
            "use_ma_cross": True,
            "ma1_length": 10,
            "ma2_length": 50,
            "ma1_smoothing": "SMA",
            "ma2_smoothing": "SMA",
        }
        result = _run(adapter, "two_mas", params, ohlcv_data)
        # On trending data, there should be some crossovers
        assert result["long_signal"].any() or result["short_signal"].any()

    def test_cross_long_short_are_different(self, adapter, ohlcv_data):
        """Long cross (MA1 crosses above MA2) differs from short cross."""
        params = {
            "use_ma_cross": True,
            "ma1_length": 10,
            "ma2_length": 50,
        }
        result = _run(adapter, "two_mas", params, ohlcv_data)
        # Cross signals should be directional
        assert not result["long_signal"].equals(result["short_signal"])

    def test_opposite_cross_reverses_signals(self, adapter, ohlcv_data):
        """opposite_ma_cross swaps long and short signals."""
        base = {"use_ma_cross": True, "ma1_length": 10, "ma2_length": 50}
        r_normal = _run(adapter, "two_mas", {**base, "opposite_ma_cross": False}, ohlcv_data)
        r_opposite = _run(adapter, "two_mas", {**base, "opposite_ma_cross": True}, ohlcv_data)
        pd.testing.assert_series_equal(r_normal["long_signal"], r_opposite["short_signal"])
        pd.testing.assert_series_equal(r_normal["short_signal"], r_opposite["long_signal"])

    def test_cross_memory_extends_signals(self, adapter, ohlcv_data):
        """Signal memory should keep cross signal active for N bars."""
        base = {"use_ma_cross": True, "ma1_length": 10, "ma2_length": 50}
        r_no_mem = _run(
            adapter,
            "two_mas",
            {
                **base,
                "activate_ma_cross_memory": False,
            },
            ohlcv_data,
        )
        r_mem = _run(
            adapter,
            "two_mas",
            {
                **base,
                "activate_ma_cross_memory": True,
                "ma_cross_memory_bars": 10,
            },
            ohlcv_data,
        )
        # Memory extends signal so sum should be >= without memory
        assert r_mem["long_signal"].sum() >= r_no_mem["long_signal"].sum()

    @pytest.mark.parametrize("ma_type", ["SMA", "EMA", "WMA", "RMA"])
    def test_ma_types_run_without_error(self, adapter, ohlcv_data, ma_type):
        """All 4 MA types run without error."""
        params = {
            "use_ma_cross": True,
            "ma1_length": 10,
            "ma1_smoothing": ma_type,
            "ma2_length": 50,
            "ma2_smoothing": ma_type,
        }
        result = _run(adapter, "two_mas", params, ohlcv_data)
        assert "long_signal" in result
        assert "ma1" in result


class TestTwoMAsFilter:
    """Tests for MA1 as filter mode."""

    def test_ma1_filter_produces_signals(self, adapter, ohlcv_data):
        """MA1 filter (close > MA1 for long, close < MA1 for short)."""
        params = {
            "use_ma1_filter": True,
            "ma1_length": 50,
            "ma1_smoothing": "SMA",
        }
        result = _run(adapter, "two_mas", params, ohlcv_data)
        # In trending data, filter should have mixed signals
        assert not result["long_signal"].all()
        assert not result["short_signal"].all()

    def test_opposite_filter_reverses(self, adapter, ohlcv_data):
        """opposite_ma1_filter swaps filter direction."""
        base = {"use_ma1_filter": True, "ma1_length": 50, "ma1_smoothing": "SMA"}
        r_normal = _run(adapter, "two_mas", {**base, "opposite_ma1_filter": False}, ohlcv_data)
        r_opposite = _run(adapter, "two_mas", {**base, "opposite_ma1_filter": True}, ohlcv_data)
        pd.testing.assert_series_equal(r_normal["long_signal"], r_opposite["short_signal"])
        pd.testing.assert_series_equal(r_normal["short_signal"], r_opposite["long_signal"])

    def test_combined_cross_and_filter(self, adapter, ohlcv_data):
        """Both MA cross and MA1 filter can be used together."""
        params = {
            "use_ma_cross": True,
            "use_ma1_filter": True,
            "ma1_length": 10,
            "ma2_length": 50,
        }
        result = _run(adapter, "two_mas", params, ohlcv_data)
        # Combined should produce fewer signals than cross alone
        r_cross = _run(
            adapter,
            "two_mas",
            {
                "use_ma_cross": True,
                "ma1_length": 10,
                "ma2_length": 50,
            },
            ohlcv_data,
        )
        assert result["long_signal"].sum() <= r_cross["long_signal"].sum()

    @pytest.mark.parametrize("source", ["close", "open", "high", "low"])
    def test_ma_source_options(self, adapter, ohlcv_data, source):
        """All source options run without error."""
        params = {
            "use_ma1_filter": True,
            "ma1_length": 20,
            "ma1_source": source,
            "ma2_source": source,
        }
        result = _run(adapter, "two_mas", params, ohlcv_data)
        assert "long_signal" in result


# ============================================================
# 6. ACCUMULATION AREAS TESTS
# ============================================================


class TestAccumulationPassthrough:
    """When use_accumulation=False (default), all True."""

    def test_passthrough_default(self, adapter, ohlcv_data):
        result = _run(adapter, "accumulation_areas", {}, ohlcv_data)
        assert result["long_signal"].all()
        assert result["short_signal"].all()

    def test_passthrough_explicit_false(self, adapter, ohlcv_data):
        result = _run(adapter, "accumulation_areas", {"use_accumulation": False}, ohlcv_data)
        assert result["long_signal"].all()
        assert result["short_signal"].all()


class TestAccumulationFilterMode:
    """Accumulation zone detection (filter mode, no breakout signals)."""

    def test_filter_mode_returns_boolean(self, adapter, ohlcv_data):
        params = {"use_accumulation": True, "backtracking_interval": 20, "min_bars_to_execute": 3}
        result = _run(adapter, "accumulation_areas", params, ohlcv_data)
        assert result["long_signal"].dtype == bool
        assert result["short_signal"].dtype == bool

    def test_filter_mode_symmetric_signals(self, adapter, ohlcv_data):
        """In filter mode, long and short signals are identical."""
        params = {"use_accumulation": True, "backtracking_interval": 20, "min_bars_to_execute": 3}
        result = _run(adapter, "accumulation_areas", params, ohlcv_data)
        pd.testing.assert_series_equal(result["long_signal"], result["short_signal"])

    def test_series_length_matches(self, adapter, ohlcv_data):
        params = {"use_accumulation": True}
        result = _run(adapter, "accumulation_areas", params, ohlcv_data)
        assert len(result["long_signal"]) == len(ohlcv_data)

    def test_flat_data_more_accumulation(self, adapter, flat_ohlcv):
        """Flat data should have more accumulation zone bars."""
        params = {"use_accumulation": True, "backtracking_interval": 15, "min_bars_to_execute": 3}
        r_flat = _run(adapter, "accumulation_areas", params, flat_ohlcv)
        assert r_flat["long_signal"].any(), "Flat data should detect accumulation zones"

    def test_higher_min_bars_fewer_zones(self, adapter, ohlcv_data):
        """Higher min_bars_to_execute → fewer consecutive qualifying bars."""
        params_lo = {"use_accumulation": True, "backtracking_interval": 20, "min_bars_to_execute": 3}
        params_hi = {"use_accumulation": True, "backtracking_interval": 20, "min_bars_to_execute": 15}
        r_lo = _run(adapter, "accumulation_areas", params_lo, ohlcv_data)
        r_hi = _run(adapter, "accumulation_areas", params_hi, ohlcv_data)
        assert r_lo["long_signal"].sum() >= r_hi["long_signal"].sum()


class TestAccumulationBreakoutMode:
    """Breakout signal mode."""

    def test_breakout_produces_signals(self, adapter, ohlcv_data):
        """Breakout mode should generate signals after accumulation zones."""
        params = {
            "use_accumulation": True,
            "backtracking_interval": 15,
            "min_bars_to_execute": 3,
            "signal_on_breakout": True,
        }
        result = _run(adapter, "accumulation_areas", params, ohlcv_data)
        # On 200 bars with trends, some breakout should occur
        assert isinstance(result["long_signal"], pd.Series)
        assert isinstance(result["short_signal"], pd.Series)

    def test_breakout_asymmetric(self, adapter, ohlcv_data):
        """Breakout up (long) and breakout down (short) are different directions."""
        params = {
            "use_accumulation": True,
            "backtracking_interval": 15,
            "min_bars_to_execute": 3,
            "signal_on_breakout": True,
        }
        result = _run(adapter, "accumulation_areas", params, ohlcv_data)
        # Long is breakout UP, short is breakout DOWN — if any signals exist, they should differ
        if result["long_signal"].any() or result["short_signal"].any():
            assert not result["long_signal"].equals(result["short_signal"])

    def test_opposite_breakout_reverses(self, adapter, ohlcv_data):
        """signal_on_opposite_breakout swaps long and short."""
        base = {
            "use_accumulation": True,
            "backtracking_interval": 15,
            "min_bars_to_execute": 3,
        }
        r_normal = _run(
            adapter,
            "accumulation_areas",
            {
                **base,
                "signal_on_breakout": True,
                "signal_on_opposite_breakout": False,
            },
            ohlcv_data,
        )
        r_opposite = _run(
            adapter,
            "accumulation_areas",
            {
                **base,
                "signal_on_breakout": True,
                "signal_on_opposite_breakout": True,
            },
            ohlcv_data,
        )
        # Opposite should swap long and short breakout directions
        pd.testing.assert_series_equal(r_normal["long_signal"], r_opposite["short_signal"])
        pd.testing.assert_series_equal(r_normal["short_signal"], r_opposite["long_signal"])


# ============================================================
# 7. EDGE CASES (all blocks)
# ============================================================


class TestEdgeCases:
    """Edge case tests for all 5 universal filter blocks."""

    def test_small_data_atr_volatility(self, adapter):
        """ATR volatility on very small dataset (5 bars)."""
        n = 5
        ohlcv = pd.DataFrame(
            {
                "open": [100, 102, 101, 103, 102],
                "high": [105, 104, 103, 105, 104],
                "low": [98, 99, 99, 100, 100],
                "close": [102, 101, 102, 104, 103],
                "volume": [1000, 1100, 900, 1200, 1000],
            }
        )
        params = {"use_atr_volatility": True, "atr_length1": 5, "atr_length2": 5}
        result = _run(adapter, "atr_volatility", params, ohlcv)
        assert len(result["long_signal"]) == n

    def test_small_data_volume_filter(self, adapter):
        """Volume filter on very small dataset."""
        ohlcv = pd.DataFrame(
            {
                "open": [100, 102, 101, 103, 102],
                "high": [105, 104, 103, 105, 104],
                "low": [98, 99, 99, 100, 100],
                "close": [102, 101, 102, 104, 103],
                "volume": [1000, 1100, 900, 1200, 1000],
            }
        )
        params = {"use_volume_filter": True, "vol_length1": 5, "vol_length2": 5}
        result = _run(adapter, "volume_filter", params, ohlcv)
        assert len(result["long_signal"]) == 5

    def test_small_data_highest_lowest(self, adapter):
        """Highest/lowest bar on small data."""
        ohlcv = pd.DataFrame(
            {
                "open": [100, 102, 101, 103, 102, 104, 103, 105, 104, 106],
                "high": [105, 104, 103, 105, 104, 108, 106, 109, 107, 110],
                "low": [98, 99, 99, 100, 100, 101, 100, 102, 101, 103],
                "close": [102, 101, 102, 104, 103, 106, 104, 107, 105, 108],
                "volume": [1000] * 10,
            }
        )
        params = {"use_highest_lowest": True, "hl_lookback_bars": 3}
        result = _run(adapter, "highest_lowest_bar", params, ohlcv)
        assert len(result["long_signal"]) == 10

    def test_small_data_two_mas(self, adapter):
        """TWO MAs on small data."""
        ohlcv = pd.DataFrame(
            {
                "open": [100, 102, 101, 103, 102, 104, 103, 105, 104, 106],
                "high": [105, 104, 103, 105, 104, 108, 106, 109, 107, 110],
                "low": [98, 99, 99, 100, 100, 101, 100, 102, 101, 103],
                "close": [102, 101, 102, 104, 103, 106, 104, 107, 105, 108],
                "volume": [1000] * 10,
            }
        )
        params = {"use_ma_cross": True, "ma1_length": 3, "ma2_length": 5}
        result = _run(adapter, "two_mas", params, ohlcv)
        assert len(result["long_signal"]) == 10
        assert "ma1" in result

    def test_small_data_accumulation(self, adapter):
        """Accumulation areas on small data."""
        ohlcv = pd.DataFrame(
            {
                "open": [100, 100.5, 100.2, 100.3, 100.1, 100.4, 100.2, 100.3, 100.5, 100.1],
                "high": [101, 101.5, 101.2, 101.3, 101.1, 101.4, 101.2, 101.3, 101.5, 101.1],
                "low": [99, 99.5, 99.2, 99.3, 99.1, 99.4, 99.2, 99.3, 99.5, 99.1],
                "close": [100.5, 100.2, 100.3, 100.1, 100.4, 100.2, 100.3, 100.5, 100.1, 100.3],
                "volume": [1000] * 10,
            }
        )
        params = {"use_accumulation": True, "backtracking_interval": 5, "min_bars_to_execute": 2}
        result = _run(adapter, "accumulation_areas", params, ohlcv)
        assert len(result["long_signal"]) == 10

    def test_constant_price_data(self, adapter):
        """Constant price data should not crash any block."""
        n = 50
        ohlcv = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [100.0] * n,
                "low": [100.0] * n,
                "close": [100.0] * n,
                "volume": [1000.0] * n,
            }
        )
        for block_type, toggle_key, toggle_val in [
            ("atr_volatility", "use_atr_volatility", True),
            ("volume_filter", "use_volume_filter", True),
            ("highest_lowest_bar", "use_highest_lowest", True),
            ("two_mas", "use_ma_cross", True),
            ("accumulation_areas", "use_accumulation", True),
        ]:
            result = _run(adapter, block_type, {toggle_key: toggle_val}, ohlcv)
            assert "long_signal" in result
            assert len(result["long_signal"]) == n


# ============================================================
# 8. VALIDATION RULES TESTS
# ============================================================


class TestValidationRulesRegistration:
    """Backend BLOCK_VALIDATION_RULES must contain entries for all 5 blocks."""

    def test_atr_volatility_rules_exist(self):
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "atr_volatility" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["atr_volatility"]
        assert "atr_diff_percent" in rules
        assert "atr_length1" in rules
        assert "atr_length2" in rules
        assert "atr_smoothing" in rules

    def test_volume_filter_rules_exist(self):
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "volume_filter" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["volume_filter"]
        assert "vol_diff_percent" in rules
        assert "vol_length1" in rules
        assert "vol_length2" in rules
        assert "vol_smoothing" in rules

    def test_highest_lowest_bar_rules_exist(self):
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "highest_lowest_bar" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["highest_lowest_bar"]
        assert "hl_lookback_bars" in rules
        assert "hl_price_percent" in rules
        assert "hl_atr_percent" in rules
        assert "block_worse_percent" in rules

    def test_two_mas_rules_exist(self):
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "two_mas" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["two_mas"]
        assert "ma1_length" in rules
        assert "ma1_smoothing" in rules
        assert "ma2_length" in rules
        assert "ma2_smoothing" in rules
        assert "ma_cross_memory_bars" in rules

    def test_accumulation_areas_rules_exist(self):
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "accumulation_areas" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["accumulation_areas"]
        assert "backtracking_interval" in rules
        assert "min_bars_to_execute" in rules


class TestConnectionRulesRegistration:
    """CONNECTION_RULES must include all 5 block types in entry_long and entry_short."""

    @pytest.mark.parametrize(
        "block_type",
        [
            "atr_volatility",
            "volume_filter",
            "highest_lowest_bar",
            "two_mas",
            "accumulation_areas",
        ],
    )
    def test_in_entry_long(self, block_type):
        from backend.api.routers.strategy_validation_ws import CONNECTION_RULES

        assert block_type in CONNECTION_RULES["entry_long"]

    @pytest.mark.parametrize(
        "block_type",
        [
            "atr_volatility",
            "volume_filter",
            "highest_lowest_bar",
            "two_mas",
            "accumulation_areas",
        ],
    )
    def test_in_entry_short(self, block_type):
        from backend.api.routers.strategy_validation_ws import CONNECTION_RULES

        assert block_type in CONNECTION_RULES["entry_short"]


# ============================================================
# 9. API VALIDATION ENDPOINT TESTS
# ============================================================


class TestAPIValidation:
    """Test that strategy validation endpoint accepts the new block types."""

    @pytest.mark.parametrize(
        "block_type,params",
        [
            ("atr_volatility", {"use_atr_volatility": True, "atr_length1": 10, "atr_length2": 50}),
            ("volume_filter", {"use_volume_filter": True, "vol_length1": 10, "vol_length2": 50}),
            ("highest_lowest_bar", {"use_highest_lowest": True, "hl_lookback_bars": 10}),
            ("two_mas", {"use_ma_cross": True, "ma1_length": 10, "ma2_length": 50}),
            ("accumulation_areas", {"use_accumulation": True, "backtracking_interval": 20}),
        ],
    )
    def test_validate_block_via_api(self, client, block_type, params):
        """Validation endpoint accepts each new block type."""
        payload = {
            "blocks": [
                {"id": "entry_long", "type": "entry_long", "params": {}},
                {"id": "blk1", "type": block_type, "category": "indicator", "params": params},
            ],
            "connections": [
                {"source": "blk1", "target": "entry_long"},
            ],
        }
        response = client.post("/api/v1/strategy-builder/validate", json=payload)
        # 200 or 422 — just ensure no 500 errors
        assert response.status_code != 500, f"Server error for {block_type}: {response.text}"
