"""
Run generate_signals directly to see all RSI signals without the engine.
Compare signal count vs TV trade count.
"""

import asyncio
import json
import sqlite3
import sys

sys.path.insert(0, "D:/bybit_strategy_tester_v2")

STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"
DB_PATH = "D:/bybit_strategy_tester_v2/data.sqlite3"


async def main():
    # Load strategy from DB
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT builder_graph, builder_blocks, builder_connections, name, symbol, timeframe FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()

    if not row:
        print("Strategy not found!")
        return

    builder_graph = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
    builder_blocks = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or [])
    builder_connections = json.loads(row[2]) if isinstance(row[2], str) else (row[2] or [])
    name = row[3]
    symbol = row[4] or "BTCUSDT"
    timeframe = row[5] or "15"

    print(f"Strategy: {name}")
    print(f"Symbol: {symbol} TF: {timeframe}")
    print(f"Blocks: {[b.get('type') for b in builder_blocks]}")

    # Build strategy_graph
    strategy_graph = {
        "name": name,
        "blocks": builder_blocks,
        "connections": builder_connections,
        "interval": timeframe,
        "direction": "both",
    }
    if builder_graph.get("main_strategy"):
        strategy_graph["main_strategy"] = builder_graph["main_strategy"]

    # Get OHLCV data via BacktestService
    import pandas as pd

    from backend.backtesting.service import BacktestService
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    svc = BacktestService()
    start_dt = pd.Timestamp("2025-11-01", tz="UTC")
    end_dt = pd.Timestamp("2026-02-23", tz="UTC")
    print(f"Fetching {symbol} {timeframe}m from {start_dt.date()} to {end_dt.date()}...")

    ohlcv = await svc._fetch_historical_data(symbol=symbol, interval=timeframe, start_date=start_dt, end_date=end_dt)
    if ohlcv is None or len(ohlcv) == 0:
        print("No OHLCV data!")
        return

    print(f"OHLCV: {len(ohlcv)} bars  {ohlcv.index[0]} to {ohlcv.index[-1]}")

    # Generate signals
    sba = StrategyBuilderAdapter(strategy_graph)
    result_raw = sba.generate_signals(ohlcv)

    # Handle SignalResult
    if not hasattr(result_raw, "entries"):
        print(f"Unknown result type: {type(result_raw)}")
        print(f"Attributes: {[a for a in dir(result_raw) if not a.startswith('_')]}")
        return

    entries = result_raw.entries
    short_entries = result_raw.short_entries

    long_count = int(entries.sum()) if hasattr(entries, "sum") else 0
    short_count = int(short_entries.sum()) if hasattr(short_entries, "sum") else 0
    print(f"\nSignals: long={long_count} short={short_count} total={long_count + short_count}")
    print("TV total: 129 (57 long + 72 short)\n")

    # First signal times
    import numpy as np
    import pandas as pd

    long_idx = np.where(np.array(entries).astype(bool))[0][:15]
    short_idx = np.where(np.array(short_entries).astype(bool))[0][:15]
    long_times = ohlcv.index[long_idx]
    short_times = ohlcv.index[short_idx]

    print("First 15 LONG signal bars (UTC):")
    for t in long_times:
        t_plus3 = pd.Timestamp(t) + pd.Timedelta(hours=3)
        print(f"  UTC: {t}  | +3h(Moscow?): {t_plus3}")
    print("\nFirst 15 SHORT signal bars (UTC):")
    for t in short_times:
        t_plus3 = pd.Timestamp(t) + pd.Timedelta(hours=3)
        print(f"  UTC: {t}  | +3h(Moscow?): {t_plus3}")

    print()
    print("TV first 5 entries (TV timestamp, likely UTC+3 Moscow or exchange time):")
    print("  short 2025-11-01 09:45  (RSI short)")
    print("  long  2025-11-03 08:15")
    print("  long  2025-11-04 09:15")
    print("  long  2025-11-04 21:45")
    print("  short 2025-11-05 23:45")


asyncio.run(main())
