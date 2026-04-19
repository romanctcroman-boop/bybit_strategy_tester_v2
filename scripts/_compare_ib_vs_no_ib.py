"""
Run intra-bar detection on 5m BTC data and check if it changes
which bars get SE=True for the 6 UNKNOWN cases.

Hypothesis: With calc_on_every_tick (5m data), the RSI cross at bar 15:00
might NOT fire (because 5m ticks show RSI bouncing around 52 without clean cross),
but the cross at bar 19:00 DOES fire on 5m data.
"""

import asyncio
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.getcwd())

import numpy as np
import pandas as pd


async def main():
    from backend.backtesting.service import BacktestService
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    svc = BacktestService()

    START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
    END_DATE = pd.Timestamp("2026-02-24T00:00:00", tz="UTC")

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), START_DATE)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    # Now get BTC 5m data for the same range
    print("Fetching BTC 5m data...")
    btc_5m = await svc._fetch_historical_data("BTCUSDT", "5", START_DATE, END_DATE)
    print(f"BTC 5m bars: {len(btc_5m)}")

    db_conn = sqlite3.connect("data.sqlite3")
    row = db_conn.execute(
        "SELECT builder_blocks, builder_connections FROM strategies WHERE id='dd2969a2-bbba-410e-b190-be1e8cc50b21'"
    ).fetchone()
    blocks = json.loads(row[0])
    connections = json.loads(row[1])

    # Run WITHOUT intra-bar
    print("\n=== WITHOUT INTRA-BAR (btcusdt_5m_ohlcv=None) ===")
    graph = {"blocks": blocks, "connections": connections, "name": "RSI_LS_10"}
    adapter_no_ib = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    result_no_ib = adapter_no_ib.generate_signals(candles)
    se_no_ib = result_no_ib.short_entries.values

    # Run WITH intra-bar (5m data)
    print("\n=== WITH INTRA-BAR (btcusdt_5m_ohlcv=btc_5m) ===")
    graph2 = {"blocks": blocks, "connections": connections, "name": "RSI_LS_10"}
    adapter_ib = StrategyBuilderAdapter(graph2, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=btc_5m)
    result_ib = adapter_ib.generate_signals(candles)
    se_ib = result_ib.short_entries.values

    idx = candles.index

    # Check differences in SE for the 6 UNKNOWN windows
    windows = [
        ("E#23", "2025-02-22 09:00", "2025-02-22 16:00"),
        ("E#57", "2025-05-09 13:00", "2025-05-09 20:00"),
        ("E#85", "2025-08-15 23:00", "2025-08-16 15:00"),
        ("E#89", "2025-08-27 01:00", "2025-08-27 13:00"),
        ("E#91", "2025-09-02 09:00", "2025-09-02 19:30"),
        ("E#120", "2025-11-24 22:00", "2025-11-25 07:00"),
    ]

    total_se_no_ib = int(np.sum(se_no_ib))
    total_se_ib = int(np.sum(se_ib))
    print(f"\nTotal SE signals: no_ib={total_se_no_ib}, with_ib={total_se_ib}")
    print(f"Difference: {total_se_ib - total_se_no_ib} additional SE signals with intra-bar")

    for label, start, end in windows:
        t_start = pd.Timestamp(start)
        t_end = pd.Timestamp(end)
        mask = (idx >= t_start) & (idx <= t_end)

        print(f"\n{'=' * 100}")
        print(f"{label}: {start} to {end}")
        print(f"{'Bar':>25s}  {'SE(noIB)':>8s}  {'SE(IB)':>8s}  {'DIFF':>6s}")
        print("-" * 60)

        for ts in idx[mask]:
            i = idx.get_loc(ts)
            no_val = int(se_no_ib[i])
            ib_val = int(se_ib[i])
            diff = "***" if no_val != ib_val else ""
            if no_val or ib_val:  # Only show bars where at least one has SE
                print(f"{str(ts):>25s}  {no_val:>8d}  {ib_val:>8d}  {diff:>6s}")


asyncio.run(main())
