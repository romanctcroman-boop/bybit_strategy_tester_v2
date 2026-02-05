"""Debug signals around bar 6502 (Trade 45 exit bar)"""

import os

os.chdir(str(Path(__file__).resolve().parents[1]))
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pathlib import Path

import numpy as np
import pandas as pd

# Load data from d:/TV (same as compare_trades.py)
tv_data_dir = Path("d:/TV")
df = pd.read_csv(tv_data_dir / "BYBIT_BTCUSDT.P_15m_full.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values("timestamp").reset_index(drop=True)

# Load TV signals
long_entries = np.load(tv_data_dir / "long_signals.npy")
short_entries = np.load(tv_data_dir / "short_signals.npy")

data = df[["open", "high", "low", "close"]].values

print("=== Signals around Trade 45 exit bar ===")
print(f"Total bars: {len(data)}")
print()

# Trade 45 entry at bar 6320, entry price is open of bar 6321
entry_signal_bar = 6320
entry_bar = 6321  # Entry is at open of NEXT bar
entry_price = data[entry_bar, 0]  # Open
tp_price = entry_price * 1.015  # 1.5% TP
sl_price = entry_price * (1 - 0.03)  # 3% SL

print(f"Trade 45: LONG entry signal at bar {entry_signal_bar}")
print(f"  Entry bar: {entry_bar}")
print(f"  Entry price (open of bar {entry_bar}): {entry_price:.2f}")
print(f"  TP price: {tp_price:.2f}")
print(f"  SL price: {sl_price:.2f}")
print()

# Find where TP hits
for i in range(entry_bar, min(entry_bar + 500, len(data))):
    high = data[i, 1]  # High
    low = data[i, 2]  # Low

    # Check TP hit
    if high >= tp_price:
        print(f"TP hits at bar {i}:")
        print(
            f"  O={data[i, 0]:.2f} H={data[i, 1]:.2f} L={data[i, 2]:.2f} C={data[i, 3]:.2f}"
        )
        print(f"  TP price {tp_price:.2f} <= High {high:.2f}")

        # Check if there's a LONG signal at this bar
        if long_entries[i]:
            next_bar_open = data[i + 1, 0] if i + 1 < len(data) else 0
            print(
                f"  ** LONG signal at same bar! Next bar open = {next_bar_open:.2f} **"
            )
        if short_entries[i]:
            next_bar_open = data[i + 1, 0] if i + 1 < len(data) else 0
            print(
                f"  ** SHORT signal at same bar! Next bar open = {next_bar_open:.2f} **"
            )
        break

print()
print("=== All ENTRY signals from bar 6495 to 6530 ===")
for i in range(6495, min(6535, len(data) - 1)):
    if long_entries[i] or short_entries[i]:
        direction = "LONG" if long_entries[i] else "SHORT"
        next_bar_open = data[i + 1, 0] if i + 1 < len(data) else 0
        ts = df.iloc[i]["timestamp"]
        print(f"Bar {i}: {ts} - {direction} signal")
        print(
            f"  Current bar: O={data[i, 0]:.2f} H={data[i, 1]:.2f} L={data[i, 2]:.2f} C={data[i, 3]:.2f}"
        )
        print(f"  Next bar open (entry price): {next_bar_open:.2f}")

print()
print("=== Signal at bar 6502 specifically ===")
i = 6502
print(f"long_entries[{i}] = {long_entries[i]}")
print(f"short_entries[{i}] = {short_entries[i]}")

# Also check bar 6321 (entry bar)
print()
print(f"=== Signal at bar {entry_signal_bar} (entry signal bar) ===")
print(f"long_entries[{entry_signal_bar}] = {long_entries[entry_signal_bar]}")
print(f"short_entries[{entry_signal_bar}] = {short_entries[entry_signal_bar]}")
