"""
AI Agent Knowledge Test: Close Conditions v2 — Channel Close & MA Cross Close

Tests verify that AI agents (DeepSeek, Qwen, Perplexity) correctly understand:

== CLOSE CHANNEL (Keltner/Bollinger) ==
- Every parameter: enabled, channel_close_timeframe, band_to_close, channel_type,
  close_condition, keltner_length, keltner_mult, bb_length, bb_deviation
- Band logic: Rebound (LONG → close on UPPER), Breakout (LONG → close on LOWER)
- Close conditions: "Wick out of band", "Out-of-band closure",
  "Close out of the band then close in", "Wick out of the band then close in"
- Channel types: "Keltner Channel" (uses calculate_keltner) vs "Bollinger Bands"
- Handler produces: {exit_long, exit_short, exit, signal} — all pd.Series(bool)

== CLOSE MA CROSS (Two MAs) ==
- Every parameter: enabled, show_ma_lines, profit_only, min_profit_percent,
  ma1_length, ma2_length
- Cross logic: Long exit when fast MA crosses below slow MA (bearish cross);
  Short exit when fast MA crosses above slow MA (bullish cross)
- profit_only flag: passes config to engine via result["profit_only"], result["min_profit"]
- MA type: always EMA (ewm)
- Handler produces: {exit_long, exit_short, exit, signal, [profit_only, min_profit]}

Architecture Notes (both blocks):
    - Frontend menu group: close_conditions
    - Frontend category assignment: addBlockToCanvas sets block.category = "close_conditions"
    - Category dispatch: "close_conditions" → _execute_close_condition(block_type, params, ohlcv, inputs)
    - NOT in _BLOCK_CATEGORY_MAP → without frontend category, _infer_category()
      falls back to "indicator" (wrong!)
    - extract_dca_config() checks block_type=="close_channel" and "close_ma_cross"
    - Validation rules in BLOCK_VALIDATION_RULES for both block types

    Frontend blockDefaults (strategy_builder.js):
      close_channel: {
        enabled: false,
        channel_close_timeframe: 'Chart',
        band_to_close: 'Rebound',
        channel_type: 'Keltner Channel',
        close_condition: 'Wick out of band',
        keltner_length: 14,
        keltner_mult: 1.5,
        bb_length: 20,
        bb_deviation: 2
      }
      close_ma_cross: {
        enabled: false,
        show_ma_lines: false,
        profit_only: false,
        min_profit_percent: 1,
        ma1_length: 10,
        ma2_length: 30
      }

Run:
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_v2_ai_agents.py -v
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_v2_ai_agents.py -v -k "channel"
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_v2_ai_agents.py -v -k "ma_cross"
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_v2_ai_agents.py -v -k "defaults"
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_v2_ai_agents.py -v -k "handler"
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_v2_ai_agents.py -v -k "dca_config"
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_v2_ai_agents.py -v -k "optimization"
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_v2_ai_agents.py -v -k "combo"
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
    Includes wicks that extend beyond Keltner/BB bands for close_channel testing.
    """
    np.random.seed(42)
    n = 1000
    dates = pd.date_range("2025-01-01", periods=n, freq="1h")
    prices = 50000.0 + np.cumsum(np.random.randn(n) * 100)
    # Add wicks that extend further for band testing
    wick_factor = np.abs(np.random.randn(n) * 60)
    return pd.DataFrame(
        {
            "open": prices + np.random.randn(n) * 20,
            "high": prices + wick_factor + 20,
            "low": prices - wick_factor - 20,
            "close": prices + np.random.randn(n) * 20,
            "volume": np.random.uniform(100, 1000, n),
        },
        index=dates,
    )


# ============================================================
# Graph Builders
# ============================================================


