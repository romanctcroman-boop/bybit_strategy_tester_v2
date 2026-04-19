"""Trace intra-bar RSI at specific 30m bars to diagnose false IB signals.

Goal: understand why the IB detection fires at bar 2025-01-01 13:00 (false)
but should only fire at 13:30 (where TV fires trade #1).

Also look at bar 2025-01-01 13:30 to see if IB fires there too.
"""

import asyncio
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, timezone

from backend.backtesting.service import BacktestService


async def main():
    svc = BacktestService()

    START = datetime(2025, 1, 1, tzinfo=timezone.utc)
    END = datetime(2025, 1, 2, tzinfo=timezone.utc)  # Just 1 day for tracing

    # We need BTC 30m with warmup for RSI
    btc_start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", btc_start, START)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START, END)
    btc_30m = pd.concat([btc_warmup, btc_main]).sort_index()
    btc_30m = btc_30m[~btc_30m.index.duplicated(keep="last")]

    # BTC 1m for the target day
    btc_1m = await svc._fetch_historical_data("BTCUSDT", "1", START, END)

    print(f"BTC 30m: {len(btc_30m)} bars")
    print(f"BTC 1m:  {len(btc_1m)} bars")

    # Compute RSI on BTC 30m
    period = 14
    closes = btc_30m["close"].values
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    ag = np.mean(gains[:period])
    al = np.mean(losses[:period])
    rsi_arr = np.full(len(closes), np.nan)
    avg_gain_arr = np.zeros(len(closes))
    avg_loss_arr = np.zeros(len(closes))
    avg_gain_arr[period] = ag
    avg_loss_arr[period] = al
    if al < 1e-10:
        rsi_arr[period] = 100.0
    else:
        rsi_arr[period] = 100.0 - 100.0 / (1.0 + ag / al)

    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
        avg_gain_arr[i + 1] = ag
        avg_loss_arr[i + 1] = al
        if al < 1e-10:
            rsi_arr[i + 1] = 100.0
        else:
            rsi_arr[i + 1] = 100.0 - 100.0 / (1.0 + ag / al)

    rsi_series = pd.Series(rsi_arr, index=btc_30m.index)

    # Target bars to trace (UTC times)
    target_bars = [
        pd.Timestamp("2025-01-01 12:30:00"),
        pd.Timestamp("2025-01-01 13:00:00"),
        pd.Timestamp("2025-01-01 13:30:00"),
        pd.Timestamp("2025-01-01 14:00:00"),
    ]

    cross_short_level = 52.0
    cross_long_level = 24.0

    print(f"\n{'=' * 100}")
    print(f"INTRA-BAR RSI TRACE (cross_short_level={cross_short_level})")
    print(f"{'=' * 100}")

    # Show bar-close RSI for context
    print(f"\n--- Bar-close RSI around target bars ---")
    mask = (btc_30m.index >= pd.Timestamp("2025-01-01 10:00:00")) & (
        btc_30m.index <= pd.Timestamp("2025-01-01 16:00:00")
    )
    for ts in btc_30m.index[mask]:
        idx = btc_30m.index.get_loc(ts)
        rsi_val = rsi_arr[idx] if idx < len(rsi_arr) else np.nan
        close_val = closes[idx]
        marker = " <-- TARGET" if ts in target_bars else ""
        cross = ""
        if idx > 0 and not np.isnan(rsi_arr[idx]) and not np.isnan(rsi_arr[idx - 1]):
            if rsi_arr[idx - 1] >= cross_short_level and rsi_arr[idx] < cross_short_level:
                cross = "  ** CROSSUNDER 52 (bar-close) **"
        print(f"  {ts}  close={close_val:10.2f}  RSI={rsi_val:8.4f}{marker}{cross}")

    print(f"\n{'=' * 100}")

    btc_30m_index = btc_30m.index
    btc_1m_close = btc_1m["close"]

    for bar_ts in target_bars:
        bar_loc = btc_30m_index.get_loc(bar_ts) if bar_ts in btc_30m_index else None
        if bar_loc is None:
            print(f"\n--- Bar {bar_ts} not found in 30m index ---")
            continue

        # Bar k: ticks from bar_ts to next bar
        next_bar_loc = bar_loc + 1
        if next_bar_loc >= len(btc_30m_index):
            continue
        next_bar_ts = btc_30m_index[next_bar_loc]

        # Get Wilder state at bar k-1
        prev_bar_loc = bar_loc - 1
        if prev_bar_loc < 0:
            continue
        prev_bar_ts = btc_30m_index[prev_bar_loc]
        ag_prev = avg_gain_arr[prev_bar_loc]
        al_prev = avg_loss_arr[prev_bar_loc]
        close_prev_30m = closes[prev_bar_loc]
        rsi_prev_30m = rsi_arr[prev_bar_loc]

        print(f"\n--- Bar k = {bar_ts} ---")
        print(f"    Bar k-1 = {prev_bar_ts}")
        print(f"    close_{'{k-1}'} = {close_prev_30m:.2f}")
        print(f"    RSI_{'{k-1}'}   = {rsi_prev_30m:.6f}")
        print(f"    ag_prev  = {ag_prev:.10f}")
        print(f"    al_prev  = {al_prev:.10f}")
        print(f"    Bar k close RSI = {rsi_arr[bar_loc]:.6f}")

        # Get 1m ticks within this bar
        mask_1m = (btc_1m_close.index >= bar_ts) & (btc_1m_close.index < next_bar_ts)
        ticks = btc_1m_close[mask_1m]

        if len(ticks) == 0:
            print(f"    No 1m ticks found")
            continue

        print(f"    1m ticks: {len(ticks)} (from {ticks.index[0]} to {ticks.index[-1]})")
        print(
            f"    {'tick_ts':>23s}  {'price':>10s}  {'delta':>10s}  {'rsi_hyp':>10s}  {'prev_rsi':>10s}  {'cross':>10s}"
        )

        prev_rsi_hyp_tick = rsi_prev_30m  # seed with bar k-1 close RSI
        fired_short = False

        for tick_ts, tick_price in ticks.items():
            delta = tick_price - close_prev_30m
            g = max(delta, 0.0)
            lo = max(-delta, 0.0)
            ag_h = (ag_prev * (period - 1) + g) / period
            al_h = (al_prev * (period - 1) + lo) / period
            cur_rsi_hyp = 100.0 if al_h < 1e-10 else 100.0 - 100.0 / (1.0 + ag_h / al_h)

            cross_marker = ""
            if prev_rsi_hyp_tick >= cross_short_level and cur_rsi_hyp < cross_short_level:
                cross_marker = " << CROSS↓52"
                fired_short = True

            print(
                f"    {str(tick_ts):>23s}  {tick_price:10.2f}  {delta:+10.2f}  "
                f"{cur_rsi_hyp:10.6f}  {prev_rsi_hyp_tick:10.6f}  {cross_marker}"
            )
            prev_rsi_hyp_tick = cur_rsi_hyp

        print(f"    => IB fired_short = {fired_short}")

    print(f"\nDone.")


asyncio.run(main())
