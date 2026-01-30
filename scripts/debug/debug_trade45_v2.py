"""Debug why Fallback skipped signal at bar 6502."""

from pathlib import Path

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection

# Load data
tv_data_dir = Path("d:/TV")
df = pd.read_csv(tv_data_dir / "BYBIT_BTCUSDT.P_15m_full.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values("timestamp").reset_index(drop=True)

long_entries = np.load(tv_data_dir / "long_signals.npy")
short_entries = np.load(tv_data_dir / "short_signals.npy")

# Trade 45 was long @ 89596.40 entry
# Find the entry bar (where open = 89596.40)
entry_price = 89596.40
entry_bars = np.where(np.abs(df["open"].values - entry_price) < 1)[0]
print(f"Trade 45 entry bar candidates: {entry_bars}")

# The signal was on the bar before, let's check
for entry_bar in entry_bars:
    if entry_bar > 0:
        signal_bar = entry_bar - 1
        print(f"\n  Entry at bar {entry_bar}, signal at bar {signal_bar}")
        print(f"    long_entries[{signal_bar}] = {long_entries[signal_bar]}")
        print(f"    timestamp: {df['timestamp'].iloc[signal_bar]}")

# Trade 45 TP = 89596.40 * 1.015 = 90940.35
tp_price = 90940.35
# Find exit bar (where high >= tp_price) starting from entry bar
entry_bar = 6320  # From previous output
print(f"\n\nLooking for TP {tp_price:.2f} starting from bar {entry_bar}...")
for i in range(entry_bar, min(entry_bar + 200, len(df))):
    if df["high"].iloc[i] >= tp_price:
        print(
            f"  TP hit at bar {i}: high={df['high'].iloc[i]:.2f}, time={df['timestamp'].iloc[i]}"
        )
        exit_bar = i
        break

# Now what signals are between exit_bar and 6502/6521?
print(f"\n\nSignals between exit bar {exit_bar} and bars 6502-6522:")
for i in range(exit_bar, 6525):
    if long_entries[i]:
        next_open = df["open"].iloc[i + 1] if i + 1 < len(df) else 0
        print(
            f"  LONG signal at bar {i}: {df['timestamp'].iloc[i]}, entry price would be {next_open:.2f}"
        )
    if short_entries[i]:
        next_open = df["open"].iloc[i + 1] if i + 1 < len(df) else 0
        print(
            f"  SHORT signal at bar {i}: {df['timestamp'].iloc[i]}, entry price would be {next_open:.2f}"
        )

# The key question: at bar 6502 when there's a long signal,
# was Fallback still in position from trade 45?
print(f"\n\n=== Position state analysis ===")
print(f"Trade 45 entry bar: {entry_bar}, exit bar: {exit_bar}")
print(f"Long signal at bar 6502")
print(f"Short signal at bar 6521")
print(f"Is exit_bar <= 6502? {exit_bar} <= 6502 = {exit_bar <= 6502}")
