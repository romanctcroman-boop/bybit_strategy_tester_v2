"""Debug avg_margin_used — compare different formulas vs TV 852.53"""

import datetime as dt
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
os.environ.setdefault("DATABASE_URL", "sqlite:///data.sqlite3")

from loguru import logger

logger.remove()

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"
TV_AVG_MARGIN = 852.53

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

close_arr = df["close"].values
total_bars = len(close_arr)
leverage = 10.0
closed_trades = [t for t in result.trades if not getattr(t, "is_open", False)]

print(f"Engine avg_margin_used: {result.metrics.avg_margin_used:.4f}  (TV: {TV_AVG_MARGIN})")
print(f"Engine max_margin_used: {result.metrics.max_margin_used:.4f}  (TV: 1033.35)")
print()

# ── Rebuild mvs_bar ──────────────────────────────────────────────────────────
mvs_bar = np.zeros(total_bars)
for t in closed_trades:
    eb = getattr(t, "entry_bar_index", None)
    xb = getattr(t, "exit_bar_index", None)
    qty = abs(getattr(t, "size", 0) or 0)
    if eb is None or xb is None or qty == 0:
        continue
    for b in range(eb, min(xb + 1, total_bars)):
        mvs_bar[b] = qty * close_arr[b]  # position value (margin_long_pct=1.0 → no /leverage)

n_nonzero = int(np.count_nonzero(mvs_bar))
print(f"Total bars:          {total_bars}")
print(f"In-position bars:    {n_nonzero}  ({n_nonzero / total_bars * 100:.1f}%)")
print(f"Flat bars:           {total_bars - n_nonzero}")
print()

# Formula candidates
avg_all = float(mvs_bar.mean())
avg_nonzero = float(mvs_bar[mvs_bar > 0].mean())
max_mv = float(mvs_bar.max())

print(f"avg ALL bars (current):   {avg_all:.4f}  diff={abs(avg_all - TV_AVG_MARGIN) / TV_AVG_MARGIN * 100:.2f}%")
print(
    f"avg IN-POSITION bars:     {avg_nonzero:.4f}  diff={abs(avg_nonzero - TV_AVG_MARGIN) / TV_AVG_MARGIN * 100:.2f}%"
)
print(f"max position value:       {max_mv:.4f}")
print()

# Per-trade formulas
entry_margins = [abs(getattr(t, "size", 0)) * getattr(t, "entry_price", 0) / leverage for t in closed_trades]
exit_margins = [abs(getattr(t, "size", 0)) * getattr(t, "exit_price", 0) / leverage for t in closed_trades]
mid_margins = [(e + x) / 2 for e, x in zip(entry_margins, exit_margins, strict=False)]
durations = [
    max(1, (getattr(t, "exit_bar_index", 0) or 0) - (getattr(t, "entry_bar_index", 0) or 0)) for t in closed_trades
]

avg_entry = float(np.mean(entry_margins))
avg_exit = float(np.mean(exit_margins))
avg_mid = float(np.mean(mid_margins))
avg_dur_wtd = float(np.average(entry_margins, weights=durations))

print(
    f"avg per-trade entry margin:      {avg_entry:.4f}  diff={abs(avg_entry - TV_AVG_MARGIN) / TV_AVG_MARGIN * 100:.2f}%"
)
print(
    f"avg per-trade exit margin:       {avg_exit:.4f}  diff={abs(avg_exit - TV_AVG_MARGIN) / TV_AVG_MARGIN * 100:.2f}%"
)
print(f"avg per-trade mid margin:        {avg_mid:.4f}  diff={abs(avg_mid - TV_AVG_MARGIN) / TV_AVG_MARGIN * 100:.2f}%")
print(
    f"avg duration-weighted entry:     {avg_dur_wtd:.4f}  diff={abs(avg_dur_wtd - TV_AVG_MARGIN) / TV_AVG_MARGIN * 100:.2f}%"
)
print()

# Same but without /leverage (position value)
entry_posval = [abs(getattr(t, "size", 0)) * getattr(t, "entry_price", 0) for t in closed_trades]
print(f"avg per-trade position value:    {float(np.mean(entry_posval)):.4f}  (no leverage)")
print()

# TV hint: margin = initial_capital * position_size (percent of capital)?
pos_size = 0.1  # 10%
initial_capital = 10000.0
print(f"capital * pos_size * leverage:   {initial_capital * pos_size:.4f}  (flat)")
print()
print(f"TV target: {TV_AVG_MARGIN}")
