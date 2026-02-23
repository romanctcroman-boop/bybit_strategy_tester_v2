"""Dump all PerformanceMetrics fields from the backtest engine result."""

import datetime as dt
import json
import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///data.sqlite3")

from loguru import logger

logger.remove()

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB = "data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"

conn = sqlite3.connect(DB)
row = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,)).fetchone()
cols = [d[0] for d in conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,)).description]
conn.close()
strat = dict(zip(cols, row, strict=False))

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
    "close_price as close, volume FROM bybit_kline_audit "
    "WHERE symbol=? AND interval=? AND market_type=? AND open_time>=? AND open_time<=? ORDER BY open_time ASC",
    conn2,
    params=("BTCUSDT", "15", "linear", start_ms, end_ms),
)
conn2.close()
df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df = df.set_index("timestamp").drop(columns=["open_time"])

params = json.loads(strat["parameters"])
cfg = BacktestConfig(
    symbol="BTCUSDT",
    interval="15",
    start_date=dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
    end_date=dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC),
    initial_capital=10000.0,
    commission_value=float(params.get("_commission", 0.0007)),
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

print("=== PerformanceMetrics fields ===")
for field in m.model_fields:
    val = getattr(m, field, None)
    print(f"  {field}: {val}")

# Also print trade stats
closed = [t for t in result.trades if not getattr(t, "is_open", False)]
wins = [t for t in closed if t.pnl > 0]
losses = [t for t in closed if t.pnl < 0]
longs = [t for t in closed if t.side in ("buy", "long")]
shorts = [t for t in closed if t.side in ("sell", "short")]
long_wins = [t for t in longs if t.pnl > 0]
long_losses = [t for t in longs if t.pnl < 0]
short_wins = [t for t in shorts if t.pnl > 0]
short_losses = [t for t in shorts if t.pnl < 0]

print("\n=== Trade stats ===")
print(f"  closed={len(closed)}, wins={len(wins)}, losses={len(losses)}")
print(f"  longs={len(longs)}: {len(long_wins)}W/{len(long_losses)}L")
print(f"  shorts={len(shorts)}: {len(short_wins)}W/{len(short_losses)}L")

import numpy as np

bars_all = [getattr(t, "bars_in_trade", 0) or 0 for t in closed]
bars_win = [getattr(t, "bars_in_trade", 0) or 0 for t in wins]
bars_loss = [getattr(t, "bars_in_trade", 0) or 0 for t in losses]
bars_long = [getattr(t, "bars_in_trade", 0) or 0 for t in longs]
bars_short = [getattr(t, "bars_in_trade", 0) or 0 for t in shorts]

print("\n=== Avg bars ===")
print(f"  avg all: {np.mean(bars_all):.1f}  (TV=74)")
print(f"  avg win: {np.mean(bars_win):.1f}  (TV=66)")
print(f"  avg loss: {np.mean(bars_loss):.1f}  (TV=101)")
print(f"  avg long: {np.mean(bars_long):.1f}  (TV=56)")
print(f"  avg short: {np.mean(bars_short):.1f}  (TV=88)")

avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0
avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0
print("\n=== Avg win/loss ===")
print(f"  avg_win={avg_win:.2f}  (TV=13.71)")
print(f"  avg_loss={avg_loss:.2f}  (TV=-33.43)")
print(f"  ratio={abs(avg_win / avg_loss):.3f}  (TV=0.41)")

long_avg_win = sum(t.pnl for t in long_wins) / len(long_wins) if long_wins else 0
long_avg_loss = sum(t.pnl for t in long_losses) / len(long_losses) if long_losses else 0
short_avg_win = sum(t.pnl for t in short_wins) / len(short_wins) if short_wins else 0
short_avg_loss = sum(t.pnl for t in short_losses) / len(short_losses) if short_losses else 0
print(f"  long avg_win={long_avg_win:.2f}  (TV=13.84)")
print(f"  long avg_loss={long_avg_loss:.2f}  (TV=-33.38)")
print(f"  short avg_win={short_avg_win:.2f}  (TV=13.61)")
print(f"  short avg_loss={short_avg_loss:.2f}  (TV=-33.47)")

open_trades = [t for t in result.trades if getattr(t, "is_open", False)]
if open_trades:
    ot = open_trades[0]
    print("\n=== Open position (unrealized) ===")
    print(f"  side={ot.side}, entry={ot.entry_price}, exit(last)={ot.exit_price}, pnl={ot.pnl:.2f}  (TV=-10.93)")
