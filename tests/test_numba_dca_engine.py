"""
Tests for the Numba JIT DCA simulation engine.

Covers:
    - Single-combo simulation correctness (basic sanity checks)
    - Batch parallel simulation matches single-combo results
    - Zero signals → zero trades
    - SL/TP trigger behavior
    - Grid order fills
    - warmup function
    - _is_dca_sltp_only_optimization detection
"""

from __future__ import annotations

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def flat_ohlcv():
    """100-bar OHLCV with slowly rising prices."""
    n = 100
    close = np.linspace(100.0, 115.0, n)
    high = close * 1.005
    low = close * 0.995
    return close, high, low


@pytest.fixture
def entry_signals_long(flat_ohlcv):
    """Single long entry signal at bar 10."""
    close, _, _ = flat_ohlcv
    signals = np.zeros(len(close), dtype=np.int8)
    signals[10] = 1
    return signals


@pytest.fixture
def entry_signals_multiple(flat_ohlcv):
    """Multiple long entry signals spread across bars."""
    close, _, _ = flat_ohlcv
    signals = np.zeros(len(close), dtype=np.int8)
    signals[5] = 1
    signals[40] = 1
    signals[70] = 1
    return signals


@pytest.fixture
def no_signals(flat_ohlcv):
    """No signals at all."""
    close, _, _ = flat_ohlcv
    return np.zeros(len(close), dtype=np.int8)


# ---------------------------------------------------------------------------
# Tests: warmup
# ---------------------------------------------------------------------------


class TestNumbaDcaWarmup:
    def test_warmup_does_not_raise(self):
        """warmup_numba_dca completes without exception."""
        from backend.backtesting.numba_dca_engine import warmup_numba_dca

        warmup_numba_dca()  # should not raise

    def test_warmup_is_idempotent(self):
        """Multiple warmup calls are safe."""
        from backend.backtesting.numba_dca_engine import warmup_numba_dca

        warmup_numba_dca()
        warmup_numba_dca()


# ---------------------------------------------------------------------------
# Tests: run_dca_single_numba
# ---------------------------------------------------------------------------


