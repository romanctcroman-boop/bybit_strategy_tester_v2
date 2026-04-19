"""Debug avg_margin — exhaustive boundary search including open trades"""

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
TV = 852.53

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
open_trades = [t for t in result.trades if getattr(t, "is_open", False)]
all_trades = result.trades

print(f"closed={len(closed_trades)}, open={len(open_trades)}")
if open_trades:
    ot = open_trades[0]
    print(
        f"Open trade: eb={getattr(ot, 'entry_bar_index', None)}, xb={getattr(ot, 'exit_bar_index', None)}, qty={getattr(ot, 'size', None)}"
    )
print()

# ── Exhaustive boundary search ───────────────────────────────────────────────
results = []
for trade_label, trades_use in [("closed", closed_trades), ("all", all_trades)]:
    for so in [0, 1, 2]:  # start offset from eb
        for eo in [-1, 0, 1]:  # end offset: -1=xb-1, 0=xb(excl), 1=xb(incl)
            mvs = np.zeros(total_bars)
            for t in trades_use:
                eb = getattr(t, "entry_bar_index", None)
                xb = getattr(t, "exit_bar_index", None)
                qty = abs(getattr(t, "size", 0) or 0)
                if eb is None or qty == 0:
                    continue
                xb_eff = (xb if xb is not None else total_bars - 1) + eo + 1
                start_b = eb + so
                for b in range(start_b, min(xb_eff, total_bars)):
                    mvs[b] = qty * close_arr[b]
            avg = float(mvs.mean())
            diff = abs(avg - TV) / TV * 100
            end_desc = f"xb{eo:+d}" if eo != 0 else "xb(excl)"
            label = f"{trade_label} eb+{so}..{end_desc}"
            results.append((diff, label, avg))

results.sort()
print("Top 10 closest to TV 852.53:")
for diff, label, avg in results[:10]:
    mark = "[OK]" if diff < 0.5 else ("[~~]" if diff < 2 else "")
    print(f"  {label:40s}: {avg:.4f}  ({diff:.2f}%) {mark}")

print()
print(f"TV target: {TV}")
print(f"Engine current: {result.metrics.avg_margin_used:.4f}")
