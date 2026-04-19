"""
Check which crossunders between engine and TV signal bars pass/fail the range condition.
Range for short: RSI >= 50 AND RSI <= 70

If a crossunder passes range, it should fire SE=1.
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

from backend.backtesting.service import BacktestService
from backend.core.indicators.momentum import calculate_rsi

CROSS_LEVEL = 52.0
RANGE_MIN = 50.0
RANGE_MAX = 70.0

# Root data: (root_id, prev_exit, eng_signal, tv_signal)
ROOTS = [
    (9, "2025-01-27 18:30", "2025-01-28 17:30", "2025-01-28 14:00"),
    (12, "2025-02-05 18:30", "2025-02-06 14:00", "2025-02-07 05:00"),
    (85, "2025-08-15 15:30", "2025-08-16 01:00", "2025-08-16 13:30"),
    (89, "2025-08-25 19:00", "2025-08-27 02:30", "2025-08-27 12:00"),
    (91, "2025-09-01 20:30", "2025-09-02 11:00", "2025-09-02 18:00"),
    (144, "2026-02-07 16:00", "2026-02-07 15:30", "2026-02-08 03:00"),
]


async def main():
    svc = BacktestService()

    btc_warmup = await svc._fetch_historical_data(
        "BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")
    )
    btc_main = await svc._fetch_historical_data(
        "BTCUSDT", "30", pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2026-02-24", tz="UTC")
    )
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    btc_rsi_arr = calculate_rsi(btc["close"].values, period=14)
    btc_rsi = pd.Series(btc_rsi_arr, index=btc.index)

    for root_id, prev_exit_str, eng_str, tv_str in ROOTS:
        prev_exit = pd.Timestamp(prev_exit_str)
        eng_sig = pd.Timestamp(eng_str)
        tv_sig = pd.Timestamp(tv_str)

        # Get range from prev_exit - 1 bar to tv_sig + 1 bar
        window = btc_rsi[
            (btc_rsi.index >= prev_exit - pd.Timedelta(minutes=30)) & (btc_rsi.index <= tv_sig + pd.Timedelta(hours=1))
        ]

        print(f"\n{'=' * 120}")
        print(f"ROOT #{root_id}  |  prev_exit={prev_exit_str}  eng={eng_str}  tv={tv_str}")
        print(f"{'=' * 120}")
        print(f"  Crossunders (RSI_prev >= {CROSS_LEVEL}, RSI < {CROSS_LEVEL}):")
        print(f"  {'Bar':>22s}  {'RSI_prev':>8s}  {'RSI':>8s}  {'range_ok':>8s}  {'signal':>8s}  Notes")

        cross_count = 0
        for j in range(1, len(window)):
            rp = window.iloc[j - 1]
            rc = window.iloc[j]
            if rp >= CROSS_LEVEL and rc < CROSS_LEVEL:
                cross_count += 1
                in_range = RANGE_MIN <= rc <= RANGE_MAX
                signal = in_range  # combined signal = range AND cross
                ts = window.index[j]
                ts_str = str(ts)[:19]

                notes = []
                if ts_str == prev_exit_str:
                    notes.append("PREV_EXIT")
                if ts_str == eng_str:
                    notes.append("ENGINE_SIGNAL")
                if ts_str == tv_str:
                    notes.append("TV_SIGNAL")

                # Check if between prev exit and TV signal
                is_between = ts >= prev_exit and ts <= tv_sig

                print(
                    f"  {ts_str:>22s}  {rp:8.4f}  {rc:8.4f}  {'YES' if in_range else 'NO':>8s}  "
                    f"{'SE=1' if signal else 'SE=0':>8s}  {'  '.join(notes)}{'  *between*' if is_between else ''}"
                )

        print(f"  Total crossunders in window: {cross_count}")

        # Count how many SE=1 signals between prev_exit and TV_signal
        valid_signals = []
        for j in range(1, len(window)):
            rp = window.iloc[j - 1]
            rc = window.iloc[j]
            ts = window.index[j]
            if rp >= CROSS_LEVEL and rc < CROSS_LEVEL and RANGE_MIN <= rc <= RANGE_MAX:
                if ts > prev_exit and ts <= tv_sig:
                    valid_signals.append((str(ts)[:19], rc))

        print(f"  Valid SE=1 signals between prev_exit and TV_signal (exclusive): {len(valid_signals)}")
        for ts, rsi in valid_signals:
            is_eng = ts == eng_str
            is_tv = ts == tv_str
            print(f"    {ts}  RSI={rsi:.4f}  {'ENGINE' if is_eng else ''}{'TV' if is_tv else ''}")

    print("\nDone.")


asyncio.run(main())
