"""Check entry_bar vs exit_bar gap across all trades."""

import datetime as dt
import json
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"

conn = sqlite3.connect(DB_PATH)
row = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,)).fetchone()
col_names = [d[0] for d in conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,)).description]
conn.close()
strat = dict(zip(col_names, row, strict=False))
builder_blocks = json.loads(strat["builder_blocks"])
builder_connections = json.loads(strat["builder_connections"])
builder_graph_raw = json.loads(strat["builder_graph"])
strategy_graph = {
    "name": strat["name"],
    "description": strat.get("description") or "",
    "blocks": builder_blocks,
    "connections": builder_connections,
    "market_type": "linear",
    "direction": "both",
    "interval": "15",
}
if builder_graph_raw and builder_graph_raw.get("main_strategy"):
    strategy_graph["main_strategy"] = builder_graph_raw["main_strategy"]

ohlcv_conn = sqlite3.connect(DB_PATH)
start_ms = int(dt.datetime(2025, 11, 1, tzinfo=dt.UTC).timestamp() * 1000)
end_ms = int(dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC).timestamp() * 1000)
df = pd.read_sql_query(
    "SELECT open_time, open_price as [open], high_price as high, low_price as low, "
    "close_price as close, volume FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
    "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
    ohlcv_conn,
    params=(start_ms, end_ms),
)
ohlcv_conn.close()
df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
ohlcv = df.set_index("timestamp").drop(columns=["open_time"])

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

adapter = StrategyBuilderAdapter(strategy_graph)
params = json.loads(strat["parameters"])
config = BacktestConfig(
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
result = engine.run(config, ohlcv, custom_strategy=adapter)
trades = result.trades

print("Trades with exit_bar <= entry_bar + 1:")
for i, t in enumerate(trades):
    gap = t.exit_bar_index - t.entry_bar_index
    if gap <= 1:
        print(
            f"  Trade #{i + 1}: entry_bar={t.entry_bar_index} exit_bar={t.exit_bar_index} gap={gap} "
            f"entry={t.entry_price:.2f} exit={t.exit_price:.2f} pnl={t.pnl:.2f}"
        )

print("\nAll trades bar gap distribution:")
gaps = [t.exit_bar_index - t.entry_bar_index for t in trades]
from collections import Counter

c = Counter(gaps)
for k in sorted(c.keys())[:20]:
    print(f"  gap={k}: {c[k]} trades")
