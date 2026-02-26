"""Check ETH RSI range condition at engine signal bars for UNKNOWN cases.
SE = short_range_condition & cross_short
short_range_condition = (rsi >= 50) & (rsi <= 70) — using ETH RSI
cross_short = (btc_rsi_prev >= 52) & (btc_rsi < 52) — using BTC RSI

If SE is True, BOTH conditions must be True.
But is ETH RSI actually in range [50, 70] at the engine signal bar?
What about the bar AFTER (the entry bar)?
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


async def main():
    svc = BacktestService()
    eth = await svc._fetch_historical_data(
        "ETHUSDT", "30", pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2026-02-24", tz="UTC")
    )
    btc = await svc._fetch_historical_data(
        "BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), pd.Timestamp("2026-02-24", tz="UTC")
    )
    btc = btc[~btc.index.duplicated(keep="last")]

    # ETH RSI (on ETH close)
    eth_rsi = pd.Series(calculate_rsi(eth["close"], period=14), index=eth.index)
    # BTC RSI (on BTC close, with full warmup then reindex to ETH)
    btc_rsi_full = pd.Series(calculate_rsi(btc["close"], period=14), index=btc.index)
    btc_rsi = btc_rsi_full.reindex(eth.index)

    # UNKNOWN cases with their signal bars
    cases = [
        ("E#20/TV#22", "2025-02-22 10:30", "2025-02-22 14:30"),
        ("E#54/TV#56", "2025-05-09 15:00", "2025-05-09 19:00"),
        ("E#82/TV#85", "2025-08-16 01:00", "2025-08-16 13:30"),
        ("E#86/TV#89", "2025-08-27 02:30", "2025-08-27 12:00"),
        ("E#88/TV#91", "2025-09-02 11:00", "2025-09-02 18:00"),
        ("E#117/TV#119", "2025-11-25 00:00", "2025-11-25 05:00"),
    ]

    print(f"{'Case':<18s}  {'Bar':19s}  {'ETH RSI':>8s}  {'BTC RSI':>8s}  {'BTC prev':>8s}  Range50-70  Cross↓52  SE?")
    print("-" * 115)

    for desc, eng_sig, tv_sig in cases:
        for label, sig_bar in [("ENG", eng_sig), ("TV", tv_sig)]:
            ts = pd.Timestamp(sig_bar)
            if ts not in eth_rsi.index:
                print(f"{desc:<18s}  {sig_bar:19s}  NOT FOUND")
                continue
            idx = eth_rsi.index.get_loc(ts)
            e_rsi = eth_rsi.iloc[idx]
            b_rsi = btc_rsi.iloc[idx]
            b_prev = btc_rsi.iloc[idx - 1] if idx > 0 else float("nan")

            in_range = 50 <= e_rsi <= 70
            cross = b_prev >= 52 and b_rsi < 52
            se = in_range and cross

            marker = f"  ← {label}"
            print(
                f"{desc:<18s}  {sig_bar:19s}  {e_rsi:8.4f}  {b_rsi:8.4f}  {b_prev:8.4f}  "
                f"{'YES':10s}  {'YES':8s}  {'SE✅' if se else 'NO'}{marker}"
                if se
                else f"{desc:<18s}  {sig_bar:19s}  {e_rsi:8.4f}  {b_rsi:8.4f}  {b_prev:8.4f}  "
                f"{'YES' if in_range else 'NO':10s}  {'YES' if cross else 'NO':8s}  {'SE✅' if se else 'NO❌'}{marker}"
            )

    # Now let me check something critical: what is the ETH RSI at bars BETWEEN
    # the two SE signals? Is there a pattern where ETH RSI goes OUT of range?
    print("\n\n" + "=" * 80)
    print("ETH RSI trajectory between engine signal and TV signal")
    print("=" * 80)

    for desc, eng_sig, tv_sig in cases:
        eng_ts = pd.Timestamp(eng_sig)
        tv_ts = pd.Timestamp(tv_sig)

        mask = (eth_rsi.index >= eng_ts) & (eth_rsi.index <= tv_ts)
        range_data = eth_rsi[mask]

        print(f"\n  {desc}: {eng_sig} → {tv_sig}")
        min_eth = range_data.min()
        max_eth = range_data.max()
        print(f"  ETH RSI range: [{min_eth:.4f}, {max_eth:.4f}]")

        # Show all bars where BTC RSI crossunders occur
        for ts in range_data.index:
            idx = eth_rsi.index.get_loc(ts)
            b_rsi = btc_rsi.iloc[idx]
            b_prev = btc_rsi.iloc[idx - 1] if idx > 0 else float("nan")
            e_rsi_val = eth_rsi.iloc[idx]
            cross = b_prev >= 52 and b_rsi < 52
            in_range = 50 <= e_rsi_val <= 70

            if cross:
                se = in_range and cross
                print(
                    f"    {ts}  ETH={e_rsi_val:.4f}  BTC={b_rsi:.4f}(prev={b_prev:.4f})  "
                    f"range={'Y' if in_range else 'N'}  cross=Y  SE={'✅' if se else '❌'}"
                )

    # BONUS: Check the E#9 (engine-only) and TV#1 cases
    print("\n\n" + "=" * 80)
    print("INTRA-BAR cases: TV#1 and E#6/TV#9")
    print("=" * 80)

    for desc, bar in [
        ("TV#1 signal", "2025-01-01 13:00"),
        ("E#1 signal", "2025-01-02 22:00"),
        ("TV#9/Root#9", "2025-01-28 14:00"),
        ("E#6 signal", "2025-01-28 17:30"),
    ]:
        ts = pd.Timestamp(bar)
        if ts not in eth_rsi.index:
            continue
        idx = eth_rsi.index.get_loc(ts)
        e_rsi = eth_rsi.iloc[idx]
        b_rsi = btc_rsi.iloc[idx]
        b_prev = btc_rsi.iloc[idx - 1] if idx > 0 else float("nan")
        in_range = 50 <= e_rsi <= 70
        cross = b_prev >= 52 and b_rsi < 52
        se = in_range and cross
        print(
            f"  {desc:20s}  {bar}  ETH={e_rsi:.4f}  BTC={b_rsi:.4f}(prev={b_prev:.4f})  "
            f"range={'Y' if in_range else 'N'}  cross={'Y' if cross else 'N'}  SE={'✅' if se else '❌'}"
        )


asyncio.run(main())
