"""Debug: compare 30m vs 5m RSI values at the 2025-02-12 divergence point."""

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

import numpy as np
import pandas as pd

from backend.backtesting.service import BacktestService
from backend.core.indicators.momentum import calculate_rsi

START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
WARMUP_BARS = 500
btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)


async def main_30m_analyze() -> None:
    svc = BacktestService()
    btc_main = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=btc_start, end_date=END_DATE
    )
    btc_5m = await svc._fetch_historical_data(symbol="BTCUSDT", interval="5", start_date=btc_start, end_date=END_DATE)
    assert btc_main is not None and btc_5m is not None
    if btc_main.index.tz is None:
        btc_main.index = btc_main.index.tz_localize("UTC")
    if btc_5m.index.tz is None:
        btc_5m.index = btc_5m.index.tz_localize("UTC")

    print(f"BTC 30m: {len(btc_main)} bars, BTC 5m: {len(btc_5m)} bars")

    rsi_30m_arr = calculate_rsi(btc_main["close"].values, period=14)
    rsi_30m = pd.Series(rsi_30m_arr, index=btc_main.index)
    rsi_5m_arr = calculate_rsi(btc_5m["close"].values, period=14)
    rsi_5m = pd.Series(rsi_5m_arr, index=btc_5m.index)

    t1 = pd.Timestamp("2025-02-12 06:00", tz="UTC")
    t2 = pd.Timestamp("2025-02-12 11:00", tz="UTC")

    print()
    print("=== 30m RSI around 2025-02-12 ===")
    for ts in btc_main.index[(btc_main.index >= t1) & (btc_main.index <= t2)]:
        c = btc_main.at[ts, "close"]
        r = rsi_30m.at[ts]
        cross = " *** CROSS_SHORT" if rsi_30m.shift(1).at[ts] >= 52 and r < 52 else ""
        print(f"  {ts}  c={c:.2f}  R30={r:.4f}{cross}")

    print()
    print("=== 5m RSI (period=14) around 2025-02-12 ===")
    rsi_5m_prev = rsi_5m.shift(1)
    for ts in btc_5m.index[(btc_5m.index >= t1) & (btc_5m.index <= t2)]:
        c = btc_5m.at[ts, "close"]
        r = rsi_5m.at[ts]
        rp = rsi_5m_prev.at[ts]
        mark = ""
        if ts.minute in (0, 30):
            mark += " <30m>"
        if rp >= 52 and r < 52:
            mark += " *** CROSS_SHORT"
        print(f"  {ts}  c={c:.2f}  R5={r:.4f}  Rp={rp:.4f}{mark}")

    # --- Hypothetical RSI (30m state, single tick update from prev 30m close) ---
    print()
    print("=== Hypothetical RSI at each 5m tick in bar 09:30 ===")
    print("    (one-step: use 30m Wilder state at 09:00, apply tick vs prev 30m close)")
    bar_prev_ts = pd.Timestamp("2025-02-12 09:00", tz="UTC")
    bar_k_ts = pd.Timestamp("2025-02-12 09:30", tz="UTC")

    idx_prev = btc_main.index.get_loc(bar_prev_ts)
    close_prev = btc_main.iloc[idx_prev]["close"]
    closes_30m = btc_main["close"].values
    deltas = np.diff(closes_30m)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    period = 14
    ag = np.mean(gains[:period])
    al = np.mean(losses[:period])
    for i in range(period, idx_prev):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period

    rsi_prev_30m = 100.0 if al < 1e-10 else 100.0 - 100.0 / (1.0 + ag / al)
    print(f"  State at {bar_prev_ts}: close={close_prev:.3f}  RSI30={rsi_prev_30m:.4f}")

    # Two variants of hypothetical RSI:
    # Variant A: always compare tick vs prev_30m_close (one-step from fixed anchor)
    # Variant B: sequential (each tick vs previous tick)
    print()
    print("  ts                              close     hyp_A(vs30m_close)  hyp_B(sequential)")
    mask_bar = (btc_5m.index > bar_prev_ts) & (btc_5m.index <= bar_k_ts)
    prev_rsi_b = rsi_prev_30m
    prev_close_b = close_prev
    for ts in btc_5m.index[mask_bar]:
        tick = btc_5m.at[ts, "close"]
        # Variant A: one-step from 30m bar state
        delta_a = tick - close_prev
        g_a = delta_a if delta_a > 0 else 0.0
        lo_a = -delta_a if delta_a < 0 else 0.0
        ag_a = (ag * (period - 1) + g_a) / period
        al_a = (al * (period - 1) + lo_a) / period
        rsi_a = 100.0 if al_a < 1e-10 else 100.0 - 100.0 / (1.0 + ag_a / al_a)

        # Variant B: sequential tick-by-tick (wrong but shown for comparison)
        delta_b = tick - prev_close_b
        g_b = delta_b if delta_b > 0 else 0.0
        lo_b = -delta_b if delta_b < 0 else 0.0
        ag_b = (ag * (period - 1) + g_b) / period  # still from 30m state, wrong
        al_b = (al * (period - 1) + lo_b) / period
        rsi_b_cur = 100.0 if al_b < 1e-10 else 100.0 - 100.0 / (1.0 + ag_b / al_b)

        cross_a = " <A_CROSS>" if rsi_prev_30m >= 52 and rsi_a < 52 else ""
        cross_b = " <B_CROSS>" if prev_rsi_b >= 52 and rsi_b_cur < 52 else ""
        print(f"  {ts}  c={tick:.3f}  A={rsi_a:.4f}{cross_a}  B={rsi_b_cur:.4f}{cross_b}")
        prev_rsi_b = rsi_b_cur
        prev_close_b = tick


