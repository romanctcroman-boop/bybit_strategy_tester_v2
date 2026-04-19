"""
Test hypothesis: TV's request.security() introduces a 1-bar delay in BTC RSI.
If so, the crossunder condition would be:
  rsi_prev = btc_rsi[bar - 2]  (instead of bar - 1)
  rsi      = btc_rsi[bar - 1]  (instead of bar)

Check if this eliminates the 4 root crossunders.
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
    btc = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2023-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )
    candles = await svc._fetch_historical_data(
        "ETHUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )

    btc_rsi_arr = calculate_rsi(btc["close"].values, period=14)
    btc_rsi = pd.Series(btc_rsi_arr, index=btc.index)
    btc_rsi_eth = btc_rsi.reindex(candles.index, method="ffill")

    timestamps = candles.index

    roots = {
        "Root #12": ("2025-02-06 14:00:00", "2025-02-07 05:00:00"),
        "Root #85": ("2025-08-16 01:00:00", "2025-08-16 13:30:00"),
        "Root #89": ("2025-08-27 02:30:00", "2025-08-27 12:00:00"),
        "Root #91": ("2025-09-02 11:00:00", "2025-09-02 18:00:00"),
    }

    print("HYPOTHESIS: TV's request.security() has a 1-bar delay on BTC RSI")
    print("=" * 100)

    for name, (engine_time, tv_time) in roots.items():
        e_idx = timestamps.get_loc(pd.Timestamp(engine_time))
        t_idx = timestamps.get_loc(pd.Timestamp(tv_time))

        # Normal (no delay): cross at bar[i] uses rsi[i] and rsi[i-1]
        normal_rsi = btc_rsi_eth.iloc[e_idx]
        normal_rsi_prev = btc_rsi_eth.iloc[e_idx - 1]
        normal_cross = normal_rsi_prev >= 52 and normal_rsi < 52

        # 1-bar delayed: rsi values are shifted by 1
        # On bar[i], TV sees btc_rsi[i-1] as "current" and btc_rsi[i-2] as "previous"
        delayed_rsi = btc_rsi_eth.iloc[e_idx - 1]  # current = previous bar's value
        delayed_rsi_prev = btc_rsi_eth.iloc[e_idx - 2]  # prev = 2 bars ago
        delayed_cross = delayed_rsi_prev >= 52 and delayed_rsi < 52

        print(f"\n{name} (engine signal bar: {engine_time}):")
        print(f"  Normal:  rsi_prev={normal_rsi_prev:.4f}, rsi={normal_rsi:.4f}, cross={normal_cross}")
        print(f"  Delayed: rsi_prev={delayed_rsi_prev:.4f}, rsi={delayed_rsi:.4f}, cross={delayed_cross}")

        # Also check TV's signal bar with both methods
        tv_normal_rsi = btc_rsi_eth.iloc[t_idx]
        tv_normal_rsi_prev = btc_rsi_eth.iloc[t_idx - 1]
        tv_normal_cross = tv_normal_rsi_prev >= 52 and tv_normal_rsi < 52

        tv_delayed_rsi = btc_rsi_eth.iloc[t_idx - 1]
        tv_delayed_rsi_prev = btc_rsi_eth.iloc[t_idx - 2]
        tv_delayed_cross = tv_delayed_rsi_prev >= 52 and tv_delayed_rsi < 52

        print(f"  TV signal bar ({tv_time}):")
        print(f"    Normal:  rsi_prev={tv_normal_rsi_prev:.4f}, rsi={tv_normal_rsi:.4f}, cross={tv_normal_cross}")
        print(f"    Delayed: rsi_prev={tv_delayed_rsi_prev:.4f}, rsi={tv_delayed_rsi:.4f}, cross={tv_delayed_cross}")

        # Now do a FULL check: recompute all SE signals with 1-bar delay
        # and see how many total signals change

    # Full recompute with delay
    print("\n\n" + "=" * 100)
    print("FULL SIGNAL COMPARISON: Normal vs 1-bar delayed BTC RSI")
    print("=" * 100)

    rsi_normal = btc_rsi_eth.copy()
    rsi_delayed = btc_rsi_eth.shift(1)  # Shift RSI by 1 bar (adds 1-bar delay)

    # Normal cross detection
    rsi_prev_normal = rsi_normal.shift(1)
    cross_normal = (rsi_prev_normal >= 52) & (rsi_normal < 52)
    range_normal = (rsi_normal >= 50) & (rsi_normal <= 70)
    se_normal = cross_normal & range_normal

    # Delayed cross detection
    rsi_prev_delayed = rsi_delayed.shift(1)
    cross_delayed = (rsi_prev_delayed >= 52) & (rsi_delayed < 52)
    range_delayed = (rsi_delayed >= 50) & (rsi_delayed <= 70)
    se_delayed = cross_delayed & range_delayed

    print(f"  Normal SE signals: {se_normal.sum()}")
    print(f"  Delayed SE signals: {se_delayed.sum()}")

    # Check which engine signal bars are affected
    for name, (engine_time, tv_time) in roots.items():
        e_idx = timestamps.get_loc(pd.Timestamp(engine_time))
        t_idx = timestamps.get_loc(pd.Timestamp(tv_time))

        print(f"\n  {name}:")
        print(f"    Engine bar SE: normal={se_normal.iloc[e_idx]}, delayed={se_delayed.iloc[e_idx]}")
        print(f"    TV bar SE:     normal={se_normal.iloc[t_idx]}, delayed={se_delayed.iloc[t_idx]}")


asyncio.run(main())