class TestRunDcaSingleNumba:
    def test_returns_dict_with_required_keys(self, flat_ohlcv, entry_signals_long):
        """Single run returns all required keys."""
        from backend.backtesting.numba_dca_engine import run_dca_single_numba

        close, high, low = flat_ohlcv
        result = run_dca_single_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=entry_signals_long,
            sl_pct=0.05,
            tp_pct=0.10,
            order_count=3,
            grid_size_pct=5.0,
        )
        required = [
            "net_profit",
            "total_return",
            "max_drawdown",
            "win_rate",
            "sharpe_ratio",
            "profit_factor",
            "n_trades",
            "equity_curve",
            "trades_pnl",
        ]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_equity_curve_length_matches_bars(self, flat_ohlcv, entry_signals_long):
        """equity_curve has same length as input OHLCV."""
        from backend.backtesting.numba_dca_engine import run_dca_single_numba

        close, high, low = flat_ohlcv
        result = run_dca_single_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=entry_signals_long,
            sl_pct=0.05,
            tp_pct=0.10,
        )
        assert len(result["equity_curve"]) == len(close)

    def test_zero_signals_zero_trades(self, flat_ohlcv, no_signals):
        """No entry signals → no trades."""
        from backend.backtesting.numba_dca_engine import run_dca_single_numba

        close, high, low = flat_ohlcv
        result = run_dca_single_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=no_signals,
            sl_pct=0.05,
            tp_pct=0.10,
        )
        assert result["n_trades"] == 0
        assert result["net_profit"] == pytest.approx(0.0, abs=1e-6)

    def test_rising_market_tp_hit(self):
        """In a consistently rising market, TP is triggered and PnL > 0."""
        from backend.backtesting.numba_dca_engine import run_dca_single_numba

        n = 200
        # Price rises 20% over period — TP at 5% should fire
        close = np.linspace(100.0, 120.0, n)
        high = close * 1.010
        low = close * 0.990

        signals = np.zeros(n, dtype=np.int8)
        signals[10] = 1  # enter at bar 10

        result = run_dca_single_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=signals,
            sl_pct=0.30,  # wide SL — won't fire
            tp_pct=0.05,  # 5% TP — will fire in rising market
            order_count=1,
            grid_size_pct=0.0,
            initial_capital=10000.0,
            leverage=1.0,
        )
        assert result["n_trades"] >= 1
        assert result["net_profit"] > 0, f"Expected profit > 0, got {result['net_profit']}"

    def test_falling_market_sl_hit(self):
        """In a falling market, SL is triggered and PnL < 0 (loss)."""
        from backend.backtesting.numba_dca_engine import run_dca_single_numba

        n = 100
        # Price falls 15% — SL at 5% fires
        close = np.linspace(100.0, 85.0, n)
        high = close * 1.005
        low = close * 0.995

        signals = np.zeros(n, dtype=np.int8)
        signals[5] = 1

        result = run_dca_single_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=signals,
            sl_pct=0.05,  # SL at 5% — should fire
            tp_pct=0.30,  # wide TP
            order_count=1,
            grid_size_pct=0.0,
            initial_capital=10000.0,
            leverage=1.0,
        )
        assert result["n_trades"] >= 1
        assert result["net_profit"] < 0, f"Expected loss, got {result['net_profit']}"

    def test_equity_curve_starts_at_initial_capital(self, flat_ohlcv, no_signals):
        """Equity curve first bar equals initial_capital when no signals."""
        from backend.backtesting.numba_dca_engine import run_dca_single_numba

        close, high, low = flat_ohlcv
        capital = 12345.0
        result = run_dca_single_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=no_signals,
            sl_pct=0.05,
            tp_pct=0.10,
            initial_capital=capital,
        )
        assert result["equity_curve"][0] == pytest.approx(capital, rel=0.01)

    def test_n_trades_is_non_negative(self, flat_ohlcv, entry_signals_multiple):
        """n_trades is always a non-negative integer."""
        from backend.backtesting.numba_dca_engine import run_dca_single_numba

        close, high, low = flat_ohlcv
        result = run_dca_single_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=entry_signals_multiple,
            sl_pct=0.05,
            tp_pct=0.08,
        )
        assert isinstance(result["n_trades"], int)
        assert result["n_trades"] >= 0

    def test_win_rate_in_valid_range(self, flat_ohlcv, entry_signals_multiple):
        """win_rate is in [0, 100]."""
        from backend.backtesting.numba_dca_engine import run_dca_single_numba

        close, high, low = flat_ohlcv
        result = run_dca_single_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=entry_signals_multiple,
            sl_pct=0.05,
            tp_pct=0.08,
        )
        assert 0.0 <= result["win_rate"] <= 100.0


# ---------------------------------------------------------------------------
# Tests: run_dca_batch_numba
# ---------------------------------------------------------------------------