asyncio.run(main_30m_analyze())


async def main_5m_compare() -> None:
    svc = BacktestService()
    btc_main = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=btc_start, end_date=END_DATE
    )
    btc_5m = await svc._fetch_historical_data(symbol="BTCUSDT", interval="5", start_date=btc_start, end_date=END_DATE)
    assert btc_main is not None and btc_5m is not None
    print(f"BTC 30m: {len(btc_main)} bars, BTC 5m: {len(btc_5m)} bars")

    # Compute 30m RSI (period=14)
    rsi_30m_arr = calculate_rsi(btc_main["close"].values, period=14)
    rsi_30m = pd.Series(rsi_30m_arr, index=btc_main.index)

    # Compute 5m RSI (period=14)
    rsi_5m_arr = calculate_rsi(btc_5m["close"].values, period=14)
    rsi_5m = pd.Series(rsi_5m_arr, index=btc_5m.index)

    # Show around 2025-02-12 07:00-10:30 UTC
    t1 = pd.Timestamp("2025-02-12 06:00", tz="UTC")
    t2 = pd.Timestamp("2025-02-12 11:00", tz="UTC")

    print()
    print("=== 30m RSI around 2025-02-12 ===")
    mask30 = (btc_main.index >= t1) & (btc_main.index <= t2)
    for ts in btc_main.index[mask30]:
        c = btc_main.loc[ts, "close"]
        r = rsi_30m.loc[ts]
        print(f"  {ts}  close={c:.3f}  RSI30={r:.4f}")

    print()
    print("=== 5m RSI around 2025-02-12 ===")
    mask5 = (btc_5m.index >= t1) & (btc_5m.index <= t2)
    for ts in btc_5m.index[mask5]:
        c = btc_5m.loc[ts, "close"]
        r = rsi_5m.loc[ts]
        marker = " <-- 30m boundary" if ts.minute in (0, 30) else ""
        marker += " *** RSI crossed 52 below" if r < 52 else ""
        print(f"  {ts}  close={c:.3f}  RSI5={r:.4f}{marker}")

    # Also show "hypothetical 30m RSI" computed as: take the 30m Wilder state at bar k-1
    # and compute one-step RSI for tick price vs previous 30m close
    print()
    print("=== Hypothetical 30m RSI (tick price vs previous 30m close) ===")
    # Get state at bar ending 2025-02-12 09:00 UTC (the bar BEFORE 09:30)
    bar_prev = pd.Timestamp("2025-02-12 09:00", tz="UTC")
    bar_k = pd.Timestamp("2025-02-12 09:30", tz="UTC")

    # Find index of bar_prev in btc_main
    idx_prev = btc_main.index.get_loc(bar_prev)
    close_prev = btc_main.iloc[idx_prev]["close"]

    # Need Wilder state at idx_prev вЂ” recompute
    closes_30m = btc_main["close"].values
    deltas = np.diff(closes_30m)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    period = 14
    ag = np.mean(gains[:period])
    al = np.mean(losses[:period])
    for i in range(period, idx_prev):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period

    rsi_at_prev = 100.0 if al < 1e-10 else 100.0 - 100.0 / (1.0 + ag / al)
    print(f"State at {bar_prev}: close={close_prev:.3f}  RSI={rsi_at_prev:.4f}")
    print(f"  avg_gain={ag:.6f}  avg_loss={al:.6f}")

    print()
    print(f"Hypothetical RSI for each 5m tick in bar {bar_k}:")
    mask_bar = (btc_5m.index > bar_prev) & (btc_5m.index <= bar_k)
    prev_rsi = rsi_at_prev
    prev_close = close_prev
    for ts in btc_5m.index[mask_bar]:
        tick = btc_5m.loc[ts, "close"]
        delta = tick - prev_close
        g = delta if delta > 0 else 0.0
        lo = -delta if delta < 0 else 0.0
        ag_h = (ag * (period - 1) + g) / period
        al_h = (al * (period - 1) + lo) / period
        cur_rsi = 100.0 if al_h < 1e-10 else 100.0 - 100.0 / (1.0 + ag_h / al_h)
        cross = " <-- CROSS" if prev_rsi >= 52 and cur_rsi < 52 else ""
        print(f"  {ts}  close={tick:.3f}  RSI_hyp={cur_rsi:.4f}  prev={prev_rsi:.4f}{cross}")
        prev_rsi = cur_rsi
        prev_close = tick  # NOTE: using tick-to-tick or always vs bar_prev?


asyncio.run(main_30m_analyze())
