"""
Investigate RSI crossunder at 2025-02-12 and other anomaly divergence points.
Compares engine RSI signals vs TV expected signal times.
"""

import asyncio
import json
import sqlite3
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
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.core.indicators.momentum import calculate_rsi

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")

# TV anomaly entry times (UTC) where engine diverges
# Engine fires 2h EARLIER than TV (bars shifted)
TV_ANOMALY_ENTRIES_UTC = [
    "2025-02-12 10:00",  # TV entry (next bar open) => signal on bar 2025-02-12 09:30
    "2025-02-14 16:30",
    "2025-02-15 16:30",
    "2025-02-19 16:00",
]


async def main():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?",
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

    svc = BacktestService()
    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )

    WARMUP_BARS = 500
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
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
            "open_time": "timestamp",
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
        if "timestamp" in df_w.columns:
            if df_w["timestamp"].dtype in ["int64", "float64"]:
                df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms", utc=True)
            else:
                df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], utc=True)
            df_w = df_w.set_index("timestamp").sort_index()
        if btc_main.index.tz is None:
            btc_main.index = btc_main.index.tz_localize("UTC")
        if df_w.index.tz is None:
            df_w.index = df_w.index.tz_localize("UTC")
        btc_candles = pd.concat([df_w, btc_main]).sort_index()
        btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]
    except Exception as e:
        print(f"BTC warmup failed: {e}")
        btc_candles = btc_main

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_candles)
    signals = adapter.generate_signals(candles)
    se = np.asarray(signals.short_entries.values, dtype=bool)
    le = np.asarray(signals.entries.values, dtype=bool)

    # Compute RSI on full BTC series
    rsi_full = calculate_rsi(btc_candles["close"].values, 14)
    btc_candles = btc_candles.copy()
    btc_candles["rsi"] = rsi_full
    btc_candles["rsi_prev"] = btc_candles["rsi"].shift(1)
    btc_candles["cross_short"] = (btc_candles["rsi_prev"] >= 52) & (btc_candles["rsi"] < 52)
    btc_candles["cross_long"] = (btc_candles["rsi_prev"] <= 24) & (btc_candles["rsi"] > 24)

    # --- Inspect around 2025-02-12 ---
    print("=" * 70)
    print("WINDOW 2025-02-11 22:00 to 2025-02-12 12:00 (BTC RSI @ 52 level)")
    print("=" * 70)
    btc_w = btc_candles.loc["2025-02-11 22:00":"2025-02-12 12:00"]
    for ts, row in btc_w.iterrows():
        cs = " <<SHORT>>" if row["cross_short"] else ""
        print(f"  {str(ts)[:16]}  BTC={row['close']:9.2f}  rsi={row['rsi']:7.3f}  prev={row['rsi_prev']:7.3f}{cs}")

    # Engine short signals around this time
    print()
    print("ETH short signals 2025-02-12:")
    eth_slice = candles.loc["2025-02-12 04:00":"2025-02-12 12:00"]
    for ts in eth_slice.index:
        pos = candles.index.get_loc(ts)
        sig = se[pos] if pos < len(se) else False
        print(f"  ETH {str(ts)[:16]}  short_entry={sig}")

    # --- Show ALL engine short signal times vs TV short signal times ---
    print()
    print("=" * 70)
    print("ALL engine SHORT signal bars (where se[i]=True):")
    print("=" * 70)
    eng_short_times = []
    for i, ts in enumerate(candles.index):
        if se[i]:
            eng_short_times.append(str(ts)[:16].replace("T", " "))
    for t in eng_short_times:
        print(f"  {t}")

    tv = pd.read_csv(r"c:\Users\roman\Downloads\z4.csv", sep=";")
    tv_ent = tv[tv["Тип"].str.startswith("Entry")].copy()
    tv_ent["ts_utc"] = pd.to_datetime(tv_ent["Дата и время"]) - pd.Timedelta(hours=3)
    # TV entry time = next bar open. Signal bar = tv_entry - 30min
    tv_ent["signal_bar"] = tv_ent["ts_utc"] - pd.Timedelta(minutes=30)
    tv_short = tv_ent[tv_ent["Сигнал"] == "RsiSE"]["signal_bar"].dt.strftime("%Y-%m-%d %H:%M").tolist()
    tv_long = tv_ent[tv_ent["Сигнал"] == "RsiLE"]["signal_bar"].dt.strftime("%Y-%m-%d %H:%M").tolist()

    print()
    print("=" * 70)
    print("TV SHORT signal bars (entry_time - 30min = signal bar):")
    print("=" * 70)
    for t in tv_short:
        print(f"  {t}")

    eng_set = set(eng_short_times)
    tv_set = set(tv_short)
    print()
    print(f"Engine SHORT signals: {len(eng_set)}")
    print(f"TV     SHORT signals: {len(tv_set)}")
    print(f"Engine-only: {sorted(eng_set - tv_set)[:10]}")
    print(f"TV-only:     {sorted(tv_set - eng_set)[:10]}")


asyncio.run(main())