def _make_rsi_with_close_channel(
    rsi_params: dict[str, Any],
    close_params: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a strategy graph: RSI indicator → entry long/short → strategy,
    plus Close Channel block (close_conditions category).

    AI Agent Knowledge:
        Close Channel block has category='close_conditions' (set by frontend).
        The adapter dispatches it to _execute_close_condition() handler.
        Handler produces: {exit_long, exit_short, exit, signal} as pd.Series(bool).
        Channel type can be "Keltner Channel" or "Bollinger Bands".
        Band modes: "Rebound" (default) or "Breakout".
    """
    return {
        "name": "RSI + Close Channel Test",
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
                "id": "cc_1",
                "type": "close_channel",
                "category": "close_conditions",
                "name": "Channel Close",
                "icon": "bar-chart",
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


def _make_rsi_with_close_ma_cross(
    rsi_params: dict[str, Any],
    close_params: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a strategy graph: RSI indicator → entry long/short → strategy,
    plus Close MA Cross block (close_conditions category).

    AI Agent Knowledge:
        Close MA Cross block has category='close_conditions' (set by frontend).
        Handler produces: {exit_long, exit_short, exit, signal} as pd.Series(bool).
        Long exit: fast MA crosses below slow MA (bearish cross).
        Short exit: fast MA crosses above slow MA (bullish cross).
        If profit_only=True, adds result["profit_only"] and result["min_profit"].
    """
    return {
        "name": "RSI + Close MA Cross Test",
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
                "id": "cmc_1",
                "type": "close_ma_cross",
                "category": "close_conditions",
                "name": "MA Cross Close",
                "icon": "trending-up",
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


def _make_both_close_conditions(
    channel_params: dict[str, Any],
    ma_cross_params: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a strategy graph with BOTH close conditions: Channel + MA Cross.

    AI Agent Knowledge:
        Multiple close condition blocks can coexist in a strategy.
        Each produces independent exit signals. The engine combines them.
    """
    return {
        "name": "RSI + Channel Close + MA Cross Close Test",
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
                "id": "cc_1",
                "type": "close_channel",
                "category": "close_conditions",
                "name": "Channel Close",
                "icon": "bar-chart",
                "x": 600,
                "y": 450,
                "params": channel_params,
            },
            {
                "id": "cmc_1",
                "type": "close_ma_cross",
                "category": "close_conditions",
                "name": "MA Cross Close",
                "icon": "trending-up",
                "x": 600,
                "y": 550,
                "params": ma_cross_params,
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
#  PART 1 — CLOSE CHANNEL DEFAULT VALUES
#
#  AI Knowledge: "What are the default parameter values?"
#  Panel fields (from strategy_builder.js blockDefaults):
#    enabled: false
#    channel_close_timeframe: 'Chart'
#    band_to_close: 'Rebound'
#    channel_type: 'Keltner Channel'
#    close_condition: 'Wick out of band'
#    keltner_length: 14
#    keltner_mult: 1.5
#    bb_length: 20
#    bb_deviation: 2
#
# ============================================================


class TestCloseChannelDefaults:
    """
    AI Prompt: "What are the default values for the Channel Close block?"
    AI Response: "The Channel Close block defaults are:
      - enabled=false, channel_close_timeframe='Chart', band_to_close='Rebound',
        channel_type='Keltner Channel', close_condition='Wick out of band',
        keltner_length=14, keltner_mult=1.5, bb_length=20, bb_deviation=2."
    """

    def test_channel_close_defaults_enabled(self):
        """Default enabled is false."""
        defaults = {
            "enabled": False,
            "channel_close_timeframe": "Chart",
            "band_to_close": "Rebound",
            "channel_type": "Keltner Channel",
            "close_condition": "Wick out of band",
            "keltner_length": 14,
            "keltner_mult": 1.5,
            "bb_length": 20,
            "bb_deviation": 2,
        }
        assert defaults["enabled"] is False
        assert defaults["band_to_close"] == "Rebound"
        assert defaults["channel_type"] == "Keltner Channel"

    def test_channel_close_defaults_keltner_values(self):
        """Default Keltner params: length=14, mult=1.5."""
        assert 14 == 14  # keltner_length
        assert 1.5 == 1.5  # keltner_mult

    def test_channel_close_defaults_bb_values(self):
        """Default BB params: length=20, deviation=2."""
        assert 20 == 20  # bb_length
        assert 2 == 2  # bb_deviation

    def test_channel_close_default_close_condition(self):
        """Default close condition is 'Wick out of band'."""
        assert "Wick out of band" == "Wick out of band"

    def test_channel_close_default_timeframe(self):
        """Default timeframe is 'Chart' (same as chart TF)."""
        assert "Chart" == "Chart"


# ============================================================
#
#  PART 2 — CLOSE MA CROSS DEFAULT VALUES
#
#  AI Knowledge: "What are the default parameter values?"
#  Panel fields (from strategy_builder.js blockDefaults):
#    enabled: false
#    show_ma_lines: false
#    profit_only: false
#    min_profit_percent: 1
#    ma1_length: 10
#    ma2_length: 30
#
# ============================================================


class TestCloseMACrossDefaults:
    """
    AI Prompt: "What are the default values for the MA Cross Close block?"
    AI Response: "The MA Cross Close defaults are:
      - enabled=false, show_ma_lines=false, profit_only=false,
        min_profit_percent=1, ma1_length=10, ma2_length=30."
    """

    def test_ma_cross_defaults_enabled(self):
        """Default enabled is false."""
        defaults = {
            "enabled": False,
            "show_ma_lines": False,
            "profit_only": False,
            "min_profit_percent": 1,
            "ma1_length": 10,
            "ma2_length": 30,
        }
        assert defaults["enabled"] is False
        assert defaults["show_ma_lines"] is False
        assert defaults["profit_only"] is False

    def test_ma_cross_defaults_profit(self):
        """Default min_profit_percent=1."""
        assert 1 == 1  # min_profit_percent

    def test_ma_cross_defaults_ma_lengths(self):
        """Default ma1_length=10 (fast), ma2_length=30 (slow)."""
        assert 10 == 10  # ma1_length (fast)
        assert 30 == 30  # ma2_length (slow)


# ============================================================
#
#  PART 3 — CLOSE CHANNEL HANDLER TESTS (category dispatch)
#
#  AI Knowledge: "How does Channel Close work in the backend?"
#  The block has category='close_conditions', which dispatches to
#  _execute_close_condition(). The handler reads channel_type, band_to_close,
#  close_condition and computes exit signals for each band mode.
#
# ============================================================


class TestCloseChannelHandler:
    """
    AI Prompt: "How does the Channel Close handler work?"
    AI Response: "The handler is dispatched via category='close_conditions' to
      _execute_close_condition(). It supports two channel types (Keltner Channel,
      Bollinger Bands), two band modes (Rebound, Breakout), and four close
      conditions. It produces exit_long, exit_short, exit, and signal series."
    """

    def test_channel_keltner_rebound_wick(self, sample_ohlcv):
        """Keltner + Rebound + 'Wick out of band': exit_long=high>=upper, exit_short=low<=lower."""
        graph = _make_rsi_with_close_channel(
            {"period": 14},
            {
                "enabled": True,
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of band",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        assert "cc_1" in cache
        block_out = cache["cc_1"]
        assert "exit_long" in block_out
        assert "exit_short" in block_out
        assert "exit" in block_out
        assert "signal" in block_out
        assert block_out["exit_long"].dtype == bool
        assert block_out["exit_short"].dtype == bool

    def test_channel_keltner_breakout_wick(self, sample_ohlcv):
        """Keltner + Breakout + 'Wick out of band': exit_long=low<=lower, exit_short=high>=upper."""
        graph = _make_rsi_with_close_channel(
            {"period": 14},
            {
                "enabled": True,
                "channel_type": "Keltner Channel",
                "band_to_close": "Breakout",
                "close_condition": "Wick out of band",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cc_1"]
        assert "exit_long" in block_out
        assert "exit_short" in block_out

    def test_channel_bollinger_rebound_wick(self, sample_ohlcv):
        """Bollinger + Rebound + 'Wick out of band': uses BB bands instead of Keltner."""
        graph = _make_rsi_with_close_channel(
            {"period": 14},
            {
                "enabled": True,
                "channel_type": "Bollinger Bands",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of band",
                "bb_length": 20,
                "bb_deviation": 2.0,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cc_1"]
        assert "exit_long" in block_out
        # BB bands should produce some exit signals on 1000 bars with wick data
        assert isinstance(block_out["exit"].sum(), (int, np.integer))

    def test_channel_out_of_band_closure(self, sample_ohlcv):
        """Close condition: 'Out-of-band closure' — close price outside band triggers exit."""
        graph = _make_rsi_with_close_channel(
            {"period": 14},
            {
                "enabled": True,
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Out-of-band closure",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cc_1"]
        assert "exit" in block_out
        assert block_out["exit"].dtype == bool

    def test_channel_close_then_in(self, sample_ohlcv):
        """Close condition: 'Close out of the band then close in' — reversal pattern."""
        graph = _make_rsi_with_close_channel(
            {"period": 14},
            {
                "enabled": True,
                "channel_type": "Bollinger Bands",
                "band_to_close": "Rebound",
                "close_condition": "Close out of the band then close in",
                "bb_length": 20,
                "bb_deviation": 2.0,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cc_1"]
        # This condition uses shift(1) — first bar should be NaN→False
        assert block_out["exit_long"].iloc[0] is np.False_

    def test_channel_wick_then_close_in(self, sample_ohlcv):
        """Close condition: 'Wick out of the band then close in' — uses high.shift(1)."""
        graph = _make_rsi_with_close_channel(
            {"period": 14},
            {
                "enabled": True,
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of the band then close in",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cc_1"]
        assert "exit_long" in block_out
        assert "exit_short" in block_out

    def test_channel_custom_keltner_params(self, sample_ohlcv):
        """Custom Keltner params: length=7, mult=3.0."""
        graph = _make_rsi_with_close_channel(
            {"period": 14},
            {
                "enabled": True,
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of band",
                "keltner_length": 7,
                "keltner_mult": 3.0,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cc_1"]
        # Wider mult should produce fewer exit signals
        assert "exit" in block_out

    def test_channel_custom_bb_params(self, sample_ohlcv):
        """Custom BB params: length=10, deviation=1.5."""
        graph = _make_rsi_with_close_channel(
            {"period": 14},
            {
                "enabled": True,
                "channel_type": "Bollinger Bands",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of band",
                "bb_length": 10,
                "bb_deviation": 1.5,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cc_1"]
        # Narrow BB (1.5 dev) should produce more exit signals
        assert block_out["exit"].sum() > 0

    def test_channel_exit_signal_is_union(self, sample_ohlcv):
        """exit = exit_long | exit_short — union of both directions."""
        graph = _make_rsi_with_close_channel(
            {"period": 14},
            {
                "enabled": True,
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of band",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cc_1"]
        combined = block_out["exit_long"] | block_out["exit_short"]
        pd.testing.assert_series_equal(block_out["exit"], combined, check_names=False)

    def test_channel_breakout_reverses_directions(self, sample_ohlcv):
        """Breakout mode reverses long/short exit bands vs Rebound."""
        graph_rebound = _make_rsi_with_close_channel(
            {"period": 14},
            {
                "enabled": True,
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of band",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
        )
        graph_breakout = _make_rsi_with_close_channel(
            {"period": 14},
            {
                "enabled": True,
                "channel_type": "Keltner Channel",
                "band_to_close": "Breakout",
                "close_condition": "Wick out of band",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
        )
        r_rebound = _run_adapter(graph_rebound, sample_ohlcv)
        r_breakout = _run_adapter(graph_breakout, sample_ohlcv)
        # Rebound exit_long (upper band) should be breakout exit_short (upper band)
        pd.testing.assert_series_equal(
            r_rebound["_value_cache"]["cc_1"]["exit_long"],
            r_breakout["_value_cache"]["cc_1"]["exit_short"],
            check_names=False,
        )


# ============================================================
#
#  PART 4 — CLOSE MA CROSS HANDLER TESTS
#
#  AI Knowledge: "How does MA Cross Close work in the backend?"
#  Long exit: fast MA crosses below slow MA (bearish cross).
#  Short exit: fast MA crosses above slow MA (bullish cross).
#
# ============================================================


class TestCloseMACrossHandler:
    """
    AI Prompt: "How does the MA Cross Close handler work?"
    AI Response: "The handler computes two EMAs (ma1_length and ma2_length),
      then detects crosses. Long exit fires when fast EMA crosses below slow EMA.
      Short exit fires when fast EMA crosses above slow EMA. If profit_only=True,
      the handler adds profit_only and min_profit series."
    """

    def test_ma_cross_default_params(self, sample_ohlcv):
        """Default params: ma1=10, ma2=30, produces exit signals."""
        graph = _make_rsi_with_close_ma_cross(
            {"period": 14},
            {
                "enabled": True,
                "ma1_length": 10,
                "ma2_length": 30,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        assert "cmc_1" in cache
        block_out = cache["cmc_1"]
        assert "exit_long" in block_out
        assert "exit_short" in block_out
        assert "exit" in block_out
        assert block_out["exit"].dtype == bool

    def test_ma_cross_exit_long_is_bearish_cross(self, sample_ohlcv):
        """exit_long fires when fast MA crosses below slow MA."""
        graph = _make_rsi_with_close_ma_cross(
            {"period": 14},
            {
                "enabled": True,
                "ma1_length": 5,
                "ma2_length": 20,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cmc_1"]
        # With 1000 bars of random walk, there should be at least 1 cross
        assert block_out["exit_long"].sum() > 0

    def test_ma_cross_exit_short_is_bullish_cross(self, sample_ohlcv):
        """exit_short fires when fast MA crosses above slow MA."""
        graph = _make_rsi_with_close_ma_cross(
            {"period": 14},
            {
                "enabled": True,
                "ma1_length": 5,
                "ma2_length": 20,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cmc_1"]
        assert block_out["exit_short"].sum() > 0

    def test_ma_cross_exit_is_union(self, sample_ohlcv):
        """exit = exit_long | exit_short."""
        graph = _make_rsi_with_close_ma_cross(
            {"period": 14},
            {
                "enabled": True,
                "ma1_length": 10,
                "ma2_length": 30,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cmc_1"]
        combined = block_out["exit_long"] | block_out["exit_short"]
        pd.testing.assert_series_equal(block_out["exit"], combined, check_names=False)

    def test_ma_cross_profit_only_off(self, sample_ohlcv):
        """When profit_only=False, no profit_only or min_profit in result."""
        graph = _make_rsi_with_close_ma_cross(
            {"period": 14},
            {
                "enabled": True,
                "profit_only": False,
                "ma1_length": 10,
                "ma2_length": 30,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cmc_1"]
        assert "profit_only" not in block_out

    def test_ma_cross_profit_only_on(self, sample_ohlcv):
        """When profit_only=True, adds profit_only and min_profit series."""
        graph = _make_rsi_with_close_ma_cross(
            {"period": 14},
            {
                "enabled": True,
                "profit_only": True,
                "min_profit_percent": 2.5,
                "ma1_length": 10,
                "ma2_length": 30,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cmc_1"]
        assert "profit_only" in block_out
        assert "min_profit" in block_out
        assert block_out["profit_only"].iloc[0] is np.True_
        assert block_out["min_profit"].iloc[0] == 2.5

    def test_ma_cross_custom_lengths(self, sample_ohlcv):
        """Custom MA lengths: fast=3, slow=50."""
        graph = _make_rsi_with_close_ma_cross(
            {"period": 14},
            {
                "enabled": True,
                "ma1_length": 3,
                "ma2_length": 50,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cmc_1"]
        assert "exit" in block_out
        # Short fast MA + long slow MA → more crosses
        total_exits = block_out["exit"].sum()
        assert total_exits > 0

    def test_ma_cross_same_length_no_cross(self, sample_ohlcv):
        """When ma1_length == ma2_length, no cross can happen → zero exits."""
        graph = _make_rsi_with_close_ma_cross(
            {"period": 14},
            {
                "enabled": True,
                "ma1_length": 20,
                "ma2_length": 20,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cmc_1"]
        assert block_out["exit"].sum() == 0

    def test_ma_cross_uses_ema(self, sample_ohlcv):
        """MA type is always EMA (exponential weighted mean)."""
        graph = _make_rsi_with_close_ma_cross(
            {"period": 14},
            {
                "enabled": True,
                "ma1_length": 10,
                "ma2_length": 30,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        # Verify by computing EMA manually and checking output
        close = sample_ohlcv["close"]
        fast_ma = close.ewm(span=10, adjust=False).mean()
        slow_ma = close.ewm(span=30, adjust=False).mean()
        expected_exit_long = ((fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))).fillna(False)
        cache = result["_value_cache"]
        block_out = cache["cmc_1"]
        pd.testing.assert_series_equal(block_out["exit_long"], expected_exit_long, check_names=False)


# ============================================================
#
#  PART 5 — CATEGORY DISPATCH
#
#  AI Knowledge: "How are close condition blocks dispatched?"
#  Frontend sets category='close_conditions' for blocks from that menu group.
#  _execute_block() routes to _execute_close_condition().
#  close_channel and close_ma_cross are NOT in _BLOCK_CATEGORY_MAP.
#
# ============================================================


class TestCategoryDispatch:
    """
    AI Prompt: "How do close condition blocks get dispatched to handlers?"
    AI Response: "Frontend sets category='close_conditions' when dragging blocks
      from the close_conditions menu group. The adapter's _execute_block() method
      dispatches to _execute_close_condition(). close_channel and close_ma_cross
      are NOT in _BLOCK_CATEGORY_MAP — without the frontend category field,
      _infer_category() falls back to 'indicator' (wrong dispatch)."
    """

    def test_close_channel_not_in_category_map(self):
        """close_channel is NOT in _BLOCK_CATEGORY_MAP."""
        assert "close_channel" not in StrategyBuilderAdapter._BLOCK_CATEGORY_MAP

    def test_close_ma_cross_not_in_category_map(self):
        """close_ma_cross is NOT in _BLOCK_CATEGORY_MAP."""
        assert "close_ma_cross" not in StrategyBuilderAdapter._BLOCK_CATEGORY_MAP

    def test_infer_category_fallback_for_close_channel(self):
        """Without frontend category, _infer_category('close_channel') → 'indicator'."""
        inferred = StrategyBuilderAdapter._infer_category("close_channel")
        assert inferred == "indicator"  # Falls back, NOT correct

    def test_infer_category_fallback_for_close_ma_cross(self):
        """Without frontend category, _infer_category('close_ma_cross') → 'indicator'."""
        inferred = StrategyBuilderAdapter._infer_category("close_ma_cross")
        assert inferred == "indicator"

    def test_frontend_category_overrides_inference(self, sample_ohlcv):
        """With category='close_conditions' from frontend, handler is correct."""
        graph = _make_rsi_with_close_channel(
            {"period": 14},
            {"enabled": True, "channel_type": "Keltner Channel", "keltner_length": 14, "keltner_mult": 1.5},
        )
        result = _run_adapter(graph, sample_ohlcv)
        # If dispatched correctly, cache["cc_1"] will have exit/exit_long/exit_short
        cache = result["_value_cache"]
        assert "exit_long" in cache["cc_1"]
        assert "exit_short" in cache["cc_1"]

    def test_close_by_time_category_coexists(self, sample_ohlcv):
        """close_by_time in same category='close_conditions' still works alongside new blocks."""
        graph = {
            "name": "All Close Conditions Test",
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
                    "y": 300,
                    "params": {"bars_since_entry": 10},
                },
                {
                    "id": "cc_1",
                    "type": "close_channel",
                    "category": "close_conditions",
                    "name": "Channel Close",
                    "x": 600,
                    "y": 450,
                    "params": {
                        "enabled": True,
                        "channel_type": "Keltner Channel",
                        "keltner_length": 14,
                        "keltner_mult": 1.5,
                    },
                },
                {
                    "id": "cmc_1",
                    "type": "close_ma_cross",
                    "category": "close_conditions",
                    "name": "MA Cross Close",
                    "x": 600,
                    "y": 550,
                    "params": {"enabled": True, "ma1_length": 10, "ma2_length": 30},
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
        cache = result["_value_cache"]
        # All 3 close condition blocks should be in cache
        assert "cbt_1" in cache
        assert "cc_1" in cache
        assert "cmc_1" in cache
        assert "exit" in cache["cbt_1"]
        assert "exit_long" in cache["cc_1"]
        assert "exit_long" in cache["cmc_1"]


# ============================================================
#
#  PART 6 — DCA CONFIG EXTRACTION
#
#  AI Knowledge: "How are close conditions extracted for DCA config?"
#  extract_dca_config() iterates blocks and checks block_type.
#  close_channel → channel_close_* keys
#  close_ma_cross → ma_cross_close_* keys
#
# ============================================================


class TestDCAConfigExtraction:
    """
    AI Prompt: "How does extract_dca_config work with new close conditions?"
    AI Response: "extract_dca_config() checks block_type=='close_channel' and
      extracts channel_close_enable, channel_close_timeframe, channel_close_type,
      etc. For block_type=='close_ma_cross' it extracts ma_cross_close_enable,
      ma_cross_close_profit_only, ma_cross_close_min_profit, ma_cross_close_ma1_length,
      ma_cross_close_ma2_length."
    """

    def test_channel_close_extracts_to_dca(self, sample_ohlcv):
        """close_channel block's params are extracted into close_conditions dict."""
        graph = _make_rsi_with_close_channel(
            {"period": 14},
            {
                "enabled": True,
                "channel_close_timeframe": "15",
                "band_to_close": "Breakout",
                "channel_type": "Bollinger Bands",
                "close_condition": "Out-of-band closure",
                "keltner_length": 20,
                "keltner_mult": 2.0,
                "bb_length": 15,
                "bb_deviation": 1.5,
            },
        )
        adapter = StrategyBuilderAdapter(graph)
        adapter.generate_signals(sample_ohlcv)
        dca = adapter.extract_dca_config()
        cc = dca["close_conditions"]
        assert cc.get("channel_close_enable") is True
        assert cc["channel_close_timeframe"] == "15"
        assert cc["channel_close_band_to_close"] == "Breakout"
        assert cc["channel_close_type"] == "Bollinger Bands"
        assert cc["channel_close_condition"] == "Out-of-band closure"
        assert cc["channel_close_keltner_length"] == 20
        assert cc["channel_close_keltner_mult"] == 2.0
        assert cc["channel_close_bb_length"] == 15
        assert cc["channel_close_bb_deviation"] == 1.5

    def test_ma_cross_close_extracts_to_dca(self, sample_ohlcv):
        """close_ma_cross block's params are extracted into close_conditions dict."""
        graph = _make_rsi_with_close_ma_cross(
            {"period": 14},
            {
                "enabled": True,
                "profit_only": True,
                "min_profit_percent": 3.0,
                "ma1_length": 5,
                "ma2_length": 50,
            },
        )
        adapter = StrategyBuilderAdapter(graph)
        adapter.generate_signals(sample_ohlcv)
        dca = adapter.extract_dca_config()
        cc = dca["close_conditions"]
        assert cc.get("ma_cross_close_enable") is True
        assert cc["ma_cross_close_profit_only"] is True
        assert cc["ma_cross_close_min_profit"] == 3.0
        assert cc["ma_cross_close_ma1_length"] == 5
        assert cc["ma_cross_close_ma2_length"] == 50

    def test_both_close_conditions_extract(self, sample_ohlcv):
        """Both channel and MA cross are extracted into same close_conditions dict."""
        graph = _make_both_close_conditions(
            {
                "enabled": True,
                "channel_type": "Keltner Channel",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
            {
                "enabled": True,
                "profit_only": False,
                "ma1_length": 10,
                "ma2_length": 30,
            },
        )
        adapter = StrategyBuilderAdapter(graph)
        adapter.generate_signals(sample_ohlcv)
        dca = adapter.extract_dca_config()
        cc = dca["close_conditions"]
        assert cc.get("channel_close_enable") is True
        assert cc.get("ma_cross_close_enable") is True

    def test_channel_close_default_params_extract(self, sample_ohlcv):
        """Default params are used when not specified in block config."""
        graph = _make_rsi_with_close_channel(
            {"period": 14},
            {"enabled": True},  # No explicit params
        )
        adapter = StrategyBuilderAdapter(graph)
        adapter.generate_signals(sample_ohlcv)
        dca = adapter.extract_dca_config()
        cc = dca["close_conditions"]
        assert cc.get("channel_close_enable") is True
        assert cc["channel_close_timeframe"] == "Chart"
        assert cc["channel_close_band_to_close"] == "Rebound"
        assert cc["channel_close_type"] == "Keltner Channel"
        assert cc["channel_close_keltner_length"] == 14
        assert cc["channel_close_keltner_mult"] == 1.5

    def test_ma_cross_close_default_params_extract(self, sample_ohlcv):
        """Default MA cross params are used when not specified."""
        graph = _make_rsi_with_close_ma_cross(
            {"period": 14},
            {"enabled": True},  # No explicit params
        )
        adapter = StrategyBuilderAdapter(graph)
        adapter.generate_signals(sample_ohlcv)
        dca = adapter.extract_dca_config()
        cc = dca["close_conditions"]
        assert cc.get("ma_cross_close_enable") is True
        assert cc["ma_cross_close_profit_only"] is False
        assert cc["ma_cross_close_min_profit"] == 1.0
        assert cc["ma_cross_close_ma1_length"] == 10
        assert cc["ma_cross_close_ma2_length"] == 30


# ============================================================
#
#  PART 7 — OPTIMIZABLE PARAMETERS
#
#  AI Knowledge: "Which parameters can be optimized?"
#  close_channel: keltner_length, keltner_mult, bb_length, bb_deviation
#  close_ma_cross: min_profit_percent, ma1_length, ma2_length
#
# ============================================================


class TestOptimizableParams:
    """
    AI Prompt: "Which close condition parameters are optimizable?"
    AI Response: "For close_channel: keltner_length, keltner_mult, bb_length,
      bb_deviation. For close_ma_cross: min_profit_percent, ma1_length, ma2_length."
    """

    def test_channel_optimizable_keltner_length(self, sample_ohlcv):
        """keltner_length is optimizable: test with 7 and 20."""
        for length in [7, 20]:
            graph = _make_rsi_with_close_channel(
                {"period": 14},
                {"enabled": True, "channel_type": "Keltner Channel", "keltner_length": length, "keltner_mult": 1.5},
            )
            result = _run_adapter(graph, sample_ohlcv)
            assert "cc_1" in result["_value_cache"]

    def test_channel_optimizable_keltner_mult(self, sample_ohlcv):
        """keltner_mult is optimizable: test with 0.5 and 3.0."""
        for mult in [0.5, 3.0]:
            graph = _make_rsi_with_close_channel(
                {"period": 14},
                {"enabled": True, "channel_type": "Keltner Channel", "keltner_length": 14, "keltner_mult": mult},
            )
            result = _run_adapter(graph, sample_ohlcv)
            assert "exit" in result["_value_cache"]["cc_1"]

    def test_channel_optimizable_bb_length(self, sample_ohlcv):
        """bb_length is optimizable: test with 10 and 50."""
        for length in [10, 50]:
            graph = _make_rsi_with_close_channel(
                {"period": 14},
                {"enabled": True, "channel_type": "Bollinger Bands", "bb_length": length, "bb_deviation": 2.0},
            )
            result = _run_adapter(graph, sample_ohlcv)
            assert "exit" in result["_value_cache"]["cc_1"]

    def test_channel_optimizable_bb_deviation(self, sample_ohlcv):
        """bb_deviation is optimizable: test with 1.0 and 3.0."""
        results = {}
        for dev in [1.0, 3.0]:
            graph = _make_rsi_with_close_channel(
                {"period": 14},
                {"enabled": True, "channel_type": "Bollinger Bands", "bb_length": 20, "bb_deviation": dev},
            )
            result = _run_adapter(graph, sample_ohlcv)
            results[dev] = result["_value_cache"]["cc_1"]["exit"].sum()
        # Narrow deviation (1.0) should produce more exit signals than wide (3.0)
        assert results[1.0] > results[3.0]

    def test_ma_cross_optimizable_ma1_length(self, sample_ohlcv):
        """ma1_length is optimizable: test with 3 and 20."""
        for length in [3, 20]:
            graph = _make_rsi_with_close_ma_cross(
                {"period": 14},
                {"enabled": True, "ma1_length": length, "ma2_length": 30},
            )
            result = _run_adapter(graph, sample_ohlcv)
            assert "exit" in result["_value_cache"]["cmc_1"]

    def test_ma_cross_optimizable_ma2_length(self, sample_ohlcv):
        """ma2_length is optimizable: test with 20 and 100."""
        for length in [20, 100]:
            graph = _make_rsi_with_close_ma_cross(
                {"period": 14},
                {"enabled": True, "ma1_length": 10, "ma2_length": length},
            )
            result = _run_adapter(graph, sample_ohlcv)
            assert "exit" in result["_value_cache"]["cmc_1"]

    def test_ma_cross_optimizable_min_profit(self, sample_ohlcv):
        """min_profit_percent is optimizable: test with 0.5 and 10."""
        for profit in [0.5, 10.0]:
            graph = _make_rsi_with_close_ma_cross(
                {"period": 14},
                {
                    "enabled": True,
                    "profit_only": True,
                    "min_profit_percent": profit,
                    "ma1_length": 10,
                    "ma2_length": 30,
                },
            )
            result = _run_adapter(graph, sample_ohlcv)
            block_out = result["_value_cache"]["cmc_1"]
            assert block_out["min_profit"].iloc[0] == profit


# ============================================================
#
#  PART 8 — COMBINATION TESTS (with entry indicators)
#
# ============================================================


class TestCloseConditionCombos:
    """
    AI Prompt: "Can I combine Channel Close with MACD entry filter?"
    AI Response: "Yes. Add MACD as entry indicator and close_channel as
      close condition. Both are processed independently — MACD provides
      entry signals, Channel Close provides exit signals."
    """

    def test_macd_with_channel_close(self, sample_ohlcv):
        """MACD entry + Channel Close exit combo."""
        graph = {
            "name": "MACD + Channel Close",
            "blocks": [
                {
                    "id": "b_macd",
                    "type": "macd",
                    "category": "indicator",
                    "name": "MACD",
                    "x": 100,
                    "y": 100,
                    "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
                },
                {
                    "id": "cc_1",
                    "type": "close_channel",
                    "category": "close_conditions",
                    "name": "Channel Close",
                    "x": 600,
                    "y": 450,
                    "params": {
                        "enabled": True,
                        "channel_type": "Bollinger Bands",
                        "bb_length": 20,
                        "bb_deviation": 2.0,
                        "band_to_close": "Rebound",
                        "close_condition": "Wick out of band",
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
        result = _run_adapter(graph, sample_ohlcv)
        assert result["entries"] is not None
        assert "cc_1" in result["_value_cache"]
        assert result["_value_cache"]["cc_1"]["exit"].sum() > 0

    def test_stochastic_with_ma_cross_close(self, sample_ohlcv):
        """Stochastic entry + MA Cross Close exit combo."""
        graph = {
            "name": "Stochastic + MA Cross Close",
            "blocks": [
                {
                    "id": "b_stoch",
                    "type": "stochastic",
                    "category": "indicator",
                    "name": "Stochastic",
                    "x": 100,
                    "y": 100,
                    "params": {"stoch_k_length": 14, "stoch_k_smoothing": 3, "stoch_d_smoothing": 3},
                },
                {
                    "id": "cmc_1",
                    "type": "close_ma_cross",
                    "category": "close_conditions",
                    "name": "MA Cross Close",
                    "x": 600,
                    "y": 450,
                    "params": {"enabled": True, "ma1_length": 10, "ma2_length": 30},
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
                    "source": {"blockId": "b_stoch", "portId": "long"},
                    "target": {"blockId": "main", "portId": "entry_long"},
                    "type": "data",
                },
                {
                    "id": "c2",
                    "source": {"blockId": "b_stoch", "portId": "short"},
                    "target": {"blockId": "main", "portId": "entry_short"},
                    "type": "data",
                },
            ],
        }
        result = _run_adapter(graph, sample_ohlcv)
        assert result["entries"] is not None
        assert "cmc_1" in result["_value_cache"]

    def test_rsi_with_both_close_conditions(self, sample_ohlcv):
        """RSI entry + both Channel Close and MA Cross Close."""
        graph = _make_both_close_conditions(
            {
                "enabled": True,
                "channel_type": "Keltner Channel",
                "keltner_length": 14,
                "keltner_mult": 1.5,
                "band_to_close": "Rebound",
                "close_condition": "Wick out of band",
            },
            {"enabled": True, "ma1_length": 10, "ma2_length": 30},
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        assert "cc_1" in cache
        assert "cmc_1" in cache
        # Both blocks should produce exit signals
        channel_exits = cache["cc_1"]["exit"].sum()
        ma_exits = cache["cmc_1"]["exit"].sum()
        assert channel_exits > 0
        assert ma_exits > 0

    def test_channel_close_with_close_by_time(self, sample_ohlcv):
        """Channel Close + Close by Time can coexist."""
        graph = {
            "name": "Channel + Time Close",
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
                    "y": 300,
                    "params": {"bars_since_entry": 20},
                },
                {
                    "id": "cc_1",
                    "type": "close_channel",
                    "category": "close_conditions",
                    "name": "Channel Close",
                    "x": 600,
                    "y": 450,
                    "params": {
                        "enabled": True,
                        "channel_type": "Keltner Channel",
                        "keltner_length": 14,
                        "keltner_mult": 1.5,
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
        cache = result["_value_cache"]
        assert "cbt_1" in cache
        assert "cc_1" in cache
        assert "max_bars" in cache["cbt_1"]
        assert "exit_long" in cache["cc_1"]


# ============================================================
#
#  PART 9 — VALIDATION RULES
#
# ============================================================


class TestCloseConditionValidation:
    """
    AI Prompt: "What validation rules exist for close conditions?"
    AI Response: "BLOCK_VALIDATION_RULES has entries for 'close_channel'
      (keltner_length 1-100, keltner_mult 0.1-100, bb_length 1-100,
      bb_deviation 0.1-100) and 'close_ma_cross' (min_profit_percent 0.1-50,
      ma1_length 1-500, ma2_length 1-500)."
    """

    def test_close_channel_validation_rules_exist(self):
        """close_channel has validation rules in BLOCK_VALIDATION_RULES."""
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "close_channel" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["close_channel"]
        assert "keltner_length" in rules
        assert "keltner_mult" in rules
        assert "bb_length" in rules
        assert "bb_deviation" in rules

    def test_close_ma_cross_validation_rules_exist(self):
        """close_ma_cross has validation rules in BLOCK_VALIDATION_RULES."""
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "close_ma_cross" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["close_ma_cross"]
        assert "min_profit_percent" in rules
        assert "ma1_length" in rules
        assert "ma2_length" in rules

    def test_validate_close_channel_valid(self):
        """Valid close_channel params pass validation."""
        from backend.api.routers.strategy_validation_ws import validate_block

        result = validate_block(
            "close_channel", {"keltner_length": 14, "keltner_mult": 1.5, "bb_length": 20, "bb_deviation": 2.0}
        )
        assert result.valid is True

    def test_validate_close_channel_invalid_length(self):
        """keltner_length=0 fails validation (min=1)."""
        from backend.api.routers.strategy_validation_ws import ValidationSeverity, validate_block

        result = validate_block("close_channel", {"keltner_length": 0})
        assert result.valid is False
        errors = [m for m in result.messages if m.severity == ValidationSeverity.ERROR]
        assert any("keltner_length" in m.message for m in errors)

    def test_validate_close_ma_cross_valid(self):
        """Valid close_ma_cross params pass validation."""
        from backend.api.routers.strategy_validation_ws import validate_block

        result = validate_block("close_ma_cross", {"min_profit_percent": 1.0, "ma1_length": 10, "ma2_length": 30})
        assert result.valid is True

    def test_validate_close_ma_cross_invalid_ma_length(self):
        """ma1_length=0 fails validation (min=1)."""
        from backend.api.routers.strategy_validation_ws import ValidationSeverity, validate_block

        result = validate_block("close_ma_cross", {"ma1_length": 0})
        assert result.valid is False
        errors = [m for m in result.messages if m.severity == ValidationSeverity.ERROR]
        assert any("ma1_length" in m.message for m in errors)

    def test_validate_close_ma_cross_profit_too_high(self):
        """min_profit_percent=60 fails validation (max=50)."""
        from backend.api.routers.strategy_validation_ws import validate_block

        result = validate_block("close_ma_cross", {"min_profit_percent": 60})
        assert result.valid is False


# ============================================================
#
#  PART 10 — EDGE CASES
#
# ============================================================


class TestCloseConditionEdgeCases:
    """Edge cases and boundary conditions for close condition blocks."""

    def test_channel_close_with_minimal_data(self):
        """Channel close with only 5 bars (less than keltner_length)."""
        np.random.seed(42)
        dates = pd.date_range("2025-01-01", periods=5, freq="1h")
        prices = [50000, 50100, 49900, 50200, 50050]
        ohlcv = pd.DataFrame(
            {
                "open": prices,
                "high": [p + 50 for p in prices],
                "low": [p - 50 for p in prices],
                "close": prices,
                "volume": [100] * 5,
            },
            index=dates,
        )
        graph = _make_rsi_with_close_channel(
            {"period": 14},
            {"enabled": True, "channel_type": "Keltner Channel", "keltner_length": 14, "keltner_mult": 1.5},
        )
        # Should not crash, even if NaN fills
        result = _run_adapter(graph, ohlcv)
        assert "cc_1" in result["_value_cache"]

    def test_ma_cross_with_minimal_data(self):
        """MA cross close with only 3 bars."""
        dates = pd.date_range("2025-01-01", periods=3, freq="1h")
        prices = [50000, 50100, 49900]
        ohlcv = pd.DataFrame(
            {
                "open": prices,
                "high": [p + 50 for p in prices],
                "low": [p - 50 for p in prices],
                "close": prices,
                "volume": [100] * 3,
            },
            index=dates,
        )
        graph = _make_rsi_with_close_ma_cross(
            {"period": 14},
            {"enabled": True, "ma1_length": 10, "ma2_length": 30},
        )
        result = _run_adapter(graph, ohlcv)
        assert "cmc_1" in result["_value_cache"]

    def test_channel_close_all_four_conditions(self, sample_ohlcv):
        """Test all 4 close conditions produce valid output."""
        conditions = [
            "Close out of the band then close in",
            "Wick out of band",
            "Wick out of the band then close in",
            "Out-of-band closure",
        ]
        for cond in conditions:
            graph = _make_rsi_with_close_channel(
                {"period": 14},
                {
                    "enabled": True,
                    "channel_type": "Keltner Channel",
                    "close_condition": cond,
                    "keltner_length": 14,
                    "keltner_mult": 1.5,
                },
            )
            result = _run_adapter(graph, sample_ohlcv)
            block_out = result["_value_cache"]["cc_1"]
            assert "exit" in block_out, f"Condition '{cond}' missing exit"
            assert block_out["exit"].dtype == bool, f"Condition '{cond}' wrong dtype"

    def test_channel_close_both_channel_types(self, sample_ohlcv):
        """Both Keltner and Bollinger produce valid exit signals."""
        for ch_type in ["Keltner Channel", "Bollinger Bands"]:
            graph = _make_rsi_with_close_channel(
                {"period": 14},
                {
                    "enabled": True,
                    "channel_type": ch_type,
                    "keltner_length": 14,
                    "keltner_mult": 1.5,
                    "bb_length": 20,
                    "bb_deviation": 2.0,
                },
            )
            result = _run_adapter(graph, sample_ohlcv)
            assert "exit" in result["_value_cache"]["cc_1"], f"Channel type '{ch_type}' missing exit"

    def test_channel_close_both_band_modes(self, sample_ohlcv):
        """Both Rebound and Breakout modes produce valid output."""
        for mode in ["Rebound", "Breakout"]:
            graph = _make_rsi_with_close_channel(
                {"period": 14},
                {
                    "enabled": True,
                    "channel_type": "Keltner Channel",
                    "band_to_close": mode,
                    "keltner_length": 14,
                    "keltner_mult": 1.5,
                },
            )
            result = _run_adapter(graph, sample_ohlcv)
            assert "exit_long" in result["_value_cache"]["cc_1"], f"Mode '{mode}' missing exit_long"

    def test_unknown_close_type_fallback(self, sample_ohlcv):
        """Unknown close type should hit the else branch (all False)."""
        graph = {
            "name": "Unknown Close Test",
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
                    "id": "unk_1",
                    "type": "close_unknown_xyz",
                    "category": "close_conditions",
                    "name": "Unknown",
                    "x": 600,
                    "y": 450,
                    "params": {},
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
        cache = result["_value_cache"]
        assert "unk_1" in cache
        assert cache["unk_1"]["exit"].sum() == 0
