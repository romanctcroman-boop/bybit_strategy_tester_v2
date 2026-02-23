"""Quick inspection of EquityCurve and bar-by-bar returns"""

import datetime as dt
import json
import os
import sqlite3
import sys

import numpy as np

sys.path.insert(0, "d:\\bybit_strategy_tester_v2")
os.environ.setdefault("DATABASE_URL", "sqlite:///data.sqlite3")
from loguru import logger

logger.remove()

import pandas as pd

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
    "SELECT open_time, open_price as open, high_price as high, low_price as low, close_price as close, volume "
    "FROM bybit_kline_audit WHERE symbol=? AND interval=? AND market_type=? AND open_time>=? AND open_time<=? ORDER BY open_time ASC",
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

ec_obj = result.equity_curve
print("EquityCurve type:", type(ec_obj))
print("EquityCurve attrs:", [a for a in dir(ec_obj) if not a.startswith("_")])
print()

for attr in ["values", "equity", "data", "curve", "returns", "timestamps", "dates"]:
    v = getattr(ec_obj, attr, None)
    if v is not None:
        try:
            arr = np.array(v)
            print(f"  .{attr}: shape={arr.shape}, first3={arr.flat[:3]}")
        except Exception as e:
            print(f"  .{attr}: error={e}")

# Try model_dump
try:
    d = ec_obj.model_dump() if hasattr(ec_obj, "model_dump") else ec_obj.dict()
    print("\nmodel_dump keys:", list(d.keys())[:10])
    for k, v in d.items():
        if hasattr(v, "__len__"):
            print(f"  {k}: len={len(v)}, first3={v[:3] if len(v) >= 3 else v}")
        else:
            print(f"  {k}: {v}")
except Exception as e:
    print(f"model_dump error: {e}")
