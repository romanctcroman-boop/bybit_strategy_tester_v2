"""
Debug Sortino: check what's happening with weekly resampling
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

# === Reconstruct what engine does for Sortino ===
# Get equity from trades
from backend.backtesting.engine import build_equity_from_trades

trades = result.trades
closed = [t for t in trades if not getattr(t, "is_open", False)]

# Build equity manually (same as engine)
equity_list, timestamps_list, _ = build_equity_from_trades(trades, 10000.0, df)
equity_arr = np.array(equity_list)
print(f"equity_arr length: {len(equity_arr)}")
print(f"timestamps_list length: {len(timestamps_list)}")
print(f"timestamps sample: {timestamps_list[:3]}")
print(f"timestamps type sample: {type(timestamps_list[0]) if timestamps_list else 'N/A'}")
print()

# Weekly resampling
ts_idx = pd.DatetimeIndex(timestamps_list)
ec_series = pd.Series(equity_arr, index=ts_idx)
print(f"ec_series index type: {ec_series.index.dtype}")
print(f"ec_series index sample: {ec_series.index[:3]}")
print(f"ec_series is tz-aware: {ec_series.index.tz}")
print()

weekly_eq = ec_series.resample("W-SUN").last().ffill()
print(f"weekly_eq length: {len(weekly_eq)}")
print(f"weekly_eq:\n{weekly_eq.to_string()}")
print()

weekly_r = weekly_eq.pct_change().dropna().values
print(f"weekly_r length: {len(weekly_r)}")
print(f"weekly_r: {weekly_r}")
print()

wm = float(np.mean(weekly_r))
wneg = np.minimum(0.0, weekly_r)
wdd = float(np.sqrt(np.sum(wneg**2) / len(weekly_r)))
print(f"weekly mean: {wm:.6f}")
print(f"weekly downside std: {wdd:.6f}")
if wdd > 1e-10:
    sortino_weekly = float(np.clip(wm / wdd * np.sqrt(52), -100, 100))
    print(f"Sortino (W-SUN, sqrt(52)): {sortino_weekly:.4f}  (TV: 16.708)")

    # Try different annualization factors
    for ppyr in [52, 57.2, 48, 56, 53, 54, 55]:
        s = wm / wdd * np.sqrt(ppyr)
        print(f"  sqrt({ppyr}): {s:.4f}")
else:
    print("wdd too small!")

print(f"\nEngine result sortino_ratio: {m.sortino_ratio:.4f}")
print(f"Engine result sharpe_ratio:  {m.sharpe_ratio:.4f}")
