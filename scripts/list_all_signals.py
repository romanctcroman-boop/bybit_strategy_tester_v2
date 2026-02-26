"""
Analyze signals during overlapping windows to find the missing trade.
Compare our trade timeline with potential extra signal.
"""

import sys

sys.path.insert(0, "d:\\bybit_strategy_tester_v2")

import asyncio
from datetime import datetime, timezone

import pandas as pd


async def main():
    import json
    import sqlite3

    from backend.backtesting.service import BacktestService
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    # Load strategy
    conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
    c = conn.cursor()
    c.execute(
        "SELECT builder_blocks, builder_connections, builder_graph FROM strategies WHERE id = '01cd8861-60eb-40dd-a9a9-8baa6f2db0fa'"
    )
    row = c.fetchone()
    conn.close()
    blocks = json.loads(row[0]) if row[0] else []
    connections = json.loads(row[1]) if row[1] else []
    builder_graph = json.loads(row[2]) if row[2] else {}
    strategy_graph = {
        "blocks": blocks,
        "connections": connections,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if builder_graph.get("main_strategy"):
        strategy_graph["main_strategy"] = builder_graph["main_strategy"]

    svc = BacktestService()
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 2, 25, tzinfo=timezone.utc)
    _btc_start = start_date - pd.Timedelta(minutes=500 * 30)

    btc_ohlcv = await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="30",
        start_date=_btc_start,
        end_date=end_date,
        market_type="linear",
    )
    eth_ohlcv = await svc._fetch_historical_data(
        symbol="ETHUSDT",
        interval="30",
        start_date=start_date,
        end_date=end_date,
        market_type="linear",
    )

    adapter = StrategyBuilderAdapter(strategy_graph, btcusdt_ohlcv=btc_ohlcv)
    signals = adapter.generate_signals(eth_ohlcv)

    # Get all signal timestamps
    long_signals = eth_ohlcv.index[signals.entries]
    short_signals = eth_ohlcv.index[signals.short_entries]

    print(f"Long signals: {len(long_signals)}")
    print(f"Short signals: {len(short_signals)}")
    print()

    # Show ALL signals with timing
    print("ALL signals (chronological):")
    all_sigs = [(t, "LONG") for t in long_signals] + [(t, "SHORT") for t in short_signals]
    all_sigs.sort(key=lambda x: x[0])
    for t, typ in all_sigs:
        print(f"  {t}  {typ}")


asyncio.run(main())
