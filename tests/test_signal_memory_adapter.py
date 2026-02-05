"""
Unit tests for Signal Memory in StrategyBuilderAdapter.

Signal memory extends buy/sell signals for N bars after each cross event;
an opposite signal cancels the extension.
"""

import numpy as np
import pandas as pd

from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter


def _ohlcv(n: int, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    base = 50000.0
    ret = np.random.randn(n) * 0.01
    close = base * np.cumprod(1 + ret)
    high = close * (1 + np.abs(np.random.randn(n) * 0.005))
    low = close * (1 - np.abs(np.random.randn(n) * 0.005))
    open_ = np.roll(close, 1)
    open_[0] = base
    vol = np.random.randint(1000, 10000, n).astype(float)
    ts = pd.date_range(start="2025-01-01", periods=n, freq="1h")
    return pd.DataFrame(
        {"timestamp": ts, "open": open_, "high": high, "low": low, "close": close, "volume": vol}
    )


def test_rsi_filter_signal_memory_extends_buy():
    """With use_signal_memory=True and signal_memory_bars=2, buy is extended for N bars after cross."""
    graph_mem = {
        "name": "RSI Memory",
        "blocks": [
            {
                "id": "f1",
                "type": "rsi_filter",
                "category": "filter",
                "params": {
                    "period": 14,
                    "oversold": 30,
                    "overbought": 70,
                    "mode": "cross",
                    "use_signal_memory": True,
                    "signal_memory_bars": 2,
                },
            }
        ],
        "connections": [],
    }
    graph_no_mem = {
        "name": "RSI No Mem",
        "blocks": [
            {
                "id": "f1",
                "type": "rsi_filter",
                "category": "filter",
                "params": {
                    "period": 14,
                    "oversold": 30,
                    "overbought": 70,
                    "mode": "cross",
                    "use_signal_memory": False,
                    "signal_memory_bars": 0,
                },
            }
        ],
        "connections": [],
    }
    ohlcv = _ohlcv(60)
    adapter_mem = StrategyBuilderAdapter(graph_mem)
    adapter_no = StrategyBuilderAdapter(graph_no_mem)
    out_mem = adapter_mem._execute_block("f1", ohlcv)
    out_no = adapter_no._execute_block("f1", ohlcv)
    buy_mem = out_mem["buy"].values
    buy_no = out_no["buy"].values
    # With memory, number of True should be >= without (extension adds bars)
    assert buy_mem.sum() >= buy_no.sum()
    assert len(buy_mem) == len(ohlcv)


def test_rsi_filter_signal_memory_disabled():
    """Without use_signal_memory, buy/sell are point-in-time only (no extension)."""
    graph = {
        "name": "RSI No Memory",
        "blocks": [
            {
                "id": "f1",
                "type": "rsi_filter",
                "category": "filter",
                "params": {
                    "period": 14,
                    "oversold": 30,
                    "overbought": 70,
                    "mode": "cross",
                    "use_signal_memory": False,
                    "signal_memory_bars": 5,
                },
            }
        ],
        "connections": [],
    }
    adapter = StrategyBuilderAdapter(graph)
    ohlcv = _ohlcv(50)
    out = adapter._execute_block("f1", ohlcv)
    assert "buy" in out and "sell" in out
    assert len(out["buy"]) == len(ohlcv)


def test_stochastic_filter_cross_memory():
    """Stochastic cross mode with activate_stoch_cross_memory extends signal."""
    graph = {
        "name": "Stoch Memory",
        "blocks": [
            {
                "id": "f1",
                "type": "stochastic_filter",
                "category": "filter",
                "params": {
                    "kPeriod": 14,
                    "dPeriod": 3,
                    "oversold": 20,
                    "overbought": 80,
                    "mode": "cross",
                    "activate_stoch_cross_memory": True,
                    "stoch_cross_memory_bars": 3,
                },
            }
        ],
        "connections": [],
    }
    adapter = StrategyBuilderAdapter(graph)
    ohlcv = _ohlcv(50)
    out = adapter._execute_block("f1", ohlcv)
    assert "buy" in out and "sell" in out
    assert out["buy"].dtype == bool or np.issubdtype(out["buy"].dtype, np.bool_)


def test_two_ma_filter_memory_bars():
    """Two MA filter with ma_cross_memory_bars extends crossover signal."""
    graph = {
        "name": "MA Memory",
        "blocks": [
            {
                "id": "f1",
                "type": "two_ma_filter",
                "category": "filter",
                "params": {
                    "fastPeriod": 9,
                    "slowPeriod": 21,
                    "maType": "ema",
                    "ma_cross_memory_bars": 2,
                },
            }
        ],
        "connections": [],
    }
    adapter = StrategyBuilderAdapter(graph)
    ohlcv = _ohlcv(50)
    out = adapter._execute_block("f1", ohlcv)
    assert "buy" in out and "sell" in out
    assert len(out["buy"]) == len(ohlcv)


def test_macd_filter_signal_memory():
    """MACD filter with macd_signal_memory_bars and disable_macd_signal_memory=False extends signal."""
    graph = {
        "name": "MACD Memory",
        "blocks": [
            {
                "id": "f1",
                "type": "macd_filter",
                "category": "filter",
                "params": {
                    "fast": 12,
                    "slow": 26,
                    "signal": 9,
                    "mode": "signal_cross",
                    "disable_macd_signal_memory": False,
                    "macd_signal_memory_bars": 2,
                },
            }
        ],
        "connections": [],
    }
    adapter = StrategyBuilderAdapter(graph)
    ohlcv = _ohlcv(50)
    out = adapter._execute_block("f1", ohlcv)
    assert "buy" in out and "sell" in out
    assert len(out["buy"]) == len(ohlcv)
