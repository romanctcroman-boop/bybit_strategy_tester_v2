"""
For UNKNOWN cases, check SE at the bar BEFORE the entry bar.
With entry_on_next_bar_open=True:
  - Signal fires at bar T
  - Entry happens at bar T+1 open (which is bar T+1's timestamp)
So if entry is at 10:30, the signal was at 10:00.
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

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)

    le = np.asarray(signals.entries.values, dtype=bool)
    se = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(le), dtype=bool)
    )

    times = candles.index
    if times.tz is not None:
        times = times.tz_localize(None)

    btc_rsi = pd.Series(calculate_rsi(btc["close"].values, period=14), index=btc.index)
    if btc_rsi.index.tz is not None:
        btc_rsi.index = btc_rsi.index.tz_localize(None)
    btc_rsi_aligned = btc_rsi.reindex(times, method="ffill")

    print("=" * 130)
    print("UNKNOWN cases: SE at SIGNAL bar (entry_bar - 1) vs ENTRY bar")
    print("With entry_on_next_bar_open=True: signal at bar[i] → entry at bar[i+1] open")
    print("=" * 130)

    # UNKNOWN cases with ENTRY bar timestamps (from _match_trades.py)
    cases = [
        ("E#20/TV#22", "2025-02-22 10:30", "2025-02-22 14:30"),
        ("E#54/TV#56", "2025-05-09 15:00", "2025-05-09 19:00"),
        ("E#82/TV#85", "2025-08-16 01:00", "2025-08-16 13:30"),
        ("E#86/TV#89", "2025-08-27 02:30", "2025-08-27 12:00"),
        ("E#88/TV#91", "2025-09-02 11:00", "2025-09-02 18:00"),
        ("E#117/TV#119", "2025-11-25 00:00", "2025-11-25 05:00"),
    ]

    for label, eng_entry, tv_entry in cases:
        eng_t = pd.Timestamp(eng_entry)
        tv_t = pd.Timestamp(tv_entry)

        eng_idx = np.where(times == eng_t)[0]
        tv_idx = np.where(times == tv_t)[0]

        if len(eng_idx) == 0 or len(tv_idx) == 0:
            print(f"  {label}: timestamps not found")
            continue

        ei = eng_idx[0]
        ti = tv_idx[0]

        # Signal bar = entry bar - 1 (because entry_on_next_bar_open=True)
        eng_sig_idx = ei - 1
        tv_sig_idx = ti - 1

        eng_sig_t = times[eng_sig_idx].strftime("%Y-%m-%d %H:%M")
        tv_sig_t = times[tv_sig_idx].strftime("%Y-%m-%d %H:%M")

        print(f"\n  {label}:")
        print(
            f"    Engine: signal bar [{eng_sig_idx}] {eng_sig_t}  SE={se[eng_sig_idx]}  "
            f"BTC_RSI={btc_rsi_aligned.iloc[eng_sig_idx]:.4f} prev={btc_rsi_aligned.iloc[eng_sig_idx - 1]:.4f}"
        )
        print(
            f"    Engine: entry  bar [{ei}] {eng_entry}  SE={se[ei]}  "
            f"BTC_RSI={btc_rsi_aligned.iloc[ei]:.4f} prev={btc_rsi_aligned.iloc[ei - 1]:.4f}"
        )
        print(
            f"    TV:     signal bar [{tv_sig_idx}] {tv_sig_t}  SE={se[tv_sig_idx]}  "
            f"BTC_RSI={btc_rsi_aligned.iloc[tv_sig_idx]:.4f} prev={btc_rsi_aligned.iloc[tv_sig_idx - 1]:.4f}"
        )
        print(
            f"    TV:     entry  bar [{ti}] {tv_entry}  SE={se[ti]}  "
            f"BTC_RSI={btc_rsi_aligned.iloc[ti]:.4f} prev={btc_rsi_aligned.iloc[ti - 1]:.4f}"
        )

        # Count SE signals between engine signal and TV signal
        se_between = se[eng_sig_idx : tv_sig_idx + 1]
        times_between = times[eng_sig_idx : tv_sig_idx + 1]
        se_count = se_between.sum()
        print(f"    SE signals between engine signal and TV signal: {se_count}")
        for j, (t, s) in enumerate(zip(times_between, se_between)):
            if s:
                actual_idx = eng_sig_idx + j
                r = btc_rsi_aligned.iloc[actual_idx]
                p = btc_rsi_aligned.iloc[actual_idx - 1]
                print(f"      SE @ {t.strftime('%Y-%m-%d %H:%M')} [{actual_idx}]  BTC_RSI={r:.4f}  prev={p:.4f}")

    # ALSO: Check if TV entries are at EXACT bars from TV CSV
    # TV#1 entry: 2025-01-01 10:30 Moscow = 2025-01-01 07:30 UTC (from as4.csv, row 2)
    # Wait, TV#1 entry from our _match_trades was 2025-01-01 13:30 UTC
    # Let me just check signal at bar before each
    print()
    print("=" * 130)
    print("TV#1 (INTRA-BAR): check signal at bar before TV entry")
    print("=" * 130)

    # TV#1 entry at 2025-01-01 13:30 UTC (from matching)
    # But wait - our previous _check_rsi script said TV#1 enters at 13:00, not 13:30
    # Let me check what the actual data says
    for tv_entry_str in ["2025-01-01 13:00", "2025-01-01 13:30"]:
        tv_t = pd.Timestamp(tv_entry_str)
        idx = np.where(times == tv_t)[0]
        if len(idx) == 0:
            print(f"  {tv_entry_str}: not found")
            continue
        i = idx[0]
        sig_i = i - 1
        print(f"\n  TV#1 if entry at {tv_entry_str}:")
        print(
            f"    Signal bar [{sig_i}] {times[sig_i].strftime('%Y-%m-%d %H:%M')}  SE={se[sig_i]}  "
            f"BTC_RSI={btc_rsi_aligned.iloc[sig_i]:.4f}  prev={btc_rsi_aligned.iloc[sig_i - 1]:.4f}"
        )
        print(
            f"    Entry  bar [{i}] {tv_entry_str}  SE={se[i]}  "
            f"BTC_RSI={btc_rsi_aligned.iloc[i]:.4f}  prev={btc_rsi_aligned.iloc[i - 1]:.4f}"
        )


asyncio.run(main())
