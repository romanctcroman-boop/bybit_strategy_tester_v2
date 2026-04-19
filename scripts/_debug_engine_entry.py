"""
Debug script: trace exactly what signals the engine receives and what trades it generates.
Runs the same flow as the API endpoint.
"""

import sys

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import json
import sqlite3
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"


def load_strategy():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,)).fetchone()
    conn.close()
    return dict(row)


def load_ohlcv(symbol="BTCUSDT", interval="15", start="2025-11-01", end="2026-02-23"):
    """Load OHLCV from the klines database."""
    conn = sqlite3.connect(DB_PATH)

    start_ms = int(datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=UTC).timestamp() * 1000)

    df = pd.read_sql_query(
        """
        SELECT open_time, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol=? AND interval=?
        AND open_time >= ? AND open_time <= ?
        ORDER BY open_time ASC
    """,
        conn,
        params=(symbol, interval, start_ms, end_ms),
    )
    conn.close()

    if df.empty:
        print("No OHLCV data found!")
        return None
    df.index = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.drop(columns=["open_time"])
    print(f"Loaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    return df


def main():
    strat = load_strategy()

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

    # Build strategy graph
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

    # Create adapter
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    adapter = StrategyBuilderAdapter(strategy_graph)

    # Load OHLCV
    ohlcv = load_ohlcv()
    if ohlcv is None:
        return

    # Generate signals
    print("\n=== GENERATING SIGNALS ===")
    signals = adapter.generate_signals(ohlcv)

    print(f"Total bars: {len(ohlcv)}")
    print(f"Long entries: {signals.entries.sum()}")
    print(f"Short entries: {signals.short_entries.sum() if signals.short_entries is not None else 0}")

    # Check first 50 bars for any signals
    print("\n=== FIRST 50 BARS SIGNALS ===")
    n = 50
    long_arr = np.asarray(signals.entries.values, dtype=bool)
    short_arr = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(long_arr), dtype=bool)
    )

    for i in range(min(n, len(ohlcv))):
        ts = ohlcv.index[i]
        has_long = long_arr[i]
        has_short = short_arr[i]
        if has_long or has_short:
            print(f"  Bar {i:3d} UTC={ts} close={ohlcv['close'].iloc[i]:.2f} | long={has_long} short={has_short}")

    # Now simulate engine behavior manually for first 50 bars
    print("\n=== ENGINE SIMULATION (first 50 bars) ===")
    close = ohlcv["close"].values
    slippage = 0.0005
    direction = "both"
    position = 0.0

    for i in range(min(50, len(ohlcv))):
        ts = ohlcv.index[i]
        price = close[i]

        if position == 0:
            if direction in ("long", "both") and long_arr[i]:
                entry_price = price * (1 + slippage)
                print(f"  Bar {i:3d} UTC={ts} LONG ENTRY: close={price:.2f} entry={entry_price:.2f}")
                position = 1
            elif direction in ("short", "both") and short_arr[i]:
                entry_price = price * (1 - slippage)
                print(f"  Bar {i:3d} UTC={ts} SHORT ENTRY: close={price:.2f} entry={entry_price:.2f}")
                position = -1

    # Check bar index 6 specifically (2025-11-01 01:45 UTC)
    # Nov 1 00:00 UTC is bar 0, 01:45 UTC is bar 7 (0-indexed)
    print("\n=== CHECKING BAR AT 01:45 UTC NOV 1 ===")
    target = pd.Timestamp("2025-11-01 01:45:00", tz="UTC")
    if target in ohlcv.index:
        idx = ohlcv.index.get_loc(target)
        print(f"Bar index: {idx}")
        print(f"Timestamp: {ohlcv.index[idx]}")
        print(f"Close: {ohlcv['close'].iloc[idx]:.2f}")
        print(f"Entry price with slippage: {ohlcv['close'].iloc[idx] * (1 - slippage):.2f}")
        print(f"long_arr[{idx}]: {long_arr[idx]}")
        print(f"short_arr[{idx}]: {short_arr[idx]}")

        # Also show bars 0-15 with their signal status
        print("\n=== BARS 0-15 ===")
        for i in range(min(16, len(ohlcv))):
            print(
                f"  [{i:2d}] {ohlcv.index[i]} close={ohlcv['close'].iloc[i]:.2f} long={long_arr[i]} short={short_arr[i]}"
            )
    else:
        print("Bar 01:45 UTC NOT FOUND in index!")
        # Find closest
        closest = min(ohlcv.index[:20], key=lambda x: abs((x - target).total_seconds()))
        print(f"Closest bar: {closest}")


if __name__ == "__main__":
    main()
