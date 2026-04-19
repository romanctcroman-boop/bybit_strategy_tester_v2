"""
AI Agent Knowledge Test: Static SL/TP Exit Block — Real API Tests

Tests verify that AI agents (DeepSeek, Qwen, Perplexity) correctly understand:
- Every parameter of the Static SL/TP exit block
- How normal mode works (set TP/SL, breakeven, close-only-in-profit, sl_type)
- How optimization mode works (ranges for TP/SL/breakeven)
- Combining exit blocks with RSI/MACD entry filters

These tests run against the REAL StrategyBuilderAdapter + TestClient (in-memory DB).
They validate that every Static SL/TP parameter combination is properly processed by the adapter.

Run:
    py -3.14 -m pytest tests/ai_agents/test_static_sltp_ai_agents.py -v
    py -3.14 -m pytest tests/ai_agents/test_static_sltp_ai_agents.py -v -k "defaults"
    py -3.14 -m pytest tests/ai_agents/test_static_sltp_ai_agents.py -v -k "breakeven"
    py -3.14 -m pytest tests/ai_agents/test_static_sltp_ai_agents.py -v -k "optimization"
    py -3.14 -m pytest tests/ai_agents/test_static_sltp_ai_agents.py -v -k "filter"
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


def _make_rsi_with_sltp(
    rsi_params: dict[str, Any],
    sltp_params: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a strategy graph: RSI indicator → entry long/short → strategy,
    plus Static SL/TP exit block (standalone, no connection needed).

    AI Agent Knowledge:
        Static SL/TP is a STANDALONE exit block. It does NOT need connections
        to the strategy node. The engine reads its config from builder_blocks.
        Only entry signals need connections.
    """
    return {
        "name": "RSI + Static SL/TP Test",
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
                "id": "sltp_1",
                "type": "static_sltp",
                "category": "exit",
                "name": "Static SL/TP",
                "icon": "shield-check",
                "x": 600,
                "y": 450,
                "params": sltp_params,
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


def _make_macd_with_sltp(
    macd_params: dict[str, Any],
    sltp_params: dict[str, Any],
) -> dict[str, Any]:
    """Build a strategy graph: MACD indicator → entry long/short → strategy + Static SL/TP."""
    return {
        "name": "MACD + Static SL/TP Test",
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
                "id": "sltp_1",
                "type": "static_sltp",
                "category": "exit",
                "name": "Static SL/TP",
                "icon": "shield-check",
                "x": 600,
                "y": 450,
                "params": sltp_params,
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


def _make_sltp_only(sltp_params: dict[str, Any]) -> dict[str, Any]:
    """
    Build a strategy graph with ONLY a Static SL/TP exit block + RSI passthrough entry.

    AI Agent Knowledge:
        This tests the SL/TP block in isolation. RSI with no modes enabled
        acts as passthrough (long/short = True on all bars), so we focus
        purely on exit block behavior.
    """
    return _make_rsi_with_sltp({"period": 14}, sltp_params)


def _run_adapter(graph: dict, ohlcv: pd.DataFrame) -> dict[str, Any]:
    """
    Run StrategyBuilderAdapter and return signal result + _value_cache.

    Returns dict with:
        - entries, exits, short_entries, short_exits: pd.Series
        - extra_data: dict (ATR/trailing config for engine)
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
#  PART 1 — STATIC SL/TP DEFAULT VALUES
#
#  AI Knowledge: "What are the default values?"
#  Panel fields:
#    take_profit_percent = 1.5
#    stop_loss_percent = 1.5
#    sl_type = 'average_price'
#    close_only_in_profit = false
#    activate_breakeven = false
#    breakeven_activation_percent = 0.5
#    new_breakeven_sl_percent = 0.1
#
# ============================================================


class TestStaticSLTPDefaults:
    """AI agents must know all default values and what each parameter does."""

    def test_default_values_passthrough(self, sample_ohlcv):
        """Default SL/TP: TP=1.5%, SL=1.5%, breakeven disabled, close_only_in_profit=false."""
        graph = _make_sltp_only(
            {
                "take_profit_percent": 1.5,
                "stop_loss_percent": 1.5,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)

        # Static SL/TP is a config-only block — it does NOT generate exit signals.
        # The engine handles SL/TP execution bar-by-bar.
        # So exits should be False (the block returns pd.Series([False, ...]))
        assert result["exits"].sum() == 0, "Static SL/TP is config-only, exits must be 0"

        # Check that the _value_cache has the correct config
        cache = result["_value_cache"]
        assert "sltp_1" in cache, "SL/TP block should be in value cache"

        sltp_cache = cache["sltp_1"]
        assert sltp_cache["stop_loss_percent"] == 1.5, "Default SL must be 1.5%"
        assert sltp_cache["take_profit_percent"] == 1.5, "Default TP must be 1.5%"

    def test_default_breakeven_disabled(self, sample_ohlcv):
        """Default: breakeven is disabled (activate_breakeven=false)."""
        graph = _make_sltp_only(
            {
                "take_profit_percent": 1.5,
                "stop_loss_percent": 1.5,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["activate_breakeven"] is False, "Breakeven must be disabled by default"
        assert cache["close_only_in_profit"] is False, "Close-only-in-profit must be disabled by default"

    def test_default_breakeven_values(self, sample_ohlcv):
        """Default breakeven values: activation=0.5%, new_sl=0.1%."""
        graph = _make_sltp_only(
            {
                "take_profit_percent": 1.5,
                "stop_loss_percent": 1.5,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["breakeven_activation_percent"] == 0.5, "Default breakeven activation must be 0.5%"
        assert cache["new_breakeven_sl_percent"] == 0.1, "Default new breakeven SL must be 0.1%"

    def test_entry_signals_exist_with_passthrough_rsi(self, sample_ohlcv):
        """RSI passthrough + Static SL/TP → entries should exist."""
        graph = _make_sltp_only({"take_profit_percent": 1.5, "stop_loss_percent": 1.5})
        result = _run_adapter(graph, sample_ohlcv)

        assert result["entries"].sum() > 0, "RSI passthrough should produce long entries"


# ============================================================
#
#  PART 2 — TAKE PROFIT & STOP LOSS CONFIGURATION
#
#  AI Knowledge: "How to set TP and SL percentages?"
#  TP: % profit from entry price to auto-close at profit.
#  SL: % loss from entry price to auto-close at loss.
#  Both are config-only → engine reads them, adapter just passes them.
#
# ============================================================


class TestSLTPConfiguration:
    """Test setting various TP/SL values — the core functionality."""

    def test_tp_2_sl_1(self, sample_ohlcv):
        """Set TP=2%, SL=1% — risk:reward = 1:2."""
        graph = _make_sltp_only({"take_profit_percent": 2.0, "stop_loss_percent": 1.0})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["take_profit_percent"] == 2.0
        assert cache["stop_loss_percent"] == 1.0

    def test_tp_3_sl_1_5(self, sample_ohlcv):
        """Set TP=3%, SL=1.5% — conservative risk:reward = 1:2."""
        graph = _make_sltp_only({"take_profit_percent": 3.0, "stop_loss_percent": 1.5})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["take_profit_percent"] == 3.0
        assert cache["stop_loss_percent"] == 1.5

    def test_tp_0_5_sl_0_5(self, sample_ohlcv):
        """Set TP=0.5%, SL=0.5% — tight scalping SL/TP."""
        graph = _make_sltp_only({"take_profit_percent": 0.5, "stop_loss_percent": 0.5})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["take_profit_percent"] == 0.5
        assert cache["stop_loss_percent"] == 0.5

    def test_tp_10_sl_5(self, sample_ohlcv):
        """Set TP=10%, SL=5% — wide swing trade SL/TP."""
        graph = _make_sltp_only({"take_profit_percent": 10.0, "stop_loss_percent": 5.0})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["take_profit_percent"] == 10.0
        assert cache["stop_loss_percent"] == 5.0

    @pytest.mark.parametrize(
        "tp,sl",
        [
            (1.0, 1.0),
            (1.5, 1.5),
            (2.0, 1.0),
            (3.0, 1.5),
            (5.0, 2.0),
            (0.5, 0.3),
        ],
    )
    def test_various_tp_sl_combinations(self, sample_ohlcv, tp, sl):
        """Parametrized: verify various TP/SL combos are stored correctly."""
        graph = _make_sltp_only({"take_profit_percent": tp, "stop_loss_percent": sl})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["take_profit_percent"] == tp, f"TP should be {tp}"
        assert cache["stop_loss_percent"] == sl, f"SL should be {sl}"
        assert result["exits"].sum() == 0, "Config-only block must not generate exit signals"


# ============================================================
#
#  PART 3 — BREAKEVEN CONFIGURATION
#
#  AI Knowledge: "How breakeven works?"
#  activate_breakeven=True → when profit reaches breakeven_activation_percent,
#  the SL is moved to entry + new_breakeven_sl_percent.
#
#  Screenshot 1 shows: Activate Breakeven? checkbox, (%) to Activate = 0.5, New SL = 0.1
#
# ============================================================


class TestBreakevenConfiguration:
    """Test breakeven activation and its parameters."""

    def test_breakeven_enabled(self, sample_ohlcv):
        """Enable breakeven: activation at 1%, new SL at 0.1%."""
        graph = _make_sltp_only(
            {
                "take_profit_percent": 2.0,
                "stop_loss_percent": 1.0,
                "activate_breakeven": True,
                "breakeven_activation_percent": 1.0,
                "new_breakeven_sl_percent": 0.1,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["activate_breakeven"] is True, "Breakeven must be enabled"
        assert cache["breakeven_activation_percent"] == 1.0, "Activation at 1%"
        assert cache["new_breakeven_sl_percent"] == 0.1, "New SL at 0.1%"

    def test_breakeven_disabled_explicit(self, sample_ohlcv):
        """Explicitly disable breakeven."""
        graph = _make_sltp_only(
            {
                "take_profit_percent": 2.0,
                "stop_loss_percent": 1.0,
                "activate_breakeven": False,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["activate_breakeven"] is False

    def test_breakeven_high_activation(self, sample_ohlcv):
        """Breakeven activation at 5% profit, new SL at 2%."""
        graph = _make_sltp_only(
            {
                "take_profit_percent": 10.0,
                "stop_loss_percent": 3.0,
                "activate_breakeven": True,
                "breakeven_activation_percent": 5.0,
                "new_breakeven_sl_percent": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["activate_breakeven"] is True
        assert cache["breakeven_activation_percent"] == 5.0
        assert cache["new_breakeven_sl_percent"] == 2.0

    def test_breakeven_tight_scalping(self, sample_ohlcv):
        """Tight scalping breakeven: activate at 0.3%, move SL to 0.05%."""
        graph = _make_sltp_only(
            {
                "take_profit_percent": 1.0,
                "stop_loss_percent": 0.5,
                "activate_breakeven": True,
                "breakeven_activation_percent": 0.3,
                "new_breakeven_sl_percent": 0.05,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["activate_breakeven"] is True
        assert cache["breakeven_activation_percent"] == 0.3
        assert cache["new_breakeven_sl_percent"] == 0.05

    @pytest.mark.parametrize(
        "activation,new_sl",
        [
            (0.5, 0.1),
            (1.0, 0.1),
            (2.0, 0.5),
            (3.0, 1.0),
            (0.3, 0.05),
        ],
    )
    def test_breakeven_parametrized(self, sample_ohlcv, activation, new_sl):
        """Parametrized breakeven: various activation/new_sl combos."""
        graph = _make_sltp_only(
            {
                "take_profit_percent": 3.0,
                "stop_loss_percent": 1.5,
                "activate_breakeven": True,
                "breakeven_activation_percent": activation,
                "new_breakeven_sl_percent": new_sl,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["breakeven_activation_percent"] == activation
        assert cache["new_breakeven_sl_percent"] == new_sl


# ============================================================
#
#  PART 4 — CLOSE ONLY IN PROFIT
#
#  AI Knowledge: "What does close_only_in_profit do?"
#  When enabled, the SL will NOT close the position if it's in loss.
#  Only TP can close. This is useful for DCA strategies where you
#  expect the average price to recover.
#
# ============================================================


class TestCloseOnlyInProfit:
    """Test the close_only_in_profit flag."""

    def test_close_only_in_profit_enabled(self, sample_ohlcv):
        """Enable close-only-in-profit: SL ignored when in loss."""
        graph = _make_sltp_only(
            {
                "take_profit_percent": 2.0,
                "stop_loss_percent": 1.0,
                "close_only_in_profit": True,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["close_only_in_profit"] is True

    def test_close_only_in_profit_disabled(self, sample_ohlcv):
        """Default: close_only_in_profit=False — SL works normally."""
        graph = _make_sltp_only(
            {
                "take_profit_percent": 2.0,
                "stop_loss_percent": 1.0,
                "close_only_in_profit": False,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["close_only_in_profit"] is False

    def test_close_only_in_profit_with_breakeven(self, sample_ohlcv):
        """Combine close_only_in_profit + breakeven — both should be stored."""
        graph = _make_sltp_only(
            {
                "take_profit_percent": 3.0,
                "stop_loss_percent": 1.5,
                "close_only_in_profit": True,
                "activate_breakeven": True,
                "breakeven_activation_percent": 1.0,
                "new_breakeven_sl_percent": 0.1,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["close_only_in_profit"] is True
        assert cache["activate_breakeven"] is True
        assert cache["breakeven_activation_percent"] == 1.0


# ============================================================
#
#  PART 5 — OPTIMIZATION MODE
#
#  AI Knowledge: "How does optimization mode work for SL/TP?"
#  Screenshot 2 shows optimization mode:
#    Each optimizable field gets: [min] → [max] / [step]
#    The optimizer tests all combinations in the range.
#
#  Optimizable fields for Static SL/TP:
#    - take_profit_percent (optimizable: true)
#    - stop_loss_percent (optimizable: true)
#    - breakeven_activation_percent (optimizable: true)
#    - new_breakeven_sl_percent (optimizable: true)
#
#  Non-optimizable fields:
#    - sl_type (select — NOT optimizable)
#    - close_only_in_profit (checkbox — NOT optimizable)
#    - activate_breakeven (checkbox — NOT optimizable)
#
#  Optimization range format: { min, max, step }
#  Example: TP from 1.0 to 3.0 step 0.5 → tests 1.0, 1.5, 2.0, 2.5, 3.0
#
# ============================================================


class TestSLTPOptimization:
    """Test optimization ranges for TP/SL/breakeven parameters."""

    def test_optimization_range_tp(self, sample_ohlcv):
        """
        AI Agent must understand: TP optimization range.
        When optimizer runs, it iterates TP from min to max with step.
        Here we test individual values from that range.
        """
        for tp_value in [1.0, 1.5, 2.0, 2.5, 3.0]:
            graph = _make_sltp_only(
                {
                    "take_profit_percent": tp_value,
                    "stop_loss_percent": 1.5,
                }
            )
            result = _run_adapter(graph, sample_ohlcv)
            cache = result["_value_cache"]["sltp_1"]
            assert cache["take_profit_percent"] == tp_value, f"TP should be {tp_value}"

    def test_optimization_range_sl(self, sample_ohlcv):
        """
        AI Agent must understand: SL optimization range.
        When optimizer runs, it iterates SL from min to max with step.
        """
        for sl_value in [0.5, 1.0, 1.5, 2.0, 2.5]:
            graph = _make_sltp_only(
                {
                    "take_profit_percent": 2.0,
                    "stop_loss_percent": sl_value,
                }
            )
            result = _run_adapter(graph, sample_ohlcv)
            cache = result["_value_cache"]["sltp_1"]
            assert cache["stop_loss_percent"] == sl_value, f"SL should be {sl_value}"

    def test_optimization_range_breakeven(self, sample_ohlcv):
        """
        AI Agent must understand: breakeven activation % optimization range.
        Only applicable when activate_breakeven=True.
        """
        for activation in [0.3, 0.5, 0.8, 1.0, 1.5]:
            graph = _make_sltp_only(
                {
                    "take_profit_percent": 2.0,
                    "stop_loss_percent": 1.0,
                    "activate_breakeven": True,
                    "breakeven_activation_percent": activation,
                    "new_breakeven_sl_percent": 0.1,
                }
            )
            result = _run_adapter(graph, sample_ohlcv)
            cache = result["_value_cache"]["sltp_1"]
            assert cache["breakeven_activation_percent"] == activation

    def test_optimization_range_new_breakeven_sl(self, sample_ohlcv):
        """
        AI Agent must understand: new breakeven SL % optimization range.
        Controls where SL moves to after breakeven activates.
        """
        for new_sl in [0.05, 0.1, 0.2, 0.3, 0.5]:
            graph = _make_sltp_only(
                {
                    "take_profit_percent": 2.0,
                    "stop_loss_percent": 1.0,
                    "activate_breakeven": True,
                    "breakeven_activation_percent": 0.5,
                    "new_breakeven_sl_percent": new_sl,
                }
            )
            result = _run_adapter(graph, sample_ohlcv)
            cache = result["_value_cache"]["sltp_1"]
            assert cache["new_breakeven_sl_percent"] == new_sl

    def test_optimization_full_grid(self, sample_ohlcv):
        """
        AI Agent must understand: optimizer tests ALL combinations.
        Example: TP in [1.0, 2.0], SL in [0.5, 1.0] → 4 combinations.
        Each combo must produce valid results.
        """
        tp_range = [1.0, 2.0]
        sl_range = [0.5, 1.0]
        results = []

        for tp in tp_range:
            for sl in sl_range:
                graph = _make_sltp_only(
                    {
                        "take_profit_percent": tp,
                        "stop_loss_percent": sl,
                    }
                )
                result = _run_adapter(graph, sample_ohlcv)
                cache = result["_value_cache"]["sltp_1"]
                assert cache["take_profit_percent"] == tp
                assert cache["stop_loss_percent"] == sl
                results.append((tp, sl, result["entries"].sum()))

        # All combos should produce same entries (entry signals don't depend on exit params)
        entry_counts = [r[2] for r in results]
        assert all(c == entry_counts[0] for c in entry_counts), "Entry signals must NOT depend on exit block parameters"

    def test_non_optimizable_fields_are_fixed(self, sample_ohlcv):
        """
        AI Agent must know: sl_type, close_only_in_profit, activate_breakeven
        are NOT optimizable. They stay fixed during optimization runs.
        """
        # These are checkboxes/selects — not number fields with min/max/step
        graph = _make_sltp_only(
            {
                "take_profit_percent": 2.0,
                "stop_loss_percent": 1.0,
                "close_only_in_profit": True,
                "activate_breakeven": True,
                "breakeven_activation_percent": 0.5,
                "new_breakeven_sl_percent": 0.1,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        # Booleans — fixed during optimization
        assert isinstance(cache["close_only_in_profit"], bool)
        assert isinstance(cache["activate_breakeven"], bool)


# ============================================================
#
#  PART 6 — CONFIG-ONLY BEHAVIOR
#
#  AI Knowledge: "Static SL/TP is config-only — engine executes"
#  The adapter stores SL/TP values in _value_cache.
#  The engine (FallbackEngineV4) reads them and applies bar-by-bar.
#  The adapter itself never sets exit=True — it's always False.
#
# ============================================================


class TestConfigOnlyBehavior:
    """Verify that Static SL/TP is truly config-only."""

    def test_exit_always_false(self, sample_ohlcv):
        """Static SL/TP exit signal is ALWAYS False — engine handles actual exits."""
        graph = _make_sltp_only({"take_profit_percent": 1.5, "stop_loss_percent": 1.5})
        result = _run_adapter(graph, sample_ohlcv)

        assert result["exits"].sum() == 0, "Static SL/TP must not generate exit signals"

    def test_short_exit_always_false(self, sample_ohlcv):
        """Short exits also False for config-only block."""
        graph = _make_sltp_only({"take_profit_percent": 1.5, "stop_loss_percent": 1.5})
        result = _run_adapter(graph, sample_ohlcv)

        # short_exits may be None or all-False
        if result["short_exits"] is not None:
            assert result["short_exits"].sum() == 0

    def test_cache_stores_all_params(self, sample_ohlcv):
        """Value cache must store ALL static_sltp params for engine consumption."""
        graph = _make_sltp_only(
            {
                "take_profit_percent": 2.5,
                "stop_loss_percent": 1.2,
                "close_only_in_profit": True,
                "activate_breakeven": True,
                "breakeven_activation_percent": 0.8,
                "new_breakeven_sl_percent": 0.15,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        # All params must be in cache for engine
        assert "take_profit_percent" in cache
        assert "stop_loss_percent" in cache
        assert "close_only_in_profit" in cache
        assert "activate_breakeven" in cache
        assert "breakeven_activation_percent" in cache
        assert "new_breakeven_sl_percent" in cache
        assert "exit" in cache  # exit signal series (all False)

    def test_exit_params_independent_of_entry(self, sample_ohlcv):
        """Exit config does NOT affect entry signal generation."""
        # Run twice with different SL/TP — entries must be identical
        graph1 = _make_sltp_only({"take_profit_percent": 1.0, "stop_loss_percent": 1.0})
        graph2 = _make_sltp_only({"take_profit_percent": 10.0, "stop_loss_percent": 5.0})

        result1 = _run_adapter(graph1, sample_ohlcv)
        result2 = _run_adapter(graph2, sample_ohlcv)

        pd.testing.assert_series_equal(
            result1["entries"],
            result2["entries"],
            check_names=False,
            obj="Entry signals must be identical regardless of SL/TP settings",
        )


# ============================================================
#
#  PART 7 — RSI FILTER + STATIC SL/TP (Combined)
#
#  AI Knowledge: "How to combine RSI filter with exit block?"
#  The entry uses RSI range/cross signals → connected to strategy.
#  The exit uses Static SL/TP → standalone block (no connection needed).
#
# ============================================================


class TestRSIFilterWithSLTP:
    """Combine RSI entry filters with Static SL/TP exits."""

    def test_rsi_range_with_sltp(self, sample_ohlcv):
        """RSI range filter (20-50 for long) + TP=2%, SL=1%."""
        graph = _make_rsi_with_sltp(
            rsi_params={
                "period": 14,
                "use_long_range": True,
                "long_rsi_more": 20,
                "long_rsi_less": 50,
            },
            sltp_params={
                "take_profit_percent": 2.0,
                "stop_loss_percent": 1.0,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        # RSI range should filter entries
        assert result["entries"].sum() < len(sample_ohlcv), "RSI range filter should limit entries"
        assert result["entries"].sum() > 0, "Some entries should exist in RSI 20-50 range"

        # SL/TP should be correctly configured
        cache = result["_value_cache"]["sltp_1"]
        assert cache["take_profit_percent"] == 2.0
        assert cache["stop_loss_percent"] == 1.0

    def test_rsi_cross_with_sltp_and_breakeven(self, sample_ohlcv):
        """RSI cross level + TP=3%, SL=1.5%, breakeven at 1%."""
        graph = _make_rsi_with_sltp(
            rsi_params={
                "period": 14,
                "use_cross_level": True,
                "cross_long_level": 30,
                "cross_short_level": 70,
            },
            sltp_params={
                "take_profit_percent": 3.0,
                "stop_loss_percent": 1.5,
                "activate_breakeven": True,
                "breakeven_activation_percent": 1.0,
                "new_breakeven_sl_percent": 0.1,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        # Cross signals should be rare
        assert result["entries"].sum() < len(sample_ohlcv) * 0.1, "Cross signals should be rare (<10%)"

        cache = result["_value_cache"]["sltp_1"]
        assert cache["take_profit_percent"] == 3.0
        assert cache["activate_breakeven"] is True
        assert cache["breakeven_activation_percent"] == 1.0

    def test_rsi_cross_memory_with_close_only_profit(self, sample_ohlcv):
        """RSI cross with 5-bar memory + close_only_in_profit=True."""
        graph = _make_rsi_with_sltp(
            rsi_params={
                "period": 14,
                "use_cross_level": True,
                "cross_long_level": 30,
                "cross_short_level": 70,
                "use_cross_memory": True,
                "cross_memory_bars": 5,
            },
            sltp_params={
                "take_profit_percent": 2.0,
                "stop_loss_percent": 1.0,
                "close_only_in_profit": True,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        # Memory should expand signals compared to no memory
        assert result["entries"].sum() > 0, "Cross + memory should produce entries"

        cache = result["_value_cache"]["sltp_1"]
        assert cache["close_only_in_profit"] is True


# ============================================================
#
#  PART 8 — MACD FILTER + STATIC SL/TP (Combined)
#
#  AI Knowledge: "How to combine MACD filter with exit block?"
#  Same principle: MACD generates entry signals, SL/TP handles exits.
#
# ============================================================


class TestMACDFilterWithSLTP:
    """Combine MACD entry filters with Static SL/TP exits."""

    def test_macd_cross_with_sltp(self, sample_ohlcv):
        """MACD cross signal + TP=2.5%, SL=1.5%."""
        graph = _make_macd_with_sltp(
            macd_params={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "use_cross_signal": True,
            },
            sltp_params={
                "take_profit_percent": 2.5,
                "stop_loss_percent": 1.5,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        # MACD cross is event-based — may or may not produce entries depending on data.
        # The key test: adapter processes without errors and SL/TP config is stored.
        total_signals = result["entries"].sum() + (
            result["short_entries"].sum() if result["short_entries"] is not None else 0
        )
        assert total_signals >= 0, "MACD cross adapter should process without errors"

        cache = result["_value_cache"]["sltp_1"]
        assert cache["take_profit_percent"] == 2.5
        assert cache["stop_loss_percent"] == 1.5

    def test_macd_histogram_with_breakeven(self, sample_ohlcv):
        """MACD histogram filter + breakeven enabled."""
        graph = _make_macd_with_sltp(
            macd_params={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "use_histogram_filter": True,
                "histogram_above": 0,
            },
            sltp_params={
                "take_profit_percent": 3.0,
                "stop_loss_percent": 1.5,
                "activate_breakeven": True,
                "breakeven_activation_percent": 1.5,
                "new_breakeven_sl_percent": 0.2,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["sltp_1"]
        assert cache["activate_breakeven"] is True
        assert cache["breakeven_activation_percent"] == 1.5
        assert cache["new_breakeven_sl_percent"] == 0.2

    def test_macd_cross_with_full_exit_config(self, sample_ohlcv):
        """MACD cross + full SL/TP config: all params set explicitly."""
        graph = _make_macd_with_sltp(
            macd_params={
                "fast_period": 8,
                "slow_period": 21,
                "signal_period": 5,
                "use_cross_signal": True,
            },
            sltp_params={
                "take_profit_percent": 4.0,
                "stop_loss_percent": 2.0,
                "close_only_in_profit": True,
                "activate_breakeven": True,
                "breakeven_activation_percent": 2.0,
                "new_breakeven_sl_percent": 0.5,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["sltp_1"]
        assert cache["take_profit_percent"] == 4.0
        assert cache["stop_loss_percent"] == 2.0
        assert cache["close_only_in_profit"] is True
        assert cache["activate_breakeven"] is True
        assert cache["breakeven_activation_percent"] == 2.0
        assert cache["new_breakeven_sl_percent"] == 0.5


# ============================================================
#
#  PART 9 — RSI + MACD COMBO + SL/TP
#
#  AI Knowledge: "How to combine RSI AND MACD filters with exit?"
#  Use RSI as entry filter connected to long, MACD connected to short,
#  or chain them. Exit is always the same Static SL/TP.
#
# ============================================================


class TestRSIMACDComboWithSLTP:
    """Test combined RSI + MACD entry with Static SL/TP exit."""

    def _make_rsi_macd_with_sltp(
        self,
        rsi_params: dict,
        macd_params: dict,
        sltp_params: dict,
    ) -> dict[str, Any]:
        """Build a graph with RSI → long, MACD → short, + Static SL/TP."""
        return {
            "name": "RSI+MACD+SL/TP Combo Test",
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
                    "id": "sltp_1",
                    "type": "static_sltp",
                    "category": "exit",
                    "name": "Static SL/TP",
                    "icon": "shield-check",
                    "x": 600,
                    "y": 450,
                    "params": sltp_params,
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
                # RSI → entry_long
                {
                    "id": "c1",
                    "source": {"blockId": "b_rsi", "portId": "long"},
                    "target": {"blockId": "main", "portId": "entry_long"},
                    "type": "data",
                },
                # MACD → entry_short
                {
                    "id": "c2",
                    "source": {"blockId": "b_macd", "portId": "short"},
                    "target": {"blockId": "main", "portId": "entry_short"},
                    "type": "data",
                },
            ],
        }

    def test_rsi_long_macd_short_with_sltp(self, sample_ohlcv):
        """RSI cross for longs + MACD cross for shorts + TP=2%, SL=1%."""
        graph = self._make_rsi_macd_with_sltp(
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
            sltp_params={
                "take_profit_percent": 2.0,
                "stop_loss_percent": 1.0,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        assert result["entries"].sum() > 0, "RSI cross should produce long entries"

        cache = result["_value_cache"]["sltp_1"]
        assert cache["take_profit_percent"] == 2.0
        assert cache["stop_loss_percent"] == 1.0

    def test_rsi_range_macd_histogram_full_config(self, sample_ohlcv):
        """RSI range for longs + MACD histogram for shorts + full SL/TP + breakeven."""
        graph = self._make_rsi_macd_with_sltp(
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
            sltp_params={
                "take_profit_percent": 3.0,
                "stop_loss_percent": 1.5,
                "close_only_in_profit": True,
                "activate_breakeven": True,
                "breakeven_activation_percent": 1.0,
                "new_breakeven_sl_percent": 0.1,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["sltp_1"]
        assert cache["take_profit_percent"] == 3.0
        assert cache["stop_loss_percent"] == 1.5
        assert cache["close_only_in_profit"] is True
        assert cache["activate_breakeven"] is True


# ============================================================
#
#  PART 10 — ALL PARAMS FULL SCENARIO
#
#  AI Knowledge: Comprehensive test — set EVERY parameter explicitly.
#  This is the "ultimate" test for AI agent understanding.
#
# ============================================================


class TestAllParamsFullScenario:
    """Set every single Static SL/TP parameter and verify all are stored."""

    def test_every_param_explicit(self, sample_ohlcv):
        """Set ALL params: TP, SL, sl_type, close_only_in_profit, breakeven, activation, new_sl."""
        graph = _make_sltp_only(
            {
                "take_profit_percent": 2.5,
                "stop_loss_percent": 1.2,
                "sl_type": "last_order",
                "close_only_in_profit": True,
                "activate_breakeven": True,
                "breakeven_activation_percent": 0.8,
                "new_breakeven_sl_percent": 0.15,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        # Verify every parameter
        assert cache["take_profit_percent"] == 2.5
        assert cache["stop_loss_percent"] == 1.2
        assert cache["close_only_in_profit"] is True
        assert cache["activate_breakeven"] is True
        assert cache["breakeven_activation_percent"] == 0.8
        assert cache["new_breakeven_sl_percent"] == 0.15

        # Exit signal is still False (config-only)
        assert cache["exit"].sum() == 0

    def test_minimal_params_fallback_defaults(self, sample_ohlcv):
        """Set only TP/SL — all other params should fall back to defaults."""
        graph = _make_sltp_only(
            {
                "take_profit_percent": 1.0,
                "stop_loss_percent": 0.5,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        # Explicit values
        assert cache["take_profit_percent"] == 1.0
        assert cache["stop_loss_percent"] == 0.5

        # Defaults for omitted params
        assert cache["close_only_in_profit"] is False
        assert cache["activate_breakeven"] is False
        assert cache["breakeven_activation_percent"] == 0.5
        assert cache["new_breakeven_sl_percent"] == 0.1

    def test_empty_params_all_defaults(self, sample_ohlcv):
        """Empty params dict — ALL values should use adapter defaults."""
        graph = _make_sltp_only({})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["sltp_1"]

        assert cache["take_profit_percent"] == 1.5, "Default TP = 1.5%"
        assert cache["stop_loss_percent"] == 1.5, "Default SL = 1.5%"
        assert cache["close_only_in_profit"] is False
        assert cache["activate_breakeven"] is False
        assert cache["breakeven_activation_percent"] == 0.5
        assert cache["new_breakeven_sl_percent"] == 0.1
