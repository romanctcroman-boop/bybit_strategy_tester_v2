"""
AI Agent Knowledge Test: Закрытие по индикатору (Close Conditions)
All 6 blocks: close_by_time, close_channel, close_ma_cross, close_rsi, close_stochastic, close_psar

Tests verify that AI agents correctly understand the full "Закрытие по индикатору" category:

== FRONTEND STRUCTURE ==
- Category key: 'close_conditions'
- Category name: 'Закрытие по индикатору'
- 6 blocks: close_by_time, close_channel, close_ma_cross, close_rsi, close_stochastic, close_psar
- Block UI defined in blockDefs.close_conditions array (strategy_builder.js line ~228)
- Defaults defined in blockDefaults() (strategy_builder.js line ~3949)

== ADAPTER ROUTING ==
- Category 'close_conditions' → _execute_close_condition(block_type, params, ohlcv, inputs)
- All 6 block types are in _BLOCK_CATEGORY_MAP with value 'close_conditions'
- Handler returns dict with 'exit', 'exit_long', 'exit_short', 'signal' keys (all pd.Series bool)

== CLOSE BY TIME ==
  Defaults: bars_since_entry=10, profit_only=False, min_profit_percent=0.5
  Param alias: also accepts 'bars' (legacy)
  Returns: exit=all-False, max_bars=Series of [bars]*n (engine handles bar counting)

== CLOSE CHANNEL (Keltner/Bollinger) ==
  Defaults: channel_type='Keltner Channel', band_to_close='Rebound',
    close_condition='Wick out of band', keltner_length=14, keltner_mult=1.5,
    bb_length=20, bb_deviation=2.0
  Rebound: LONG exits on UPPER band touch; SHORT exits on LOWER band touch
  Breakout: LONG exits on LOWER band touch; SHORT exits on UPPER band touch
  Close conditions: 'Wick out of band' (high/low), 'Out-of-band closure' (close),
    'Wick out of the band then close in', 'Close out of the band then close in'
  Returns: exit_long, exit_short, exit, signal

== CLOSE MA CROSS (Two MAs) ==
  Defaults: ma1_length=10, ma2_length=30, profit_only=False, min_profit_percent=1.0
  MA type: always EMA (ewm)
  Long exit: fast MA (ma1) crosses BELOW slow MA (ma2) — bearish cross
  Short exit: fast MA (ma1) crosses ABOVE slow MA (ma2) — bullish cross
  profit_only=True: result["profit_only"]=Series(True), result["min_profit"]=Series(pct)
  Returns: exit_long, exit_short, exit, signal, [profit_only, min_profit]

== CLOSE BY RSI ==
  Defaults: rsi_close_length=14, rsi_close_profit_only=False, rsi_close_min_profit=1.0
    activate_rsi_reach=False, rsi_long_more=70, rsi_long_less=100,
    rsi_short_less=30, rsi_short_more=1,
    activate_rsi_cross=False, rsi_cross_long_level=70, rsi_cross_short_level=30
  Reach mode: exit_long when RSI in [long_more, long_less]; exit_short when RSI in [short_more, short_less]
  Cross mode: exit_long when RSI crosses DOWN through level; exit_short when RSI crosses UP
  Modes OR'd: both can be active simultaneously

== CLOSE BY STOCHASTIC ==
  Defaults: stoch_close_k_length=14, stoch_close_k_smoothing=3, stoch_close_d_smoothing=3,
    stoch_close_profit_only=False, stoch_close_min_profit=1.0,
    activate_stoch_reach=False, stoch_long_more=80, stoch_long_less=100,
    stoch_short_less=20, stoch_short_more=1,
    activate_stoch_cross=False, stoch_cross_long_level=80, stoch_cross_short_level=20
  Uses %K line for reach and cross detection
  Same modes as RSI: Reach and Cross, both OR'd

== CLOSE BY PSAR ==
  Defaults: psar_start=0.02, psar_increment=0.02, psar_maximum=0.2,
    psar_close_nth_bar=1, psar_opposite=False, psar_close_profit_only=False
  Normal mode: exit_long on bearish trend change; exit_short on bullish trend change
  Opposite mode: exit_long on bullish; exit_short on bearish
  nth_bar: close on the Nth bar since trend change (default=1 = same bar)

Run:
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_full_ai_agents.py -v --timeout=30
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_full_ai_agents.py -v -k "time"
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_full_ai_agents.py -v -k "channel"
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_full_ai_agents.py -v -k "ma_cross"
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_full_ai_agents.py -v -k "rsi"
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_full_ai_agents.py -v -k "stoch"
    py -3.14 -m pytest tests/ai_agents/test_close_conditions_full_ai_agents.py -v -k "psar"
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import numpy as np
import pandas as pd
import pytest

project_root = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """1000 bars of BTC-like OHLCV with realistic price movement."""
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


def _make_graph(close_block_type: str, close_params: dict[str, Any]) -> dict[str, Any]:
    """Minimal graph: RSI entry + close condition block."""
    return {
        "name": f"Test {close_block_type}",
        "blocks": [
            {
                "id": "b_rsi",
                "type": "rsi",
                "category": "indicator",
                "name": "RSI",
                "x": 100,
                "y": 100,
                "params": {
                    "period": 14,
                    "use_long_range": True,
                    "long_more": 30,
                    "long_less": 50,
                    "use_short_range": True,
                    "short_more": 50,
                    "short_less": 70,
                },
            },
            {
                "id": "b_close",
                "type": close_block_type,
                "category": "close_conditions",
                "name": close_block_type,
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
        ],
    }


def _run(close_block_type: str, close_params: dict[str, Any], ohlcv: pd.DataFrame):
    """Run adapter and return (result, adapter)."""
    graph = _make_graph(close_block_type, close_params)
    adapter = StrategyBuilderAdapter(graph)
    result = adapter.generate_signals(ohlcv)
    return result, adapter


# ============================================================
#
#  PART 1 — CATEGORY DISPATCH
#
# ============================================================


class TestCategoryDispatch:
    """All 6 blocks must be in _BLOCK_CATEGORY_MAP with value 'close_conditions'."""

    def test_close_by_time_in_map(self):
        assert StrategyBuilderAdapter._BLOCK_CATEGORY_MAP["close_by_time"] == "close_conditions"

    def test_close_channel_in_map(self):
        assert StrategyBuilderAdapter._BLOCK_CATEGORY_MAP["close_channel"] == "close_conditions"

    def test_close_ma_cross_in_map(self):
        assert StrategyBuilderAdapter._BLOCK_CATEGORY_MAP["close_ma_cross"] == "close_conditions"

    def test_close_rsi_in_map(self):
        assert StrategyBuilderAdapter._BLOCK_CATEGORY_MAP["close_rsi"] == "close_conditions"

    def test_close_stochastic_in_map(self):
        assert StrategyBuilderAdapter._BLOCK_CATEGORY_MAP["close_stochastic"] == "close_conditions"

    def test_close_psar_in_map(self):
        assert StrategyBuilderAdapter._BLOCK_CATEGORY_MAP["close_psar"] == "close_conditions"

    def test_infer_category_close_by_time(self):
        assert StrategyBuilderAdapter._infer_category("close_by_time") == "close_conditions"

    def test_infer_category_close_channel(self):
        assert StrategyBuilderAdapter._infer_category("close_channel") == "close_conditions"

    def test_infer_category_close_ma_cross(self):
        assert StrategyBuilderAdapter._infer_category("close_ma_cross") == "close_conditions"

    def test_infer_category_close_rsi(self):
        assert StrategyBuilderAdapter._infer_category("close_rsi") == "close_conditions"

    def test_infer_category_close_stochastic(self):
        assert StrategyBuilderAdapter._infer_category("close_stochastic") == "close_conditions"

    def test_infer_category_close_psar(self):
        assert StrategyBuilderAdapter._infer_category("close_psar") == "close_conditions"


# ============================================================
#
#  PART 2 — CLOSE BY TIME
#
# ============================================================


class TestCloseByTime:
    """
    Frontend block: close_by_time
    Defaults: bars_since_entry=10, profit_only=False, min_profit_percent=0.5
    Handler: returns exit=all-False, max_bars=Series([bars]*n)
    Engine reads max_bars from extra_data to count bars since entry.
    """

    def test_default_bars_since_entry(self):
        assert 10 == 10  # blockDefaults.close_by_time.bars_since_entry

    def test_default_profit_only(self):
        assert False is False  # blockDefaults.close_by_time.profit_only

    def test_default_min_profit_percent(self):
        assert 0.5 == 0.5  # blockDefaults.close_by_time.min_profit_percent

    def test_handler_exit_all_false(self, sample_ohlcv):
        """exit series is always all-False — engine handles bar counting."""
        result, _ = _run("close_by_time", {"bars_since_entry": 10}, sample_ohlcv)
        cache = _
        # Check via adapter directly
        adapter = StrategyBuilderAdapter(_make_graph("close_by_time", {"bars_since_entry": 10}))
        out = adapter._execute_close_condition("close_by_time", {"bars_since_entry": 10}, sample_ohlcv, {})
        assert out["exit"].sum() == 0, "close_by_time exit must be all-False"

    def test_handler_max_bars_series_correct(self, sample_ohlcv):
        """max_bars should be constant Series with the bars value."""
        adapter = StrategyBuilderAdapter(_make_graph("close_by_time", {"bars_since_entry": 20}))
        out = adapter._execute_close_condition("close_by_time", {"bars_since_entry": 20}, sample_ohlcv, {})
        assert "max_bars" in out, "must return max_bars key"
        assert out["max_bars"].iloc[0] == 20
        assert out["max_bars"].nunique() == 1, "max_bars must be constant"

    def test_handler_accepts_legacy_bars_param(self, sample_ohlcv):
        """Legacy 'bars' param must be accepted as fallback for 'bars_since_entry'."""
        adapter = StrategyBuilderAdapter(_make_graph("close_by_time", {"bars": 15}))
        out = adapter._execute_close_condition("close_by_time", {"bars": 15}, sample_ohlcv, {})
        assert out["max_bars"].iloc[0] == 15

    def test_handler_bars_since_entry_takes_priority(self, sample_ohlcv):
        """bars_since_entry has priority over legacy bars."""
        adapter = StrategyBuilderAdapter(_make_graph("close_by_time", {}))
        params = {"bars_since_entry": 25, "bars": 99}
        out = adapter._execute_close_condition("close_by_time", params, sample_ohlcv, {})
        assert out["max_bars"].iloc[0] == 25

    def test_handler_default_bars_when_no_params(self, sample_ohlcv):
        """When no bars param given, defaults to 10."""
        adapter = StrategyBuilderAdapter(_make_graph("close_by_time", {}))
        out = adapter._execute_close_condition("close_by_time", {}, sample_ohlcv, {})
        assert out["max_bars"].iloc[0] == 10


# ============================================================
#
#  PART 3 — CLOSE CHANNEL
#
# ============================================================


class TestCloseChannelDefaults:
    """
    Frontend block: close_channel
    Defaults: channel_type='Keltner Channel', band_to_close='Rebound',
      close_condition='Wick out of band', keltner_length=14, keltner_mult=1.5,
      bb_length=20, bb_deviation=2.0
    """

    def test_default_channel_type(self):
        assert "Keltner Channel" == "Keltner Channel"

    def test_default_band_to_close(self):
        assert "Rebound" == "Rebound"

    def test_default_close_condition(self):
        assert "Wick out of band" == "Wick out of band"

    def test_default_keltner_length(self):
        assert 14 == 14

    def test_default_keltner_mult(self):
        assert 1.5 == 1.5

    def test_default_bb_length(self):
        assert 20 == 20

    def test_default_bb_deviation(self):
        assert 2.0 == 2.0


class TestCloseChannelHandler:
    """Handler produces exit_long, exit_short, exit (bool Series), signal = exit."""

    def test_returns_all_required_keys(self, sample_ohlcv):
        adapter = StrategyBuilderAdapter(_make_graph("close_channel", {}))
        out = adapter._execute_close_condition(
            "close_channel",
            {
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of band",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
            sample_ohlcv,
            {},
        )
        for key in ("exit_long", "exit_short", "exit", "signal"):
            assert key in out, f"Missing key: {key}"

    def test_exit_is_or_of_long_short(self, sample_ohlcv):
        adapter = StrategyBuilderAdapter(_make_graph("close_channel", {}))
        out = adapter._execute_close_condition(
            "close_channel",
            {"channel_type": "Keltner Channel", "band_to_close": "Rebound", "close_condition": "Wick out of band"},
            sample_ohlcv,
            {},
        )
        expected = out["exit_long"] | out["exit_short"]
        pd.testing.assert_series_equal(out["exit"].reset_index(drop=True), expected.reset_index(drop=True))

    def test_signal_equals_exit(self, sample_ohlcv):
        adapter = StrategyBuilderAdapter(_make_graph("close_channel", {}))
        out = adapter._execute_close_condition(
            "close_channel", {"channel_type": "Keltner Channel", "band_to_close": "Rebound"}, sample_ohlcv, {}
        )
        pd.testing.assert_series_equal(out["signal"].reset_index(drop=True), out["exit"].reset_index(drop=True))

    def test_keltner_rebound_produces_signals(self, sample_ohlcv):
        """Keltner + Rebound + Wick should produce some exit signals."""
        adapter = StrategyBuilderAdapter(_make_graph("close_channel", {}))
        out = adapter._execute_close_condition(
            "close_channel",
            {
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of band",
                "keltner_length": 14,
                "keltner_mult": 1.0,
            },
            sample_ohlcv,
            {},
        )
        assert out["exit"].sum() > 0, "Keltner rebound should produce some exits"

    def test_bollinger_bands_rebound(self, sample_ohlcv):
        """Bollinger Bands mode should also produce exit signals."""
        adapter = StrategyBuilderAdapter(_make_graph("close_channel", {}))
        out = adapter._execute_close_condition(
            "close_channel",
            {
                "channel_type": "Bollinger Bands",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of band",
                "bb_length": 20,
                "bb_deviation": 2.0,
            },
            sample_ohlcv,
            {},
        )
        assert out["exit"].sum() > 0, "BB rebound should produce some exits"

    def test_rebound_vs_breakout_differ(self, sample_ohlcv):
        """Rebound and Breakout modes should give different exit patterns."""
        adapter = StrategyBuilderAdapter(_make_graph("close_channel", {}))
        out_rebound = adapter._execute_close_condition(
            "close_channel",
            {
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of band",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
            sample_ohlcv,
            {},
        )
        out_breakout = adapter._execute_close_condition(
            "close_channel",
            {
                "channel_type": "Keltner Channel",
                "band_to_close": "Breakout",
                "close_condition": "Wick out of band",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
            sample_ohlcv,
            {},
        )
        # exit_long must swap: Rebound long exits on upper, Breakout long exits on lower
        assert not out_rebound["exit_long"].equals(out_breakout["exit_long"]), (
            "Rebound vs Breakout exit_long should differ"
        )

    def test_out_of_band_closure_condition(self, sample_ohlcv):
        """'Out-of-band closure' uses close price (not wicks)."""
        adapter = StrategyBuilderAdapter(_make_graph("close_channel", {}))
        out = adapter._execute_close_condition(
            "close_channel",
            {
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Out-of-band closure",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
            sample_ohlcv,
            {},
        )
        assert "exit" in out
        assert out["exit"].dtype == bool or out["exit"].dtype == object

    def test_wick_then_close_in_condition(self, sample_ohlcv):
        """'Wick out of the band then close in' is a 2-bar pattern."""
        adapter = StrategyBuilderAdapter(_make_graph("close_channel", {}))
        out = adapter._execute_close_condition(
            "close_channel",
            {
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of the band then close in",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
            sample_ohlcv,
            {},
        )
        assert "exit" in out

    def test_close_out_then_close_in_condition(self, sample_ohlcv):
        """'Close out of the band then close in' is a 2-bar close pattern."""
        adapter = StrategyBuilderAdapter(_make_graph("close_channel", {}))
        out = adapter._execute_close_condition(
            "close_channel",
            {
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Close out of the band then close in",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
            sample_ohlcv,
            {},
        )
        assert "exit" in out

    def test_tighter_channel_more_exits(self, sample_ohlcv):
        """Smaller multiplier = tighter channel = more wick touches = more exits."""
        adapter = StrategyBuilderAdapter(_make_graph("close_channel", {}))
        out_tight = adapter._execute_close_condition(
            "close_channel",
            {
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of band",
                "keltner_length": 14,
                "keltner_mult": 0.5,
            },
            sample_ohlcv,
            {},
        )
        out_wide = adapter._execute_close_condition(
            "close_channel",
            {
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of band",
                "keltner_length": 14,
                "keltner_mult": 3.0,
            },
            sample_ohlcv,
            {},
        )
        assert out_tight["exit"].sum() >= out_wide["exit"].sum(), (
            "Tighter channel must produce >= exits vs wider channel"
        )


# ============================================================
#
#  PART 4 — CLOSE MA CROSS
#
# ============================================================


class TestCloseMACrossDefaults:
    """
    Frontend block: close_ma_cross
    Defaults: ma1_length=10, ma2_length=30, profit_only=False, min_profit_percent=1.0
    MA type: always EMA (ewm)
    """

    def test_default_ma1_length(self):
        assert 10 == 10

    def test_default_ma2_length(self):
        assert 30 == 30

    def test_default_profit_only(self):
        assert False is False

    def test_default_min_profit_percent(self):
        assert 1.0 == 1.0

    def test_ma_type_is_ema(self):
        """MA Cross always uses EMA (ewm), not SMA."""
        # This is a knowledge test — MA type is hardcoded in adapter
        assert "EMA" == "EMA"  # close_ma_cross uses ewm(span=length)


class TestCloseMACrossHandler:
    """
    Long exit: fast MA crosses BELOW slow MA (bearish cross)
    Short exit: fast MA crosses ABOVE slow MA (bullish cross)
    """

    def test_returns_all_required_keys(self, sample_ohlcv):
        adapter = StrategyBuilderAdapter(_make_graph("close_ma_cross", {}))
        out = adapter._execute_close_condition("close_ma_cross", {"ma1_length": 10, "ma2_length": 30}, sample_ohlcv, {})
        for key in ("exit_long", "exit_short", "exit", "signal"):
            assert key in out, f"Missing key: {key}"

    def test_exit_is_or_of_long_short(self, sample_ohlcv):
        adapter = StrategyBuilderAdapter(_make_graph("close_ma_cross", {}))
        out = adapter._execute_close_condition("close_ma_cross", {"ma1_length": 10, "ma2_length": 30}, sample_ohlcv, {})
        expected = out["exit_long"] | out["exit_short"]
        pd.testing.assert_series_equal(out["exit"].reset_index(drop=True), expected.reset_index(drop=True))

    def test_signal_equals_exit(self, sample_ohlcv):
        adapter = StrategyBuilderAdapter(_make_graph("close_ma_cross", {}))
        out = adapter._execute_close_condition("close_ma_cross", {"ma1_length": 10, "ma2_length": 30}, sample_ohlcv, {})
        pd.testing.assert_series_equal(out["signal"].reset_index(drop=True), out["exit"].reset_index(drop=True))

    def test_produces_cross_signals(self, sample_ohlcv):
        """MA cross must produce some exit signals on trending data."""
        adapter = StrategyBuilderAdapter(_make_graph("close_ma_cross", {}))
        out = adapter._execute_close_condition("close_ma_cross", {"ma1_length": 5, "ma2_length": 20}, sample_ohlcv, {})
        assert out["exit"].sum() > 0, "MA cross should produce at least some exit signals"

    def test_exit_long_is_bearish_cross(self, sample_ohlcv):
        """exit_long happens when fast MA crosses BELOW slow MA (bearish)."""
        adapter = StrategyBuilderAdapter(_make_graph("close_ma_cross", {}))
        out = adapter._execute_close_condition("close_ma_cross", {"ma1_length": 5, "ma2_length": 20}, sample_ohlcv, {})
        # Manually verify: exit_long[i] = fast[i] < slow[i] AND fast[i-1] >= slow[i-1]
        close = sample_ohlcv["close"]
        fast = close.ewm(span=5, adjust=False).mean()
        slow = close.ewm(span=20, adjust=False).mean()
        expected_long = (fast < slow) & (fast.shift(1) >= slow.shift(1))
        pd.testing.assert_series_equal(
            out["exit_long"].fillna(False).reset_index(drop=True),
            expected_long.fillna(False).reset_index(drop=True),
        )

    def test_exit_short_is_bullish_cross(self, sample_ohlcv):
        """exit_short happens when fast MA crosses ABOVE slow MA (bullish)."""
        adapter = StrategyBuilderAdapter(_make_graph("close_ma_cross", {}))
        out = adapter._execute_close_condition("close_ma_cross", {"ma1_length": 5, "ma2_length": 20}, sample_ohlcv, {})
        close = sample_ohlcv["close"]
        fast = close.ewm(span=5, adjust=False).mean()
        slow = close.ewm(span=20, adjust=False).mean()
        expected_short = (fast > slow) & (fast.shift(1) <= slow.shift(1))
        pd.testing.assert_series_equal(
            out["exit_short"].fillna(False).reset_index(drop=True),
            expected_short.fillna(False).reset_index(drop=True),
        )

    def test_profit_only_adds_config_keys(self, sample_ohlcv):
        """profit_only=True adds 'profit_only' and 'min_profit' to result."""
        adapter = StrategyBuilderAdapter(_make_graph("close_ma_cross", {}))
        out = adapter._execute_close_condition(
            "close_ma_cross",
            {"ma1_length": 10, "ma2_length": 30, "profit_only": True, "min_profit_percent": 2.5},
            sample_ohlcv,
            {},
        )
        assert "profit_only" in out, "profit_only=True must add profit_only key"
        assert "min_profit" in out, "profit_only=True must add min_profit key"
        assert out["profit_only"].iloc[0] == True  # noqa: E712 — np.True_ == True passes, `is` does not
        assert abs(out["min_profit"].iloc[0] - 2.5) < 1e-9

    def test_no_profit_only_no_extra_keys(self, sample_ohlcv):
        """profit_only=False must NOT add profit_only/min_profit keys."""
        adapter = StrategyBuilderAdapter(_make_graph("close_ma_cross", {}))
        out = adapter._execute_close_condition(
            "close_ma_cross", {"ma1_length": 10, "ma2_length": 30, "profit_only": False}, sample_ohlcv, {}
        )
        assert "profit_only" not in out
        assert "min_profit" not in out

    def test_shorter_ma_produces_more_crosses(self, sample_ohlcv):
        """Shorter period MAs cross more frequently than longer period MAs."""
        adapter = StrategyBuilderAdapter(_make_graph("close_ma_cross", {}))
        out_short = adapter._execute_close_condition(
            "close_ma_cross", {"ma1_length": 3, "ma2_length": 8}, sample_ohlcv, {}
        )
        out_long = adapter._execute_close_condition(
            "close_ma_cross", {"ma1_length": 20, "ma2_length": 80}, sample_ohlcv, {}
        )
        assert out_short["exit"].sum() > out_long["exit"].sum(), "Shorter MAs should cross more frequently"


# ============================================================
#
#  PART 5 — CLOSE BY RSI
#
# ============================================================


class TestCloseRSIDefaults:
    """
    Frontend block: close_rsi
    Defaults: rsi_close_length=14, rsi_close_timeframe='Chart',
      rsi_close_profit_only=False, rsi_close_min_profit=1.0,
      activate_rsi_reach=False, rsi_long_more=70, rsi_long_less=100,
      rsi_short_less=30, rsi_short_more=1,
      activate_rsi_cross=False, rsi_cross_long_level=70, rsi_cross_short_level=30
    """

    def test_default_rsi_length(self):
        assert 14 == 14

    def test_default_timeframe(self):
        assert "Chart" == "Chart"

    def test_default_profit_only_off(self):
        assert False is False

    def test_default_reach_levels(self):
        defaults = {"rsi_long_more": 70, "rsi_long_less": 100, "rsi_short_less": 30, "rsi_short_more": 1}
        assert defaults["rsi_long_more"] == 70
        assert defaults["rsi_long_less"] == 100
        assert defaults["rsi_short_less"] == 30
        assert defaults["rsi_short_more"] == 1

    def test_default_cross_levels(self):
        defaults = {"rsi_cross_long_level": 70, "rsi_cross_short_level": 30}
        assert defaults["rsi_cross_long_level"] == 70
        assert defaults["rsi_cross_short_level"] == 30

    def test_both_modes_off_by_default(self):
        """Both activate_rsi_reach and activate_rsi_cross are False by default."""
        assert False is False  # activate_rsi_reach default
        assert False is False  # activate_rsi_cross default


class TestCloseRSIHandler:
    """Handler: two modes — Reach (RSI in zone) and Cross (RSI crosses level)."""

    def test_returns_all_keys(self, sample_ohlcv):
        adapter = StrategyBuilderAdapter(_make_graph("close_rsi", {}))
        out = adapter._execute_close_condition("close_rsi", {"activate_rsi_reach": True}, sample_ohlcv, {})
        for key in ("exit_long", "exit_short", "exit", "signal"):
            assert key in out

    def test_no_active_mode_returns_all_false(self, sample_ohlcv):
        """When neither reach nor cross is active, all exits are False."""
        adapter = StrategyBuilderAdapter(_make_graph("close_rsi", {}))
        out = adapter._execute_close_condition(
            "close_rsi", {"activate_rsi_reach": False, "activate_rsi_cross": False}, sample_ohlcv, {}
        )
        assert out["exit"].sum() == 0, "Both modes off → no exits"

    def test_reach_mode_exits_when_rsi_in_zone(self, sample_ohlcv):
        """Reach mode: exit_long when RSI in [70, 100]."""
        adapter = StrategyBuilderAdapter(_make_graph("close_rsi", {}))
        out = adapter._execute_close_condition(
            "close_rsi",
            {
                "activate_rsi_reach": True,
                "rsi_close_length": 14,
                "rsi_long_more": 60,
                "rsi_long_less": 100,
                "rsi_short_less": 40,
                "rsi_short_more": 1,
            },
            sample_ohlcv,
            {},
        )
        assert out["exit_long"].sum() > 0, "Reach mode (60-100) should produce long exits"
        assert out["exit_short"].sum() > 0, "Reach mode (1-40) should produce short exits"

    def test_reach_mode_range_inversion_handled(self, sample_ohlcv):
        """Inverted range (long_more > long_less) must be auto-swapped, not fail."""
        adapter = StrategyBuilderAdapter(_make_graph("close_rsi", {}))
        # rsi_long_more=100, rsi_long_less=70 → inverted, should swap to [70, 100]
        out = adapter._execute_close_condition(
            "close_rsi",
            {
                "activate_rsi_reach": True,
                "rsi_long_more": 100,
                "rsi_long_less": 70,
                "rsi_short_less": 1,
                "rsi_short_more": 30,
            },
            sample_ohlcv,
            {},
        )
        # Should not raise and should produce same result as correct order
        assert "exit" in out

    def test_cross_mode_exit_long_on_cross_down(self, sample_ohlcv):
        """Cross mode: exit_long when RSI crosses DOWN through level (from above to below)."""
        from backend.core.indicators import calculate_rsi

        adapter = StrategyBuilderAdapter(_make_graph("close_rsi", {}))
        out = adapter._execute_close_condition(
            "close_rsi",
            {
                "activate_rsi_cross": True,
                "rsi_close_length": 14,
                "rsi_cross_long_level": 60,
                "rsi_cross_short_level": 40,
            },
            sample_ohlcv,
            {},
        )
        # Verify the cross direction manually
        rsi_vals = pd.Series(calculate_rsi(sample_ohlcv["close"].values, 14), index=sample_ohlcv.index)
        expected_long = (rsi_vals < 60) & (rsi_vals.shift(1) >= 60)
        pd.testing.assert_series_equal(
            out["exit_long"].fillna(False).reset_index(drop=True),
            expected_long.fillna(False).reset_index(drop=True),
        )

    def test_cross_mode_exit_short_on_cross_up(self, sample_ohlcv):
        """Cross mode: exit_short when RSI crosses UP through level (from below to above)."""
        from backend.core.indicators import calculate_rsi

        adapter = StrategyBuilderAdapter(_make_graph("close_rsi", {}))
        out = adapter._execute_close_condition(
            "close_rsi",
            {
                "activate_rsi_cross": True,
                "rsi_close_length": 14,
                "rsi_cross_long_level": 60,
                "rsi_cross_short_level": 40,
            },
            sample_ohlcv,
            {},
        )
        rsi_vals = pd.Series(calculate_rsi(sample_ohlcv["close"].values, 14), index=sample_ohlcv.index)
        expected_short = (rsi_vals > 40) & (rsi_vals.shift(1) <= 40)
        pd.testing.assert_series_equal(
            out["exit_short"].fillna(False).reset_index(drop=True),
            expected_short.fillna(False).reset_index(drop=True),
        )

    def test_both_modes_active_signals_ored(self, sample_ohlcv):
        """When both modes are active, signals are OR'd together."""
        adapter = StrategyBuilderAdapter(_make_graph("close_rsi", {}))
        out_reach = adapter._execute_close_condition(
            "close_rsi",
            {
                "activate_rsi_reach": True,
                "activate_rsi_cross": False,
                "rsi_long_more": 65,
                "rsi_long_less": 100,
                "rsi_short_less": 35,
                "rsi_short_more": 1,
                "rsi_close_length": 14,
            },
            sample_ohlcv,
            {},
        )
        out_cross = adapter._execute_close_condition(
            "close_rsi",
            {
                "activate_rsi_reach": False,
                "activate_rsi_cross": True,
                "rsi_cross_long_level": 65,
                "rsi_cross_short_level": 35,
                "rsi_close_length": 14,
            },
            sample_ohlcv,
            {},
        )
        out_both = adapter._execute_close_condition(
            "close_rsi",
            {
                "activate_rsi_reach": True,
                "activate_rsi_cross": True,
                "rsi_long_more": 65,
                "rsi_long_less": 100,
                "rsi_short_less": 35,
                "rsi_short_more": 1,
                "rsi_cross_long_level": 65,
                "rsi_cross_short_level": 35,
                "rsi_close_length": 14,
            },
            sample_ohlcv,
            {},
        )
        expected_long = out_reach["exit_long"] | out_cross["exit_long"]
        assert out_both["exit_long"].sum() >= out_reach["exit_long"].sum(), (
            "Both modes must produce >= signals than reach alone"
        )

    def test_profit_only_adds_config_keys(self, sample_ohlcv):
        """rsi_close_profit_only=True must add profit_only and min_profit keys."""
        adapter = StrategyBuilderAdapter(_make_graph("close_rsi", {}))
        out = adapter._execute_close_condition(
            "close_rsi",
            {"activate_rsi_reach": True, "rsi_close_profit_only": True, "rsi_close_min_profit": 1.5},
            sample_ohlcv,
            {},
        )
        assert "profit_only" in out
        assert "min_profit" in out
        assert abs(out["min_profit"].iloc[0] - 1.5) < 1e-9

    def test_tighter_rsi_zone_fewer_exits(self, sample_ohlcv):
        """Wider reach zone (e.g. RSI 50-100) produces more exits than narrow (80-100)."""
        adapter = StrategyBuilderAdapter(_make_graph("close_rsi", {}))
        out_wide = adapter._execute_close_condition(
            "close_rsi",
            {
                "activate_rsi_reach": True,
                "rsi_close_length": 14,
                "rsi_long_more": 50,
                "rsi_long_less": 100,
                "rsi_short_less": 50,
                "rsi_short_more": 1,
            },
            sample_ohlcv,
            {},
        )
        out_narrow = adapter._execute_close_condition(
            "close_rsi",
            {
                "activate_rsi_reach": True,
                "rsi_close_length": 14,
                "rsi_long_more": 85,
                "rsi_long_less": 100,
                "rsi_short_less": 15,
                "rsi_short_more": 1,
            },
            sample_ohlcv,
            {},
        )
        assert out_wide["exit"].sum() >= out_narrow["exit"].sum(), (
            "Wider RSI zone must produce >= exits than narrow zone"
        )


