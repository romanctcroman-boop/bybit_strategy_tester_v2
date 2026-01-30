"""Debug equity curve - detailed trace at problematic bars."""

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

# Rename columns
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

# Load TV signals
long_entries = np.load(tv_data_dir / "long_signals.npy")
short_entries = np.load(tv_data_dir / "short_signals.npy")

print(
    f"Loaded {len(df)} candles, {long_entries.sum()} long, {short_entries.sum()} short signals"
)

# Prepare candles
candles = df.reset_index(drop=True)

# Create BacktestInput
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

# Run Fallback engine
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2

fb_engine = FallbackEngineV2()
fb_result = fb_engine.run(input_data)

print("=" * 70)
print("FALLBACK ENGINE")
print("=" * 70)
print(f"Trades: {len(fb_result.trades)}")
print(f"Net Profit: {fb_result.metrics.net_profit:.2f}")
print(f"Max Drawdown: {fb_result.metrics.max_drawdown:.2f}")

# Get equity curve
fb_equity = np.array(fb_result.equity_curve)
print(f"\nEquity curve: {len(fb_equity)} points")
print(f"Min: {fb_equity.min():.2f}, Max: {fb_equity.max():.2f}")

# Find bars where equity is very low (less than 1000 when initial is 1M)
zero_bars = np.where(fb_equity < 1000)[0]
print(f"\nFound {len(zero_bars)} bars with equity < 1000")
if len(zero_bars) > 0:
    for b in zero_bars[:10]:
        print(f"  Bar {b}: equity={fb_equity[b]:.2f}")

# Run Numba engine
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

nb_engine = NumbaEngineV2()
nb_result = nb_engine.run(input_data)

print("\n" + "=" * 70)
print("NUMBA ENGINE")
print("=" * 70)
print(f"Trades: {len(nb_result.trades)}")
print(f"Net Profit: {nb_result.metrics.net_profit:.2f}")
print(f"Max Drawdown: {nb_result.metrics.max_drawdown:.2f}")

nb_equity = np.array(nb_result.equity_curve)
print(f"\nEquity curve: {len(nb_equity)} points")
print(f"Min: {nb_equity.min():.2f}, Max: {nb_equity.max():.2f}")

# Compare equity curves
print("\n" + "=" * 70)
print("EQUITY COMPARISON")
print("=" * 70)

# Find first difference
min_len = min(len(fb_equity), len(nb_equity))
for i in range(min_len):
    if abs(fb_equity[i] - nb_equity[i]) > 0.01:
        print(f"First diff at bar {i}: FB={fb_equity[i]:.2f} NB={nb_equity[i]:.2f}")
        # Show surrounding bars
        print(f"\nBars {max(0, i - 3)} to {min(min_len, i + 5)}:")
        for j in range(max(0, i - 3), min(min_len, i + 5)):
            diff = abs(fb_equity[j] - nb_equity[j])
            marker = " <-- DIFF" if diff > 0.01 else ""
            print(
                f"  Bar {j}: FB={fb_equity[j]:>12.2f}  NB={nb_equity[j]:>12.2f}{marker}"
            )
        break
else:
    print("No differences found in equity curves!")

# Compare trade PnLs
print("\n" + "=" * 70)
print("TRADE PNL COMPARISON (first 10)")
print("=" * 70)

for i in range(min(10, len(fb_result.trades), len(nb_result.trades))):
    fb_t = fb_result.trades[i]
    nb_t = nb_result.trades[i]
    diff = abs(fb_t.pnl - nb_t.pnl)
    marker = " <-- DIFF" if diff > 0.01 else ""
    print(f"Trade {i + 1}: FB PnL={fb_t.pnl:>8.2f}  NB PnL={nb_t.pnl:>8.2f}{marker}")
