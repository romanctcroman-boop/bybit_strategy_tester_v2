"""
Analyze whether RSI[T-1] distance from 52 (i.e., how far above 52 was previous RSI)
explains the TV-skip pattern.

Also test: "use_cross_memory" behavior - if RSI crossed under 52 in recent N bars, skip.
"""

import asyncio
import json
import sqlite3
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import numpy as np
import pandas as pd
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.service import BacktestService
from backend.core.indicators import calculate_rsi

START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")

EXTRA_ENTRIES = [
    "2025-02-12 07:30",
    "2025-02-15 00:00",
    "2025-02-17 13:00",
    "2025-02-18 04:30",
    "2025-02-19 18:00",
    "2025-03-30 05:30",
    "2025-03-31 12:00",
    "2025-04-20 02:00",
    "2025-05-11 20:30",
    "2025-05-13 07:30",
    "2025-05-19 01:30",
    "2025-06-22 07:00",
    "2025-06-24 19:00",
    "2025-07-03 04:30",
    "2025-07-04 23:00",
    "2025-07-11 18:00",
    "2025-07-13 09:30",
    "2025-07-24 09:30",
    "2025-08-16 01:00",
    "2025-08-27 02:30",
    "2025-09-02 11:00",
    "2025-11-25 00:00",
]

# TV replacements (for extras that have one)
TV_REPLACEMENTS = {
    "2025-02-12 07:30": "2025-02-12 10:00",
    "2025-02-15 00:00": "2025-02-15 16:30",
    "2025-02-18 04:30": "2025-02-19 16:00",
    "2025-03-31 12:00": "2025-04-02 02:30",
    "2025-06-22 07:00": "2025-06-22 12:30",
    "2025-06-24 19:00": "2025-06-25 22:30",
    "2025-07-24 09:30": "2025-07-25 12:00",
    "2025-08-16 01:00": "2025-08-16 14:00",
    "2025-08-27 02:30": "2025-08-27 12:30",
    "2025-11-25 00:00": "2025-11-25 05:30",
}


