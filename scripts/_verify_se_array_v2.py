"""
Verify actual SE signal array from generate_signals() at all divergent bars.
Fixed: tz handling for candle index.
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
    print(f"ETH index tz: {candles.index.tz}  dtype: {candles.index.dtype}")
    print(f"ETH range: {candles.index[0]} .. {candles.index[-1]}")

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
    # Make tz-naive for comparison
    if times.tz is not None:
        times_naive = times.tz_localize(None)
    else:
        times_naive = times

    print(f"SE signals: {se.sum()}")
    print()

    # Compute BTC RSI manually for comparison
    btc_rsi = pd.Series(calculate_rsi(btc["close"].values, period=14), index=btc.index)
    # Align to ETH index
    if btc_rsi.index.tz is not None:
        btc_rsi.index = btc_rsi.index.tz_localize(None)
    btc_rsi_aligned = btc_rsi.reindex(times_naive, method="ffill")

    # Check ALL cases
    check_bars = [
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
        ("TV#1", "2025-01-01 13:00"),
        ("E#1", "2025-01-02 22:00"),
        ("TV#9", "2025-01-28 14:00"),
        ("E#6", "2025-01-28 17:30"),
    ]

    print(f"{'Label':15s}  {'Timestamp':20s}  SE     LE     BTC_RSI     BTC_prev    Range50-70  Cross↓52")
    print("-" * 120)

    for label, ts_str in check_bars:
        # Use tz-naive timestamp for lookup
        ts_naive = pd.Timestamp(ts_str)

        # Find index position
        pos = times_naive.get_indexer([ts_naive], method=None)
        if pos[0] == -1:
            # Try nearest
            pos = times_naive.get_indexer([ts_naive], method="nearest")
            actual_t = times_naive[pos[0]]
            if abs((actual_t - ts_naive).total_seconds()) > 1800:
                print(f"  {label:15s}  {ts_str:20s}  -- not found (nearest={actual_t}) --")
                continue
            else:
                print(f"  {label:15s}  {ts_str:20s}  (snapped to {actual_t})", end="")
                idx = pos[0]
        else:
            idx = pos[0]

        se_val = se[idx]
        le_val = le[idx]
        btc_r = btc_rsi_aligned.iloc[idx]
        btc_p = btc_rsi_aligned.iloc[idx - 1] if idx > 0 else float("nan")
        in_range = 50 <= btc_r <= 70
        cross = btc_p >= 52 and btc_r < 52

        print(
            f"  {label:15s}  {ts_str:20s}  SE={se_val!s:5s}  LE={le_val!s:5s}  "
            f"BTC_RSI={btc_r:8.4f}  prev={btc_p:8.4f}  "
            f"range={'Y' if in_range else 'N'}  cross={'Y' if cross else 'N'}"
        )

    # Trace SE signals in windows for UNKNOWN cases
    print()
    print("=" * 120)
    print("SE signal trace in windows for UNKNOWN cases")
    print("=" * 120)

    unknown_windows = [
        ("E#20/TV#22", "2025-02-22 04:30", "2025-02-22 14:30"),
        ("E#54/TV#56", "2025-05-09 12:00", "2025-05-09 19:00"),
        ("E#82/TV#85", "2025-08-15 17:00", "2025-08-16 13:30"),
        ("E#86/TV#89", "2025-08-26 20:00", "2025-08-27 12:00"),
        ("E#88/TV#91", "2025-09-02 04:00", "2025-09-02 18:00"),
        ("E#117/TV#119", "2025-11-24 18:00", "2025-11-25 05:00"),
    ]

    for label, start, end in unknown_windows:
        s = pd.Timestamp(start)
        e = pd.Timestamp(end)
        mask = (times_naive >= s) & (times_naive <= e)
        indices = np.where(mask)[0]

        se_count = se[mask].sum()
        print(f"\n  {label}: {se_count} SE signals in window {start} → {end}")

        for i in indices:
            if se[i]:
                t = times_naive[i].strftime("%Y-%m-%d %H:%M")
                btc_r = btc_rsi_aligned.iloc[i]
                btc_p = btc_rsi_aligned.iloc[i - 1] if i > 0 else float("nan")
                in_range = 50 <= btc_r <= 70
                cross = btc_p >= 52 and btc_r < 52
                print(
                    f"    SE @ {t}  BTC_RSI={btc_r:.4f}  prev={btc_p:.4f}  "
                    f"range={'Y' if in_range else 'N'}  cross={'Y' if cross else 'N'}"
                )


asyncio.run(main())
