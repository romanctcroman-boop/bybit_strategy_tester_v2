"""
Debug Sortino & Sharpe: find exact TV formula
"""

import datetime as dt
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "d:\\bybit_strategy_tester_v2")
os.environ.setdefault("DATABASE_URL", "sqlite:///data.sqlite3")

from loguru import logger

logger.remove()

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB = "d:\\bybit_strategy_tester_v2\\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"

conn = sqlite3.connect(DB)
cur = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,))
cols = [d[0] for d in cur.description]
strat = dict(zip(cols, cur.fetchone(), strict=False))
conn.close()

bb = json.loads(strat["builder_blocks"])
bc = json.loads(strat["builder_connections"])
bg = json.loads(strat["builder_graph"])
g = {
    "name": strat["name"],
    "blocks": bb,
    "connections": bc,
    "market_type": "linear",
    "direction": "both",
    "interval": "15",
}
if bg and bg.get("main_strategy"):
    g["main_strategy"] = bg["main_strategy"]
adapter = StrategyBuilderAdapter(g)

conn2 = sqlite3.connect(DB)
start_ms = int(dt.datetime(2025, 11, 1, tzinfo=dt.UTC).timestamp() * 1000)
end_ms = int(dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC).timestamp() * 1000)
df = pd.read_sql_query(
    "SELECT open_time, open_price as open, high_price as high, low_price as low, "
    "close_price as close, volume "
    "FROM bybit_kline_audit WHERE symbol=? AND interval=? AND market_type=? "
    "AND open_time>=? AND open_time<=? ORDER BY open_time ASC",
    conn2,
    params=("BTCUSDT", "15", "linear", start_ms, end_ms),
)
conn2.close()
df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df = df.set_index("timestamp").drop(columns=["open_time"])

params_j = json.loads(strat["parameters"])
cfg = BacktestConfig(
    symbol="BTCUSDT",
    interval="15",
    start_date=dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
    end_date=dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC),
    initial_capital=10000.0,
    commission_value=float(params_j.get("_commission", 0.0007)),
    slippage=0.0,
    leverage=10.0,
    position_size=0.1,
    pyramiding=1,
    direction="both",
    stop_loss=0.032,
    take_profit=0.015,
)

engine = BacktestEngine()
result = engine.run(cfg, df, custom_strategy=adapter)
m = result.metrics

# Reconstruct equity/timestamps directly from OHLCV
timestamps = df.index.tolist()
ts_idx = pd.DatetimeIndex(timestamps)

# Use the engine equity curve
equity_arr_full = np.array(result.equity_curve.equity)  # N elements (timestamps-aligned)
ec_series = pd.Series(equity_arr_full, index=ts_idx)

print(f"equity_arr_full length: {len(equity_arr_full)}")
print(f"timestamps length: {len(timestamps)}")
print(f"Index tz: {ec_series.index.tz}")
print()

# === SORTINO ANALYSIS ===
print("=" * 60)
print("SORTINO ANALYSIS (TV: 16.708)")
print("=" * 60)

# Weekly W-SUN
weekly_eq = ec_series.resample("W-SUN").last().ffill()
weekly_r = weekly_eq.pct_change().dropna().values
print(f"Weekly (W-SUN) bars: {len(weekly_r)}")
print(f"Weekly returns: mean={np.mean(weekly_r):.6f}, std={np.std(weekly_r):.6f}")

wm = np.mean(weekly_r)
wneg = np.minimum(0.0, weekly_r)
wdd = np.sqrt(np.sum(wneg**2) / len(weekly_r))
print(f"Weekly downside deviation: {wdd:.6f}")
print()

# Try different annualization factors for Sortino
print("Sortino with different annualization factors:")
target = 16.708
for ppyr in [52, 53, 54, 55, 56, 57, 58, 60, 57.2, 56.5, 55.5]:
    s = wm / wdd * np.sqrt(ppyr) if wdd > 1e-10 else 0.0
    diff = abs(s - target) / target * 100
    mark = " ← MATCH" if diff < 1 else ""
    print(f"  sqrt({ppyr:5.1f}): {s:.4f}  ({diff:.2f}% from TV){mark}")

# Monthly
monthly_eq = ec_series.resample("MS").last().ffill()
monthly_r = monthly_eq.pct_change().dropna().values
print(f"\nMonthly (MS) bars: {len(monthly_r)}")
if len(monthly_r) >= 2:
    mm = np.mean(monthly_r)
    mneg = np.minimum(0.0, monthly_r)
    mdd = np.sqrt(np.sum(mneg**2) / len(monthly_r))
    print(f"Monthly Sortino (sqrt(12)): {mm / mdd * np.sqrt(12):.4f}" if mdd > 1e-10 else "mdd=0")

# Daily
daily_eq = ec_series.resample("D").last().ffill()
daily_r = daily_eq.pct_change().dropna().values
print(f"\nDaily bars: {len(daily_r)}")
dm = np.mean(daily_r)
dneg = np.minimum(0.0, daily_r)
ddd = np.sqrt(np.sum(dneg**2) / len(daily_r))
print(f"Daily Sortino (sqrt(365)): {dm / ddd * np.sqrt(365):.4f}" if ddd > 1e-10 else "ddd=0")
print(f"Daily Sortino (sqrt(252)): {dm / ddd * np.sqrt(252):.4f}" if ddd > 1e-10 else "ddd=0")

print()
print(f"Engine sortino_ratio: {m.sortino_ratio:.4f}  (TV: {target})")

# === SHARPE ANALYSIS ===
print()
print("=" * 60)
print("SHARPE ANALYSIS (TV: 0.895)")
print("=" * 60)
target_sh = 0.895

# Weekly
wstd = np.std(weekly_r)
sharpe_weekly52 = wm / wstd * np.sqrt(52) if wstd > 1e-10 else 0.0
print(f"Weekly Sharpe sqrt(52): {sharpe_weekly52:.4f}")
for ppyr in [52, 57.2, 56.5, 55, 60]:
    s = wm / wstd * np.sqrt(ppyr) if wstd > 1e-10 else 0.0
    diff = abs(s - target_sh) / target_sh * 100
    mark = " ← MATCH" if diff < 1 else ""
    print(f"  Weekly sqrt({ppyr:5.1f}): {s:.4f}  ({diff:.2f}% from TV){mark}")

# Daily
if ddd > 1e-10:
    for ppyr in [252, 365]:
        s = dm / np.std(daily_r) * np.sqrt(ppyr)
        diff = abs(s - target_sh) / target_sh * 100
        mark = " ← MATCH" if diff < 1 else ""
        print(f"  Daily  sqrt({ppyr}): {s:.4f}  ({diff:.2f}% from TV){mark}")

# Bar-by-bar
bar_r = ec_series.pct_change().dropna().values
bm = np.mean(bar_r)
bstd = np.std(bar_r)
for ppyr in [96, 4 * 96, 24 * 4, 365 * 24 * 4, 8760 * 4]:
    s = bm / bstd * np.sqrt(ppyr) if bstd > 1e-10 else 0.0
    diff = abs(s - target_sh) / target_sh * 100
    mark = " ← MATCH" if diff < 1 else ""
    print(f"  Bar(15m) sqrt({ppyr}): {s:.4f}  ({diff:.2f}% from TV){mark}")

print(f"\nEngine sharpe_ratio: {m.sharpe_ratio:.4f}  (TV: {target_sh})")