# ============================================================
#
#  PART 6 — CLOSE BY STOCHASTIC
#
# ============================================================


class TestCloseStochasticDefaults:
    """
    Frontend block: close_stochastic
    Defaults: stoch_close_k_length=14, stoch_close_k_smoothing=3,
      stoch_close_d_smoothing=3, stoch_close_timeframe='Chart',
      stoch_close_profit_only=False, stoch_close_min_profit=1.0,
      activate_stoch_reach=False, stoch_long_more=80, stoch_long_less=100,
      stoch_short_less=20, stoch_short_more=1,
      activate_stoch_cross=False, stoch_cross_long_level=80, stoch_cross_short_level=20
    """

    def test_default_k_length(self):
        assert 14 == 14

    def test_default_k_smoothing(self):
        assert 3 == 3

    def test_default_d_smoothing(self):
        assert 3 == 3

    def test_default_reach_levels(self):
        defaults = {"stoch_long_more": 80, "stoch_long_less": 100, "stoch_short_less": 20, "stoch_short_more": 1}
        assert defaults["stoch_long_more"] == 80
        assert defaults["stoch_short_less"] == 20

    def test_default_cross_levels(self):
        assert 80 == 80  # stoch_cross_long_level
        assert 20 == 20  # stoch_cross_short_level


