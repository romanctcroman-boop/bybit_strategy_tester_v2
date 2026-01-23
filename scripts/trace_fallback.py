"""
Trace Fallback engine directly
"""
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')

import numpy as np
import pandas as pd
import sqlite3

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

from backend.backtesting.strategies import RSIStrategy
strategy = RSIStrategy(params={"period": 14, "overbought": 70, "oversold": 30})
signals = strategy.generate_signals(df)

# Get signal arrays as Fallback would
long_entries = signals.entries
long_exits = signals.exits
short_entries = signals.short_entries
short_exits = signals.short_exits

direction = "both"

# Simulate just like Fallback (simplified)
position = 0.0
n_bars = len(df)
close = df['close'].values

# Fast-forward to bar 480 (Trade 20 entry)
position = 1.0  # Simulate being in Long position

trades = []

for i in range(480, n_bars):
    if position == 0:
        # Long entry
        if direction in ("long", "both") and long_entries.iloc[i]:
            position = 1.0
            trades.append(("ENTRY", i, "LONG"))
            print(f"Bar {i}: LONG ENTRY")
        # Short entry
        elif direction in ("short", "both") and short_entries is not None and short_entries.iloc[i]:
            position = 1.0
            trades.append(("ENTRY", i, "SHORT"))
            print(f"Bar {i}: SHORT ENTRY (short_entries[{i}]={short_entries.iloc[i]})")
    
    elif position > 0:
        # For simplicity, check signal exit for Long
        should_exit = False
        if long_exits is not None and long_exits.iloc[i]:
            should_exit = True
            print(f"Bar {i}: LONG EXIT (long_exits[{i}]={long_exits.iloc[i]})")
        
        if should_exit:
            position = 0.0
            trades.append(("EXIT", i, "LONG"))

print(f"\nTotal trades: {len(trades)}")
print(f"Last 5 events: {trades[-5:] if len(trades) >= 5 else trades}")
