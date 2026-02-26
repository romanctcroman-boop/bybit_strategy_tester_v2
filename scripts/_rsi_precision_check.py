"""
Check exact RSI values with full precision at the 6 UNKNOWN first-SE bars.
Also try alternative RSI computations (SMA-seed vs EWM) to see if tiny
differences in RSI cause crossunder to fail.

Hypothesis: TV and our code compute RSI slightly differently at startup,
causing RSI at the 1st SE bar to be >= 52.000 (no crossunder) in TV
but < 52.000 (crossunder fires) in our code.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

import numpy as np
import pandas as pd


def compute_rsi_wilder_ewm(close: pd.Series, period: int = 14) -> pd.Series:
    """Our current method: pandas EWM with alpha=1/period"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_rsi_sma_seed(close: pd.Series, period: int = 14) -> pd.Series:
    """TV/Wilder method: first avg is SMA, then Wilder smoothing.
    Pine Script's ta.rsi uses ta.rma which is:
      rma = alpha * source + (1 - alpha) * rma[1]
      where alpha = 1/period
    The FIRST value is an SMA of the first `period` values.
    """
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    n = len(close)
    avg_gain = np.full(n, np.nan)
    avg_loss = np.full(n, np.nan)

    # First value: SMA of gains/losses over first `period` bars (indices 1..period)
    # delta[0] is NaN, so we start from index 1
    if n > period:
        avg_gain[period] = gain.iloc[1 : period + 1].mean()
        avg_loss[period] = loss.iloc[1 : period + 1].mean()

        alpha = 1.0 / period
        for i in range(period + 1, n):
            avg_gain[i] = alpha * gain.iloc[i] + (1 - alpha) * avg_gain[i - 1]
            avg_loss[i] = alpha * loss.iloc[i] + (1 - alpha) * avg_loss[i - 1]

    rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100)
    rsi = 100 - (100 / (1 + rs))
    return pd.Series(rsi, index=close.index)


