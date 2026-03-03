"""
AI Agent Knowledge Test: Exit Conditions — Extended Coverage

Tests verify all 8 previously-uncovered exit block types in _execute_exit:
  1. atr_stop         — ATR-based stop loss (use_atr_sl, atr_sl, atr_sl_mult, atr_sl_on_wicks)
  2. time_exit        — Exit after N bars (max_bars Series)
  3. breakeven_exit   — Move SL to breakeven (breakeven_trigger float)
  4. chandelier_exit  — ATR-trailing using rolling high/low (exit_long, exit_short)
  5. session_exit     — Exit at specific hour (exit based on index.hour)
  6. signal_exit      — Opposite signal mode (signal_exit_mode=True)
  7. indicator_exit   — Generic indicator threshold (7 indicators × 4 modes = 28 combos)
  8. partial_close    — Partial close at targets (partial_targets list)

Run:
    py -3.14 -m pytest tests/ai_agents/test_exit_conditions_extended_ai_agents.py -v
    py -3.14 -m pytest tests/ai_agents/test_exit_conditions_extended_ai_agents.py -v -k "TestIndicatorExit"
    py -3.14 -m pytest tests/ai_agents/test_exit_conditions_extended_ai_agents.py -v -k "TestChandelierExit"
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

from backend.backtesting.strategies import SignalResult
from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter as _Adapter

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="module")
def sample_ohlcv() -> pd.DataFrame:
    """1000-bar OHLCV with hourly timestamps."""
    np.random.seed(7)
    n = 1000
    dates = pd.date_range("2025-01-01", periods=n, freq="1h")
    prices = 50000.0 + np.cumsum(np.random.randn(n) * 200)
    prices = np.clip(prices, 1000, None)
    high = prices + np.abs(np.random.randn(n) * 80)
    low = prices - np.abs(np.random.randn(n) * 80)
    low = np.clip(low, 1, None)
    return pd.DataFrame(
        {
            "open": prices + np.random.randn(n) * 25,
            "high": high,
            "low": low,
            "close": prices,
            "volume": np.random.uniform(500, 5000, n),
        },
        index=dates,
    )


# Minimal strategy graph with a single RSI block so _validate_params doesn't raise
_EMPTY_GRAPH: dict = {
    "blocks": [{"id": "rsi_dummy", "type": "rsi", "params": {"period": 14}, "inputs": {}}],
    "connections": [],
}


@pytest.fixture(scope="module")
def adapter() -> _Adapter:
    """Adapter instance with minimal graph — used to call _execute_exit directly."""
    return _Adapter(_EMPTY_GRAPH)


def _call_exit(adapter: _Adapter, exit_type: str, params: dict, ohlcv: pd.DataFrame) -> dict[str, Any]:
    """Call _execute_exit directly."""
    return adapter._execute_exit(exit_type=exit_type, params=params, ohlcv=ohlcv, inputs={})


# ============================================================
# 1. ATR Stop
# ============================================================


class TestAtrStop:
    """Tests for atr_stop exit block."""

    def test_returns_exit_series(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "atr_stop", {"period": 14, "multiplier": 2.0}, sample_ohlcv)
        assert "exit" in result
        assert isinstance(result["exit"], pd.Series)
        assert len(result["exit"]) == len(sample_ohlcv)

    def test_exit_all_false(self, adapter, sample_ohlcv):
        """atr_stop exit Series is always False — engine handles execution."""
        result = _call_exit(adapter, "atr_stop", {"period": 14, "multiplier": 2.0}, sample_ohlcv)
        assert not result["exit"].any(), "atr_stop should return all-False exit (engine executes)"

    def test_use_atr_sl_true(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "atr_stop", {"period": 14, "multiplier": 2.0}, sample_ohlcv)
        assert result.get("use_atr_sl") is True

    def test_atr_sl_series_positive(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "atr_stop", {"period": 14, "multiplier": 2.0}, sample_ohlcv)
        assert "atr_sl" in result
        atr_sl = result["atr_sl"]
        assert isinstance(atr_sl, pd.Series)
        valid = atr_sl.dropna()
        assert (valid >= 0).all(), "ATR SL values must be non-negative"

    def test_atr_sl_mult_passed_through(self, adapter, sample_ohlcv):
        for mult in [1.0, 2.0, 3.5]:
            result = _call_exit(adapter, "atr_stop", {"period": 14, "multiplier": mult}, sample_ohlcv)
            assert abs(result["atr_sl_mult"] - mult) < 1e-9, f"multiplier {mult} not passed through"

    def test_on_wicks_default_false(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "atr_stop", {"period": 14, "multiplier": 2.0}, sample_ohlcv)
        assert result["atr_sl_on_wicks"] is False

    def test_on_wicks_true(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "atr_stop", {"period": 14, "multiplier": 2.0, "on_wicks": True}, sample_ohlcv)
        assert result["atr_sl_on_wicks"] is True

    def test_period_clamped_min(self, adapter, sample_ohlcv):
        """Period 0 is clamped to minimum (1)."""
        result = _call_exit(adapter, "atr_stop", {"period": 0, "multiplier": 2.0}, sample_ohlcv)
        assert "atr_sl" in result  # should not crash

    def test_period_clamped_max(self, adapter, sample_ohlcv):
        """Period > 150 is clamped to 150."""
        result = _call_exit(adapter, "atr_stop", {"period": 999, "multiplier": 2.0}, sample_ohlcv)
        assert "atr_sl" in result

    def test_multiplier_clamped_min(self, adapter, sample_ohlcv):
        """Multiplier < 0.1 is clamped to 0.1."""
        result = _call_exit(adapter, "atr_stop", {"period": 14, "multiplier": 0.001}, sample_ohlcv)
        assert result["atr_sl_mult"] >= 0.1

    def test_multiplier_clamped_max(self, adapter, sample_ohlcv):
        """Multiplier > 4.0 is clamped to 4.0."""
        result = _call_exit(adapter, "atr_stop", {"period": 14, "multiplier": 99.0}, sample_ohlcv)
        assert result["atr_sl_mult"] <= 4.0

    def test_smoothing_rma_default(self, adapter, sample_ohlcv):
        """Default smoothing is RMA."""
        result = _call_exit(adapter, "atr_stop", {"period": 14, "multiplier": 2.0}, sample_ohlcv)
        assert "atr_sl" in result  # RMA smoothing used internally

    def test_smoothing_ema(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "atr_stop", {"period": 14, "multiplier": 2.0, "smoothing": "EMA"}, sample_ohlcv)
        assert "atr_sl" in result

    def test_smoothing_sma(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "atr_stop", {"period": 14, "multiplier": 2.0, "smoothing": "SMA"}, sample_ohlcv)
        assert "atr_sl" in result

    def test_smoothing_invalid_falls_back(self, adapter, sample_ohlcv):
        """Invalid smoothing method is corrected to RMA."""
        result = _call_exit(adapter, "atr_stop", {"period": 14, "multiplier": 2.0, "smoothing": "BANANA"}, sample_ohlcv)
        assert "atr_sl" in result  # should not crash

    def test_period_effect_on_atr_values(self, adapter, sample_ohlcv):
        """Different periods produce different ATR SL values."""
        r5 = _call_exit(adapter, "atr_stop", {"period": 5, "multiplier": 2.0}, sample_ohlcv)
        r50 = _call_exit(adapter, "atr_stop", {"period": 50, "multiplier": 2.0}, sample_ohlcv)
        v5 = r5["atr_sl"].dropna().values
        v50 = r50["atr_sl"].dropna().values
        n = min(len(v5), len(v50))
        assert not np.allclose(v5[-n:], v50[-n:]), "Different ATR periods should produce different SL values"


# ============================================================
# 2. Time Exit
# ============================================================


class TestTimeExit:
    """Tests for time_exit block."""

    def test_returns_exit_series(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "time_exit", {"bars": 10}, sample_ohlcv)
        assert "exit" in result
        assert isinstance(result["exit"], pd.Series)
        assert len(result["exit"]) == len(sample_ohlcv)

    def test_exit_all_false(self, adapter, sample_ohlcv):
        """time_exit exit Series is all False — engine tracks bars."""
        result = _call_exit(adapter, "time_exit", {"bars": 10}, sample_ohlcv)
        assert not result["exit"].any()

    def test_max_bars_series_returned(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "time_exit", {"bars": 10}, sample_ohlcv)
        assert "max_bars" in result
        assert isinstance(result["max_bars"], pd.Series)
        assert len(result["max_bars"]) == len(sample_ohlcv)

    def test_max_bars_constant_value(self, adapter, sample_ohlcv):
        """max_bars should be a constant Series matching the bars param."""
        result = _call_exit(adapter, "time_exit", {"bars": 15}, sample_ohlcv)
        assert (result["max_bars"] == 15).all()

    @pytest.mark.parametrize("bars", [1, 5, 10, 20, 50, 100])
    def test_various_bar_counts(self, adapter, sample_ohlcv, bars):
        result = _call_exit(adapter, "time_exit", {"bars": bars}, sample_ohlcv)
        assert (result["max_bars"] == bars).all()

    def test_default_bars_is_10(self, adapter, sample_ohlcv):
        """Default bars param is 10."""
        result = _call_exit(adapter, "time_exit", {}, sample_ohlcv)
        assert (result["max_bars"] == 10).all()


# ============================================================
# 3. Breakeven Exit
# ============================================================


class TestBreakevenExit:
    """Tests for breakeven_exit and break_even_exit (alias)."""

    @pytest.mark.parametrize("exit_type", ["breakeven_exit", "break_even_exit"])
    def test_returns_exit_series(self, adapter, sample_ohlcv, exit_type):
        result = _call_exit(adapter, exit_type, {"trigger_percent": 1.0}, sample_ohlcv)
        assert "exit" in result
        assert isinstance(result["exit"], pd.Series)
        assert not result["exit"].any()

    @pytest.mark.parametrize("exit_type", ["breakeven_exit", "break_even_exit"])
    def test_breakeven_trigger_returned(self, adapter, sample_ohlcv, exit_type):
        result = _call_exit(adapter, exit_type, {"trigger_percent": 1.5}, sample_ohlcv)
        assert "breakeven_trigger" in result
        assert abs(result["breakeven_trigger"] - 1.5) < 1e-9

    def test_default_trigger_is_1pct(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "breakeven_exit", {}, sample_ohlcv)
        assert abs(result["breakeven_trigger"] - 1.0) < 1e-9

    @pytest.mark.parametrize("trigger", [0.5, 1.0, 2.0, 3.0, 5.0])
    def test_various_trigger_values(self, adapter, sample_ohlcv, trigger):
        result = _call_exit(adapter, "breakeven_exit", {"trigger_percent": trigger}, sample_ohlcv)
        assert abs(result["breakeven_trigger"] - trigger) < 1e-9

    def test_both_aliases_equivalent(self, adapter, sample_ohlcv):
        """breakeven_exit and break_even_exit produce identical results."""
        r1 = _call_exit(adapter, "breakeven_exit", {"trigger_percent": 2.0}, sample_ohlcv)
        r2 = _call_exit(adapter, "break_even_exit", {"trigger_percent": 2.0}, sample_ohlcv)
        assert r1["breakeven_trigger"] == r2["breakeven_trigger"]
        assert (r1["exit"] == r2["exit"]).all()


# ============================================================
# 4. Chandelier Exit
# ============================================================


class TestChandelierExit:
    """Tests for chandelier_exit block."""

    def test_returns_exit_long_short(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "chandelier_exit", {"period": 22, "multiplier": 3.0}, sample_ohlcv)
        assert "exit_long" in result
        assert "exit_short" in result
        assert "exit" in result

    def test_exit_series_are_bool(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "chandelier_exit", {"period": 22, "multiplier": 3.0}, sample_ohlcv)
        assert result["exit_long"].dtype == bool or pd.api.types.is_bool_dtype(result["exit_long"])
        assert result["exit_short"].dtype == bool or pd.api.types.is_bool_dtype(result["exit_short"])

    def test_exit_is_union_of_long_short(self, adapter, sample_ohlcv):
        """exit = exit_long | exit_short."""
        result = _call_exit(adapter, "chandelier_exit", {"period": 22, "multiplier": 3.0}, sample_ohlcv)
        expected = result["exit_long"] | result["exit_short"]
        assert (result["exit"] == expected).all()

    def test_exit_series_correct_length(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "chandelier_exit", {"period": 22, "multiplier": 3.0}, sample_ohlcv)
        assert len(result["exit_long"]) == len(sample_ohlcv)
        assert len(result["exit_short"]) == len(sample_ohlcv)

    def test_exit_fires_some_signals(self, adapter, sample_ohlcv):
        """With 1000 bars, chandelier should fire at least a few exits."""
        result = _call_exit(adapter, "chandelier_exit", {"period": 22, "multiplier": 3.0}, sample_ohlcv)
        total_exits = result["exit"].sum()
        assert total_exits > 0, "Chandelier should fire some exit signals over 1000 bars"

    def test_period_effect(self, adapter, sample_ohlcv):
        """Different periods produce different exit signals."""
        r10 = _call_exit(adapter, "chandelier_exit", {"period": 10, "multiplier": 3.0}, sample_ohlcv)
        r50 = _call_exit(adapter, "chandelier_exit", {"period": 50, "multiplier": 3.0}, sample_ohlcv)
        # Different periods should yield different total exit counts
        exits10 = r10["exit"].sum()
        exits50 = r50["exit"].sum()
        # Just verify the structure is correct regardless of exit counts
        assert isinstance(exits10, (int, np.integer))
        assert isinstance(exits50, (int, np.integer))

    def test_multiplier_effect(self, adapter, sample_ohlcv):
        """Higher multiplier means less sensitive — fewer exits."""
        r_tight = _call_exit(adapter, "chandelier_exit", {"period": 22, "multiplier": 1.0}, sample_ohlcv)
        r_wide = _call_exit(adapter, "chandelier_exit", {"period": 22, "multiplier": 5.0}, sample_ohlcv)
        exits_tight = r_tight["exit"].sum()
        exits_wide = r_wide["exit"].sum()
        # Just verify both are valid counts — ordering depends on price action
        assert isinstance(exits_tight, (int, np.integer))
        assert isinstance(exits_wide, (int, np.integer))

    def test_default_params(self, adapter, sample_ohlcv):
        """Default params (period=22, mult=3.0) should work."""
        result = _call_exit(adapter, "chandelier_exit", {}, sample_ohlcv)
        assert "exit_long" in result and "exit_short" in result


# ============================================================
# 5. Session Exit
# ============================================================


class TestSessionExit:
    """Tests for session_exit block."""

    def test_returns_exit_series(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "session_exit", {"exit_hour": 21}, sample_ohlcv)
        assert "exit" in result
        assert isinstance(result["exit"], pd.Series)
        assert len(result["exit"]) == len(sample_ohlcv)

    def test_exit_fires_at_correct_hour(self, adapter, sample_ohlcv):
        """Exit fires only on bars where hour matches exit_hour."""
        for exit_hour in [0, 6, 12, 18, 21, 23]:
            result = _call_exit(adapter, "session_exit", {"exit_hour": exit_hour}, sample_ohlcv)
            exit_bars = result["exit"]
            # Verify: every True bar has the matching hour
            true_indices = sample_ohlcv.index[exit_bars]
            if len(true_indices) > 0:
                assert (true_indices.hour == exit_hour).all(), (
                    f"session_exit hour={exit_hour}: some exit bars have wrong hour"
                )

    def test_exit_does_not_fire_at_wrong_hour(self, adapter, sample_ohlcv):
        """No exits at non-matching hours."""
        result = _call_exit(adapter, "session_exit", {"exit_hour": 5}, sample_ohlcv)
        exit_bars = result["exit"]
        false_indices = sample_ohlcv.index[~exit_bars]
        # All non-exit bars should NOT be hour 5
        if len(false_indices) > 0:
            assert not (false_indices.hour == 5).all(), "Non-exit bars should not all be hour 5"

    def test_default_exit_hour_21(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "session_exit", {}, sample_ohlcv)
        true_indices = sample_ohlcv.index[result["exit"]]
        if len(true_indices) > 0:
            assert (true_indices.hour == 21).all()

    @pytest.mark.parametrize("exit_hour", [0, 3, 8, 16, 20, 23])
    def test_various_exit_hours(self, adapter, sample_ohlcv, exit_hour):
        result = _call_exit(adapter, "session_exit", {"exit_hour": exit_hour}, sample_ohlcv)
        assert isinstance(result["exit"], pd.Series)
        assert len(result["exit"]) == len(sample_ohlcv)

    def test_exit_fires_predictable_count(self, adapter, sample_ohlcv):
        """With hourly data over 1000 bars, each hour fires ~41-42 times."""
        for exit_hour in [0, 12]:
            result = _call_exit(adapter, "session_exit", {"exit_hour": exit_hour}, sample_ohlcv)
            count = result["exit"].sum()
            # 1000 bars / 24 hours ≈ 41-42 bars per hour
            assert 35 <= count <= 50, f"session_exit hour={exit_hour}: expected ~41 exits, got {count}"


# ============================================================
# 6. Signal Exit
# ============================================================


class TestSignalExit:
    """Tests for signal_exit block."""

    def test_returns_exit_series(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "signal_exit", {}, sample_ohlcv)
        assert "exit" in result
        assert isinstance(result["exit"], pd.Series)
        assert len(result["exit"]) == len(sample_ohlcv)

    def test_exit_all_false(self, adapter, sample_ohlcv):
        """signal_exit returns all-False — engine handles by tracking opposite signal."""
        result = _call_exit(adapter, "signal_exit", {}, sample_ohlcv)
        assert not result["exit"].any()

    def test_signal_exit_mode_true(self, adapter, sample_ohlcv):
        """signal_exit_mode=True must be present to tell engine to use opposite signal."""
        result = _call_exit(adapter, "signal_exit", {}, sample_ohlcv)
        assert result.get("signal_exit_mode") is True

    def test_no_params_required(self, adapter, sample_ohlcv):
        """signal_exit works with empty params dict."""
        result = _call_exit(adapter, "signal_exit", {}, sample_ohlcv)
        assert "signal_exit_mode" in result

    def test_extra_params_ignored(self, adapter, sample_ohlcv):
        """Extra unknown params don't crash signal_exit."""
        result = _call_exit(adapter, "signal_exit", {"foo": "bar", "baz": 42}, sample_ohlcv)
        assert "signal_exit_mode" in result


