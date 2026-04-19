"""Check summary statistics vs TradingView reported results."""

import json
import sqlite3
import sys
from datetime import UTC, datetime

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"

conn = sqlite3.connect(DB_PATH)
row = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,)).fetchone()
col_names = [d[0] for d in conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,)).description]
conn.close()
strat = dict(zip(col_names, row, strict=False))

builder_blocks = (
    json.loads(strat["builder_blocks"]) if isinstance(strat["builder_blocks"], str) else strat["builder_blocks"]
)
builder_connections = (
    json.loads(strat["builder_connections"])
    if isinstance(strat["builder_connections"], str)
    else strat["builder_connections"]
)
builder_graph_raw = (
    json.loads(strat["builder_graph"]) if isinstance(strat["builder_graph"], str) else strat["builder_graph"]
)

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

from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

adapter = StrategyBuilderAdapter(strategy_graph)

conn2 = sqlite3.connect(DB_PATH)
start_ms = int(datetime(2025, 11, 1, tzinfo=UTC).timestamp() * 1000)
end_ms = int(datetime(2026, 2, 23, 23, 59, tzinfo=UTC).timestamp() * 1000)
ohlcv = pd.read_sql_query(
    "SELECT open_time, open_price as open, high_price as high, low_price as low, close_price as close, volume "
    "FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
    "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
    conn2,
    params=(start_ms, end_ms),
)
conn2.close()
ohlcv["timestamp"] = pd.to_datetime(ohlcv["open_time"], unit="ms", utc=True)
ohlcv = ohlcv.set_index("timestamp").drop(columns=["open_time"])

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig

params = json.loads(strat["parameters"]) if isinstance(strat["parameters"], str) else strat["parameters"]

config = BacktestConfig(
    symbol="BTCUSDT",
    interval="15",
    start_date=datetime(2025, 11, 1, tzinfo=UTC),
    end_date=datetime(2026, 2, 23, 23, 59, tzinfo=UTC),
    initial_capital=10000.0,
    commission_value=float(params.get("_commission", 0.0007)),
    slippage=float(params.get("_slippage", 0.0005)),
    leverage=float(params.get("_leverage", 10.0)),
    position_size=0.1,
    pyramiding=int(params.get("_pyramiding", 1)),
    direction="both",
    stop_loss=0.032,
    take_profit=0.015,
)

engine = BacktestEngine()
result = engine.run(config, ohlcv, custom_strategy=adapter)

trades = result.trades
winning = [t for t in trades if t.pnl > 0]
losing = [t for t in trades if t.pnl < 0]
total_pnl = sum(t.pnl for t in trades)
initial = config.initial_capital
final_equity = initial + total_pnl

print("=" * 60)
print("OUR ENGINE RESULTS")
print("=" * 60)
print(f"Total trades:      {len(trades)}")
print(f"Winning trades:    {len(winning)} ({100 * len(winning) / len(trades):.1f}%)")
print(f"Losing trades:     {len(losing)} ({100 * len(losing) / len(trades):.1f}%)")
print(f"Total PnL:         ${total_pnl:.2f}")
print(f"Net return:        {100 * total_pnl / initial:.2f}%")
print(f"Final equity:      ${final_equity:.2f}")
print()
print("=" * 60)
print("TRADINGVIEW REPORTED")
print("=" * 60)
print("Total trades:      129")
print("Winning trades:    101 (78.3%)")
print("Losing trades:     28 (21.7%)")
print("Net return:        +4.83%  (cum PnL = $481.32)")
print("Final equity:      $10481.32")
