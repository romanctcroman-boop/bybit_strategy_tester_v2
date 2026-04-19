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

    rsi = calculate_rsi(btc["close"], period=14)

    # All divergent cases where engine fires EARLIER or TV has no bar-close cross
    cases = [
        # (description, TV_signal_bar, eng_signal_bar)
        # TV signal bar = TV entry - 30min (entry_on_next_bar_open)
        ("TV#1 (no SE at all)", "2025-01-01 13:00:00", "2025-01-02 22:00:00"),
        ("E#6/TV#9 (Root #9)", "2025-01-28 14:00:00", "2025-01-28 17:30:00"),
        ("E#9 engine-only", None, "2025-02-06 14:00:00"),
        ("E#20/TV#22", "2025-02-22 14:30:00", "2025-02-22 10:30:00"),
        ("E#54/TV#56", "2025-05-09 19:00:00", "2025-05-09 15:00:00"),
        ("E#55 engine-only", None, "2025-05-11 05:00:00"),
        ("E#56 engine-only", None, "2025-05-11 20:30:00"),
        ("E#57/TV#57", "2025-05-13 23:00:00", "2025-05-13 07:30:00"),
        ("TV#58 TV-only", "2025-05-14 10:30:00", None),
        ("TV#59 TV-only", "2025-05-15 21:00:00", None),
        ("TV#60 TV-only", "2025-05-17 05:00:00", None),
        ("E#82/TV#85", "2025-08-16 13:30:00", "2025-08-16 01:00:00"),
        ("E#86/TV#89", "2025-08-27 12:00:00", "2025-08-27 02:30:00"),
        ("E#88/TV#91", "2025-09-02 18:00:00", "2025-09-02 11:00:00"),
        ("E#89 engine-only", None, "2025-09-02 19:00:00"),
        ("E#117/TV#119", "2025-11-25 05:00:00", "2025-11-25 00:00:00"),
        ("TV#136 TV-only", "2026-02-01 10:00:00", None),
    ]

    cross_level = 52.0

    print(f"{'Case':<25s}  {'TV_bar RSI':>12s}  {'Eng_bar RSI':>12s}  {'TV cross?':8s}  {'Eng cross?':8s}  Notes")
    print("-" * 120)

    for desc, tv_bar, eng_bar in cases:
        tv_rsi = tv_cross = eng_rsi = eng_cross = ""
        notes = ""

        if tv_bar:
            ts = pd.Timestamp(tv_bar)
            if ts in rsi.index:
                r = rsi.loc[ts]
                tv_rsi = f"{r:.4f}"
                # Check crossunder: prev >= 52 and curr < 52
                idx = rsi.index.get_loc(ts)
                if idx > 0:
                    prev_r = rsi.iloc[idx - 1]
                    if prev_r >= cross_level and r < cross_level:
                        tv_cross = "YES"
                    else:
                        tv_cross = "NO"
                        if r >= cross_level:
                            notes += f"RSI≥52 (no cross, {r:.4f})"
                        else:
                            notes += f"prev={prev_r:.4f}<52 (already below)"
            else:
                tv_rsi = "NOT FOUND"

        if eng_bar:
            ts = pd.Timestamp(eng_bar)
            if ts in rsi.index:
                r = rsi.loc[ts]
                eng_rsi = f"{r:.4f}"
                idx = rsi.index.get_loc(ts)
                if idx > 0:
                    prev_r = rsi.iloc[idx - 1]
                    if prev_r >= cross_level and r < cross_level:
                        eng_cross = "YES"
                    else:
                        eng_cross = "NO"
                        if r >= cross_level:
                            notes += f" | eng RSI≥52"
                        else:
                            notes += f" | eng prev={prev_r:.4f}"
            else:
                eng_rsi = "NOT FOUND"

        print(f"{desc:<25s}  {tv_rsi:>12s}  {eng_rsi:>12s}  {tv_cross:8s}  {eng_cross:8s}  {notes}")

    # Now let's trace the first 2 weeks in detail to understand TV trades #1-#5
    print("\n\n" + "=" * 80)
    print("DETAILED: BTC RSI around 2025-01-01 to 2025-01-14")
    print("cross_short = (rsi_prev >= 52) & (rsi < 52)")
    print("=" * 80)

    start = pd.Timestamp("2025-01-01 00:00:00")
    end = pd.Timestamp("2025-01-14 23:00:00")

    mask = (rsi.index >= start) & (rsi.index <= end)
    rsi_range = rsi[mask]

    for i in range(1, len(rsi_range)):
        ts = rsi_range.index[i]
        r = rsi_range.iloc[i]
        prev_r = rsi_range.iloc[i - 1]
        cross = prev_r >= cross_level and r < cross_level
        near_cross = abs(r - cross_level) < 1.0 or (prev_r >= cross_level and r < cross_level + 0.5)

        if cross:
            # Check if also in range [50, 70]
            in_range = 50 <= r <= 70
            print(f"  CROSS ↓ {ts}  RSI: {prev_r:.4f} → {r:.4f}  in_range={in_range}")
        elif near_cross and abs(r - cross_level) < 0.3:
            print(f"  NEAR  ↓ {ts}  RSI: {prev_r:.4f} → {r:.4f}  (within 0.3 of 52)")

    # Check TV trade #1 entry: 2025-01-01 13:30 UTC
    # Signal would be at 13:00 bar. But NO SE signal.
    # Maybe TV uses a different warmup? Let's check RSI around that bar
    print("\nBTC RSI detail 2025-01-01 10:00 to 16:00:")
    for i in range(len(rsi)):
        ts = rsi.index[i]
        if pd.Timestamp("2025-01-01 10:00") <= ts <= pd.Timestamp("2025-01-01 16:00"):
            r = rsi.iloc[i]
            prev_r = rsi.iloc[i - 1] if i > 0 else float("nan")
            cross = prev_r >= cross_level and r < cross_level
            print(f"  {ts}  RSI={r:.6f}  prev={prev_r:.6f}  cross={cross}")


asyncio.run(main())
