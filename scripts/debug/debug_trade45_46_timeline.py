"""Understand Trade 45 SHORT and Trade 46 LONG timeline"""

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

# Trade 45: SHORT entry=91800.00 exit=90423.00 TAKE_PROFIT
# Trade 46: LONG entry=89596.40 exit=90940.35 TAKE_PROFIT

print("=== TRADE 45: SHORT ===")
# Find entry bar for SHORT at 91800.00
for i in range(len(data)):
    if abs(data[i, 0] - 91800.00) < 0.1:
        print(f"Trade 45 entry at bar {i}:")
        print(f"  Open = {data[i, 0]:.2f}")
        # Signal was at bar i-1
        print(
            f"  Signal at bar {i - 1}: short_entries[{i - 1}] = {short_entries[i - 1]}"
        )

        # Calculate TP/SL for SHORT
        entry_price = 91800.00
        tp_price = entry_price * (1 - 0.015)  # 90423
        sl_price = entry_price * (1 + 0.03)  # 94554
        print(f"  TP price: {tp_price:.2f}")
        print(f"  SL price: {sl_price:.2f}")

        # Find TP hit
        for j in range(i, len(data)):
            low = data[j, 2]
            if low <= tp_price:
                print(f"\n  TP hits at bar {j}:")
                print(f"  Low = {data[j, 2]:.2f} <= TP = {tp_price:.2f}")
                print(
                    f"  Bar {j}: O={data[j, 0]:.2f} H={data[j, 1]:.2f} L={data[j, 2]:.2f} C={data[j, 3]:.2f}"
                )

                # Check signals at this bar
                print(f"  long_entries[{j}] = {long_entries[j]}")
                print(f"  short_entries[{j}] = {short_entries[j]}")
                break
        break

print()
print("=== TRADE 46: LONG ===")
# Find entry bar for LONG at 89596.40
for i in range(len(data)):
    if abs(data[i, 0] - 89596.40) < 0.1:
        print(f"Trade 46 entry at bar {i}:")
        print(f"  Open = {data[i, 0]:.2f}")
        # Signal was at bar i-1
        print(f"  Signal at bar {i - 1}: long_entries[{i - 1}] = {long_entries[i - 1]}")
        break

print()
print("=== TIMELINE ===")
# Now I need to understand the timeline:
# 1. Trade 45 SHORT enters at bar X
# 2. Trade 45 SHORT exits (TP) at bar Y
# 3. Trade 46 LONG signal at bar ?
# 4. Trade 46 LONG enters at bar Z

# Trade 45 entry
t45_entry_bar = None
for i in range(len(data)):
    if abs(data[i, 0] - 91800.00) < 0.1:
        t45_entry_bar = i
        break
t45_signal_bar = t45_entry_bar - 1

# Trade 45 exit
t45_tp = 91800.00 * (1 - 0.015)  # 90423
t45_exit_bar = None
for j in range(t45_entry_bar, len(data)):
    if data[j, 2] <= t45_tp:
        t45_exit_bar = j
        break

# Trade 46 entry
t46_entry_bar = None
for i in range(len(data)):
    if abs(data[i, 0] - 89596.40) < 0.1:
        t46_entry_bar = i
        break
t46_signal_bar = t46_entry_bar - 1

# Trade 46 exit
t46_tp = 89596.40 * 1.015  # 90940.35
t46_exit_bar = None
for j in range(t46_entry_bar, len(data)):
    if data[j, 1] >= t46_tp:
        t46_exit_bar = j
        break

print("Trade 45 (SHORT):")
print(f"  Signal bar: {t45_signal_bar}")
print(f"  Entry bar: {t45_entry_bar}")
print(f"  Exit bar: {t45_exit_bar}")
print()
print("Trade 46 (LONG):")
print(f"  Signal bar: {t46_signal_bar}")
print(f"  Entry bar: {t46_entry_bar}")
print(f"  Exit bar: {t46_exit_bar}")
print()

# Check if Trade 45 exit and Trade 46 signal overlap
print("=== OVERLAP CHECK ===")
print(f"Trade 45 exits at bar {t45_exit_bar}")
print(f"Trade 46 signal at bar {t46_signal_bar}")
print(f"Trade 46 TP hits (exit) at bar {t46_exit_bar}")

if t45_exit_bar is not None and t46_signal_bar is not None:
    if t45_exit_bar == t46_signal_bar:
        print("\n*** OVERLAP: Trade 45 exit and Trade 46 signal on SAME bar! ***")
        print("This means:")
        print(
            f"  1. At bar {t45_exit_bar}: SHORT TP hit detected, pending_short_exit=True, in_short=False"
        )
        print(
            f"  2. At bar {t45_exit_bar}: LONG signal exists, but need not in_long AND not in_short"
        )
        print("  3. Wait... in_short was just set to False...")
    elif t45_exit_bar < t46_signal_bar:
        print("\nTrade 45 exits before Trade 46 signal - sequential (OK)")
    else:
        print("\nTrade 45 exits after Trade 46 signal - overlapping positions!")
