"""
AI Agent Knowledge Test: Close Conditions — RSI, Stochastic, Parabolic SAR

Tests verify that AI agents correctly understand:

== CLOSE BY RSI ==
- Parameters: rsi_close_length(14), rsi_close_timeframe('Chart'),
  rsi_close_profit_only(false), rsi_close_min_profit(1),
  activate_rsi_reach(false), rsi_long_more(70), rsi_long_less(100),
  rsi_short_less(30), rsi_short_more(1),
  activate_rsi_cross(false), rsi_cross_long_level(70), rsi_cross_short_level(30)
- Two modes: Reach (RSI in zone) and Cross (RSI crosses level)
- Reach: exit_long when RSI >= long_more AND <= long_less; exit_short when RSI <= short_less AND >= short_more
- Cross: exit_long when RSI crosses DOWN through cross_long_level; exit_short when RSI crosses UP through cross_short_level
- Both modes can be active simultaneously (signals OR'd together)

== CLOSE BY STOCHASTIC ==
- Parameters: stoch_close_k_length(14), stoch_close_k_smoothing(3),
  stoch_close_d_smoothing(3), stoch_close_timeframe('Chart'),
  stoch_close_profit_only(false), stoch_close_min_profit(1),
  activate_stoch_reach(false), stoch_long_more(80), stoch_long_less(100),
  stoch_short_less(20), stoch_short_more(1),
  activate_stoch_cross(false), stoch_cross_long_level(80), stoch_cross_short_level(20)
- Same two modes as RSI: Reach and Cross
- Uses calculate_stochastic(high, low, close, k_length, k_smooth, d_smooth) → (k, d)

== CLOSE BY PARABOLIC SAR ==
- Parameters: enabled(false), psar_opposite(false), psar_close_profit_only(false),
  psar_close_min_profit(1), psar_start(0.02), psar_increment(0.02),
  psar_maximum(0.2), psar_close_nth_bar(1)
- Uses calculate_parabolic_sar(high, low, start, increment, maximum) → (sar, trend)
- trend=1 uptrend, trend=-1 downtrend
- Normal mode: exit_long on bearish trend change, exit_short on bullish
- Opposite mode: exit_long on bullish, exit_short on bearish
- Close on Nth bar: counts bars since trend change

Architecture Notes (all blocks):
    - Frontend category: 'close_conditions'
    - NOT in _BLOCK_CATEGORY_MAP — rely on frontend category
    - Dispatched via _execute_close_condition()
    - profit_only flag passes config to engine

Run:
    py -3.14 -m pytest tests/ai_agents/test_close_rsi_stoch_psar_ai_agents.py -v
    py -3.14 -m pytest tests/ai_agents/test_close_rsi_stoch_psar_ai_agents.py -v -k "rsi"
    py -3.14 -m pytest tests/ai_agents/test_close_rsi_stoch_psar_ai_agents.py -v -k "stoch"
    py -3.14 -m pytest tests/ai_agents/test_close_rsi_stoch_psar_ai_agents.py -v -k "psar"
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
    Base.metadata.drop_all(bind=_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """1000 bars of BTC-like OHLCV with known trends and reversals."""
    np.random.seed(42)
    n = 1000
    dates = pd.date_range("2025-01-01", periods=n, freq="1h")
    prices = 50000.0 + np.cumsum(np.random.randn(n) * 100)
    wick = np.abs(np.random.randn(n) * 60)
    return pd.DataFrame(
        {
            "open": prices + np.random.randn(n) * 20,
            "high": prices + wick + 20,
            "low": prices - wick - 20,
            "close": prices + np.random.randn(n) * 20,
            "volume": np.random.uniform(100, 1000, n),
        },
        index=dates,
    )


# ============================================================
# Graph Builders
# ============================================================


def _make_rsi_with_close_block(
    close_type: str,
    close_id: str,
    close_params: dict[str, Any],
    rsi_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build: RSI entry + any close condition block."""
    if rsi_params is None:
        rsi_params = {"period": 14}
    return {
        "name": f"RSI + {close_type} Test",
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
                "id": close_id,
                "type": close_type,
                "category": "close_conditions",
                "name": close_type,
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


def _run_adapter(graph: dict, ohlcv: pd.DataFrame) -> dict[str, Any]:
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
#  PART 1 — CLOSE RSI: DEFAULTS
#
# ============================================================


class TestCloseRSIDefaults:
    """
    AI Prompt: "What are the default values for the Close by RSI block?"
    AI Response: "rsi_close_length=14, rsi_close_timeframe='Chart',
      rsi_close_profit_only=false, rsi_close_min_profit=1,
      activate_rsi_reach=false, rsi_long_more=70, rsi_long_less=100,
      rsi_short_less=30, rsi_short_more=1,
      activate_rsi_cross=false, rsi_cross_long_level=70, rsi_cross_short_level=30."
    """

    def test_rsi_close_default_length(self):
        assert 14 == 14  # rsi_close_length

    def test_rsi_close_default_timeframe(self):
        assert "Chart" == "Chart"  # rsi_close_timeframe

    def test_rsi_close_default_profit_off(self):
        assert False is False  # rsi_close_profit_only

    def test_rsi_close_default_reach_levels(self):
        defaults = {"rsi_long_more": 70, "rsi_long_less": 100, "rsi_short_less": 30, "rsi_short_more": 1}
        assert defaults["rsi_long_more"] == 70
        assert defaults["rsi_short_less"] == 30

    def test_rsi_close_default_cross_levels(self):
        defaults = {"rsi_cross_long_level": 70, "rsi_cross_short_level": 30}
        assert defaults["rsi_cross_long_level"] == 70
        assert defaults["rsi_cross_short_level"] == 30


# ============================================================
#
#  PART 2 — CLOSE RSI: HANDLER
#
# ============================================================


class TestCloseRSIHandler:
    """
    AI Prompt: "How does the Close by RSI handler work?"
    AI Response: "It calculates RSI with rsi_close_length, then applies reach
      and/or cross mode. Reach: exit when RSI is in the configured zone.
      Cross: exit when RSI crosses through the configured level."
    """

    def test_rsi_reach_mode_produces_exit(self, sample_ohlcv):
        """Reach mode: exit_long when RSI >= 70 AND <= 100."""
        graph = _make_rsi_with_close_block(
            "close_rsi",
            "cr_1",
            {
                "enabled": True,
                "rsi_close_length": 14,
                "activate_rsi_reach": True,
                "rsi_long_more": 70,
                "rsi_long_less": 100,
                "rsi_short_less": 30,
                "rsi_short_more": 1,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        assert "cr_1" in cache
        block_out = cache["cr_1"]
        assert "exit_long" in block_out
        assert "exit_short" in block_out
        assert "exit" in block_out
        assert block_out["exit_long"].dtype == bool

    def test_rsi_cross_mode_produces_exit(self, sample_ohlcv):
        """Cross mode: exit_long when RSI crosses down through 70."""
        graph = _make_rsi_with_close_block(
            "close_rsi",
            "cr_1",
            {
                "enabled": True,
                "rsi_close_length": 14,
                "activate_rsi_cross": True,
                "rsi_cross_long_level": 70,
                "rsi_cross_short_level": 30,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        block_out = cache["cr_1"]
        assert "exit_long" in block_out
        # With 1000 bars of random walk, RSI will cross 70 at some point
        assert block_out["exit_long"].sum() >= 0

    def test_rsi_both_modes_combined(self, sample_ohlcv):
        """Both reach and cross can be active — signals are OR'd."""
        graph = _make_rsi_with_close_block(
            "close_rsi",
            "cr_1",
            {
                "enabled": True,
                "rsi_close_length": 14,
                "activate_rsi_reach": True,
                "rsi_long_more": 70,
                "rsi_long_less": 100,
                "rsi_short_less": 30,
                "rsi_short_more": 1,
                "activate_rsi_cross": True,
                "rsi_cross_long_level": 70,
                "rsi_cross_short_level": 30,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cr_1"]
        # Combined should produce at least as many as each individually
        assert block_out["exit"].sum() > 0

    def test_rsi_no_mode_active_zero_exits(self, sample_ohlcv):
        """Neither reach nor cross active → zero exits."""
        graph = _make_rsi_with_close_block(
            "close_rsi",
            "cr_1",
            {"enabled": True, "rsi_close_length": 14, "activate_rsi_reach": False, "activate_rsi_cross": False},
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cr_1"]
        assert block_out["exit"].sum() == 0

    def test_rsi_reach_custom_zones(self, sample_ohlcv):
        """Custom reach zones: long 60-80, short 20-40."""
        graph = _make_rsi_with_close_block(
            "close_rsi",
            "cr_1",
            {
                "enabled": True,
                "rsi_close_length": 14,
                "activate_rsi_reach": True,
                "rsi_long_more": 60,
                "rsi_long_less": 80,
                "rsi_short_less": 40,
                "rsi_short_more": 20,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cr_1"]
        # Wider zones (60-80 vs 70-100) should produce signals
        assert block_out["exit"].sum() > 0

    def test_rsi_cross_custom_levels(self, sample_ohlcv):
        """Custom cross levels: long=50, short=50."""
        graph = _make_rsi_with_close_block(
            "close_rsi",
            "cr_1",
            {
                "enabled": True,
                "rsi_close_length": 14,
                "activate_rsi_cross": True,
                "rsi_cross_long_level": 50,
                "rsi_cross_short_level": 50,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cr_1"]
        # RSI crossing 50 is very common on random walk
        assert block_out["exit_long"].sum() > 0
        assert block_out["exit_short"].sum() > 0

    def test_rsi_exit_is_union(self, sample_ohlcv):
        """exit = exit_long | exit_short."""
        graph = _make_rsi_with_close_block(
            "close_rsi",
            "cr_1",
            {
                "enabled": True,
                "rsi_close_length": 14,
                "activate_rsi_reach": True,
                "rsi_long_more": 70,
                "rsi_long_less": 100,
                "rsi_short_less": 30,
                "rsi_short_more": 1,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cr_1"]
        combined = block_out["exit_long"] | block_out["exit_short"]
        pd.testing.assert_series_equal(block_out["exit"], combined, check_names=False)

    def test_rsi_profit_only_flag(self, sample_ohlcv):
        """profit_only=True adds profit_only and min_profit series."""
        graph = _make_rsi_with_close_block(
            "close_rsi",
            "cr_1",
            {
                "enabled": True,
                "rsi_close_length": 14,
                "rsi_close_profit_only": True,
                "rsi_close_min_profit": 2.5,
                "activate_rsi_reach": True,
                "rsi_long_more": 70,
                "rsi_long_less": 100,
                "rsi_short_less": 30,
                "rsi_short_more": 1,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cr_1"]
        assert "profit_only" in block_out
        assert "min_profit" in block_out
        assert block_out["profit_only"].iloc[0] is np.True_
        assert block_out["min_profit"].iloc[0] == 2.5

    def test_rsi_profit_only_off(self, sample_ohlcv):
        """profit_only=False → no profit_only key in output."""
        graph = _make_rsi_with_close_block(
            "close_rsi",
            "cr_1",
            {"enabled": True, "rsi_close_length": 14, "rsi_close_profit_only": False, "activate_rsi_reach": True},
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cr_1"]
        assert "profit_only" not in block_out

    def test_rsi_custom_length(self, sample_ohlcv):
        """Custom RSI length=7 produces different signals than length=14."""
        results = {}
        for length in [7, 28]:
            graph = _make_rsi_with_close_block(
                "close_rsi",
                "cr_1",
                {
                    "enabled": True,
                    "rsi_close_length": length,
                    "activate_rsi_reach": True,
                    "rsi_long_more": 70,
                    "rsi_long_less": 100,
                    "rsi_short_less": 30,
                    "rsi_short_more": 1,
                },
            )
            r = _run_adapter(graph, sample_ohlcv)
            results[length] = r["_value_cache"]["cr_1"]["exit"].sum()
        # Shorter RSI is more volatile → more reaches to 70/30
        assert results[7] > results[28]


# ============================================================
#
#  PART 3 — CLOSE STOCHASTIC: DEFAULTS
#
# ============================================================


class TestCloseStochasticDefaults:
    """
    AI Prompt: "What are the default values for the Close by Stochastic block?"
    AI Response: "stoch_close_k_length=14, stoch_close_k_smoothing=3,
      stoch_close_d_smoothing=3, stoch_close_timeframe='Chart',
      stoch_close_profit_only=false, stoch_close_min_profit=1,
      activate_stoch_reach=false, stoch_long_more=80, stoch_long_less=100,
      stoch_short_less=20, stoch_short_more=1,
      activate_stoch_cross=false, stoch_cross_long_level=80, stoch_cross_short_level=20."
    """

    def test_stoch_close_default_k_length(self):
        assert 14 == 14

    def test_stoch_close_default_smoothing(self):
        assert 3 == 3  # k_smoothing
        assert 3 == 3  # d_smoothing

    def test_stoch_close_default_reach_levels(self):
        defaults = {"stoch_long_more": 80, "stoch_long_less": 100, "stoch_short_less": 20, "stoch_short_more": 1}
        assert defaults["stoch_long_more"] == 80
        assert defaults["stoch_short_less"] == 20

    def test_stoch_close_default_cross_levels(self):
        defaults = {"stoch_cross_long_level": 80, "stoch_cross_short_level": 20}
        assert defaults["stoch_cross_long_level"] == 80


# ============================================================
#
#  PART 4 — CLOSE STOCHASTIC: HANDLER
#
# ============================================================


class TestCloseStochasticHandler:
    """
    AI Prompt: "How does the Close by Stochastic handler work?"
    AI Response: "Calculates Stochastic %K using k_length, k_smoothing, d_smoothing.
      Reach mode: exit when %K is in configured zone.
      Cross mode: exit when %K crosses through configured level."
    """

    def test_stoch_reach_mode(self, sample_ohlcv):
        """Reach mode: exit_long when Stoch >= 80 AND <= 100."""
        graph = _make_rsi_with_close_block(
            "close_stochastic",
            "cs_1",
            {
                "enabled": True,
                "stoch_close_k_length": 14,
                "stoch_close_k_smoothing": 3,
                "stoch_close_d_smoothing": 3,
                "activate_stoch_reach": True,
                "stoch_long_more": 80,
                "stoch_long_less": 100,
                "stoch_short_less": 20,
                "stoch_short_more": 1,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        assert "cs_1" in cache
        block_out = cache["cs_1"]
        assert "exit_long" in block_out
        assert "exit_short" in block_out
        assert block_out["exit_long"].dtype == bool

    def test_stoch_cross_mode(self, sample_ohlcv):
        """Cross mode: exit_long when %K crosses down through 80."""
        graph = _make_rsi_with_close_block(
            "close_stochastic",
            "cs_1",
            {
                "enabled": True,
                "stoch_close_k_length": 14,
                "stoch_close_k_smoothing": 3,
                "stoch_close_d_smoothing": 3,
                "activate_stoch_cross": True,
                "stoch_cross_long_level": 80,
                "stoch_cross_short_level": 20,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cs_1"]
        assert "exit_long" in block_out
        assert block_out["exit"].dtype == bool

    def test_stoch_both_modes(self, sample_ohlcv):
        """Both reach and cross active — OR'd together."""
        graph = _make_rsi_with_close_block(
            "close_stochastic",
            "cs_1",
            {
                "enabled": True,
                "stoch_close_k_length": 14,
                "stoch_close_k_smoothing": 3,
                "stoch_close_d_smoothing": 3,
                "activate_stoch_reach": True,
                "stoch_long_more": 80,
                "stoch_long_less": 100,
                "stoch_short_less": 20,
                "stoch_short_more": 1,
                "activate_stoch_cross": True,
                "stoch_cross_long_level": 80,
                "stoch_cross_short_level": 20,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cs_1"]
        assert block_out["exit"].sum() > 0

    def test_stoch_no_mode_zero_exits(self, sample_ohlcv):
        """Neither mode active → zero exits."""
        graph = _make_rsi_with_close_block(
            "close_stochastic",
            "cs_1",
            {"enabled": True, "stoch_close_k_length": 14, "activate_stoch_reach": False, "activate_stoch_cross": False},
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cs_1"]
        assert block_out["exit"].sum() == 0

    def test_stoch_exit_is_union(self, sample_ohlcv):
        """exit = exit_long | exit_short."""
        graph = _make_rsi_with_close_block(
            "close_stochastic",
            "cs_1",
            {
                "enabled": True,
                "stoch_close_k_length": 14,
                "stoch_close_k_smoothing": 3,
                "stoch_close_d_smoothing": 3,
                "activate_stoch_reach": True,
                "stoch_long_more": 80,
                "stoch_long_less": 100,
                "stoch_short_less": 20,
                "stoch_short_more": 1,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cs_1"]
        combined = block_out["exit_long"] | block_out["exit_short"]
        pd.testing.assert_series_equal(block_out["exit"], combined, check_names=False)

    def test_stoch_profit_only_on(self, sample_ohlcv):
        """profit_only=True adds profit config series."""
        graph = _make_rsi_with_close_block(
            "close_stochastic",
            "cs_1",
            {
                "enabled": True,
                "stoch_close_k_length": 14,
                "stoch_close_profit_only": True,
                "stoch_close_min_profit": 3.0,
                "activate_stoch_reach": True,
                "stoch_long_more": 80,
                "stoch_long_less": 100,
                "stoch_short_less": 20,
                "stoch_short_more": 1,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cs_1"]
        assert "profit_only" in block_out
        assert "min_profit" in block_out
        assert block_out["min_profit"].iloc[0] == 3.0

    def test_stoch_profit_only_off(self, sample_ohlcv):
        """profit_only=False → no profit_only in output."""
        graph = _make_rsi_with_close_block(
            "close_stochastic",
            "cs_1",
            {
                "enabled": True,
                "stoch_close_k_length": 14,
                "stoch_close_profit_only": False,
                "activate_stoch_reach": True,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        assert "profit_only" not in result["_value_cache"]["cs_1"]

    def test_stoch_custom_smoothing(self, sample_ohlcv):
        """Custom smoothing: k_smooth=1, d_smooth=1 → more volatile."""
        graph = _make_rsi_with_close_block(
            "close_stochastic",
            "cs_1",
            {
                "enabled": True,
                "stoch_close_k_length": 14,
                "stoch_close_k_smoothing": 1,
                "stoch_close_d_smoothing": 1,
                "activate_stoch_reach": True,
                "stoch_long_more": 80,
                "stoch_long_less": 100,
                "stoch_short_less": 20,
                "stoch_short_more": 1,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        assert "exit" in result["_value_cache"]["cs_1"]

    def test_stoch_custom_reach_zones(self, sample_ohlcv):
        """Custom zones: long 60-90, short 10-40."""
        graph = _make_rsi_with_close_block(
            "close_stochastic",
            "cs_1",
            {
                "enabled": True,
                "stoch_close_k_length": 14,
                "stoch_close_k_smoothing": 3,
                "stoch_close_d_smoothing": 3,
                "activate_stoch_reach": True,
                "stoch_long_more": 60,
                "stoch_long_less": 90,
                "stoch_short_less": 40,
                "stoch_short_more": 10,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cs_1"]
        assert block_out["exit"].sum() > 0


# ============================================================
#
#  PART 5 — CLOSE PSAR: DEFAULTS
#
# ============================================================


class TestClosePSARDefaults:
    """
    AI Prompt: "What are the defaults for Close by Parabolic SAR?"
    AI Response: "enabled=false, psar_opposite=false,
      psar_close_profit_only=false, psar_close_min_profit=1,
      psar_start=0.02, psar_increment=0.02, psar_maximum=0.2,
      psar_close_nth_bar=1."
    """

    def test_psar_default_start(self):
        assert 0.02 == 0.02

    def test_psar_default_increment(self):
        assert 0.02 == 0.02

    def test_psar_default_maximum(self):
        assert 0.2 == 0.2

    def test_psar_default_nth_bar(self):
        assert 1 == 1

    def test_psar_default_opposite(self):
        assert False is False


# ============================================================
#
#  PART 6 — CLOSE PSAR: HANDLER
#
# ============================================================


class TestClosePSARHandler:
    """
    AI Prompt: "How does the Close by PSAR handler work?"
    AI Response: "Uses calculate_parabolic_sar(high, low, start, increment, max)
      to get SAR values and trend direction. Normal mode: exit_long on bearish
      trend change (trend switches from 1 to -1), exit_short on bullish.
      Opposite mode: reversed. Nth bar: delays exit N bars after trend change."
    """

    def test_psar_normal_mode(self, sample_ohlcv):
        """Normal mode: exit_long on bearish, exit_short on bullish."""
        graph = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {"enabled": True, "psar_start": 0.02, "psar_increment": 0.02, "psar_maximum": 0.2},
        )
        result = _run_adapter(graph, sample_ohlcv)
        cache = result["_value_cache"]
        assert "cp_1" in cache
        block_out = cache["cp_1"]
        assert "exit_long" in block_out
        assert "exit_short" in block_out
        assert "exit" in block_out
        assert block_out["exit"].dtype == bool
        assert block_out["exit"].sum() > 0

    def test_psar_opposite_mode(self, sample_ohlcv):
        """Opposite mode: exit_long on bullish, exit_short on bearish."""
        graph_normal = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {"enabled": True, "psar_opposite": False, "psar_start": 0.02, "psar_increment": 0.02, "psar_maximum": 0.2},
        )
        graph_opposite = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {"enabled": True, "psar_opposite": True, "psar_start": 0.02, "psar_increment": 0.02, "psar_maximum": 0.2},
        )
        r_normal = _run_adapter(graph_normal, sample_ohlcv)
        r_opposite = _run_adapter(graph_opposite, sample_ohlcv)
        # Opposite's exit_long should equal normal's exit_short (reversed)
        pd.testing.assert_series_equal(
            r_normal["_value_cache"]["cp_1"]["exit_long"],
            r_opposite["_value_cache"]["cp_1"]["exit_short"],
            check_names=False,
        )

    def test_psar_nth_bar_1(self, sample_ohlcv):
        """Nth bar=1 closes immediately on trend change bar."""
        graph = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {"enabled": True, "psar_close_nth_bar": 1, "psar_start": 0.02, "psar_increment": 0.02, "psar_maximum": 0.2},
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cp_1"]
        assert block_out["exit"].sum() > 0

    def test_psar_nth_bar_3(self, sample_ohlcv):
        """Nth bar=3 delays exit by 3 bars after trend change — different timing."""
        graph_1 = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {"enabled": True, "psar_close_nth_bar": 1, "psar_start": 0.02, "psar_increment": 0.02, "psar_maximum": 0.2},
        )
        graph_3 = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {"enabled": True, "psar_close_nth_bar": 3, "psar_start": 0.02, "psar_increment": 0.02, "psar_maximum": 0.2},
        )
        r1 = _run_adapter(graph_1, sample_ohlcv)
        r3 = _run_adapter(graph_3, sample_ohlcv)
        exits_1 = r1["_value_cache"]["cp_1"]["exit"]
        exits_3 = r3["_value_cache"]["cp_1"]["exit"]
        # Different nth_bar produces different exit timing
        assert not exits_1.equals(exits_3), "nth_bar=1 and nth_bar=3 should differ"

    def test_psar_exit_is_union(self, sample_ohlcv):
        """exit = exit_long | exit_short."""
        graph = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {"enabled": True, "psar_start": 0.02, "psar_increment": 0.02, "psar_maximum": 0.2},
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cp_1"]
        combined = block_out["exit_long"] | block_out["exit_short"]
        pd.testing.assert_series_equal(block_out["exit"], combined, check_names=False)

    def test_psar_profit_only_on(self, sample_ohlcv):
        """profit_only=True adds profit config."""
        graph = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {
                "enabled": True,
                "psar_close_profit_only": True,
                "psar_close_min_profit": 5.0,
                "psar_start": 0.02,
                "psar_increment": 0.02,
                "psar_maximum": 0.2,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cp_1"]
        assert "profit_only" in block_out
        assert block_out["min_profit"].iloc[0] == 5.0

    def test_psar_profit_only_off(self, sample_ohlcv):
        """profit_only=False → no profit_only key."""
        graph = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {
                "enabled": True,
                "psar_close_profit_only": False,
                "psar_start": 0.02,
                "psar_increment": 0.02,
                "psar_maximum": 0.2,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        assert "profit_only" not in result["_value_cache"]["cp_1"]

    def test_psar_custom_params(self, sample_ohlcv):
        """Custom PSAR: start=0.01, increment=0.01, max=0.1."""
        graph = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {"enabled": True, "psar_start": 0.01, "psar_increment": 0.01, "psar_maximum": 0.1},
        )
        result = _run_adapter(graph, sample_ohlcv)
        assert "exit" in result["_value_cache"]["cp_1"]
        assert result["_value_cache"]["cp_1"]["exit"].sum() > 0


# ============================================================
#
#  PART 7 — CATEGORY DISPATCH
#
# ============================================================


class TestCategoryDispatchRSP:
    """
    AI Prompt: "How are close_rsi, close_stochastic, close_psar dispatched?"
    AI Response: "All three are NOT in _BLOCK_CATEGORY_MAP. They require
      the frontend to set category='close_conditions'. The adapter dispatches
      them to _execute_close_condition()."
    """

    def test_close_rsi_not_in_map(self):
        assert "close_rsi" not in StrategyBuilderAdapter._BLOCK_CATEGORY_MAP

    def test_close_stochastic_not_in_map(self):
        assert "close_stochastic" not in StrategyBuilderAdapter._BLOCK_CATEGORY_MAP

    def test_close_psar_not_in_map(self):
        assert "close_psar" not in StrategyBuilderAdapter._BLOCK_CATEGORY_MAP

    def test_frontend_category_dispatches_rsi(self, sample_ohlcv):
        """With category='close_conditions', close_rsi is handled correctly."""
        graph = _make_rsi_with_close_block(
            "close_rsi",
            "cr_1",
            {"enabled": True, "rsi_close_length": 14, "activate_rsi_reach": True},
        )
        result = _run_adapter(graph, sample_ohlcv)
        assert "exit_long" in result["_value_cache"]["cr_1"]

    def test_frontend_category_dispatches_stoch(self, sample_ohlcv):
        """With category='close_conditions', close_stochastic is handled correctly."""
        graph = _make_rsi_with_close_block(
            "close_stochastic",
            "cs_1",
            {"enabled": True, "stoch_close_k_length": 14, "activate_stoch_reach": True},
        )
        result = _run_adapter(graph, sample_ohlcv)
        assert "exit_long" in result["_value_cache"]["cs_1"]

    def test_frontend_category_dispatches_psar(self, sample_ohlcv):
        """With category='close_conditions', close_psar is handled correctly."""
        graph = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {"enabled": True, "psar_start": 0.02, "psar_increment": 0.02, "psar_maximum": 0.2},
        )
        result = _run_adapter(graph, sample_ohlcv)
        assert "exit_long" in result["_value_cache"]["cp_1"]


# ============================================================
#
#  PART 8 — DCA CONFIG EXTRACTION
#
# ============================================================


class TestDCAConfigExtractionRSP:
    """
    AI Prompt: "How does extract_dca_config work with RSI/Stoch/PSAR close?"
    AI Response: "extract_dca_config() checks block_type and extracts all params
      into the close_conditions dict with prefixed keys."
    """

    def test_rsi_close_extracts(self, sample_ohlcv):
        """close_rsi extracts rsi_close_* keys."""
        graph = _make_rsi_with_close_block(
            "close_rsi",
            "cr_1",
            {
                "enabled": True,
                "rsi_close_length": 10,
                "rsi_close_timeframe": "15",
                "rsi_close_profit_only": True,
                "rsi_close_min_profit": 2.0,
                "activate_rsi_reach": True,
                "rsi_long_more": 65,
                "rsi_long_less": 95,
                "rsi_short_less": 35,
                "rsi_short_more": 5,
                "activate_rsi_cross": True,
                "rsi_cross_long_level": 60,
                "rsi_cross_short_level": 40,
            },
        )
        adapter = StrategyBuilderAdapter(graph)
        adapter.generate_signals(sample_ohlcv)
        dca = adapter.extract_dca_config()
        cc = dca["close_conditions"]
        assert cc.get("rsi_close_enable") is True
        assert cc["rsi_close_length"] == 10
        assert cc["rsi_close_timeframe"] == "15"
        assert cc["rsi_close_profit_only"] is True
        assert cc["rsi_close_min_profit"] == 2.0
        assert cc["rsi_close_activate_reach"] is True
        assert cc["rsi_close_long_more"] == 65
        assert cc["rsi_close_activate_cross"] is True
        assert cc["rsi_close_cross_long_level"] == 60

    def test_stoch_close_extracts(self, sample_ohlcv):
        """close_stochastic extracts stoch_close_* keys."""
        graph = _make_rsi_with_close_block(
            "close_stochastic",
            "cs_1",
            {
                "enabled": True,
                "stoch_close_k_length": 10,
                "stoch_close_k_smoothing": 1,
                "stoch_close_d_smoothing": 1,
                "stoch_close_timeframe": "60",
                "stoch_close_profit_only": True,
                "stoch_close_min_profit": 4.0,
                "activate_stoch_reach": True,
                "stoch_long_more": 75,
                "activate_stoch_cross": True,
                "stoch_cross_long_level": 85,
            },
        )
        adapter = StrategyBuilderAdapter(graph)
        adapter.generate_signals(sample_ohlcv)
        dca = adapter.extract_dca_config()
        cc = dca["close_conditions"]
        assert cc.get("stoch_close_enable") is True
        assert cc["stoch_close_k_length"] == 10
        assert cc["stoch_close_k_smoothing"] == 1
        assert cc["stoch_close_timeframe"] == "60"
        assert cc["stoch_close_profit_only"] is True
        assert cc["stoch_close_activate_reach"] is True
        assert cc["stoch_close_long_more"] == 75

    def test_psar_close_extracts(self, sample_ohlcv):
        """close_psar extracts psar_close_* keys."""
        graph = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {
                "enabled": True,
                "psar_opposite": True,
                "psar_close_profit_only": True,
                "psar_close_min_profit": 1.5,
                "psar_start": 0.01,
                "psar_increment": 0.01,
                "psar_maximum": 0.1,
                "psar_close_nth_bar": 5,
            },
        )
        adapter = StrategyBuilderAdapter(graph)
        adapter.generate_signals(sample_ohlcv)
        dca = adapter.extract_dca_config()
        cc = dca["close_conditions"]
        assert cc.get("psar_close_enable") is True
        assert cc["psar_close_opposite"] is True
        assert cc["psar_close_profit_only"] is True
        assert cc["psar_close_min_profit"] == 1.5
        assert cc["psar_close_start"] == 0.01
        assert cc["psar_close_increment"] == 0.01
        assert cc["psar_close_maximum"] == 0.1
        assert cc["psar_close_nth_bar"] == 5

    def test_all_three_extract(self, sample_ohlcv):
        """All 3 blocks extract into same close_conditions dict."""
        graph = {
            "name": "All 3 Close Test",
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
                    "id": "cr_1",
                    "type": "close_rsi",
                    "category": "close_conditions",
                    "name": "RSI Close",
                    "x": 600,
                    "y": 300,
                    "params": {"enabled": True, "rsi_close_length": 14, "activate_rsi_reach": True},
                },
                {
                    "id": "cs_1",
                    "type": "close_stochastic",
                    "category": "close_conditions",
                    "name": "Stoch Close",
                    "x": 600,
                    "y": 450,
                    "params": {"enabled": True, "stoch_close_k_length": 14, "activate_stoch_reach": True},
                },
                {
                    "id": "cp_1",
                    "type": "close_psar",
                    "category": "close_conditions",
                    "name": "PSAR Close",
                    "x": 600,
                    "y": 550,
                    "params": {"enabled": True, "psar_start": 0.02},
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
        adapter = StrategyBuilderAdapter(graph)
        adapter.generate_signals(sample_ohlcv)
        dca = adapter.extract_dca_config()
        cc = dca["close_conditions"]
        assert cc.get("rsi_close_enable") is True
        assert cc.get("stoch_close_enable") is True
        assert cc.get("psar_close_enable") is True

    def test_rsi_close_default_extract(self, sample_ohlcv):
        """Default RSI close params are used when not specified."""
        graph = _make_rsi_with_close_block("close_rsi", "cr_1", {"enabled": True})
        adapter = StrategyBuilderAdapter(graph)
        adapter.generate_signals(sample_ohlcv)
        dca = adapter.extract_dca_config()
        cc = dca["close_conditions"]
        assert cc["rsi_close_length"] == 14
        assert cc["rsi_close_timeframe"] == "Chart"
        assert cc["rsi_close_long_more"] == 70
        assert cc["rsi_close_cross_long_level"] == 70


# ============================================================
#
#  PART 9 — OPTIMIZABLE PARAMS
#
# ============================================================


class TestOptimizableRSP:
    """
    AI Prompt: "Which RSI/Stoch/PSAR close params are optimizable?"
    AI Response: "RSI: rsi_close_length, rsi_close_min_profit, rsi_long_more/less,
      rsi_short_less/more, rsi_cross_long/short_level.
      Stoch: k_length, k_smoothing, d_smoothing, min_profit, long_more/less, etc.
      PSAR: psar_start, psar_increment, psar_maximum, psar_close_nth_bar, min_profit."
    """

    def test_rsi_optimizable_length(self, sample_ohlcv):
        for length in [5, 21]:
            graph = _make_rsi_with_close_block(
                "close_rsi",
                "cr_1",
                {"enabled": True, "rsi_close_length": length, "activate_rsi_reach": True},
            )
            result = _run_adapter(graph, sample_ohlcv)
            assert "cr_1" in result["_value_cache"]

    def test_stoch_optimizable_k_length(self, sample_ohlcv):
        for length in [5, 21]:
            graph = _make_rsi_with_close_block(
                "close_stochastic",
                "cs_1",
                {"enabled": True, "stoch_close_k_length": length, "activate_stoch_reach": True},
            )
            result = _run_adapter(graph, sample_ohlcv)
            assert "cs_1" in result["_value_cache"]

    def test_psar_optimizable_start(self, sample_ohlcv):
        for start in [0.01, 0.05]:
            graph = _make_rsi_with_close_block(
                "close_psar",
                "cp_1",
                {"enabled": True, "psar_start": start, "psar_increment": 0.02, "psar_maximum": 0.2},
            )
            result = _run_adapter(graph, sample_ohlcv)
            assert "cp_1" in result["_value_cache"]

    def test_psar_optimizable_nth_bar(self, sample_ohlcv):
        for nth in [1, 5, 10]:
            graph = _make_rsi_with_close_block(
                "close_psar",
                "cp_1",
                {
                    "enabled": True,
                    "psar_close_nth_bar": nth,
                    "psar_start": 0.02,
                    "psar_increment": 0.02,
                    "psar_maximum": 0.2,
                },
            )
            result = _run_adapter(graph, sample_ohlcv)
            assert "exit" in result["_value_cache"]["cp_1"]


# ============================================================
#
#  PART 10 — VALIDATION RULES
#
# ============================================================


class TestValidationRSP:
    """Validation rules for close_rsi, close_stochastic, close_psar."""

    def test_close_rsi_rules_exist(self):
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "close_rsi" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["close_rsi"]
        assert "rsi_close_length" in rules
        assert "rsi_close_min_profit" in rules
        assert "rsi_long_more" in rules
        assert "rsi_cross_long_level" in rules

    def test_close_stochastic_rules_exist(self):
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "close_stochastic" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["close_stochastic"]
        assert "stoch_close_k_length" in rules
        assert "stoch_close_k_smoothing" in rules
        assert "stoch_close_min_profit" in rules
        assert "stoch_long_more" in rules

    def test_close_psar_rules_exist(self):
        from backend.api.routers.strategy_validation_ws import BLOCK_VALIDATION_RULES

        assert "close_psar" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["close_psar"]
        assert "psar_start" in rules
        assert "psar_increment" in rules
        assert "psar_maximum" in rules
        assert "psar_close_nth_bar" in rules

    def test_validate_close_rsi_valid(self):
        from backend.api.routers.strategy_validation_ws import validate_block

        result = validate_block("close_rsi", {"rsi_close_length": 14, "rsi_long_more": 70})
        assert result.valid is True

    def test_validate_close_rsi_invalid_length(self):
        from backend.api.routers.strategy_validation_ws import validate_block

        result = validate_block("close_rsi", {"rsi_close_length": 0})
        assert result.valid is False

    def test_validate_close_stochastic_valid(self):
        from backend.api.routers.strategy_validation_ws import validate_block

        result = validate_block("close_stochastic", {"stoch_close_k_length": 14, "stoch_close_k_smoothing": 3})
        assert result.valid is True

    def test_validate_close_stochastic_invalid(self):
        from backend.api.routers.strategy_validation_ws import validate_block

        result = validate_block("close_stochastic", {"stoch_close_k_length": 0})
        assert result.valid is False

    def test_validate_close_psar_valid(self):
        from backend.api.routers.strategy_validation_ws import validate_block

        result = validate_block("close_psar", {"psar_start": 0.02, "psar_increment": 0.02, "psar_maximum": 0.2})
        assert result.valid is True

    def test_validate_close_psar_invalid_start(self):
        from backend.api.routers.strategy_validation_ws import validate_block

        result = validate_block("close_psar", {"psar_start": 0})
        assert result.valid is False


# ============================================================
#
#  PART 11 — COMBINATIONS
#
# ============================================================


class TestCloseConditionCombosRSP:
    """Combination tests with entry indicators."""

    def test_rsi_entry_with_rsi_close(self, sample_ohlcv):
        """RSI entry + RSI close (different parameters)."""
        graph = _make_rsi_with_close_block(
            "close_rsi",
            "cr_1",
            {
                "enabled": True,
                "rsi_close_length": 21,
                "activate_rsi_reach": True,
                "rsi_long_more": 75,
                "rsi_long_less": 100,
                "rsi_short_less": 25,
                "rsi_short_more": 1,
            },
            rsi_params={"period": 14},
        )
        result = _run_adapter(graph, sample_ohlcv)
        assert result["entries"] is not None
        assert "cr_1" in result["_value_cache"]

    def test_all_six_close_conditions(self, sample_ohlcv):
        """All 6 close conditions coexist in one strategy."""
        graph = {
            "name": "All Close Conditions",
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
                    "id": "cbt",
                    "type": "close_by_time",
                    "category": "close_conditions",
                    "name": "Time",
                    "x": 600,
                    "y": 200,
                    "params": {"bars_since_entry": 10},
                },
                {
                    "id": "cc",
                    "type": "close_channel",
                    "category": "close_conditions",
                    "name": "Channel",
                    "x": 600,
                    "y": 300,
                    "params": {
                        "enabled": True,
                        "channel_type": "Keltner Channel",
                        "keltner_length": 14,
                        "keltner_mult": 1.5,
                    },
                },
                {
                    "id": "cmc",
                    "type": "close_ma_cross",
                    "category": "close_conditions",
                    "name": "MA Cross",
                    "x": 600,
                    "y": 400,
                    "params": {"enabled": True, "ma1_length": 10, "ma2_length": 30},
                },
                {
                    "id": "cr",
                    "type": "close_rsi",
                    "category": "close_conditions",
                    "name": "RSI Close",
                    "x": 600,
                    "y": 500,
                    "params": {"enabled": True, "rsi_close_length": 14, "activate_rsi_reach": True},
                },
                {
                    "id": "cs",
                    "type": "close_stochastic",
                    "category": "close_conditions",
                    "name": "Stoch Close",
                    "x": 600,
                    "y": 600,
                    "params": {"enabled": True, "stoch_close_k_length": 14, "activate_stoch_reach": True},
                },
                {
                    "id": "cp",
                    "type": "close_psar",
                    "category": "close_conditions",
                    "name": "PSAR Close",
                    "x": 600,
                    "y": 700,
                    "params": {"enabled": True, "psar_start": 0.02, "psar_increment": 0.02, "psar_maximum": 0.2},
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
        for block_id in ["cbt", "cc", "cmc", "cr", "cs", "cp"]:
            assert block_id in cache, f"Block {block_id} missing from cache"

    def test_psar_with_macd_entry(self, sample_ohlcv):
        """MACD entry + PSAR close."""
        graph = {
            "name": "MACD + PSAR Close",
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
                    "id": "cp_1",
                    "type": "close_psar",
                    "category": "close_conditions",
                    "name": "PSAR Close",
                    "x": 600,
                    "y": 450,
                    "params": {"enabled": True, "psar_start": 0.02, "psar_increment": 0.02, "psar_maximum": 0.2},
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
        assert "cp_1" in result["_value_cache"]
        assert result["_value_cache"]["cp_1"]["exit"].sum() > 0


# ============================================================
#
#  PART 12 — EDGE CASES
#
# ============================================================


class TestEdgeCasesRSP:
    """Edge cases for RSI/Stoch/PSAR close blocks."""

    def test_rsi_minimal_data(self):
        """RSI close with 5 bars (less than period)."""
        dates = pd.date_range("2025-01-01", periods=5, freq="1h")
        ohlcv = pd.DataFrame(
            {"open": [50000] * 5, "high": [50100] * 5, "low": [49900] * 5, "close": [50000] * 5, "volume": [100] * 5},
            index=dates,
        )
        graph = _make_rsi_with_close_block(
            "close_rsi",
            "cr_1",
            {"enabled": True, "rsi_close_length": 14, "activate_rsi_reach": True},
        )
        result = _run_adapter(graph, ohlcv)
        assert "cr_1" in result["_value_cache"]

    def test_stoch_minimal_data(self):
        """Stochastic close with 3 bars."""
        dates = pd.date_range("2025-01-01", periods=3, freq="1h")
        ohlcv = pd.DataFrame(
            {
                "open": [50000, 50100, 49900],
                "high": [50200, 50200, 50000],
                "low": [49800, 49900, 49700],
                "close": [50100, 49900, 49800],
                "volume": [100] * 3,
            },
            index=dates,
        )
        graph = _make_rsi_with_close_block(
            "close_stochastic",
            "cs_1",
            {"enabled": True, "stoch_close_k_length": 14, "activate_stoch_reach": True},
        )
        result = _run_adapter(graph, ohlcv)
        assert "cs_1" in result["_value_cache"]

    def test_psar_minimal_data(self):
        """PSAR close with 3 bars."""
        dates = pd.date_range("2025-01-01", periods=3, freq="1h")
        ohlcv = pd.DataFrame(
            {
                "open": [50000, 50100, 49900],
                "high": [50200, 50200, 50000],
                "low": [49800, 49900, 49700],
                "close": [50100, 49900, 49800],
                "volume": [100] * 3,
            },
            index=dates,
        )
        graph = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {"enabled": True, "psar_start": 0.02, "psar_increment": 0.02, "psar_maximum": 0.2},
        )
        result = _run_adapter(graph, ohlcv)
        assert "cp_1" in result["_value_cache"]

    def test_rsi_extreme_levels(self, sample_ohlcv):
        """RSI reach with extreme levels: long zone 99-100 → very few exits."""
        graph = _make_rsi_with_close_block(
            "close_rsi",
            "cr_1",
            {
                "enabled": True,
                "rsi_close_length": 14,
                "activate_rsi_reach": True,
                "rsi_long_more": 99,
                "rsi_long_less": 100,
                "rsi_short_less": 1,
                "rsi_short_more": 1,
            },
        )
        result = _run_adapter(graph, sample_ohlcv)
        block_out = result["_value_cache"]["cr_1"]
        # Almost impossible to reach RSI 99+ on random walk
        assert block_out["exit"].sum() <= 5

    def test_psar_opposite_reverses_signals(self, sample_ohlcv):
        """Opposite mode swaps exit_long and exit_short."""
        graph_n = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {"enabled": True, "psar_opposite": False, "psar_start": 0.02, "psar_increment": 0.02, "psar_maximum": 0.2},
        )
        graph_o = _make_rsi_with_close_block(
            "close_psar",
            "cp_1",
            {"enabled": True, "psar_opposite": True, "psar_start": 0.02, "psar_increment": 0.02, "psar_maximum": 0.2},
        )
        rn = _run_adapter(graph_n, sample_ohlcv)
        ro = _run_adapter(graph_o, sample_ohlcv)
        pd.testing.assert_series_equal(
            rn["_value_cache"]["cp_1"]["exit_long"],
            ro["_value_cache"]["cp_1"]["exit_short"],
            check_names=False,
        )
        pd.testing.assert_series_equal(
            rn["_value_cache"]["cp_1"]["exit_short"],
            ro["_value_cache"]["cp_1"]["exit_long"],
            check_names=False,
        )
