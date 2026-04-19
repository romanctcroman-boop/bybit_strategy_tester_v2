"""
Debug Sharpe: find exact TV formula for 15-minute bars
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

# Get bar-by-bar equity returns
timestamps = df.index.tolist()
ts_idx = pd.DatetimeIndex(timestamps)
equity_arr = np.array(result.equity_curve.equity)  # N elements
ec_series = pd.Series(equity_arr, index=ts_idx)

print(f"Equity length: {len(equity_arr)}")

# 15-min bar returns
bar_r = ec_series.pct_change().dropna().values
mean_r = np.mean(bar_r)
std_r = np.std(bar_r, ddof=1)
print(f"\n15-min bar returns: n={len(bar_r)}, mean={mean_r:.8f}, std={std_r:.8f}")

# TV uses a specific formula based on how many 15m bars are in a year
# 365.25 days * 24h * 4 bars/h = 35040 bars/year
# OR 365 days * 24 * 4 = 35040
# OR trading-hours adjusted: 365.25 * 24 * 4 = 35040

print("\n=== Sharpe with 15m factor = 35040 bars/year ===")
rfr_annual = 0.02  # 2% annual
period_rfr = rfr_annual / 35040
print(f"RFR per 15m bar: {period_rfr:.8f}")
s1 = (mean_r - period_rfr) / std_r * np.sqrt(35040)
print(f"Sharpe (35040, rfr=2%): {s1:.4f}")
s2 = mean_r / std_r * np.sqrt(35040)
print(f"Sharpe (35040, rfr=0%): {s2:.4f}")

# Try 0 RFR
rfr = 0.0
s3 = (mean_r - rfr) / std_r * np.sqrt(35040)
print(f"Sharpe (35040, rfr=0): {s3:.4f}")

# What about using ddof=0?
std_r0 = np.std(bar_r, ddof=0)
s4 = mean_r / std_r0 * np.sqrt(35040)
print(f"Sharpe (35040, rfr=0, ddof=0): {s4:.4f}")

# Let's figure out what factor gives exactly 0.895
# 0.895 = mean_r / std_r * sqrt(X)  (with rfr≈0)
# X = (0.895 * std_r / mean_r)^2
target = 0.895
x_needed = (target * std_r / mean_r) ** 2
print(f"\n>>> To get Sharpe={target}: need sqrt({x_needed:.1f}), i.e. {x_needed:.1f} bars/year")
# ddof=0 version
x0_needed = (target * std_r0 / mean_r) ** 2
print(f">>> With ddof=0: need sqrt({x0_needed:.1f}), i.e. {x0_needed:.1f} bars/year")

# RFR needed
print("\n=== What RFR gives 0.895 with factor 35040? ===")
# 0.895 = (mean_r - rfr) / std_r * sqrt(35040)
# rfr = mean_r - 0.895 * std_r / sqrt(35040)
rfr_needed = mean_r - target * std_r / np.sqrt(35040)
print(f"Period rfr: {rfr_needed:.8f}, annual: {rfr_needed * 35040:.4f} = {rfr_needed * 35040 * 100:.2f}%")

# Try 1% annual RFR (TV default)
rfr1pct = 0.01 / 35040
s5 = (mean_r - rfr1pct) / std_r * np.sqrt(35040)
print(f"\nSharpe (35040, rfr=1%): {s5:.4f}")
rfr0pct = 0.0 / 35040
s6 = (mean_r - rfr0pct) / std_r * np.sqrt(35040)
print(f"Sharpe (35040, rfr=0%): {s6:.4f}")

# Try log returns instead of percent returns
log_r = np.log(equity_arr[1:] / equity_arr[:-1])
log_mean = np.mean(log_r)
log_std = np.std(log_r, ddof=1)
print(f"\nLog returns: mean={log_mean:.8f}, std={log_std:.8f}")
s_log = log_mean / log_std * np.sqrt(35040)
print(f"Sharpe (log returns, 35040): {s_log:.4f}")

# Daily resampling with specific factor
daily_eq = ec_series.resample("D").last().ffill()
daily_r = daily_eq.pct_change().dropna().values
dm = np.mean(daily_r)
dstd = np.std(daily_r, ddof=1)
print(f"\nDaily returns: n={len(daily_r)}, mean={dm:.6f}, std={dstd:.6f}")
for ppyr in [252, 365, 365.25]:
    period_rfr2 = 0.02 / ppyr
    s_d = (dm - period_rfr2) / dstd * np.sqrt(ppyr)
    diff = abs(s_d - target) / target * 100
    mark = " ← MATCH" if diff < 2 else ""
    print(f"  Daily sqrt({ppyr}) rfr=2%: {s_d:.4f}  ({diff:.2f}%){mark}")
    s_d2 = dm / dstd * np.sqrt(ppyr)
    diff2 = abs(s_d2 - target) / target * 100
    mark2 = " ← MATCH" if diff2 < 2 else ""
    print(f"  Daily sqrt({ppyr}) rfr=0%: {s_d2:.4f}  ({diff2:.2f}%){mark2}")

# Weekly
weekly_eq = ec_series.resample("W-SUN").last().ffill()
weekly_r = weekly_eq.pct_change().dropna().values
wm = np.mean(weekly_r)
wstd = np.std(weekly_r, ddof=1)
print(f"\nWeekly returns: n={len(weekly_r)}, mean={wm:.6f}, std={wstd:.6f}")
for ppyr in [52, 57.2]:
    period_rfr3 = 0.02 / ppyr
    s_w = (wm - period_rfr3) / wstd * np.sqrt(ppyr)
    diff = abs(s_w - target) / target * 100
    mark = " ← MATCH" if diff < 2 else ""
    print(f"  Weekly sqrt({ppyr}) rfr=2%: {s_w:.4f}  ({diff:.2f}%){mark}")
    s_w2 = wm / wstd * np.sqrt(ppyr)
    diff2 = abs(s_w2 - target) / target * 100
    mark2 = " ← MATCH" if diff2 < 2 else ""
    print(f"  Weekly sqrt({ppyr}) rfr=0%: {s_w2:.4f}  ({diff2:.2f}%){mark2}")

print(f"\nEngine sharpe_ratio: {m.sharpe_ratio:.4f}  (TV: 0.895)")
