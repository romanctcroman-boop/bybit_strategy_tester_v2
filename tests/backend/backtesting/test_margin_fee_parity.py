"""Tests for margin conservation, equity formula, and fee accuracy."""

from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig, StrategyType

UTC = timezone.utc


def _cfg(**kw):
    base = {
        "symbol": "BTCUSDT",
        "interval": "15",
        "start_date": datetime(2025, 6, 1, tzinfo=UTC),
        "end_date": datetime(2025, 6, 2, tzinfo=UTC),
        "strategy_type": StrategyType.SMA_CROSSOVER,
        "strategy_params": {"fast_period": 2, "slow_period": 5},
        "initial_capital": 10000.0,
        "taker_fee": 0.0007,
        "maker_fee": 0.0002,
        "leverage": 10.0,
        "position_size": 1.0,
        "slippage": 0.0,
        "direction": "long",
    }
    base.update(kw)
    return BacktestConfig(**base)


def _ohlcv(prices):
    arr = np.asarray(prices, dtype=np.float64)
    idx = pd.date_range("2025-06-01", periods=len(arr), freq="15min", tz="UTC")
    return pd.DataFrame(
        {"open": arr, "high": arr * 1.005, "low": arr * 0.995, "close": arr, "volume": 1000.0},
        index=idx,
    )


def _make_signals(ohlcv, longs=(), shorts=()):
    """Build a SignalResult-compatible SimpleNamespace for _run_fallback."""
    n = len(ohlcv)
    idx = ohlcv.index
    le = pd.Series(np.zeros(n, dtype=bool), index=idx)
    se = pd.Series(np.zeros(n, dtype=bool), index=idx)
    lx = pd.Series(np.zeros(n, dtype=bool), index=idx)
    sx = pd.Series(np.zeros(n, dtype=bool), index=idx)
    for i in longs:
        le.iloc[i] = True
    for i in shorts:
        se.iloc[i] = True
    return SimpleNamespace(
        entries=le,
        exits=lx,
        long_entries=le,
        long_exits=lx,
        short_entries=se,
        short_exits=sx,
        entry_sizes=None,
        short_entry_sizes=None,
        extra_data=None,
    )


def _run(cfg, prices, longs=(), shorts=()):
    ohlcv = _ohlcv(prices)
    signals = _make_signals(ohlcv, longs=longs, shorts=shorts)
    eng = BacktestEngine()
    return eng._run_fallback(config=cfg, ohlcv=ohlcv, signals=signals)


class TestMarginConservation:
    def test_zero_fees(self):
        cfg = _cfg(taker_fee=0.0, leverage=10.0)
        r = _run(cfg, [100] * 10, longs=[1])
        pnl = sum(t.pnl for t in r.trades)
        eq = r.equity_curve.equity
        assert eq[-1] == pytest.approx(10000.0 + pnl, rel=1e-6)

    @pytest.mark.parametrize("lev", [1.0, 5.0, 10.0, 50.0])
    def test_across_leverage(self, lev):
        cfg = _cfg(taker_fee=0.0, leverage=lev)
        prices = [100, 100, 105, 110, 110, 110, 110, 110, 110, 110]
        r = _run(cfg, prices, longs=[1])
        pnl = sum(t.pnl for t in r.trades)
        eq = r.equity_curve.equity
        assert eq[-1] == pytest.approx(10000.0 + pnl, rel=1e-6)

    def test_with_fees(self):
        cfg = _cfg(taker_fee=0.0007, leverage=10.0)
        prices = [100, 100, 105, 110, 115, 115, 115, 115, 115, 115]
        r = _run(cfg, prices, longs=[1])
        pnl = sum(t.pnl for t in r.trades)
        eq = r.equity_curve.equity
        assert eq[-1] == pytest.approx(10000.0 + pnl, rel=1e-4)


class TestEquityFormula:
    def test_not_inflated_by_leverage(self):
        cfg = _cfg(taker_fee=0.0, leverage=10.0)
        r = _run(cfg, [100] * 10, longs=[0])
        eq = r.equity_curve.equity
        for i, val in enumerate(eq[1:], 1):
            assert val < 20000, f"Bar {i}: eq={val} inflated"
            assert val == pytest.approx(10000.0, rel=0.01)

    def test_bounded_with_profit(self):
        cfg = _cfg(taker_fee=0.0, leverage=5.0)
        prices = [100, 102, 104, 106, 108, 110, 110, 110, 110, 110]
        r = _run(cfg, prices, longs=[0])
        eq = r.equity_curve.equity
        for val in eq:
            assert val <= 20000, f"Equity {val} too high"


class TestFeeRecording:
    def test_exact_not_double_exit(self):
        cfg = _cfg(taker_fee=0.0007, leverage=1.0)
        prices = [100, 100, 105, 110, 115, 120, 120, 120, 120, 120]
        r = _run(cfg, prices, longs=[1])
        if r.trades:
            t = r.trades[0]
            exact = t.size * t.entry_price * 0.0007 + t.size * t.exit_price * 0.0007
            assert t.fees == pytest.approx(exact, rel=0.02)

    def test_large_price_move(self):
        cfg = _cfg(taker_fee=0.001, leverage=1.0)
        prices = [100, 100, 110, 120, 130, 140, 125, 125, 125, 125]
        r = _run(cfg, prices, longs=[1])
        if r.trades:
            t = r.trades[0]
            exact = t.size * t.entry_price * 0.001 + t.size * t.exit_price * 0.001
            assert t.fees == pytest.approx(exact, rel=0.02)


class TestMarginReconstructionError:
    def test_no_leak_flat(self):
        cfg = _cfg(taker_fee=0.0007, leverage=10.0)
        r = _run(cfg, [100] * 10, longs=[0])
        if r.trades:
            t = r.trades[0]
            assert t.pnl < 0
            assert t.pnl > -200
            eq = r.equity_curve.equity
            assert eq[-1] == pytest.approx(10000.0 + t.pnl, rel=1e-4)

    def test_leak_math(self):
        old = 10000.0 / (1 + 0.0007)
        leak = 10000.0 - old
        assert leak == pytest.approx(6.995, rel=0.01)

    @pytest.mark.parametrize("fee", [0.0001, 0.0004, 0.0007, 0.001, 0.005])
    def test_no_leak_various_fees(self, fee):
        cfg = _cfg(taker_fee=fee, leverage=10.0)
        r = _run(cfg, [100] * 10, longs=[0])
        if r.trades:
            eq = r.equity_curve.equity
            assert eq[-1] == pytest.approx(10000.0 + r.trades[0].pnl, rel=1e-4)


class TestEndOfDataClose:
    def test_margin_correct(self):
        cfg = _cfg(taker_fee=0.0007, leverage=10.0)
        prices = [100, 102, 104, 106, 108, 110, 112, 114, 116, 118]
        r = _run(cfg, prices, longs=[0])
        assert r.trades[-1].exit_comment == "end_of_backtest"
        pnl = sum(t.pnl for t in r.trades)
        eq = r.equity_curve.equity
        assert eq[-1] == pytest.approx(10000.0 + pnl, rel=1e-4)

    def test_fees_exact(self):
        cfg = _cfg(taker_fee=0.001, leverage=1.0)
        prices = [100, 100, 105, 110, 115, 120, 120, 120, 120, 120]
        r = _run(cfg, prices, longs=[1])
        if r.trades:
            t = r.trades[0]
            if t.exit_comment == "end_of_backtest":
                exact = t.size * t.entry_price * 0.001 + t.size * t.exit_price * 0.001
                assert t.fees == pytest.approx(exact, rel=0.02)
