"""Detailed analysis of Trade 46 exit and potential Trade 47 entry"""

import os

os.chdir(str(Path(__file__).resolve().parents[1]))
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pathlib import Path

import numpy as np
import pandas as pd

# Load data from d:/TV
tv_data_dir = Path("d:/TV")
df = pd.read_csv(tv_data_dir / "BYBIT_BTCUSDT.P_15m_full.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values("timestamp").reset_index(drop=True)

# Load TV signals
long_entries = np.load(tv_data_dir / "long_signals.npy")
short_entries = np.load(tv_data_dir / "short_signals.npy")

data = df[["open", "high", "low", "close"]].values

# Trade 46 parameters
# Entry price = 89596.40, Exit price = 90940.35 (TP)
entry_price_46 = 89596.40
tp_price_46 = entry_price_46 * 1.015  # 90940.35

# Find entry bar (bar where open = entry price)
entry_bar_46 = None
for i in range(len(data)):
    if abs(data[i, 0] - entry_price_46) < 0.1:
        entry_bar_46 = i
        print(f"Trade 46 entry at bar {i}:")
        print(f"  Open = {data[i, 0]:.2f}")
        print(f"  TP price = {tp_price_46:.2f}")
        break

# Find where TP hits
for i in range(entry_bar_46, len(data)):
    high = data[i, 1]
    if high >= tp_price_46:
        print(f"\nTrade 46 TP hits at bar {i}:")
        print(
            f"  O={data[i, 0]:.2f} H={data[i, 1]:.2f} L={data[i, 2]:.2f} C={data[i, 3]:.2f}"
        )
        print(f"  Timestamp: {df.iloc[i]['timestamp']}")
        print(f"  High {high:.2f} >= TP {tp_price_46:.2f}")

        # Check signals at this bar
        print(f"\n  Signals at bar {i}:")
        print(f"    long_entries[{i}] = {long_entries[i]}")
        print(f"    short_entries[{i}] = {short_entries[i]}")

        if long_entries[i]:
            next_open = data[i + 1, 0] if i + 1 < len(data) else 0
            print(
                f"    → LONG signal! Entry would be at next bar open = {next_open:.2f}"
            )
            print("    → This is Trade 47 in Numba (entry=90810.90)")

        # Check signals around this bar
        print(f"\n  Signals in bars {i - 5} to {i + 10}:")
        for j in range(max(0, i - 5), min(len(data), i + 15)):
            le = long_entries[j] if j < len(long_entries) else False
            se = short_entries[j] if j < len(short_entries) else False
            if le or se:
                direction = "LONG" if le else "SHORT"
                next_open = data[j + 1, 0] if j + 1 < len(data) else 0
                print(f"    Bar {j}: {direction} signal, next open = {next_open:.2f}")

        break

# Now understand why Fallback skips the LONG at 6502
print("\n" + "=" * 60)
print("=== WHY FALLBACK SKIPS LONG AT 6502 ===")
print("=" * 60)

# The key insight is the order of operations in the main loop:
# 1. Execute pending exits (from previous bar)
# 2. Accumulate MFE/MAE
# 3. Check exit conditions (sets pending_exit for next bar)
# 4. Check entry conditions

# For Trade 46:
# - At bar 6501 or 6502: exit condition detected (TP), pending_long_exit = True
# - At same bar: in_long = False (freed)
# - At same bar: entry condition checked - but is there a signal?

print("\nThe key is when exit vs entry happens:")
print("  1. At bar X: TP condition detected → pending_long_exit=True, in_long=False")
print("  2. At bar X: Entry checked → if signal exists, new position opened")
print("  3. At bar X+1: Execute pending exit (record Trade 46)")
print("\nBut the condition check uses: `i < n - 2` (skip last 2 bars)")
print("Let's check bar indices...")
print(f"\nTotal bars: {len(data)}")
print(f"n - 2 = {len(data) - 2}")
