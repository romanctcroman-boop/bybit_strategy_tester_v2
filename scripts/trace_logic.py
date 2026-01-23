"""
Direct trace of bars 498-501 in both engines
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

close = df['close'].values.astype(np.float64)
high = df['high'].values.astype(np.float64)
low = df['low'].values.astype(np.float64)

long_entries = signals.entries.values.astype(np.bool_)
long_exits = signals.exits.values.astype(np.bool_)
short_entries = signals.short_entries.values.astype(np.bool_)
short_exits = signals.short_exits.values.astype(np.bool_)

# Simulate bars 480-504 manually to trace what happens
print("Manual simulation trace:")
print("=" * 80)

# State before Trade 20
# Trade 20: entry=480, exit=498, is_long=True
# Starting from bar 480 with a Long position

# Let's trace from bar 495
for i in range(495, 504):
    le = long_entries[i]
    lx = long_exits[i]
    se = short_entries[i]
    sx = short_exits[i]
    
    print(f"\nBar {i}: close={close[i]:.2f}")
    print(f"  Signals: long_entry={le}, long_exit={lx}, short_entry={se}, short_exit={sx}")
    
    # At bar 498: We are in Long position (Trade 20)
    if i == 498:
        print(f"  --> This bar: Long position exits (long_exit=True)")
        print(f"  --> But short_entry is also True - does new position open?")
        
    if i == 499:
        print(f"  --> Bar 499: position=0 after exit on 498")
        print(f"  --> short_entry={se} - should we enter?")

print("\n" + "=" * 80)
print("The question: When Numba exits on bar 498 (inside 'elif position > 0')...")
print("Does it then check entry on the SAME bar 498 or wait until bar 499?")
print("\nAnswer: It waits until bar 499 because 'if position == 0' and 'elif position > 0'")
print("are mutually exclusive in the same iteration.")
print("\nBut on bar 499, short_entry is True and position is 0, so Numba enters!")
