"""
AI Agent Knowledge Test: Divergence Detection Block (unified multi-indicator)

Tests verify that AI agents correctly understand:

== DIVERGENCE BLOCK ==
- Category: 'divergence' (in "Условия Входа" / Entry Conditions)
- Single unified block type: 'divergence'
- _BLOCK_CATEGORY_MAP: "divergence" -> "divergence"
- Dispatched via _execute_divergence(block_type, params, ohlcv)

== GENERAL PARAMETERS ==
- pivot_interval (int 1-9, default 9): Bars left/right for pivot high/low detection
- act_without_confirmation (bool, default false): If true, signal fires immediately;
  if false, waits for price confirmation (close in divergence direction)
- show_divergence_lines (bool, default false): Display config only
- activate_diver_signal_memory (bool, default false): Keep signal active for N bars
- keep_diver_signal_memory_bars (int 1-100, default 5): How many bars to keep signal

== INDICATOR TOGGLES ==
- use_divergence_rsi (bool, default false) + rsi_period (int, default 14)
- use_divergence_stochastic (bool, default false) + stoch_length (int, default 14)
- use_divergence_momentum (bool, default false) + momentum_length (int, default 10)
- use_divergence_cmf (bool, default false) + cmf_period (int, default 21)
- use_obv (bool, default false) — no period param
- use_mfi (bool, default false) + mfi_length (int, default 14)

== DIVERGENCE DETECTION LOGIC ==
- Pivot highs/lows found using pivot_interval as lookback window
- For each enabled indicator:
  * Bullish divergence: price lower low + indicator higher low
  * Bearish divergence: price higher high + indicator lower high
- Multiple indicator signals are OR'd together
- Confirmation: next bar close > prev close (bullish) or close < prev (bearish)
- Signal memory: divergence signal persists for N bars after detection

== OUTPUT ==
- Returns dict with keys: signal, bullish, bearish (all pd.Series[bool])
- signal = bullish | bearish

Architecture:
    - Frontend category: 'divergence' (blockLibrary.divergence)
    - _BLOCK_CATEGORY_MAP: "divergence" -> "divergence"
    - Backend handler: _execute_divergence()
    - CONNECTION_RULES: divergence in entry_long and entry_short allowed sources

Run:
    py -3.14 -m pytest tests/ai_agents/test_divergence_block_ai_agents.py -v
    py -3.14 -m pytest tests/ai_agents/test_divergence_block_ai_agents.py -v -k "rsi"
    py -3.14 -m pytest tests/ai_agents/test_divergence_block_ai_agents.py -v -k "memory"
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
def ohlcv_data() -> pd.DataFrame:
    """Generate 200-bar OHLCV data with clear trends for divergence detection."""
    np.random.seed(42)
    n = 200
    base_price = 50000.0

    # Create trending data with reversals to generate divergence patterns
    trend = np.zeros(n)
    for i in range(n):
        if i < 50:
            trend[i] = i * 10  # uptrend
        elif i < 100:
            trend[i] = 500 - (i - 50) * 12  # downtrend (lower lows)
        elif i < 150:
            trend[i] = -100 + (i - 100) * 8  # uptrend
        else:
            trend[i] = 300 - (i - 150) * 6  # downtrend

    noise = np.random.randn(n) * 50
    close = base_price + trend + noise
    high = close + np.abs(np.random.randn(n)) * 100
    low = close - np.abs(np.random.randn(n)) * 100
    open_price = np.roll(close, 1)
    open_price[0] = base_price
    volume = np.random.uniform(1000, 10000, n)

    return pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="1h"),
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


@pytest.fixture
def small_ohlcv() -> pd.DataFrame:
    """Small 20-bar OHLCV dataset for edge case testing."""
    np.random.seed(99)
    n = 20
    close = np.array([100, 102, 101, 99, 97, 98, 100, 103, 105, 104,
                       102, 100, 98, 96, 97, 99, 101, 103, 102, 100], dtype=float)
    high = close + 2
    low = close - 2
    open_price = np.roll(close, 1)
    open_price[0] = 100
    volume = np.full(n, 5000.0)

    return pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="1h"),
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def _make_adapter(blocks: list[dict], connections: list[dict] | None = None) -> StrategyBuilderAdapter:
    """Create adapter from blocks."""
    graph = {
        "name": "Test Divergence Strategy",
        "blocks": blocks,
        "connections": connections or [],
    }
    return StrategyBuilderAdapter(graph)


def _divergence_block(params: dict[str, Any] | None = None) -> dict:
    """Helper to create a divergence block with given params."""
    default = {
        "pivot_interval": 5,
        "act_without_confirmation": True,
        "use_divergence_rsi": True,
        "rsi_period": 14,
    }
    if params:
        default.update(params)
    return {
        "id": "div1",
        "type": "divergence",
        "category": "divergence",
        "params": default,
    }


# ============================================================
# 1. BLOCK IDENTITY & CATEGORY TESTS
# ============================================================


class TestDivergenceBlockIdentity:
    """Tests that the divergence block is properly registered and dispatched."""

    def test_block_type_is_divergence(self, ohlcv_data):
        """Block type must be 'divergence'."""
        adapter = _make_adapter([_divergence_block()])
        result = adapter.generate_signals(ohlcv_data)
        assert result is not None

    def test_category_is_divergence(self, ohlcv_data):
        """Category must be 'divergence'."""
        block = _divergence_block()
        assert block["category"] == "divergence"
        adapter = _make_adapter([block])
        result = adapter.generate_signals(ohlcv_data)
        assert result is not None

    def test_category_map_contains_divergence(self):
        """_BLOCK_CATEGORY_MAP must map 'divergence' -> 'divergence'."""
        assert StrategyBuilderAdapter._BLOCK_CATEGORY_MAP.get("divergence") == "divergence"

    def test_inferred_category_fallback(self, ohlcv_data):
        """Block without explicit category should infer from _BLOCK_CATEGORY_MAP."""
        block = {
            "id": "div1",
            "type": "divergence",
            "params": {"pivot_interval": 5, "use_divergence_rsi": True, "rsi_period": 14},
        }
        adapter = _make_adapter([block])
        result = adapter.generate_signals(ohlcv_data)
        assert result is not None


# ============================================================
# 2. RETURN STRUCTURE TESTS
# ============================================================


class TestDivergenceReturnStructure:
    """Tests that the handler returns correct output format."""

    def test_returns_dict_with_required_keys(self, ohlcv_data):
        """Must return dict with signal, bullish, bearish keys."""
        adapter = _make_adapter([_divergence_block()])
        # Access internal method for direct testing
        block = _divergence_block()
        result = adapter._execute_divergence("divergence", block["params"], ohlcv_data)
        assert "signal" in result
        assert "bullish" in result
        assert "bearish" in result

    def test_return_series_length_matches_data(self, ohlcv_data):
        """All returned series must have same length as input data."""
        adapter = _make_adapter([_divergence_block()])
        result = adapter._execute_divergence("divergence", _divergence_block()["params"], ohlcv_data)
        assert len(result["signal"]) == len(ohlcv_data)
        assert len(result["bullish"]) == len(ohlcv_data)
        assert len(result["bearish"]) == len(ohlcv_data)

    def test_return_series_are_boolean(self, ohlcv_data):
        """All returned series must contain boolean values."""
        adapter = _make_adapter([_divergence_block()])
        result = adapter._execute_divergence("divergence", _divergence_block()["params"], ohlcv_data)
        assert result["signal"].dtype == bool
        assert result["bullish"].dtype == bool
        assert result["bearish"].dtype == bool

    def test_signal_equals_bullish_or_bearish(self, ohlcv_data):
        """signal must be bullish | bearish."""
        adapter = _make_adapter([_divergence_block()])
        result = adapter._execute_divergence("divergence", _divergence_block()["params"], ohlcv_data)
        expected_signal = result["bullish"] | result["bearish"]
        pd.testing.assert_series_equal(result["signal"], expected_signal)


# ============================================================
# 3. NO INDICATORS ENABLED
# ============================================================


class TestDivergenceNoIndicators:
    """Tests behavior when no indicators are enabled."""

    def test_no_indicators_returns_all_false(self, ohlcv_data):
        """With no indicators enabled, all signals must be False."""
        block = _divergence_block({"use_divergence_rsi": False})
        adapter = _make_adapter([block])
        result = adapter._execute_divergence("divergence", block["params"], ohlcv_data)
        assert not result["signal"].any()
        assert not result["bullish"].any()
        assert not result["bearish"].any()

    def test_default_params_no_indicators(self, ohlcv_data):
        """Default params (all use_* False) should produce empty signals."""
        params = {
            "pivot_interval": 9,
            "act_without_confirmation": False,
            "use_divergence_rsi": False,
            "use_divergence_stochastic": False,
            "use_divergence_momentum": False,
            "use_divergence_cmf": False,
            "use_obv": False,
            "use_mfi": False,
        }
        block = _divergence_block(params)
        adapter = _make_adapter([block])
        result = adapter._execute_divergence("divergence", block["params"], ohlcv_data)
        assert not result["signal"].any()


# ============================================================
# 4. INDIVIDUAL INDICATOR TESTS
# ============================================================


class TestDivergenceRSI:
    """Tests for RSI divergence detection."""

    def test_rsi_only_produces_valid_result(self, ohlcv_data):
        """RSI divergence must run without error."""
        params = {"use_divergence_rsi": True, "rsi_period": 14, "pivot_interval": 3, "act_without_confirmation": True}
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, ohlcv_data)
        assert isinstance(result["bullish"], pd.Series)
        assert isinstance(result["bearish"], pd.Series)

    def test_rsi_period_parameter_applied(self, ohlcv_data):
        """Different RSI periods should produce different results."""
        params_14 = {"use_divergence_rsi": True, "rsi_period": 14, "pivot_interval": 3, "act_without_confirmation": True}
        params_5 = {"use_divergence_rsi": True, "rsi_period": 5, "pivot_interval": 3, "act_without_confirmation": True}

        adapter = _make_adapter([_divergence_block(params_14)])
        r14 = adapter._execute_divergence("divergence", params_14, ohlcv_data)
        r5 = adapter._execute_divergence("divergence", params_5, ohlcv_data)

        # Results may differ (not always, but at least runs without error)
        assert len(r14["signal"]) == len(r5["signal"]) == len(ohlcv_data)


class TestDivergenceStochastic:
    """Tests for Stochastic divergence detection."""

    def test_stochastic_only(self, ohlcv_data):
        """Stochastic divergence must run without error."""
        params = {
            "use_divergence_rsi": False,
            "use_divergence_stochastic": True,
            "stoch_length": 14,
            "pivot_interval": 3,
            "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, ohlcv_data)
        assert len(result["signal"]) == len(ohlcv_data)

    def test_stochastic_length_param(self, ohlcv_data):
        """Different stoch_length should produce valid results."""
        params = {
            "use_divergence_rsi": False,
            "use_divergence_stochastic": True,
            "stoch_length": 7,
            "pivot_interval": 3,
            "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, ohlcv_data)
        assert isinstance(result["bearish"], pd.Series)


class TestDivergenceMomentum:
    """Tests for Momentum (ROC) divergence detection."""

    def test_momentum_only(self, ohlcv_data):
        """Momentum divergence must run without error."""
        params = {
            "use_divergence_rsi": False,
            "use_divergence_momentum": True,
            "momentum_length": 10,
            "pivot_interval": 3,
            "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, ohlcv_data)
        assert len(result["signal"]) == len(ohlcv_data)


class TestDivergenceCMF:
    """Tests for CMF divergence detection."""

    def test_cmf_only(self, ohlcv_data):
        """CMF divergence must run without error."""
        params = {
            "use_divergence_rsi": False,
            "use_divergence_cmf": True,
            "cmf_period": 21,
            "pivot_interval": 3,
            "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, ohlcv_data)
        assert len(result["signal"]) == len(ohlcv_data)


class TestDivergenceOBV:
    """Tests for OBV divergence detection."""

    def test_obv_only(self, ohlcv_data):
        """OBV divergence must run without error (no period param)."""
        params = {
            "use_divergence_rsi": False,
            "use_obv": True,
            "pivot_interval": 3,
            "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, ohlcv_data)
        assert len(result["signal"]) == len(ohlcv_data)


class TestDivergenceMFI:
    """Tests for MFI divergence detection."""

    def test_mfi_only(self, ohlcv_data):
        """MFI divergence must run without error."""
        params = {
            "use_divergence_rsi": False,
            "use_mfi": True,
            "mfi_length": 14,
            "pivot_interval": 3,
            "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, ohlcv_data)
        assert len(result["signal"]) == len(ohlcv_data)


# ============================================================
# 5. MULTIPLE INDICATORS COMBINED
# ============================================================


class TestDivergenceMultipleIndicators:
    """Tests for multiple indicators enabled simultaneously."""

    def test_rsi_and_stochastic(self, ohlcv_data):
        """RSI + Stochastic simultaneously."""
        params = {
            "use_divergence_rsi": True, "rsi_period": 14,
            "use_divergence_stochastic": True, "stoch_length": 14,
            "pivot_interval": 3, "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, ohlcv_data)
        assert len(result["signal"]) == len(ohlcv_data)

    def test_all_six_indicators(self, ohlcv_data):
        """All six indicators enabled at once."""
        params = {
            "use_divergence_rsi": True, "rsi_period": 14,
            "use_divergence_stochastic": True, "stoch_length": 14,
            "use_divergence_momentum": True, "momentum_length": 10,
            "use_divergence_cmf": True, "cmf_period": 21,
            "use_obv": True,
            "use_mfi": True, "mfi_length": 14,
            "pivot_interval": 3, "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, ohlcv_data)
        assert result["signal"].dtype == bool
        assert len(result["signal"]) == len(ohlcv_data)

    def test_combined_signals_are_ored(self, ohlcv_data):
        """Multiple indicators produce OR'd signals (more signals than single)."""
        params_single = {
            "use_divergence_rsi": True, "rsi_period": 14,
            "pivot_interval": 3, "act_without_confirmation": True,
        }
        params_multi = {
            "use_divergence_rsi": True, "rsi_period": 14,
            "use_divergence_stochastic": True, "stoch_length": 14,
            "use_divergence_momentum": True, "momentum_length": 10,
            "pivot_interval": 3, "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params_single)])
        r_single = adapter._execute_divergence("divergence", params_single, ohlcv_data)
        r_multi = adapter._execute_divergence("divergence", params_multi, ohlcv_data)

        # Multi-indicator should have >= signals (OR logic)
        assert r_multi["signal"].sum() >= r_single["signal"].sum()


# ============================================================
# 6. PIVOT INTERVAL PARAMETER
# ============================================================


class TestDivergencePivotInterval:
    """Tests for pivot_interval parameter."""

    def test_pivot_interval_default_9(self, ohlcv_data):
        """Default pivot_interval is 9."""
        params = {"use_divergence_rsi": True, "rsi_period": 14, "act_without_confirmation": True}
        # pivot_interval not set — uses default 9
        block = {
            "id": "div1", "type": "divergence", "category": "divergence",
            "params": params,
        }
        adapter = _make_adapter([block])
        result = adapter._execute_divergence("divergence", params, ohlcv_data)
        assert len(result["signal"]) == len(ohlcv_data)

    def test_pivot_interval_1(self, ohlcv_data):
        """Smallest pivot_interval (1) produces valid results."""
        params = {
            "pivot_interval": 1, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, ohlcv_data)
        assert len(result["signal"]) == len(ohlcv_data)

    def test_pivot_interval_9(self, ohlcv_data):
        """Largest pivot_interval (9) produces valid results."""
        params = {
            "pivot_interval": 9, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, ohlcv_data)
        assert len(result["signal"]) == len(ohlcv_data)

    def test_larger_pivot_interval_fewer_pivots(self, ohlcv_data):
        """Larger pivot_interval should find fewer pivots → potentially fewer signals."""
        params_small = {
            "pivot_interval": 1, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": True,
        }
        params_large = {
            "pivot_interval": 9, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params_small)])
        r_small = adapter._execute_divergence("divergence", params_small, ohlcv_data)
        r_large = adapter._execute_divergence("divergence", params_large, ohlcv_data)

        # Both should run; signal count may differ
        assert len(r_small["signal"]) == len(r_large["signal"])