async def main():
    svc = BacktestService()

    candles_eth = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    eth_idx = candles_eth.index

    WARMUP = 500
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc_warmup = None
    try:
        raw = await svc.adapter.get_historical_klines(
            symbol="BTCUSDT",
            interval="30",
            start_time=int(btc_start.timestamp() * 1000),
            end_time=int(START_DATE.timestamp() * 1000),
            market_type="linear",
        )
        if raw:
            dfw = pd.DataFrame(raw)
            col_map = {
                "startTime": "timestamp",
                "open_time": "timestamp",
                "openPrice": "open",
                "highPrice": "high",
                "lowPrice": "low",
                "closePrice": "close",
            }
            for old, new in col_map.items():
                if old in dfw.columns and new not in dfw.columns:
                    dfw = dfw.rename(columns={old: new})
            for col in ["open", "high", "low", "close", "volume"]:
                if col in dfw.columns:
                    dfw[col] = pd.to_numeric(dfw[col], errors="coerce")
            if "timestamp" in dfw.columns:
                dfw["timestamp"] = (
                    pd.to_datetime(dfw["timestamp"], unit="ms", utc=True)
                    if dfw["timestamp"].dtype in ["int64", "float64"]
                    else pd.to_datetime(dfw["timestamp"], utc=True)
                )
                dfw = dfw.set_index("timestamp").sort_index()
            btc_warmup = dfw
    except Exception as e:
        print(f"Warmup failed: {e}")

    if btc_warmup is not None and len(btc_warmup) > 0:
        if btc_main.index.tz is None:
            btc_main.index = btc_main.index.tz_localize("UTC")
        if btc_warmup.index.tz is None:
            btc_warmup.index = btc_warmup.index.tz_localize("UTC")
        btc_full = pd.concat([btc_warmup, btc_main]).sort_index()
        btc_full = btc_full[~btc_full.index.duplicated(keep="last")]
    else:
        btc_full = btc_main

    RSI_PERIOD = 14
    CROSS_LEVEL = 52.0
    rsi_vals = calculate_rsi(btc_full["close"].values.astype(float), RSI_PERIOD)
    btc_full["rsi"] = rsi_vals

    # Align to ETH index
    if eth_idx.tz is None and btc_full.index.tz is not None:
        align_idx = eth_idx.tz_localize("UTC")
    else:
        align_idx = eth_idx
    rsi_a = btc_full["rsi"].reindex(align_idx)

    def get_rsi_at(ts_str):
        ts = pd.Timestamp(ts_str)
        if ts not in eth_idx:
            ts = pd.Timestamp(ts_str, tz="UTC")
        if ts not in eth_idx:
            return None
        pos = eth_idx.get_loc(ts)
        return pos, rsi_a.iloc[pos]

    # ── Analysis 1: RSI[T-1] distance from 52 ────────────────────────────────
    print("RSI[T-1] ANALYSIS for extra engine entries vs TV replacements:")
    print(f"{'#':>3}  {'Type':8}  {'Entry':16}  {'RSI[T-1]':>9}  {'Distance':>9}  {'RSI[T]':>7}  Drop")
    print("-" * 75)

    extra_distances = []
    for i, eng_ts_str in enumerate(EXTRA_ENTRIES, 1):
        r = get_rsi_at(eng_ts_str)
        if r is None:
            continue
        pos, rsi_t = r
        rsi_tm1 = rsi_a.iloc[pos - 1] if pos >= 1 else np.nan
        dist = rsi_tm1 - CROSS_LEVEL  # how far above 52 was T-1
        drop = rsi_tm1 - rsi_t  # how much RSI dropped in one bar
        extra_distances.append(dist)
        tv_ts = TV_REPLACEMENTS.get(eng_ts_str, "")
        mark = "*" if tv_ts else " "
        print(
            f"{i:>3}{mark} {'EXTRA':8}  {eng_ts_str[:13]:16}  {rsi_tm1:>9.3f}  {dist:>+9.3f}  {rsi_t:>7.3f}  {drop:>5.2f}"
        )

        # Also show TV replacement
        if tv_ts:
            r2 = get_rsi_at(tv_ts)
            if r2:
                pos2, rsi_t2 = r2
                rsi_tm1_2 = rsi_a.iloc[pos2 - 1] if pos2 >= 1 else np.nan
                dist2 = rsi_tm1_2 - CROSS_LEVEL
                drop2 = rsi_tm1_2 - rsi_t2
                print(
                    f"   {'  TV_REPL':8}  {tv_ts[:13]:16}  {rsi_tm1_2:>9.3f}  {dist2:>+9.3f}  {rsi_t2:>7.3f}  {drop2:>5.2f}"
                )

    print()
    print(f"Avg RSI[T-1] distance for 22 extras: {np.nanmean(extra_distances):+.3f}")

    # ── Analysis 2: Test "distance > threshold" filter ───────────────────────
    # Hypothesis: TV skips when RSI[T-1] is too far above cross_level
    # (suggesting the crossunder was from a high RSI value - "too sharp" drop)
    print()
    print("THRESHOLD FILTER TEST:")
    print("If RSI[T-1] > (cross_level + threshold): skip signal")
    print()
    rsi_prev = rsi_a.shift(1)
    short_cross = (rsi_prev >= CROSS_LEVEL) & (rsi_a < CROSS_LEVEL)

    total_crosses = short_cross.sum()
    print(f"Total crossunders: {total_crosses}")

    for threshold in [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 15]:
        # Keep signal only if RSI[T-1] was within (cross_level + threshold)
        # i.e., RSI[T-1] <= cross_level + threshold
        if threshold == 0:
            filtered = short_cross.copy()  # no filter
        else:
            filtered = short_cross & (rsi_prev <= CROSS_LEVEL + threshold)
        print(
            f"  threshold={threshold:>3}: {filtered.sum():>4} signals retained "
            f"(removed {total_crosses - filtered.sum():>4})"
        )

    # ── Analysis 3: Look at "bars since RSI was last below 52" (no recent cross) ─
    print()
    print("BARS SINCE LAST CROSS-UNDER (cross memory) ANALYSIS:")
    print("For each extra entry, how many bars ago was the previous crossunder?")
    cross_times = eth_idx[short_cross.values]

    for eng_ts_str in EXTRA_ENTRIES[:6]:
        r = get_rsi_at(eng_ts_str)
        if r is None:
            continue
        pos, _ = r
        ts = eth_idx[pos]
        # Find previous crossunder
        cross_before_pos = [i for i, ct in enumerate(cross_times) if ct < ts]
        if cross_before_pos:
            prev_cross_t = cross_times[cross_before_pos[-1]]
            bars_since = (ts - prev_cross_t).total_seconds() / 1800
            print(f"  {eng_ts_str[:13]}: prev crossunder at {str(prev_cross_t)[:16]} ({bars_since:.0f} bars ago)")
        else:
            print(f"  {eng_ts_str[:13]}: no previous crossunder")

    # ── Analysis 4: RSI[T-1] > 52 by more than X OR RSI dropped > Y ─────────
    print()
    print("COMBINED FILTER: RSI[T-1] > 52+X (too sharp entry from high RSI)")
    print("For extra signals that have TV replacements: what's TV replacement RSI[T-1]?")
    print()
    for eng_ts_str, tv_ts_str in TV_REPLACEMENTS.items():
        r_e = get_rsi_at(eng_ts_str)
        r_t = get_rsi_at(tv_ts_str)
        if r_e and r_t:
            p_e, rsi_e_t = r_e
            p_t, rsi_t_t = r_t
            d_e = rsi_a.iloc[p_e - 1] - CROSS_LEVEL if p_e >= 1 else np.nan
            d_t = rsi_a.iloc[p_t - 1] - CROSS_LEVEL if p_t >= 1 else np.nan
            # Are ALL TV replacements also distant?
            print(
                f"  E: {eng_ts_str[:13]}  RSI[T-1] dist={d_e:+.2f}  →  TV: {tv_ts_str[:13]}  RSI[T-1] dist={d_t:+.2f}"
            )


asyncio.run(main())
