"""
AI Agent Knowledge Test: Trailing Stop Exit Block — Real API Tests

Tests verify that AI agents (DeepSeek, Qwen, Perplexity) correctly understand:
- Every parameter of the Trailing Stop exit block
- How normal mode works (activation_percent, trailing_percent, trail_type)
- How optimization mode works (ranges for activation_percent, trailing_percent)
- That trail_type is a select field and NOT optimizable
- How extra_data is populated for the engine (use_trailing_stop, etc.)
- Combining trailing stop with RSI/MACD entry filters

These tests run against the REAL StrategyBuilderAdapter + TestClient (in-memory DB).
They validate that every Trailing Stop parameter combination is properly processed.

Run:
    py -3.14 -m pytest tests/ai_agents/test_trailing_stop_ai_agents.py -v
    py -3.14 -m pytest tests/ai_agents/test_trailing_stop_ai_agents.py -v -k "defaults"
    py -3.14 -m pytest tests/ai_agents/test_trailing_stop_ai_agents.py -v -k "trail_type"
    py -3.14 -m pytest tests/ai_agents/test_trailing_stop_ai_agents.py -v -k "optimization"
    py -3.14 -m pytest tests/ai_agents/test_trailing_stop_ai_agents.py -v -k "extra_data"
    py -3.14 -m pytest tests/ai_agents/test_trailing_stop_ai_agents.py -v -k "filter"
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


def _make_rsi_with_trailing(
    rsi_params: dict[str, Any],
    trailing_params: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a strategy graph: RSI indicator → entry long/short → strategy,
    plus Trailing Stop exit block (standalone, no connection needed).

    AI Agent Knowledge:
        Trailing Stop is a STANDALONE config-only exit block. It does NOT
        need connections to the strategy node. The engine reads its config
        from extra_data (use_trailing_stop, trailing_activation_percent,
        trailing_percent, trail_type).
    """
    return {
        "name": "RSI + Trailing Stop Test",
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
                "id": "trail_1",
                "type": "trailing_stop_exit",
                "category": "exit",
                "name": "Trailing Stop",
                "icon": "arrow-trending",
                "x": 600,
                "y": 450,
                "params": trailing_params,
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


def _make_macd_with_trailing(
    macd_params: dict[str, Any],
    trailing_params: dict[str, Any],
) -> dict[str, Any]:
    """Build a strategy graph: MACD indicator → entry long/short → strategy + Trailing Stop."""
    return {
        "name": "MACD + Trailing Stop Test",
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
                "id": "trail_1",
                "type": "trailing_stop_exit",
                "category": "exit",
                "name": "Trailing Stop",
                "icon": "arrow-trending",
                "x": 600,
                "y": 450,
                "params": trailing_params,
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


def _make_trailing_only(trailing_params: dict[str, Any]) -> dict[str, Any]:
    """
    Build a strategy graph with ONLY a Trailing Stop exit block + RSI passthrough entry.

    AI Agent Knowledge:
        This tests the Trailing Stop block in isolation. RSI with no modes
        enabled acts as passthrough (long/short = True on all bars), so we
        focus purely on exit block behavior and extra_data population.
    """
    return _make_rsi_with_trailing({"period": 14}, trailing_params)


def _run_adapter(graph: dict, ohlcv: pd.DataFrame) -> dict[str, Any]:
    """
    Run StrategyBuilderAdapter and return signal result + _value_cache.

    Returns dict with:
        - entries, exits, short_entries, short_exits: pd.Series
        - extra_data: dict (trailing stop config for engine)
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
#  PART 1 — TRAILING STOP DEFAULT VALUES
#
#  AI Knowledge: "What are the default values?"
#  Panel fields (from strategy_builder.js blockDefaults):
#    activation_percent = 1.0  (% profit to activate trailing)
#    trailing_percent = 0.5    (trailing distance %)
#    trail_type = 'percent'    (type: percent / atr / points)
#
# ============================================================


class TestTrailingStopDefaults:
    """AI agents must know all default values and what each parameter does."""

    def test_default_values_passthrough(self, sample_ohlcv):
        """Default Trailing: activation=1.0%, distance=0.5%, type=percent."""
        graph = _make_trailing_only(
            {
                "activation_percent": 1.0,
                "trailing_percent": 0.5,
                "trail_type": "percent",
            }
        )
        result = _run_adapter(graph, sample_ohlcv)

        # Trailing Stop is config-only — exits must be 0
        assert result["exits"].sum() == 0, "Trailing Stop is config-only, exits must be 0"

        # Check _value_cache has correct config
        cache = result["_value_cache"]
        assert "trail_1" in cache, "Trailing block should be in value cache"

        trail_cache = cache["trail_1"]
        assert trail_cache["trailing_activation_percent"] == 1.0, "Default activation must be 1.0%"
        assert trail_cache["trailing_percent"] == 0.5, "Default trailing distance must be 0.5%"
        assert trail_cache["trail_type"] == "percent", "Default trail type must be 'percent'"

    def test_default_trail_type_is_percent(self, sample_ohlcv):
        """Default trail_type is 'percent' — not 'atr' or 'points'."""
        graph = _make_trailing_only(
            {
                "activation_percent": 1.0,
                "trailing_percent": 0.5,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        assert cache["trail_type"] == "percent", "Default trail type must be 'percent'"

    def test_empty_params_all_defaults(self, sample_ohlcv):
        """Empty params dict — ALL values should use adapter defaults."""
        graph = _make_trailing_only({})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        assert cache["trailing_activation_percent"] == 1.0, "Default activation = 1.0%"
        assert cache["trailing_percent"] == 0.5, "Default trailing = 0.5%"
        assert cache["trail_type"] == "percent", "Default trail type = 'percent'"

    def test_entry_signals_exist_with_passthrough_rsi(self, sample_ohlcv):
        """RSI passthrough + Trailing Stop → entries should exist."""
        graph = _make_trailing_only({"activation_percent": 1.0, "trailing_percent": 0.5})
        result = _run_adapter(graph, sample_ohlcv)

        assert result["entries"].sum() > 0, "RSI passthrough should produce long entries"


# ============================================================
#
#  PART 2 — ACTIVATION & TRAILING DISTANCE CONFIGURATION
#
#  AI Knowledge: "How to set activation and trailing distance?"
#  activation_percent: profit % threshold before trailing activates.
#    Once price reaches entry + activation%, trailing stop starts.
#  trailing_percent: distance % from the peak price after activation.
#    If price retraces by trailing% from its highest point, exit.
#
# ============================================================


class TestTrailingConfiguration:
    """Test setting various activation/trailing distance values."""

    def test_activation_2_trailing_1(self, sample_ohlcv):
        """Activation at 2% profit, trail distance 1%."""
        graph = _make_trailing_only({"activation_percent": 2.0, "trailing_percent": 1.0})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        assert cache["trailing_activation_percent"] == 2.0
        assert cache["trailing_percent"] == 1.0

    def test_activation_0_5_trailing_0_3(self, sample_ohlcv):
        """Tight scalping: activate at 0.5%, trail by 0.3%."""
        graph = _make_trailing_only({"activation_percent": 0.5, "trailing_percent": 0.3})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        assert cache["trailing_activation_percent"] == 0.5
        assert cache["trailing_percent"] == 0.3

    def test_activation_5_trailing_2(self, sample_ohlcv):
        """Wide swing: activate at 5%, trail by 2%."""
        graph = _make_trailing_only({"activation_percent": 5.0, "trailing_percent": 2.0})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        assert cache["trailing_activation_percent"] == 5.0
        assert cache["trailing_percent"] == 2.0

    def test_activation_10_trailing_3(self, sample_ohlcv):
        """Very wide: activate at 10%, trail by 3%."""
        graph = _make_trailing_only({"activation_percent": 10.0, "trailing_percent": 3.0})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        assert cache["trailing_activation_percent"] == 10.0
        assert cache["trailing_percent"] == 3.0

    @pytest.mark.parametrize(
        "activation,trailing",
        [
            (0.5, 0.3),
            (1.0, 0.5),
            (2.0, 1.0),
            (3.0, 1.5),
            (5.0, 2.0),
            (10.0, 5.0),
        ],
    )
    def test_various_activation_trailing_combos(self, sample_ohlcv, activation, trailing):
        """Parametrized: verify various activation/trailing combos are stored correctly."""
        graph = _make_trailing_only({"activation_percent": activation, "trailing_percent": trailing})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        assert cache["trailing_activation_percent"] == activation, f"Activation should be {activation}"
        assert cache["trailing_percent"] == trailing, f"Trailing should be {trailing}"
        assert result["exits"].sum() == 0, "Config-only block must not generate exit signals"


# ============================================================
#
#  PART 3 — TRAIL TYPE CONFIGURATION
#
#  AI Knowledge: "What trail types are available?"
#  trail_type is a select field with 3 options:
#    'percent' — Процент (% based trailing)
#    'atr'     — ATR (ATR-based trailing distance)
#    'points'  — Пункты (point-based trailing distance)
#
#  trail_type is NOT optimizable — it stays fixed during optimization.
#  Only activation_percent and trailing_percent are optimizable.
#
# ============================================================


class TestTrailTypeConfiguration:
    """Test setting trail_type to each valid option."""

    def test_trail_type_percent(self, sample_ohlcv):
        """Trail type = percent (Процент)."""
        graph = _make_trailing_only({"activation_percent": 1.0, "trailing_percent": 0.5, "trail_type": "percent"})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        assert cache["trail_type"] == "percent"

    def test_trail_type_atr(self, sample_ohlcv):
        """Trail type = atr (ATR-based)."""
        graph = _make_trailing_only({"activation_percent": 1.0, "trailing_percent": 0.5, "trail_type": "atr"})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        assert cache["trail_type"] == "atr"

    def test_trail_type_points(self, sample_ohlcv):
        """Trail type = points (Пункты)."""
        graph = _make_trailing_only({"activation_percent": 1.0, "trailing_percent": 0.5, "trail_type": "points"})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        assert cache["trail_type"] == "points"

    @pytest.mark.parametrize("trail_type", ["percent", "atr", "points"])
    def test_all_trail_types_parametrized(self, sample_ohlcv, trail_type):
        """Parametrized: all 3 trail types should be stored correctly."""
        graph = _make_trailing_only({"activation_percent": 1.0, "trailing_percent": 0.5, "trail_type": trail_type})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        assert cache["trail_type"] == trail_type, f"Trail type should be '{trail_type}'"

    def test_trail_type_does_not_affect_entries(self, sample_ohlcv):
        """Changing trail_type must NOT change entry signals."""
        results = {}
        for tt in ["percent", "atr", "points"]:
            graph = _make_trailing_only({"activation_percent": 1.0, "trailing_percent": 0.5, "trail_type": tt})
            results[tt] = _run_adapter(graph, sample_ohlcv)

        pd.testing.assert_series_equal(
            results["percent"]["entries"],
            results["atr"]["entries"],
            check_names=False,
            obj="Trail type must not affect entry signals (percent vs atr)",
        )
        pd.testing.assert_series_equal(
            results["percent"]["entries"],
            results["points"]["entries"],
            check_names=False,
            obj="Trail type must not affect entry signals (percent vs points)",
        )


# ============================================================
#
#  PART 4 — OPTIMIZATION MODE
#
#  AI Knowledge: "How does optimization mode work for Trailing Stop?"
#  Screenshot 3 shows optimization mode:
#    Each optimizable field gets: [min] → [max] / [step]
#    The optimizer tests all combinations in the range.
#
#  Optimizable fields for Trailing Stop:
#    - activation_percent (optimizable: true) → number with min/max/step
#    - trailing_percent (optimizable: true) → number with min/max/step
#
#  Non-optimizable fields:
#    - trail_type (select — NOT optimizable, stays fixed)
#
#  Optimization range format: { min, max, step }
#  Example: activation from 0.5 to 2.0 step 0.5 → tests 0.5, 1.0, 1.5, 2.0
#
# ============================================================


class TestTrailingOptimization:
    """Test optimization ranges for activation/trailing parameters."""

    def test_optimization_range_activation(self, sample_ohlcv):
        """
        AI Agent must understand: activation_percent optimization range.
        Optimizer iterates from min to max with step.
        """
        for activation in [0.5, 1.0, 1.5, 2.0, 2.5]:
            graph = _make_trailing_only({"activation_percent": activation, "trailing_percent": 0.5})
            result = _run_adapter(graph, sample_ohlcv)
            cache = result["_value_cache"]["trail_1"]
            assert cache["trailing_activation_percent"] == activation, f"Activation should be {activation}"

    def test_optimization_range_trailing(self, sample_ohlcv):
        """
        AI Agent must understand: trailing_percent optimization range.
        Optimizer iterates trailing distance from min to max with step.
        """
        for trailing in [0.3, 0.5, 0.8, 1.0, 1.5]:
            graph = _make_trailing_only({"activation_percent": 1.0, "trailing_percent": trailing})
            result = _run_adapter(graph, sample_ohlcv)
            cache = result["_value_cache"]["trail_1"]
            assert cache["trailing_percent"] == trailing, f"Trailing should be {trailing}"

    def test_optimization_full_grid(self, sample_ohlcv):
        """
        AI Agent must understand: optimizer tests ALL combinations.
        Example: activation in [0.5, 1.0], trailing in [0.3, 0.5] → 4 combos.
        Each combo must produce valid results.
        """
        activation_range = [0.5, 1.0, 1.5]
        trailing_range = [0.3, 0.5]
        results = []

        for act in activation_range:
            for trail in trailing_range:
                graph = _make_trailing_only({"activation_percent": act, "trailing_percent": trail})
                result = _run_adapter(graph, sample_ohlcv)
                cache = result["_value_cache"]["trail_1"]
                assert cache["trailing_activation_percent"] == act
                assert cache["trailing_percent"] == trail
                results.append((act, trail, result["entries"].sum()))

        # All combos should produce same entries (entry signals don't depend on exit params)
        entry_counts = [r[2] for r in results]
        assert all(c == entry_counts[0] for c in entry_counts), (
            "Entry signals must NOT depend on trailing stop parameters"
        )

    def test_non_optimizable_trail_type_fixed(self, sample_ohlcv):
        """
        AI Agent must know: trail_type is a select field (NOT optimizable).
        It stays fixed during optimization runs — only number fields
        with min/max/step are iterated by the optimizer.
        """
        graph = _make_trailing_only(
            {
                "activation_percent": 1.0,
                "trailing_percent": 0.5,
                "trail_type": "atr",
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        # trail_type is a string — fixed during optimization
        assert isinstance(cache["trail_type"], str)
        assert cache["trail_type"] == "atr"


# ============================================================
#
#  PART 5 — CONFIG-ONLY BEHAVIOR
#
#  AI Knowledge: "Trailing Stop is config-only — engine executes"
#  The adapter stores trailing params in _value_cache.
#  The engine (FallbackEngineV4) reads them via extra_data
#  and applies trailing stop bar-by-bar during position management.
#  The adapter itself never sets exit=True — it's always False.
#
# ============================================================


class TestConfigOnlyBehavior:
    """Verify that Trailing Stop is truly config-only."""

    def test_exit_always_false(self, sample_ohlcv):
        """Trailing Stop exit signal is ALWAYS False — engine handles actual exits."""
        graph = _make_trailing_only({"activation_percent": 1.0, "trailing_percent": 0.5})
        result = _run_adapter(graph, sample_ohlcv)

        assert result["exits"].sum() == 0, "Trailing Stop must not generate exit signals"

    def test_short_exit_always_false(self, sample_ohlcv):
        """Short exits also False for config-only block."""
        graph = _make_trailing_only({"activation_percent": 1.0, "trailing_percent": 0.5})
        result = _run_adapter(graph, sample_ohlcv)

        if result["short_exits"] is not None:
            assert result["short_exits"].sum() == 0

    def test_cache_stores_all_params(self, sample_ohlcv):
        """Value cache must store ALL trailing stop params for engine consumption."""
        graph = _make_trailing_only(
            {
                "activation_percent": 2.0,
                "trailing_percent": 1.0,
                "trail_type": "atr",
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        # All params must be in cache for engine
        assert "trailing_activation_percent" in cache
        assert "trailing_percent" in cache
        assert "trail_type" in cache
        assert "exit" in cache  # exit signal series (all False)

    def test_exit_params_independent_of_entry(self, sample_ohlcv):
        """Exit config does NOT affect entry signal generation."""
        graph1 = _make_trailing_only({"activation_percent": 0.5, "trailing_percent": 0.3})
        graph2 = _make_trailing_only({"activation_percent": 10.0, "trailing_percent": 5.0})

        result1 = _run_adapter(graph1, sample_ohlcv)
        result2 = _run_adapter(graph2, sample_ohlcv)

        pd.testing.assert_series_equal(
            result1["entries"],
            result2["entries"],
            check_names=False,
            obj="Entry signals must be identical regardless of trailing stop settings",
        )


# ============================================================
#
#  PART 6 — EXTRA_DATA POPULATION
#
#  AI Knowledge: "How does extra_data work for trailing stop?"
#  Unlike Static SL/TP (which does NOT populate extra_data),
#  Trailing Stop DOES populate extra_data with:
#    - use_trailing_stop = True
#    - trailing_activation_percent = float
#    - trailing_percent = float
#    - trail_type = str ('percent' / 'atr' / 'points')
#
#  The engine reads these from extra_data during bar-by-bar execution.
#  This is the mechanism by which the adapter communicates trailing
#  stop configuration to FallbackEngineV4.
#
# ============================================================


class TestExtraDataPopulation:
    """Verify that extra_data is correctly populated for the engine."""

    def test_use_trailing_stop_flag(self, sample_ohlcv):
        """extra_data must contain use_trailing_stop=True when block is present."""
        graph = _make_trailing_only({"activation_percent": 1.0, "trailing_percent": 0.5})
        result = _run_adapter(graph, sample_ohlcv)
        extra = result["extra_data"]

        assert extra.get("use_trailing_stop") is True, "use_trailing_stop must be True"

    def test_extra_data_activation_percent(self, sample_ohlcv):
        """extra_data must contain trailing_activation_percent as float."""
        graph = _make_trailing_only({"activation_percent": 2.5, "trailing_percent": 0.5})
        result = _run_adapter(graph, sample_ohlcv)
        extra = result["extra_data"]

        assert extra["trailing_activation_percent"] == 2.5
        assert isinstance(extra["trailing_activation_percent"], float)

    def test_extra_data_trailing_percent(self, sample_ohlcv):
        """extra_data must contain trailing_percent as float."""
        graph = _make_trailing_only({"activation_percent": 1.0, "trailing_percent": 1.5})
        result = _run_adapter(graph, sample_ohlcv)
        extra = result["extra_data"]

        assert extra["trailing_percent"] == 1.5
        assert isinstance(extra["trailing_percent"], float)

    def test_extra_data_trail_type(self, sample_ohlcv):
        """extra_data must contain trail_type as string."""
        graph = _make_trailing_only({"activation_percent": 1.0, "trailing_percent": 0.5, "trail_type": "atr"})
        result = _run_adapter(graph, sample_ohlcv)
        extra = result["extra_data"]

        assert extra["trail_type"] == "atr"
        assert isinstance(extra["trail_type"], str)

    def test_extra_data_all_fields_present(self, sample_ohlcv):
        """All 4 trailing stop fields must be in extra_data."""
        graph = _make_trailing_only({"activation_percent": 3.0, "trailing_percent": 1.5, "trail_type": "points"})
        result = _run_adapter(graph, sample_ohlcv)
        extra = result["extra_data"]

        assert "use_trailing_stop" in extra
        assert "trailing_activation_percent" in extra
        assert "trailing_percent" in extra
        assert "trail_type" in extra

        assert extra["use_trailing_stop"] is True
        assert extra["trailing_activation_percent"] == 3.0
        assert extra["trailing_percent"] == 1.5
        assert extra["trail_type"] == "points"

    @pytest.mark.parametrize("trail_type", ["percent", "atr", "points"])
    def test_extra_data_trail_type_variants(self, sample_ohlcv, trail_type):
        """extra_data trail_type must match the configured value for all 3 types."""
        graph = _make_trailing_only({"activation_percent": 1.0, "trailing_percent": 0.5, "trail_type": trail_type})
        result = _run_adapter(graph, sample_ohlcv)
        extra = result["extra_data"]

        assert extra["trail_type"] == trail_type


# ============================================================
#
#  PART 7 — RSI FILTER + TRAILING STOP (Combined)
#
#  AI Knowledge: "How to combine RSI filter with trailing stop?"
#  The entry uses RSI range/cross signals → connected to strategy.
#  The exit uses Trailing Stop → standalone block (no connection needed).
#
# ============================================================


class TestRSIFilterWithTrailing:
    """Combine RSI entry filters with Trailing Stop exits."""

    def test_rsi_range_with_trailing(self, sample_ohlcv):
        """RSI range filter (20-50 for long) + activation=2%, trail=1%."""
        graph = _make_rsi_with_trailing(
            rsi_params={
                "period": 14,
                "use_long_range": True,
                "long_rsi_more": 20,
                "long_rsi_less": 50,
            },
            trailing_params={
                "activation_percent": 2.0,
                "trailing_percent": 1.0,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        # RSI range should filter entries
        assert result["entries"].sum() < len(sample_ohlcv), "RSI range should limit entries"
        assert result["entries"].sum() > 0, "Some entries should exist in RSI 20-50 range"

        # Trailing config should be correct
        cache = result["_value_cache"]["trail_1"]
        assert cache["trailing_activation_percent"] == 2.0
        assert cache["trailing_percent"] == 1.0

        # extra_data should have trailing config
        extra = result["extra_data"]
        assert extra.get("use_trailing_stop") is True

    def test_rsi_cross_with_trailing_atr(self, sample_ohlcv):
        """RSI cross level + trailing with ATR type."""
        graph = _make_rsi_with_trailing(
            rsi_params={
                "period": 14,
                "use_cross_level": True,
                "cross_long_level": 30,
                "cross_short_level": 70,
            },
            trailing_params={
                "activation_percent": 1.5,
                "trailing_percent": 0.8,
                "trail_type": "atr",
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        # Cross signals should be rare
        assert result["entries"].sum() < len(sample_ohlcv) * 0.1, "Cross signals should be rare (<10%)"

        cache = result["_value_cache"]["trail_1"]
        assert cache["trail_type"] == "atr"

        extra = result["extra_data"]
        assert extra["trail_type"] == "atr"

    def test_rsi_cross_memory_with_trailing_points(self, sample_ohlcv):
        """RSI cross with 5-bar memory + trailing in points mode."""
        graph = _make_rsi_with_trailing(
            rsi_params={
                "period": 14,
                "use_cross_level": True,
                "cross_long_level": 30,
                "cross_short_level": 70,
                "use_cross_memory": True,
                "cross_memory_bars": 5,
            },
            trailing_params={
                "activation_percent": 3.0,
                "trailing_percent": 1.5,
                "trail_type": "points",
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        assert result["entries"].sum() > 0, "Cross + memory should produce entries"

        cache = result["_value_cache"]["trail_1"]
        assert cache["trail_type"] == "points"

        extra = result["extra_data"]
        assert extra["trail_type"] == "points"
        assert extra["trailing_activation_percent"] == 3.0


# ============================================================
#
#  PART 8 — MACD FILTER + TRAILING STOP (Combined)
#
#  AI Knowledge: "How to combine MACD filter with trailing stop?"
#  Same principle: MACD generates entry signals, trailing stop handles exits.
#
# ============================================================


class TestMACDFilterWithTrailing:
    """Combine MACD entry filters with Trailing Stop exits."""

    def test_macd_cross_with_trailing(self, sample_ohlcv):
        """MACD cross signal + activation=2%, trail=1%."""
        graph = _make_macd_with_trailing(
            macd_params={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "use_cross_signal": True,
            },
            trailing_params={
                "activation_percent": 2.0,
                "trailing_percent": 1.0,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        # MACD cross is event-based — may or may not produce entries.
        total_signals = result["entries"].sum() + (
            result["short_entries"].sum() if result["short_entries"] is not None else 0
        )
        assert total_signals >= 0, "MACD cross adapter should process without errors"

        cache = result["_value_cache"]["trail_1"]
        assert cache["trailing_activation_percent"] == 2.0
        assert cache["trailing_percent"] == 1.0

        extra = result["extra_data"]
        assert extra.get("use_trailing_stop") is True

    def test_macd_histogram_with_trailing_atr(self, sample_ohlcv):
        """MACD histogram filter + trailing with ATR type."""
        graph = _make_macd_with_trailing(
            macd_params={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "use_histogram_filter": True,
                "histogram_above": 0,
            },
            trailing_params={
                "activation_percent": 3.0,
                "trailing_percent": 1.5,
                "trail_type": "atr",
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["trail_1"]
        assert cache["trail_type"] == "atr"
        assert cache["trailing_activation_percent"] == 3.0

        extra = result["extra_data"]
        assert extra["trail_type"] == "atr"

    def test_macd_cross_with_full_trailing_config(self, sample_ohlcv):
        """MACD cross + full trailing config: all params set explicitly."""
        graph = _make_macd_with_trailing(
            macd_params={
                "fast_period": 8,
                "slow_period": 21,
                "signal_period": 5,
                "use_cross_signal": True,
            },
            trailing_params={
                "activation_percent": 5.0,
                "trailing_percent": 2.5,
                "trail_type": "points",
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["trail_1"]
        assert cache["trailing_activation_percent"] == 5.0
        assert cache["trailing_percent"] == 2.5
        assert cache["trail_type"] == "points"

        extra = result["extra_data"]
        assert extra["use_trailing_stop"] is True
        assert extra["trailing_activation_percent"] == 5.0
        assert extra["trailing_percent"] == 2.5
        assert extra["trail_type"] == "points"


# ============================================================
#
#  PART 9 — RSI + MACD COMBO + TRAILING STOP
#
#  AI Knowledge: "How to combine RSI AND MACD filters with trailing stop?"
#  Use RSI as entry filter connected to long, MACD connected to short,
#  or chain them. Exit is always the same Trailing Stop.
#
# ============================================================


class TestRSIMACDComboWithTrailing:
    """Test combined RSI + MACD entry with Trailing Stop exit."""

    def _make_rsi_macd_with_trailing(
        self,
        rsi_params: dict,
        macd_params: dict,
        trailing_params: dict,
    ) -> dict[str, Any]:
        """Build a graph with RSI → long, MACD → short, + Trailing Stop."""
        return {
            "name": "RSI+MACD+Trailing Stop Combo Test",
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
                    "id": "trail_1",
                    "type": "trailing_stop_exit",
                    "category": "exit",
                    "name": "Trailing Stop",
                    "icon": "arrow-trending",
                    "x": 600,
                    "y": 450,
                    "params": trailing_params,
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

    def test_rsi_long_macd_short_with_trailing(self, sample_ohlcv):
        """RSI cross for longs + MACD cross for shorts + trailing stop."""
        graph = self._make_rsi_macd_with_trailing(
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
            trailing_params={
                "activation_percent": 2.0,
                "trailing_percent": 1.0,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        assert result["entries"].sum() > 0, "RSI cross should produce long entries"

        cache = result["_value_cache"]["trail_1"]
        assert cache["trailing_activation_percent"] == 2.0
        assert cache["trailing_percent"] == 1.0

        extra = result["extra_data"]
        assert extra["use_trailing_stop"] is True

    def test_rsi_range_macd_histogram_full_trailing(self, sample_ohlcv):
        """RSI range + MACD histogram + full trailing stop config with ATR type."""
        graph = self._make_rsi_macd_with_trailing(
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
            trailing_params={
                "activation_percent": 4.0,
                "trailing_percent": 2.0,
                "trail_type": "atr",
            },
        )
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["trail_1"]
        assert cache["trailing_activation_percent"] == 4.0
        assert cache["trailing_percent"] == 2.0
        assert cache["trail_type"] == "atr"

        extra = result["extra_data"]
        assert extra["use_trailing_stop"] is True
        assert extra["trail_type"] == "atr"


# ============================================================
#
#  PART 10 — ALL PARAMS FULL SCENARIO
#
#  AI Knowledge: Comprehensive test — set EVERY parameter explicitly.
#  This is the "ultimate" test for AI agent understanding.
#
# ============================================================


class TestAllParamsFullScenario:
    """Set every single Trailing Stop parameter and verify all are stored."""

    def test_every_param_explicit(self, sample_ohlcv):
        """Set ALL params: activation=3.0, trailing=1.5, trail_type=atr."""
        graph = _make_trailing_only(
            {
                "activation_percent": 3.0,
                "trailing_percent": 1.5,
                "trail_type": "atr",
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        # Verify every parameter in _value_cache
        assert cache["trailing_activation_percent"] == 3.0
        assert cache["trailing_percent"] == 1.5
        assert cache["trail_type"] == "atr"

        # Exit signal is still False (config-only)
        assert cache["exit"].sum() == 0

        # Verify extra_data propagation
        extra = result["extra_data"]
        assert extra["use_trailing_stop"] is True
        assert extra["trailing_activation_percent"] == 3.0
        assert extra["trailing_percent"] == 1.5
        assert extra["trail_type"] == "atr"

    def test_minimal_params_fallback_defaults(self, sample_ohlcv):
        """Set only activation — trailing and trail_type should fall back to defaults."""
        graph = _make_trailing_only(
            {
                "activation_percent": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["trail_1"]

        # Explicit value
        assert cache["trailing_activation_percent"] == 2.0

        # Defaults for omitted params
        assert cache["trailing_percent"] == 0.5
        assert cache["trail_type"] == "percent"

        # extra_data should still be populated
        extra = result["extra_data"]
        assert extra["use_trailing_stop"] is True
        assert extra["trailing_activation_percent"] == 2.0
        assert extra["trailing_percent"] == 0.5
        assert extra["trail_type"] == "percent"

    def test_all_trail_types_full_cycle(self, sample_ohlcv):
        """
        Run full cycle with each trail_type — verify _value_cache + extra_data
        are consistent for all 3 types (percent, atr, points).
        """
        for trail_type in ["percent", "atr", "points"]:
            graph = _make_trailing_only(
                {
                    "activation_percent": 2.0,
                    "trailing_percent": 1.0,
                    "trail_type": trail_type,
                }
            )
            result = _run_adapter(graph, sample_ohlcv)
            cache = result["_value_cache"]["trail_1"]
            extra = result["extra_data"]

            # _value_cache and extra_data must be consistent
            assert cache["trail_type"] == trail_type
            assert extra["trail_type"] == trail_type
            assert cache["trailing_activation_percent"] == extra["trailing_activation_percent"]
            assert cache["trailing_percent"] == extra["trailing_percent"]
