"""Compare trades between Fallback and Numba to find divergence."""

import sys
from pathlib import Path

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import numpy as np
import pandas as pd

from backend.backtesting.interfaces import BacktestInput, TradeDirection

# Parameters
config = {
    "initial_capital": 1_000_000.0,
    "fixed_amount": 100.0,
    "leverage": 10,
    "take_profit": 0.015,
    "stop_loss": 0.03,
    "commission": 0.0007,
}

# Load OHLC data
tv_data_dir = Path(r"d:/TV")
df = pd.read_csv(tv_data_dir / "BYBIT_BTCUSDT.P_15m_full.csv")
column_map = {
    "time": "timestamp",
    "Time": "timestamp",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}
df.rename(columns=column_map, inplace=True)
if "timestamp" in df.columns:
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["timestamp"] = df["timestamp"].dt.tz_localize(None)

long_entries = np.load(tv_data_dir / "long_signals.npy")
short_entries = np.load(tv_data_dir / "short_signals.npy")

candles = df.reset_index(drop=True)
timestamps = df["timestamp"].values

input_data = BacktestInput(
    candles=candles,
    candles_1m=None,
    initial_capital=config["initial_capital"],
    use_fixed_amount=True,
    fixed_amount=config["fixed_amount"],
    leverage=config["leverage"],
    take_profit=config["take_profit"],
    stop_loss=config["stop_loss"],
    taker_fee=config["commission"],
    direction=TradeDirection.BOTH,
    long_entries=long_entries,
    short_entries=short_entries,
    use_bar_magnifier=False,
)

# Run both engines
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

fb_result = FallbackEngineV2().run(input_data)
nb_result = NumbaEngineV2().run(input_data)

print(f"FB trades: {len(fb_result.trades)}")
print(f"NB trades: {len(nb_result.trades)}")


# Find entry bars for all trades
def get_entry_bar(trade, timestamps):
    for i, ts in enumerate(timestamps):
        if ts == trade.entry_time:
            return i
    return None


fb_entries = [(get_entry_bar(t, timestamps), t.direction) for t in fb_result.trades]
nb_entries = [(get_entry_bar(t, timestamps), t.direction) for t in nb_result.trades]

# Find first difference
print("\nComparing trades by entry bar...")
for i in range(min(len(fb_entries), len(nb_entries))):
    fb_bar, fb_dir = fb_entries[i]
    nb_bar, nb_dir = nb_entries[i]
    if fb_bar != nb_bar or fb_dir != nb_dir:
        print(f"Trade {i + 1} differs!")
        print(f"  FB: entry_bar={fb_bar}, direction={fb_dir}")
        print(f"  NB: entry_bar={nb_bar}, direction={nb_dir}")
        # Show surrounding trades
        print("\nSurrounding FB trades:")
        for j in range(max(0, i - 2), min(len(fb_entries), i + 5)):
            bar, dir = fb_entries[j]
            t = fb_result.trades[j]
            exit_bar = None
            for k, ts in enumerate(timestamps):
                if ts == t.exit_time:
                    exit_bar = k
            print(f"  Trade {j + 1}: {dir} entry={bar} exit={exit_bar} pnl={t.pnl:.2f}")
        print("\nSurrounding NB trades:")
        for j in range(max(0, i - 2), min(len(nb_entries), i + 5)):
            bar, dir = nb_entries[j]
            t = nb_result.trades[j]
            exit_bar = None
            for k, ts in enumerate(timestamps):
                if ts == t.exit_time:
                    exit_bar = k
            print(f"  Trade {j + 1}: {dir} entry={bar} exit={exit_bar} pnl={t.pnl:.2f}")
        break
else:
    if len(fb_entries) != len(nb_entries):
        print(
            f"Trade counts differ but first {min(len(fb_entries), len(nb_entries))} match"
        )
        print(f"Extra FB trades starting at {len(nb_entries)}:")
        for i in range(len(nb_entries), len(fb_entries)):
            bar, dir = fb_entries[i]
            t = fb_result.trades[i]
            print(f"  Trade {i + 1}: {dir} entry={bar} pnl={t.pnl:.2f}")
    else:
        print("All trades match!")
