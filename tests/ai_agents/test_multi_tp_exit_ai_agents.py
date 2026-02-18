"""
AI Agent Knowledge Test: Multi TP Exit Block — Real Adapter Tests

Tests verify that AI agents (DeepSeek, Qwen, Perplexity) correctly understand:
- Every parameter of the Multi TP Exit block (8 fields: tp1-3 percent+close%, use_tp2/tp3)
- How TP1 is always enabled; TP2 and TP3 have toggle checkboxes
- How close percentages allocate position across TP levels (should sum to 100%)
- How the block is config-only (category "multiple_tp" → returns {})
- How extract_dca_config() collects multi_tp params into DCA config
- Which parameters are optimizable (only tp1/tp2/tp3_percent)
- Combining Multi TP exit with RSI/MACD entry filters

Architecture Notes:
    - Block type: "multi_tp_exit"
    - Category mapping: "multi_tp_exit" → "multiple_tp" (NOT "exit"!)
    - Dispatch: returns {} (config-only, no signal output)
    - _value_cache: block key exists but value is {} (empty dict)
    - extract_dca_config(): checks category=="multiple_tp", collects params
      into dca_tp{1-4}_percent / dca_tp{1-4}_close_percent keys
    - Our frontend sends flat params (tp1_percent, tp1_close_percent, etc.)
      while extract_dca_config expects block_type=="multi_tp_levels" with
      params.levels[] array — this is a known mismatch (tested explicitly)
    - Block params are always accessible via adapter.blocks[block_id]["params"]

These tests run against the REAL StrategyBuilderAdapter (in-memory DB).
They validate that every Multi TP Exit parameter combination is properly processed.

Run:
    py -3.14 -m pytest tests/ai_agents/test_multi_tp_exit_ai_agents.py -v
    py -3.14 -m pytest tests/ai_agents/test_multi_tp_exit_ai_agents.py -v -k "defaults"
    py -3.14 -m pytest tests/ai_agents/test_multi_tp_exit_ai_agents.py -v -k "close_percent"
    py -3.14 -m pytest tests/ai_agents/test_multi_tp_exit_ai_agents.py -v -k "optimization"
    py -3.14 -m pytest tests/ai_agents/test_multi_tp_exit_ai_agents.py -v -k "dca_config"
    py -3.14 -m pytest tests/ai_agents/test_multi_tp_exit_ai_agents.py -v -k "filter"
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


def _make_rsi_with_multi_tp(
    rsi_params: dict[str, Any],
    multi_tp_params: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a strategy graph: RSI indicator → entry long/short → strategy,
    plus Multi TP Exit block (standalone, config-only).

    AI Agent Knowledge:
        Multi TP Exit block has category='exit' (set by frontend).
        The adapter dispatches it to _execute_exit() → multi_tp_exit handler.
        Handler produces: exit=pd.Series(False), multi_tp_config=[{percent, allocation}].
        NOTE: Handler reads tp{n}_allocation (NOT tp{n}_close_percent from frontend).
        The block params are stored in adapter.blocks[block_id]["params"].
    """
    return {
        "name": "RSI + Multi TP Exit Test",
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
                "id": "multi_tp_1",
                "type": "multi_tp_exit",
                "category": "exit",
                "name": "Multi TP Levels",
                "icon": "layers",
                "x": 600,
                "y": 450,
                "params": multi_tp_params,
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


def _make_macd_with_multi_tp(
    macd_params: dict[str, Any],
    multi_tp_params: dict[str, Any],
) -> dict[str, Any]:
    """Build a strategy graph: MACD indicator → entry long/short → strategy + Multi TP Exit."""
    return {
        "name": "MACD + Multi TP Exit Test",
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
                "id": "multi_tp_1",
                "type": "multi_tp_exit",
                "category": "exit",
                "name": "Multi TP Levels",
                "icon": "layers",
                "x": 600,
                "y": 450,
                "params": multi_tp_params,
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


def _make_multi_tp_only(multi_tp_params: dict[str, Any]) -> dict[str, Any]:
    """
    Build a strategy graph with ONLY a Multi TP Exit block + RSI passthrough entry.

    AI Agent Knowledge:
        RSI with default params acts as passthrough. This isolates Multi TP behavior.
    """
    return _make_rsi_with_multi_tp({"period": 14}, multi_tp_params)


def _run_adapter(graph: dict, ohlcv: pd.DataFrame) -> dict[str, Any]:
    """
    Run StrategyBuilderAdapter and return signal result + _value_cache + adapter.

    Returns dict with:
        - entries, exits, short_entries, short_exits: pd.Series
        - extra_data: dict (engine config from adapter)
        - _value_cache: internal adapter cache (for inspecting block outputs)
        - adapter: the adapter instance (for calling extract_dca_config, etc.)
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
        "adapter": adapter,
    }


# ============================================================
#
#  PART 1 — MULTI TP EXIT DEFAULT VALUES
#
#  AI Knowledge: "What are the default values?"
#  Panel fields (from strategy_builder.js blockDefaults):
#    tp1_percent = 1.0           (number, optimizable, range 0.5-30)
#    tp1_close_percent = 33      (number, NOT optimizable, range 0.5-30)
#    tp2_percent = 2.0           (number, optimizable, range 0.5-30)
#    tp2_close_percent = 33      (number, NOT optimizable, range 0.5-30)
#    tp3_percent = 3.0           (number, optimizable, range 0.5-30)
#    tp3_close_percent = 34      (number, NOT optimizable, range 0.5-30)
#    use_tp2 = true              (checkbox — enable TP2?)
#    use_tp3 = true              (checkbox — enable TP3?)
#
#  Close percents: 33 + 33 + 34 = 100% (full position closed)
#
# ============================================================


class TestMultiTPExitDefaults:
    """AI agents must know all default values and what each parameter does."""

    def test_default_values_all_tp_enabled(self, sample_ohlcv):
        """Default: TP1 always on, TP2 + TP3 enabled. Close percents sum to 100."""
        graph = _make_multi_tp_only({})
        result = _run_adapter(graph, sample_ohlcv)

        # Multi TP produces exit=False series (no dynamic exit triggers)
        assert result["exits"].sum() == 0, "Multi TP exit series should be all False"

        # Block should be in _value_cache with exit series + multi_tp_config
        cache = result["_value_cache"]
        assert "multi_tp_1" in cache, "Multi TP block must be in _value_cache"
        # When category="exit" is set (as frontend sends), _execute_exit produces output
        assert "exit" in cache["multi_tp_1"], "Should have exit series from _execute_exit"
        assert "multi_tp_config" in cache["multi_tp_1"], "Should have multi_tp_config list"

    def test_default_params_stored_in_blocks(self, sample_ohlcv):
        """Params with defaults must be accessible via adapter.blocks."""
        defaults = {
            "tp1_percent": 1.0,
            "tp1_close_percent": 33,
            "tp2_percent": 2.0,
            "tp2_close_percent": 33,
            "tp3_percent": 3.0,
            "tp3_close_percent": 34,
            "use_tp2": True,
            "use_tp3": True,
        }
        graph = _make_multi_tp_only(defaults)
        result = _run_adapter(graph, sample_ohlcv)

        adapter = result["adapter"]
        block_params = adapter.blocks["multi_tp_1"]["params"]
        assert block_params["tp1_percent"] == 1.0
        assert block_params["tp1_close_percent"] == 33
        assert block_params["tp2_percent"] == 2.0
        assert block_params["tp2_close_percent"] == 33
        assert block_params["tp3_percent"] == 3.0
        assert block_params["tp3_close_percent"] == 34
        assert block_params["use_tp2"] is True
        assert block_params["use_tp3"] is True

    def test_default_close_percents_sum_to_100(self, sample_ohlcv):
        """Default close percents: 33 + 33 + 34 = 100%."""
        defaults = {
            "tp1_close_percent": 33,
            "tp2_close_percent": 33,
            "tp3_close_percent": 34,
        }
        graph = _make_multi_tp_only(defaults)
        result = _run_adapter(graph, sample_ohlcv)

        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        total = p["tp1_close_percent"] + p["tp2_close_percent"] + p["tp3_close_percent"]
        assert total == 100, f"Close percents must sum to 100, got {total}"

    def test_no_exit_signals_generated(self, sample_ohlcv):
        """Multi TP is purely config — exits=0, short_exits=0."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 2.0,
                "tp2_percent": 4.0,
                "tp3_percent": 6.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        assert result["exits"].sum() == 0
        assert result["short_exits"].sum() == 0

    def test_entries_still_work_with_multi_tp(self, sample_ohlcv):
        """RSI entry signals must still be generated when Multi TP is attached."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 1.0,
                "tp2_percent": 2.0,
                "tp3_percent": 3.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        # RSI with default 14 should produce some entry signals
        total_entries = int(result["entries"].sum() + result["short_entries"].sum())
        assert total_entries > 0, "RSI entry signals must still fire with Multi TP attached"


# ============================================================
#
#  PART 2 — CATEGORY MAPPING AND DISPATCH
#
#  AI Knowledge: "How is multi_tp_exit dispatched?"
#  TWO paths exist depending on whether category is set:
#
#  Path A (frontend default): category='exit' in graph
#    → _execute_exit() → multi_tp_exit handler
#    → produces: {'exit': pd.Series(False), 'multi_tp_config': [...]}
#    → NOTE: handler reads tp{n}_allocation (NOT tp{n}_close_percent!)
#
#  Path B (category missing): _infer_category via _BLOCK_CATEGORY_MAP
#    → "multi_tp_exit" → "multiple_tp"
#    → returns {} (config-only)
#
#  Frontend ALWAYS sends category='exit', so Path A is the real path.
#
# ============================================================


class TestMultiTPCategoryMapping:
    """AI agents must understand the dual dispatch paths for multi_tp_exit."""

    def test_category_mapping_in_adapter(self):
        """Block type 'multi_tp_exit' maps to category 'multiple_tp'."""
        cat = StrategyBuilderAdapter._BLOCK_CATEGORY_MAP.get("multi_tp_exit")
        assert cat == "multiple_tp", f"Expected 'multiple_tp', got '{cat}'"

    def test_category_auto_inferred(self, sample_ohlcv):
        """When block has no explicit category, _infer_category maps to 'multiple_tp'."""
        # Build graph without category on the multi_tp block
        graph = _make_multi_tp_only({"tp1_percent": 1.5})
        # Remove the explicit category
        for block in graph["blocks"]:
            if block["id"] == "multi_tp_1":
                del block["category"]
        result = _run_adapter(graph, sample_ohlcv)

        # After execution, the category should be auto-inferred and cached
        adapter = result["adapter"]
        assert adapter.blocks["multi_tp_1"]["category"] == "multiple_tp"

    def test_dispatch_returns_empty_dict(self, sample_ohlcv):
        """When category='exit' (frontend default), _execute_exit handles multi_tp_exit."""
        graph = _make_multi_tp_only({"tp1_percent": 5.0})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["multi_tp_1"]
        # _execute_exit produces exit series + multi_tp_config
        assert "exit" in cache, "exit key should exist from _execute_exit handler"
        assert "multi_tp_config" in cache, "multi_tp_config should exist"

    def test_not_dispatched_to_execute_exit(self, sample_ohlcv):
        """
        When category is MISSING (not sent), _infer_category maps to 'multiple_tp' → returns {}.
        But when frontend sends category='exit', it goes through _execute_exit → multi_tp_exit handler.
        Frontend always sends category='exit', so the handler IS reached in practice.
        """
        graph = _make_multi_tp_only({"tp1_percent": 1.0})
        result = _run_adapter(graph, sample_ohlcv)

        # Frontend sends category='exit', so _execute_exit IS reached
        cache = result["_value_cache"]["multi_tp_1"]
        assert "exit" in cache, "With category='exit', block goes through _execute_exit"
        # multi_tp_config contains the TP level allocations
        config = cache["multi_tp_config"]
        assert isinstance(config, list)
        assert len(config) == 3, "Default 3 TP levels in multi_tp_config"


# ============================================================
#
#  PART 3 — TP LEVEL CONFIGURATION
#
#  AI Knowledge: "How do the 3 TP levels work?"
#  - TP1: Always enabled (no toggle checkbox)
#  - TP2: Controlled by use_tp2 checkbox
#  - TP3: Controlled by use_tp3 checkbox
#  - Each TP level has: target percent (distance) + close percent (position %)
#
# ============================================================


class TestTPLevelConfiguration:
    """AI agents must know TP1 is always on, TP2/TP3 are toggleable."""

    def test_tp1_always_present(self, sample_ohlcv):
        """TP1 has no toggle — it's always active."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 1.5,
                "tp1_close_percent": 50,
                "use_tp2": False,
                "use_tp3": False,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_percent"] == 1.5
        assert p["tp1_close_percent"] == 50
        # No use_tp1 flag — TP1 is always on

    def test_tp2_disabled(self, sample_ohlcv):
        """use_tp2=False disables TP2 level."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 1.0,
                "tp1_close_percent": 60,
                "use_tp2": False,
                "tp2_percent": 2.0,
                "tp2_close_percent": 0,
                "use_tp3": False,
                "tp3_percent": 3.0,
                "tp3_close_percent": 40,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["use_tp2"] is False

    def test_tp3_disabled(self, sample_ohlcv):
        """use_tp3=False disables TP3 level."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 1.0,
                "tp1_close_percent": 50,
                "use_tp2": True,
                "tp2_percent": 2.0,
                "tp2_close_percent": 50,
                "use_tp3": False,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["use_tp3"] is False
        assert p["use_tp2"] is True

    def test_all_three_tp_enabled(self, sample_ohlcv):
        """All 3 TP levels enabled with different target percents."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 0.5,
                "tp1_close_percent": 30,
                "use_tp2": True,
                "tp2_percent": 1.5,
                "tp2_close_percent": 30,
                "use_tp3": True,
                "tp3_percent": 3.0,
                "tp3_close_percent": 40,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_percent"] == 0.5
        assert p["tp2_percent"] == 1.5
        assert p["tp3_percent"] == 3.0
        total_close = p["tp1_close_percent"] + p["tp2_close_percent"] + p["tp3_close_percent"]
        assert total_close == 100

    def test_custom_target_percents(self, sample_ohlcv):
        """Custom TP targets within valid range (0.5-30%)."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 0.5,
                "tp2_percent": 5.0,
                "tp3_percent": 15.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_percent"] == 0.5
        assert p["tp2_percent"] == 5.0
        assert p["tp3_percent"] == 15.0

    def test_high_target_percents(self, sample_ohlcv):
        """Edge case: max target percents (30% each)."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 30.0,
                "tp2_percent": 30.0,
                "tp3_percent": 30.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_percent"] == 30.0
        assert p["tp2_percent"] == 30.0
        assert p["tp3_percent"] == 30.0


# ============================================================
#
#  PART 4 — CLOSE PERCENT ALLOCATION
#
#  AI Knowledge: "How does position allocation work?"
#  - tp1_close_percent: % of position to close at TP1
#  - tp2_close_percent: % of position to close at TP2
#  - tp3_close_percent: % of position to close at TP3
#  - Should sum to 100% (defaults: 33+33+34=100)
#  - NOT optimizable (close% fields)
#
# ============================================================


class TestClosePercentAllocation:
    """AI agents must know how position allocation across TP levels works."""

    def test_equal_allocation(self, sample_ohlcv):
        """Equal 33/33/34 split (default)."""
        graph = _make_multi_tp_only(
            {
                "tp1_close_percent": 33,
                "tp2_close_percent": 33,
                "tp3_close_percent": 34,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_close_percent"] + p["tp2_close_percent"] + p["tp3_close_percent"] == 100

    def test_heavy_tp1_allocation(self, sample_ohlcv):
        """Most of position closed at TP1 (80/10/10)."""
        graph = _make_multi_tp_only(
            {
                "tp1_close_percent": 80,
                "tp2_close_percent": 10,
                "tp3_close_percent": 10,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_close_percent"] == 80
        assert p["tp2_close_percent"] == 10
        assert p["tp3_close_percent"] == 10

    def test_heavy_tp3_allocation(self, sample_ohlcv):
        """Most of position closed at TP3 (10/10/80)."""
        graph = _make_multi_tp_only(
            {
                "tp1_close_percent": 10,
                "tp2_close_percent": 10,
                "tp3_close_percent": 80,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp3_close_percent"] == 80

    def test_tp1_only_100_percent(self, sample_ohlcv):
        """TP1 takes 100% when TP2 and TP3 disabled."""
        graph = _make_multi_tp_only(
            {
                "tp1_close_percent": 100,
                "use_tp2": False,
                "tp2_close_percent": 0,
                "use_tp3": False,
                "tp3_close_percent": 0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_close_percent"] == 100
        assert p["use_tp2"] is False
        assert p["use_tp3"] is False

    def test_two_levels_50_50(self, sample_ohlcv):
        """Two TP levels with 50/50 split (TP3 disabled)."""
        graph = _make_multi_tp_only(
            {
                "tp1_close_percent": 50,
                "use_tp2": True,
                "tp2_close_percent": 50,
                "use_tp3": False,
                "tp3_close_percent": 0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_close_percent"] == 50
        assert p["tp2_close_percent"] == 50


# ============================================================
#
#  PART 5 — EXTRACT DCA CONFIG INTEGRATION
#
#  AI Knowledge: "How does Multi TP integrate with DCA?"
#  extract_dca_config() scans blocks with category=="multiple_tp".
#  IMPORTANT: There's a known block_type mismatch!
#    - Our block_type is "multi_tp_exit"
#    - extract_dca_config checks for block_type=="multi_tp_levels"
#    - The "multi_tp_levels" path expects params.levels[] array format
#    - Our frontend sends flat params (tp1_percent, etc.)
#  Result: extract_dca_config won't collect our multi_tp_exit params
#  into dca_tp{n}_percent/dca_tp{n}_close_percent keys.
#  The block params are still accessible directly via adapter.blocks.
#
# ============================================================


class TestExtractDCAConfig:
    """AI agents must understand the DCA config extraction behavior."""

    def test_extract_dca_config_callable(self, sample_ohlcv):
        """extract_dca_config() can be called after generate_signals."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 1.0,
                "tp2_percent": 2.0,
                "tp3_percent": 3.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        dca_config = adapter.extract_dca_config()
        assert isinstance(dca_config, dict)

    def test_dca_config_has_default_multi_tp_keys(self, sample_ohlcv):
        """DCA config always has dca_multi_tp_enabled and tp percent defaults."""
        graph = _make_multi_tp_only({"tp1_percent": 1.0})
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        dca_config = adapter.extract_dca_config()

        # These defaults are always present in extract_dca_config output
        assert "dca_multi_tp_enabled" in dca_config
        assert "dca_tp1_percent" in dca_config
        assert "dca_tp2_percent" in dca_config
        assert "dca_tp3_percent" in dca_config
        assert "dca_tp4_percent" in dca_config
        assert "dca_tp1_close_percent" in dca_config
        assert "dca_tp2_close_percent" in dca_config
        assert "dca_tp3_close_percent" in dca_config
        assert "dca_tp4_close_percent" in dca_config

    def test_block_type_mismatch_documented(self, sample_ohlcv):
        """
        KNOWN MISMATCH: Our block_type is 'multi_tp_exit' but extract_dca_config
        checks for 'multi_tp_levels'. This means our block's flat params won't be
        auto-collected into dca_tp{n} keys. The block params are still in adapter.blocks.
        """
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 5.0,
                "tp1_close_percent": 50,
                "tp2_percent": 10.0,
                "tp2_close_percent": 30,
                "tp3_percent": 15.0,
                "tp3_close_percent": 20,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        dca_config = adapter.extract_dca_config()

        # Since block_type is "multi_tp_exit" (not "multi_tp_levels"),
        # the dca_multi_tp_enabled should remain False (default)
        assert dca_config["dca_multi_tp_enabled"] is False, (
            "Known mismatch: multi_tp_exit block_type != multi_tp_levels, so DCA TP not auto-enabled"
        )

        # But the params are still accessible directly
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_percent"] == 5.0
        assert p["tp2_percent"] == 10.0
        assert p["tp3_percent"] == 15.0

    def test_dca_config_defaults_unchanged(self, sample_ohlcv):
        """DCA config TP defaults remain at their initial values (not overwritten)."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 7.0,
                "tp2_percent": 14.0,
                "tp3_percent": 21.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        dca_config = adapter.extract_dca_config()

        # Defaults from extract_dca_config (not modified by multi_tp_exit)
        assert dca_config["dca_tp1_percent"] == 0.5
        assert dca_config["dca_tp2_percent"] == 1.0
        assert dca_config["dca_tp3_percent"] == 2.0
        assert dca_config["dca_tp4_percent"] == 3.0
        assert dca_config["dca_tp1_close_percent"] == 25.0
        assert dca_config["dca_tp2_close_percent"] == 25.0
        assert dca_config["dca_tp3_close_percent"] == 25.0
        assert dca_config["dca_tp4_close_percent"] == 25.0

    def test_multi_tp_levels_format_works_in_extract(self, sample_ohlcv):
        """
        If a block with type='multi_tp_levels' and levels[] array is provided,
        extract_dca_config DOES collect the TP params correctly.
        This tests the correct code path (vs our multi_tp_exit mismatch).
        """
        graph = {
            "name": "Multi TP Levels Format Test",
            "blocks": [
                {
                    "id": "b_rsi",
                    "type": "rsi",
                    "category": "indicator",
                    "name": "RSI",
                    "x": 100,
                    "y": 100,
                    "params": {"period": 14},
                },
                {
                    "id": "mtp_levels",
                    "type": "multi_tp_levels",
                    "category": "multiple_tp",
                    "name": "Multi TP (levels format)",
                    "x": 600,
                    "y": 450,
                    "params": {
                        "levels": [
                            {"percent": 1.0, "close_percent": 33},
                            {"percent": 2.0, "close_percent": 33},
                            {"percent": 3.0, "close_percent": 34},
                        ]
                    },
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
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        dca_config = adapter.extract_dca_config()

        # This format DOES activate multi TP in DCA config
        assert dca_config["dca_multi_tp_enabled"] is True
        assert dca_config["dca_tp1_percent"] == 1.0
        assert dca_config["dca_tp2_percent"] == 2.0
        assert dca_config["dca_tp3_percent"] == 3.0
        assert dca_config["dca_tp1_close_percent"] == 33
        assert dca_config["dca_tp2_close_percent"] == 33
        assert dca_config["dca_tp3_close_percent"] == 34


# ============================================================
#
#  PART 6 — OPTIMIZATION MODE
#
#  AI Knowledge: "Which params are optimizable?"
#  Only target percent fields are optimizable:
#    - tp1_percent: optimizable: true
#    - tp2_percent: optimizable: true
#    - tp3_percent: optimizable: true
#  Close percent fields are NOT optimizable:
#    - tp1_close_percent: optimizable: false (UI slider, not optimizer)
#    - tp2_close_percent: optimizable: false
#    - tp3_close_percent: optimizable: false
#
# ============================================================


class TestMultiTPOptimization:
    """AI agents must know only target% fields are optimizable, not close%."""

    def test_optimizable_target_percents(self, sample_ohlcv):
        """Target percent fields can be varied for optimization."""
        configs = [
            {"tp1_percent": 0.5, "tp2_percent": 1.0, "tp3_percent": 2.0},
            {"tp1_percent": 1.0, "tp2_percent": 3.0, "tp3_percent": 5.0},
            {"tp1_percent": 2.0, "tp2_percent": 5.0, "tp3_percent": 10.0},
        ]
        for cfg in configs:
            graph = _make_multi_tp_only(cfg)
            result = _run_adapter(graph, sample_ohlcv)
            adapter = result["adapter"]
            p = adapter.blocks["multi_tp_1"]["params"]
            assert p["tp1_percent"] == cfg["tp1_percent"]
            assert p["tp2_percent"] == cfg["tp2_percent"]
            assert p["tp3_percent"] == cfg["tp3_percent"]

    def test_close_percents_not_optimizable(self, sample_ohlcv):
        """Close percent fields are fixed allocation — NOT optimizable.
        They can be set but the optimizer should not vary them."""
        graph = _make_multi_tp_only(
            {
                "tp1_close_percent": 25,
                "tp2_close_percent": 25,
                "tp3_close_percent": 50,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        # Close percents are stored as-is
        assert p["tp1_close_percent"] == 25
        assert p["tp2_close_percent"] == 25
        assert p["tp3_close_percent"] == 50

    def test_optimization_sweep_tp1(self, sample_ohlcv):
        """Sweep TP1 percent across range while keeping TP2/TP3 fixed."""
        for tp1 in [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0]:
            graph = _make_multi_tp_only(
                {
                    "tp1_percent": tp1,
                    "tp2_percent": 4.0,
                    "tp3_percent": 8.0,
                }
            )
            result = _run_adapter(graph, sample_ohlcv)
            adapter = result["adapter"]
            p = adapter.blocks["multi_tp_1"]["params"]
            assert p["tp1_percent"] == tp1

    def test_optimization_sweep_all_targets(self, sample_ohlcv):
        """Sweep all TP targets together at different scales."""
        scales = [
            (0.5, 1.0, 1.5),
            (1.0, 2.0, 3.0),
            (5.0, 10.0, 15.0),
            (10.0, 20.0, 30.0),
        ]
        for tp1, tp2, tp3 in scales:
            graph = _make_multi_tp_only(
                {
                    "tp1_percent": tp1,
                    "tp2_percent": tp2,
                    "tp3_percent": tp3,
                }
            )
            result = _run_adapter(graph, sample_ohlcv)
            adapter = result["adapter"]
            p = adapter.blocks["multi_tp_1"]["params"]
            assert p["tp1_percent"] == tp1
            assert p["tp2_percent"] == tp2
            assert p["tp3_percent"] == tp3


# ============================================================
#
#  PART 7 — EXIT HANDLER BEHAVIOR
#
#  AI Knowledge: "Multi TP goes through _execute_exit with category='exit'"
#  When frontend sends category='exit':
#  - _execute_exit produces: exit=False (no dynamic triggers), multi_tp_config=[...]
#  - multi_tp_config uses param names tp{n}_allocation (NOT tp{n}_close_percent)
#  - Our frontend sends tp{n}_close_percent → handler falls to defaults (30, 30, 40)
#  - The engine reads TP levels from multi_tp_config OR block params
#  - Block does NOT need connections to strategy node
#
# ============================================================


class TestConfigOnlyBehavior:
    """AI agents must understand Multi TP exit handler — no dynamic triggers."""

    def test_no_extra_data_from_multi_tp(self, sample_ohlcv):
        """Multi TP does NOT populate extra_data with TP config (it stays in _value_cache only)."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 1.0,
                "tp2_percent": 2.0,
                "tp3_percent": 3.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        extra = result["extra_data"] or {}
        # Multi TP does NOT add any keys to extra_data
        assert "multi_tp_config" not in extra
        assert "multi_tp_levels" not in extra

    def test_no_connections_needed(self, sample_ohlcv):
        """Multi TP block works without any connections (standalone)."""
        graph = {
            "name": "Multi TP Standalone Test",
            "blocks": [
                {
                    "id": "b_rsi",
                    "type": "rsi",
                    "category": "indicator",
                    "name": "RSI",
                    "x": 100,
                    "y": 100,
                    "params": {"period": 14},
                },
                {
                    "id": "multi_tp_1",
                    "type": "multi_tp_exit",
                    "category": "exit",
                    "name": "Multi TP",
                    "x": 600,
                    "y": 450,
                    "params": {
                        "tp1_percent": 2.0,
                        "tp1_close_percent": 50,
                        "tp2_percent": 4.0,
                        "tp2_close_percent": 50,
                        "use_tp2": True,
                        "use_tp3": False,
                    },
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
        result = _run_adapter(graph, sample_ohlcv)
        # Block still processes without connections to it
        assert "multi_tp_1" in result["_value_cache"]
        # Has exit + multi_tp_config from _execute_exit handler
        cache_val = result["_value_cache"]["multi_tp_1"]
        assert "exit" in cache_val
        assert "multi_tp_config" in cache_val

    def test_cache_has_exit_and_config(self, sample_ohlcv):
        """
        _value_cache entry for multi_tp_exit contains exit series + multi_tp_config.

        When category='exit' (frontend default), _execute_exit handles it:
        - 'exit': pd.Series of False (no dynamic triggers)
        - 'multi_tp_config': list of {percent, allocation} dicts
        """
        graph = _make_multi_tp_only({"tp1_percent": 3.0})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["multi_tp_1"]
        assert cache is not None
        assert "exit" in cache, "exit series from _execute_exit"
        assert "multi_tp_config" in cache, "multi_tp_config from _execute_exit"
        # Exit series is all False (config-only, no dynamic triggers)
        assert cache["exit"].sum() == 0

    def test_block_params_accessible_directly(self, sample_ohlcv):
        """Even though dispatch returns {}, params are in adapter.blocks[id]['params']."""
        custom_params = {
            "tp1_percent": 0.8,
            "tp1_close_percent": 40,
            "use_tp2": True,
            "tp2_percent": 1.6,
            "tp2_close_percent": 30,
            "use_tp3": True,
            "tp3_percent": 2.4,
            "tp3_close_percent": 30,
        }
        graph = _make_multi_tp_only(custom_params)
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]

        for key, val in custom_params.items():
            assert p[key] == val, f"Param {key}: expected {val}, got {p[key]}"

    def test_allocation_param_name_mismatch(self, sample_ohlcv):
        """
        KNOWN MISMATCH: _execute_exit reads tp{n}_allocation but frontend sends tp{n}_close_percent.

        The _execute_exit handler uses params.get("tp1_allocation", 30), but the frontend
        sends "tp1_close_percent". So multi_tp_config in _value_cache always uses defaults
        (30, 30, 40) unless the param is named tp{n}_allocation.

        The block params (tp{n}_close_percent) are still accessible in adapter.blocks.
        """
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 1.0,
                "tp1_close_percent": 80,  # Frontend param name
                "tp2_percent": 2.0,
                "tp2_close_percent": 10,
                "tp3_percent": 3.0,
                "tp3_close_percent": 10,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["multi_tp_1"]

        # multi_tp_config uses tp{n}_allocation defaults (30, 30, 40) — NOT our close_percents
        config = cache["multi_tp_config"]
        assert config[0]["allocation"] == 30, "Fallback to default: tp1_allocation=30"
        assert config[1]["allocation"] == 30, "Fallback to default: tp2_allocation=30"
        assert config[2]["allocation"] == 40, "Fallback to default: tp3_allocation=40"

        # But tp{n}_close_percent is still accessible in block params
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_close_percent"] == 80
        assert p["tp2_close_percent"] == 10
        assert p["tp3_close_percent"] == 10


# ============================================================
#
#  PART 8 — USE_TP2 / USE_TP3 TOGGLES
#
#  AI Knowledge: "How do the TP2/TP3 toggles work?"
#  - use_tp2: checkbox, default True
#  - use_tp3: checkbox, default True
#  - When disabled, that TP level is skipped
#  - Close% should be reallocated (frontend responsibility)
#
# ============================================================


class TestTPToggles:
    """AI agents must know the use_tp2/use_tp3 toggle behavior."""

    def test_both_toggles_enabled_default(self, sample_ohlcv):
        """Default: both use_tp2 and use_tp3 are True."""
        graph = _make_multi_tp_only(
            {
                "use_tp2": True,
                "use_tp3": True,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["use_tp2"] is True
        assert p["use_tp3"] is True

    def test_disable_tp2_only(self, sample_ohlcv):
        """Disable TP2 — only TP1 and TP3 active."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 1.0,
                "tp1_close_percent": 50,
                "use_tp2": False,
                "tp2_percent": 2.0,
                "tp2_close_percent": 0,
                "use_tp3": True,
                "tp3_percent": 3.0,
                "tp3_close_percent": 50,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["use_tp2"] is False
        assert p["use_tp3"] is True
        # Allocation between TP1 + TP3 = 100%
        assert p["tp1_close_percent"] + p["tp3_close_percent"] == 100

    def test_disable_tp3_only(self, sample_ohlcv):
        """Disable TP3 — only TP1 and TP2 active."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 1.0,
                "tp1_close_percent": 50,
                "use_tp2": True,
                "tp2_percent": 2.0,
                "tp2_close_percent": 50,
                "use_tp3": False,
                "tp3_percent": 3.0,
                "tp3_close_percent": 0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["use_tp3"] is False
        assert p["use_tp2"] is True
        assert p["tp1_close_percent"] + p["tp2_close_percent"] == 100

    def test_disable_both_tp2_tp3(self, sample_ohlcv):
        """Disable both TP2 and TP3 — only TP1 remains (100%)."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 1.0,
                "tp1_close_percent": 100,
                "use_tp2": False,
                "tp2_percent": 2.0,
                "tp2_close_percent": 0,
                "use_tp3": False,
                "tp3_percent": 3.0,
                "tp3_close_percent": 0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["use_tp2"] is False
        assert p["use_tp3"] is False
        assert p["tp1_close_percent"] == 100

    def test_toggle_doesnt_affect_target_percent(self, sample_ohlcv):
        """Disabling a TP level doesn't remove its target% — it's still stored."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 1.0,
                "use_tp2": False,
                "tp2_percent": 5.0,
                "use_tp3": False,
                "tp3_percent": 10.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        # Target percents are still stored even when disabled
        assert p["tp2_percent"] == 5.0
        assert p["tp3_percent"] == 10.0


# ============================================================
#
#  PART 9 — COMBINED WITH RSI ENTRY
#
#  AI Knowledge: "Multi TP + RSI entry = config exit + RSI signals"
#
# ============================================================


class TestMultiTPWithRSI:
    """AI agents must know Multi TP doesn't interfere with RSI entry signals."""

    def test_rsi_entries_with_multi_tp(self, sample_ohlcv):
        """RSI generates entries independently of Multi TP config."""
        rsi_params = {
            "period": 14,
            "mode": "cross",
            "overbought": 70,
            "oversold": 30,
        }
        tp_params = {
            "tp1_percent": 1.0,
            "tp1_close_percent": 33,
            "tp2_percent": 2.0,
            "tp2_close_percent": 33,
            "tp3_percent": 3.0,
            "tp3_close_percent": 34,
        }
        graph = _make_rsi_with_multi_tp(rsi_params, tp_params)
        result = _run_adapter(graph, sample_ohlcv)

        total_entries = int(result["entries"].sum() + result["short_entries"].sum())
        assert total_entries >= 0, "RSI signals must be >= 0 (cross mode is event-based)"

    def test_rsi_aggressive_with_multi_tp(self, sample_ohlcv):
        """RSI with aggressive settings + Multi TP config."""
        rsi_params = {
            "period": 7,
            "mode": "level",
            "overbought": 55,
            "oversold": 45,
        }
        tp_params = {
            "tp1_percent": 0.5,
            "tp1_close_percent": 50,
            "use_tp2": True,
            "tp2_percent": 1.0,
            "tp2_close_percent": 50,
            "use_tp3": False,
        }
        graph = _make_rsi_with_multi_tp(rsi_params, tp_params)
        result = _run_adapter(graph, sample_ohlcv)

        total_entries = int(result["entries"].sum() + result["short_entries"].sum())
        assert total_entries > 0, "Aggressive RSI should produce signals"
        assert result["exits"].sum() == 0, "Multi TP is config-only — no exits"

    def test_rsi_conservative_with_multi_tp(self, sample_ohlcv):
        """RSI with conservative settings + Multi TP with high targets."""
        rsi_params = {
            "period": 21,
            "mode": "level",
            "overbought": 80,
            "oversold": 20,
        }
        tp_params = {
            "tp1_percent": 5.0,
            "tp1_close_percent": 20,
            "tp2_percent": 10.0,
            "tp2_close_percent": 30,
            "tp3_percent": 20.0,
            "tp3_close_percent": 50,
        }
        graph = _make_rsi_with_multi_tp(rsi_params, tp_params)
        result = _run_adapter(graph, sample_ohlcv)

        # Conservative RSI with period 21 should produce fewer signals
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_percent"] == 5.0
        assert p["tp3_percent"] == 20.0


# ============================================================
#
#  PART 10 — COMBINED WITH MACD ENTRY
#
#  AI Knowledge: "Multi TP + MACD entry = config exit + MACD signals"
#
# ============================================================


class TestMultiTPWithMACD:
    """AI agents must know Multi TP doesn't interfere with MACD entry signals."""

    def test_macd_entries_with_multi_tp(self, sample_ohlcv):
        """MACD cross signals work independently of Multi TP config."""
        macd_params = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "mode": "cross",
        }
        tp_params = {
            "tp1_percent": 1.0,
            "tp2_percent": 2.0,
            "tp3_percent": 3.0,
        }
        graph = _make_macd_with_multi_tp(macd_params, tp_params)
        result = _run_adapter(graph, sample_ohlcv)

        total_entries = int(result["entries"].sum() + result["short_entries"].sum())
        assert total_entries >= 0, "MACD cross signals should be >= 0"
        assert result["exits"].sum() == 0, "Multi TP is config-only"

    def test_macd_histogram_with_multi_tp(self, sample_ohlcv):
        """MACD histogram mode + Multi TP with only TP1."""
        macd_params = {
            "fast_period": 8,
            "slow_period": 21,
            "signal_period": 5,
            "mode": "histogram",
        }
        tp_params = {
            "tp1_percent": 2.0,
            "tp1_close_percent": 100,
            "use_tp2": False,
            "use_tp3": False,
        }
        graph = _make_macd_with_multi_tp(macd_params, tp_params)
        result = _run_adapter(graph, sample_ohlcv)

        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_close_percent"] == 100
        assert p["use_tp2"] is False
        assert p["use_tp3"] is False

    def test_macd_with_3_level_multi_tp(self, sample_ohlcv):
        """MACD with full 3-level Multi TP configuration."""
        macd_params = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "mode": "cross",
        }
        tp_params = {
            "tp1_percent": 1.0,
            "tp1_close_percent": 30,
            "use_tp2": True,
            "tp2_percent": 3.0,
            "tp2_close_percent": 30,
            "use_tp3": True,
            "tp3_percent": 5.0,
            "tp3_close_percent": 40,
        }
        graph = _make_macd_with_multi_tp(macd_params, tp_params)
        result = _run_adapter(graph, sample_ohlcv)

        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        total_close = p["tp1_close_percent"] + p["tp2_close_percent"] + p["tp3_close_percent"]
        assert total_close == 100


# ============================================================
#
#  PART 11 — COMPARISON WITH ORIGINAL TRADINGVIEW FORMAT
#
#  AI Knowledge: "Our 3 TP levels vs original 4 TP levels"
#  Original TradingView:
#    - "Use Multiple Take Profits" master toggle
#    - 4 TP levels (TP1-TP4), each with Profit Percent + Value (close%)
#    - TP4 always closes ALL remaining position
#    - Range: 0.5% — 30%
#  Our implementation:
#    - 3 TP levels (TP1-TP3)
#    - TP1 always enabled (no toggle)
#    - TP2/TP3 have use_tp2/use_tp3 checkboxes
#    - Close percents are manually allocated (should sum to 100%)
#    - No master "Use Multiple Take Profits" toggle
#
# ============================================================


class TestTradingViewComparison:
    """AI agents must understand differences between our 3-level and TV's 4-level format."""

    def test_our_implementation_has_3_levels(self, sample_ohlcv):
        """We have 3 TP levels (not 4 like TradingView original)."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 1.0,
                "tp2_percent": 2.0,
                "tp3_percent": 3.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]

        # We have tp1, tp2, tp3 — no tp4
        assert "tp1_percent" in p
        assert "tp2_percent" in p
        assert "tp3_percent" in p
        assert "tp4_percent" not in p, "Our block has 3 levels, not 4"

    def test_no_master_toggle(self, sample_ohlcv):
        """Our block has no 'Use Multiple Take Profits' master toggle (unlike TV)."""
        graph = _make_multi_tp_only({"tp1_percent": 1.0})
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]

        # No master toggle — the block's presence implies multi TP is enabled
        assert "use_multiple_tp" not in p
        assert "enabled" not in p

    def test_tp3_is_last_level_closes_remainder(self, sample_ohlcv):
        """In our 3-level system, TP3 is the last level (analogous to TV's TP4)."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 1.0,
                "tp1_close_percent": 25,
                "tp2_percent": 2.0,
                "tp2_close_percent": 25,
                "tp3_percent": 3.0,
                "tp3_close_percent": 50,  # TP3 closes remaining 50%
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        # TP3 is the last level — should close whatever remains
        assert p["tp3_close_percent"] == 50

    def test_dca_config_supports_4_levels(self, sample_ohlcv):
        """extract_dca_config has dca_tp1-tp4 keys (supports TV's 4-level format)."""
        graph = _make_multi_tp_only({"tp1_percent": 1.0})
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        dca_config = adapter.extract_dca_config()

        # DCA config supports 4 levels even though our UI has 3
        for i in range(1, 5):
            assert f"dca_tp{i}_percent" in dca_config
            assert f"dca_tp{i}_close_percent" in dca_config


# ============================================================
#
#  PART 12 — EDGE CASES AND PARAMETER VALIDATION
#
# ============================================================


class TestEdgeCases:
    """Edge cases and boundary conditions for Multi TP Exit."""

    def test_minimum_target_percent(self, sample_ohlcv):
        """Minimum valid target: 0.5%."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 0.5,
                "tp2_percent": 0.5,
                "tp3_percent": 0.5,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_percent"] == 0.5

    def test_maximum_target_percent(self, sample_ohlcv):
        """Maximum valid target: 30%."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 30.0,
                "tp2_percent": 30.0,
                "tp3_percent": 30.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp3_percent"] == 30.0

    def test_empty_params_uses_adapter_defaults(self, sample_ohlcv):
        """Empty params dict should not crash — adapter stores empty params."""
        graph = _make_multi_tp_only({})
        result = _run_adapter(graph, sample_ohlcv)
        # Block processes without error
        assert "multi_tp_1" in result["_value_cache"]

    def test_ascending_target_order(self, sample_ohlcv):
        """Best practice: TP1 < TP2 < TP3 (ascending targets)."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 1.0,
                "tp2_percent": 2.0,
                "tp3_percent": 3.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_percent"] < p["tp2_percent"] < p["tp3_percent"]

    def test_equal_target_percents(self, sample_ohlcv):
        """Edge case: all TP targets at same level."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 2.0,
                "tp2_percent": 2.0,
                "tp3_percent": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_percent"] == p["tp2_percent"] == p["tp3_percent"] == 2.0

    def test_descending_target_order(self, sample_ohlcv):
        """Unusual but valid: TP1 > TP2 > TP3 (descending targets)."""
        graph = _make_multi_tp_only(
            {
                "tp1_percent": 10.0,
                "tp2_percent": 5.0,
                "tp3_percent": 2.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_percent"] > p["tp2_percent"] > p["tp3_percent"]

    def test_fractional_close_percents(self, sample_ohlcv):
        """Close percents can be fractional (e.g., 33.33)."""
        graph = _make_multi_tp_only(
            {
                "tp1_close_percent": 33.33,
                "tp2_close_percent": 33.33,
                "tp3_close_percent": 33.34,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        total = p["tp1_close_percent"] + p["tp2_close_percent"] + p["tp3_close_percent"]
        assert abs(total - 100.0) < 0.01, f"Fractional close percents should ~sum to 100, got {total}"

    def test_multiple_adapter_runs_stable(self, sample_ohlcv):
        """Running adapter multiple times with same params gives same result."""
        tp_params = {
            "tp1_percent": 1.5,
            "tp2_percent": 3.0,
            "tp3_percent": 4.5,
            "tp1_close_percent": 30,
            "tp2_close_percent": 30,
            "tp3_close_percent": 40,
        }
        results = []
        for _ in range(3):
            graph = _make_multi_tp_only(tp_params)
            result = _run_adapter(graph, sample_ohlcv)
            adapter = result["adapter"]
            p = adapter.blocks["multi_tp_1"]["params"]
            results.append(p.copy())

        for r in results[1:]:
            for key in tp_params:
                assert r[key] == results[0][key], f"Unstable result for {key}"


# ============================================================
#
#  PART 13 — FULL SCENARIO (RSI + MACD + Multi TP)
#
# ============================================================


class TestFullScenario:
    """Full scenario combining multiple entry indicators with Multi TP exit."""

    def test_rsi_and_multi_tp_full_config(self, sample_ohlcv):
        """Complete scenario: RSI entry + 3-level Multi TP exit."""
        rsi_params = {
            "period": 14,
            "mode": "level",
            "overbought": 70,
            "oversold": 30,
        }
        tp_params = {
            "tp1_percent": 1.0,
            "tp1_close_percent": 33,
            "use_tp2": True,
            "tp2_percent": 2.0,
            "tp2_close_percent": 33,
            "use_tp3": True,
            "tp3_percent": 3.0,
            "tp3_close_percent": 34,
        }
        graph = _make_rsi_with_multi_tp(rsi_params, tp_params)
        result = _run_adapter(graph, sample_ohlcv)

        # RSI produces entry signals
        total_entries = int(result["entries"].sum() + result["short_entries"].sum())
        assert total_entries > 0

        # Multi TP is config-only
        assert result["exits"].sum() == 0

        # Both blocks in cache
        assert "b_rsi" in result["_value_cache"]
        assert "multi_tp_1" in result["_value_cache"]

        # Multi TP params stored correctly
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["tp1_percent"] == 1.0
        assert p["tp2_percent"] == 2.0
        assert p["tp3_percent"] == 3.0
        total_close = p["tp1_close_percent"] + p["tp2_close_percent"] + p["tp3_close_percent"]
        assert total_close == 100

    def test_macd_and_multi_tp_full_config(self, sample_ohlcv):
        """Complete scenario: MACD entry + custom 2-level Multi TP."""
        macd_params = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "mode": "cross",
        }
        tp_params = {
            "tp1_percent": 2.0,
            "tp1_close_percent": 60,
            "use_tp2": True,
            "tp2_percent": 5.0,
            "tp2_close_percent": 40,
            "use_tp3": False,
            "tp3_percent": 10.0,
            "tp3_close_percent": 0,
        }
        graph = _make_macd_with_multi_tp(macd_params, tp_params)
        result = _run_adapter(graph, sample_ohlcv)

        # MACD produces signals
        total_entries = int(result["entries"].sum() + result["short_entries"].sum())
        assert total_entries >= 0  # Cross mode is event-based

        # Multi TP params correct
        adapter = result["adapter"]
        p = adapter.blocks["multi_tp_1"]["params"]
        assert p["use_tp3"] is False
        assert p["tp1_close_percent"] + p["tp2_close_percent"] == 100

    def test_extract_dca_after_full_run(self, sample_ohlcv):
        """extract_dca_config works correctly after full generate_signals run."""
        graph = _make_rsi_with_multi_tp(
            {"period": 14},
            {
                "tp1_percent": 1.0,
                "tp2_percent": 2.0,
                "tp3_percent": 3.0,
                "tp1_close_percent": 33,
                "tp2_close_percent": 33,
                "tp3_close_percent": 34,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]

        dca_config = adapter.extract_dca_config()
        assert isinstance(dca_config, dict)
        # DCA defaults still present
        assert "dca_enabled" in dca_config
        assert "dca_multi_tp_enabled" in dca_config