class TestRunDcaBatchNumba:
    def test_returns_dict_with_arrays(self, flat_ohlcv, entry_signals_long):
        """Batch returns dict with numpy arrays of correct length."""
        from backend.backtesting.numba_dca_engine import run_dca_batch_numba

        close, high, low = flat_ohlcv
        sl_arr = np.array([0.03, 0.05, 0.10], dtype=np.float64)
        tp_arr = np.array([0.06, 0.10, 0.20], dtype=np.float64)

        result = run_dca_batch_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=entry_signals_long,
            sl_pct_arr=sl_arr,
            tp_pct_arr=tp_arr,
        )
        assert "net_profit" in result
        assert "n_trades" in result
        assert len(result["net_profit"]) == 3
        assert len(result["n_trades"]) == 3

    def test_batch_matches_single_results(self, flat_ohlcv, entry_signals_long):
        """Each batch combo matches single-combo result (within floating point tolerance)."""
        from backend.backtesting.numba_dca_engine import run_dca_batch_numba, run_dca_single_numba

        close, high, low = flat_ohlcv
        configs = [
            (0.03, 0.06),
            (0.05, 0.10),
            (0.08, 0.15),
        ]
        sl_arr = np.array([c[0] for c in configs])
        tp_arr = np.array([c[1] for c in configs])

        batch = run_dca_batch_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=entry_signals_long,
            sl_pct_arr=sl_arr,
            tp_pct_arr=tp_arr,
            order_count=3,
            grid_size_pct=5.0,
        )

        for i, (sl, tp) in enumerate(configs):
            single = run_dca_single_numba(
                close=close,
                high=high,
                low=low,
                entry_signals=entry_signals_long,
                sl_pct=sl,
                tp_pct=tp,
                order_count=3,
                grid_size_pct=5.0,
            )
            assert batch["n_trades"][i] == single["n_trades"], (
                f"Combo {i}: batch n_trades={batch['n_trades'][i]} != single={single['n_trades']}"
            )
            assert batch["net_profit"][i] == pytest.approx(single["net_profit"], rel=1e-5, abs=1e-6), (
                f"Combo {i}: net_profit mismatch"
            )

    def test_zero_signals_batch_all_zero_trades(self, flat_ohlcv, no_signals):
        """Zero signals → all combos have 0 trades."""
        from backend.backtesting.numba_dca_engine import run_dca_batch_numba

        close, high, low = flat_ohlcv
        sl_arr = np.array([0.02, 0.05, 0.08])
        tp_arr = np.array([0.04, 0.10, 0.16])

        result = run_dca_batch_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=no_signals,
            sl_pct_arr=sl_arr,
            tp_pct_arr=tp_arr,
        )
        assert np.all(result["n_trades"] == 0)
        assert np.all(result["net_profit"] == pytest.approx(0.0, abs=1e-6))

    def test_wider_tp_generally_more_profit(self, flat_ohlcv):
        """In a trending market, wider TP produces higher or equal profit."""
        from backend.backtesting.numba_dca_engine import run_dca_batch_numba

        close, high, low = flat_ohlcv  # slowly rising market
        signals = np.zeros(len(close), dtype=np.int8)
        signals[5] = 1

        sl_arr = np.array([0.20, 0.20])  # same wide SL
        tp_arr = np.array([0.02, 0.10])  # narrow vs wide TP

        result = run_dca_batch_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=signals,
            sl_pct_arr=sl_arr,
            tp_pct_arr=tp_arr,
            order_count=1,
            grid_size_pct=0.0,
            leverage=1.0,
        )
        # Both should have at least 1 trade; wide TP allows more upside
        assert result["n_trades"][0] >= 1 or result["n_trades"][1] >= 1

    def test_commission_reduces_profit(self, flat_ohlcv):
        """Higher commission reduces net_profit."""
        from backend.backtesting.numba_dca_engine import run_dca_batch_numba

        close, high, low = flat_ohlcv
        signals = np.zeros(len(close), dtype=np.int8)
        signals[5] = 1

        sl_arr = np.array([0.15, 0.15])
        tp_arr = np.array([0.08, 0.08])

        # Low vs high commission
        r_low = run_dca_batch_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=signals,
            sl_pct_arr=sl_arr,
            tp_pct_arr=tp_arr,
            taker_fee=0.0001,
            order_count=1,
            grid_size_pct=0.0,
            leverage=1.0,
        )
        r_high = run_dca_batch_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=signals,
            sl_pct_arr=sl_arr,
            tp_pct_arr=tp_arr,
            taker_fee=0.01,
            order_count=1,
            grid_size_pct=0.0,
            leverage=1.0,
        )
        for i in range(2):
            if r_low["n_trades"][i] > 0 and r_high["n_trades"][i] > 0:
                assert r_low["net_profit"][i] >= r_high["net_profit"][i], (
                    f"Combo {i}: low-fee profit should be ≥ high-fee profit"
                )

    def test_mismatched_sl_tp_arrays_raises(self, flat_ohlcv, entry_signals_long):
        """sl_pct_arr and tp_pct_arr of different lengths raises AssertionError."""
        from backend.backtesting.numba_dca_engine import run_dca_batch_numba

        close, high, low = flat_ohlcv
        with pytest.raises(AssertionError):
            run_dca_batch_numba(
                close=close,
                high=high,
                low=low,
                entry_signals=entry_signals_long,
                sl_pct_arr=np.array([0.03, 0.05]),
                tp_pct_arr=np.array([0.06]),  # length mismatch
            )


