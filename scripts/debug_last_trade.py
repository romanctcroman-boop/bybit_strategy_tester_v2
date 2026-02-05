"""
Debug last trade timing
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3

import numpy as np
import pandas as pd

# Load data
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
df = pd.read_sql("""
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    AND open_time >= 1735689600000
    AND open_time < 1737504000000
    ORDER BY open_time ASC
""", conn)
conn.close()

df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
df.set_index('open_time', inplace=True)

# ============ NUMBA ============
from backend.backtesting.numba_engine import simulate_trades_numba
from backend.backtesting.strategies import RSIStrategy

strategy = RSIStrategy(params={"period": 14, "overbought": 70, "oversold": 30})
signals = strategy.generate_signals(df)

close = df['close'].values.astype(np.float64)
high = df['high'].values.astype(np.float64)
low = df['low'].values.astype(np.float64)

long_entries = signals.entries.values.astype(np.bool_)
long_exits = signals.exits.values.astype(np.bool_)
short_entries = signals.short_entries.values.astype(np.bool_)
short_exits = signals.short_exits.values.astype(np.bool_)

trades, equity, _, n_trades = simulate_trades_numba(
    close, high, low,
    long_entries, long_exits,
    short_entries, short_exits,
    10000.0, 1.0, 0.0004, 0.0001,
    0.03, 0.06, 1.0, 2
)

print(f"Total bars: {len(close)}")
print(f"Numba trades: {n_trades}")

# Check last trades
print("\nLast 5 trades:")
for i in range(max(0, n_trades-5), n_trades):
    entry_idx = int(trades[i, 0])
    exit_idx = int(trades[i, 1])
    is_long = trades[i, 2] == 1.0
    pnl = trades[i, 5]
    print(f"  Trade {i+1}: entry={entry_idx}, exit={exit_idx}, is_long={is_long}, pnl={pnl:.2f}")

# Check last signal entries
print("\nLast entries/exits in signals:")
for i in range(495, 504):
    print(f"  Bar {i}: long_entry={long_entries[i]}, long_exit={long_exits[i]}, short_entry={short_entries[i]}, short_exit={short_exits[i]}, close={close[i]:.2f}")