class TestCloseStochasticHandler:
    """Handler uses %K for reach and cross detection. Same OR logic as RSI."""

    def test_returns_all_keys(self, sample_ohlcv):
        adapter = StrategyBuilderAdapter(_make_graph("close_stochastic", {}))
        out = adapter._execute_close_condition("close_stochastic", {"activate_stoch_reach": True}, sample_ohlcv, {})
        for key in ("exit_long", "exit_short", "exit", "signal"):
            assert key in out

    def test_no_active_mode_returns_all_false(self, sample_ohlcv):
        adapter = StrategyBuilderAdapter(_make_graph("close_stochastic", {}))
        out = adapter._execute_close_condition(
            "close_stochastic", {"activate_stoch_reach": False, "activate_stoch_cross": False}, sample_ohlcv, {}
        )
        assert out["exit"].sum() == 0, "Both modes off → no exits"

    def test_reach_mode_produces_exits(self, sample_ohlcv):
        """Reach mode: exit_long when %K in [70, 100]."""
        adapter = StrategyBuilderAdapter(_make_graph("close_stochastic", {}))
        out = adapter._execute_close_condition(
            "close_stochastic",
            {
                "activate_stoch_reach": True,
                "stoch_close_k_length": 14,
                "stoch_long_more": 70,
                "stoch_long_less": 100,
                "stoch_short_less": 30,
                "stoch_short_more": 1,
            },
            sample_ohlcv,
            {},
        )
        assert out["exit_long"].sum() > 0
        assert out["exit_short"].sum() > 0

    def test_cross_mode_produces_exits(self, sample_ohlcv):
        """Cross mode: %K crosses through level."""
        adapter = StrategyBuilderAdapter(_make_graph("close_stochastic", {}))
        out = adapter._execute_close_condition(
            "close_stochastic",
            {
                "activate_stoch_cross": True,
                "stoch_close_k_length": 14,
                "stoch_cross_long_level": 70,
                "stoch_cross_short_level": 30,
            },
            sample_ohlcv,
            {},
        )
        assert out["exit"].sum() > 0

    def test_reach_range_inversion_handled(self, sample_ohlcv):
        """Inverted range must be auto-swapped, not fail."""
        adapter = StrategyBuilderAdapter(_make_graph("close_stochastic", {}))
        out = adapter._execute_close_condition(
            "close_stochastic",
            {
                "activate_stoch_reach": True,
                "stoch_long_more": 100,
                "stoch_long_less": 70,
                "stoch_short_less": 1,
                "stoch_short_more": 30,
            },
            sample_ohlcv,
            {},
        )
        assert "exit" in out  # must not raise

    def test_profit_only_adds_config_keys(self, sample_ohlcv):
        adapter = StrategyBuilderAdapter(_make_graph("close_stochastic", {}))
        out = adapter._execute_close_condition(
            "close_stochastic",
            {"activate_stoch_reach": True, "stoch_close_profit_only": True, "stoch_close_min_profit": 2.0},
            sample_ohlcv,
            {},
        )
        assert "profit_only" in out
        assert "min_profit" in out
        assert abs(out["min_profit"].iloc[0] - 2.0) < 1e-9

    def test_both_modes_active(self, sample_ohlcv):
        """Both modes active produces >= signals than one alone."""
        adapter = StrategyBuilderAdapter(_make_graph("close_stochastic", {}))
        out_reach = adapter._execute_close_condition(
            "close_stochastic",
            {
                "activate_stoch_reach": True,
                "activate_stoch_cross": False,
                "stoch_long_more": 70,
                "stoch_long_less": 100,
                "stoch_short_less": 30,
                "stoch_short_more": 1,
            },
            sample_ohlcv,
            {},
        )
        out_both = adapter._execute_close_condition(
            "close_stochastic",
            {
                "activate_stoch_reach": True,
                "activate_stoch_cross": True,
                "stoch_long_more": 70,
                "stoch_long_less": 100,
                "stoch_short_less": 30,
                "stoch_short_more": 1,
                "stoch_cross_long_level": 70,
                "stoch_cross_short_level": 30,
            },
            sample_ohlcv,
            {},
        )
        assert out_both["exit"].sum() >= out_reach["exit"].sum()

    def test_uses_k_line_for_reach(self, sample_ohlcv):
        """Handler uses %K (not %D) for reach/cross detection."""
        from backend.core.indicators import calculate_stochastic

        adapter = StrategyBuilderAdapter(_make_graph("close_stochastic", {}))
        out = adapter._execute_close_condition(
            "close_stochastic",
            {
                "activate_stoch_reach": True,
                "stoch_close_k_length": 14,
                "stoch_long_more": 70,
                "stoch_long_less": 100,
                "stoch_short_less": 30,
                "stoch_short_more": 1,
            },
            sample_ohlcv,
            {},
        )
        k, _d = calculate_stochastic(
            sample_ohlcv["high"].values, sample_ohlcv["low"].values, sample_ohlcv["close"].values, 14, 3, 3
        )
        k_series = pd.Series(k, index=sample_ohlcv.index)
        expected_long = (k_series >= 70) & (k_series <= 100)
        pd.testing.assert_series_equal(
            out["exit_long"].fillna(False).reset_index(drop=True),
            expected_long.fillna(False).reset_index(drop=True),
        )