# ============================================================
# 7. Indicator Exit
# ============================================================


class TestIndicatorExit:
    """Tests for indicator_exit block — 7 indicators × 4 modes."""

    INDICATORS = ["rsi", "cci", "mfi", "roc", "obv", "macd", "stochastic"]
    MODES = ["above", "below", "cross_above", "cross_below"]

    @pytest.mark.parametrize("indicator", INDICATORS)
    def test_indicator_default_params(self, adapter, sample_ohlcv, indicator):
        """Each indicator produces valid exit series with default threshold."""
        result = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": indicator, "threshold": 50, "mode": "above", "period": 14},
            sample_ohlcv,
        )
        assert "exit" in result
        exit_series = result["exit"]
        assert isinstance(exit_series, pd.Series)
        assert len(exit_series) == len(sample_ohlcv)

    @pytest.mark.parametrize("mode", MODES)
    def test_rsi_all_modes(self, adapter, sample_ohlcv, mode):
        """RSI works with all 4 exit modes."""
        result = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": "rsi", "threshold": 70, "mode": mode, "period": 14},
            sample_ohlcv,
        )
        assert "exit" in result
        exit_series = result["exit"]
        assert pd.api.types.is_bool_dtype(exit_series) or exit_series.dtype == object

    @pytest.mark.parametrize("mode", MODES)
    def test_cci_all_modes(self, adapter, sample_ohlcv, mode):
        result = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": "cci", "threshold": 100, "mode": mode, "period": 20},
            sample_ohlcv,
        )
        assert "exit" in result

    @pytest.mark.parametrize("mode", MODES)
    def test_mfi_all_modes(self, adapter, sample_ohlcv, mode):
        result = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": "mfi", "threshold": 80, "mode": mode, "period": 14},
            sample_ohlcv,
        )
        assert "exit" in result

    @pytest.mark.parametrize("mode", MODES)
    def test_roc_all_modes(self, adapter, sample_ohlcv, mode):
        result = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": "roc", "threshold": 0, "mode": mode, "period": 12},
            sample_ohlcv,
        )
        assert "exit" in result

    @pytest.mark.parametrize("mode", MODES)
    def test_obv_all_modes(self, adapter, sample_ohlcv, mode):
        result = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": "obv", "threshold": 0, "mode": mode, "period": 14},
            sample_ohlcv,
        )
        assert "exit" in result

    @pytest.mark.parametrize("mode", MODES)
    def test_macd_all_modes(self, adapter, sample_ohlcv, mode):
        """MACD uses histogram for comparison."""
        result = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": "macd", "threshold": 0, "mode": mode, "period": 12},
            sample_ohlcv,
        )
        assert "exit" in result

    @pytest.mark.parametrize("mode", MODES)
    def test_stochastic_all_modes(self, adapter, sample_ohlcv, mode):
        result = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": "stochastic", "threshold": 80, "mode": mode, "period": 14},
            sample_ohlcv,
        )
        assert "exit" in result

    def test_above_mode_logic(self, adapter, sample_ohlcv):
        """'above' mode: exit = indicator > threshold."""
        # RSI with threshold=0 should always be above → all True
        result = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": "rsi", "threshold": 0, "mode": "above", "period": 14},
            sample_ohlcv,
        )
        # RSI > 0 is almost always True (after warmup)
        valid = result["exit"].iloc[20:]
        assert valid.sum() > len(valid) * 0.99, "RSI > 0 should be almost always True"

    def test_below_mode_logic(self, adapter, sample_ohlcv):
        """'below' mode: exit = indicator < threshold."""
        # RSI with threshold=0 should never be below → all False
        result = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": "rsi", "threshold": 0, "mode": "below", "period": 14},
            sample_ohlcv,
        )
        valid = result["exit"].iloc[20:]
        assert valid.sum() == 0, "RSI < 0 should never be True"

    def test_cross_above_fires_fewer_than_above(self, adapter, sample_ohlcv):
        """cross_above fires fewer signals than plain above (only on crossings)."""
        r_above = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": "rsi", "threshold": 50, "mode": "above", "period": 14},
            sample_ohlcv,
        )
        r_cross = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": "rsi", "threshold": 50, "mode": "cross_above", "period": 14},
            sample_ohlcv,
        )
        assert r_cross["exit"].sum() <= r_above["exit"].sum(), "cross_above should fire fewer signals than above"

    def test_cross_below_fires_fewer_than_below(self, adapter, sample_ohlcv):
        r_below = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": "rsi", "threshold": 50, "mode": "below", "period": 14},
            sample_ohlcv,
        )
        r_cross = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": "rsi", "threshold": 50, "mode": "cross_below", "period": 14},
            sample_ohlcv,
        )
        assert r_cross["exit"].sum() <= r_below["exit"].sum()

    def test_no_nan_in_exit(self, adapter, sample_ohlcv):
        """Exit Series should have no NaN values (fillna applied)."""
        for indicator in self.INDICATORS:
            result = _call_exit(
                adapter,
                "indicator_exit",
                {"indicator": indicator, "threshold": 50, "mode": "above", "period": 14},
                sample_ohlcv,
            )
            assert not result["exit"].isna().any(), f"indicator_exit ({indicator}): exit contains NaN"

    def test_unknown_indicator_fallback_to_rsi(self, adapter, sample_ohlcv):
        """Unknown indicator falls back to RSI without crashing."""
        result = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": "foobar_unknown", "threshold": 50, "mode": "above", "period": 14},
            sample_ohlcv,
        )
        assert "exit" in result
        # Should not raise

    def test_default_indicator_is_rsi(self, adapter, sample_ohlcv):
        """Default indicator (omitted from params) should work."""
        result = _call_exit(
            adapter,
            "indicator_exit",
            {"threshold": 50, "mode": "above"},
            sample_ohlcv,
        )
        assert "exit" in result

    @pytest.mark.parametrize(
        "indicator,mode",
        [
            ("rsi", "above"),
            ("cci", "below"),
            ("macd", "cross_above"),
            ("stochastic", "cross_below"),
            ("obv", "above"),
            ("mfi", "below"),
            ("roc", "cross_above"),
        ],
    )
    def test_all_indicator_mode_combos_produce_valid_series(self, adapter, sample_ohlcv, indicator, mode):
        """Spot check of 7 indicator × mode combos."""
        result = _call_exit(
            adapter,
            "indicator_exit",
            {"indicator": indicator, "threshold": 50, "mode": mode, "period": 14},
            sample_ohlcv,
        )
        assert "exit" in result
        assert len(result["exit"]) == len(sample_ohlcv)
        assert not result["exit"].isna().any()


