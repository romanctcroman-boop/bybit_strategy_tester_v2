"""Compare fee calculations between Fallback and Numba"""

import os

os.chdir(str(Path(__file__).resolve().parents[1]))
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pathlib import Path

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection

# Load data from d:/TV
tv_data_dir = Path("d:/TV")
df = pd.read_csv(tv_data_dir / "BYBIT_BTCUSDT.P_15m_full.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values("timestamp").reset_index(drop=True)

# Load TV signals
long_entries = np.load(tv_data_dir / "long_signals.npy")
short_entries = np.load(tv_data_dir / "short_signals.npy")

# Config
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

print(f"Fallback trades: {len(fb_result.trades)}")
print(f"Numba trades: {len(nb_result.trades)}")
print()

# Compare first 5 trades in detail
print("=== DETAILED TRADE COMPARISON (First 5) ===")
for i in range(min(5, len(fb_result.trades))):
    fb_t = fb_result.trades[i]
    nb_t = nb_result.trades[i]

    print(f"\nTrade {i + 1}:")
    print(
        f"  FB: {fb_t.direction:5} entry={fb_t.entry_price:.2f} exit={fb_t.exit_price:.2f}"
    )
    print(f"      PnL={fb_t.pnl:.4f}, Fees={fb_t.fees:.4f}")
    print(
        f"  NB: {nb_t.direction:5} entry={nb_t.entry_price:.2f} exit={nb_t.exit_price:.2f}"
    )
    print(f"      PnL={nb_t.pnl:.4f}, Fees={nb_t.fees:.4f}")

    if abs(fb_t.pnl - nb_t.pnl) > 0.01:
        print(f"  *** PnL DIFF: {fb_t.pnl - nb_t.pnl:.4f} ***")
    if abs(fb_t.fees - nb_t.fees) > 0.01:
        print(f"  *** FEES DIFF: {fb_t.fees - nb_t.fees:.4f} ***")

# Calculate totals
fb_total_pnl = sum(t.pnl for t in fb_result.trades)
nb_total_pnl = sum(t.pnl for t in nb_result.trades)
fb_total_fees = sum(t.fees for t in fb_result.trades)
nb_total_fees = sum(t.fees for t in nb_result.trades)

print("\n=== TOTALS ===")
print(f"FB Total PnL: {fb_total_pnl:.4f}, Total Fees: {fb_total_fees:.4f}")
print(f"NB Total PnL: {nb_total_pnl:.4f}, Total Fees: {nb_total_fees:.4f}")
print(f"PnL Diff: {fb_total_pnl - nb_total_pnl:.4f}")
print(f"Fees Diff: {fb_total_fees - nb_total_fees:.4f}")

# Find trades with largest differences
print("\n=== TRADES WITH LARGEST PnL DIFFERENCES ===")
diffs = []
for i, (fb_t, nb_t) in enumerate(zip(fb_result.trades, nb_result.trades)):
    diff = abs(fb_t.pnl - nb_t.pnl)
    if diff > 0.01:
        diffs.append((i, fb_t, nb_t, diff))

diffs.sort(key=lambda x: x[3], reverse=True)
for i, fb_t, nb_t, diff in diffs[:5]:
    print(f"Trade {i + 1}: FB_pnl={fb_t.pnl:.4f} NB_pnl={nb_t.pnl:.4f} diff={diff:.4f}")
    print(f"  FB fees={fb_t.fees:.4f}, NB fees={nb_t.fees:.4f}")