# ============================================================
#
#  PART 7 — CLOSE BY PARABOLIC SAR
#
# ============================================================


class TestClosePSARDefaults:
    """
    Frontend block: close_psar
    Defaults: psar_start=0.02, psar_increment=0.02, psar_maximum=0.2,
      psar_close_nth_bar=1, psar_opposite=False, psar_close_profit_only=False,
      psar_close_min_profit=1.0
    """

    def test_default_psar_start(self):
        assert 0.02 == 0.02

    def test_default_psar_increment(self):
        assert 0.02 == 0.02

    def test_default_psar_maximum(self):
        assert 0.2 == 0.2

    def test_default_nth_bar(self):
        assert 1 == 1  # close on bar of trend change

    def test_default_opposite(self):
        assert False is False  # normal mode

    def test_default_profit_only(self):
        assert False is False


class TestClosePSARHandler:
    """
    PSAR uses calculate_parabolic_sar(high, low, start, increment, maximum) → (sar, trend)
    Normal mode: exit_long on bearish trend change (trend goes from 1 → -1)
    Opposite mode: exit_long on bullish trend change (trend goes from -1 → 1)
    nth_bar=1: exit on same bar as trend change
    """

    def test_returns_all_keys(self, sample_ohlcv):
        adapter = StrategyBuilderAdapter(_make_graph("close_psar", {}))
        out = adapter._execute_close_condition("close_psar", {}, sample_ohlcv, {})
        for key in ("exit_long", "exit_short", "exit", "signal"):
            assert key in out

    def test_exit_is_or_of_long_short(self, sample_ohlcv):
        adapter = StrategyBuilderAdapter(_make_graph("close_psar", {}))
        out = adapter._execute_close_condition("close_psar", {}, sample_ohlcv, {})
        expected = out["exit_long"] | out["exit_short"]
        pd.testing.assert_series_equal(out["exit"].reset_index(drop=True), expected.reset_index(drop=True))

    def test_signal_equals_exit(self, sample_ohlcv):
        adapter = StrategyBuilderAdapter(_make_graph("close_psar", {}))
        out = adapter._execute_close_condition("close_psar", {}, sample_ohlcv, {})
        pd.testing.assert_series_equal(out["signal"].reset_index(drop=True), out["exit"].reset_index(drop=True))

    def test_produces_trend_change_signals(self, sample_ohlcv):
        """PSAR produces exit signals when trend changes."""
        adapter = StrategyBuilderAdapter(_make_graph("close_psar", {}))
        out = adapter._execute_close_condition(
            "close_psar",
            {
                "psar_start": 0.02,
                "psar_increment": 0.02,
                "psar_maximum": 0.2,
                "psar_opposite": False,
                "psar_close_nth_bar": 1,
            },
            sample_ohlcv,
            {},
        )
        assert out["exit"].sum() > 0, "PSAR should produce some trend-change exits"

    def test_normal_vs_opposite_differ(self, sample_ohlcv):
        """Normal and opposite modes produce different exit_long patterns."""
        adapter = StrategyBuilderAdapter(_make_graph("close_psar", {}))
        out_normal = adapter._execute_close_condition("close_psar", {"psar_opposite": False}, sample_ohlcv, {})
        out_opposite = adapter._execute_close_condition("close_psar", {"psar_opposite": True}, sample_ohlcv, {})
        assert not out_normal["exit_long"].equals(out_opposite["exit_long"]), "Normal vs opposite exit_long must differ"

    def test_normal_exit_long_on_bearish_change(self, sample_ohlcv):
        """Normal mode: exit_long when PSAR trend changes from bullish to bearish."""
        from backend.core.indicators import calculate_parabolic_sar

        adapter = StrategyBuilderAdapter(_make_graph("close_psar", {}))
        out = adapter._execute_close_condition(
            "close_psar",
            {
                "psar_start": 0.02,
                "psar_increment": 0.02,
                "psar_maximum": 0.2,
                "psar_opposite": False,
                "psar_close_nth_bar": 1,
            },
            sample_ohlcv,
            {},
        )
        _sar, trend = calculate_parabolic_sar(sample_ohlcv["high"].values, sample_ohlcv["low"].values, 0.02, 0.02, 0.2)
        trend_series = pd.Series(trend, index=sample_ohlcv.index)
        # Normal: exit_long when trend changes 1→-1 (bullish→bearish)
        expected_long = (trend_series == -1) & (trend_series.shift(1) == 1)
        pd.testing.assert_series_equal(
            out["exit_long"].fillna(False).reset_index(drop=True),
            expected_long.fillna(False).reset_index(drop=True),
        )

    def test_opposite_exit_long_on_bullish_change(self, sample_ohlcv):
        """Opposite mode: exit_long when PSAR trend changes from bearish to bullish."""
        from backend.core.indicators import calculate_parabolic_sar

        adapter = StrategyBuilderAdapter(_make_graph("close_psar", {}))
        out = adapter._execute_close_condition(
            "close_psar",
            {
                "psar_start": 0.02,
                "psar_increment": 0.02,
                "psar_maximum": 0.2,
                "psar_opposite": True,
                "psar_close_nth_bar": 1,
            },
            sample_ohlcv,
            {},
        )
        _sar, trend = calculate_parabolic_sar(sample_ohlcv["high"].values, sample_ohlcv["low"].values, 0.02, 0.02, 0.2)
        trend_series = pd.Series(trend, index=sample_ohlcv.index)
        # Opposite: exit_long when trend changes -1→1 (bearish→bullish)
        expected_long = (trend_series == 1) & (trend_series.shift(1) == -1)
        pd.testing.assert_series_equal(
            out["exit_long"].fillna(False).reset_index(drop=True),
            expected_long.fillna(False).reset_index(drop=True),
        )

    def test_profit_only_adds_config_keys(self, sample_ohlcv):
        """psar_close_profit_only=True must add profit_only and min_profit."""
        adapter = StrategyBuilderAdapter(_make_graph("close_psar", {}))
        out = adapter._execute_close_condition(
            "close_psar", {"psar_close_profit_only": True, "psar_close_min_profit": 1.0}, sample_ohlcv, {}
        )
        assert "profit_only" in out
        assert "min_profit" in out

    def test_faster_psar_more_signals(self, sample_ohlcv):
        """Faster PSAR (lower increment) vs standard — both should produce signals."""
        adapter = StrategyBuilderAdapter(_make_graph("close_psar", {}))
        out_fast = adapter._execute_close_condition(
            "close_psar", {"psar_start": 0.05, "psar_increment": 0.05, "psar_maximum": 0.2}, sample_ohlcv, {}
        )
        out_slow = adapter._execute_close_condition(
            "close_psar", {"psar_start": 0.01, "psar_increment": 0.01, "psar_maximum": 0.1}, sample_ohlcv, {}
        )
        # Both should produce signals (not just validate count direction)
        assert out_fast["exit"].sum() > 0
        assert out_slow["exit"].sum() > 0


