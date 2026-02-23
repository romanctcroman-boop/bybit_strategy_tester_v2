"""Debug trade #100 exit reason."""

import datetime as dt
import json
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()

DB = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRAT = "5a1741ac-ad9e-4285-a9d6-58067c56407a"

conn = sqlite3.connect(DB)
row = conn.execute("SELECT * FROM strategies WHERE id=?", (STRAT,)).fetchone()
cols = [d[0] for d in conn.execute("SELECT * FROM strategies WHERE id=?", (STRAT,)).description]
conn.close()
strat = dict(zip(cols, row, strict=False))
sg = json.loads(strat["builder_graph"])
sg.update(
    {
        "name": strat["name"],
        "description": "",
        "blocks": json.loads(strat["builder_blocks"]),
        "connections": json.loads(strat["builder_connections"]),
        "market_type": "linear",
        "direction": "both",
        "interval": "15",
    }
)

conn2 = sqlite3.connect(DB)
df = pd.read_sql_query(
    "SELECT open_time, open_price as [open], high_price as high, low_price as low, "
    "close_price as close, volume FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
    "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
    conn2,
    params=(
        int(dt.datetime(2025, 11, 1, tzinfo=dt.UTC).timestamp() * 1000),
        int(dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC).timestamp() * 1000),
    ),
)
conn2.close()
df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
ohlcv = df.set_index("timestamp").drop(columns=["open_time"])

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

cfg = BacktestConfig(
    symbol="BTCUSDT",
    interval="15",
    start_date=dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
    end_date=dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC),
    initial_capital=10000.0,
    commission_value=0.0007,
    slippage=0.0,
    leverage=10.0,
    position_size=0.1,
    pyramiding=1,
    direction="both",
    stop_loss=0.032,
    take_profit=0.015,
)
adapter = StrategyBuilderAdapter(sg)
result = BacktestEngine().run(cfg, ohlcv, custom_strategy=adapter)
t = result.trades[99]
print("Trade #100:")
print(f"  side        = {t.side}")
print(f"  entry_price = {t.entry_price}")
print(f"  exit_price  = {t.exit_price}")
print(f"  pnl         = {t.pnl:.4f}")
print(f"  entry_bar   = {t.entry_bar_index}")
print(f"  exit_bar    = {t.exit_bar_index}")
print(f"  exit_reason = {getattr(t, 'exit_reason', 'N/A')}")
print(f"  entry_time  = {t.entry_time}")
print(f"  exit_time   = {t.exit_time}")

# Show bar range
ebar = t.entry_bar_index
xbar = t.exit_bar_index
ts = list(ohlcv.index)
print()
for b in range(max(0, ebar - 1), min(len(ts), xbar + 3)):
    row_o = ohlcv.iloc[b]
    marker = " <<< ENTRY" if b == ebar else (" <<< EXIT" if b == xbar else "")
    print(f"  bar[{b}] O={row_o['open']:.2f} H={row_o['high']:.2f} L={row_o['low']:.2f} C={row_o['close']:.2f}{marker}")
