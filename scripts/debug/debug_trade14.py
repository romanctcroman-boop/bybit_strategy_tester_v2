"""Debug Trade 14 differences"""

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

# Compare Trade 14 in detail
i = 13  # 0-indexed
fb_t = fb_result.trades[i]
nb_t = nb_result.trades[i]

print(f"=== TRADE {i + 1} DETAILED COMPARISON ===")
print()
print("Fallback:")
print(f"  Direction: {fb_t.direction}")
print(f"  Entry price: {fb_t.entry_price:.4f}")
print(f"  Exit price: {fb_t.exit_price:.4f}")
print(f"  Size: {fb_t.size:.8f}")
print(f"  PnL: {fb_t.pnl:.4f}")
print(f"  Fees: {fb_t.fees:.4f}")
print(f"  Exit reason: {fb_t.exit_reason}")

print()
print("Numba:")
print(f"  Direction: {nb_t.direction}")
print(f"  Entry price: {nb_t.entry_price:.4f}")
print(f"  Exit price: {nb_t.exit_price:.4f}")
print(f"  Size: {nb_t.size:.8f}")
print(f"  PnL: {nb_t.pnl:.4f}")
print(f"  Fees: {nb_t.fees:.4f}")
print(f"  Exit reason: {nb_t.exit_reason}")

print()
print("Differences:")
print(f"  Entry diff: {fb_t.entry_price - nb_t.entry_price:.4f}")
print(f"  Exit diff: {fb_t.exit_price - nb_t.exit_price:.4f}")
print(f"  Size diff: {fb_t.size - nb_t.size:.8f}")
print(f"  PnL diff: {fb_t.pnl - nb_t.pnl:.4f}")
print(f"  Fees diff: {fb_t.fees - nb_t.fees:.4f}")

# Calculate what PnL should be for Numba given its size
if nb_t.direction == "short":
    expected_pnl_nb = (nb_t.entry_price - nb_t.exit_price) * nb_t.size
else:
    expected_pnl_nb = (nb_t.exit_price - nb_t.entry_price) * nb_t.size

print()
print(f"Expected NB PnL (before fees): {expected_pnl_nb:.4f}")
print(f"NB Fees: {nb_t.fees:.4f}")
print(f"Expected NB PnL (after fees): {expected_pnl_nb - nb_t.fees:.4f}")
print(f"Actual NB PnL: {nb_t.pnl:.4f}")
