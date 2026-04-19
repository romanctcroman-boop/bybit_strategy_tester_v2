"""
Dump all RSI crossunder signals for RSI_L/S_7 and compare with TV trades from z4.csv.
Shows RSI_prev/curr at each signal bar to understand discrepancies.
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

from backend.backtesting.indicator_handlers import calculate_rsi
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"
Z4_PATH = r"d:\bybit_strategy_tester_v2\z4.csv"


def load_graph():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br) if isinstance(br, str) else (br or [])
    conns = json.loads(cr) if isinstance(cr, str) else (cr or [])
    gp = json.loads(gr) if isinstance(gr, str) else (gr or {})
    ms = gp.get("main_strategy", {})
    graph = {
        "name": name,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if ms:
        graph["main_strategy"] = ms
    return graph


def load_tv_trades():
    df = pd.read_csv(Z4_PATH)
    # Normalize columns
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    # Find entry time column
    entry_col = [c for c in df.columns if "entry" in c and "time" in c]
    exit_col = [c for c in df.columns if "exit" in c and "time" in c]
    type_col = [c for c in df.columns if "type" in c or "direction" in c or "trade" in c]
    price_col = [c for c in df.columns if "entry" in c and "price" in c]

    print(f"z4.csv columns: {list(df.columns)}")
    return df


async def main():
    graph = load_graph()
    svc = BacktestService()
    START = pd.Timestamp("2025-01-01", tz="UTC")
    END = pd.Timestamp("2026-02-24", tz="UTC")

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START, END)

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

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_all)
    signals = adapter.generate_signals(candles)

    le = np.asarray(signals.entries.values, dtype=bool)
    se = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(le), dtype=bool)
    )
    lx = np.asarray(signals.exits.values, dtype=bool) if signals.exits is not None else np.zeros(len(le), dtype=bool)
    sx = (
        np.asarray(signals.short_exits.values, dtype=bool)
        if signals.short_exits is not None
        else np.zeros(len(le), dtype=bool)
    )

    # Recompute RSI from BTC (should match what adapter computed)
    btc_close = btc_all["close"].copy()
    if candles.index.tz is None and btc_close.index.tz is not None:
        btc_close.index = btc_close.index.tz_localize(None)
    btc_rsi_arr = calculate_rsi(btc_close.values, period=14)
    btc_rsi = pd.Series(btc_rsi_arr, index=btc_close.index)
    rsi = btc_rsi.reindex(candles.index, method="ffill")

    print(f"\nTotal long signals: {le.sum()},  short signals: {se.sum()}")
    print(f"Total long exits:   {lx.sum()},  short exits:   {sx.sum()}")

    # Load TV trades
    tv_df = load_tv_trades()
    print(f"\nTV rows: {len(tv_df)}")

    # Parse TV entry times — try to find entry price and direction
    # Print first row to understand structure
    print("\nFirst TV row:")
    print(tv_df.iloc[0].to_dict())

    print("\n\nAll SHORT entry signals with RSI context:")
    print(f"{'bar_time':<22}  {'RSI[-1]':>9}  {'RSI[0]':>9}  {'RSI[+1]':>9}  {'ETH_close':>10}")
    print("-" * 75)
    for i, t in enumerate(candles.index):
        if se[i]:
            rsi_curr = float(rsi.iloc[i]) if i < len(rsi) else float("nan")
            rsi_prev = float(rsi.iloc[i - 1]) if i > 0 else float("nan")
            rsi_next = float(rsi.iloc[i + 1]) if i + 1 < len(rsi) else float("nan")
            eth_close = float(candles["close"].iloc[i])
            print(f"{str(t)[:19]:<22}  {rsi_prev:>9.4f}  {rsi_curr:>9.4f}  {rsi_next:>9.4f}  {eth_close:>10.2f}")

    print("\n\nAll LONG entry signals with RSI context:")
    print(f"{'bar_time':<22}  {'RSI[-1]':>9}  {'RSI[0]':>9}  {'RSI[+1]':>9}  {'ETH_close':>10}")
    print("-" * 75)
    for i, t in enumerate(candles.index):
        if le[i]:
            rsi_curr = float(rsi.iloc[i]) if i < len(rsi) else float("nan")
            rsi_prev = float(rsi.iloc[i - 1]) if i > 0 else float("nan")
            rsi_next = float(rsi.iloc[i + 1]) if i + 1 < len(rsi) else float("nan")
            eth_close = float(candles["close"].iloc[i])
            print(f"{str(t)[:19]:<22}  {rsi_prev:>9.4f}  {rsi_curr:>9.4f}  {rsi_next:>9.4f}  {eth_close:>10.2f}")


asyncio.run(main())