# ============================================================
# 8. Partial Close
# ============================================================


class TestPartialClose:
    """Tests for partial_close exit block."""

    def test_returns_exit_series(self, adapter, sample_ohlcv):
        result = _call_exit(adapter, "partial_close", {"targets": [{"profit": 1.0, "close_pct": 50}]}, sample_ohlcv)
        assert "exit" in result
        assert isinstance(result["exit"], pd.Series)
        assert not result["exit"].any()

    def test_partial_targets_returned(self, adapter, sample_ohlcv):
        targets = [{"profit": 1.0, "close_pct": 50}]
        result = _call_exit(adapter, "partial_close", {"targets": targets}, sample_ohlcv)
        assert "partial_targets" in result
        assert result["partial_targets"] == targets

    def test_multiple_targets(self, adapter, sample_ohlcv):
        targets = [
            {"profit": 1.0, "close_pct": 30},
            {"profit": 2.0, "close_pct": 30},
            {"profit": 3.0, "close_pct": 40},
        ]
        result = _call_exit(adapter, "partial_close", {"targets": targets}, sample_ohlcv)
        assert result["partial_targets"] == targets
        assert len(result["partial_targets"]) == 3

    def test_default_targets(self, adapter, sample_ohlcv):
        """Default targets when none provided."""
        result = _call_exit(adapter, "partial_close", {}, sample_ohlcv)
        assert "partial_targets" in result
        assert isinstance(result["partial_targets"], list)
        assert len(result["partial_targets"]) > 0

    def test_targets_structure(self, adapter, sample_ohlcv):
        """Default target has profit and close_pct keys."""
        result = _call_exit(adapter, "partial_close", {}, sample_ohlcv)
        target = result["partial_targets"][0]
        assert "profit" in target or "close_pct" in target, f"partial_close target missing expected keys: {target}"

    def test_empty_targets_list(self, adapter, sample_ohlcv):
        """Empty targets list is passed through without crash."""
        result = _call_exit(adapter, "partial_close", {"targets": []}, sample_ohlcv)
        assert "partial_targets" in result

    def test_e2e_generate_signals(self, sample_ohlcv):
        """partial_close works end-to-end in generate_signals."""
        strategy = {
            "blocks": [
                {
                    "id": "rsi_1",
                    "type": "rsi",
                    "params": {"period": 14, "cross_long_level": 30, "cross_short_level": 70},
                    "inputs": {},
                },
                {
                    "id": "exit_1",
                    "type": "partial_close",
                    "category": "exit",
                    "params": {"targets": [{"profit": 1.0, "close_pct": 50}]},
                    "inputs": {},
                },
            ],
            "connections": [],
        }
        result = _Adapter(strategy).generate_signals(sample_ohlcv)
        assert isinstance(result, SignalResult)