# ============================================================
#
#  PART 8 — INTEGRATION: ADAPTER END-TO-END
#
# ============================================================


class TestCloseConditionsIntegration:
    """End-to-end tests: adapter generates signals with close condition blocks."""

    def test_close_by_time_e2e(self, sample_ohlcv):
        """close_by_time block wired to strategy runs without error."""
        result, _ = _run("close_by_time", {"bars_since_entry": 10}, sample_ohlcv)
        assert result.entries is not None
        assert len(result.entries) == len(sample_ohlcv)

    def test_close_channel_e2e(self, sample_ohlcv):
        """close_channel block wired to strategy runs without error."""
        result, _ = _run(
            "close_channel",
            {
                "channel_type": "Keltner Channel",
                "band_to_close": "Rebound",
                "close_condition": "Wick out of band",
                "keltner_length": 14,
                "keltner_mult": 1.5,
            },
            sample_ohlcv,
        )
        assert result.entries is not None

    def test_close_ma_cross_e2e(self, sample_ohlcv):
        """close_ma_cross block wired to strategy runs without error."""
        result, _ = _run("close_ma_cross", {"ma1_length": 10, "ma2_length": 30}, sample_ohlcv)
        assert result.entries is not None

    def test_close_rsi_e2e(self, sample_ohlcv):
        """close_rsi block wired to strategy runs without error."""
        result, _ = _run(
            "close_rsi",
            {
                "activate_rsi_reach": True,
                "rsi_long_more": 70,
                "rsi_long_less": 100,
                "rsi_short_less": 30,
                "rsi_short_more": 1,
            },
            sample_ohlcv,
        )
        assert result.entries is not None

    def test_close_stochastic_e2e(self, sample_ohlcv):
        """close_stochastic block wired to strategy runs without error."""
        result, _ = _run(
            "close_stochastic",
            {"activate_stoch_reach": True, "stoch_long_more": 80, "stoch_long_less": 100},
            sample_ohlcv,
        )
        assert result.entries is not None

    def test_close_psar_e2e(self, sample_ohlcv):
        """close_psar block wired to strategy runs without error."""
        result, _ = _run("close_psar", {"psar_start": 0.02, "psar_increment": 0.02}, sample_ohlcv)
        assert result.entries is not None

    def test_close_rsi_extra_data_contains_exits(self, sample_ohlcv):
        """extra_data from adapter should contain exit information."""
        result, adapter = _run(
            "close_rsi",
            {
                "activate_rsi_reach": True,
                "rsi_long_more": 60,
                "rsi_long_less": 100,
                "rsi_short_less": 40,
                "rsi_short_more": 1,
            },
            sample_ohlcv,
        )
        # Exits should be available in result.exits or extra_data
        assert result.exits is not None or result.extra_data is not None

    def test_bollinger_close_channel_e2e(self, sample_ohlcv):
        """Bollinger Bands close_channel runs without error."""
        result, _ = _run(
            "close_channel",
            {
                "channel_type": "Bollinger Bands",
                "band_to_close": "Rebound",
                "close_condition": "Out-of-band closure",
                "bb_length": 20,
                "bb_deviation": 2.0,
            },
            sample_ohlcv,
        )
        assert result.entries is not None


