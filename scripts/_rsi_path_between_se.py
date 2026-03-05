"""
Trace BTC RSI path between 1st SE and 2nd SE for all 6 UNKNOWN cases.
Key question: Does RSI go BACK ABOVE 52 between the two SE bars?
If so, TV might require RSI to "reset" above the level before a new crossunder fires.

Also check: what happens to the SHORT RANGE condition (50 <= rsi <= 70)?
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

    # Compute BTC RSI aligned to ETH bars
    btc_close = btc["close"]
    btc_aligned = btc_close.reindex(candles.index, method="ffill")
    delta = btc_aligned.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    btc_rsi = 100 - (100 / (1 + rs))

    idx = candles.index

    # WAIT! We're computing RSI on btc_aligned (ffill'd to ETH bars)
    # But the _handle_rsi code computes RSI on the FULL BTC series first, THEN reindexes.
    # Let me compute it the same way.
    delta2 = btc_close.diff()
    gain2 = delta2.where(delta2 > 0, 0.0)
    loss2 = (-delta2).where(delta2 < 0, 0.0)
    avg_gain2 = gain2.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss2 = loss2.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs2 = avg_gain2 / avg_loss2
    btc_rsi_full = 100 - (100 / (1 + rs2))
    # Reindex to ETH candles
    btc_rsi2 = btc_rsi_full.reindex(candles.index, method="ffill")

    unknown_cases = [
        ("E#23", "2025-02-22 10:30", "2025-02-22 13:30"),
        ("E#57", "2025-05-09 15:00", "2025-05-09 19:00"),
        ("E#85", "2025-08-16 01:00", "2025-08-16 13:30"),
        ("E#89", "2025-08-27 02:30", "2025-08-27 12:00"),
        ("E#91", "2025-09-02 11:00", "2025-09-02 18:00"),
        ("E#120", "2025-11-25 00:00", "2025-11-25 05:00"),
    ]

    cross_level = 52.0
    range_low = 50.0
    range_high = 70.0

    print("=" * 130)
    print("BTC RSI PATH between 1st SE and 2nd SE for UNKNOWN cases")
    print(f"Cross level: {cross_level}, Short range: [{range_low}, {range_high}]")
    print("Using RSI computed on FULL BTC series, then reindexed to ETH bars (same as engine)")
    print("=" * 130)

    for label, first_se_str, second_se_str in unknown_cases:
        first_se = pd.Timestamp(first_se_str)
        second_se = pd.Timestamp(second_se_str)

        # Show RSI from 1 bar before 1st SE to 1 bar after 2nd SE
        window_start = first_se - pd.Timedelta(minutes=30)
        window_end = second_se + pd.Timedelta(minutes=30)

        w_mask = (idx >= window_start) & (idx <= window_end)

        print(f"\n{'=' * 110}")
        print(f"{label}: 1st SE={first_se}, 2nd SE={second_se}")
        print(f"{'Bar':>25s}  {'BTC RSI':>12s}  {'Prev RSI':>12s}  {'Range?':>8s}  {'Cross?':>8s}  {'SE?':>6s}  Notes")
        print("-" * 110)

        rsi_went_above_52 = False
        min_rsi = 100
        max_rsi = 0
        bars_below_52 = 0
        bars_above_52 = 0

        for ts in idx[w_mask]:
            i = idx.get_loc(ts)
            rsi_val = btc_rsi2.iloc[i]
            rsi_prev = btc_rsi2.iloc[i - 1] if i > 0 else np.nan

            in_range = range_low <= rsi_val <= range_high
            crossunder = (not np.isnan(rsi_prev)) and rsi_prev >= cross_level and rsi_val < cross_level

            notes = []
            if ts == first_se:
                notes.append("<<< 1st SE")
            elif ts == second_se:
                notes.append("<<< 2nd SE")

            if ts > first_se and ts < second_se:
                if rsi_val >= cross_level:
                    bars_above_52 += 1
                    if not rsi_went_above_52:
                        notes.append("** RSI goes ABOVE 52 **")
                        rsi_went_above_52 = True
                else:
                    bars_below_52 += 1
                min_rsi = min(min_rsi, rsi_val)
                max_rsi = max(max_rsi, rsi_val)

            se_flag = "TRUE" if crossunder and in_range else "-"
            print(
                f"{ts!s:>25s}  {rsi_val:12.6f}  {rsi_prev:12.6f}  "
                f"{'YES' if in_range else 'no':>8s}  "
                f"{'CROSS!' if crossunder else '-':>8s}  "
                f"{se_flag:>6s}  "
                f"{'  '.join(notes)}"
            )

        print("\n  Between 1st and 2nd SE:")
        print(f"    RSI went above 52? {rsi_went_above_52}")
        print(f"    Bars above 52: {bars_above_52}, Bars below 52: {bars_below_52}")
        if max_rsi > 0:
            print(f"    RSI range: [{min_rsi:.6f}, {max_rsi:.6f}]")

    # KEY QUESTION: Does RSI go above 52 between the two SE bars?
    # If YES in all 6 cases, then TV's ta.crossunder naturally fires on the 2nd one
    # because RSI went back above 52 and then crossed down again.
    # In that case, our code is ALSO generating a crossunder on the 2nd bar,
    # but it ALSO generates one on the 1st bar.
    # The engine takes the 1st one. TV takes the 2nd one.
    # This means TV has some mechanism to SKIP the 1st crossunder.

    print("\n\n" + "=" * 110)
    print("ALTERNATIVE HYPOTHESIS: Does TV's 'process_orders_on_close' affect crossunder detection?")
    print("In Pine Script with process_orders_on_close=true:")
    print("  The strategy 'sees' the bar close, then processes orders.")
    print("  This is what we do (entry_on_next_bar_open=True).")
    print("  BUT: what if TV's process_orders_on_close also affects WHEN signals are evaluated?")
    print("  I.e., TV evaluates signals on the CLOSE of bar i, but the entry is on the OPEN of bar i+1.")
    print("  This should be the same as what we do.")
    print("=" * 110)


asyncio.run(main())
