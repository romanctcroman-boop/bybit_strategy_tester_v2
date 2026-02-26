"""
Fetch BTCUSDT 30m from Bybit API starting 2023-01-01 (paginated),
compute Wilder RSI-14, compare with our 500-bar warmup version at key
crossunder points to see if the RSI values converge to TV's values.
"""

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
from backend.core.indicators import calculate_rsi

# Key crossunder bars where engine fires but TV doesn't (from _find_extra5.py / _breakeven_rsi.py)
# These are bars where engine RSI crosses below 52 but TV RSI stays >= 52
CHECK_BARS = [
    pd.Timestamp("2025-02-12 07:30"),
    pd.Timestamp("2025-02-15 00:00"),
    pd.Timestamp("2025-02-17 13:00"),
    pd.Timestamp("2025-02-18 04:30"),
    pd.Timestamp("2025-02-19 18:00"),
    pd.Timestamp("2025-03-30 05:30"),
]

START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
HISTORY_START = pd.Timestamp("2023-01-01", tz="UTC")  # 2 years of warmup


async def fetch_full_btc():
    """Fetch BTCUSDT 30m paginated from 2023-01-01."""
    svc = BacktestService()

    print("Fetching BTC main data (2025-01-01 to 2026-02-24)...")
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    print(f"  Main: {len(btc_main)} bars  [{btc_main.index[0]} — {btc_main.index[-1]}]")

    # Paginated fetch for warmup: 2023-01-01 to 2025-01-01
    # Bybit API returns max 1000 bars per call → need ~35,040 bars / 1000 = ~35 pages
    print("Fetching BTC warmup data (2023-01-01 to 2025-01-01) via paginated API...")
    all_warmup = []
    page_start = HISTORY_START
    page_end = START_DATE

    while page_start < page_end:
        # Calculate next chunk end (1000 bars × 30min = 500 hours)
        chunk_end = min(page_start + pd.Timedelta(hours=500), page_end)

        ts_start = int(page_start.timestamp() * 1000)
        ts_end = int(chunk_end.timestamp() * 1000)

        raw = await svc.adapter.get_historical_klines("BTCUSDT", "30", ts_start, ts_end, market_type="linear")
        if not raw:
            break

        df_chunk = pd.DataFrame(raw)
        # Normalize column names
        col_map = {
            "startTime": "timestamp",
            "open_time": "timestamp",
            "openPrice": "open",
            "highPrice": "high",
            "lowPrice": "low",
            "closePrice": "close",
        }
        df_chunk = df_chunk.rename(columns={k: v for k, v in col_map.items() if k in df_chunk.columns})
        if "timestamp" not in df_chunk.columns:
            df_chunk = df_chunk.rename(columns={df_chunk.columns[0]: "timestamp"})
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df_chunk.columns:
                df_chunk[col] = pd.to_numeric(df_chunk[col], errors="coerce")
        if df_chunk["timestamp"].dtype in ["int64", "float64"]:
            df_chunk["timestamp"] = pd.to_datetime(df_chunk["timestamp"], unit="ms")
        df_chunk = df_chunk.set_index("timestamp").sort_index()

        # Strip tz to match btc_main (tz-naive)
        if btc_main.index.tz is None and df_chunk.index.tz is not None:
            df_chunk.index = df_chunk.index.tz_localize(None)

        all_warmup.append(df_chunk)
        page_start = chunk_end

        # Progress
        pct = (chunk_end - HISTORY_START) / (START_DATE - HISTORY_START) * 100
        print(f"  Fetched up to {chunk_end.date()} ({pct:.0f}%)", end="\r")

    print()

    if not all_warmup:
        print("ERROR: Could not fetch warmup data!")
        return None, btc_main

    warmup_df = pd.concat(all_warmup).sort_index()
    warmup_df = warmup_df[~warmup_df.index.duplicated(keep="last")]
    print(f"  Warmup: {len(warmup_df)} bars  [{warmup_df.index[0]} — {warmup_df.index[-1]}]")

    # Combine
    if btc_main.index.tz is None:
        btc_main_stripped = btc_main
    else:
        btc_main_stripped = btc_main.copy()
        btc_main_stripped.index = btc_main_stripped.index.tz_localize(None)

    full_btc = pd.concat([warmup_df, btc_main_stripped]).sort_index()
    full_btc = full_btc[~full_btc.index.duplicated(keep="last")]
    print(f"  Full BTC: {len(full_btc)} bars  [{full_btc.index[0]} — {full_btc.index[-1]}]")

    return full_btc, btc_main


