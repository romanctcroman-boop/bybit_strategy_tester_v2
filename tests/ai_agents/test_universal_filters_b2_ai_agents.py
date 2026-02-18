"""
AI Agent Knowledge Test: Universal Filters Batch 2
(Keltner/Bollinger Channel, RVI, MFI, CCI, Momentum)

Tests verify that AI agents correctly understand:

== KELTNER/BOLLINGER CHANNEL (filter) ==
- Block type: 'keltner_bollinger', category: 'indicator'
- Toggle: use_channel (bool, default false → passthrough: all True)
- Parameters: channel_timeframe (BYBIT_TF_OPTS), channel_mode (Rebound|Breackout),
  channel_type (Bollinger Bands|Keltner Channel),
  enter_conditions (Out-of-band closure|Wick out of band|Wick out of the band then close in|
                    Close out of the band then close in),
  keltner_length (0.1-100, default 14), keltner_mult (0.1-100, default 1.5),
  bb_length (0.1-100, default 20), bb_deviation (0.1-100, default 2)
- Returns: {long_signal, short_signal} — asymmetric (Rebound: lower→long, upper→short;
  Breakout: upper→long, lower→short)

== RVI - RELATIVE VOLATILITY INDEX (filter) ==
- Block type: 'rvi_filter', category: 'indicator'
- Parameters: rvi_length (int 1-100, default 10), rvi_timeframe,
  rvi_ma_type (WMA|RMA|SMA|EMA), rvi_ma_length (int 1-100, default 2)
- Long range: use_rvi_long_range (bool), rvi_long_more (1-100), rvi_long_less (1-100)
- Short range: use_rvi_short_range (bool), rvi_short_less (1-100), rvi_short_more (1-100)
- Returns: {long_signal, short_signal, rvi}

== MFI - MONEY FLOW INDEX (filter) ==
- Block type: 'mfi_filter', category: 'indicator'
- Parameters: mfi_length (int 1-100, default 14), mfi_timeframe,
  use_btcusdt_mfi (bool, config only)
- Long range: use_mfi_long_range (bool), mfi_long_more (1-100), mfi_long_less (1-100)
- Short range: use_mfi_short_range (bool), mfi_short_less (1-100), mfi_short_more (1-100)
- Returns: {long_signal, short_signal, mfi}

== CCI - COMMODITY CHANNEL INDEX (filter) ==
- Block type: 'cci_filter', category: 'indicator'
- Parameters: cci_length (int 1-100, default 14), cci_timeframe
- Long range: use_cci_long_range (bool), cci_long_more (-400..400), cci_long_less (-400..400)
- Short range: use_cci_short_range (bool), cci_short_less (-400..400), cci_short_more (-400..400)
- Returns: {long_signal, short_signal, cci}

== MOMENTUM (filter) ==
- Block type: 'momentum_filter', category: 'indicator'
- Parameters: momentum_length (int 1-100, default 14), momentum_timeframe,
  use_btcusdt_momentum (bool, config only),
  momentum_source (close|open|high|low|hl2|hlc3|ohlc4|hlcc4)
- Long range: use_momentum_long_range, momentum_long_more (-100..100), momentum_long_less
- Short range: use_momentum_short_range, momentum_short_less, momentum_short_more
- Returns: {long_signal, short_signal, momentum}

Architecture:
    - Frontend category: 'indicator' (blockLibrary.indicators)
    - _BLOCK_CATEGORY_MAP: all 5 -> "indicator"
    - Backend handler: _execute_indicator()
    - CONNECTION_RULES: all 5 in entry_long and entry_short

Run:
    py -3.14 -m pytest tests/ai_agents/test_universal_filters_b2_ai_agents.py -v
    py -3.14 -m pytest tests/ai_agents/test_universal_filters_b2_ai_agents.py -v -k "keltner"
    py -3.14 -m pytest tests/ai_agents/test_universal_filters_b2_ai_agents.py -v -k "rvi"
    py -3.14 -m pytest tests/ai_agents/test_universal_filters_b2_ai_agents.py -v -k "mfi"
    py -3.14 -m pytest tests/ai_agents/test_universal_filters_b2_ai_agents.py -v -k "cci"
    py -3.14 -m pytest tests/ai_agents/test_universal_filters_b2_ai_agents.py -v -k "momentum"
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
            trend[i] = 1000 - (i - 50) * 10  # downtrend
        elif i < 150:
            trend[i] = 500 + np.sin(i * 0.3) * 100  # choppy range
        else:
            trend[i] = 500 + (i - 150) * 15  # resumption

    noise = np.random.randn(n) * 80
    close = base_price + trend + noise
    high = close + np.abs(np.random.randn(n)) * 150
    low = close - np.abs(np.random.randn(n)) * 150
    open_price = np.roll(close, 1)
    open_price[0] = base_price
    volume = np.random.uniform(500, 20000, n)

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
    """All 5 universal filter block types (batch 2) are mapped to 'indicator'."""

    @pytest.mark.parametrize(
        "block_type",
        [
            "keltner_bollinger",
            "rvi_filter",
            "mfi_filter",
            "cci_filter",
            "momentum_filter",
        ],
    )
    def test_category_map_contains_block(self, block_type):
        """_BLOCK_CATEGORY_MAP must map '{block_type}' -> 'indicator'."""
        assert StrategyBuilderAdapter._BLOCK_CATEGORY_MAP.get(block_type) == "indicator"


# ============================================================
# 2. KELTNER/BOLLINGER CHANNEL TESTS
# ============================================================


class TestKeltnerBollingerPassthrough:
    """When use_channel=False (default), long/short are all True."""

    def test_passthrough_default_params(self, adapter, ohlcv_data):
        result = _run(adapter, "keltner_bollinger", {}, ohlcv_data)
        assert "long_signal" in result
        assert "short_signal" in result
        assert result["long_signal"].all()
        assert result["short_signal"].all()

    def test_passthrough_explicit_false(self, adapter, ohlcv_data):
        result = _run(adapter, "keltner_bollinger", {"use_channel": False}, ohlcv_data)
        assert result["long_signal"].all()
        assert result["short_signal"].all()


class TestKeltnerChannel:
    """Tests for Keltner Channel mode."""

    def test_keltner_active_returns_boolean(self, adapter, ohlcv_data):
        params = {"use_channel": True, "channel_type": "Keltner Channel", "keltner_length": 14, "keltner_mult": 1.5}
        result = _run(adapter, "keltner_bollinger", params, ohlcv_data)
        assert result["long_signal"].dtype == bool
        assert result["short_signal"].dtype == bool

    def test_keltner_series_length(self, adapter, ohlcv_data):
        params = {"use_channel": True, "channel_type": "Keltner Channel"}
        result = _run(adapter, "keltner_bollinger", params, ohlcv_data)
        assert len(result["long_signal"]) == len(ohlcv_data)
        assert len(result["short_signal"]) == len(ohlcv_data)

    def test_keltner_rebound_asymmetric(self, adapter, ohlcv_data):
        """Rebound mode: lower band → long, upper band → short — should differ."""
        params = {"use_channel": True, "channel_type": "Keltner Channel", "channel_mode": "Rebound"}
        result = _run(adapter, "keltner_bollinger", params, ohlcv_data)
        # In trending data, upper and lower touches differ
        if result["long_signal"].any() or result["short_signal"].any():
            assert not result["long_signal"].equals(result["short_signal"])

    def test_keltner_breakout_vs_rebound_differ(self, adapter, ohlcv_data):
        """Breakout and Rebound modes produce opposite long/short assignments."""
        base = {"use_channel": True, "channel_type": "Keltner Channel"}
        r_rebound = _run(adapter, "keltner_bollinger", {**base, "channel_mode": "Rebound"}, ohlcv_data)
        r_breakout = _run(adapter, "keltner_bollinger", {**base, "channel_mode": "Breackout"}, ohlcv_data)
        # Rebound long = Breakout short (lower band signal)
        pd.testing.assert_series_equal(r_rebound["long_signal"], r_breakout["short_signal"])
        pd.testing.assert_series_equal(r_rebound["short_signal"], r_breakout["long_signal"])


class TestBollingerBands:
    """Tests for Bollinger Bands mode."""

    def test_bollinger_active_returns_boolean(self, adapter, ohlcv_data):
        params = {"use_channel": True, "channel_type": "Bollinger Bands", "bb_length": 20, "bb_deviation": 2}
        result = _run(adapter, "keltner_bollinger", params, ohlcv_data)
        assert result["long_signal"].dtype == bool
        assert result["short_signal"].dtype == bool

    def test_bollinger_narrower_bands_more_signals(self, adapter, ohlcv_data):
        """Narrower bands (lower deviation) → more signals."""
        base = {"use_channel": True, "channel_type": "Bollinger Bands", "bb_length": 20}
        r_narrow = _run(adapter, "keltner_bollinger", {**base, "bb_deviation": 1.0}, ohlcv_data)
        r_wide = _run(adapter, "keltner_bollinger", {**base, "bb_deviation": 3.0}, ohlcv_data)
        narrow_count = r_narrow["long_signal"].sum() + r_narrow["short_signal"].sum()
        wide_count = r_wide["long_signal"].sum() + r_wide["short_signal"].sum()
        assert narrow_count >= wide_count

    def test_bollinger_vs_keltner_differ(self, adapter, ohlcv_data):
        """Bollinger and Keltner channels produce different results."""
        base = {"use_channel": True, "channel_mode": "Rebound"}
        r_bb = _run(adapter, "keltner_bollinger", {**base, "channel_type": "Bollinger Bands"}, ohlcv_data)
        r_kc = _run(adapter, "keltner_bollinger", {**base, "channel_type": "Keltner Channel"}, ohlcv_data)
        # Different calculation methods → different signals (unless all False)
        assert (not r_bb["long_signal"].equals(r_kc["long_signal"])) or (
            not r_bb["long_signal"].any() and not r_kc["long_signal"].any()
        )


class TestChannelEnterConditions:
    """Tests for different enter conditions."""

    @pytest.mark.parametrize(
        "cond",
        [
            "Out-of-band closure",
            "Wick out of band",
            "Wick out of the band then close in",
            "Close out of the band then close in",
        ],
    )
    def test_enter_condition_runs_without_error(self, adapter, ohlcv_data, cond):
        """All enter conditions must execute without error."""
        params = {"use_channel": True, "channel_type": "Keltner Channel", "enter_conditions": cond}
        result = _run(adapter, "keltner_bollinger", params, ohlcv_data)
        assert "long_signal" in result
        assert "short_signal" in result

    def test_wick_produces_more_than_close(self, adapter, ohlcv_data):
        """Wick out of band should produce >= signals than close out of band."""
        base = {"use_channel": True, "channel_type": "Keltner Channel", "channel_mode": "Rebound"}
        r_wick = _run(adapter, "keltner_bollinger", {**base, "enter_conditions": "Wick out of band"}, ohlcv_data)
        r_close = _run(adapter, "keltner_bollinger", {**base, "enter_conditions": "Out-of-band closure"}, ohlcv_data)
        wick_total = r_wick["long_signal"].sum() + r_wick["short_signal"].sum()
        close_total = r_close["long_signal"].sum() + r_close["short_signal"].sum()
        assert wick_total >= close_total


# ============================================================
# 3. RVI FILTER TESTS
# ============================================================


class TestRVIFilterPassthrough:
    """When no range toggles are enabled, long/short are all True."""

    def test_passthrough_default(self, adapter, ohlcv_data):
        result = _run(adapter, "rvi_filter", {}, ohlcv_data)
        assert result["long_signal"].all()
        assert result["short_signal"].all()

    def test_returns_rvi_series(self, adapter, ohlcv_data):
        """Must return rvi series in output."""
        result = _run(adapter, "rvi_filter", {}, ohlcv_data)
        assert "rvi" in result
        assert isinstance(result["rvi"], pd.Series)
        assert len(result["rvi"]) == len(ohlcv_data)


class TestRVILongRange:
    """Tests for RVI Long Range filter."""

    def test_long_range_filters_signals(self, adapter, ohlcv_data):
        params = {"use_rvi_long_range": True, "rvi_long_more": 30, "rvi_long_less": 70}
        result = _run(adapter, "rvi_filter", params, ohlcv_data)
        # With a range filter, not all bars should pass
        assert not result["long_signal"].all()

    def test_long_range_narrows_signals(self, adapter, ohlcv_data):
        """Narrower range → fewer signals."""
        r_wide = _run(
            adapter,
            "rvi_filter",
            {
                "use_rvi_long_range": True,
                "rvi_long_more": 1,
                "rvi_long_less": 99,
            },
            ohlcv_data,
        )
        r_narrow = _run(
            adapter,
            "rvi_filter",
            {
                "use_rvi_long_range": True,
                "rvi_long_more": 40,
                "rvi_long_less": 60,
            },
            ohlcv_data,
        )
        assert r_wide["long_signal"].sum() >= r_narrow["long_signal"].sum()

    def test_long_range_only_affects_long(self, adapter, ohlcv_data):
        """Long range filter should only affect long signal, not short."""
        params = {"use_rvi_long_range": True, "rvi_long_more": 30, "rvi_long_less": 70}
        result = _run(adapter, "rvi_filter", params, ohlcv_data)
        assert result["short_signal"].all()


class TestRVIShortRange:
    """Tests for RVI Short Range filter."""

    def test_short_range_filters_signals(self, adapter, ohlcv_data):
        params = {"use_rvi_short_range": True, "rvi_short_less": 70, "rvi_short_more": 30}
        result = _run(adapter, "rvi_filter", params, ohlcv_data)
        assert not result["short_signal"].all()

    def test_short_range_only_affects_short(self, adapter, ohlcv_data):
        """Short range filter should only affect short signal, not long."""
        params = {"use_rvi_short_range": True, "rvi_short_less": 70, "rvi_short_more": 30}
        result = _run(adapter, "rvi_filter", params, ohlcv_data)
        assert result["long_signal"].all()

    def test_both_ranges_combined(self, adapter, ohlcv_data):
        """Both ranges can be used together."""
        params = {
            "use_rvi_long_range": True,
            "rvi_long_more": 30,
            "rvi_long_less": 70,
            "use_rvi_short_range": True,
            "rvi_short_less": 70,
            "rvi_short_more": 30,
        }
        result = _run(adapter, "rvi_filter", params, ohlcv_data)
        assert not result["long_signal"].all()
        assert not result["short_signal"].all()

    @pytest.mark.parametrize("ma_type", ["WMA", "RMA", "SMA", "EMA"])
    def test_rvi_ma_types_run_without_error(self, adapter, ohlcv_data, ma_type):
        """All 4 MA types run without error."""
        params = {"rvi_length": 10, "rvi_ma_type": ma_type, "rvi_ma_length": 5}
        result = _run(adapter, "rvi_filter", params, ohlcv_data)
        assert "rvi" in result


# ============================================================
# 4. MFI FILTER TESTS
# ============================================================


class TestMFIFilterPassthrough:
    """When no range toggles are enabled, long/short are all True."""

    def test_passthrough_default(self, adapter, ohlcv_data):
        result = _run(adapter, "mfi_filter", {}, ohlcv_data)
        assert result["long_signal"].all()
        assert result["short_signal"].all()

    def test_returns_mfi_series(self, adapter, ohlcv_data):
        result = _run(adapter, "mfi_filter", {}, ohlcv_data)
        assert "mfi" in result
        assert isinstance(result["mfi"], pd.Series)
        assert len(result["mfi"]) == len(ohlcv_data)


class TestMFILongRange:
    """Tests for MFI Long Range filter."""

    def test_long_range_filters_signals(self, adapter, ohlcv_data):
        params = {"use_mfi_long_range": True, "mfi_long_more": 20, "mfi_long_less": 80}
        result = _run(adapter, "mfi_filter", params, ohlcv_data)
        assert not result["long_signal"].all()

    def test_long_range_only_affects_long(self, adapter, ohlcv_data):
        params = {"use_mfi_long_range": True, "mfi_long_more": 20, "mfi_long_less": 80}
        result = _run(adapter, "mfi_filter", params, ohlcv_data)
        assert result["short_signal"].all()


class TestMFIShortRange:
    """Tests for MFI Short Range filter."""

    def test_short_range_filters_signals(self, adapter, ohlcv_data):
        params = {"use_mfi_short_range": True, "mfi_short_less": 80, "mfi_short_more": 20}
        result = _run(adapter, "mfi_filter", params, ohlcv_data)
        assert not result["short_signal"].all()

    def test_short_range_only_affects_short(self, adapter, ohlcv_data):
        params = {"use_mfi_short_range": True, "mfi_short_less": 80, "mfi_short_more": 20}
        result = _run(adapter, "mfi_filter", params, ohlcv_data)
        assert result["long_signal"].all()

    def test_both_ranges_combined(self, adapter, ohlcv_data):
        params = {
            "use_mfi_long_range": True,
            "mfi_long_more": 20,
            "mfi_long_less": 80,
            "use_mfi_short_range": True,
            "mfi_short_less": 80,
            "mfi_short_more": 20,
        }
        result = _run(adapter, "mfi_filter", params, ohlcv_data)
        assert not result["long_signal"].all()
        assert not result["short_signal"].all()

    def test_different_periods_differ(self, adapter, ohlcv_data):
        """Different MFI periods produce different indicator values."""
        r10 = _run(adapter, "mfi_filter", {"mfi_length": 10}, ohlcv_data)
        r30 = _run(adapter, "mfi_filter", {"mfi_length": 30}, ohlcv_data)
        assert not r10["mfi"].equals(r30["mfi"])


# ============================================================
# 5. CCI FILTER TESTS
# ============================================================


class TestCCIFilterPassthrough:
    """When no range toggles are enabled, long/short are all True."""

    def test_passthrough_default(self, adapter, ohlcv_data):
        result = _run(adapter, "cci_filter", {}, ohlcv_data)
        assert result["long_signal"].all()
        assert result["short_signal"].all()

    def test_returns_cci_series(self, adapter, ohlcv_data):
        result = _run(adapter, "cci_filter", {}, ohlcv_data)
        assert "cci" in result
        assert isinstance(result["cci"], pd.Series)
        assert len(result["cci"]) == len(ohlcv_data)


class TestCCILongRange:
    """Tests for CCI Long Range filter."""

    def test_long_range_filters_signals(self, adapter, ohlcv_data):
        params = {"use_cci_long_range": True, "cci_long_more": -100, "cci_long_less": 100}
        result = _run(adapter, "cci_filter", params, ohlcv_data)
        # CCI oscillates widely, narrow range should filter
        assert not result["long_signal"].all()

    def test_long_range_only_affects_long(self, adapter, ohlcv_data):
        params = {"use_cci_long_range": True, "cci_long_more": -100, "cci_long_less": 100}
        result = _run(adapter, "cci_filter", params, ohlcv_data)
        assert result["short_signal"].all()

    def test_wider_range_more_signals(self, adapter, ohlcv_data):
        r_narrow = _run(
            adapter,
            "cci_filter",
            {
                "use_cci_long_range": True,
                "cci_long_more": -50,
                "cci_long_less": 50,
            },
            ohlcv_data,
        )
        r_wide = _run(
            adapter,
            "cci_filter",
            {
                "use_cci_long_range": True,
                "cci_long_more": -400,
                "cci_long_less": 400,
            },
            ohlcv_data,
        )
        assert r_wide["long_signal"].sum() >= r_narrow["long_signal"].sum()


class TestCCIShortRange:
    """Tests for CCI Short Range filter."""

    def test_short_range_filters_signals(self, adapter, ohlcv_data):
        params = {"use_cci_short_range": True, "cci_short_less": 100, "cci_short_more": -100}
        result = _run(adapter, "cci_filter", params, ohlcv_data)
        assert not result["short_signal"].all()

    def test_short_range_only_affects_short(self, adapter, ohlcv_data):
        params = {"use_cci_short_range": True, "cci_short_less": 100, "cci_short_more": -100}
        result = _run(adapter, "cci_filter", params, ohlcv_data)
        assert result["long_signal"].all()

    def test_both_ranges_combined(self, adapter, ohlcv_data):
        params = {
            "use_cci_long_range": True,
            "cci_long_more": -100,
            "cci_long_less": 100,
            "use_cci_short_range": True,
            "cci_short_less": 100,
            "cci_short_more": -100,
        }
        result = _run(adapter, "cci_filter", params, ohlcv_data)
        assert not result["long_signal"].all()
        assert not result["short_signal"].all()


# ============================================================
# 6. MOMENTUM FILTER TESTS
# ============================================================


class TestMomentumFilterPassthrough:
    """When no range toggles are enabled, long/short are all True."""

    def test_passthrough_default(self, adapter, ohlcv_data):
        result = _run(adapter, "momentum_filter", {}, ohlcv_data)
        assert result["long_signal"].all()
        assert result["short_signal"].all()

    def test_returns_momentum_series(self, adapter, ohlcv_data):
        result = _run(adapter, "momentum_filter", {}, ohlcv_data)
        assert "momentum" in result
        assert isinstance(result["momentum"], pd.Series)
        assert len(result["momentum"]) == len(ohlcv_data)


class TestMomentumLongRange:
    """Tests for Momentum Long Range filter."""

    def test_long_range_filters_signals(self, adapter, ohlcv_data):
        params = {"use_momentum_long_range": True, "momentum_long_more": -50, "momentum_long_less": 50}
        result = _run(adapter, "momentum_filter", params, ohlcv_data)
        # With range restriction, not all bars pass
        assert not result["long_signal"].all() or result["long_signal"].isna().any()

    def test_long_range_only_affects_long(self, adapter, ohlcv_data):
        params = {"use_momentum_long_range": True, "momentum_long_more": -50, "momentum_long_less": 50}
        result = _run(adapter, "momentum_filter", params, ohlcv_data)
        assert result["short_signal"].all()


class TestMomentumShortRange:
    """Tests for Momentum Short Range filter."""

    def test_short_range_filters_signals(self, adapter, ohlcv_data):
        params = {"use_momentum_short_range": True, "momentum_short_less": 50, "momentum_short_more": -50}
        result = _run(adapter, "momentum_filter", params, ohlcv_data)
        assert not result["short_signal"].all() or result["short_signal"].isna().any()

    def test_short_range_only_affects_short(self, adapter, ohlcv_data):
        params = {"use_momentum_short_range": True, "momentum_short_less": 50, "momentum_short_more": -50}
        result = _run(adapter, "momentum_filter", params, ohlcv_data)
        assert result["long_signal"].all()

    def test_both_ranges_combined(self, adapter, ohlcv_data):
        params = {
            "use_momentum_long_range": True,
            "momentum_long_more": -50,
            "momentum_long_less": 50,
            "use_momentum_short_range": True,
            "momentum_short_less": 50,
            "momentum_short_more": -50,
        }
        result = _run(adapter, "momentum_filter", params, ohlcv_data)
        # At least one direction should be filtered
        assert not result["long_signal"].all() or not result["short_signal"].all()

    @pytest.mark.parametrize("source", ["close", "open", "high", "low"])
    def test_momentum_source_options(self, adapter, ohlcv_data, source):
        """All source options run without error."""
        params = {"momentum_source": source, "momentum_length": 10}
        result = _run(adapter, "momentum_filter", params, ohlcv_data)
        assert "momentum" in result

    def test_different_lengths_differ(self, adapter, ohlcv_data):
        """Different momentum periods produce different values."""
        r5 = _run(adapter, "momentum_filter", {"momentum_length": 5}, ohlcv_data)
        r20 = _run(adapter, "momentum_filter", {"momentum_length": 20}, ohlcv_data)
        assert not r5["momentum"].equals(r20["momentum"])


# ============================================================
# 7. EDGE CASES (all blocks)
# ============================================================


class TestEdgeCases:
    """Edge case tests for all 5 universal filter blocks (batch 2)."""

    def test_small_data_keltner(self, adapter):
        """Keltner on very small dataset."""
        ohlcv = pd.DataFrame(
            {
                "open": [100, 102, 101, 103, 102, 104, 103, 105, 104, 106],
                "high": [105, 104, 103, 106, 105, 108, 107, 110, 108, 112],
                "low": [98, 99, 99, 100, 99, 101, 100, 102, 101, 103],
                "close": [102, 101, 102, 104, 103, 106, 105, 108, 106, 110],
                "volume": [1000] * 10,
            }
        )
        params = {"use_channel": True, "channel_type": "Keltner Channel", "keltner_length": 5}
        result = _run(adapter, "keltner_bollinger", params, ohlcv)
        assert len(result["long_signal"]) == 10

    def test_small_data_rvi(self, adapter):
        """RVI on small data."""
        ohlcv = pd.DataFrame(
            {
                "open": [
                    100,
                    102,
                    101,
                    103,
                    102,
                    104,
                    103,
                    105,
                    104,
                    106,
                    108,
                    107,
                    109,
                    108,
                    110,
                    112,
                    111,
                    113,
                    112,
                    114,
                ],
                "high": [
                    105,
                    104,
                    103,
                    105,
                    104,
                    108,
                    106,
                    109,
                    107,
                    110,
                    112,
                    111,
                    113,
                    112,
                    114,
                    116,
                    115,
                    117,
                    116,
                    118,
                ],
                "low": [
                    98,
                    99,
                    99,
                    100,
                    100,
                    101,
                    100,
                    102,
                    101,
                    103,
                    105,
                    104,
                    106,
                    105,
                    107,
                    109,
                    108,
                    110,
                    109,
                    111,
                ],
                "close": [
                    102,
                    101,
                    102,
                    104,
                    103,
                    106,
                    104,
                    107,
                    105,
                    108,
                    110,
                    109,
                    111,
                    110,
                    112,
                    114,
                    113,
                    115,
                    114,
                    116,
                ],
                "volume": [1000] * 20,
            }
        )
        params = {"rvi_length": 5, "rvi_ma_type": "SMA", "rvi_ma_length": 3}
        result = _run(adapter, "rvi_filter", params, ohlcv)
        assert len(result["long_signal"]) == 20
        assert "rvi" in result

    def test_small_data_mfi(self, adapter):
        """MFI on small data."""
        ohlcv = pd.DataFrame(
            {
                "open": [
                    100,
                    102,
                    101,
                    103,
                    102,
                    104,
                    103,
                    105,
                    104,
                    106,
                    108,
                    107,
                    109,
                    108,
                    110,
                    112,
                    111,
                    113,
                    112,
                    114,
                ],
                "high": [
                    105,
                    104,
                    103,
                    105,
                    104,
                    108,
                    106,
                    109,
                    107,
                    110,
                    112,
                    111,
                    113,
                    112,
                    114,
                    116,
                    115,
                    117,
                    116,
                    118,
                ],
                "low": [
                    98,
                    99,
                    99,
                    100,
                    100,
                    101,
                    100,
                    102,
                    101,
                    103,
                    105,
                    104,
                    106,
                    105,
                    107,
                    109,
                    108,
                    110,
                    109,
                    111,
                ],
                "close": [
                    102,
                    101,
                    102,
                    104,
                    103,
                    106,
                    104,
                    107,
                    105,
                    108,
                    110,
                    109,
                    111,
                    110,
                    112,
                    114,
                    113,
                    115,
                    114,
                    116,
                ],
                "volume": [
                    1000,
                    1100,
                    900,
                    1200,
                    1000,
                    1300,
                    1100,
                    1400,
                    1200,
                    1500,
                    1000,
                    1100,
                    900,
                    1200,
                    1000,
                    1300,
                    1100,
                    1400,
                    1200,
                    1500,
                ],
            }
        )
        result = _run(adapter, "mfi_filter", {"mfi_length": 5}, ohlcv)
        assert len(result["long_signal"]) == 20

    def test_small_data_cci(self, adapter):
        """CCI on small data."""
        ohlcv = pd.DataFrame(
            {
                "open": [
                    100,
                    102,
                    101,
                    103,
                    102,
                    104,
                    103,
                    105,
                    104,
                    106,
                    108,
                    107,
                    109,
                    108,
                    110,
                    112,
                    111,
                    113,
                    112,
                    114,
                ],
                "high": [
                    105,
                    104,
                    103,
                    105,
                    104,
                    108,
                    106,
                    109,
                    107,
                    110,
                    112,
                    111,
                    113,
                    112,
                    114,
                    116,
                    115,
                    117,
                    116,
                    118,
                ],
                "low": [
                    98,
                    99,
                    99,
                    100,
                    100,
                    101,
                    100,
                    102,
                    101,
                    103,
                    105,
                    104,
                    106,
                    105,
                    107,
                    109,
                    108,
                    110,
                    109,
                    111,
                ],
                "close": [
                    102,
                    101,
                    102,
                    104,
                    103,
                    106,
                    104,
                    107,
                    105,
                    108,
                    110,
                    109,
                    111,
                    110,
                    112,
                    114,
                    113,
                    115,
                    114,
                    116,
                ],
                "volume": [1000] * 20,
            }
        )
        result = _run(adapter, "cci_filter", {"cci_length": 5}, ohlcv)
        assert len(result["long_signal"]) == 20

    def test_small_data_momentum(self, adapter):
        """Momentum on small data."""
        ohlcv = pd.DataFrame(
            {
                "open": [100, 102, 101, 103, 102],
                "high": [105, 104, 103, 105, 104],
                "low": [98, 99, 99, 100, 100],
                "close": [102, 101, 102, 104, 103],
                "volume": [1000] * 5,
            }
        )
        result = _run(adapter, "momentum_filter", {"momentum_length": 2}, ohlcv)
        assert len(result["long_signal"]) == 5
        assert "momentum" in result

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
            ("keltner_bollinger", "use_channel", True),
            ("rvi_filter", "use_rvi_long_range", True),
            ("mfi_filter", "use_mfi_long_range", True),
            ("cci_filter", "use_cci_long_range", True),
            ("momentum_filter", "use_momentum_long_range", True),
        ]:
            result = _run(adapter, block_type, {toggle_key: toggle_val}, ohlcv)
            assert "long_signal" in result
            assert len(result["long_signal"]) == n


# ============================================================
# 8. VALIDATION RULES TESTS
# ============================================================


class TestValidationRulesRegistration:
    """Backend BLOCK_VALIDATION_RULES must contain entries for all 5 blocks."""

    def test_keltner_bollinger_rules_exist(self):
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "keltner_bollinger" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["keltner_bollinger"]
        assert "keltner_length" in rules
        assert "keltner_mult" in rules
        assert "bb_length" in rules
        assert "bb_deviation" in rules
        assert "channel_mode" in rules
        assert "channel_type" in rules
        assert "enter_conditions" in rules

    def test_rvi_filter_rules_exist(self):
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "rvi_filter" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["rvi_filter"]
        assert "rvi_length" in rules
        assert "rvi_ma_type" in rules
        assert "rvi_ma_length" in rules
        assert "rvi_long_more" in rules
        assert "rvi_long_less" in rules
        assert "rvi_short_less" in rules
        assert "rvi_short_more" in rules

    def test_mfi_filter_rules_exist(self):
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "mfi_filter" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["mfi_filter"]
        assert "mfi_length" in rules
        assert "mfi_long_more" in rules
        assert "mfi_short_less" in rules

    def test_cci_filter_rules_exist(self):
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "cci_filter" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["cci_filter"]
        assert "cci_length" in rules
        assert "cci_long_more" in rules
        assert "cci_short_less" in rules

    def test_momentum_filter_rules_exist(self):
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "momentum_filter" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["momentum_filter"]
        assert "momentum_length" in rules
        assert "momentum_source" in rules
        assert "momentum_long_more" in rules
        assert "momentum_short_less" in rules


class TestConnectionRulesRegistration:
    """CONNECTION_RULES must include all 5 block types in entry_long and entry_short."""

    @pytest.mark.parametrize(
        "block_type",
        [
            "keltner_bollinger",
            "rvi_filter",
            "mfi_filter",
            "cci_filter",
            "momentum_filter",
        ],
    )
    def test_in_entry_long(self, block_type):
        from backend.api.routers.strategy_validation_ws import CONNECTION_RULES

        assert block_type in CONNECTION_RULES["entry_long"]

    @pytest.mark.parametrize(
        "block_type",
        [
            "keltner_bollinger",
            "rvi_filter",
            "mfi_filter",
            "cci_filter",
            "momentum_filter",
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
            ("keltner_bollinger", {"use_channel": True, "channel_type": "Keltner Channel"}),
            ("rvi_filter", {"use_rvi_long_range": True, "rvi_long_more": 30, "rvi_long_less": 70}),
            ("mfi_filter", {"use_mfi_long_range": True, "mfi_long_more": 20, "mfi_long_less": 80}),
            ("cci_filter", {"use_cci_long_range": True, "cci_long_more": -100, "cci_long_less": 100}),
            ("momentum_filter", {"use_momentum_long_range": True, "momentum_long_more": -50, "momentum_long_less": 50}),
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
        assert response.status_code != 500, f"Server error for {block_type}: {response.text}"
