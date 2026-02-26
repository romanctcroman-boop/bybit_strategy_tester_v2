"""
Look at the TV CSV data to understand the EXACT timing of TV entries
for the 6 UNKNOWN cases and check for patterns.

For each UNKNOWN case:
1. What is the TV entry bar close price?
2. What is BTC RSI at the TV entry bar?
3. Is the TV entry always on a bar where RSI crosses STRONGLY below 52
   (vs the weak crossunders on 1st SE)?
4. Check the RSI DURING the trade (between entry and TP exit of PREVIOUS trade)
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

    svc = BacktestService()

    START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
    END_DATE = pd.Timestamp("2026-02-24T00:00:00", tz="UTC")

    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), START_DATE)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)

    # Compute BTC RSI
    btc_close = btc["close"]
    delta = btc_close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    btc_rsi_full = 100 - (100 / (1 + rs))
    btc_rsi = btc_rsi_full.reindex(candles.index, method="ffill")

    cross_short_level = 52.0
    idx = candles.index

    # The 6 UNKNOWN cases with full context
    # (label, prev_exit, 1st_SE, 2nd_SE, eng_entry, tv_entry)
    unknown_cases = [
        ("E#23", "2025-02-21 19:00", "2025-02-22 10:30", "2025-02-22 13:30", "2025-02-22 11:00", "2025-02-22 15:00"),
        ("E#57", "2025-05-09 14:30", "2025-05-09 15:00", "2025-05-09 19:00", "2025-05-09 15:30", "2025-05-09 19:30"),
        ("E#85", "2025-08-15 15:30", "2025-08-16 01:00", "2025-08-16 13:30", "2025-08-16 01:30", "2025-08-16 14:00"),
        ("E#89", "2025-08-25 19:00", "2025-08-27 02:30", "2025-08-27 12:00", "2025-08-27 03:00", "2025-08-27 12:30"),
        ("E#91", "2025-09-01 20:30", "2025-09-02 11:00", "2025-09-02 18:00", "2025-09-02 11:30", "2025-09-02 18:30"),
        ("E#120", "2025-11-24 17:30", "2025-11-25 00:00", "2025-11-25 05:00", "2025-11-25 00:30", "2025-11-25 05:30"),
    ]

    print("=" * 140)
    print("COMPARING 1st SE vs 2nd SE crossunder characteristics")
    print("=" * 140)

    for label, prev_exit_str, first_se_str, second_se_str, eng_entry_str, tv_entry_str in unknown_cases:
        first_se = pd.Timestamp(first_se_str)
        second_se = pd.Timestamp(second_se_str)
        prev_exit = pd.Timestamp(prev_exit_str)

        # RSI at 1st SE
        first_prev = first_se - pd.Timedelta(minutes=30)
        r1_prev = btc_rsi.loc[first_prev] if first_prev in btc_rsi.index else np.nan
        r1_curr = btc_rsi.loc[first_se] if first_se in btc_rsi.index else np.nan
        r1_drop = r1_prev - r1_curr

        # RSI at 2nd SE
        second_prev = second_se - pd.Timedelta(minutes=30)
        r2_prev = btc_rsi.loc[second_prev] if second_prev in btc_rsi.index else np.nan
        r2_curr = btc_rsi.loc[second_se] if second_se in btc_rsi.index else np.nan
        r2_drop = r2_prev - r2_curr

        # RSI at previous trade entry
        # We know RSI was in range [50,70] at entry (short_range_condition)
        # What was it EXACTLY at the start of the previous trade?

        # How many crossunders between prev_exit and 2nd_SE?
        w_mask = (idx > prev_exit) & (idx <= second_se)
        rsi_prev_shifted = btc_rsi.shift(1)
        cross_mask = (rsi_prev_shifted >= cross_short_level) & (btc_rsi < cross_short_level)
        n_crosses = int(cross_mask[w_mask].sum())

        # How many of those are in-range (50-70)?
        in_range = (btc_rsi >= 50) & (btc_rsi <= 70)
        n_crosses_in_range = int((cross_mask & in_range)[w_mask].sum())

        # RSI between exit and 1st SE: check if RSI was ABOVE 52 during any bar of the trade
        trade_mask = (idx > prev_exit) & (idx <= first_se)
        rsi_during = btc_rsi[trade_mask]
        rsi_was_above_52_before_1st = any(rsi_during >= cross_short_level)
        n_bars_above_52_before_1st = int((rsi_during >= cross_short_level).sum())

        print(f"\n{'=' * 100}")
        print(f"{label}: prev_exit={prev_exit}, 1st_SE={first_se}, 2nd_SE={second_se}")
        print(f"  1st SE: RSI {r1_prev:.4f} → {r1_curr:.4f}  drop={r1_drop:.4f}  prev_above_52={r1_prev >= 52}")
        print(f"  2nd SE: RSI {r2_prev:.4f} → {r2_curr:.4f}  drop={r2_drop:.4f}  prev_above_52={r2_prev >= 52}")
        print(
            f"  Drop comparison: 1st={r1_drop:.4f}, 2nd={r2_drop:.4f}, larger={'1st' if r1_drop > r2_drop else '2nd'}"
        )
        print(f"  Total crossunders between exit and 2nd SE: {n_crosses} ({n_crosses_in_range} in range)")
        print(f"  RSI was above 52 before 1st SE? {rsi_was_above_52_before_1st} ({n_bars_above_52_before_1st} bars)")

        # KEY: What was RSI doing DURING the previous trade?
        # Check if RSI dipped below 52 during the trade
        # If so, and the position was short, then TV might consider that the
        # crossunder "belongs" to the trade and the first post-exit crossunder
        # is actually a "continuation" not a "fresh" signal

        # Also check: what was RSI right at the exit bar?
        if prev_exit in btc_rsi.index:
            rsi_at_exit = btc_rsi.loc[prev_exit]
            print(f"  RSI at exit bar: {rsi_at_exit:.4f} {'< 52' if rsi_at_exit < 52 else '>= 52'}")

        # Check bars between exit and 1st SE with RSI path
        print(f"  RSI path from exit to 1st SE:")
        transition_mask = (idx >= prev_exit) & (idx <= first_se)
        below_52_consecutive = 0
        max_below_52_consecutive = 0
        for ts in idx[transition_mask]:
            rsi_val = btc_rsi.loc[ts]
            if rsi_val < cross_short_level:
                below_52_consecutive += 1
                max_below_52_consecutive = max(max_below_52_consecutive, below_52_consecutive)
            else:
                below_52_consecutive = 0
        print(f"    Max consecutive bars below 52: {max_below_52_consecutive}")

    # ANOTHER ANGLE: Check if TV entries happen on bars where the RSI drop is
    # particularly STRONG (above some threshold)
    print("\n\n" + "=" * 100)
    print("RSI DROP COMPARISON: 1st SE vs 2nd SE (TV entry)")
    print("Hypothesis: TV only enters when the crossunder drop exceeds some threshold")
    print("=" * 100)

    drops_1st = []
    drops_2nd = []
    for label, _, first_se_str, second_se_str, _, _ in unknown_cases:
        first_se = pd.Timestamp(first_se_str)
        second_se = pd.Timestamp(second_se_str)
        first_prev = first_se - pd.Timedelta(minutes=30)
        second_prev = second_se - pd.Timedelta(minutes=30)
        r1_prev = btc_rsi.loc[first_prev]
        r1_curr = btc_rsi.loc[first_se]
        r2_prev = btc_rsi.loc[second_prev]
        r2_curr = btc_rsi.loc[second_se]
        d1 = r1_prev - r1_curr
        d2 = r2_prev - r2_curr
        drops_1st.append(d1)
        drops_2nd.append(d2)
        print(f"  {label}: 1st_drop={d1:.4f}  2nd_drop={d2:.4f}")

    print(f"\n  Mean 1st drop: {np.mean(drops_1st):.4f}")
    print(f"  Mean 2nd drop: {np.mean(drops_2nd):.4f}")
    print(f"  1st drop > 2nd in {sum(d1 > d2 for d1, d2 in zip(drops_1st, drops_2nd, strict=True))}/6 cases")

    # Check ALL SE signals in the dataset: what's the distribution of drops?
    rsi_prev_s = btc_rsi.shift(1)
    cross_all = (rsi_prev_s >= 52) & (btc_rsi < 52) & (btc_rsi >= 50) & (btc_rsi <= 70)
    drops_all = (rsi_prev_s - btc_rsi)[cross_all]
    print(f"\n  ALL SE crossunder drops distribution:")
    print(f"    Count: {len(drops_all)}")
    print(f"    Mean: {drops_all.mean():.4f}")
    print(f"    Min: {drops_all.min():.4f}")
    print(f"    Max: {drops_all.max():.4f}")
    print(f"    Median: {drops_all.median():.4f}")
    print(f"    25th percentile: {drops_all.quantile(0.25):.4f}")
    print(f"    75th percentile: {drops_all.quantile(0.75):.4f}")


asyncio.run(main())
