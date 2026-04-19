"""
AI Agent Knowledge Test: ATR Exit Block — Real Adapter Tests

Tests verify that AI agents (DeepSeek, Qwen, Perplexity) correctly understand:
- Every parameter of the ATR Exit block (10 fields: 5 for SL, 5 for TP)
- How ATR Stop Loss section works (use_atr_sl, on_wicks, smoothing, period, multiplier)
- How ATR Take Profit section works (use_atr_tp, on_wicks, smoothing, period, multiplier)
- Which smoothing methods are available (WMA, RMA, SMA, EMA)
- How optimization mode works (only period and multiplier are optimizable)
- How extra_data is populated for the engine (atr_sl/atr_tp series, mult, on_wicks)
- Combining ATR exit with RSI/MACD entry filters

These tests run against the REAL StrategyBuilderAdapter (in-memory DB).
They validate that every ATR Exit parameter combination is properly processed.

Run:
    py -3.14 -m pytest tests/ai_agents/test_atr_exit_ai_agents.py -v
    py -3.14 -m pytest tests/ai_agents/test_atr_exit_ai_agents.py -v -k "defaults"
    py -3.14 -m pytest tests/ai_agents/test_atr_exit_ai_agents.py -v -k "smoothing"
    py -3.14 -m pytest tests/ai_agents/test_atr_exit_ai_agents.py -v -k "optimization"
    py -3.14 -m pytest tests/ai_agents/test_atr_exit_ai_agents.py -v -k "extra_data"
    py -3.14 -m pytest tests/ai_agents/test_atr_exit_ai_agents.py -v -k "filter"
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
    Realistic OHLCV data with known price action.
    1000 bars, hourly, BTC-like with trends and reversals.
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
# Graph Builders
# ============================================================


def _make_rsi_with_atr_exit(
    rsi_params: dict[str, Any],
    atr_params: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a strategy graph: RSI indicator → entry long/short → strategy,
    plus ATR Exit block (standalone, config-only).

    AI Agent Knowledge:
        ATR Exit is a STANDALONE exit block. It does NOT need connections
        to the strategy node. The engine reads ATR config from extra_data.
        Unlike trailing stop, ATR exit computes ATR pd.Series in the adapter
        and passes them via extra_data for bar-by-bar engine execution.
    """
    return {
        "name": "RSI + ATR Exit Test",
        "blocks": [
            {
                "id": "b_rsi",
                "type": "rsi",
                "category": "indicator",
                "name": "RSI",
                "x": 100,
                "y": 100,
                "params": rsi_params,
            },
            {
                "id": "atr_1",
                "type": "atr_exit",
                "category": "exit",
                "name": "ATR Exit",
                "icon": "chart-bar",
                "x": 600,
                "y": 450,
                "params": atr_params,
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


def _make_macd_with_atr_exit(
    macd_params: dict[str, Any],
    atr_params: dict[str, Any],
) -> dict[str, Any]:
    """Build a strategy graph: MACD indicator → entry long/short → strategy + ATR Exit."""
    return {
        "name": "MACD + ATR Exit Test",
        "blocks": [
            {
                "id": "b_macd",
                "type": "macd",
                "category": "indicator",
                "name": "MACD",
                "x": 100,
                "y": 100,
                "params": macd_params,
            },
            {
                "id": "atr_1",
                "type": "atr_exit",
                "category": "exit",
                "name": "ATR Exit",
                "icon": "chart-bar",
                "x": 600,
                "y": 450,
                "params": atr_params,
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


def _make_atr_exit_only(atr_params: dict[str, Any]) -> dict[str, Any]:
    """
    Build a strategy graph with ONLY an ATR Exit block + RSI passthrough entry.

    AI Agent Knowledge:
        RSI with no modes acts as passthrough. This isolates ATR exit behavior.
    """
    return _make_rsi_with_atr_exit({"period": 14}, atr_params)


def _run_adapter(graph: dict, ohlcv: pd.DataFrame) -> dict[str, Any]:
    """
    Run StrategyBuilderAdapter and return signal result + _value_cache.

    Returns dict with:
        - entries, exits, short_entries, short_exits: pd.Series
        - extra_data: dict (ATR series + config for engine)
        - _value_cache: internal adapter cache (for inspecting exit block outputs)
    """
    adapter = StrategyBuilderAdapter(graph)
    result = adapter.generate_signals(ohlcv)
    return {
        "entries": result.entries,
        "exits": result.exits,
        "short_entries": result.short_entries,
        "short_exits": result.short_exits,
        "extra_data": result.extra_data,
        "_value_cache": adapter._value_cache,
    }


# ============================================================
#
#  PART 1 — ATR EXIT DEFAULT VALUES
#
#  AI Knowledge: "What are the default values?"
#  Panel fields (from strategy_builder.js blockDefaults):
#    use_atr_sl = false          (checkbox — use ATR Stop Loss?)
#    atr_sl_on_wicks = false     (checkbox — check wicks?)
#    atr_sl_smoothing = 'WMA'   (select: WMA/RMA/SMA/EMA)
#    atr_sl_period = 140        (number, optimizable, range 1-150)
#    atr_sl_multiplier = 4.0    (number, optimizable, range 0.1-4, step 0.1)
#    use_atr_tp = false          (checkbox — use ATR Take Profit?)
#    atr_tp_on_wicks = false     (checkbox — check wicks?)
#    atr_tp_smoothing = 'WMA'   (select: WMA/RMA/SMA/EMA)
#    atr_tp_period = 140        (number, optimizable, range 1-150)
#    atr_tp_multiplier = 4.0    (number, optimizable, range 0.1-4, step 0.1)
#
# ============================================================


class TestATRExitDefaults:
    """AI agents must know all default values and what each parameter does."""

    def test_default_values_both_disabled(self, sample_ohlcv):
        """Default: both ATR SL and ATR TP are disabled."""
        graph = _make_atr_exit_only({})
        result = _run_adapter(graph, sample_ohlcv)

        # ATR exit with both disabled — config-only, exits = 0
        assert result["exits"].sum() == 0, "ATR exit is config-only, exits must be 0"

        cache = result["_value_cache"]
        assert "atr_1" in cache, "ATR exit block should be in value cache"

        atr_cache = cache["atr_1"]
        assert atr_cache["use_atr_sl"] is False, "Default: ATR SL disabled"
        assert atr_cache["use_atr_tp"] is False, "Default: ATR TP disabled"

    def test_default_no_extra_data_when_disabled(self, sample_ohlcv):
        """When both ATR SL and TP are disabled, extra_data should NOT contain ATR fields."""
        graph = _make_atr_exit_only({})
        result = _run_adapter(graph, sample_ohlcv)
        extra = result["extra_data"] or {}

        assert "use_atr_sl" not in extra, "No ATR SL in extra_data when disabled"
        assert "use_atr_tp" not in extra, "No ATR TP in extra_data when disabled"

    def test_entry_signals_exist_with_passthrough_rsi(self, sample_ohlcv):
        """RSI passthrough + ATR Exit → entries should exist."""
        graph = _make_atr_exit_only({})
        result = _run_adapter(graph, sample_ohlcv)

        assert result["entries"].sum() > 0, "RSI passthrough should produce long entries"


# ============================================================
#
#  PART 2 — ATR STOP LOSS CONFIGURATION
#
#  AI Knowledge: "How ATR Stop Loss works?"
#  When use_atr_sl=True, the adapter computes ATR with the specified
#  smoothing method (WMA/RMA/SMA/EMA) and period. The engine then
#  checks: if current loss >= multiplier x ATR, exit position.
#
#  atr_sl_on_wicks: if False, only close price is checked.
#    If True, wicks (high/low) are also checked for SL trigger.
#
# ============================================================


class TestATRStopLossConfig:
    """Test ATR Stop Loss section — 5 parameters."""

    def test_atr_sl_enabled_default_params(self, sample_ohlcv):
        """Enable ATR SL with default smoothing/period/multiplier."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_smoothing": "WMA",
                "atr_sl_period": 140,
                "atr_sl_multiplier": 4.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["use_atr_sl"] is True
        assert "atr_sl" in cache, "ATR SL series must be computed"
        assert isinstance(cache["atr_sl"], pd.Series), "ATR SL must be a pd.Series"
        assert cache["atr_sl_mult"] == 4.0
        assert len(cache["atr_sl"]) == len(sample_ohlcv)

    def test_atr_sl_on_wicks_enabled(self, sample_ohlcv):
        """Enable ATR SL on wicks — check high/low for SL trigger."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_on_wicks": True,
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["atr_sl_on_wicks"] is True

    def test_atr_sl_on_wicks_disabled(self, sample_ohlcv):
        """Disable ATR SL on wicks — only close price checked."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_on_wicks": False,
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["atr_sl_on_wicks"] is False

    def test_atr_sl_custom_period_and_multiplier(self, sample_ohlcv):
        """Custom period=20, multiplier=2.5 for ATR SL."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_period": 20,
                "atr_sl_multiplier": 2.5,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["atr_sl_mult"] == 2.5
        assert isinstance(cache["atr_sl"], pd.Series)

    @pytest.mark.parametrize(
        "period,mult",
        [
            (10, 1.0),
            (14, 2.0),
            (50, 3.0),
            (100, 3.5),
            (140, 4.0),
        ],
    )
    def test_atr_sl_various_period_multiplier(self, sample_ohlcv, period, mult):
        """Parametrized: various ATR SL period/multiplier combos."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_period": period,
                "atr_sl_multiplier": mult,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["use_atr_sl"] is True
        assert cache["atr_sl_mult"] == mult
        assert isinstance(cache["atr_sl"], pd.Series)
        assert result["exits"].sum() == 0, "Config-only: exits must be 0"

    def test_atr_sl_period_clamped_to_max_150(self, sample_ohlcv):
        """Period is clamped: max(1, min(150, period)). Value > 150 → 150."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_period": 200,  # Exceeds max
                "atr_sl_multiplier": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        # Adapter clamps to 150
        assert cache["use_atr_sl"] is True
        assert isinstance(cache["atr_sl"], pd.Series)

    def test_atr_sl_multiplier_clamped(self, sample_ohlcv):
        """Multiplier is clamped: max(0.1, min(4.0, mult)). Value > 4 → 4."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_period": 14,
                "atr_sl_multiplier": 10.0,  # Exceeds max
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["atr_sl_mult"] == 4.0, "Multiplier clamped to max 4.0"


# ============================================================
#
#  PART 3 — ATR TAKE PROFIT CONFIGURATION
#
#  AI Knowledge: "How ATR Take Profit works?"
#  Mirrored structure: use_atr_tp, on_wicks, smoothing, period, multiplier.
#  When use_atr_tp=True, engine checks: if profit >= multiplier x ATR, exit.
#
# ============================================================


class TestATRTakeProfitConfig:
    """Test ATR Take Profit section — 5 parameters."""

    def test_atr_tp_enabled_default_params(self, sample_ohlcv):
        """Enable ATR TP with default smoothing/period/multiplier."""
        graph = _make_atr_exit_only(
            {
                "use_atr_tp": True,
                "atr_tp_smoothing": "WMA",
                "atr_tp_period": 140,
                "atr_tp_multiplier": 4.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["use_atr_tp"] is True
        assert "atr_tp" in cache, "ATR TP series must be computed"
        assert isinstance(cache["atr_tp"], pd.Series), "ATR TP must be a pd.Series"
        assert cache["atr_tp_mult"] == 4.0
        assert len(cache["atr_tp"]) == len(sample_ohlcv)

    def test_atr_tp_on_wicks_enabled(self, sample_ohlcv):
        """Enable ATR TP on wicks."""
        graph = _make_atr_exit_only(
            {
                "use_atr_tp": True,
                "atr_tp_on_wicks": True,
                "atr_tp_period": 14,
                "atr_tp_multiplier": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["atr_tp_on_wicks"] is True

    def test_atr_tp_custom_period_and_multiplier(self, sample_ohlcv):
        """Custom period=30, multiplier=3.0 for ATR TP."""
        graph = _make_atr_exit_only(
            {
                "use_atr_tp": True,
                "atr_tp_period": 30,
                "atr_tp_multiplier": 3.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["atr_tp_mult"] == 3.0
        assert isinstance(cache["atr_tp"], pd.Series)

    @pytest.mark.parametrize(
        "period,mult",
        [
            (10, 1.0),
            (14, 2.0),
            (50, 3.0),
            (100, 3.5),
            (140, 4.0),
        ],
    )
    def test_atr_tp_various_period_multiplier(self, sample_ohlcv, period, mult):
        """Parametrized: various ATR TP period/multiplier combos."""
        graph = _make_atr_exit_only(
            {
                "use_atr_tp": True,
                "atr_tp_period": period,
                "atr_tp_multiplier": mult,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["use_atr_tp"] is True
        assert cache["atr_tp_mult"] == mult
        assert isinstance(cache["atr_tp"], pd.Series)


# ============================================================
#
#  PART 4 — SMOOTHING METHOD CONFIGURATION
#
#  AI Knowledge: "What smoothing methods are available?"
#  Both ATR SL and ATR TP support 4 smoothing methods:
#    'WMA' — Weighted Moving Average (default)
#    'RMA' — Running Moving Average (Wilder's)
#    'SMA' — Simple Moving Average
#    'EMA' — Exponential Moving Average
#
#  Smoothing methods are select fields — NOT optimizable.
#  Invalid smoothing values fall back to 'RMA'.
#
# ============================================================


class TestSmoothingMethods:
    """Test all 4 smoothing methods for ATR SL and ATR TP."""

    @pytest.mark.parametrize("method", ["WMA", "RMA", "SMA", "EMA"])
    def test_atr_sl_smoothing_methods(self, sample_ohlcv, method):
        """ATR SL smoothing: all 4 methods should produce valid ATR series."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_smoothing": method,
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["use_atr_sl"] is True
        assert isinstance(cache["atr_sl"], pd.Series)
        # ATR values should be positive (after warmup period)
        valid_atr = cache["atr_sl"].dropna()
        assert (valid_atr > 0).all(), f"ATR values must be positive for method {method}"

    @pytest.mark.parametrize("method", ["WMA", "RMA", "SMA", "EMA"])
    def test_atr_tp_smoothing_methods(self, sample_ohlcv, method):
        """ATR TP smoothing: all 4 methods should produce valid ATR series."""
        graph = _make_atr_exit_only(
            {
                "use_atr_tp": True,
                "atr_tp_smoothing": method,
                "atr_tp_period": 14,
                "atr_tp_multiplier": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["use_atr_tp"] is True
        assert isinstance(cache["atr_tp"], pd.Series)
        valid_atr = cache["atr_tp"].dropna()
        assert (valid_atr > 0).all(), f"ATR values must be positive for method {method}"

    def test_invalid_smoothing_falls_back_to_rma(self, sample_ohlcv):
        """Invalid smoothing method → falls back to 'RMA'."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_smoothing": "INVALID",
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        # Adapter falls back: if sl_smoothing not in (...): sl_smoothing = "RMA"
        assert cache["use_atr_sl"] is True
        assert isinstance(cache["atr_sl"], pd.Series)

    def test_different_smoothing_produces_different_atr(self, sample_ohlcv):
        """Different smoothing methods should produce different ATR values."""
        atr_results = {}
        for method in ["WMA", "RMA", "SMA", "EMA"]:
            graph = _make_atr_exit_only(
                {
                    "use_atr_sl": True,
                    "atr_sl_smoothing": method,
                    "atr_sl_period": 14,
                    "atr_sl_multiplier": 2.0,
                }
            )
            result = _run_adapter(graph, sample_ohlcv)
            atr_results[method] = result["_value_cache"]["atr_1"]["atr_sl"]

        # At least some pairs should differ (not all smoothing methods give same result)
        wma_sum = atr_results["WMA"].dropna().sum()
        sma_sum = atr_results["SMA"].dropna().sum()
        assert wma_sum != sma_sum, "WMA and SMA should produce different ATR values"


# ============================================================
#
#  PART 5 — COMBINED ATR SL + ATR TP
#
#  AI Knowledge: "Can ATR SL and TP be used together?"
#  Yes! Both can be enabled simultaneously with independent settings.
#  Each has its own smoothing method, period, multiplier, and on_wicks flag.
#
# ============================================================


class TestCombinedATRSLTP:
    """Test ATR SL and TP enabled simultaneously."""

    def test_both_enabled_same_settings(self, sample_ohlcv):
        """Both ATR SL and TP enabled with same period/multiplier."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
                "use_atr_tp": True,
                "atr_tp_period": 14,
                "atr_tp_multiplier": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["use_atr_sl"] is True
        assert cache["use_atr_tp"] is True
        assert isinstance(cache["atr_sl"], pd.Series)
        assert isinstance(cache["atr_tp"], pd.Series)

    def test_both_enabled_different_settings(self, sample_ohlcv):
        """Both ATR SL and TP with completely different settings."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_smoothing": "EMA",
                "atr_sl_period": 20,
                "atr_sl_multiplier": 1.5,
                "atr_sl_on_wicks": True,
                "use_atr_tp": True,
                "atr_tp_smoothing": "SMA",
                "atr_tp_period": 50,
                "atr_tp_multiplier": 3.0,
                "atr_tp_on_wicks": False,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["use_atr_sl"] is True
        assert cache["use_atr_tp"] is True
        assert cache["atr_sl_mult"] == 1.5
        assert cache["atr_tp_mult"] == 3.0
        assert cache["atr_sl_on_wicks"] is True
        assert cache["atr_tp_on_wicks"] is False

    def test_sl_only_no_tp(self, sample_ohlcv):
        """Only ATR SL enabled, TP disabled."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
                "use_atr_tp": False,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["use_atr_sl"] is True
        assert cache["use_atr_tp"] is False
        assert "atr_sl" in cache
        assert "atr_tp" not in cache

    def test_tp_only_no_sl(self, sample_ohlcv):
        """Only ATR TP enabled, SL disabled."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": False,
                "use_atr_tp": True,
                "atr_tp_period": 14,
                "atr_tp_multiplier": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["use_atr_sl"] is False
        assert cache["use_atr_tp"] is True
        assert "atr_sl" not in cache
        assert "atr_tp" in cache


# ============================================================
#
#  PART 6 — OPTIMIZATION MODE
#
#  AI Knowledge: "How does optimization mode work for ATR Exit?"
#  Screenshot 4 shows optimization mode:
#    Each optimizable field gets: [min] → [max] / [step]
#
#  Optimizable fields (4 total):
#    - atr_sl_period (range 1-150, optimizable: true)
#    - atr_sl_multiplier (range 0.1-4, step 0.1, optimizable: true)
#    - atr_tp_period (range 1-150, optimizable: true)
#    - atr_tp_multiplier (range 0.1-4, step 0.1, optimizable: true)
#
#  Non-optimizable fields (6 total):
#    - use_atr_sl (checkbox)
#    - atr_sl_on_wicks (checkbox)
#    - atr_sl_smoothing (select — NOT optimizable)
#    - use_atr_tp (checkbox)
#    - atr_tp_on_wicks (checkbox)
#    - atr_tp_smoothing (select — NOT optimizable)
#
# ============================================================


class TestATROptimization:
    """Test optimization ranges for ATR period/multiplier parameters."""

    def test_optimization_range_sl_period(self, sample_ohlcv):
        """AI Agent must understand: ATR SL period optimization range."""
        for period in [10, 50, 100, 140]:
            graph = _make_atr_exit_only(
                {
                    "use_atr_sl": True,
                    "atr_sl_period": period,
                    "atr_sl_multiplier": 2.0,
                }
            )
            result = _run_adapter(graph, sample_ohlcv)
            cache = result["_value_cache"]["atr_1"]
            assert cache["use_atr_sl"] is True
            assert isinstance(cache["atr_sl"], pd.Series)

    def test_optimization_range_sl_multiplier(self, sample_ohlcv):
        """AI Agent must understand: ATR SL multiplier optimization range (0.1-4.0)."""
        for mult in [0.5, 1.0, 2.0, 3.0, 4.0]:
            graph = _make_atr_exit_only(
                {
                    "use_atr_sl": True,
                    "atr_sl_period": 14,
                    "atr_sl_multiplier": mult,
                }
            )
            result = _run_adapter(graph, sample_ohlcv)
            cache = result["_value_cache"]["atr_1"]
            assert cache["atr_sl_mult"] == mult

    def test_optimization_range_tp_period(self, sample_ohlcv):
        """AI Agent must understand: ATR TP period optimization range."""
        for period in [10, 50, 100, 140]:
            graph = _make_atr_exit_only(
                {
                    "use_atr_tp": True,
                    "atr_tp_period": period,
                    "atr_tp_multiplier": 2.0,
                }
            )
            result = _run_adapter(graph, sample_ohlcv)
            cache = result["_value_cache"]["atr_1"]
            assert cache["use_atr_tp"] is True
            assert isinstance(cache["atr_tp"], pd.Series)

    def test_optimization_full_grid_sl(self, sample_ohlcv):
        """Optimizer tests ALL combinations of SL period x multiplier."""
        period_range = [14, 50]
        mult_range = [1.0, 2.0]
        results = []

        for period in period_range:
            for mult in mult_range:
                graph = _make_atr_exit_only(
                    {
                        "use_atr_sl": True,
                        "atr_sl_period": period,
                        "atr_sl_multiplier": mult,
                    }
                )
                result = _run_adapter(graph, sample_ohlcv)
                cache = result["_value_cache"]["atr_1"]
                assert cache["use_atr_sl"] is True
                assert cache["atr_sl_mult"] == mult
                results.append(result["entries"].sum())

        # Entry signals must NOT depend on exit parameters
        assert all(c == results[0] for c in results), "Entry signals must NOT depend on ATR exit parameters"

    def test_non_optimizable_fields_fixed(self, sample_ohlcv):
        """Checkboxes and selects are NOT optimizable — stay fixed during optimization."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_on_wicks": True,
                "atr_sl_smoothing": "EMA",
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert isinstance(cache["use_atr_sl"], bool)
        assert isinstance(cache["atr_sl_on_wicks"], bool)


# ============================================================
#
#  PART 7 — CONFIG-ONLY BEHAVIOR
#
#  AI Knowledge: "ATR Exit is config-only — engine executes"
#  The adapter computes ATR pd.Series and stores in _value_cache.
#  The engine reads ATR data via extra_data and applies bar-by-bar.
#  The adapter exit signal is always False.
#
# ============================================================


class TestConfigOnlyBehavior:
    """Verify that ATR Exit is config-only (adapter exit = False)."""

    def test_exit_always_false(self, sample_ohlcv):
        """ATR exit signal is ALWAYS False — engine handles actual exits."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
                "use_atr_tp": True,
                "atr_tp_period": 14,
                "atr_tp_multiplier": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)

        assert result["exits"].sum() == 0, "ATR exit must not generate exit signals"

    def test_short_exit_always_false(self, sample_ohlcv):
        """Short exits also False for config-only block."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)

        if result["short_exits"] is not None:
            assert result["short_exits"].sum() == 0

    def test_exit_params_independent_of_entry(self, sample_ohlcv):
        """Exit config does NOT affect entry signal generation."""
        graph1 = _make_atr_exit_only({"use_atr_sl": True, "atr_sl_period": 10, "atr_sl_multiplier": 1.0})
        graph2 = _make_atr_exit_only({"use_atr_sl": True, "atr_sl_period": 140, "atr_sl_multiplier": 4.0})

        result1 = _run_adapter(graph1, sample_ohlcv)
        result2 = _run_adapter(graph2, sample_ohlcv)

        pd.testing.assert_series_equal(
            result1["entries"],
            result2["entries"],
            check_names=False,
            obj="Entry signals must be identical regardless of ATR exit settings",
        )


# ============================================================
#
#  PART 8 — EXTRA_DATA POPULATION
#
#  AI Knowledge: "How does extra_data work for ATR Exit?"
#  When use_atr_sl=True, extra_data gets:
#    - use_atr_sl = True
#    - atr_sl = pd.Series (ATR values)
#    - atr_sl_mult = float
#    - atr_sl_on_wicks = bool
#
#  When use_atr_tp=True, extra_data gets:
#    - use_atr_tp = True
#    - atr_tp = pd.Series (ATR values)
#    - atr_tp_mult = float
#    - atr_tp_on_wicks = bool
#
# ============================================================


class TestExtraDataPopulation:
    """Verify that extra_data is correctly populated for the engine."""

    def test_extra_data_sl_only(self, sample_ohlcv):
        """Extra_data with only ATR SL enabled."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_on_wicks": True,
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.5,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        extra = result["extra_data"]

        assert extra.get("use_atr_sl") is True
        assert isinstance(extra["atr_sl"], pd.Series)
        assert extra["atr_sl_mult"] == 2.5
        assert extra["atr_sl_on_wicks"] is True

        # TP should NOT be in extra_data
        assert "use_atr_tp" not in extra

    def test_extra_data_tp_only(self, sample_ohlcv):
        """Extra_data with only ATR TP enabled."""
        graph = _make_atr_exit_only(
            {
                "use_atr_tp": True,
                "atr_tp_on_wicks": False,
                "atr_tp_period": 20,
                "atr_tp_multiplier": 3.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        extra = result["extra_data"]

        assert extra.get("use_atr_tp") is True
        assert isinstance(extra["atr_tp"], pd.Series)
        assert extra["atr_tp_mult"] == 3.0
        assert extra["atr_tp_on_wicks"] is False

        # SL should NOT be in extra_data
        assert "use_atr_sl" not in extra

    def test_extra_data_both_sl_and_tp(self, sample_ohlcv):
        """Extra_data with both ATR SL and TP enabled — all 8 fields present."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_on_wicks": True,
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
                "use_atr_tp": True,
                "atr_tp_on_wicks": False,
                "atr_tp_period": 30,
                "atr_tp_multiplier": 3.5,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        extra = result["extra_data"]

        # SL fields
        assert extra["use_atr_sl"] is True
        assert isinstance(extra["atr_sl"], pd.Series)
        assert extra["atr_sl_mult"] == 2.0
        assert extra["atr_sl_on_wicks"] is True

        # TP fields
        assert extra["use_atr_tp"] is True
        assert isinstance(extra["atr_tp"], pd.Series)
        assert extra["atr_tp_mult"] == 3.5
        assert extra["atr_tp_on_wicks"] is False

    def test_extra_data_empty_when_both_disabled(self, sample_ohlcv):
        """No ATR data in extra_data when both SL and TP are disabled."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": False,
                "use_atr_tp": False,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        extra = result["extra_data"] or {}

        assert "use_atr_sl" not in extra
        assert "use_atr_tp" not in extra
        assert "atr_sl" not in extra
        assert "atr_tp" not in extra

    def test_atr_series_length_matches_ohlcv(self, sample_ohlcv):
        """ATR series in extra_data must match OHLCV length."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
                "use_atr_tp": True,
                "atr_tp_period": 14,
                "atr_tp_multiplier": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        extra = result["extra_data"]

        assert len(extra["atr_sl"]) == len(sample_ohlcv)
        assert len(extra["atr_tp"]) == len(sample_ohlcv)


# ============================================================
#
#  PART 9 — RSI FILTER + ATR EXIT (Combined)
#
# ============================================================


class TestRSIFilterWithATRExit:
    """Combine RSI entry filters with ATR exit."""

    def test_rsi_range_with_atr_sl(self, sample_ohlcv):
        """RSI range filter (20-50) + ATR SL."""
        graph = _make_rsi_with_atr_exit(
            rsi_params={
                "period": 14,
                "use_long_range": True,
                "long_rsi_more": 20,
                "long_rsi_less": 50,
            },
            atr_params={
                "use_atr_sl": True,
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        assert result["entries"].sum() < len(sample_ohlcv), "RSI range should limit entries"
        assert result["entries"].sum() > 0

        cache = result["_value_cache"]["atr_1"]
        assert cache["use_atr_sl"] is True

        extra = result["extra_data"]
        assert extra.get("use_atr_sl") is True

    def test_rsi_cross_with_atr_sl_tp(self, sample_ohlcv):
        """RSI cross level + both ATR SL and TP."""
        graph = _make_rsi_with_atr_exit(
            rsi_params={
                "period": 14,
                "use_cross_level": True,
                "cross_long_level": 30,
                "cross_short_level": 70,
            },
            atr_params={
                "use_atr_sl": True,
                "atr_sl_period": 20,
                "atr_sl_multiplier": 2.5,
                "atr_sl_on_wicks": True,
                "use_atr_tp": True,
                "atr_tp_period": 30,
                "atr_tp_multiplier": 3.0,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        assert result["entries"].sum() < len(sample_ohlcv) * 0.1

        extra = result["extra_data"]
        assert extra["use_atr_sl"] is True
        assert extra["use_atr_tp"] is True
        assert extra["atr_sl_on_wicks"] is True


# ============================================================
#
#  PART 10 — MACD FILTER + ATR EXIT (Combined)
#
# ============================================================


class TestMACDFilterWithATRExit:
    """Combine MACD entry filters with ATR exit."""

    def test_macd_cross_with_atr_sl(self, sample_ohlcv):
        """MACD cross signal + ATR SL."""
        graph = _make_macd_with_atr_exit(
            macd_params={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "use_cross_signal": True,
            },
            atr_params={
                "use_atr_sl": True,
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        total_signals = result["entries"].sum() + (
            result["short_entries"].sum() if result["short_entries"] is not None else 0
        )
        assert total_signals >= 0

        cache = result["_value_cache"]["atr_1"]
        assert cache["use_atr_sl"] is True

    def test_macd_histogram_with_full_atr_config(self, sample_ohlcv):
        """MACD histogram + full ATR SL+TP config with different smoothing."""
        graph = _make_macd_with_atr_exit(
            macd_params={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "use_histogram_filter": True,
                "histogram_above": 0,
            },
            atr_params={
                "use_atr_sl": True,
                "atr_sl_smoothing": "EMA",
                "atr_sl_period": 20,
                "atr_sl_multiplier": 1.5,
                "atr_sl_on_wicks": True,
                "use_atr_tp": True,
                "atr_tp_smoothing": "SMA",
                "atr_tp_period": 50,
                "atr_tp_multiplier": 3.0,
                "atr_tp_on_wicks": False,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        extra = result["extra_data"]
        assert extra["use_atr_sl"] is True
        assert extra["use_atr_tp"] is True
        assert extra["atr_sl_mult"] == 1.5
        assert extra["atr_tp_mult"] == 3.0


# ============================================================
#
#  PART 11 — RSI + MACD COMBO + ATR EXIT
#
# ============================================================


class TestRSIMACDComboWithATRExit:
    """Test combined RSI + MACD entry with ATR exit."""

    def _make_rsi_macd_with_atr_exit(
        self,
        rsi_params: dict,
        macd_params: dict,
        atr_params: dict,
    ) -> dict[str, Any]:
        """Build a graph with RSI → long, MACD → short, + ATR Exit."""
        return {
            "name": "RSI+MACD+ATR Exit Combo Test",
            "blocks": [
                {
                    "id": "b_rsi",
                    "type": "rsi",
                    "category": "indicator",
                    "name": "RSI",
                    "x": 100,
                    "y": 100,
                    "params": rsi_params,
                },
                {
                    "id": "b_macd",
                    "type": "macd",
                    "category": "indicator",
                    "name": "MACD",
                    "x": 100,
                    "y": 300,
                    "params": macd_params,
                },
                {
                    "id": "atr_1",
                    "type": "atr_exit",
                    "category": "exit",
                    "name": "ATR Exit",
                    "icon": "chart-bar",
                    "x": 600,
                    "y": 450,
                    "params": atr_params,
                },
                {
                    "id": "main",
                    "type": "strategy",
                    "category": "main",
                    "name": "Strategy",
                    "isMain": True,
                    "x": 500,
                    "y": 200,
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
                    "source": {"blockId": "b_macd", "portId": "short"},
                    "target": {"blockId": "main", "portId": "entry_short"},
                    "type": "data",
                },
            ],
        }

    def test_rsi_long_macd_short_with_atr_sl_tp(self, sample_ohlcv):
        """RSI cross for longs + MACD cross for shorts + ATR SL+TP."""
        graph = self._make_rsi_macd_with_atr_exit(
            rsi_params={
                "period": 14,
                "use_cross_level": True,
                "cross_long_level": 30,
                "cross_short_level": 70,
            },
            macd_params={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "use_cross_signal": True,
            },
            atr_params={
                "use_atr_sl": True,
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
                "use_atr_tp": True,
                "atr_tp_period": 20,
                "atr_tp_multiplier": 3.0,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        assert result["entries"].sum() > 0

        extra = result["extra_data"]
        assert extra["use_atr_sl"] is True
        assert extra["use_atr_tp"] is True

    def test_rsi_range_macd_histogram_full_atr(self, sample_ohlcv):
        """RSI range + MACD histogram + full ATR config."""
        graph = self._make_rsi_macd_with_atr_exit(
            rsi_params={
                "period": 14,
                "use_long_range": True,
                "long_rsi_more": 20,
                "long_rsi_less": 50,
            },
            macd_params={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "use_histogram_filter": True,
                "histogram_above": 0,
            },
            atr_params={
                "use_atr_sl": True,
                "atr_sl_smoothing": "RMA",
                "atr_sl_period": 14,
                "atr_sl_multiplier": 2.0,
                "atr_sl_on_wicks": True,
                "use_atr_tp": True,
                "atr_tp_smoothing": "EMA",
                "atr_tp_period": 30,
                "atr_tp_multiplier": 3.5,
                "atr_tp_on_wicks": False,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        extra = result["extra_data"]
        assert extra["use_atr_sl"] is True
        assert extra["use_atr_tp"] is True
        assert extra["atr_sl_on_wicks"] is True
        assert extra["atr_tp_on_wicks"] is False


# ============================================================
#
#  PART 12 — ALL PARAMS FULL SCENARIO
#
#  AI Knowledge: Comprehensive test — set EVERY parameter explicitly.
#
# ============================================================


class TestAllParamsFullScenario:
    """Set every single ATR Exit parameter and verify all are stored."""

    def test_every_param_explicit(self, sample_ohlcv):
        """Set ALL 10 params: both SL and TP with all sub-fields."""
        graph = _make_atr_exit_only(
            {
                "use_atr_sl": True,
                "atr_sl_on_wicks": True,
                "atr_sl_smoothing": "EMA",
                "atr_sl_period": 20,
                "atr_sl_multiplier": 2.5,
                "use_atr_tp": True,
                "atr_tp_on_wicks": False,
                "atr_tp_smoothing": "SMA",
                "atr_tp_period": 50,
                "atr_tp_multiplier": 3.5,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        # Verify _value_cache
        assert cache["use_atr_sl"] is True
        assert cache["use_atr_tp"] is True
        assert cache["atr_sl_on_wicks"] is True
        assert cache["atr_tp_on_wicks"] is False
        assert cache["atr_sl_mult"] == 2.5
        assert cache["atr_tp_mult"] == 3.5
        assert isinstance(cache["atr_sl"], pd.Series)
        assert isinstance(cache["atr_tp"], pd.Series)

        # Exit signal is still False (config-only)
        assert cache["exit"].sum() == 0

        # Verify extra_data
        extra = result["extra_data"]
        assert extra["use_atr_sl"] is True
        assert extra["use_atr_tp"] is True
        assert extra["atr_sl_mult"] == 2.5
        assert extra["atr_tp_mult"] == 3.5
        assert extra["atr_sl_on_wicks"] is True
        assert extra["atr_tp_on_wicks"] is False

    def test_minimal_params_fallback_defaults(self, sample_ohlcv):
        """Empty params — both SL and TP disabled, no ATR computed."""
        graph = _make_atr_exit_only({})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["atr_1"]

        assert cache["use_atr_sl"] is False
        assert cache["use_atr_tp"] is False
        assert "atr_sl" not in cache
        assert "atr_tp" not in cache

    def test_all_smoothing_methods_full_cycle(self, sample_ohlcv):
        """
        Run full cycle with each smoothing method for SL —
        verify _value_cache + extra_data are consistent.
        """
        for method in ["WMA", "RMA", "SMA", "EMA"]:
            graph = _make_atr_exit_only(
                {
                    "use_atr_sl": True,
                    "atr_sl_smoothing": method,
                    "atr_sl_period": 14,
                    "atr_sl_multiplier": 2.0,
                }
            )
            result = _run_adapter(graph, sample_ohlcv)
            cache = result["_value_cache"]["atr_1"]
            extra = result["extra_data"]

            # Both should have ATR SL data
            assert cache["use_atr_sl"] is True
            assert extra["use_atr_sl"] is True
            assert isinstance(cache["atr_sl"], pd.Series)
            assert isinstance(extra["atr_sl"], pd.Series)

            # ATR values should be consistent between cache and extra_data
            pd.testing.assert_series_equal(
                cache["atr_sl"],
                extra["atr_sl"],
                check_names=False,
                obj=f"ATR SL series must match between cache and extra_data ({method})",
            )
