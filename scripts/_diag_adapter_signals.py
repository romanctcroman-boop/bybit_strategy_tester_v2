"""Diagnostic: count signals from StrategyBuilderAdapter with exact MACD_03 params"""

import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import sqlite3

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput
from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter

# Load OHLCV from bybit_kline_audit table (same as compare_macd_tv.py)
conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
START_MS = int(pd.Timestamp("2025-01-01", tz="UTC").timestamp() * 1000)
END_MS = int(pd.Timestamp("2026-03-01", tz="UTC").timestamp() * 1000)
df = pd.read_sql(
    f"SELECT open_time, open_price AS open, high_price AS high, low_price AS low, close_price AS close, volume"
    f" FROM bybit_kline_audit WHERE symbol='ETHUSDT' AND interval='30'"
    f" AND open_time >= {START_MS} AND open_time <= {END_MS}"
    f" ORDER BY open_time",
    conn,
)
conn.close()
df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df.set_index("open_time", inplace=True)
for col in ["open", "high", "low", "close", "volume"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")
ohlcv = df
start = ohlcv.index[0]
end = ohlcv.index[-1]
print(f"OHLCV bars: {len(ohlcv)} ({ohlcv.index[0]} to {ohlcv.index[-1]})")


def run_with_memory(disable_memory: bool, memory_bars: int = 5):
    graph = {
        "blocks": [
            {
                "id": "main_strategy",
                "type": "strategy",
                "category": "main",
                "name": "Strategy",
                "isMain": True,
                "params": {},
                "x": 0,
                "y": 0,
            },
            {
                "id": "macd_block",
                "type": "macd",
                "category": "indicator",
                "name": "MACD",
                "isMain": False,
                "params": {
                    "fast_period": 14,
                    "slow_period": 15,
                    "signal_period": 9,
                    "use_macd_cross_zero": True,
                    "opposite_macd_cross_zero": True,
                    "macd_cross_zero_level": 0,
                    "use_macd_cross_signal": True,
                    "signal_only_if_macd_positive": False,
                    "opposite_macd_cross_signal": True,
                    "disable_signal_memory": disable_memory,
                    "signal_memory_bars": memory_bars,
                },
                "x": 0,
                "y": 0,
            },
            {
                "id": "sltp_block",
                "type": "static_sltp",
                "category": "exit",
                "name": "Static SL/TP",
                "isMain": False,
                "params": {
                    "take_profit_percent": 6.6,
                    "stop_loss_percent": 13.2,
                    "sl_type": "average_price",
                },
                "x": 0,
                "y": 0,
            },
        ],
        "connections": [
            {
                "id": "c1",
                "source": {"blockId": "macd_block", "portId": "long"},
                "target": {"blockId": "main_strategy", "portId": "entry_long"},
                "type": "condition",
            },
            {
                "id": "c2",
                "source": {"blockId": "macd_block", "portId": "short"},
                "target": {"blockId": "main_strategy", "portId": "entry_short"},
                "type": "condition",
            },
            {
                "id": "c3",
                "source": {"blockId": "sltp_block", "portId": "config"},
                "target": {"blockId": "main_strategy", "portId": "sl_tp"},
                "type": "config",
            },
        ],
        "market_type": "linear",
        "direction": "both",
    }
    adapter = StrategyBuilderAdapter(graph)
    result_signals = adapter.generate_signals(ohlcv)
    # SignalResult has .entries, .exits, .short_entries, .short_exits as boolean Series
    long_entries_s = result_signals.entries.fillna(False).astype(bool)
    short_entries_s = (
        result_signals.short_entries.fillna(False).astype(bool)
        if result_signals.short_entries is not None
        else pd.Series(False, index=ohlcv.index)
    )
    long_exits_s = (
        result_signals.exits.fillna(False).astype(bool)
        if result_signals.exits is not None
        else pd.Series(False, index=ohlcv.index)
    )
    short_exits_s = (
        result_signals.short_exits.fillna(False).astype(bool)
        if result_signals.short_exits is not None
        else pd.Series(False, index=ohlcv.index)
    )
    long_count = long_entries_s.sum()
    short_count = short_entries_s.sum()

    # Run backtest
    inp = BacktestInput(
        candles=ohlcv,
        long_entries=long_entries_s.values,
        long_exits=long_exits_s.values,
        short_entries=short_entries_s.values,
        short_exits=short_exits_s.values,
        symbol="ETHUSDT",
        interval="30",
        initial_capital=10000.0,
        position_size=0.1,
        use_fixed_amount=False,
        leverage=10,
        stop_loss=0.132,
        take_profit=0.066,
        taker_fee=0.0007,
        slippage=0.0,
    )
    engine = FallbackEngineV4()
    bt_result = engine.run(inp)
    trades = bt_result.metrics.total_trades
    wr = bt_result.metrics.win_rate * 100
    net = bt_result.metrics.net_profit / 10000 * 100  # pct of initial capital

    mem_str = "memory=OFF" if disable_memory else f"memory=ON(bars={memory_bars})"
    print(f"[{mem_str}] raw signals: L={long_count} S={short_count} | trades={trades}, WR={wr:.1f}%, net={net:.2f}%")
    return trades


print("\n--- Testing with exact DB params (disable_signal_memory=False, memory_bars=5) ---")
t1 = run_with_memory(disable_memory=False, memory_bars=5)

print("\n--- Testing with memory OFF (disable_signal_memory=True) ---")
t2 = run_with_memory(disable_memory=True, memory_bars=5)

print("\n--- Testing with memory OFF (disable_signal_memory=True, memory_bars=0) ---")
t3 = run_with_memory(disable_memory=True, memory_bars=0)

print(f"\nSummary: memory_ON={t1} trades, memory_OFF={t2} trades, memory_OFF_bars0={t3} trades")
print("TV reference: 42 trades")
print("DB stored: 62 trades")
