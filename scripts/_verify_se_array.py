"""
Verify that SE=True from generate_signals() at engine entry bars E#82 and E#88.
The _check_eth_rsi_range.py showed ETH RSI < 50 at these bars, but:
  - When use_btc_source=True, the range condition uses BTC RSI, not ETH RSI
  - BTC RSI at crossunder is always near 50-52, which IS in range [50,70]
  - So SE should be True at all these bars

This script confirms the actual SE array values from the strategy.
"""

import asyncio
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
os.chdir(r"d:\bybit_strategy_tester_v2")

from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.core.indicators.momentum import calculate_rsi

STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")


async def main():
    svc = BacktestService()

    # Load strategy graph
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br) if isinstance(br, str) else (br or [])
    conns = json.loads(cr) if isinstance(cr, str) else (cr or [])
    gp = json.loads(gr) if isinstance(gr, str) else (gr or {})
    ms = gp.get("main_strategy", {})
    graph = {
        "name": name,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if ms:
        graph["main_strategy"] = ms

    # Fetch data
    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    btc_warmup = await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="30",
        start_date=pd.Timestamp("2020-01-01", tz="UTC"),
        end_date=START_DATE,
    )
    btc_main = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    print(f"ETH: {len(candles)} bars   BTC: {len(btc)} bars (incl warmup)")

    # Generate signals
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)

    le = np.asarray(signals.entries.values, dtype=bool)
    se = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(le), dtype=bool)
    )

    times = candles.index
    print(f"SE signals: {se.sum()}")
    print()

    # Check ALL 6 UNKNOWN cases + 2 INTRA-BAR cases
    check_bars = [
        # UNKNOWN - engine signal bars
        ("E#20 eng", "2025-02-22 10:30"),
        ("E#20 TV", "2025-02-22 14:30"),
        ("E#54 eng", "2025-05-09 15:00"),
        ("E#54 TV", "2025-05-09 19:00"),
        ("E#82 eng", "2025-08-16 01:00"),
        ("E#82 TV", "2025-08-16 13:30"),
        ("E#86 eng", "2025-08-27 02:30"),
        ("E#86 TV", "2025-08-27 12:00"),
        ("E#88 eng", "2025-09-02 11:00"),
        ("E#88 TV", "2025-09-02 18:00"),
        ("E#117 eng", "2025-11-25 00:00"),
        ("E#117 TV", "2025-11-25 05:00"),
        # INTRA-BAR
        ("TV#1", "2025-01-01 13:00"),
        ("E#1", "2025-01-02 22:00"),
        ("TV#9", "2025-01-28 14:00"),
        ("E#6", "2025-01-28 17:30"),
    ]

    # Compute BTC RSI manually for comparison
    btc_rsi = pd.Series(calculate_rsi(btc["close"].values, period=14), index=btc.index)
    # Reindex to ETH candles
    btc_rsi_aligned = btc_rsi.reindex(candles.index, method="ffill")

    print(f"{'Label':15s}  {'Timestamp':20s}  SE     LE     BTC_RSI     BTC_prev    Range50-70  Cross↓52")
    print("-" * 120)

    for label, ts_str in check_bars:
        ts = pd.Timestamp(ts_str, tz="UTC")
        matches = times.get_indexer([ts], method=None)
        if matches[0] == -1:
            print(f"  {label:15s}  {ts_str:20s}  -- timestamp not found --")
            continue

        idx = matches[0]
        se_val = se[idx]
        le_val = le[idx]
        btc_r = btc_rsi_aligned.iloc[idx]
        btc_p = btc_rsi_aligned.iloc[idx - 1] if idx > 0 else float("nan")
        in_range = 50 <= btc_r <= 70
        cross = btc_p >= 52 and btc_r < 52

        print(
            f"  {label:15s}  {ts_str:20s}  {str(se_val):6s} {str(le_val):6s} "
            f"{btc_r:10.4f}  {btc_p:10.4f}  {'YES' if in_range else 'NO':10s}  {'YES' if cross else 'NO'}"
        )

    # Now the KEY question: for the 6 UNKNOWN cases, let's trace SE signals
    # between the prev exit and the engine signal
    print()
    print("=" * 120)
    print("SE signal count between prev TV exit and TV entry for UNKNOWN cases")
    print("=" * 120)

    # For each UNKNOWN, find all SE=True bars in the window before engine fires
    unknown_windows = [
        ("E#20/TV#22", "2025-02-22 04:30", "2025-02-22 14:30"),  # prev exit -> TV entry
        ("E#54/TV#56", "2025-05-09 12:00", "2025-05-09 19:00"),
        ("E#82/TV#85", "2025-08-15 17:00", "2025-08-16 13:30"),
        ("E#86/TV#89", "2025-08-26 20:00", "2025-08-27 12:00"),
        ("E#88/TV#91", "2025-09-02 04:00", "2025-09-02 18:00"),
        ("E#117/TV#119", "2025-11-24 18:00", "2025-11-25 05:00"),
    ]

    for label, start, end in unknown_windows:
        s = pd.Timestamp(start, tz="UTC")
        e = pd.Timestamp(end, tz="UTC")
        mask = (times >= s) & (times <= e)
        window_se = se[mask]
        window_times = times[mask]
        se_bars = [
            (pd.Timestamp(t).strftime("%Y-%m-%d %H:%M"), btc_rsi_aligned.loc[t])
            for t, v in zip(window_times, window_se)
            if v
        ]

        print(f"\n  {label}: {len(se_bars)} SE signals in window {start} → {end}")
        for t, r in se_bars:
            print(f"    SE @ {t}  BTC_RSI={r:.4f}")


asyncio.run(main())
