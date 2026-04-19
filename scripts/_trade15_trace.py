"""
Trace Trade 15 exit in detail: check OHLC around Feb 11 to find exactly when TP hits.
Also check around Feb 12 07:30 to understand why engine enters there.
"""

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import pandas as pd
from loguru import logger

logger.remove()

from backend.backtesting.indicator_handlers import calculate_rsi
from backend.backtesting.service import BacktestService

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"


async def main():
    svc = BacktestService()
    START = pd.Timestamp("2025-01-01", tz="UTC")
    END = pd.Timestamp("2026-02-24", tz="UTC")

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START, END)

    # Fetch BTC with warmup
    import numpy as np

    WARMUP = 500
    btc_start = START - pd.Timedelta(minutes=WARMUP * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START, END)
    warmup_start_ts = int(btc_start.timestamp() * 1000)
    warmup_end_ts = int(START.timestamp() * 1000)
    raw_warmup = await svc.adapter.get_historical_klines(
        symbol="BTCUSDT",
        interval="30",
        start_time=warmup_start_ts,
        end_time=warmup_end_ts,
        market_type="linear",
    )
    df_w = pd.DataFrame(raw_warmup)
    col_map = {
        "startTime": "timestamp",
        "open_time": "timestamp",
        "openPrice": "open",
        "highPrice": "high",
        "lowPrice": "low",
        "closePrice": "close",
    }
    for old, new in col_map.items():
        if old in df_w.columns and new not in df_w.columns:
            df_w = df_w.rename(columns={old: new})
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df_w.columns:
            df_w[col] = pd.to_numeric(df_w[col], errors="coerce")
    if "timestamp" in df_w.columns:
        if df_w["timestamp"].dtype in ["int64", "float64"]:
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms", utc=True)
        else:
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], utc=True)
        df_w = df_w.set_index("timestamp").sort_index()
    if btc_main.index.tz is None:
        btc_main.index = btc_main.index.tz_localize("UTC")
    btc_all = pd.concat([df_w, btc_main]).sort_index()
    btc_all = btc_all[~btc_all.index.duplicated(keep="last")]

    # Compute BTC RSI
    btc_close = btc_all["close"].copy()
    if candles.index.tz is None and btc_close.index.tz is not None:
        btc_close.index = btc_close.index.tz_localize(None)
    btc_rsi_arr = calculate_rsi(btc_close.values, period=14)
    btc_rsi = pd.Series(btc_rsi_arr, index=btc_close.index)
    rsi = btc_rsi.reindex(candles.index, method="ffill")

    # Trade 15: entry=02-10 19:30, price=2671.23, direction=short
    entry_price = 2671.23
    tp_price = entry_price * (1 - 0.023)
    sl_price = entry_price * (1 + 0.132)
    print(f"Trade 15: SHORT entry={entry_price:.2f}, TP={tp_price:.4f}, SL={sl_price:.4f}")
    print()

    # Handle tz-naive candles index
    if candles.index.tz is None:
        tz_kwarg = {}
    else:
        tz_kwarg = {"tz": "UTC"}

    # Show OHLC from entry to exit
    t_start = pd.Timestamp("2025-02-10 19:30", **tz_kwarg)
    t_end = pd.Timestamp("2025-02-12 09:30", **tz_kwarg)  # past the exit

    subset = candles.loc[t_start:t_end]
    print(f"ETH OHLC from {t_start} to {t_end}:")
    print(
        f"{'bar_time':<22}  {'open':>10}  {'high':>10}  {'low':>10}  {'close':>10}  {'RSI':>8}  {'TP_hit':>7}  {'SL_hit':>7}"
    )
    print("-" * 100)

    for t, row in subset.iterrows():
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        rsi_val = float(rsi.loc[t]) if t in rsi.index else float("nan")
        tp_hit = " TP!" if l <= tp_price else ""
        sl_hit = " SL!" if h >= sl_price else ""
        marker = ""
        if tp_hit:
            marker = " <-- TP hit"
        elif sl_hit:
            marker = " <-- SL hit"
        print(
            f"{str(t)[:19]:<22}  {o:>10.4f}  {h:>10.4f}  {l:>10.4f}  {c:>10.4f}  {rsi_val:>8.4f}  {tp_hit:>7}  {sl_hit:>7}  {marker}"
        )

    print()
    print(f"TP price = {tp_price:.4f}")
    print(f"SL price = {sl_price:.4f}")

    # Now look specifically at Feb 12 07:00 - 12:00
    print()
    print("=" * 100)
    print("DETAILED OHLC + RSI around Feb 12 07:00 - 12:00:")
    t2_start = pd.Timestamp("2025-02-12 06:00", **tz_kwarg)
    t2_end = pd.Timestamp("2025-02-12 12:00", **tz_kwarg)
    subset2 = candles.loc[t2_start:t2_end]

    print(f"{'bar_time':<22}  {'open':>10}  {'high':>10}  {'low':>10}  {'close':>10}  {'RSI':>8}  {'crossunder52':>13}")
    print("-" * 100)

    rsi_vals = rsi.reindex(candles.index, method="ffill")
    for t, row in subset2.iterrows():
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        rsi_curr = float(rsi.loc[t]) if t in rsi.index else float("nan")
        t_prev = candles.index[candles.index.get_loc(t) - 1]
        rsi_prev_val = float(rsi.loc[t_prev]) if t_prev in rsi.index else float("nan")
        crossunder = (rsi_prev_val >= 52) and (rsi_curr < 52)
        cu_marker = " <crossunder52" if crossunder else ""
        print(f"{str(t)[:19]:<22}  {o:>10.4f}  {h:>10.4f}  {l:>10.4f}  {c:>10.4f}  {rsi_curr:>8.4f}  {cu_marker}")


asyncio.run(main())
