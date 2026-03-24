"""Check RSI-1 strategy connections and run backtest directly."""

import json
import sqlite3
import sys

sys.path.insert(0, ".")

STRATEGY_ID = "824561e0-5e27-4be4-a33a-b064a726d14c"
DB_PATH = "data.sqlite3"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?", (STRATEGY_ID,))
row = cur.fetchone()
conn.close()

if not row:
    print("NOT FOUND")
    exit()

blocks_raw, conns_raw, graph_raw = row
blocks = json.loads(blocks_raw) if blocks_raw else []
conns = json.loads(conns_raw) if conns_raw else []
graph = json.loads(graph_raw) if graph_raw else {}
graph_conns = graph.get("connections", [])

print("=== CONNECTIONS (builder_connections) ===")
for c in conns:
    src = c.get("source") or c
    tgt = c.get("target") or c
    src_block = src.get("blockId", c.get("from", "?"))
    src_port = src.get("portId", c.get("fromPort", "?"))
    tgt_block = tgt.get("blockId", c.get("to", "?"))
    tgt_port = tgt.get("portId", c.get("toPort", "?"))
    print(f"  {src_block}.{src_port} → {tgt_block}.{tgt_port}")

print("\n=== CONNECTIONS (builder_graph) ===")
for c in graph_conns:
    src = c.get("source") or c
    tgt = c.get("target") or c
    src_block = src.get("blockId", c.get("from", "?"))
    src_port = src.get("portId", c.get("fromPort", "?"))
    tgt_block = tgt.get("blockId", c.get("to", "?"))
    tgt_port = tgt.get("portId", c.get("toPort", "?"))
    print(f"  {src_block}.{src_port} → {tgt_block}.{tgt_port}")

# Now run backtest directly with the stored graph
print("\n=== RUNNING BACKTEST WITH STORED GRAPH ===")
import asyncio
from datetime import UTC, datetime


async def run_bt():
    from backend.backtesting.service import BacktestService
    from backend.optimization.builder_optimizer import run_builder_backtest

    svc = BacktestService()
    ohlcv = await svc._fetch_historical_data(
        symbol="ETHUSDT",
        interval="30",
        start_date=datetime(2025, 1, 1, tzinfo=UTC),
        end_date=datetime(2026, 1, 1, tzinfo=UTC),
        market_type="linear",
    )
    print(f"OHLCV loaded: {len(ohlcv)} bars")

    strategy_graph = {
        "name": "RSI-1",
        "blocks": blocks,
        "connections": graph_conns or conns,
        "interval": "30",
        "market_type": "linear",
        "direction": "both",
    }

    config = {
        "symbol": "ETHUSDT",
        "interval": "30",
        "initial_capital": 10000.0,
        "leverage": 10,
        "position_size": 0.1,
        "commission": 0.0007,
        "direction": "both",
    }

    result = run_builder_backtest(strategy_graph, ohlcv, config)
    if result:
        print(f"Total trades:  {result.get('total_trades')}")
        print(f"Net profit:    ${result.get('net_profit', 0):.2f}")
        print(f"Sharpe:        {result.get('sharpe_ratio', 0):.4f}")
        print(f"Win rate:      {result.get('win_rate', 0):.2f}%")
    else:
        print("No result returned")


asyncio.run(run_bt())
