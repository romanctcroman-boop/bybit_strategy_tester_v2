"""Debug trade #100 entry/exit bar indices."""

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
t100 = trades[99]  # 0-indexed trade 100
print("Trade 100:")
print(f"  side={t100.side} entry={t100.entry_price} exit={t100.exit_price} pnl={t100.pnl:.2f}")
print(f"  entry_bar={t100.entry_bar_index} exit_bar={t100.exit_bar_index}")
print(f"  entry_time={t100.entry_time} exit_time={t100.exit_time}")

# Show ohlcv at entry and next bars
ts_list = list(ohlcv.index)
ebar = t100.entry_bar_index
xbar = t100.exit_bar_index
for b in range(max(0, ebar - 1), min(len(ts_list), xbar + 2)):
    o = ohlcv.iloc[b]["open"]
    h = ohlcv.iloc[b]["high"]
    lo = ohlcv.iloc[b]["low"]
    c = ohlcv.iloc[b]["close"]
    marker = " <<< ENTRY" if b == ebar else (" <<< EXIT" if b == xbar else "")
    print(f"  bar[{b}] {ts_list[b].isoformat()} O={o:.2f} H={h:.2f} L={lo:.2f} C={c:.2f}{marker}")

print(f"\nTP target = 61334.10 * 1.015 = {61334.10 * 1.015:.2f}")
if ebar + 1 < len(ts_list):
    o_next = ohlcv.iloc[ebar + 1]["open"]
    print(f"Open of bar[entry+1] = {o_next:.2f}")
    print(f"Gap-through? {o_next >= 61334.10 * 1.015}")

# Also check entry_bar open
o_entry = ohlcv.iloc[ebar]["open"]
print(f"\nEntry bar open = {o_entry:.2f}")
print(f"Entry price in trade = {t100.entry_price:.2f}")
print("=> TV entry = close of signal bar (00:15 UTC close = 61334.10)")
print("=> Our entry = close of signal bar? or open of next bar?")
