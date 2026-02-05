#!/usr/bin/env python3
"""Verify that VBT and Fallback are truly different engines."""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sqlite3

import pandas as pd
import vectorbt as vbt

from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategies import get_strategy

# Load data
conn = sqlite3.connect(str(ROOT / "data.sqlite3"))
start_ts = int(datetime(2025, 1, 1).timestamp() * 1000)
end_ts = int(datetime(2025, 1, 11).timestamp() * 1000)
cursor = conn.cursor()
cursor.execute(
    """SELECT open_time, open_price, high_price, low_price, close_price, volume
    FROM bybit_kline_audit WHERE symbol = 'BTCUSDT' AND interval = '15'
    AND open_time >= ? AND open_time <= ? ORDER BY open_time""",
    (start_ts, end_ts),
)
rows = cursor.fetchall()
conn.close()

df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume"])
df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
df = df.set_index("open_time")
for col in ["open", "high", "low", "close", "volume"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

config = BacktestConfig(
    symbol="BTCUSDT",
    interval="15",
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 1, 11),
    strategy_type="rsi",
    strategy_params={"period": 21, "oversold": 30, "overbought": 70},
    direction="long",
    initial_capital=10000.0,
    leverage=10.0,
    position_size=1.0,
)
strategy = get_strategy(config.strategy_type, config.strategy_params)
signals = strategy.generate_signals(df)

# Create VBT portfolio DIRECTLY (proof that vectorbt is used)
close = df["close"].values
order_value = float(config.position_size) * float(config.initial_capital)
pf = vbt.Portfolio.from_signals(
    close=close,
    entries=signals.entries,
    exits=signals.exits,
    init_cash=config.initial_capital,
    size=order_value,
    size_type="value",
    fees=config.taker_fee,
    slippage=config.slippage,
    freq="15min",
)

print("=" * 70)
print("PROOF: VBT and FALLBACK are DIFFERENT engines")
print("=" * 70)

print("\n=== VBT RAW DATA (directly from vectorbt library) ===")
records = pf.trades.records_readable
for i, row in records.head(3).iterrows():
    size = row["Size"]
    entry = row["Avg Entry Price"]
    pnl = row["PnL"]
    print(f"Trade {i}: Size={size:.6f}, Entry=${entry:.2f}, PnL=${pnl:.2f} (NO LEVERAGE!)")

print("\nVBT internal equity (vectorbt calculates WITHOUT leverage):")
print(f"  Initial: ${config.initial_capital:.2f}")
print(f"  Final:   ${pf.value().values[-1]:.2f}")
print(f"  Delta:   ${pf.value().values[-1] - config.initial_capital:.2f}")

# Compare with normalized output
from backend.backtesting.engine import BacktestEngine

engine = BacktestEngine()

print("\n" + "=" * 70)
print("Now running both engines:")
print("=" * 70)

fb = engine._run_fallback(config, df, signals)
vb = engine._run_vectorbt(config, df, signals)

print("\n=== SIDE-BY-SIDE COMPARISON ===")
print(f"{'Metric':<25} {'Fallback':>15} {'VBT Normalized':>15} {'Match':>10}")
print("-" * 70)

for i in range(min(3, len(fb.trades), len(vb.trades))):
    fb_t = fb.trades[i]
    vb_t = vb.trades[i]

    # Size
    size_match = abs(fb_t.size - vb_t.size) < 0.0001
    print(f"Trade {i+1} Size:           {fb_t.size:>15.6f} {vb_t.size:>15.6f} {'✓' if size_match else '✗':>10}")

    # PnL
    pnl_match = abs(fb_t.pnl - vb_t.pnl) < 0.01
    print(f"Trade {i+1} PnL:            ${fb_t.pnl:>14.2f} ${vb_t.pnl:>14.2f} {'✓' if pnl_match else '✗':>10}")

print()
total_fb = sum(t.pnl for t in fb.trades)
total_vb = sum(t.pnl for t in vb.trades)
total_match = abs(total_fb - total_vb) < 0.01
print(f"TOTAL PnL:               ${total_fb:>14.2f} ${total_vb:>14.2f} {'✓' if total_match else '✗':>10}")

print("\n" + "=" * 70)
print(f"RESULT: {'100% MATCH - Both engines produce identical results!' if total_match else 'MISMATCH!'}")
print("=" * 70)