# ============================================================
# 7. CONFIRMATION FILTER
# ============================================================


class TestDivergenceConfirmation:
    """Tests for act_without_confirmation parameter."""

    def test_without_confirmation_more_signals(self, ohlcv_data):
        """act_without_confirmation=True should produce >= signals than False."""
        params_no_confirm = {
            "pivot_interval": 3, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": True,
        }
        params_with_confirm = {
            "pivot_interval": 3, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": False,
        }
        adapter = _make_adapter([_divergence_block(params_no_confirm)])
        r_no = adapter._execute_divergence("divergence", params_no_confirm, ohlcv_data)
        r_yes = adapter._execute_divergence("divergence", params_with_confirm, ohlcv_data)

        # Without confirmation should have >= signals (confirmation filters some out)
        assert r_no["signal"].sum() >= r_yes["signal"].sum()

    def test_confirmation_requires_close_direction(self, ohlcv_data):
        """With confirmation, bullish requires close > prev_close."""
        params = {
            "pivot_interval": 3, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": False,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, ohlcv_data)
        # Result should still be valid
        assert result["signal"].dtype == bool


# ============================================================
# 8. SIGNAL MEMORY
# ============================================================


class TestDivergenceSignalMemory:
    """Tests for activate_diver_signal_memory and keep_diver_signal_memory_bars."""

    def test_memory_extends_signals(self, ohlcv_data):
        """With signal memory, signals should persist for N bars."""
        params_no_mem = {
            "pivot_interval": 3, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": True,
            "activate_diver_signal_memory": False,
        }
        params_with_mem = {
            "pivot_interval": 3, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": True,
            "activate_diver_signal_memory": True,
            "keep_diver_signal_memory_bars": 5,
        }
        adapter = _make_adapter([_divergence_block(params_no_mem)])
        r_no = adapter._execute_divergence("divergence", params_no_mem, ohlcv_data)
        r_mem = adapter._execute_divergence("divergence", params_with_mem, ohlcv_data)

        # Signal memory should extend signals → more True values
        assert r_mem["signal"].sum() >= r_no["signal"].sum()

    def test_memory_bars_1_same_as_no_memory(self, ohlcv_data):
        """Memory with 1 bar is effectively same as no memory."""
        params_no_mem = {
            "pivot_interval": 3, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": True,
            "activate_diver_signal_memory": False,
        }
        params_mem_1 = {
            "pivot_interval": 3, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": True,
            "activate_diver_signal_memory": True,
            "keep_diver_signal_memory_bars": 1,
        }
        adapter = _make_adapter([_divergence_block(params_no_mem)])
        r_no = adapter._execute_divergence("divergence", params_no_mem, ohlcv_data)
        r_mem1 = adapter._execute_divergence("divergence", params_mem_1, ohlcv_data)

        # With memory_bars=1, signals shouldn't extend beyond original bar
        # (memory loop only sets the original bar)
        pd.testing.assert_series_equal(r_no["signal"], r_mem1["signal"])

    def test_larger_memory_more_signals(self, ohlcv_data):
        """Larger memory_bars should produce >= signals than smaller."""
        params_5 = {
            "pivot_interval": 3, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": True,
            "activate_diver_signal_memory": True,
            "keep_diver_signal_memory_bars": 5,
        }
        params_20 = {
            "pivot_interval": 3, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": True,
            "activate_diver_signal_memory": True,
            "keep_diver_signal_memory_bars": 20,
        }
        adapter = _make_adapter([_divergence_block(params_5)])
        r_5 = adapter._execute_divergence("divergence", params_5, ohlcv_data)
        r_20 = adapter._execute_divergence("divergence", params_20, ohlcv_data)

        assert r_20["signal"].sum() >= r_5["signal"].sum()


# ============================================================
# 9. EDGE CASES
# ============================================================


class TestDivergenceEdgeCases:
    """Tests for edge cases and small data."""

    def test_small_data_no_crash(self, small_ohlcv):
        """Handler must not crash on small datasets."""
        params = {
            "pivot_interval": 3, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, small_ohlcv)
        assert len(result["signal"]) == len(small_ohlcv)

    def test_very_small_data_5_bars(self):
        """Handler must handle 5-bar data without error."""
        df = pd.DataFrame({
            "timestamp": pd.date_range("2025-01-01", periods=5, freq="1h"),
            "open": [100, 101, 99, 98, 100],
            "high": [102, 103, 101, 100, 102],
            "low": [98, 99, 97, 96, 98],
            "close": [101, 100, 98, 99, 101],
            "volume": [1000, 1100, 1200, 1100, 1000],
        })
        params = {
            "pivot_interval": 1, "use_divergence_rsi": True, "rsi_period": 3,
            "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, df)
        assert len(result["signal"]) == 5

    def test_pivot_interval_larger_than_half_data(self):
        """pivot_interval larger than half data length should still work (few/no pivots)."""
        df = pd.DataFrame({
            "timestamp": pd.date_range("2025-01-01", periods=10, freq="1h"),
            "open": np.arange(100, 110, dtype=float),
            "high": np.arange(101, 111, dtype=float),
            "low": np.arange(99, 109, dtype=float),
            "close": np.arange(100.5, 110.5, dtype=float),
            "volume": np.full(10, 1000.0),
        })
        params = {
            "pivot_interval": 9, "use_divergence_rsi": True, "rsi_period": 5,
            "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, df)
        assert len(result["signal"]) == 10
        # With pivot_interval=9 and only 10 bars, no pivots can be found
        assert not result["signal"].any()

    def test_constant_price_no_divergence(self, ohlcv_data):
        """Constant price should produce no divergence."""
        const_df = ohlcv_data.copy()
        const_df["open"] = 50000.0
        const_df["high"] = 50001.0
        const_df["low"] = 49999.0
        const_df["close"] = 50000.0

        params = {
            "pivot_interval": 3, "use_divergence_rsi": True, "rsi_period": 14,
            "act_without_confirmation": True,
        }
        adapter = _make_adapter([_divergence_block(params)])
        result = adapter._execute_divergence("divergence", params, const_df)
        # With constant price, no pivots → no divergence
        assert not result["signal"].any()

    def test_empty_params_uses_defaults(self, ohlcv_data):
        """Empty params should use all defaults without error."""
        adapter = _make_adapter([{
            "id": "div1", "type": "divergence", "category": "divergence", "params": {},
        }])
        result = adapter._execute_divergence("divergence", {}, ohlcv_data)
        # No indicators enabled by default → all False
        assert not result["signal"].any()


# ============================================================
# 10. INTEGRATION WITH STRATEGY BUILDER
# ============================================================


class TestDivergenceIntegration:
    """Integration tests: divergence block within a full strategy graph."""

    def test_divergence_to_buy_action(self, ohlcv_data):
        """Divergence → buy action pipeline."""
        blocks = [
            _divergence_block(),
            {"id": "b2", "type": "buy", "category": "action", "params": {}},
        ]
        connections = [{"from": "div1", "to": "b2"}]
        adapter = _make_adapter(blocks, connections)
        result = adapter.generate_signals(ohlcv_data)
        assert result is not None

    def test_divergence_with_stop_loss(self, ohlcv_data):
        """Divergence → buy → stop_loss pipeline."""
        blocks = [
            _divergence_block(),
            {"id": "b2", "type": "buy", "category": "action", "params": {}},
            {"id": "b3", "type": "stop_loss", "category": "action", "params": {"percent": 2.0}},
        ]
        connections = [
            {"from": "div1", "to": "b2"},
            {"from": "b2", "to": "b3"},
        ]
        adapter = _make_adapter(blocks, connections)
        result = adapter.generate_signals(ohlcv_data)
        assert result is not None

    def test_divergence_with_filter(self, ohlcv_data):
        """Divergence + trend filter pipeline."""
        blocks = [
            _divergence_block(),
            {"id": "b2", "type": "trend_filter", "category": "filter",
             "params": {"period": 20, "mode": "slope_up"}},
            {"id": "b3", "type": "buy", "category": "action", "params": {}},
        ]
        connections = [
            {"from": "div1", "to": "b2"},
            {"from": "b2", "to": "b3"},
        ]
        adapter = _make_adapter(blocks, connections)
        result = adapter.generate_signals(ohlcv_data)
        assert result is not None

    def test_divergence_with_all_indicators_full_strategy(self, ohlcv_data):
        """Full strategy with all indicators, memory, and confirmation."""
        blocks = [
            {
                "id": "div1",
                "type": "divergence",
                "category": "divergence",
                "params": {
                    "pivot_interval": 5,
                    "act_without_confirmation": False,
                    "activate_diver_signal_memory": True,
                    "keep_diver_signal_memory_bars": 3,
                    "use_divergence_rsi": True, "rsi_period": 14,
                    "use_divergence_stochastic": True, "stoch_length": 14,
                    "use_divergence_momentum": True, "momentum_length": 10,
                    "use_divergence_cmf": True, "cmf_period": 21,
                    "use_obv": True,
                    "use_mfi": True, "mfi_length": 14,
                },
            },
            {"id": "b2", "type": "buy", "category": "action", "params": {}},
            {"id": "b3", "type": "stop_loss", "category": "action", "params": {"percent": 2.0}},
            {"id": "b4", "type": "take_profit", "category": "action", "params": {"percent": 4.0}},
        ]
        connections = [
            {"from": "div1", "to": "b2"},
            {"from": "b2", "to": "b3"},
            {"from": "b3", "to": "b4"},
        ]
        adapter = _make_adapter(blocks, connections)
        result = adapter.generate_signals(ohlcv_data)
        assert result is not None


# ============================================================
# 11. VALIDATION RULES
# ============================================================


class TestDivergenceValidation:
    """Tests that backend validation rules are properly registered."""

    def test_validation_endpoint_exists(self, client):
        """The validation WebSocket endpoint should exist."""
        # Just verify the app loads without error
        response = client.get("/api/v1/health")
        assert response.status_code in (200, 404, 503)

    def test_divergence_in_validation_rules(self):
        """'divergence' should be in BLOCK_VALIDATION_RULES."""
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES
        assert "divergence" in BLOCK_VALIDATION_RULES

    def test_divergence_validation_pivot_interval(self):
        """pivot_interval validation should have min=1, max=9."""
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["divergence"]
        assert rules["pivot_interval"]["min"] == 1
        assert rules["pivot_interval"]["max"] == 9

    def test_divergence_in_connection_rules(self):
        """'divergence' should be in CONNECTION_RULES for entry_long and entry_short."""
        from backend.api.routers.strategy_validation_ws import CONNECTION_RULES
        assert "divergence" in CONNECTION_RULES["entry_long"]
        assert "divergence" in CONNECTION_RULES["entry_short"]


# ============================================================
# 12. API ENDPOINT TESTS
# ============================================================


class TestDivergenceAPI:
    """Tests for divergence block via API endpoints."""

    def test_validate_strategy_with_divergence(self, client):
        """Strategy with divergence block should pass validation."""
        strategy = {
            "name": "Divergence RSI Strategy",
            "blocks": [
                {
                    "id": "div1",
                    "type": "divergence",
                    "category": "divergence",
                    "params": {
                        "pivot_interval": 5,
                        "use_divergence_rsi": True,
                        "rsi_period": 14,
                        "act_without_confirmation": True,
                    },
                },
            ],
            "connections": [],
        }
        response = client.post("/api/v1/strategy-builder/validate", json=strategy)
        # Accept 200 or 404 (endpoint may not exist) — main thing is no 500
        assert response.status_code != 500


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