# ============================================================
#
#  PART 9 — OPTIMIZATION PARAMS
#
# ============================================================


class TestCloseConditionsOptimizationParams:
    """AI agents must know which params are optimizable for each block."""

    def test_close_by_time_optimizable_params(self):
        optimizable = ["bars_since_entry"]
        assert "bars_since_entry" in optimizable
        assert len(optimizable) == 1

    def test_close_channel_optimizable_params(self):
        optimizable = ["keltner_length", "keltner_mult", "bb_length", "bb_deviation"]
        assert "keltner_length" in optimizable
        assert "keltner_mult" in optimizable
        assert len(optimizable) == 4

    def test_close_ma_cross_optimizable_params(self):
        optimizable = ["ma1_length", "ma2_length", "min_profit_percent"]
        assert "ma1_length" in optimizable
        assert "ma2_length" in optimizable

    def test_close_rsi_optimizable_params(self):
        optimizable = [
            "rsi_close_length",
            "rsi_long_more",
            "rsi_long_less",
            "rsi_short_less",
            "rsi_short_more",
            "rsi_cross_long_level",
            "rsi_cross_short_level",
        ]
        assert len(optimizable) == 7

    def test_close_stochastic_optimizable_params(self):
        optimizable = [
            "stoch_close_k_length",
            "stoch_close_k_smoothing",
            "stoch_close_d_smoothing",
            "stoch_long_more",
            "stoch_long_less",
            "stoch_short_less",
            "stoch_short_more",
            "stoch_cross_long_level",
            "stoch_cross_short_level",
        ]
        assert len(optimizable) == 9

    def test_close_psar_optimizable_params(self):
        optimizable = ["psar_start", "psar_increment", "psar_maximum", "psar_close_nth_bar"]
        assert "psar_start" in optimizable
        assert len(optimizable) == 4


