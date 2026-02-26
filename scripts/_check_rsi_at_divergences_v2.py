"""Check BTC RSI values at all divergent points to understand the pattern."""

import asyncio
import json
import sqlite3
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")
from backend.backtesting.service import BacktestService
from backend.core.indicators.momentum import calculate_rsi


async def main():
    svc = BacktestService()
    btc = await svc._fetch_historical_data(
        "BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), pd.Timestamp("2026-02-24", tz="UTC")
    )
    btc = btc[~btc.index.duplicated(keep="last")]

    rsi_arr = calculate_rsi(btc["close"], period=14)
    # Make it a pandas Series
    rsi = pd.Series(rsi_arr, index=btc.index)

    cross_level = 52.0

    # All divergent cases
    cases = [
        ("TV#1 (no SE)", "2025-01-01 13:00:00", "2025-01-02 22:00:00"),
        ("E#6/TV#9 (Root#9)", "2025-01-28 14:00:00", "2025-01-28 17:30:00"),
        ("E#9 eng-only", None, "2025-02-06 14:00:00"),
        ("E#20/TV#22", "2025-02-22 14:30:00", "2025-02-22 10:30:00"),
        ("E#54/TV#56", "2025-05-09 19:00:00", "2025-05-09 15:00:00"),
        ("E#55 eng-only", None, "2025-05-11 05:00:00"),
        ("E#56 eng-only", None, "2025-05-11 20:30:00"),
        ("E#57/TV#57", "2025-05-13 23:00:00", "2025-05-13 07:30:00"),
        ("TV#58 TV-only", "2025-05-14 10:30:00", None),
        ("TV#59 TV-only", "2025-05-15 21:00:00", None),
        ("TV#60 TV-only", "2025-05-17 05:00:00", None),
        ("E#82/TV#85", "2025-08-16 13:30:00", "2025-08-16 01:00:00"),
        ("E#86/TV#89", "2025-08-27 12:00:00", "2025-08-27 02:30:00"),
        ("E#88/TV#91", "2025-09-02 18:00:00", "2025-09-02 11:00:00"),
        ("E#89 eng-only", None, "2025-09-02 19:00:00"),
        ("E#117/TV#119", "2025-11-25 05:00:00", "2025-11-25 00:00:00"),
        ("TV#136 TV-only", "2026-02-01 10:00:00", None),
    ]

    print(f"{'Case':<22s}  {'TV_bar RSI':>12s}  {'Eng_bar RSI':>12s}  TV_cx  Eng_cx  Notes")
    print("-" * 110)

    for desc, tv_bar, eng_bar in cases:
        tv_rsi_s = tv_cross = eng_rsi_s = eng_cross = ""
        notes = ""

        if tv_bar:
            ts = pd.Timestamp(tv_bar)
            if ts in rsi.index:
                idx = rsi.index.get_loc(ts)
                r = rsi.iloc[idx]
                tv_rsi_s = f"{r:.4f}"
                if idx > 0:
                    prev_r = rsi.iloc[idx - 1]
                    if prev_r >= cross_level and r < cross_level:
                        tv_cross = "YES"
                    else:
                        tv_cross = "NO"
                        notes += f"tv_prev={prev_r:.2f},tv_cur={r:.2f}"
            else:
                tv_rsi_s = "N/A"

        if eng_bar:
            ts = pd.Timestamp(eng_bar)
            if ts in rsi.index:
                idx = rsi.index.get_loc(ts)
                r = rsi.iloc[idx]
                eng_rsi_s = f"{r:.4f}"
                if idx > 0:
                    prev_r = rsi.iloc[idx - 1]
                    if prev_r >= cross_level and r < cross_level:
                        eng_cross = "YES"
                    else:
                        eng_cross = "NO"
                        if notes:
                            notes += " | "
                        notes += f"eng_prev={prev_r:.2f},eng_cur={r:.2f}"
            else:
                eng_rsi_s = "N/A"

        print(f"{desc:<22s}  {tv_rsi_s:>12s}  {eng_rsi_s:>12s}  {tv_cross:5s}  {eng_cross:6s}  {notes}")

    # ============ Detailed first 2 weeks ============
    print("\n\n" + "=" * 80)
    print("BTC RSI crossunders (prev >= 52, cur < 52) : Jan 1 - Jan 14, 2025")
    print("=" * 80)

    start = pd.Timestamp("2025-01-01 00:00:00")
    end = pd.Timestamp("2025-01-15 00:00:00")

    for i in range(1, len(rsi)):
        ts = rsi.index[i]
        if ts < start or ts > end:
            continue
        r = rsi.iloc[i]
        prev_r = rsi.iloc[i - 1]
        if prev_r >= cross_level and r < cross_level:
            in_range = 50 <= r <= 70
            print(f"  CROSS ↓ {ts}  RSI: {prev_r:.4f} → {r:.4f}  in_range={in_range}")

    # Check RSI around TV trade #1 signal bar
    print("\n\nBTC RSI detail: 2025-01-01 10:00 to 16:00")
    for i in range(len(rsi)):
        ts = rsi.index[i]
        if pd.Timestamp("2025-01-01 10:00") <= ts <= pd.Timestamp("2025-01-01 16:00"):
            r = rsi.iloc[i]
            prev_r = rsi.iloc[i - 1] if i > 0 else float("nan")
            cross = prev_r >= cross_level and r < cross_level
            marker = " ← CROSS" if cross else (" ← NEAR" if abs(r - 52) < 0.5 else "")
            print(f"  {ts}  RSI={r:.6f}  prev={prev_r:.6f}{marker}")

    # Check exit-time mismatches: same-bar TP
    print("\n\n" + "=" * 80)
    print("EXIT MISMATCHES: Same-bar TP detection")
    print("=" * 80)

    # E#45/TV#47: short entry=2025-04-13 19:30, exit: E=21:00 vs TV=19:30
    # TV exits on SAME BAR as entry → TV detects TP hit intra-bar on entry bar
    eth = await svc._fetch_historical_data(
        "ETHUSDT", "30", pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2026-02-24", tz="UTC")
    )

    print("\nE#45/TV#47: short entry 2025-04-13 19:30, TP=2.3%")
    entry_bar = pd.Timestamp("2025-04-13 19:30:00")
    if entry_bar in eth.index:
        idx = eth.index.get_loc(entry_bar)
        bar = eth.iloc[idx]
        entry_price = bar["open"]
        tp_price = entry_price * (1 - 0.023)
        print(f"  Entry bar: O={bar['open']:.2f} H={bar['high']:.2f} L={bar['low']:.2f} C={bar['close']:.2f}")
        print(f"  Entry price (open): {entry_price:.2f}")
        print(f"  TP price (short, -2.3%): {tp_price:.2f}")
        print(f"  Low of entry bar: {bar['low']:.2f}")
        if bar["low"] <= tp_price:
            print(f"  → TP HIT on entry bar! Low {bar['low']:.2f} <= TP {tp_price:.2f}")
        else:
            print(f"  → TP NOT hit on entry bar")

        # Check next bar
        if idx + 1 < len(eth):
            next_bar = eth.iloc[idx + 1]
            print(
                f"  Next bar ({eth.index[idx + 1]}): O={next_bar['open']:.2f} H={next_bar['high']:.2f} L={next_bar['low']:.2f} C={next_bar['close']:.2f}"
            )
            if next_bar["low"] <= tp_price:
                print(f"  → TP would hit on next bar too")

    print("\nE#103/TV#105: long entry 2025-10-17 11:00, TP=2.3%")
    entry_bar = pd.Timestamp("2025-10-17 11:00:00")
    if entry_bar in eth.index:
        idx = eth.index.get_loc(entry_bar)
        bar = eth.iloc[idx]
        entry_price = bar["open"]
        tp_price = entry_price * (1 + 0.023)
        print(f"  Entry bar: O={bar['open']:.2f} H={bar['high']:.2f} L={bar['low']:.2f} C={bar['close']:.2f}")
        print(f"  Entry price (open): {entry_price:.2f}")
        print(f"  TP price (long, +2.3%): {tp_price:.2f}")
        print(f"  High of entry bar: {bar['high']:.2f}")
        if bar["high"] >= tp_price:
            print(f"  → TP HIT on entry bar! High {bar['high']:.2f} >= TP {tp_price:.2f}")
        else:
            print(f"  → TP NOT hit on entry bar")


asyncio.run(main())
