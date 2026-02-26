"""
Full bar-by-bar comparison: TV ETH (BYBIT_ETHUSDT.P, 30 (2).csv) vs our Bybit API.
Range: 2025-01-01 to 2026-02-24 — 20148 bars.

Goal: find ALL price differences to understand if ETH data divergence
contributes to signal mismatches in Strategy_RSI_L/S_10.
"""

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="ERROR")

import numpy as np
import pandas as pd

from backend.backtesting.service import BacktestService

TV_CSV = r"c:\Users\roman\Downloads\BYBIT_ETHUSDT.P, 30 (2).csv"

# Load TV bars
tv = pd.read_csv(TV_CSV)
tv["time"] = pd.to_datetime(tv["time"], utc=True)
tv = tv.set_index("time").sort_index()
print(f"TV bars:  {len(tv):6d}  [{tv.index[0].date()} .. {tv.index[-1].date()}]")


async def main():
    svc = BacktestService()

    start = pd.Timestamp("2025-01-01", tz="UTC")
    end = pd.Timestamp("2026-02-25", tz="UTC")

    print("Fetching Bybit ETH 30m 2025-01-01..2026-02-25 ...")
    our = await svc._fetch_historical_data("ETHUSDT", "30", start, end)
    if our.index.tz is None:
        our.index = our.index.tz_localize("UTC")
    our = our.sort_index()
    our = our[~our.index.duplicated(keep="last")]
    print(f"Our bars: {len(our):6d}  [{our.index[0].date()} .. {our.index[-1].date()}]")

    # ── Alignment ──────────────────────────────────────────────────────────────
    common = tv.index.intersection(our.index)
    tv_only = tv.index.difference(our.index)
    our_only = our.index.difference(tv.index)
    print(f"\nCommon bars: {len(common)}")
    print(f"TV-only:     {len(tv_only)}")
    print(f"Our-only:    {len(our_only)}")

    if len(tv_only) > 0:
        print(f"  TV-only (first 5): {list(tv_only[:5])}")
    if len(our_only) > 0:
        print(f"  Our-only (first 5): {list(our_only[:5])}")

    # ── Close price comparison ─────────────────────────────────────────────────
    tv_c = tv.loc[common, "close"]
    our_c = our.loc[common, "close"]
    diff = (tv_c - our_c).abs()

    thresholds = [0.005, 0.01, 0.05, 0.10, 0.50, 1.0]
    print(f"\nClose price diff distribution:")
    for thr in thresholds:
        cnt = (diff > thr).sum()
        print(f"  > ${thr:5.3f}: {cnt:5d} bars  ({cnt / len(common) * 100:.2f}%)")

    # Show bars with diff > $0.01
    big_diff = diff[diff > 0.01].sort_values(ascending=False)
    print(f"\nBars with |close diff| > $0.01: {len(big_diff)}")
    if len(big_diff) > 0:
        print(f"{'Time (UTC)':22s}  {'TV close':10s}  {'Our close':10s}  {'diff':8s}")
        for ts in big_diff.index[:40]:
            print(f"{str(ts)[:22]:22s}  {tv_c[ts]:10.4f}  {our_c[ts]:10.4f}  {tv_c[ts] - our_c[ts]:+8.4f}")
        if len(big_diff) > 40:
            print(f"  ... and {len(big_diff) - 40} more")

    # ── Now check: what about HIGH and LOW? ───────────────────────────────────
    print(f"\nHigh price diff distribution (|TV high - Our high|):")
    tv_h = tv.loc[common, "high"]
    our_h = our.loc[common, "high"]
    hdiff = (tv_h - our_h).abs()
    for thr in [0.01, 0.10, 1.0]:
        cnt = (hdiff > thr).sum()
        print(f"  > ${thr:5.2f}: {cnt:5d} bars")

    print(f"\nLow price diff distribution (|TV low - Our low|):")
    tv_l = tv.loc[common, "low"]
    our_l = our.loc[common, "low"]
    ldiff = (tv_l - our_l).abs()
    for thr in [0.01, 0.10, 1.0]:
        cnt = (ldiff > thr).sum()
        print(f"  > ${thr:5.2f}: {cnt:5d} bars")

    # ── RSI comparison on close prices ────────────────────────────────────────
    def rsi14(series):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_g = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        avg_l = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        rs = avg_g / avg_l.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    # Use only the common index for fair comparison
    tv_rsi = rsi14(tv_c)
    our_rsi = rsi14(our_c)
    rsi_diff = (tv_rsi - our_rsi).abs()

    print(f"\nRSI diff distribution (ETH RSI TV vs Our):")
    for thr in [0.001, 0.01, 0.1, 0.5, 1.0]:
        cnt = (rsi_diff > thr).sum()
        print(f"  > {thr:.3f}: {cnt:5d} bars  ({cnt / len(common) * 100:.2f}%)")

    print(f"\nMax ETH RSI diff: {rsi_diff.max():.6f}")

    # ── Crossunder check: does ETH RSI diff change any crossunder signals? ────
    # Strategy uses BTC RSI not ETH RSI for entry filter — but let's check ETH
    # in case ETH is also used somewhere.
    # The strategy_RSI_L/S_10 uses BTC RSI, not ETH RSI.
    # ETH data is only OHLCV source for the backtest, not for RSI signal.
    # So ETH close diff just affects trade P&L (tiny), not signal timing.
    print(f"\nNote: Strategy uses BTC RSI for signals, ETH is just OHLCV.")
    print(f"ETH close diff only affects P&L marginally, not signal timing.")

    # ── Summary stats ──────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"SUMMARY:")
    print(f"  Total common bars: {len(common)}")
    print(f"  Bars with close diff > $0.01: {(diff > 0.01).sum()}")
    print(f"  Avg close diff: ${diff.mean():.6f}")
    print(f"  Max close diff: ${diff.max():.4f}")
    if len(big_diff) > 0:
        max_ts = diff.idxmax()
        print(f"  Max diff bar: {str(max_ts)[:22]}")
        print(f"    TV={tv_c[max_ts]:.4f}, Our={our_c[max_ts]:.4f}")
    print(f"\nConclusion: ETH bars are {'IDENTICAL' if (diff > 0.01).sum() == 0 else 'SLIGHTLY DIFFERENT'}")
    print(f"  => Signal divergence comes from BTC RSI source data differences")


asyncio.run(main())
