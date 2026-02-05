"""Compare trades by PnL to find where they diverge."""

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

# Load data
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

# Compare by PnL sequence
fb_pnls = [round(t.pnl, 2) for t in fb_result.trades]
nb_pnls = [round(t.pnl, 2) for t in nb_result.trades]

# Find first PnL difference
print("\nComparing PnL sequences...")
min_len = min(len(fb_pnls), len(nb_pnls))
for i in range(min_len):
    if abs(fb_pnls[i] - nb_pnls[i]) > 0.01:
        print(f"First PnL diff at trade {i + 1}:")
        print(f"  FB: {fb_pnls[i]:.2f}")
        print(f"  NB: {nb_pnls[i]:.2f}")
        print(f"\nContext (trades {max(1, i - 2)} to {min(min_len, i + 5)}):")
        for j in range(max(0, i - 2), min(min_len, i + 5)):
            diff = abs(fb_pnls[j] - nb_pnls[j])
            marker = " <-- DIFF" if diff > 0.01 else ""
            print(
                f"  Trade {j + 1}: FB={fb_pnls[j]:>8.2f}  NB={nb_pnls[j]:>8.2f}{marker}"
            )
        break
else:
    print(f"First {min_len} trades have matching PnLs!")
    if len(fb_pnls) > min_len:
        print(f"\nExtra FB trades ({len(fb_pnls) - min_len}):")
        for i in range(min_len, len(fb_pnls)):
            print(f"  Trade {i + 1}: PnL={fb_pnls[i]:.2f}")
    if len(nb_pnls) > min_len:
        print(f"\nExtra NB trades ({len(nb_pnls) - min_len}):")
        for i in range(min_len, len(nb_pnls)):
            print(f"  Trade {i + 1}: PnL={nb_pnls[i]:.2f}")

# Total PnL comparison
print("\nTotal PnL:")
print(f"  FB: {sum(fb_pnls):.2f}")
print(f"  NB: {sum(nb_pnls):.2f}")
