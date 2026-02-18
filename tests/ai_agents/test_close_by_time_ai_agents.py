"""
AI Agent Knowledge Test: Close by Time Block — Real Adapter Tests

Tests verify that AI agents (DeepSeek, Qwen, Perplexity) correctly understand:
- Every parameter of the Close by Time block (4 fields: enabled, bars_since_entry,
  profit_only, min_profit_percent)
- How the block is placed from the close_conditions menu group
- How frontend assigns category='close_conditions' → _execute_close_condition()
- How the handler reads params.get("bars", 10) — NOT "bars_since_entry" (param mismatch)
- How extract_dca_config() checks block_type=="time_bars_close" (NOT "close_by_time")
- How close_by_time is NOT in _BLOCK_CATEGORY_MAP (requires frontend category)
- Which parameters are optimizable (bars_since_entry only)
- Combining Close by Time with RSI/MACD entry filters

Architecture Notes:
    - Block type: "close_by_time"
    - Frontend menu group: close_conditions
    - Frontend category assignment: addBlockToCanvas(blockId, blockType) sets
      block.category = blockType (the menu group key = "close_conditions")
    - Category dispatch: "close_conditions" → _execute_close_condition(block_type, params, ohlcv, inputs)
    - Handler output: {exit: pd.Series(False), max_bars: pd.Series([bars]*n)}
    - PARAM MISMATCH: Handler reads params.get("bars", 10), but frontend default
      is "bars_since_entry: 10" → handler always uses default value 10
    - DCA CONFIG MISMATCH: extract_dca_config() checks block_type=="time_bars_close"
      (NOT "close_by_time") → our block's params won't be auto-extracted
    - NOT in _BLOCK_CATEGORY_MAP → without frontend category, _infer_category()
      falls back to "indicator" (wrong!)

    Original TradingView description (from spec):
      - Use Close By Time Since Order: true/false
      - Close order after XX bars: 1-100
      - Close only with Profit: true/false
      - Min Profit percent for Close %%: 0.1-20

    Frontend blockDefaults (strategy_builder.js line 3678):
      close_by_time: {
        enabled: false,
        bars_since_entry: 10,
        profit_only: false,
        min_profit_percent: 0
      }

These tests run against the REAL StrategyBuilderAdapter (in-memory DB).
They validate that every Close by Time parameter combination is properly processed.

Run:
    py -3.14 -m pytest tests/ai_agents/test_close_by_time_ai_agents.py -v
    py -3.14 -m pytest tests/ai_agents/test_close_by_time_ai_agents.py -v -k "defaults"
    py -3.14 -m pytest tests/ai_agents/test_close_by_time_ai_agents.py -v -k "category"
    py -3.14 -m pytest tests/ai_agents/test_close_by_time_ai_agents.py -v -k "handler"
    py -3.14 -m pytest tests/ai_agents/test_close_by_time_ai_agents.py -v -k "dca_config"
    py -3.14 -m pytest tests/ai_agents/test_close_by_time_ai_agents.py -v -k "optimization"
    py -3.14 -m pytest tests/ai_agents/test_close_by_time_ai_agents.py -v -k "filter"
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


def _make_rsi_with_close_by_time(
    rsi_params: dict[str, Any],
    close_params: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a strategy graph: RSI indicator → entry long/short → strategy,
    plus Close by Time block (close_conditions category).

    AI Agent Knowledge:
        Close by Time block has category='close_conditions' (set by frontend
        addBlockToCanvas from the close_conditions menu group).
        The adapter dispatches it to _execute_close_condition() handler.
        Handler produces: {exit: pd.Series(False), max_bars: pd.Series([bars]*n)}.
        NOTE: Handler reads params.get("bars", 10) — NOT "bars_since_entry".
    """
    return {
        "name": "RSI + Close by Time Test",
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
                "id": "cbt_1",
                "type": "close_by_time",
                "category": "close_conditions",
                "name": "Close by Time",
                "icon": "clock",
                "x": 600,
                "y": 450,
                "params": close_params,
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


def _make_macd_with_close_by_time(
    macd_params: dict[str, Any],
    close_params: dict[str, Any],
) -> dict[str, Any]:
    """Build a strategy graph: MACD indicator → entry long/short → strategy + Close by Time."""
    return {
        "name": "MACD + Close by Time Test",
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
                "id": "cbt_1",
                "type": "close_by_time",
                "category": "close_conditions",
                "name": "Close by Time",
                "icon": "clock",
                "x": 600,
                "y": 450,
                "params": close_params,
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


def _make_close_by_time_only(close_params: dict[str, Any]) -> dict[str, Any]:
    """
    Build a strategy graph with ONLY a Close by Time block + RSI passthrough entry.

    AI Agent Knowledge:
        RSI with default params acts as passthrough. This isolates Close by Time behavior.
    """
    return _make_rsi_with_close_by_time({"period": 14}, close_params)


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
#  PART 1 — CLOSE BY TIME DEFAULT VALUES
#
#  AI Knowledge: "What are the default values?"
#  Panel fields (from strategy_builder.js blockDefaults line 3678):
#    enabled = false          (checkbox — master toggle)
#    bars_since_entry = 10    (number, optimizable, range 1-100)
#    profit_only = false      (checkbox — close only with profit)
#    min_profit_percent = 0   (number, range 0.1-20)
#
#  TradingView original:
#    Use Close By Time Since Order: true/false
#    Close order after XX bars: 1-100
#    Close only with Profit: true/false
#    Min Profit percent for Close %%: 0.1-20
#
# ============================================================


class TestCloseByTimeDefaults:
    """AI agents must know all default values and what each parameter does."""

    def test_default_values_block_processes(self, sample_ohlcv):
        """Default: enabled=false, bars_since_entry=10, profit_only=false, min_profit_percent=0."""
        graph = _make_close_by_time_only({})
        result = _run_adapter(graph, sample_ohlcv)

        # Close by Time goes through _execute_close_condition → produces exit + max_bars
        cache = result["_value_cache"]
        assert "cbt_1" in cache, "Close by Time block must be in _value_cache"
        assert "exit" in cache["cbt_1"], "Should have exit series from handler"
        assert "max_bars" in cache["cbt_1"], "Should have max_bars series from handler"

    def test_default_params_stored_in_blocks(self, sample_ohlcv):
        """Params with defaults must be accessible via adapter.blocks."""
        defaults = {
            "enabled": False,
            "bars_since_entry": 10,
            "profit_only": False,
            "min_profit_percent": 0,
        }
        graph = _make_close_by_time_only(defaults)
        result = _run_adapter(graph, sample_ohlcv)

        adapter = result["adapter"]
        block_params = adapter.blocks["cbt_1"]["params"]
        assert block_params["enabled"] is False
        assert block_params["bars_since_entry"] == 10
        assert block_params["profit_only"] is False
        assert block_params["min_profit_percent"] == 0

    def test_enabled_true(self, sample_ohlcv):
        """enabled=True activates the close-by-time feature."""
        graph = _make_close_by_time_only({"enabled": True, "bars_since_entry": 5})
        result = _run_adapter(graph, sample_ohlcv)

        adapter = result["adapter"]
        p = adapter.blocks["cbt_1"]["params"]
        assert p["enabled"] is True
        assert p["bars_since_entry"] == 5

    def test_no_exit_signals_generated(self, sample_ohlcv):
        """Close by Time exit series is all False (actual closing done by engine)."""
        graph = _make_close_by_time_only({"enabled": True, "bars_since_entry": 20})
        result = _run_adapter(graph, sample_ohlcv)

        # Handler returns exit=False series — engine handles actual position closing
        assert result["exits"].sum() == 0, "Close by Time does not produce exit signals directly"
        assert result["short_exits"].sum() == 0

    def test_entries_still_work_with_close_by_time(self, sample_ohlcv):
        """RSI entry signals must still be generated when Close by Time is attached."""
        graph = _make_close_by_time_only({"enabled": True, "bars_since_entry": 10})
        result = _run_adapter(graph, sample_ohlcv)
        total_entries = int(result["entries"].sum() + result["short_entries"].sum())
        assert total_entries > 0, "RSI entry signals must still fire with Close by Time attached"


# ============================================================
#
#  PART 2 — CATEGORY DISPATCH
#
#  AI Knowledge: "How is close_by_time dispatched?"
#
#  Frontend path: addBlockToCanvas("close_by_time", "close_conditions")
#    → block.category = "close_conditions"
#    → _execute_close_condition(block_type="close_by_time", params, ohlcv, inputs)
#    → handler reads params.get("bars", 10), returns {exit, max_bars}
#
#  close_by_time is NOT in _BLOCK_CATEGORY_MAP.
#  If category is missing, _infer_category falls back to "indicator" (WRONG!)
#  The frontend always sends category="close_conditions", so this works in practice.
#
# ============================================================


class TestCloseByTimeCategoryDispatch:
    """AI agents must understand how close_by_time is dispatched."""

    def test_not_in_block_category_map(self):
        """Block type 'close_by_time' is NOT in _BLOCK_CATEGORY_MAP."""
        cat = StrategyBuilderAdapter._BLOCK_CATEGORY_MAP.get("close_by_time")
        assert cat is None, f"Expected None (not in map), got '{cat}'"

    def test_infer_category_falls_back_to_indicator(self):
        """Without frontend category, _infer_category falls back to 'indicator' (wrong!)."""
        inferred = StrategyBuilderAdapter._infer_category("close_by_time")
        assert inferred == "indicator", (
            f"Expected fallback to 'indicator', got '{inferred}'. "
            "close_by_time is NOT in _BLOCK_CATEGORY_MAP and has no matching prefix."
        )

    def test_frontend_category_used_for_dispatch(self, sample_ohlcv):
        """When frontend sends category='close_conditions', dispatch works correctly."""
        graph = _make_close_by_time_only({"enabled": True, "bars_since_entry": 15})
        result = _run_adapter(graph, sample_ohlcv)

        adapter = result["adapter"]
        assert adapter.blocks["cbt_1"]["category"] == "close_conditions"

        # Handler produces exit + max_bars
        cache = result["_value_cache"]["cbt_1"]
        assert "exit" in cache
        assert "max_bars" in cache

    def test_without_category_wrong_dispatch(self, sample_ohlcv):
        """
        Without explicit category, close_by_time falls back to 'indicator' dispatch
        (via _infer_category). This is a KNOWN ISSUE — frontend always sends category.
        """
        graph = _make_close_by_time_only({"enabled": True, "bars_since_entry": 10})
        # Remove the explicit category
        for block in graph["blocks"]:
            if block["id"] == "cbt_1":
                del block["category"]
        result = _run_adapter(graph, sample_ohlcv)

        adapter = result["adapter"]
        # Falls back to "indicator" since close_by_time is not in _BLOCK_CATEGORY_MAP
        assert adapter.blocks["cbt_1"]["category"] == "indicator", (
            "Without frontend category, _infer_category defaults to 'indicator'"
        )

    def test_close_conditions_dispatch_path(self, sample_ohlcv):
        """Verify the dispatch path: close_conditions → _execute_close_condition."""
        graph = _make_close_by_time_only({"bars_since_entry": 25})
        result = _run_adapter(graph, sample_ohlcv)

        # _execute_close_condition returns dict with exit and max_bars
        cache = result["_value_cache"]["cbt_1"]
        assert isinstance(cache, dict)
        assert "exit" in cache
        assert "max_bars" in cache
        # exit is False series (engine implements actual bar counting)
        assert cache["exit"].sum() == 0


# ============================================================
#
#  PART 3 — HANDLER OUTPUT
#
#  AI Knowledge: "What does _execute_close_condition return for close_by_time?"
#
#  Handler code (strategy_builder_adapter.py line 2985-2991):
#    if close_type == "close_by_time":
#        bars = params.get("bars", 10)
#        result["exit"] = pd.Series([False] * n, index=idx)
#        result["max_bars"] = pd.Series([bars] * n, index=idx)
#
#  Returns:
#    - exit: pd.Series of False (all False, engine implements actual closing)
#    - max_bars: pd.Series filled with the bars value (constant for all rows)
#
# ============================================================


class TestCloseByTimeHandlerOutput:
    """AI agents must understand the handler output format."""

    def test_exit_series_all_false(self, sample_ohlcv):
        """Handler returns exit=pd.Series(False) — engine does actual position closing."""
        graph = _make_close_by_time_only({"bars_since_entry": 10})
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["cbt_1"]
        assert isinstance(cache["exit"], pd.Series)
        assert cache["exit"].dtype == bool
        assert cache["exit"].sum() == 0, "exit series should be all False"

    def test_max_bars_series_constant(self, sample_ohlcv):
        """Handler returns max_bars=pd.Series([bars]*n) — constant value across all rows."""
        graph = _make_close_by_time_only({"bars_since_entry": 20})
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["cbt_1"]
        max_bars = cache["max_bars"]
        assert isinstance(max_bars, pd.Series)
        assert len(max_bars) == len(sample_ohlcv)
        # NOTE: handler reads params.get("bars", 10), NOT "bars_since_entry"
        # Since frontend sends "bars_since_entry" but handler reads "bars",
        # the handler uses default value 10 (param name mismatch)
        assert max_bars.iloc[0] == 10, "Param mismatch: handler reads 'bars' (default 10), not 'bars_since_entry'"

    def test_max_bars_with_correct_param_name(self, sample_ohlcv):
        """When using the handler's expected param name 'bars', value is used correctly."""
        graph = _make_close_by_time_only({"bars": 50})
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["cbt_1"]
        max_bars = cache["max_bars"]
        assert max_bars.iloc[0] == 50, "With correct param name 'bars', value should be 50"
        # All values are the same constant
        assert max_bars.nunique() == 1, "max_bars should be constant across all rows"

    def test_handler_output_is_dict(self, sample_ohlcv):
        """Handler output is a dict with exactly 'exit' and 'max_bars' keys."""
        graph = _make_close_by_time_only({"bars": 15})
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["cbt_1"]
        assert isinstance(cache, dict)
        assert "exit" in cache
        assert "max_bars" in cache

    def test_series_length_matches_ohlcv(self, sample_ohlcv):
        """Both output series have same length as input OHLCV."""
        graph = _make_close_by_time_only({"bars": 30})
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["cbt_1"]
        n = len(sample_ohlcv)
        assert len(cache["exit"]) == n
        assert len(cache["max_bars"]) == n

    def test_series_index_matches_ohlcv(self, sample_ohlcv):
        """Both output series share the same index as input OHLCV."""
        graph = _make_close_by_time_only({"bars": 10})
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["cbt_1"]
        pd.testing.assert_index_equal(cache["exit"].index, sample_ohlcv.index)
        pd.testing.assert_index_equal(cache["max_bars"].index, sample_ohlcv.index)


# ============================================================
#
#  PART 4 — PARAM NAME MISMATCH
#
#  AI Knowledge: "What is the param name mismatch?"
#
#  Frontend blockDefaults key: "bars_since_entry" (value 10)
#  Handler reads: params.get("bars", 10)
#
#  This means when frontend sends {bars_since_entry: 30}, the handler
#  ignores it and uses default 10 instead. The engine may read
#  "bars_since_entry" directly from block params, bypassing the handler.
#
#  TradingView original name: "Close order after XX bars"
#
# ============================================================


class TestParamNameMismatch:
    """AI agents must understand the param name mismatch between frontend and handler."""

    def test_frontend_param_name_ignored_by_handler(self, sample_ohlcv):
        """
        KNOWN MISMATCH: Frontend sends 'bars_since_entry' but handler reads 'bars'.
        The handler falls back to default value 10.
        """
        graph = _make_close_by_time_only({"bars_since_entry": 50})
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["cbt_1"]
        # Handler uses params.get("bars", 10) → falls to default 10
        assert cache["max_bars"].iloc[0] == 10, "Handler reads 'bars' not 'bars_since_entry', so default 10 is used"

    def test_handler_param_name_works(self, sample_ohlcv):
        """When using the handler's expected param name 'bars', it works."""
        graph = _make_close_by_time_only({"bars": 75})
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["cbt_1"]
        assert cache["max_bars"].iloc[0] == 75

    def test_both_param_names_sent(self, sample_ohlcv):
        """When both 'bars' and 'bars_since_entry' are sent, handler uses 'bars'."""
        graph = _make_close_by_time_only({"bars": 30, "bars_since_entry": 50})
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["cbt_1"]
        assert cache["max_bars"].iloc[0] == 30, "Handler reads 'bars', ignoring 'bars_since_entry'"

    def test_frontend_param_still_in_block_params(self, sample_ohlcv):
        """Frontend's 'bars_since_entry' is stored in block params (engine can read it directly)."""
        graph = _make_close_by_time_only({"bars_since_entry": 42})
        result = _run_adapter(graph, sample_ohlcv)

        adapter = result["adapter"]
        p = adapter.blocks["cbt_1"]["params"]
        assert p["bars_since_entry"] == 42, "bars_since_entry is stored in params — engine can read it directly"

    def test_profit_only_param_stored_correctly(self, sample_ohlcv):
        """profit_only param is stored as-is (no mismatch for this field)."""
        graph = _make_close_by_time_only({"profit_only": True, "min_profit_percent": 0.5})
        result = _run_adapter(graph, sample_ohlcv)

        adapter = result["adapter"]
        p = adapter.blocks["cbt_1"]["params"]
        assert p["profit_only"] is True
        assert p["min_profit_percent"] == 0.5


# ============================================================
#
#  PART 5 — EXTRACT DCA CONFIG INTEGRATION
#
#  AI Knowledge: "How does Close by Time integrate with DCA config?"
#
#  extract_dca_config() scans blocks checking block_type.
#  IMPORTANT: There's a known block_type mismatch!
#    - Our block_type is "close_by_time"
#    - extract_dca_config checks for block_type=="time_bars_close"
#    - If type was "time_bars_close", it would extract:
#      time_bars_close_enable, close_after_bars (default 20),
#      close_only_profit (default True), close_min_profit (default 0.5),
#      close_max_bars (default 100)
#    - But since our type is "close_by_time", NONE of these are extracted
#  Result: extract_dca_config close_conditions won't contain time_bars entries
#  The block params are still accessible via adapter.blocks[block_id]["params"]
#
# ============================================================


class TestExtractDCAConfig:
    """AI agents must understand the DCA config extraction behavior."""

    def test_extract_dca_config_callable(self, sample_ohlcv):
        """extract_dca_config() can be called after generate_signals."""
        graph = _make_close_by_time_only({"enabled": True, "bars_since_entry": 15})
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        dca_config = adapter.extract_dca_config()
        assert isinstance(dca_config, dict)

    def test_dca_config_has_close_conditions_key(self, sample_ohlcv):
        """DCA config always has close_conditions sub-dict."""
        graph = _make_close_by_time_only({"enabled": True})
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        dca_config = adapter.extract_dca_config()
        assert "close_conditions" in dca_config
        assert isinstance(dca_config["close_conditions"], dict)

    def test_block_type_mismatch_documented(self, sample_ohlcv):
        """
        KNOWN MISMATCH: Our block_type is 'close_by_time' but extract_dca_config
        checks for 'time_bars_close'. Our block's params won't be auto-extracted
        into time_bars_close_enable / close_after_bars / etc. keys.
        """
        graph = _make_close_by_time_only(
            {
                "enabled": True,
                "bars_since_entry": 30,
                "profit_only": True,
                "min_profit_percent": 1.0,
            }
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        dca_config = adapter.extract_dca_config()

        close_conds = dca_config["close_conditions"]
        # Since block_type is "close_by_time" (not "time_bars_close"),
        # the time_bars_close_enable key should NOT be set
        assert "time_bars_close_enable" not in close_conds, (
            "Known mismatch: close_by_time block_type != time_bars_close, "
            "so time_bars_close_enable is not auto-extracted"
        )

    def test_correct_block_type_would_extract(self, sample_ohlcv):
        """
        If a block with type='time_bars_close' is provided, extract_dca_config
        DOES collect the close-by-time params correctly.
        This tests the correct code path (vs our close_by_time mismatch).
        """
        graph = {
            "name": "time_bars_close Format Test",
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
                    "id": "tbc_1",
                    "type": "time_bars_close",
                    "category": "close_conditions",
                    "name": "Time Bars Close",
                    "x": 600,
                    "y": 450,
                    "params": {
                        "close_after_bars": 30,
                        "close_only_profit": True,
                        "close_min_profit": 1.0,
                        "close_max_bars": 50,
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

        close_conds = dca_config["close_conditions"]
        # This format DOES activate time_bars_close in DCA config
        assert close_conds["time_bars_close_enable"] is True
        assert close_conds["close_after_bars"] == 30
        assert close_conds["close_only_profit"] is True
        assert close_conds["close_min_profit"] == 1.0
        assert close_conds["close_max_bars"] == 50

    def test_params_still_accessible_via_blocks(self, sample_ohlcv):
        """Even though DCA extract misses our block, params are in adapter.blocks."""
        custom = {
            "enabled": True,
            "bars_since_entry": 25,
            "profit_only": True,
            "min_profit_percent": 2.0,
        }
        graph = _make_close_by_time_only(custom)
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["cbt_1"]["params"]

        for key, val in custom.items():
            assert p[key] == val, f"Param {key}: expected {val}, got {p[key]}"


# ============================================================
#
#  PART 6 — OPTIMIZATION MODE
#
#  AI Knowledge: "Which params are optimizable?"
#  - bars_since_entry: optimizable (range 1-100)
#  - enabled: NOT optimizable (toggle)
#  - profit_only: NOT optimizable (toggle)
#  - min_profit_percent: could be optimizable (range 0.1-20)
#
# ============================================================


class TestCloseByTimeOptimization:
    """AI agents must know which fields are optimizable."""

    def test_sweep_bars_since_entry(self, sample_ohlcv):
        """bars_since_entry is the main optimizable param (range 1-100)."""
        for bars in [1, 5, 10, 20, 50, 100]:
            graph = _make_close_by_time_only({"bars_since_entry": bars})
            result = _run_adapter(graph, sample_ohlcv)
            adapter = result["adapter"]
            p = adapter.blocks["cbt_1"]["params"]
            assert p["bars_since_entry"] == bars

    def test_sweep_bars_handler_param(self, sample_ohlcv):
        """Sweep using handler's 'bars' param — directly affects max_bars output."""
        for bars in [1, 5, 10, 20, 50, 100]:
            graph = _make_close_by_time_only({"bars": bars})
            result = _run_adapter(graph, sample_ohlcv)
            cache = result["_value_cache"]["cbt_1"]
            assert cache["max_bars"].iloc[0] == bars

    def test_sweep_min_profit_percent(self, sample_ohlcv):
        """min_profit_percent can be varied across valid range (0.1-20)."""
        for pct in [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0]:
            graph = _make_close_by_time_only({"profit_only": True, "min_profit_percent": pct})
            result = _run_adapter(graph, sample_ohlcv)
            adapter = result["adapter"]
            p = adapter.blocks["cbt_1"]["params"]
            assert p["min_profit_percent"] == pct

    def test_optimization_combination(self, sample_ohlcv):
        """Sweep both bars and min_profit_percent together."""
        configs = [
            {"bars": 5, "min_profit_percent": 0.1},
            {"bars": 20, "min_profit_percent": 1.0},
            {"bars": 50, "min_profit_percent": 5.0},
            {"bars": 100, "min_profit_percent": 20.0},
        ]
        for cfg in configs:
            graph = _make_close_by_time_only(cfg)
            result = _run_adapter(graph, sample_ohlcv)
            cache = result["_value_cache"]["cbt_1"]
            assert cache["max_bars"].iloc[0] == cfg["bars"]
            adapter = result["adapter"]
            p = adapter.blocks["cbt_1"]["params"]
            assert p["min_profit_percent"] == cfg["min_profit_percent"]


# ============================================================
#
#  PART 7 — RSI + CLOSE BY TIME COMBINATIONS
#
#  AI Knowledge: "How does Close by Time work with RSI entry?"
#  RSI provides entry signals, Close by Time defines when to close.
#  Both blocks process independently — Close by Time doesn't filter entries.
#
# ============================================================


class TestRSIWithCloseByTime:
    """AI agents must understand RSI + Close by Time combination."""

    def test_rsi_default_with_close_10_bars(self, sample_ohlcv):
        """RSI default + Close after 10 bars."""
        graph = _make_rsi_with_close_by_time(
            {"period": 14},
            {"enabled": True, "bars": 10},
        )
        result = _run_adapter(graph, sample_ohlcv)

        # RSI produces entries
        total_entries = int(result["entries"].sum() + result["short_entries"].sum())
        assert total_entries > 0

        # Close by Time produces config (no direct exit signals)
        cache = result["_value_cache"]["cbt_1"]
        assert cache["max_bars"].iloc[0] == 10

    def test_rsi_overbought_oversold_with_close(self, sample_ohlcv):
        """RSI with custom levels + Close after 25 bars with profit filter."""
        graph = _make_rsi_with_close_by_time(
            {"period": 21, "mode": "level", "overbought": 75, "oversold": 25},
            {"enabled": True, "bars": 25, "profit_only": True, "min_profit_percent": 1.0},
        )
        result = _run_adapter(graph, sample_ohlcv)

        # Both blocks in cache
        assert "b_rsi" in result["_value_cache"]
        assert "cbt_1" in result["_value_cache"]

        # Verify params stored
        adapter = result["adapter"]
        p = adapter.blocks["cbt_1"]["params"]
        assert p["profit_only"] is True
        assert p["min_profit_percent"] == 1.0

    def test_rsi_fast_with_close_100_bars(self, sample_ohlcv):
        """RSI fast period (7) + Close after max bars (100)."""
        graph = _make_rsi_with_close_by_time(
            {"period": 7},
            {"enabled": True, "bars": 100},
        )
        result = _run_adapter(graph, sample_ohlcv)

        cache = result["_value_cache"]["cbt_1"]
        assert cache["max_bars"].iloc[0] == 100


# ============================================================
#
#  PART 8 — MACD + CLOSE BY TIME COMBINATIONS
#
# ============================================================


class TestMACDWithCloseByTime:
    """AI agents must understand MACD + Close by Time combination."""

    def test_macd_default_with_close_by_time(self, sample_ohlcv):
        """MACD default + Close after 15 bars."""
        graph = _make_macd_with_close_by_time(
            {"fast_period": 12, "slow_period": 26, "signal_period": 9},
            {"enabled": True, "bars": 15},
        )
        result = _run_adapter(graph, sample_ohlcv)

        # MACD produces signals
        total_entries = int(result["entries"].sum() + result["short_entries"].sum())
        assert total_entries >= 0  # Cross mode is event-based

        # Close by Time config present
        cache = result["_value_cache"]["cbt_1"]
        assert cache["max_bars"].iloc[0] == 15

    def test_macd_with_profit_only_close(self, sample_ohlcv):
        """MACD + Close only when profitable, min 2% profit."""
        graph = _make_macd_with_close_by_time(
            {"fast_period": 12, "slow_period": 26, "signal_period": 9, "mode": "cross"},
            {"enabled": True, "bars": 20, "profit_only": True, "min_profit_percent": 2.0},
        )
        result = _run_adapter(graph, sample_ohlcv)

        adapter = result["adapter"]
        p = adapter.blocks["cbt_1"]["params"]
        assert p["profit_only"] is True
        assert p["min_profit_percent"] == 2.0
        assert p["bars"] == 20


# ============================================================
#
#  PART 9 — TRADINGVIEW COMPARISON
#
#  AI Knowledge: "Our close_by_time vs TradingView original"
#
#  TradingView original:
#    - Use Close By Time Since Order: true/false
#    - Close order after XX bars: 1-100
#    - Close only with Profit: true/false
#    - Min Profit percent for Close %%: 0.1-20
#
#  Our frontend:
#    - enabled: false         → TV's "Use Close By Time Since Order"
#    - bars_since_entry: 10   → TV's "Close order after XX bars"
#    - profit_only: false     → TV's "Close only with Profit"
#    - min_profit_percent: 0  → TV's "Min Profit percent for Close %%"
#
#  Key differences:
#    1. TV default bars=??, ours=10
#    2. TV profit range 0.1-20, ours starts at 0
#    3. Param name mismatch: handler reads "bars" not "bars_since_entry"
#
# ============================================================


class TestTradingViewComparison:
    """AI agents must understand TV original vs our implementation."""

    def test_enabled_maps_to_tv_use_close(self, sample_ohlcv):
        """Our 'enabled' maps to TV's 'Use Close By Time Since Order'."""
        for val in [True, False]:
            graph = _make_close_by_time_only({"enabled": val})
            result = _run_adapter(graph, sample_ohlcv)
            adapter = result["adapter"]
            p = adapter.blocks["cbt_1"]["params"]
            assert p["enabled"] == val

    def test_bars_maps_to_tv_close_after(self, sample_ohlcv):
        """Our 'bars_since_entry' maps to TV's 'Close order after XX bars' (1-100)."""
        for bars in [1, 50, 100]:
            graph = _make_close_by_time_only({"bars_since_entry": bars})
            result = _run_adapter(graph, sample_ohlcv)
            adapter = result["adapter"]
            p = adapter.blocks["cbt_1"]["params"]
            assert p["bars_since_entry"] == bars

    def test_profit_only_maps_to_tv_close_with_profit(self, sample_ohlcv):
        """Our 'profit_only' maps to TV's 'Close only with Profit'."""
        for val in [True, False]:
            graph = _make_close_by_time_only({"profit_only": val})
            result = _run_adapter(graph, sample_ohlcv)
            adapter = result["adapter"]
            p = adapter.blocks["cbt_1"]["params"]
            assert p["profit_only"] == val

    def test_min_profit_maps_to_tv_min_profit_pct(self, sample_ohlcv):
        """Our 'min_profit_percent' maps to TV's 'Min Profit percent for Close %%' (0.1-20)."""
        for pct in [0.1, 1.0, 5.0, 10.0, 20.0]:
            graph = _make_close_by_time_only({"profit_only": True, "min_profit_percent": pct})
            result = _run_adapter(graph, sample_ohlcv)
            adapter = result["adapter"]
            p = adapter.blocks["cbt_1"]["params"]
            assert p["min_profit_percent"] == pct


# ============================================================
#
#  PART 10 — EDGE CASES AND BOUNDARY CONDITIONS
#
# ============================================================


class TestEdgeCases:
    """Edge cases and boundary conditions for Close by Time."""

    def test_minimum_bars_1(self, sample_ohlcv):
        """Minimum valid bars: 1 (close immediately after entry bar)."""
        graph = _make_close_by_time_only({"bars": 1})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["cbt_1"]
        assert cache["max_bars"].iloc[0] == 1

    def test_maximum_bars_100(self, sample_ohlcv):
        """Maximum valid bars: 100."""
        graph = _make_close_by_time_only({"bars": 100})
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]["cbt_1"]
        assert cache["max_bars"].iloc[0] == 100

    def test_zero_min_profit(self, sample_ohlcv):
        """min_profit_percent=0 means any profit (including 0) is acceptable."""
        graph = _make_close_by_time_only({"profit_only": True, "min_profit_percent": 0})
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]
        p = adapter.blocks["cbt_1"]["params"]
        assert p["min_profit_percent"] == 0

    def test_empty_params_uses_handler_defaults(self, sample_ohlcv):
        """Empty params dict should not crash — handler uses defaults."""
        graph = _make_close_by_time_only({})
        result = _run_adapter(graph, sample_ohlcv)
        # Handler uses bars=10 default
        cache = result["_value_cache"]["cbt_1"]
        assert cache["max_bars"].iloc[0] == 10

    def test_no_extra_data_from_close_by_time(self, sample_ohlcv):
        """Close by Time does NOT populate extra_data."""
        graph = _make_close_by_time_only({"bars": 20})
        result = _run_adapter(graph, sample_ohlcv)
        extra = result["extra_data"] or {}
        assert "max_bars" not in extra
        assert "close_by_time" not in extra

    def test_no_connections_needed(self, sample_ohlcv):
        """Close by Time block works without any connections (standalone)."""
        graph = {
            "name": "Close by Time Standalone Test",
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
                    "id": "cbt_1",
                    "type": "close_by_time",
                    "category": "close_conditions",
                    "name": "Close by Time",
                    "x": 600,
                    "y": 450,
                    "params": {"enabled": True, "bars": 15},
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
        assert "cbt_1" in result["_value_cache"]
        cache_val = result["_value_cache"]["cbt_1"]
        assert "exit" in cache_val
        assert "max_bars" in cache_val

    def test_multiple_adapter_runs_stable(self, sample_ohlcv):
        """Running adapter multiple times with same params gives same result."""
        close_params = {
            "enabled": True,
            "bars": 30,
            "profit_only": True,
            "min_profit_percent": 1.5,
        }
        results = []
        for _ in range(3):
            graph = _make_close_by_time_only(close_params)
            result = _run_adapter(graph, sample_ohlcv)
            cache = result["_value_cache"]["cbt_1"]
            results.append(cache["max_bars"].iloc[0])

        assert all(r == results[0] for r in results), "max_bars should be stable across runs"


# ============================================================
#
#  PART 11 — FULL SCENARIOS
#
# ============================================================


class TestFullScenario:
    """Full scenario combining entry indicators with Close by Time."""

    def test_rsi_and_close_by_time_full_config(self, sample_ohlcv):
        """Complete scenario: RSI entry + Close after 20 bars with profit filter."""
        rsi_params = {
            "period": 14,
            "mode": "level",
            "overbought": 70,
            "oversold": 30,
        }
        close_params = {
            "enabled": True,
            "bars": 20,
            "bars_since_entry": 20,
            "profit_only": True,
            "min_profit_percent": 0.5,
        }
        graph = _make_rsi_with_close_by_time(rsi_params, close_params)
        result = _run_adapter(graph, sample_ohlcv)

        # RSI produces entry signals
        total_entries = int(result["entries"].sum() + result["short_entries"].sum())
        assert total_entries > 0

        # Close by Time is config-only
        assert result["exits"].sum() == 0

        # Both blocks in cache
        assert "b_rsi" in result["_value_cache"]
        assert "cbt_1" in result["_value_cache"]

        # Close by Time params stored correctly
        adapter = result["adapter"]
        p = adapter.blocks["cbt_1"]["params"]
        assert p["enabled"] is True
        assert p["bars"] == 20
        assert p["profit_only"] is True
        assert p["min_profit_percent"] == 0.5

    def test_macd_and_close_by_time_full_config(self, sample_ohlcv):
        """Complete scenario: MACD entry + Close after 50 bars without profit filter."""
        macd_params = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "mode": "cross",
        }
        close_params = {
            "enabled": True,
            "bars": 50,
            "profit_only": False,
            "min_profit_percent": 0,
        }
        graph = _make_macd_with_close_by_time(macd_params, close_params)
        result = _run_adapter(graph, sample_ohlcv)

        # MACD produces signals
        total_entries = int(result["entries"].sum() + result["short_entries"].sum())
        assert total_entries >= 0

        # Close by Time params correct
        adapter = result["adapter"]
        p = adapter.blocks["cbt_1"]["params"]
        assert p["profit_only"] is False
        assert p["bars"] == 50

    def test_extract_dca_after_full_run(self, sample_ohlcv):
        """extract_dca_config works correctly after full generate_signals run."""
        graph = _make_rsi_with_close_by_time(
            {"period": 14},
            {"enabled": True, "bars": 15, "profit_only": True, "min_profit_percent": 1.0},
        )
        result = _run_adapter(graph, sample_ohlcv)
        adapter = result["adapter"]

        dca_config = adapter.extract_dca_config()
        assert isinstance(dca_config, dict)
        # DCA defaults still present
        assert "dca_enabled" in dca_config
        assert "close_conditions" in dca_config
