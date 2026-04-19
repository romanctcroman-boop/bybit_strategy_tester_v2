"""
Find why our engine picks a DIFFERENT long signal than TV after trade #1 exits.
Both engines exit trade #1 at 03:00 UTC Nov 3 (TP hit).
TV picks long at 05:15 UTC Nov 3 but our engine picks 06:45 UTC Nov 3.
"""

import json
import sqlite3
import sys
from datetime import UTC, datetime

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"


def load_ohlcv():
    conn = sqlite3.connect(DB_PATH)
    start_ms = int(datetime(2025, 11, 1, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime(2026, 2, 23, tzinfo=UTC).timestamp() * 1000)
    df = pd.read_sql_query(
        "SELECT open_time, open_price as open, high_price as high, "
        "low_price as low, close_price as close, volume "
        "FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
        "AND open_time >= ? AND open_time <= ? "
        "ORDER BY open_time ASC",
        conn,
        params=(start_ms, end_ms),
    )
    conn.close()
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("timestamp").drop(columns=["open_time"])


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cursor.fetchone()
    col_names = [d[0] for d in cursor.description]
    conn.close()
    strat = dict(zip(col_names, row, strict=True))

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

    ohlcv = load_ohlcv()
    signals = adapter.generate_signals(ohlcv)

    long_arr = np.asarray(signals.entries.values, dtype=bool)
    (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(long_arr), dtype=bool)
    )

    # Find all long signals on Nov 3
    print("=== LONG SIGNALS ON NOV 3 UTC ===")
    nov3_start = pd.Timestamp("2025-11-03 00:00:00", tz="UTC")
    nov3_end = pd.Timestamp("2025-11-04 00:00:00", tz="UTC")

    for i, ts in enumerate(ohlcv.index):
        if nov3_start <= ts < nov3_end and long_arr[i]:
            print(f"  Bar {i}: {ts} close={ohlcv['close'].iloc[i]:.2f} LONG SIGNAL")

    # Now check: after trade #1 exit at 03:00 UTC Nov 3 (bar ~), what bars are available?
    exit_time = pd.Timestamp("2025-11-03 03:00:00", tz="UTC")
    exit_idx = ohlcv.index.get_loc(exit_time) if exit_time in ohlcv.index else None
    print(f"\nTrade #1 exit bar: {exit_time}, index={exit_idx}")

    # What is the TP exit bar?
    # Our engine: entry at 06:30 UTC Nov 1 = bar 26, price=109917.9*(1-0.0005)
    # TP at 1.5% from entry price
    entry_bar = 26
    entry_price = ohlcv["close"].iloc[26] * (1 - 0.0005)  # Short entry = close*(1-slippage)
    tp_price = entry_price * (1 - 0.015)  # Short TP = entry*(1-TP%)
    print("\nTrade #1 analysis:")
    print(f"  Entry bar: {entry_bar} = {ohlcv.index[entry_bar]} close={ohlcv['close'].iloc[26]:.2f}")
    print(f"  Entry price (with slippage): {entry_price:.4f}")
    print(f"  TP price (1.5%): {tp_price:.4f}")

    # Find when low crosses TP for short (low <= tp_price)
    print("\n  Bars after entry where low <= TP:")
    for i in range(27, min(400, len(ohlcv))):
        ts = ohlcv.index[i]
        low = ohlcv["low"].iloc[i]
        ohlcv["close"].iloc[i]
        if low <= tp_price:
            print(f"    Bar {i}: {ts} low={low:.2f} <= TP={tp_price:.4f} ← EXIT HERE")
            print(f"    Exit bar index = {i}, exit time = {ts}")
            exit_idx_actual = i
            break

    # Find long signals AFTER exit bar
    print(f"\n=== LONG SIGNALS AFTER EXIT (bar >= {exit_idx_actual}) ===")
    for i in range(exit_idx_actual, min(exit_idx_actual + 100, len(ohlcv))):
        ts = ohlcv.index[i]
        if long_arr[i]:
            print(
                f"  Bar {i}: {ts} close={ohlcv['close'].iloc[i]:.2f} LONG SIGNAL (TV+15min={ts + pd.Timedelta(minutes=15)})"
            )

    # TV entry is 05:15 UTC Nov 3 = bar at 05:00 UTC Nov 3
    tv_entry_time = pd.Timestamp("2025-11-03 05:00:00", tz="UTC")  # signal bar (TV shows 05:15 = entry bar)
    tv_entry_idx = ohlcv.index.get_loc(tv_entry_time) if tv_entry_time in ohlcv.index else None
    print(f"\nTV Trade #2 signal bar: {tv_entry_time}, index={tv_entry_idx}")
    if tv_entry_idx:
        print(f"  long_arr[{tv_entry_idx}] = {long_arr[tv_entry_idx]}")
        print(f"  Our exit was at bar {exit_idx_actual}")
        print(f"  Signal bar {tv_entry_idx} > exit bar {exit_idx_actual}? {tv_entry_idx > exit_idx_actual}")

    # Our engine enters long at 06:45 UTC Nov 3 = signal bar at 06:45 UTC
    our_entry_bar = pd.Timestamp("2025-11-03 06:45:00", tz="UTC")
    our_entry_idx = ohlcv.index.get_loc(our_entry_bar) if our_entry_bar in ohlcv.index else None
    print(f"\nOur Trade #2 signal bar: {our_entry_bar}, index={our_entry_idx}")
    if our_entry_idx:
        print(f"  long_arr[{our_entry_idx}] = {long_arr[our_entry_idx]}")


if __name__ == "__main__":
    main()