async def main():
    from backend.backtesting.service import BacktestService

    svc = BacktestService()

    START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
    END_DATE = pd.Timestamp("2026-02-24T00:00:00", tz="UTC")

    # Load BTC data with warmup
    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), START_DATE)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    # Also load candles for timestamp alignment
    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)

    # Compute BTC RSI with both methods on BTC close
    btc_close = btc["close"]
    rsi_ewm = compute_rsi_wilder_ewm(btc_close, 14)
    rsi_sma = compute_rsi_sma_seed(btc_close, 14)

    # Align to ETH candles timeframe
    rsi_ewm_aligned = rsi_ewm.reindex(candles.index, method="ffill")
    rsi_sma_aligned = rsi_sma.reindex(candles.index, method="ffill")

    idx = candles.index

    # The 6 UNKNOWN cases with their 1st and 2nd SE bars
    # (label, 1st_SE_bar, 2nd_SE_bar)
    unknown_cases = [
        ("E#23", "2025-02-22 10:30", "2025-02-22 13:30"),
        ("E#57", "2025-05-09 15:00", "2025-05-09 19:00"),
        ("E#85", "2025-08-16 01:00", "2025-08-16 13:30"),
        ("E#89", "2025-08-27 02:30", "2025-08-27 12:00"),
        ("E#91", "2025-09-02 11:00", "2025-09-02 18:00"),
        ("E#120", "2025-11-25 00:00", "2025-11-25 05:00"),
    ]

    cross_level = 52.0

    print("=" * 140)
    print("RSI PRECISION CHECK FOR 6 UNKNOWN CASES")
    print(f"Cross short level: {cross_level}")
    print("Crossunder = rsi_prev >= 52.0 AND rsi < 52.0")
    print("=" * 140)

    for label, first_se_str, second_se_str in unknown_cases:
        first_se = pd.Timestamp(first_se_str)
        second_se = pd.Timestamp(second_se_str)

        # Get indices in the BTC timeseries (not ETH aligned)
        # We need to check the RSI at the ACTUAL BTC bar time
        # The aligned version uses ffill which could introduce errors

        print(f"\n{'=' * 100}")
        print(f"{label}")
        print(f"  1st SE bar: {first_se}")
        print(f"  2nd SE bar: {second_se}")

        for se_label, se_ts in [("1st SE", first_se), ("2nd SE", second_se)]:
            prev_ts = se_ts - pd.Timedelta(minutes=30)

            # Check aligned RSI values
            if se_ts in rsi_ewm_aligned.index:
                ewm_curr = rsi_ewm_aligned.loc[se_ts]
                ewm_prev = rsi_ewm_aligned.loc[prev_ts] if prev_ts in rsi_ewm_aligned.index else np.nan
            else:
                ewm_curr = np.nan
                ewm_prev = np.nan

            if se_ts in rsi_sma_aligned.index:
                sma_curr = rsi_sma_aligned.loc[se_ts]
                sma_prev = rsi_sma_aligned.loc[prev_ts] if prev_ts in rsi_sma_aligned.index else np.nan
            else:
                sma_curr = np.nan
                sma_prev = np.nan

            # Also check RAW BTC RSI at those timestamps
            if se_ts in rsi_ewm.index:
                ewm_raw_curr = rsi_ewm.loc[se_ts]
                ewm_raw_prev = rsi_ewm.loc[prev_ts] if prev_ts in rsi_ewm.index else np.nan
            else:
                ewm_raw_curr = np.nan
                ewm_raw_prev = np.nan

            if se_ts in rsi_sma.index:
                sma_raw_curr = rsi_sma.loc[se_ts]
                sma_raw_prev = rsi_sma.loc[prev_ts] if prev_ts in rsi_sma.index else np.nan
            else:
                sma_raw_curr = np.nan
                sma_raw_prev = np.nan

            # Cross check
            ewm_cross = ewm_prev >= cross_level and ewm_curr < cross_level
            sma_cross = sma_prev >= cross_level and sma_curr < cross_level
            ewm_raw_cross = ewm_raw_prev >= cross_level and ewm_raw_curr < cross_level
            sma_raw_cross = sma_raw_prev >= cross_level and sma_raw_curr < cross_level

            print(f"\n  {se_label} ({se_ts}):")
            print(f"    EWM aligned: RSI[T-1]={ewm_prev:.10f}  RSI[T]={ewm_curr:.10f}  cross={ewm_cross}")
            print(f"    SMA aligned: RSI[T-1]={sma_prev:.10f}  RSI[T]={sma_curr:.10f}  cross={sma_cross}")
            print(f"    EWM raw BTC: RSI[T-1]={ewm_raw_prev:.10f}  RSI[T]={ewm_raw_curr:.10f}  cross={ewm_raw_cross}")
            print(f"    SMA raw BTC: RSI[T-1]={sma_raw_prev:.10f}  RSI[T]={sma_raw_curr:.10f}  cross={sma_raw_cross}")

            # Distance from boundary
            print(f"    Distance from 52.0:")
            print(f"      EWM T-1: {ewm_prev - cross_level:+.10f}  T: {ewm_curr - cross_level:+.10f}")
            print(f"      SMA T-1: {sma_prev - cross_level:+.10f}  T: {sma_curr - cross_level:+.10f}")

            if ewm_cross != sma_cross:
                print(f"    *** METHODS DISAGREE! EWM={ewm_cross}, SMA={sma_cross} ***")

    # Summary: check how many bars have different cross results
    print("\n\n" + "=" * 100)
    print("GLOBAL COMPARISON: EWM vs SMA-seed RSI cross detection differences")
    rsi_ewm_prev = rsi_ewm_aligned.shift(1)
    rsi_sma_prev = rsi_sma_aligned.shift(1)
    ewm_cross_all = (rsi_ewm_prev >= cross_level) & (rsi_ewm_aligned < cross_level)
    sma_cross_all = (rsi_sma_prev >= cross_level) & (rsi_sma_aligned < cross_level)

    ewm_only = ewm_cross_all & ~sma_cross_all
    sma_only = sma_cross_all & ~ewm_cross_all
    print(f"  Total EWM crossunders: {ewm_cross_all.sum()}")
    print(f"  Total SMA crossunders: {sma_cross_all.sum()}")
    print(f"  EWM-only (fires in EWM but NOT SMA): {ewm_only.sum()}")
    print(f"  SMA-only (fires in SMA but NOT EWM): {sma_only.sum()}")

    if ewm_only.any():
        print(f"\n  EWM-only crossunder bars:")
        for ts in idx[ewm_only]:
            i = idx.get_loc(ts)
            prev_ts_local = ts - pd.Timedelta(minutes=30)
            e_prev = rsi_ewm_aligned.loc[prev_ts_local] if prev_ts_local in rsi_ewm_aligned.index else np.nan
            e_curr = rsi_ewm_aligned.loc[ts]
            s_prev = rsi_sma_aligned.loc[prev_ts_local] if prev_ts_local in rsi_sma_aligned.index else np.nan
            s_curr = rsi_sma_aligned.loc[ts]
            print(f"    {ts}: EWM {e_prev:.6f}->{e_curr:.6f}  SMA {s_prev:.6f}->{s_curr:.6f}")

    if sma_only.any():
        print(f"\n  SMA-only crossunder bars:")
        for ts in idx[sma_only]:
            prev_ts_local = ts - pd.Timedelta(minutes=30)
            e_prev = rsi_ewm_aligned.loc[prev_ts_local] if prev_ts_local in rsi_ewm_aligned.index else np.nan
            e_curr = rsi_ewm_aligned.loc[ts]
            s_prev = rsi_sma_aligned.loc[prev_ts_local] if prev_ts_local in rsi_sma_aligned.index else np.nan
            s_curr = rsi_sma_aligned.loc[ts]
            print(f"    {ts}: EWM {e_prev:.6f}->{e_curr:.6f}  SMA {s_prev:.6f}->{s_curr:.6f}")

    # KEY CHECK: For each 1st-SE bar, does the SMA method say NO cross?
    print("\n\n" + "=" * 100)
    print("KEY CHECK: Does SMA-seed method disagree on 1st SE bars?")
    for label, first_se_str, second_se_str in unknown_cases:
        first_se = pd.Timestamp(first_se_str)
        second_se = pd.Timestamp(second_se_str)
        prev_ts = first_se - pd.Timedelta(minutes=30)

        if first_se in rsi_sma_aligned.index and prev_ts in rsi_sma_aligned.index:
            s_prev = rsi_sma_aligned.loc[prev_ts]
            s_curr = rsi_sma_aligned.loc[first_se]
            s_cross = s_prev >= cross_level and s_curr < cross_level
            e_prev = rsi_ewm_aligned.loc[prev_ts]
            e_curr = rsi_ewm_aligned.loc[first_se]
            e_cross = e_prev >= cross_level and e_curr < cross_level
            match = "SAME" if s_cross == e_cross else "DIFFERENT !!!!"
            print(f"  {label} 1st SE ({first_se}): EWM_cross={e_cross}, SMA_cross={s_cross} -> {match}")


asyncio.run(main())