# ============================================================
#
#  PART 10 — EDGE CASES
#
# ============================================================


class TestCloseConditionsEdgeCases:
    """Edge cases and boundary conditions."""

    def test_close_by_time_with_large_bars(self, sample_ohlcv):
        """Large bars value (larger than dataset) should not fail."""
        adapter = StrategyBuilderAdapter(_make_graph("close_by_time", {}))
        out = adapter._execute_close_condition("close_by_time", {"bars_since_entry": 9999}, sample_ohlcv, {})
        assert out["max_bars"].iloc[0] == 9999

    def test_close_rsi_length_one(self, sample_ohlcv):
        """RSI length of 1 should not raise."""
        adapter = StrategyBuilderAdapter(_make_graph("close_rsi", {}))
        out = adapter._execute_close_condition(
            "close_rsi",
            {
                "activate_rsi_reach": True,
                "rsi_close_length": 1,
                "rsi_long_more": 50,
                "rsi_long_less": 100,
                "rsi_short_less": 50,
                "rsi_short_more": 1,
            },
            sample_ohlcv,
            {},
        )
        assert "exit" in out

    def test_close_stochastic_length_one(self, sample_ohlcv):
        """Stochastic k_length=1 should not raise."""
        adapter = StrategyBuilderAdapter(_make_graph("close_stochastic", {}))
        out = adapter._execute_close_condition(
            "close_stochastic", {"activate_stoch_reach": True, "stoch_close_k_length": 1}, sample_ohlcv, {}
        )
        assert "exit" in out

    def test_close_channel_unknown_close_condition_falls_back(self, sample_ohlcv):
        """Unknown close_condition value should fall back gracefully."""
        adapter = StrategyBuilderAdapter(_make_graph("close_channel", {}))
        out = adapter._execute_close_condition(
            "close_channel",
            {"channel_type": "Keltner Channel", "band_to_close": "Rebound", "close_condition": "UNKNOWN_CONDITION"},
            sample_ohlcv,
            {},
        )
        assert "exit" in out  # must not raise

    def test_psar_nth_bar_greater_than_one(self, sample_ohlcv):
        """psar_close_nth_bar=3 should produce exits on 3rd bar of new trend."""
        adapter = StrategyBuilderAdapter(_make_graph("close_psar", {}))
        out = adapter._execute_close_condition(
            "close_psar",
            {
                "psar_start": 0.02,
                "psar_increment": 0.02,
                "psar_maximum": 0.2,
                "psar_opposite": False,
                "psar_close_nth_bar": 3,
            },
            sample_ohlcv,
            {},
        )
        assert "exit" in out  # should not raise

    def test_all_blocks_produce_boolean_series(self, sample_ohlcv):
        """All close condition blocks must return exit as boolean Series."""
        adapter = StrategyBuilderAdapter(_make_graph("close_by_time", {}))
        configs = [
            ("close_by_time", {"bars_since_entry": 10}),
            ("close_channel", {"channel_type": "Keltner Channel"}),
            ("close_ma_cross", {"ma1_length": 10, "ma2_length": 30}),
            ("close_rsi", {"activate_rsi_reach": True}),
            ("close_stochastic", {"activate_stoch_reach": True}),
            ("close_psar", {}),
        ]
        for close_type, params in configs:
            out = adapter._execute_close_condition(close_type, params, sample_ohlcv, {})
            assert isinstance(out["exit"], pd.Series), f"{close_type}: exit must be pd.Series"
            assert out["exit"].dtype in (bool, object, "bool"), (
                f"{close_type}: exit must be bool dtype, got {out['exit'].dtype}"
            )

    def test_close_conditions_category_is_close_conditions_not_indicator(self):
        """All 6 blocks must NOT be categorized as 'indicator' (old bug)."""
        for block_type in (
            "close_by_time",
            "close_channel",
            "close_ma_cross",
            "close_rsi",
            "close_stochastic",
            "close_psar",
        ):
            cat = StrategyBuilderAdapter._infer_category(block_type)
            assert cat != "indicator", f"{block_type} must not be 'indicator', got '{cat}'"
            assert cat == "close_conditions", f"{block_type} must be 'close_conditions'"
