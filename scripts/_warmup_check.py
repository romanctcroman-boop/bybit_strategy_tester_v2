"""Verify RSI convergence with different warmup lengths.
Check if our BTC RSI matches the values we previously verified against TV."""

import asyncio
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.service import BacktestService


def compute_rsi(close, period=14):
    """Compute RSI using Wilder's RMA (same as Pine ta.rsi)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


async def main():
    svc = BacktestService()

    # Current approach: warmup from 2020-01-01
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
    btc_full = pd.concat([btc_warmup, btc_main]).sort_index()
    btc_full = btc_full[~btc_full.index.duplicated(keep="last")]

    rsi_from_2020 = compute_rsi(btc_full["close"])

    # Also try from 2018 (even more warmup)
    btc_2018 = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2018-01-01", tz="UTC"),
        pd.Timestamp("2020-01-01", tz="UTC"),
    )
    btc_from_2018 = pd.concat([btc_2018, btc_full]).sort_index()
    btc_from_2018 = btc_from_2018[~btc_from_2018.index.duplicated(keep="last")]
    rsi_from_2018 = compute_rsi(btc_from_2018["close"])

    # Also try with minimal warmup (500 bars ≈ 10 days for 30m)
    btc_short = btc_full.iloc[-20000:]  # ~400 days
    rsi_short = compute_rsi(btc_short["close"])

    # Compare at critical bars
    bars = [
        "2025-02-06 14:00",  # Root #12 engine signal
        "2025-02-06 13:30",  # Root #12 prev bar
        "2025-08-16 01:00",  # Root #85 engine signal
        "2025-08-16 00:30",  # Root #85 prev bar
        "2025-08-27 02:30",  # Root #89 engine signal
        "2025-08-27 02:00",  # Root #89 prev bar
        "2025-09-02 11:00",  # Root #91 engine signal
        "2025-09-02 10:30",  # Root #91 prev bar
    ]

    print(f"{'Bar':<25} | {'RSI_2018':>12} | {'RSI_2020':>12} | {'RSI_short':>12} | {'Δ(2018-2020)':>12}")
    print("-" * 90)

    for bar_str in bars:
        ts = pd.Timestamp(bar_str)
        r_2018 = rsi_from_2018.loc[ts] if ts in rsi_from_2018.index else np.nan
        r_2020 = rsi_from_2020.loc[ts] if ts in rsi_from_2020.index else np.nan
        r_short = rsi_short.loc[ts] if ts in rsi_short.index else np.nan
        diff = r_2018 - r_2020 if not (np.isnan(r_2018) or np.isnan(r_2020)) else np.nan

        print(f"{bar_str:<25} | {r_2018:>12.6f} | {r_2020:>12.6f} | {r_short:>12.6f} | {diff:>+12.6f}")

    # Also check: how many bars of BTC 30m data do we actually have?
    print("\nBTC 30m data available:")
    print(f"  From 2018: {len(btc_from_2018)} bars, {btc_from_2018.index[0]} to {btc_from_2018.index[-1]}")
    print(f"  From 2020: {len(btc_full)} bars, {btc_full.index[0]} to {btc_full.index[-1]}")
    print(f"  Short (500): {len(btc_short)} bars, {btc_short.index[0]} to {btc_short.index[-1]}")

    # The REAL question: how far back does TV's BTC data go?
    # Pine Script has access to all historical data for BTCUSDT on the exchange
    # Bybit launched in late 2018, but BTC/USDT perp has data from ~2019-10
    # So TV would have BTC data from ~2019 or 2020, similar to us

    # Check: convergence by Feb 2025 for 2018 vs 2020 start
    feb_check = pd.Timestamp("2025-02-01")
    r18 = rsi_from_2018.loc[feb_check] if feb_check in rsi_from_2018.index else np.nan
    r20 = rsi_from_2020.loc[feb_check] if feb_check in rsi_from_2020.index else np.nan
    print("\nConvergence check at 2025-02-01:")
    print(f"  RSI (from 2018): {r18:.10f}")
    print(f"  RSI (from 2020): {r20:.10f}")
    print(f"  Diff: {r18 - r20:.15f}")

    # Check the very first bar where data starts
    print(f"\nFirst available BTC 30m data point: {btc_full.index[0]}")
    print(f"  Close: {btc_full['close'].iloc[0]:.2f}")


asyncio.run(main())
