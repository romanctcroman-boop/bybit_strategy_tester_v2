"""Direct comparison of Numba vs Fallback at bar 6502"""

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

print("=== STEP-BY-STEP SIMULATION ===")
print()

# Trade 46 entry parameters
t46_signal_bar = 6319
t46_entry_bar = 6320
t46_entry_price = data[t46_entry_bar, 0]  # 89596.40
t46_tp = t46_entry_price * 1.015  # 90940.35

print(f"Trade 46: LONG")
print(f"  Signal bar: {t46_signal_bar}")
print(f"  Entry bar: {t46_entry_bar}")
print(f"  Entry price: {t46_entry_price:.2f}")
print(f"  TP: {t46_tp:.2f}")
print()

# Simulate at bar 6501
bar = 6501
print(f"=== BAR {bar} ===")
o, h, lo, c = data[bar]
print(f"  O={o:.2f} H={h:.2f} L={lo:.2f} C={c:.2f}")
tp_hit = h >= t46_tp
print(f"  TP hit? {tp_hit} (H={h:.2f} >= TP={t46_tp:.2f})")
print(
    f"  Signals: long_entries[{bar}]={long_entries[bar]}, short_entries[{bar}]={short_entries[bar]}"
)
print()

# Simulate at bar 6502
bar = 6502
print(f"=== BAR {bar} ===")
o, h, lo, c = data[bar]
print(f"  O={o:.2f} H={h:.2f} L={lo:.2f} C={c:.2f}")
tp_hit = h >= t46_tp
print(f"  TP hit? {tp_hit} (H={h:.2f} >= TP={t46_tp:.2f})")
print(
    f"  Signals: long_entries[{bar}]={long_entries[bar]}, short_entries[{bar}]={short_entries[bar]}"
)
print()

print("=== NUMBA LOGIC ===")
print("At bar 6502:")
print("  1. Check LONG EXIT: TP hit → exit, in_long = False, exit_idx = 6502")
print("  2. Check SHORT EXIT: not in_short, skip")
print("  3. Check LONG ENTRY: not in_long ✓, long_entries[6502]=True ✓ → ENTER")
print("  4. Entry at open_prices[6503] = 90810.90")
print()

print("=== FALLBACK LOGIC ===")
print("At bar 6501:")
print("  - pending_long_exit = False")
print("  - Check exit: TP NOT hit (H=90756 < TP=90940.35)")
print("  - Check entry: in_long = True, skip")
print()
print("At bar 6502:")
print("  1. Execute pending exits: none (pending_long_exit = False)")
print("  2. Check exit conditions: TP hit!")
print("     → pending_long_exit = True")
print("     → in_long = False")
print("  3. Check entry: not in_long ✓, long_entries[6502]=True ✓ → SHOULD ENTER!")
print()

# But wait, maybe there's something else in Fallback...
# Let me check if cash is the issue
print("=== CHECKING CASH ===")
# Initial: 10000
# Trade 46 allocated: 10000 (use_fixed_amount=True, fixed_amount=10000)
# So cash = 0 after Trade 46 entry
print("After Trade 46 entry:")
print("  cash = 10000 - 10000 (allocated) = 0")
print()
print("At bar 6502 (TP exit):")
print("  pending_long_exit = True, so exit is NOT EXECUTED YET")
print("  cash = 0 (still, exit pnl not added)")
print()
print("Entry check at bar 6502:")
print("  allocated = min(fixed_amount=10000, cash=0) = 0")
print("  Condition: allocated >= 1.0 → 0 >= 1.0 → FALSE")
print("  → ENTRY SKIPPED!")
print()
print("=== ROOT CAUSE FOUND! ===")
print("Fallback uses pending exit mechanism:")
print("  - At bar where TP hits: position is 'freed' (in_long=False)")
print("  - But cash is NOT updated until next bar (exit pending)")
print("  - Entry check sees cash=0, skips entry")
print()
print("Numba does NOT use pending mechanism:")
print("  - At bar where TP hits: exit immediately, cash += allocated + pnl")
print("  - Entry check sees cash > 0, enters")
