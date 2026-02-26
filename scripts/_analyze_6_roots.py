"""Analyze all 6 root divergences: show RSI, gap to 52, and whether a tiny
RSI shift (< 1.0) would change the cross detection.

If the gap is < 1.0 for all 6 roots, the explanation is likely a small
numerical difference between our RSI and TV's RSI.
"""

import asyncio
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from backend.backtesting.service import BacktestService
from backend.core.indicators.momentum import calculate_rsi

# 6 roots from trade structure analysis (signal bars, not entry bars)
# Engine signal bar = engine entry bar - 30min (entry_on_next_bar_open)
ROOT_SIGNAL_BARS_ENGINE = [
    ("Root #9", "2025-01-28 17:30", +7),  # Engine 7 bars LATER
    ("Root #12", "2025-02-06 14:00", -30),  # Engine 30 bars EARLIER
    ("Root #85", "2025-08-16 01:00", -25),
    ("Root #89", "2025-08-27 02:30", -19),
    ("Root #91", "2025-09-02 11:00", -14),
    ("Root #144", "2026-02-07 16:00", -22),
]

# TV signal bars (TV entry - 30min)
ROOT_SIGNAL_BARS_TV = [
    ("Root #9", "2025-01-28 14:00"),
    ("Root #12", "2025-02-07 05:00"),
    ("Root #85", "2025-08-16 13:30"),
    ("Root #89", "2025-08-27 12:00"),
    ("Root #91", "2025-09-02 18:00"),
    ("Root #144", "2026-02-08 03:00"),
]

CROSS_LEVEL = 52.0


async def main():
    svc = BacktestService()

    # Fetch BTC 30m with warmup
    btc_start = pd.Timestamp("2020-01-01", tz="UTC")
    end = pd.Timestamp("2026-02-24", tz="UTC")
    start = pd.Timestamp("2025-01-01", tz="UTC")

    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", btc_start, start)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", start, end)
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    closes = btc["close"].values
    rsi_arr = calculate_rsi(closes, period=14)
    rsi = pd.Series(rsi_arr, index=btc.index)

    print(f"BTC 30m: {len(btc)} bars")
    print(f"Cross level: {CROSS_LEVEL}")
    print()

    # Analyze engine signal bars
    print("=" * 120)
    print("ENGINE SIGNAL BARS (where our engine fires the short signal)")
    print("=" * 120)
    for name, ts_str, delta in ROOT_SIGNAL_BARS_ENGINE:
        ts = pd.Timestamp(ts_str)
        if ts in rsi.index:
            loc = rsi.index.get_loc(ts)
            rsi_cur = rsi.iloc[loc]
            rsi_prev = rsi.iloc[loc - 1] if loc > 0 else np.nan
            gap = rsi_cur - CROSS_LEVEL
            crosses = rsi_prev >= CROSS_LEVEL and rsi_cur < CROSS_LEVEL
            print(
                f"  {name:12s}  {ts_str:20s}  RSI_prev={rsi_prev:.4f}  RSI_cur={rsi_cur:.4f}  gap={gap:+.4f}  crosses={crosses}  Δ_bars={delta:+d}"
            )
        else:
            print(f"  {name:12s}  {ts_str:20s}  NOT FOUND in index")

    print()
    print("=" * 120)
    print("TV SIGNAL BARS (where TradingView fires the short signal)")
    print("=" * 120)
    for name, ts_str in ROOT_SIGNAL_BARS_TV:
        ts = pd.Timestamp(ts_str)
        if ts in rsi.index:
            loc = rsi.index.get_loc(ts)
            rsi_cur = rsi.iloc[loc]
            rsi_prev = rsi.iloc[loc - 1] if loc > 0 else np.nan
            gap = rsi_cur - CROSS_LEVEL
            crosses = rsi_prev >= CROSS_LEVEL and rsi_cur < CROSS_LEVEL
            print(
                f"  {name:12s}  {ts_str:20s}  RSI_prev={rsi_prev:.4f}  RSI_cur={rsi_cur:.4f}  gap={gap:+.4f}  crosses={crosses}"
            )
        else:
            print(f"  {name:12s}  {ts_str:20s}  NOT FOUND in index")

    # For the "engine fires EARLIER" roots, check if there's a bar-close crossunder at
    # the ENGINE bar. If yes, the engine is correct — TV must be seeing something different.
    print()
    print("=" * 120)
    print("DETAILED ANALYSIS: Why does the engine fire at its bar but TV doesn't?")
    print("=" * 120)
    for name, eng_str, delta in ROOT_SIGNAL_BARS_ENGINE:
        if delta >= 0:
            continue  # Only analyze "engine earlier" cases
        tv_name, tv_str = [(n, t) for n, t in ROOT_SIGNAL_BARS_TV if n == name][0]
        eng_ts = pd.Timestamp(eng_str)
        tv_ts = pd.Timestamp(tv_str)

        print(f"\n  --- {name} ---")
        print(f"  Engine signal: {eng_str}  |  TV signal: {tv_str}  |  Δ = {delta} bars")

        if eng_ts in rsi.index and tv_ts in rsi.index:
            eng_loc = rsi.index.get_loc(eng_ts)
            tv_loc = rsi.index.get_loc(tv_ts)

            # Show RSI around engine bar (5 bars before, 5 after)
            print(f"  RSI around engine signal bar ({eng_str}):")
            for j in range(max(0, eng_loc - 3), min(len(rsi), eng_loc + 4)):
                r = rsi.iloc[j]
                r_prev = rsi.iloc[j - 1] if j > 0 else np.nan
                cross = r_prev >= CROSS_LEVEL and r < CROSS_LEVEL
                marker = " <-- ENGINE" if j == eng_loc else ""
                cross_marker = " ** CROSS↓52 **" if cross else ""
                print(f"    {rsi.index[j]}  RSI={r:.4f}  prev={r_prev:.4f}{cross_marker}{marker}")

            # Show RSI around TV bar
            print(f"  RSI around TV signal bar ({tv_str}):")
            for j in range(max(0, tv_loc - 3), min(len(rsi), tv_loc + 4)):
                r = rsi.iloc[j]
                r_prev = rsi.iloc[j - 1] if j > 0 else np.nan
                cross = r_prev >= CROSS_LEVEL and r < CROSS_LEVEL
                marker = " <-- TV" if j == tv_loc else ""
                cross_marker = " ** CROSS↓52 **" if cross else ""
                print(f"    {rsi.index[j]}  RSI={r:.4f}  prev={r_prev:.4f}{cross_marker}{marker}")

            # Count how many bar-close crossunders between engine and TV bars
            cross_count = 0
            for j in range(eng_loc, tv_loc + 1):
                r = rsi.iloc[j]
                r_prev = rsi.iloc[j - 1] if j > 0 else np.nan
                if r_prev >= CROSS_LEVEL and r < CROSS_LEVEL:
                    cross_count += 1
                    print(f"    >> Cross at {rsi.index[j]}  (RSI: {r_prev:.4f} → {r:.4f})")
            print(f"  Total bar-close crossunders between engine and TV: {cross_count}")

    print("\nDone.")


asyncio.run(main())
