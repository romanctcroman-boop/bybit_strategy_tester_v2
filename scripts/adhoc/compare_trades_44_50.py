"""Compare Trade 44-50 between Fallback and Numba"""

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

# Print trades 44-50 side by side
print("=== Trades 44-52 (0-indexed 43-51) ===")
print()
print("Fallback:")
for i in range(43, min(52, len(fb_result.trades))):
    t = fb_result.trades[i]
    print(
        f"  {i + 1}: {t.direction:5} entry={t.entry_price:.2f} exit={t.exit_price:.2f} {t.exit_reason.name}"
    )

print()
print("Numba:")
for i in range(43, min(52, len(nb_result.trades))):
    t = nb_result.trades[i]
    print(
        f"  {i + 1}: {t.direction:5} entry={t.entry_price:.2f} exit={t.exit_price:.2f} {t.exit_reason.name}"
    )

# Find first differing trade
print()
print("=== Finding first trade difference ===")
for i in range(min(len(fb_result.trades), len(nb_result.trades))):
    fb_t = fb_result.trades[i]
    nb_t = nb_result.trades[i]

    if (
        fb_t.direction != nb_t.direction
        or abs(fb_t.entry_price - nb_t.entry_price) > 0.1
        or abs(fb_t.exit_price - nb_t.exit_price) > 0.1
    ):
        print(f"First difference at trade {i + 1}:")
        print(
            f"  FB: {fb_t.direction:5} entry={fb_t.entry_price:.2f} exit={fb_t.exit_price:.2f} {fb_t.exit_reason.name}"
        )
        print(
            f"  NB: {nb_t.direction:5} entry={nb_t.entry_price:.2f} exit={nb_t.exit_price:.2f} {nb_t.exit_reason.name}"
        )
        break
