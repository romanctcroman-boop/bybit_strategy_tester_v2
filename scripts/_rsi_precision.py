"""Check RSI values precisely at the bars where engine fires but TV doesn't.
Maybe TV's RSI is slightly different (e.g., rounding, precision)
and the crossunder doesn't actually happen in TV."""

import asyncio
import json
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.service import BacktestService


async def main():
    svc = BacktestService()

    candles = await svc._fetch_historical_data(
        "ETHUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc_warmup = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2020-01-01", tz="UTC"),
        pd.Timestamp("2025-01-01", tz="UTC"),
    )
    btc_main = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    # Compute BTC RSI-14 with RMA (Pine-compatible)
    btc_close = btc["close"]
    period = 14
    delta = btc_close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Pine's ta.rsi uses RMA = EMA with alpha=1/period
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    btc_rsi_full = 100 - (100 / (1 + rs))

    # Reindex to ETH bars
    rsi = btc_rsi_full.reindex(candles.index, method="ffill")

    # Check bars around each root's engine signal
    bars_to_check = [
        ("Root #12 engine signal", "2025-02-06 14:00"),
        ("Root #12 prev bar", "2025-02-06 13:30"),
        ("Root #12 TV signal", "2025-02-07 05:00"),
        ("Root #12 TV prev bar", "2025-02-07 04:30"),
        ("Root #85 engine signal", "2025-08-16 01:00"),
        ("Root #85 prev bar", "2025-08-16 00:30"),
        ("Root #85 TV signal", "2025-08-16 13:30"),
        ("Root #85 TV prev bar", "2025-08-16 13:00"),
        ("Root #89 engine signal", "2025-08-27 02:30"),
        ("Root #89 prev bar", "2025-08-27 02:00"),
        ("Root #89 TV signal", "2025-08-27 12:00"),
        ("Root #89 TV prev bar", "2025-08-27 11:30"),
        ("Root #91 engine signal", "2025-09-02 11:00"),
        ("Root #91 prev bar", "2025-09-02 10:30"),
        ("Root #91 TV signal", "2025-09-02 18:00"),
        ("Root #91 TV prev bar", "2025-09-02 17:30"),
    ]

    print(f"{'Label':<30} | {'Timestamp':<20} | {'BTC RSI':>12} | Cross↓52?")
    print("-" * 85)

    for label, ts_str in bars_to_check:
        ts = pd.Timestamp(ts_str)
        rsi_val = rsi.loc[ts] if ts in rsi.index else np.nan

        # Find previous bar's RSI
        idx = candles.index.get_loc(ts)
        rsi_prev = rsi.iloc[idx - 1] if idx > 0 else np.nan

        cross = "YES" if (rsi_prev >= 52 and rsi_val < 52) else "NO"
        range_ok = "✓" if (rsi_val >= 50 and rsi_val <= 70) else "✗"

        is_signal = "prev" in label.lower()

        if "prev bar" in label.lower():
            print(f"{label:<30} | {ts_str:<20} | {rsi_val:>12.6f} |")
        else:
            print(f"{label:<30} | {ts_str:<20} | {rsi_val:>12.6f} | {cross} (prev={rsi_prev:.6f}) range={range_ok}")

    # KEY: Let's check if maybe the BTC RSI is computed with a different warmup
    # or if there's a difference between our BTC 30m data and TV's BTC 30m data
    # at these specific timestamps

    print("\n\n=== BTC close prices at these bars ===")
    for label, ts_str in bars_to_check:
        if "prev bar" in label.lower():
            continue
        ts = pd.Timestamp(ts_str)
        # Find the BTC 30m bar that corresponds
        # Since we reindex with ffill, the BTC bar might be at a different timestamp
        btc_ts = btc_rsi_full.index[btc_rsi_full.index <= ts][-1]
        btc_close_val = btc_close.loc[btc_ts]
        btc_rsi_val = btc_rsi_full.loc[btc_ts]
        prev_btc_ts = btc_rsi_full.index[btc_rsi_full.index <= ts][-2]
        prev_btc_rsi = btc_rsi_full.loc[prev_btc_ts]

        print(
            f"{label:<30} | ETH bar: {ts_str}, BTC bar: {btc_ts}, "
            f"BTC close={btc_close_val:.2f}, BTC RSI={btc_rsi_val:.6f}, "
            f"prev BTC RSI={prev_btc_rsi:.6f}"
        )

    # Check: is the RSI very close to 52 at these bars?
    print("\n\n=== How close to 52? ===")
    for label, ts_str in bars_to_check:
        if "prev bar" in label.lower():
            continue
        ts = pd.Timestamp(ts_str)
        rsi_val = rsi.loc[ts]
        idx = candles.index.get_loc(ts)
        rsi_prev = rsi.iloc[idx - 1]
        if rsi_prev >= 52 and rsi_val < 52:
            margin = 52 - rsi_val  # how far below 52
            print(f"{label:<30}: RSI={rsi_val:.6f}, margin below 52 = {margin:.6f}")


asyncio.run(main())
