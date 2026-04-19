"""
Debug final cash vs expected
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

print(f"Numba trades: {n_trades}")
print(f"Numba final equity: {equity[-1]:.2f}")

# Calculate sum of PnLs
pnls = trades[:n_trades, 5]
total_pnl = np.sum(pnls)
print(f"Sum of PnLs: {total_pnl:.2f}")
print(f"Expected equity (10000 + pnl): {10000 + total_pnl:.2f}")
print(f"Difference: {equity[-1] - (10000 + total_pnl):.2f}")

# Check if last position is still open
print("\nLast equity values:")
for i in range(-5, 0):
    print(f"  equity[{504+i}] = {equity[i]:.2f}")