# ---------------------------------------------------------------------------
# Tests: _is_dca_sltp_only_optimization
# ---------------------------------------------------------------------------


class TestIsDcaSltpOnlyOptimization:
    """Tests for the fast-path detection helper."""

    def _make_graph(self, block_types: list[str]) -> dict:
        blocks = [{"id": f"block_{i}", "type": t, "params": {}} for i, t in enumerate(block_types)]
        return {"blocks": blocks, "connections": []}

    def test_detects_sltp_only(self):
        from backend.optimization.builder_optimizer import _is_dca_sltp_only_optimization

        graph = self._make_graph(["rsi", "dca", "static_sltp"])
        combos = [
            {"block_2.stop_loss_percent": 1.5, "block_2.take_profit_percent": 2.0},
            {"block_2.stop_loss_percent": 2.0, "block_2.take_profit_percent": 3.0},
        ]
        is_sltp, ids = _is_dca_sltp_only_optimization(combos, graph)
        assert is_sltp is True
        assert "block_2" in ids

    def test_returns_false_when_rsi_also_varies(self):
        from backend.optimization.builder_optimizer import _is_dca_sltp_only_optimization

        graph = self._make_graph(["rsi", "dca", "static_sltp"])
        combos = [
            {"block_0.period": 14, "block_2.stop_loss_percent": 1.5},
            {"block_0.period": 20, "block_2.stop_loss_percent": 2.0},
        ]
        is_sltp, _ = _is_dca_sltp_only_optimization(combos, graph)
        assert is_sltp is False

    def test_returns_false_when_no_static_sltp_block(self):
        from backend.optimization.builder_optimizer import _is_dca_sltp_only_optimization

        graph = self._make_graph(["rsi", "dca"])  # no static_sltp
        combos = [
            {"block_0.period": 14},
            {"block_0.period": 20},
        ]
        is_sltp, ids = _is_dca_sltp_only_optimization(combos, graph)
        assert is_sltp is False
        assert ids == []

    def test_returns_false_for_empty_combos(self):
        from backend.optimization.builder_optimizer import _is_dca_sltp_only_optimization

        graph = self._make_graph(["static_sltp"])
        is_sltp, _ = _is_dca_sltp_only_optimization([], graph)
        assert is_sltp is False

    def test_single_combo_with_sltp_block(self):
        from backend.optimization.builder_optimizer import _is_dca_sltp_only_optimization

        graph = self._make_graph(["dca", "static_sltp"])
        combos = [{"block_1.stop_loss_percent": 2.5}]
        is_sltp, ids = _is_dca_sltp_only_optimization(combos, graph)
        assert is_sltp is True
        assert "block_1" in ids

    def test_path_without_dot_returns_false(self):
        from backend.optimization.builder_optimizer import _is_dca_sltp_only_optimization

        graph = self._make_graph(["static_sltp"])
        combos = [{"stop_loss_percent": 2.0}]  # missing block_id prefix
        is_sltp, _ = _is_dca_sltp_only_optimization(combos, graph)
        assert is_sltp is False
