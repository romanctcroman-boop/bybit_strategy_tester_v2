"""Debug trade 45-46 discrepancy between Fallback and Numba."""

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

input_data = BacktestInput(
    candles=df,
    candles_1m=None,
    initial_capital=10000,
    use_fixed_amount=True,
    fixed_amount=10000,
    leverage=10,
    take_profit=0.015,
    stop_loss=0.03,
    taker_fee=0.0007,
    direction=TradeDirection.BOTH,
    long_entries=long_entries,
    short_entries=short_entries,
    use_bar_magnifier=False,
)

fb = FallbackEngineV2()
nb = NumbaEngineV2()

fb_result = fb.run(input_data)
nb_result = nb.run(input_data)

print("=== Trade 45 details ===")
fb_t45 = fb_result.trades[45]
nb_t45 = nb_result.trades[45]
print(
    f"  Fallback: {fb_t45.direction} @ {fb_t45.entry_price:.2f} → {fb_t45.exit_price:.2f} ({fb_t45.exit_reason}) entry_time={fb_t45.entry_time}"
)
print(
    f"  Numba:    {nb_t45.direction} @ {nb_t45.entry_price:.2f} → {nb_t45.exit_price:.2f} ({nb_t45.exit_reason})"
)

print()
print("=== Trade 46 details ===")
fb_t46 = fb_result.trades[46]
nb_t46 = nb_result.trades[46]
print(
    f"  Fallback: {fb_t46.direction} @ {fb_t46.entry_price:.2f} → {fb_t46.exit_price:.2f} ({fb_t46.exit_reason}) entry_time={fb_t46.entry_time}"
)
print(
    f"  Numba:    {nb_t46.direction} @ {nb_t46.entry_price:.2f} → {nb_t46.exit_price:.2f} ({nb_t46.exit_reason})"
)

# Find signal bars for trade 46
print()
print("=== Finding signal bars ===")

# Fallback trade 46: short @ 89650.30
fb_entry_price = 89650.30
# This is entry price = open of bar i+1, so we need bar i where signal was
mask = np.abs(df["open"].values - fb_entry_price) < 1
indices = np.where(mask)[0]
print(f"Fallback entry price {fb_entry_price:.2f} is at bar(s): {indices}")
for idx in indices:
    if idx > 0:
        print(
            f"  Signal bar {idx - 1}: long={long_entries[idx - 1]}, short={short_entries[idx - 1]}, time={df['timestamp'].iloc[idx - 1]}"
        )

# Numba trade 46: long @ 90810.90
nb_entry_price = 90810.90
mask = np.abs(df["open"].values - nb_entry_price) < 1
indices = np.where(mask)[0]
print(f"Numba entry price {nb_entry_price:.2f} is at bar(s): {indices}")
for idx in indices:
    if idx > 0:
        print(
            f"  Signal bar {idx - 1}: long={long_entries[idx - 1]}, short={short_entries[idx - 1]}, time={df['timestamp'].iloc[idx - 1]}"
        )

# So the question is: why did Numba take long@90810 instead of short@89650?
# Let's see if both signals exist
print()
print("=== Signal overlap check ===")
# short signal at bar 6376 (for entry @89650.30)
# long signal at bar 6502 (for entry @90810.90)
# Which came first?
print(f"short_entries[6375]: {short_entries[6375]} (for short @ 89650.30)")
print(f"long_entries[6502]: {long_entries[6502]} (for long @ 90810.90)")

# Check what bar trade 45 exited
print()
print("=== Trade 45 exit analysis ===")
# Trade 45 long entry @ 89596.40
entry_bar = np.where(np.abs(df["open"].values - 89596.40) < 1)[0]
print(f"Trade 45 entry bar candidates: {entry_bar}")

# TP would be at 89596.40 * 1.015 = 90940.35
tp_price = 89596.40 * 1.015
print(f"Trade 45 TP price: {tp_price:.2f}")
