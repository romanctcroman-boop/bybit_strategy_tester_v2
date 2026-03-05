"""
Diagnose specific RSI crossunder timing differences between engine and TV.
Focus on Feb 12 2025 divergence: engine fires at 07:30, TV fires at 10:00.
"""

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import pandas as pd
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.service import BacktestService
from backend.core.indicators import calculate_rsi

START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
WARMUP_BARS = 500


async def main():
    svc = BacktestService()

    # Fetch BTC with warmup
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    warmup_ts_start = int(btc_start.timestamp() * 1000)
    warmup_ts_end = int(START_DATE.timestamp() * 1000)
    raw_warmup = await svc.adapter.get_historical_klines(
        "BTCUSDT", "30", warmup_ts_start, warmup_ts_end, market_type="linear"
    )
    if raw_warmup:
        df_w = pd.DataFrame(raw_warmup)
        for old, new in {
            "startTime": "timestamp",
            "open_time": "timestamp",
            "openPrice": "open",
            "highPrice": "high",
            "lowPrice": "low",
            "closePrice": "close",
        }.items():
            if old in df_w.columns and new not in df_w.columns:
                df_w = df_w.rename(columns={old: new})
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df_w.columns:
                df_w[col] = pd.to_numeric(df_w[col], errors="coerce")
        if df_w["timestamp"].dtype in ["int64", "float64"]:
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms")
        df_w = df_w.set_index("timestamp").sort_index()
        if btc_main.index.tz is None and df_w.index.tz is not None:
            df_w.index = df_w.index.tz_localize(None)
        btc = pd.concat([df_w, btc_main]).sort_index()
        btc = btc[~btc.index.duplicated(keep="last")]
    else:
        btc = btc_main

    print(f"Total BTC bars: {len(btc)}, first={btc.index[0]}, last={btc.index[-1]}")

    # Compute RSI on full BTC series
    rsi_full = calculate_rsi(btc["close"].values, period=14)
    btc["rsi"] = rsi_full

    # Focus on Feb 11-13 window
    window_start = pd.Timestamp("2025-02-11 00:00")
    window_end = pd.Timestamp("2025-02-12 14:00")
    btc_window = btc.loc[window_start:window_end]

    print("\n=== BTC RSI around Feb 12 (engine fires short at 07:30) ===")
    print(f"{'Timestamp':<22} {'BTC Close':>12} {'RSI':>10} {'Cross<52?':>10}")
    for i, (ts, row) in enumerate(btc_window.iterrows()):
        rsi_val = row["rsi"]
        # Check crossunder from previous bar
        cross = ""
        if i > 0:
            prev_rsi = list(btc_window["rsi"])[i - 1]
            if prev_rsi >= 52 and rsi_val < 52:
                cross = " <<< CROSSUNDER"
            elif prev_rsi < 52 and rsi_val >= 52:
                cross = " >>> CROSS ABOVE"
        print(f"  {ts!s:<20} {row['close']:>12.2f} {rsi_val:>10.4f}{cross}")

    # Now look at multiple extra trades to find pattern
    # Extra trades in engine but not TV (from _find_extra5.py output):
    extra_times = [
        ("2025-02-12 07:30", "TV ep=2628.13 at 10:00"),
        ("2025-02-15 00:00", "TV ep=2724.45 at 14:30"),
        ("2025-02-17 13:00", "TV ep=2695.20 at 16:30"),
        ("2025-02-18 04:30", "TV ep=2695.69 at 16:00"),
        ("2025-02-19 18:00", "TV ep=2617.00 at somewhere"),
    ]

    print("\n=== All crossunders below 52 in our engine (Feb 1 - Mar 1) ===")
    feb_start = pd.Timestamp("2025-02-01 00:00")
    feb_end = pd.Timestamp("2025-03-01 00:00")
    btc_feb = btc.loc[feb_start:feb_end]

    rsi_arr = btc_feb["rsi"].values
    for i in range(1, len(rsi_arr)):
        if rsi_arr[i - 1] >= 52 and rsi_arr[i] < 52:
            ts = btc_feb.index[i]
            print(
                f"  crossunder at {str(ts)[:16]}  close={btc_feb['close'].iloc[i]:.2f}  RSI: {rsi_arr[i - 1]:.4f} -> {rsi_arr[i]:.4f}"
            )


asyncio.run(main())
