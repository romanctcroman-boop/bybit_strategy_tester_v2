"""Debug Trade 45 entry bar more carefully"""

import os

os.chdir(str(Path(__file__).resolve().parents[1]))
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pathlib import Path

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
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
fb_result = fb.run(input_data)

print(f"Total Fallback trades: {len(fb_result.trades)}")
print()

# Find Trade 45
if len(fb_result.trades) >= 45:
    t = fb_result.trades[44]  # 0-indexed
    print(f"Trade 45:")
    print(f"  Direction: {t.direction}")
    print(f"  Entry price: {t.entry_price:.2f}")
    print(f"  Exit price: {t.exit_price:.2f}")
    print(f"  Exit reason: {t.exit_reason}")
    print(f"  Duration bars: {t.duration_bars}")

    # Calculate entry bar
    # entry_price = open of (signal_bar + 1), so signal_bar = entry_bar - 1
    data = df[["open", "high", "low", "close"]].values

    # Find signal bar by matching entry price
    entry_price = t.entry_price
    for i in range(len(data) - 1):
        next_open = data[i + 1, 0]
        if abs(next_open - entry_price) < 0.01:
            # Check if there was a long signal at bar i
            if t.direction == "long" and long_entries[i]:
                print(f"  Signal bar: {i}")
                print(f"  Entry bar (i+1): {i + 1}")
                print(f"  Verified: open[{i + 1}] = {next_open:.2f}")

                # Calculate expected exit bar
                tp_price = entry_price * 1.015
                sl_price = entry_price * (1 - 0.03)

                # Find exit bar
                for j in range(i + 1, min(i + 1 + t.duration_bars + 5, len(data))):
                    high = data[j, 1]
                    low = data[j, 2]

                    if high >= tp_price:
                        print(f"  TP hit at bar {j}")
                        print(f"    High={high:.2f} >= TP={tp_price:.2f}")
                        # Check for new signal at same bar
                        if long_entries[j]:
                            print(f"    *** LONG signal also at bar {j} ***")
                        if short_entries[j]:
                            print(f"    *** SHORT signal also at bar {j} ***")
                        break
                break

print()
print("=== Trade 46 ===")
if len(fb_result.trades) >= 46:
    t = fb_result.trades[45]  # 0-indexed
    print(f"  Direction: {t.direction}")
    print(f"  Entry price: {t.entry_price:.2f}")
    print(f"  Exit price: {t.exit_price:.2f}")
    print(f"  Exit reason: {t.exit_reason}")

print()
print("=== Trade 47 ===")
if len(fb_result.trades) >= 47:
    t = fb_result.trades[46]  # 0-indexed
    print(f"  Direction: {t.direction}")
    print(f"  Entry price: {t.entry_price:.2f}")
    print(f"  Exit price: {t.exit_price:.2f}")
    print(f"  Exit reason: {t.exit_reason}")