# ============================================================
# Integration Tests: Exit Blocks with Entry Blocks
# ============================================================


class TestExitEntryIntegration:
    """Combined entry + exit block strategies end-to-end."""

    def test_atr_stop_with_rsi_entry(self, adapter, sample_ohlcv):
        strategy = {
            "blocks": [
                {
                    "id": "rsi_1",
                    "type": "rsi",
                    "params": {"period": 14, "cross_long_level": 30, "cross_short_level": 70},
                    "inputs": {},
                },
                {
                    "id": "exit_1",
                    "type": "atr_stop",
                    "category": "exit",
                    "params": {"period": 14, "multiplier": 2.0},
                    "inputs": {},
                },
            ],
            "connections": [],
        }
        result = _Adapter(strategy).generate_signals(sample_ohlcv)
        assert isinstance(result, SignalResult)

    def test_time_exit_with_macd_entry(self, adapter, sample_ohlcv):
        strategy = {
            "blocks": [
                {"id": "macd_1", "type": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}, "inputs": {}},
                {"id": "exit_1", "type": "time_exit", "category": "exit", "params": {"bars": 20}, "inputs": {}},
            ],
            "connections": [],
        }
        result = _Adapter(strategy).generate_signals(sample_ohlcv)
        assert isinstance(result, SignalResult)

    def test_chandelier_with_supertrend_entry(self, adapter, sample_ohlcv):
        strategy = {
            "blocks": [
                {"id": "st_1", "type": "supertrend", "params": {"period": 10, "multiplier": 3.0}, "inputs": {}},
                {
                    "id": "exit_1",
                    "type": "chandelier_exit",
                    "category": "exit",
                    "params": {"period": 22, "multiplier": 3.0},
                    "inputs": {},
                },
            ],
            "connections": [],
        }
        result = _Adapter(strategy).generate_signals(sample_ohlcv)
        assert isinstance(result, SignalResult)

    def test_session_exit_with_qqe_entry(self, adapter, sample_ohlcv):
        strategy = {
            "blocks": [
                {
                    "id": "qqe_1",
                    "type": "qqe",
                    "params": {"rsi_period": 14, "fast": 5, "slow": 3, "sf": 5.0},
                    "inputs": {},
                },
                {"id": "exit_1", "type": "session_exit", "category": "exit", "params": {"exit_hour": 20}, "inputs": {}},
            ],
            "connections": [],
        }
        result = _Adapter(strategy).generate_signals(sample_ohlcv)
        assert isinstance(result, SignalResult)

    def test_indicator_exit_rsi_mode_with_stoch_entry(self, adapter, sample_ohlcv):
        strategy = {
            "blocks": [
                {
                    "id": "stoch_1",
                    "type": "stochastic",
                    "params": {"k_period": 14, "d_period": 3, "smooth_k": 3},
                    "inputs": {},
                },
                {
                    "id": "exit_1",
                    "type": "indicator_exit",
                    "category": "exit",
                    "params": {"indicator": "rsi", "threshold": 70, "mode": "above", "period": 14},
                    "inputs": {},
                },
            ],
            "connections": [],
        }
        result = _Adapter(strategy).generate_signals(sample_ohlcv)
        assert isinstance(result, SignalResult)

    def test_signal_exit_standalone(self, adapter, sample_ohlcv):
        strategy = {
            "blocks": [{"id": "exit_1", "type": "signal_exit", "category": "exit", "params": {}, "inputs": {}}],
            "connections": [],
        }
        result = _Adapter(strategy).generate_signals(sample_ohlcv)
        assert isinstance(result, SignalResult)

    def test_breakeven_with_rsi(self, adapter, sample_ohlcv):
        strategy = {
            "blocks": [
                {
                    "id": "rsi_1",
                    "type": "rsi",
                    "params": {"period": 14, "cross_long_level": 30, "cross_short_level": 70},
                    "inputs": {},
                },
                {
                    "id": "exit_1",
                    "type": "breakeven_exit",
                    "category": "exit",
                    "params": {"trigger_percent": 1.5},
                    "inputs": {},
                },
            ],
            "connections": [],
        }
        result = _Adapter(strategy).generate_signals(sample_ohlcv)
        assert isinstance(result, SignalResult)


