"""
Compare RSI values at the 4 root signal bars using:
1. BTC warmup from 2023-01-23 (our current warmup)
2. BTC warmup from 2020-03-25 (earliest available from Bybit)

If the RSI values differ, it would explain why TV sees different crosses.
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

    # Load main period BTC data (strategy period)
    btc_main = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )

    # Load warmup starting from 2020 (earliest available)
    btc_from_2020 = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2020-01-01", tz="UTC"),
        pd.Timestamp("2025-01-01", tz="UTC"),
    )

    # Load warmup starting from 2023 (what we currently use)
    btc_from_2023 = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2023-01-01", tz="UTC"),
        pd.Timestamp("2025-01-01", tz="UTC"),
    )

    # Combine warmup + main
    btc_full_2020 = pd.concat([btc_from_2020, btc_main]).sort_index()
    btc_full_2020 = btc_full_2020[~btc_full_2020.index.duplicated(keep="last")]

    btc_full_2023 = pd.concat([btc_from_2023, btc_main]).sort_index()
    btc_full_2023 = btc_full_2023[~btc_full_2023.index.duplicated(keep="last")]

    print(f"BTC data from 2020: {len(btc_full_2020)} bars, {btc_full_2020.index[0]} to {btc_full_2020.index[-1]}")
    print(f"BTC data from 2023: {len(btc_full_2023)} bars, {btc_full_2023.index[0]} to {btc_full_2023.index[-1]}")

    # Compute RSI on both
    rsi_2020 = calculate_rsi(btc_full_2020["close"].values, period=14)
    rsi_2020_series = pd.Series(rsi_2020, index=btc_full_2020.index)

    rsi_2023 = calculate_rsi(btc_full_2023["close"].values, period=14)
    rsi_2023_series = pd.Series(rsi_2023, index=btc_full_2023.index)

    # Load ETH candles to get the index mapping
    candles = await svc._fetch_historical_data(
        "ETHUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )

    # Reindex both RSI series to the ETH candle index
    rsi_2020_eth = rsi_2020_series.reindex(candles.index, method="ffill")
    rsi_2023_eth = rsi_2023_series.reindex(candles.index, method="ffill")

    timestamps = candles.index

    # Root signal bars (engine's signal bar)
    roots = {
        "Root #12": "2025-02-06 14:00:00",
        "Root #85": "2025-08-16 01:00:00",
        "Root #89": "2025-08-27 02:30:00",
        "Root #91": "2025-09-02 11:00:00",
    }

    print("\n" + "=" * 100)
    print("RSI COMPARISON AT ROOT SIGNAL BARS")
    print("=" * 100)

    for name, time_str in roots.items():
        t = pd.Timestamp(time_str)
        idx = timestamps.get_loc(t)

        rsi_2020_val = rsi_2020_eth.iloc[idx]
        rsi_2020_prev = rsi_2020_eth.iloc[idx - 1]
        rsi_2023_val = rsi_2023_eth.iloc[idx]
        rsi_2023_prev = rsi_2023_eth.iloc[idx - 1]

        cross_2020 = rsi_2020_prev >= 52 and rsi_2020_val < 52
        cross_2023 = rsi_2023_prev >= 52 and rsi_2023_val < 52

        diff_val = rsi_2020_val - rsi_2023_val
        diff_prev = rsi_2020_prev - rsi_2023_prev

        print(f"\n{name} ({time_str}):")
        print(f"  RSI (2020 warmup): prev={rsi_2020_prev:.6f}, bar={rsi_2020_val:.6f}, cross={cross_2020}")
        print(f"  RSI (2023 warmup): prev={rsi_2023_prev:.6f}, bar={rsi_2023_val:.6f}, cross={cross_2023}")
        print(f"  Difference: prev_Δ={diff_prev:.6f}, bar_Δ={diff_val:.6f}")
        print(f"  Margin below 52 (2020): {52 - rsi_2020_val:.6f}")
        print(f"  Margin below 52 (2023): {52 - rsi_2023_val:.6f}")

    # Also check some general statistics about the RSI difference
    common_idx = rsi_2020_eth.dropna().index.intersection(rsi_2023_eth.dropna().index)
    diff = rsi_2020_eth[common_idx] - rsi_2023_eth[common_idx]
    print("\n" + "=" * 100)
    print("OVERALL RSI DIFFERENCE STATISTICS (2020 - 2023 warmup)")
    print(f"  Common bars: {len(common_idx)}")
    print(f"  Mean diff: {diff.mean():.10f}")
    print(f"  Max diff: {diff.max():.10f}")
    print(f"  Min diff: {diff.min():.10f}")
    print(f"  Std diff: {diff.std():.10f}")
    print(f"  Max abs diff: {diff.abs().max():.10f}")

    # Show the bars with largest differences
    top_diffs = diff.abs().nlargest(20)
    print("\n  Top 20 bars with largest RSI difference:")
    for ts, d in top_diffs.items():
        actual_diff = diff[ts]
        print(f"    {ts}: Δ={actual_diff:.10f}")


asyncio.run(main())
