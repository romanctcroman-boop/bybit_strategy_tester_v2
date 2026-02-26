"""Compare Binance vs Bybit BTC closes at the divergence window."""

import datetime
import sys

sys.path.insert(0, ".")
import asyncio

import numpy as np
import pandas as pd
import requests
from loguru import logger

logger.remove()
from backend.backtesting.service import BacktestService
from backend.core.indicators import calculate_rsi

WINDOW_START = pd.Timestamp("2025-02-12 06:00", tz="UTC")
WINDOW_END = pd.Timestamp("2025-02-12 11:00", tz="UTC")
WARMUP_START = pd.Timestamp("2020-01-01", tz="UTC")
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")


def get_binance_klines(symbol: str, interval: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Fetch klines from Binance public API."""
    all_rows = []
    st = int(start.timestamp() * 1000)
    et = int(end.timestamp() * 1000)
    while st < et:
        kline_params: dict[str, str | int] = {
            "symbol": symbol,
            "interval": interval,
            "startTime": st,
            "endTime": et,
            "limit": 1000,
        }
        resp = requests.get(
            "https://api.binance.com/api/v3/klines",
            params=kline_params,
            timeout=30,
        )
        data = resp.json()
        if not data:
            break
        all_rows.extend(data)
        st = data[-1][0] + 1
        if len(data) < 1000:
            break
    df = pd.DataFrame(
        all_rows,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "qav",
            "num_trades",
            "tbbav",
            "tbqav",
            "ignore",
        ],
    )
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    df["close"] = df["close"].astype(float)
    df["open"] = df["open"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    return df


async def main():
    svc = BacktestService()

    # --- Bybit BTC 30m (with warmup) ---
    print("Fetching Bybit BTC 30m with 2020 warmup...")
    raw = await svc.adapter.get_historical_klines(
        symbol="BTCUSDT",
        interval="30",
        start_time=int(WARMUP_START.timestamp() * 1000),
        end_time=int(START_DATE.timestamp() * 1000),
        market_type="linear",
    )
    df_w = pd.DataFrame(raw)
    df_w["timestamp"] = pd.to_datetime(df_w["open_time"], unit="ms", utc=True)
    df_w = df_w.set_index("timestamp").sort_index()

    btc_main = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=START_DATE, end_date=pd.Timestamp("2026-02-24", tz="UTC")
    )
    if btc_main.index.tz is None:
        btc_main.index = btc_main.index.tz_localize("UTC")

    bybit = pd.concat([df_w, btc_main]).sort_index()
    bybit = bybit[~bybit.index.duplicated(keep="last")]

    # --- Binance BTC 30m (with warmup) ---
    print("Fetching Binance BTC 30m with 2020 warmup...")
    binance_w = get_binance_klines("BTCUSDT", "30m", WARMUP_START, START_DATE)
    binance_main = get_binance_klines("BTCUSDT", "30m", START_DATE, pd.Timestamp("2026-02-24", tz="UTC"))
    binance = pd.concat([binance_w, binance_main]).sort_index()
    binance = binance[~binance.index.duplicated(keep="last")]
    print(f"Binance BTC 30m: {len(binance)} bars")

    # --- Compute RSI for both ---
    bybit_rsi = pd.Series(calculate_rsi(bybit["close"].values, period=14), index=bybit.index)
    binance_rsi = pd.Series(calculate_rsi(binance["close"].values, period=14), index=binance.index)

    # --- Compare at divergence window ---
    print("\nBTC close + RSI comparison at 2025-02-12 06:00-11:00 UTC:")
    print(
        f"{'Time':7s}  {'Bybit close':12s}  {'Binance close':13s}  {'Bybit RSI':10s}  {'Binance RSI':11s}  diff_close  diff_rsi"
    )
    for ts in pd.date_range(WINDOW_START, WINDOW_END, freq="30min"):
        by_c = bybit["close"].get(ts, float("nan"))
        bn_c = binance["close"].get(ts, float("nan"))
        by_r = bybit_rsi.get(ts, float("nan"))
        bn_r = binance_rsi.get(ts, float("nan"))
        flag = " <<< ENGINE FIRES (RSI<52, prev>=52)" if (by_r < 52 and not np.isnan(by_r)) else ""
        bn_flag = " <<< BINANCE FIRES" if (bn_r < 52 and not np.isnan(bn_r)) else ""
        print(
            f"{ts.strftime('%H:%M'):7s}  {by_c:12.2f}  {bn_c:13.2f}  {by_r:10.4f}  {bn_r:11.4f}  {by_c - bn_c:+10.2f}  {by_r - bn_r:+8.4f}{flag}{bn_flag}"
        )

    # --- Count total signals for both sources ---
    print("\n--- Signal count for full period ---")
    for label, rsi_s in [("Bybit", bybit_rsi), ("Binance", binance_rsi)]:
        rsi_vals = rsi_s
        prev_rsi = rsi_vals.shift(1)
        short_cross = (prev_rsi >= 52) & (rsi_vals < 52)
        long_cross = (prev_rsi <= 24) & (rsi_vals > 24)
        print(
            f"  {label}: {short_cross.sum()} short crosses (RSI below 52)  {long_cross.sum()} long crosses (RSI above 24)"
        )

    print("\nBinance saved for further use.")
    # Save Binance data for use in indicator_handlers
    binance[["open", "high", "low", "close", "volume"]].to_csv(r"c:\Users\roman\Downloads\binance_btc_30m.csv")
    print("Saved to c:/Users/roman/Downloads/binance_btc_30m.csv")


asyncio.run(main())