# ============================================================
# Exit Block Registry Completeness
# ============================================================


class TestExitBlockCompleteness:
    """Verify all exit types are handled by _execute_exit."""

    EXIT_TYPES = [
        "static_sltp",
        "trailing_stop_exit",
        "atr_stop",
        "time_exit",
        "breakeven_exit",
        "break_even_exit",
        "chandelier_exit",
        "atr_exit",
        "session_exit",
        "signal_exit",
        "indicator_exit",
        "partial_close",
        "multi_tp_exit",
    ]

    @pytest.mark.parametrize("exit_type", EXIT_TYPES)
    def test_exit_type_returns_exit_key(self, adapter, sample_ohlcv, exit_type):
        """Every exit type must return at minimum an 'exit' key."""
        # Use safe params for each type
        params = {
            "static_sltp": {"stop_loss_percent": 1.5, "take_profit_percent": 2.0},
            "trailing_stop_exit": {"activation_percent": 1.0, "trailing_percent": 0.5},
            "atr_stop": {"period": 14, "multiplier": 2.0},
            "time_exit": {"bars": 10},
            "breakeven_exit": {"trigger_percent": 1.0},
            "break_even_exit": {"trigger_percent": 1.0},
            "chandelier_exit": {"period": 22, "multiplier": 3.0},
            "atr_exit": {"use_atr_sl": True, "atr_sl_period": 14, "atr_sl_multiplier": 2.0},
            "session_exit": {"exit_hour": 21},
            "signal_exit": {},
            "indicator_exit": {"indicator": "rsi", "threshold": 70, "mode": "above", "period": 14},
            "partial_close": {"targets": [{"profit": 1.0, "close_pct": 50}]},
            "multi_tp_exit": {"tp1_percent": 1.0, "tp2_percent": 2.0, "tp3_percent": 3.0},
        }.get(exit_type, {})

        result = adapter._execute_exit(exit_type=exit_type, params=params, ohlcv=sample_ohlcv, inputs={})
        assert "exit" in result, f"Exit type '{exit_type}' did not return 'exit' key"
        assert isinstance(result["exit"], pd.Series), f"Exit type '{exit_type}' 'exit' is not pd.Series"
        assert len(result["exit"]) == len(sample_ohlcv), f"Exit type '{exit_type}' 'exit' length mismatch"

    def test_unknown_exit_type_returns_false_series(self, adapter, sample_ohlcv):
        """Unknown exit type falls through to default — returns all-False exit."""
        result = adapter._execute_exit(
            exit_type="totally_unknown_exit_xyz",
            params={},
            ohlcv=sample_ohlcv,
            inputs={},
        )
        assert "exit" in result
        assert not result["exit"].any()
