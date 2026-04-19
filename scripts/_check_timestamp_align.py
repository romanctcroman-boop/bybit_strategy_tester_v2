"""
Check for timestamp alignment between BTC 30m and ETH 30m bars.
Specifically, check at the 4 root signal bars whether the ffill reindex
might assign a DIFFERENT BTC bar than TV would use.
"""

import asyncio
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.service import BacktestService
from backend.core.indicators import calculate_rsi


async def main():
    svc = BacktestService()

    # Load ETH and BTC data
    candles = await svc._fetch_historical_data(
        "ETHUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2023-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )

    eth_ts = candles.index
    btc_ts = btc.index

    print(f"ETH bars: {len(eth_ts)}, from {eth_ts[0]} to {eth_ts[-1]}")
    print(f"BTC bars: {len(btc_ts)}, from {btc_ts[0]} to {btc_ts[-1]}")

    # Check: for each ETH bar in the strategy period, is there an EXACT matching BTC bar?
    eth_strategy = eth_ts  # strategy period
    btc_strategy = btc_ts[btc_ts >= eth_strategy[0]]

    missing_in_btc = eth_strategy.difference(btc_strategy)
    missing_in_eth = btc_strategy[btc_strategy <= eth_strategy[-1]].difference(eth_strategy)

    print(f"\nETH bars missing from BTC index: {len(missing_in_btc)}")
    if len(missing_in_btc) > 0 and len(missing_in_btc) <= 20:
        for ts in missing_in_btc:
            print(f"  {ts}")

    print(f"BTC bars missing from ETH index: {len(missing_in_eth)}")
    if len(missing_in_eth) > 0 and len(missing_in_eth) <= 20:
        for ts in missing_in_eth:
            print(f"  {ts}")

    # Now check at the 4 root signal bars AND the bars before them:
    # What BTC bar gets assigned via reindex ffill?
    roots = {
        "Root #12": "2025-02-06 14:00:00",
        "Root #85": "2025-08-16 01:00:00",
        "Root #89": "2025-08-27 02:30:00",
        "Root #91": "2025-09-02 11:00:00",
    }

    # Compute BTC RSI
    btc_rsi_arr = calculate_rsi(btc["close"].values, period=14)
    btc_rsi = pd.Series(btc_rsi_arr, index=btc.index)

    # Check: does the RSI reindex correctly?
    btc_rsi_eth = btc_rsi.reindex(candles.index, method="ffill")

    for name, time_str in roots.items():
        t = pd.Timestamp(time_str)
        idx = eth_ts.get_loc(t)
        prev_t = eth_ts[idx - 1]

        # Check if these exact timestamps exist in BTC index
        t_in_btc = t in btc_ts
        prev_in_btc = prev_t in btc_ts

        print(f"\n{name} ({time_str}):")
        print(f"  Signal bar {t}: in_BTC={t_in_btc}")
        print(f"  Prev bar {prev_t}: in_BTC={prev_in_btc}")

        if t_in_btc:
            btc_rsi_direct = btc_rsi[t]
            btc_rsi_ffill = btc_rsi_eth[t]
            print(f"  BTC RSI direct: {btc_rsi_direct:.6f}")
            print(f"  BTC RSI ffill:  {btc_rsi_ffill:.6f}")
            print(f"  Match: {btc_rsi_direct == btc_rsi_ffill}")

        if prev_in_btc:
            btc_rsi_direct_prev = btc_rsi[prev_t]
            btc_rsi_ffill_prev = btc_rsi_eth[prev_t]
            print(f"  BTC RSI prev direct: {btc_rsi_direct_prev:.6f}")
            print(f"  BTC RSI prev ffill:  {btc_rsi_ffill_prev:.6f}")
            print(f"  Match: {btc_rsi_direct_prev == btc_rsi_ffill_prev}")

    # Also check: what happens if there's a BTC bar BETWEEN two ETH bars?
    # This would mean BTC has a 30m bar that ETH doesn't, causing ffill to use
    # a stale BTC RSI value
    print("\n" + "=" * 80)
    print("Checking around root signal bars for BTC bars between ETH bars...")

    for name, time_str in roots.items():
        t = pd.Timestamp(time_str)
        idx = eth_ts.get_loc(t)

        # Check 5 bars around the signal bar
        for j in range(idx - 3, idx + 3):
            eth_bar = eth_ts[j]
            # Find BTC bars between eth_ts[j-1] and eth_ts[j]
            if j > 0:
                prev_eth = eth_ts[j - 1]
                btc_between = btc_ts[(btc_ts > prev_eth) & (btc_ts < eth_bar)]
                if len(btc_between) > 0:
                    print(f"  {name}: BTC bars between {prev_eth} and {eth_bar}:")
                    for b in btc_between:
                        print(f"    {b}")


asyncio.run(main())
