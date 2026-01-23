"""
Check actual signals in Fallback
"""
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')

import numpy as np
import pandas as pd
import sqlite3

from backend.backtesting.strategies import RSIStrategy

# Load data
conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
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

strategy = RSIStrategy(params={"period": 14, "overbought": 70, "oversold": 30})
signals = strategy.generate_signals(df)

print("Signals type:", type(signals.short_entries))
print("\nLast 10 entries/exits:")
for i in range(494, 504):
    le = signals.entries.iloc[i] if hasattr(signals.entries, 'iloc') else signals.entries.values[i]
    lx = signals.exits.iloc[i] if hasattr(signals.exits, 'iloc') else signals.exits.values[i]
    se = signals.short_entries.iloc[i] if hasattr(signals.short_entries, 'iloc') else signals.short_entries.values[i]
    sx = signals.short_exits.iloc[i] if hasattr(signals.short_exits, 'iloc') else signals.short_exits.values[i]
    print(f"  Bar {i}: long_entry={le}, long_exit={lx}, short_entry={se}, short_exit={sx}")

# Check actual numpy values
print("\nNumpy array values:")
long_entries = signals.entries.values.astype(np.bool_)
short_entries = signals.short_entries.values.astype(np.bool_)
for i in range(494, 504):
    print(f"  Bar {i}: long_entry={long_entries[i]}, short_entry={short_entries[i]}")
