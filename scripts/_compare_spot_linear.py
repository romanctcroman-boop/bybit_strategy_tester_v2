"""Compare spot vs linear BTC close prices to see which gives the right RSI."""

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
END_DATE = pd.Timestamp("2025-02-13", tz="UTC")
WARMUP_BARS = 500


async def get_btc(svc, market_type):
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE, market_type=market_type)
    warmup_ts_start = int(btc_start.timestamp() * 1000)
    warmup_ts_end = int(START_DATE.timestamp() * 1000)
    raw_warmup = await svc.adapter.get_historical_klines(
        "BTCUSDT", "30", warmup_ts_start, warmup_ts_end, market_type=market_type
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
        if btc_main.index.tz is None:
            df_w.index = df_w.index.tz_localize(None)
        btc = pd.concat([df_w, btc_main]).sort_index()
        btc = btc[~btc.index.duplicated(keep="last")]
    else:
        btc = btc_main
    rsi_full = calculate_rsi(btc["close"].values, period=14)
    btc["rsi"] = rsi_full
    return btc


async def main():
    svc = BacktestService()
    linear_btc = await get_btc(svc, "linear")
    spot_btc = await get_btc(svc, "spot")

    window_start = pd.Timestamp("2025-02-12 06:00")
    window_end = pd.Timestamp("2025-02-12 12:00")

    lin_w = linear_btc.loc[window_start:window_end]
    spot_w = spot_btc.loc[window_start:window_end]

    print("=== Feb 12 BTC RSI: Linear vs Spot vs TV ===")
    print(f"{'Timestamp':<22} {'Linear Close':>13} {'Linear RSI':>11} {'Spot Close':>13} {'Spot RSI':>11}  Notes")
    # TV fires at 10:00 (ep=2628.13), so SPOT close at 10:00 should be ~2628.13
    tv_crossunder_ts = pd.Timestamp("2025-02-12 10:00")
    for ts in lin_w.index:
        l_close = lin_w.loc[ts, "close"] if ts in lin_w.index else float("nan")
        l_rsi = lin_w.loc[ts, "rsi"] if ts in lin_w.index else float("nan")
        s_close = spot_w.loc[ts, "close"] if ts in spot_w.index else float("nan")
        s_rsi = spot_w.loc[ts, "rsi"] if ts in spot_w.index else float("nan")
        note = " <<< TV SHORT ENTRY" if ts == tv_crossunder_ts else ""
        print(f"  {str(ts):<20} {l_close:>13.2f} {l_rsi:>11.4f} {s_close:>13.2f} {s_rsi:>11.4f}{note}")


asyncio.run(main())