async def main():
    full_btc, btc_main = await fetch_full_btc()
    if full_btc is None:
        return

    # Compute RSI on full history (2023-01-01 → 2026-02-24)
    print("\nComputing Wilder RSI-14 on full 2-year BTC history...")
    rsi_full_arr = calculate_rsi(full_btc["close"].values, period=14)
    rsi_full = pd.Series(rsi_full_arr, index=full_btc.index)

    # Compute RSI on 500-bar warmup (our current approach)
    print("Computing Wilder RSI-14 on 500-bar warmup...")
    btc_500_start = START_DATE - pd.Timedelta(minutes=500 * 30)
    btc_main_naive = btc_main.copy()
    if btc_main_naive.index.tz is not None:
        btc_main_naive.index = btc_main_naive.index.tz_localize(None)

    # Simulate the 500-bar warmup by slicing full_btc
    warmup_500 = full_btc[full_btc.index < btc_500_start.replace(tzinfo=None)]
    warmup_500 = warmup_500.iloc[-500:]  # last 500 bars before strategy start
    btc_500 = pd.concat([warmup_500, btc_main_naive]).sort_index()
    btc_500 = btc_500[~btc_500.index.duplicated(keep="last")]

    rsi_500_arr = calculate_rsi(btc_500["close"].values, period=14)
    rsi_500 = pd.Series(rsi_500_arr, index=btc_500.index)

    # Compare at check bars
    print(f"\n{'Timestamp':<22} {'RSI_full':>10} {'RSI_500':>10} {'Diff':>8}  {'TV fires?':>12}")
    print("─" * 70)

    # TV fires at these bars (from _final_compare.py missing list — TV entries that engine misses)
    tv_fires_not_engine = {
        pd.Timestamp("2025-02-12 10:00"),
        pd.Timestamp("2025-02-14 16:30"),
        pd.Timestamp("2025-02-15 16:30"),
        pd.Timestamp("2025-02-19 16:00"),
    }

    # Engine fires but TV doesn't (from extra engine list)
    engine_fires_not_tv = {
        pd.Timestamp("2025-02-12 07:30"),
        pd.Timestamp("2025-02-15 00:00"),
        pd.Timestamp("2025-02-17 13:00"),
        pd.Timestamp("2025-02-18 04:30"),
        pd.Timestamp("2025-02-19 18:00"),
    }

    # Check a window around the first divergence (Feb 12)
    feb_window = full_btc[
        (full_btc.index >= pd.Timestamp("2025-02-11 00:00")) & (full_btc.index <= pd.Timestamp("2025-02-13 00:00"))
    ]
    print("\n=== Feb 11-13 window: full-history RSI vs 500-bar RSI ===")
    print(f"{'Timestamp':<22} {'Close':>10} {'RSI_full':>10} {'RSI_500':>10} {'Diff':>8}")
    print("─" * 65)
    for ts in feb_window.index:
        r_full = rsi_full.get(ts, float("nan"))
        r_500 = rsi_500.get(ts, float("nan"))
        diff = r_full - r_500
        eng_mark = " ← ENG" if ts in engine_fires_not_tv else ""
        tv_mark = " ← TV" if ts in tv_fires_not_engine else ""
        close = feb_window.loc[ts, "close"] if "close" in feb_window.columns else 0
        print(f"  {str(ts):<20} {close:>10.2f} {r_full:>10.4f} {r_500:>10.4f} {diff:>+8.4f}{eng_mark}{tv_mark}")

    # Summary: how many of the "extra engine" bars cross 52 in full vs 500?
    print("\n=== Extra engine crossunders: does full-history RSI still cross 52? ===")
    print(
        f"{'Bar':<22} {'RSI_full[T-1]':>14} {'RSI_full[T]':>12} {'RSI_500[T-1]':>14} {'RSI_500[T]':>12} {'Full crosses?':>14}"
    )
    print("─" * 90)
    for ts in sorted(engine_fires_not_tv):
        prev_ts = ts - pd.Timedelta(minutes=30)
        rf_prev = rsi_full.get(prev_ts, float("nan"))
        rf_cur = rsi_full.get(ts, float("nan"))
        r5_prev = rsi_500.get(prev_ts, float("nan"))
        r5_cur = rsi_500.get(ts, float("nan"))
        full_cross = "YES (still)" if (rf_prev >= 52 and rf_cur < 52) else "NO (fixed!)" if (rf_prev >= 52) else "n/a"
        print(f"  {str(ts):<20} {rf_prev:>14.4f} {rf_cur:>12.4f} {r5_prev:>14.4f} {r5_cur:>12.4f} {full_cross:>14}")


asyncio.run(main())
