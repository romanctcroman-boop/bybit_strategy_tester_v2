"""
Check exact SE values at every bar between prev trade exit and engine entry
for E#57 (prev exit 14:30, engine entry 15:30, TV entry 19:30)
"""

import asyncio
import os
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

    # Load ETH data
    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)

    # Load BTC data (warmup + main)
    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), START_DATE)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    import json as _json
    import sqlite3

    db_conn = sqlite3.connect("data.sqlite3")
    row = db_conn.execute(
        "SELECT builder_blocks, builder_connections FROM strategies WHERE id='dd2969a2-bbba-410e-b190-be1e8cc50b21'"
    ).fetchone()
    blocks = _json.loads(row[0])
    connections = _json.loads(row[1])

    graph = {
        "blocks": blocks,
        "connections": connections,
        "name": "Strategy_RSI_LS_10",
    }
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    result = adapter.generate_signals(candles)
    le = result.entries.values
    lx = result.exits.values
    se = result.short_entries.values
    sx = result.short_exits.values

    # Use the candles dataframe for OHLC data
    idx = candles.index

    # Find the bars around 2025-05-09 14:00 to 20:00 UTC
    t_start = pd.Timestamp("2025-05-09 13:00")
    t_end = pd.Timestamp("2025-05-09 21:00")

    mask = (idx >= t_start) & (idx <= t_end)
    subset = candles.loc[mask]

    print("=" * 120)
    print("E#57 CASE: SE/SX/LE/LX values bar-by-bar around 2025-05-09 14:00-20:00 UTC")
    print("Prev trade TP exit: bar 14:30. Engine entry: bar 15:30. TV entry: bar 19:30.")
    print("=" * 120)
    print(
        f"{'Bar time':>25s}  {'Open':>10s}  {'High':>10s}  {'Low':>10s}  {'Close':>10s}  {'SE':>5s}  {'SX':>5s}  {'LE':>5s}  {'LX':>5s}"
    )
    print("-" * 120)

    for ts in subset.index:
        i = idx.get_loc(ts)
        row = candles.iloc[i]
        print(
            f"{str(ts):>25s}  {row['open']:10.2f}  {row['high']:10.2f}  {row['low']:10.2f}  {row['close']:10.2f}  {se[i]:5}  {sx[i]:5}  {le[i]:5}  {lx[i]:5}"
        )

    # Also check BTC RSI at these bars
    print("\n\nBTC RSI at these bars:")
    # Check result for RSI data - it's a SignalResult, check extra_data
    if hasattr(result, "extra_data") and result.extra_data:
        print(f"extra_data keys: {list(result.extra_data.keys())}")
    else:
        print("No extra_data in SignalResult")

    # Now check ALL 6 UNKNOWN cases' SE bars
    print("\n\n" + "=" * 120)
    print("ALL 6 UNKNOWN CASES: Checking SE[exit_bar] and SE[exit_bar-1]")
    print("Key question: Is there an SE=True on the same bar where TP fires?")
    print("=" * 120)

    unknown_cases = [
        ("E#23", "2025-02-22 10:00", "2025-02-22 11:00", "2025-02-22 15:00"),
        ("E#57", "2025-05-09 14:00", "2025-05-09 15:30", "2025-05-09 19:30"),
        ("E#85", "2025-08-15 22:30", "2025-08-16 01:30", "2025-08-16 14:00"),
        ("E#89", "2025-08-26 18:30", "2025-08-27 03:00", "2025-08-27 12:30"),
        ("E#91", "2025-09-02 08:30", "2025-09-02 11:30", "2025-09-02 18:30"),
        ("E#120", "2025-11-24 18:30", "2025-11-25 00:30", "2025-11-25 05:30"),
    ]

    for label, prev_exit_str, eng_entry_str, tv_entry_str in unknown_cases:
        prev_exit = pd.Timestamp(prev_exit_str)
        eng_entry = pd.Timestamp(eng_entry_str)
        tv_entry = pd.Timestamp(tv_entry_str)

        # Find the bar where TP fires (prev_exit is when exit executes, TP fires on the bar BEFORE)
        # Actually, prev_exit is the exit_time of the previous trade
        # In our engine: TP detected at bar X → pending_exit, executes at bar X+1
        # The exit_time in trade record = bar X+1's time (where pending exit executes)
        # So the TP detection bar = prev_exit - 30min

        # Let me just show all bars from prev_exit-2h to eng_entry+30min
        window_start = prev_exit - pd.Timedelta(hours=2)
        window_end = tv_entry + pd.Timedelta(minutes=30)

        print(f"\n{label}: prev_exit={prev_exit}, eng_entry={eng_entry}, tv_entry={tv_entry}")
        print(f"  Bars from {window_start} to {window_end}:")

        w_mask = (idx >= window_start) & (idx <= window_end)
        for ts in idx[w_mask]:
            i = idx.get_loc(ts)
            markers = []
            if ts == prev_exit:
                markers.append("<<< EXIT EXECUTES")
            if ts == eng_entry:
                markers.append("<<< ENGINE ENTRY")
            if ts == tv_entry:
                markers.append("<<< TV ENTRY")
            # TP detection bar (one bar before exit)
            tp_bar = prev_exit - pd.Timedelta(minutes=30)
            if ts == tp_bar:
                markers.append("<<< TP DETECTED")
            marker_str = "  ".join(markers)
            print(f"    {ts}  SE={se[i]:5}  SX={sx[i]:5}  LE={le[i]:5}  LX={lx[i]:5}  {marker_str}")


asyncio.run(main())
