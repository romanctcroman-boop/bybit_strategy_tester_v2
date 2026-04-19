"""
Diagnose WHY bars differ between our Bybit API data and TradingView BYBIT:BTCUSDT.P

Key question: are the differences from:
1. Timezone handling (UTC offset)
2. Bar open/close time convention (open vs close aligned)
3. API pagination artifacts (last bar of chunk)
4. Mark price vs Last price (TV may use mark price for risk data)
5. Different candle alignment (TV uses exchange server time)

We compare actual close prices around trade 9 divergence: 2025-01-28
TV trade 9: entry short at 2025-01-28 14:30 MSK = 11:30 UTC, price=3170.30
Engine:     entry short at 2025-01-28 18:00 UTC, price=3165.71
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
import requests

from backend.backtesting.service import BacktestService


async def main():
    svc = BacktestService()

    # ── Fetch BTC 30m from Bybit API (our engine source) ─────────────────────
    start = pd.Timestamp("2020-01-01", tz="UTC")
    end = pd.Timestamp("2026-02-24", tz="UTC")
    print("Fetching Bybit BTC 30m (2020 warmup)...")
    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", start, pd.Timestamp("2025-01-01", tz="UTC"))
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2025-01-01", tz="UTC"), end)
    bybit_btc = pd.concat([btc_warmup, btc_main]).sort_index()
    bybit_btc = bybit_btc[~bybit_btc.index.duplicated(keep="last")]
    print(f"Bybit BTC: {len(bybit_btc)} bars")

    # Make index tz-aware UTC
    if bybit_btc.index.tz is None:
        bybit_btc.index = bybit_btc.index.tz_localize("UTC")

    # ── Compute RSI on Bybit BTC ──────────────────────────────────────────────
    def rsi(series, period=14):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    bybit_btc["rsi"] = rsi(bybit_btc["close"])

    # ── Window: 2025-01-27 00:00 UTC to 2025-01-30 00:00 UTC ─────────────────
    # Trade 9 divergence: TV says 11:30 UTC, engine says 18:00 UTC (2025-01-28)
    w_start = pd.Timestamp("2025-01-27 00:00", tz="UTC")
    w_end = pd.Timestamp("2025-01-30 00:00", tz="UTC")
    window = bybit_btc.loc[w_start:w_end]

    print("\n=== Bybit BTC 30m RSI around trade 9 divergence (2025-01-28) ===")
    print(f"{'Time (UTC)':20s}  {'close':10s}  {'RSI':8s}  cross52?")
    prev_rsi = None
    for ts, row in window.iterrows():
        ts_str = str(ts)[:16]
        cross = ""
        if prev_rsi is not None and prev_rsi >= 52 and row["rsi"] < 52:
            cross = "  <<< crossunder(rsi, 52) SIGNAL"
        elif prev_rsi is not None and row["rsi"] > 52:
            cross = "  (above 52)"
        print(f"{ts_str:20s}  {row['close']:10.2f}  {row['rsi']:8.4f}{cross}")
        prev_rsi = row["rsi"]

    # ── Check duplicate/missing timestamps ───────────────────────────────────
    print("\n=== Checking timestamp continuity (2025-01-27 to 2025-01-30) ===")
    window_idx = window.index
    expected = pd.date_range(w_start, w_end, freq="30min", tz="UTC")
    missing = expected.difference(window_idx)
    extra = window_idx.difference(expected)
    print(f"Expected bars: {len(expected)},  Actual: {len(window_idx)}")
    if len(missing) > 0:
        print(f"MISSING bars: {list(missing[:10])}")
    if len(extra) > 0:
        print(f"EXTRA bars:   {list(extra[:10])}")
    else:
        print("No missing or extra bars in window.")

    # ── Compare with Bybit mark price kline (TV may use mark price) ──────────
    print("\n=== Fetching Bybit MARK PRICE kline for comparison ===")
    try:
        url = "https://api.bybit.com/v5/market/mark-price-kline"
        params = {
            "category": "linear",
            "symbol": "BTCUSDT",
            "interval": "30",
            "start": int(w_start.timestamp() * 1000),
            "end": int(w_end.timestamp() * 1000),
            "limit": 200,
        }
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json().get("result", {}).get("list", [])
        if data:
            mark_df = pd.DataFrame(data, columns=["open_time", "open", "high", "low", "close"])
            mark_df["ts"] = pd.to_datetime(mark_df["open_time"].astype(int), unit="ms", utc=True)
            mark_df = mark_df.set_index("ts").sort_index()
            mark_df["close"] = mark_df["close"].astype(float)

            print(f"{'Time (UTC)':20s}  {'last_close':10s}  {'mark_close':10s}  diff")
            for ts in window.index:
                if ts in mark_df.index:
                    lc = window.loc[ts, "close"]
                    mc = mark_df.loc[ts, "close"]
                    print(f"{str(ts)[:16]:20s}  {lc:10.2f}  {mc:10.2f}  {lc - mc:+.4f}")
        else:
            print("No mark price data returned")
    except Exception as e:
        print(f"Mark price fetch failed: {e}")

    # ── Check index timezone: are bars tz-naive from our fetch? ──────────────
    print("\n=== Timezone check ===")
    print(f"bybit_btc.index.tz = {bybit_btc.index.tz}")
    print(f"First 3 index values: {list(bybit_btc.index[:3])}")

    # ── Check pagination boundary (chunk seam) around 2025-01-01 ─────────────
    seam_start = pd.Timestamp("2024-12-31 22:00", tz="UTC")
    seam_end = pd.Timestamp("2025-01-01 02:00", tz="UTC")
    seam = bybit_btc.loc[seam_start:seam_end]
    print("\n=== Pagination seam (2025-01-01 boundary) ===")
    for ts, row in seam.iterrows():
        print(f"  {str(ts)[:16]}  close={row['close']:.2f}")

    # ── Summary: count all short crossunder(rsi,52) signals ──────────────────
    main_period = bybit_btc.loc[pd.Timestamp("2025-01-01", tz="UTC") : end]
    prev = main_period["rsi"].shift(1)
    cross_signals = (prev >= 52) & (main_period["rsi"] < 52)
    print(f"\n=== Total crossunder(rsi,52) signals in 2025-2026: {cross_signals.sum()} ===")
    # TV expects (from qq2): 121 short entries
    print(f"TV short entries: 121  |  Engine signals: {cross_signals.sum()}")


asyncio.run(main())
