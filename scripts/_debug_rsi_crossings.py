"""Quick check: RSI values around 2025-02-12 07:30 to understand the mismatch."""

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
import numpy as np, pandas as pd
from loguru import logger

logger.remove()
from backend.backtesting.service import BacktestService
from backend.core.indicators import calculate_rsi

START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
PERIOD = 14
CHECK_TIME = pd.Timestamp("2025-02-12 07:30", tz="UTC")


async def main():
    svc = BacktestService()
    WARMUP = 500
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP * 30)
    btc_main = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    try:
        raw = await svc.adapter.get_historical_klines(
            symbol="BTCUSDT",
            interval="30",
            start_time=int(btc_start.timestamp() * 1000),
            end_time=int(START_DATE.timestamp() * 1000),
            market_type="linear",
        )
        df_w = pd.DataFrame(raw)
        for o, n in {
            "startTime": "timestamp",
            "openPrice": "open",
            "highPrice": "high",
            "lowPrice": "low",
            "closePrice": "close",
        }.items():
            if o in df_w.columns and n not in df_w.columns:
                df_w = df_w.rename(columns={o: n})
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df_w.columns:
                df_w[col] = pd.to_numeric(df_w[col], errors="coerce")
        df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms", utc=True)
        df_w = df_w.set_index("timestamp").sort_index()
        if btc_main.index.tz is None:
            btc_main.index = btc_main.index.tz_localize("UTC")
        btc_candles = pd.concat([df_w, btc_main]).sort_index()
        btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]
        print(f"BTC 30m: {len(btc_candles)} bars [{btc_candles.index[0]} .. {btc_candles.index[-1]}]")
    except Exception as e:
        print(f"Warmup fail: {e}")
        btc_candles = btc_main

    btc_close = btc_candles["close"].copy()
    if btc_close.index.tz is None:
        btc_close.index = btc_close.index.tz_localize("UTC")

    rsi_arr = calculate_rsi(btc_close.values, period=PERIOD)
    btc_rsi = pd.Series(rsi_arr, index=btc_close.index)

    # Print RSI around 2025-02-12 07:00-10:00
    window_start = pd.Timestamp("2025-02-12 06:00", tz="UTC")
    window_end = pd.Timestamp("2025-02-12 11:00", tz="UTC")
    rsi_window = btc_rsi[(btc_rsi.index >= window_start) & (btc_rsi.index <= window_end)]
    print("\nBTC 30m RSI around 2025-02-12 07:00-10:30:")
    print(f"{'time':25s}  {'BTC close':12s}  {'RSI':10s}  {'RSI[prev]':10s}  cross<52?")
    for i, (ts, rsi_val) in enumerate(rsi_window.items()):
        idx_in_series = btc_close.index.get_loc(ts)
        prev_rsi = btc_rsi.iloc[idx_in_series - 1] if idx_in_series > 0 else float("nan")
        close_val = btc_close.loc[ts]
        cross = ">>> CROSS <<<" if (prev_rsi >= 52 and rsi_val < 52) else ""
        print(f"{str(ts):25s}  {close_val:12.4f}  {rsi_val:10.4f}  {prev_rsi:10.4f}  {cross}")


asyncio.run(main())
