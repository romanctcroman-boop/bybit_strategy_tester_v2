"""Deep investigation: Why does TV skip the 1st valid crossunder and enter at the 2nd?
Category B divergences: E#20/TV#22, E#54/TV#56, E#57/TV#57, E#82/TV#85, E#86/TV#89, E#88/TV#91, E#117/TV#119

Hypothesis: The 1st crossunder occurs while the PREVIOUS trade is still OPEN in TV
(due to TV having a different exit time from a previous divergence cascade).
"""

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

TV_CSV = r"c:\Users\roman\Downloads\as4.csv"


def parse_tv_trades(csv_path):
    tv_raw = pd.read_csv(csv_path, sep=";")
    trades = []
    for i in range(0, len(tv_raw), 2):
        exit_row = tv_raw.iloc[i]
        entry_row = tv_raw.iloc[i + 1]
        entry_type = str(entry_row["Тип"]).strip()
        direction = "short" if "short" in entry_type.lower() else "long"
        entry_msk = pd.Timestamp(str(entry_row["Дата и время"]).strip())
        exit_msk = pd.Timestamp(str(exit_row["Дата и время"]).strip())
        entry_utc = entry_msk - pd.Timedelta(hours=3)
        exit_utc = exit_msk - pd.Timedelta(hours=3)
        pnl = float(str(exit_row["Чистая прибыль / убыток USDT"]).replace(",", ".").strip())
        trades.append(
            {
                "tv_num": i // 2 + 1,
                "direction": direction,
                "entry_time": entry_utc,
                "exit_time": exit_utc,
                "pnl": pnl,
            }
        )
    return trades


def main():
    tv_trades = parse_tv_trades(TV_CSV)

    # Category B cases - engine enters at 1st cross, TV enters at 2nd
    # Format: (eng_entry, tv_entry, tv_num)
    cases = [
        ("E#20/TV#22", "2025-02-22 11:00", "2025-02-22 15:00", 22),
        ("E#54/TV#56", "2025-05-09 15:30", "2025-05-09 19:30", 56),
        ("E#57/TV#57", "2025-05-13 08:00", "2025-05-13 23:30", 57),
        ("E#82/TV#85", "2025-08-16 01:30", "2025-08-16 14:00", 85),
        ("E#86/TV#89", "2025-08-27 03:00", "2025-08-27 12:30", 89),
        ("E#88/TV#91", "2025-09-02 11:30", "2025-09-02 18:30", 91),
        ("E#117/TV#119", "2025-11-25 00:30", "2025-11-25 05:30", 119),
    ]

    print("For each Category B divergence:")
    print("Check if the PREVIOUS TV trade is still open when engine's 1st cross fires\n")
    print(f"{'Case':<18s}  {'Prev TV exit':19s}  {'Eng 1st entry':19s}  {'TV entry':19s}  Still open?  Gap")
    print("-" * 120)

    for desc, eng_entry, tv_entry, tv_num in cases:
        eng_ts = pd.Timestamp(eng_entry)
        tv_ts = pd.Timestamp(tv_entry)

        # Find previous TV trade
        prev_tv = tv_trades[tv_num - 2]  # tv_num is 1-indexed
        prev_exit = prev_tv["exit_time"]

        still_open = eng_ts < prev_exit
        gap = eng_ts - prev_exit

        marker = "YES ←" if still_open else "no"
        print(f"{desc:<18s}  {str(prev_exit):19s}  {str(eng_ts):19s}  {str(tv_ts):19s}  {marker:11s}  {gap}")

        if still_open:
            # Show the previous trade details
            print(
                f"  → Prev TV#{prev_tv['tv_num']}: {prev_tv['direction']} "
                f"entry={prev_tv['entry_time']} exit={prev_exit}"
            )

    # Now check engine-only trades too
    print("\n\nEngine-only trades (engine has, TV doesn't):")
    print("Check if previous TV trade was still open\n")

    eng_only = [
        ("E#9", "2025-02-06 14:30", 12),  # Nearest TV trade before this
        ("E#55", "2025-05-11 05:30", 56),
        ("E#56", "2025-05-11 21:00", 56),
        ("E#89", "2025-09-02 19:30", 91),
    ]

    for desc, eng_entry, nearest_tv_num in eng_only:
        eng_ts = pd.Timestamp(eng_entry)

        # Find the TV trade that's active at this time
        active_tv = None
        for t in tv_trades:
            if t["entry_time"] <= eng_ts <= t["exit_time"]:
                active_tv = t
                break

        if active_tv:
            print(
                f"  {desc} entry={eng_ts}: TV#{active_tv['tv_num']} STILL OPEN "
                f"({active_tv['direction']} {active_tv['entry_time']} → {active_tv['exit_time']})"
            )
        else:
            # Check what TV trade is before/after
            prev_tv = None
            for t in tv_trades:
                if t["exit_time"] <= eng_ts:
                    prev_tv = t
                else:
                    break
            if prev_tv:
                gap = eng_ts - prev_tv["exit_time"]
                print(
                    f"  {desc} entry={eng_ts}: TV is FLAT. Prev TV#{prev_tv['tv_num']} "
                    f"exited {prev_tv['exit_time']} ({gap} ago)"
                )

    # TV-only trades
    print("\n\nTV-only trades (TV has, engine doesn't):")

    tv_only = [
        ("TV#2", 2),
        ("TV#3", 3),
        ("TV#4", 4),
        ("TV#5", 5),
        ("TV#58", 58),
        ("TV#59", 59),
        ("TV#60", 60),
        ("TV#136", 136),
    ]

    for desc, tv_num in tv_only:
        t = tv_trades[tv_num - 1]
        # Check what engine trade was active at this time
        print(f"  {desc}: {t['direction']} entry={t['entry_time']} exit={t['exit_time']} pnl={t['pnl']:.2f}")
        # Check previous TV trade
        if tv_num > 1:
            prev = tv_trades[tv_num - 2]
            gap = t["entry_time"] - prev["exit_time"]
            print(f"    Prev TV#{prev['tv_num']} exit={prev['exit_time']}, gap={gap}")


main()
