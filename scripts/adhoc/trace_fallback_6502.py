"""Trace Fallback execution around bar 6502"""

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
entry_bar_46 = 6320  # Bar where open = 89596.40
entry_price_46 = data[entry_bar_46, 0]  # 89596.40
tp_price_46 = entry_price_46 * 1.015
sl_price_46 = entry_price_46 * (1 - 0.03)

print("Trade 46:")
print(f"  Entry bar: {entry_bar_46}, Entry price: {entry_price_46:.2f}")
print(f"  TP price: {tp_price_46:.2f}")
print(f"  SL price: {sl_price_46:.2f}")
print()

# Check bars 6500-6503
print("=== Bars 6500-6503 ===")
for i in range(6500, 6504):
    o, h, l, c = data[i]
    tp_hit = h >= tp_price_46
    sl_hit = l <= sl_price_46
    le = long_entries[i]
    se = short_entries[i]

    print(f"Bar {i}: O={o:.2f} H={h:.2f} L={l:.2f} C={c:.2f}")
    print(f"  TP hit: {tp_hit} (need H >= {tp_price_46:.2f})")
    print(f"  SL hit: {sl_hit} (need L <= {sl_price_46:.2f})")
    print(f"  LONG signal: {le}, SHORT signal: {se}")
    print()

# Trace Fallback logic step by step
print("=" * 60)
print("=== TRACE FALLBACK LOGIC ===")
print("=" * 60)

print("""
At start of bar 6320 (signal bar):
  - in_long = False
  - long_entries[6319] was True (signal at 6319)

But wait, signal bar is actually 6319 if entry is at bar 6320.
Let me verify...
""")

# Find which bar has the signal for entry at 6320
print("Checking signal at bar 6319:")
print(f"  long_entries[6319] = {long_entries[6319]}")
print(f"  open[6320] = {data[6320, 0]:.2f}")

print("\nChecking signal at bar 6320:")
print(f"  long_entries[6320] = {long_entries[6320]}")
print(f"  open[6321] = {data[6321, 0]:.2f}")

# Trade 46 entry is 89596.40, let's find which bar has this as open
for i in range(6310, 6325):
    if abs(data[i, 0] - 89596.40) < 0.1:
        print(f"\nBar with open 89596.40 is bar {i}")
        print(f"  Signal must be at bar {i - 1}")
        print(f"  long_entries[{i - 1}] = {long_entries[i - 1]}")
