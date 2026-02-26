"""
Compare engine with entry_on_next_bar_open=True against TV CSV trades.
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

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
TV_CSV = r"c:\Users\roman\Downloads\z4.csv"


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

    r = FallbackEngineV4().run(
        BacktestInput(
            candles=candles,
            long_entries=le,
            long_exits=lx,
            short_entries=se,
            short_exits=sx,
            initial_capital=10_000.0,
            position_size=0.10,
            use_fixed_amount=True,
            fixed_amount=100.0,
            leverage=10,
            stop_loss=0.132,
            take_profit=0.023,
            taker_fee=0.0007,
            slippage=0.0,
            direction=TradeDirection.BOTH,
            pyramiding=1,
            interval="30",
            entry_on_next_bar_open=True,
        )
    )
    trades = r.trades
    longs = [t for t in trades if t.direction == "long"]
    shorts = [t for t in trades if t.direction == "short"]
    print(f"NEXT_BAR: {len(trades)} trades ({len(longs)}L + {len(shorts)}S)  [TV: 147 = 32L+115S]")

    tv = pd.read_csv(TV_CSV, sep=";")
    tv_ent = tv[tv["Тип"].str.startswith("Entry")].copy()
    tv_ent["ts_utc"] = pd.to_datetime(tv_ent["Дата и время"]) - pd.Timedelta(hours=3)
    tv_ent["ts_str"] = tv_ent["ts_utc"].dt.strftime("%Y-%m-%d %H:%M")
    tv_ent["side"] = tv_ent["Сигнал"].map({"RsiSE": "short", "RsiLE": "long"})
    tv_ent["price"] = pd.to_numeric(tv_ent["Цена USDT"].astype(str).str.replace(",", "."), errors="coerce")
    tv_rows = [(row.ts_str, row.side, row.price) for row in tv_ent.itertuples()]

    print()
    print("DETAILED COMPARISON (all engine trades vs TV, first 30 shown):")
    hdr = f"  {'i':3s}  {'side':5s}  {'eng_time':16s}  {'tv_time':16s}  {'T?':4s}  {'eng_ep':9s}  {'tv_ep':9s}  P?"
    print(hdr)
    ok_t = ok_p = total = 0
    for i, (t, (tvt, tvs, tvep)) in enumerate(zip(trades[:30], tv_rows[:30], strict=False)):
        eng_t = str(t.entry_time)[:16].replace("T", " ")
        tm = eng_t == tvt
        pm = abs(t.entry_price - tvep) < 0.50 if tvep and tvep > 0 else None
        ok_t += int(tm)
        ok_p += int(pm) if pm is not None else 0
        total += 1
        print(
            f"  {i:3d}  {t.direction:5s}  {eng_t:16s}  {tvt:16s}  {'OK' if tm else '!':4s}"
            f"  {t.entry_price:9.2f}  {tvep:9.2f}  {'OK' if pm else ('!' if pm is not None else '?')}"
        )
    print(f"Time OK: {ok_t}/{total}  Price OK (+-0.5): {ok_p}/{total}")

    # Find divergence
    eng_times = sorted(str(t.entry_time)[:16].replace("T", " ") for t in trades)
    tv_times_list = sorted(r[0] for r in tv_rows)
    eng_set = set(eng_times)
    tv_set = set(tv_times_list)
    eng_only = sorted(eng_set - tv_set)
    tv_only = sorted(tv_set - eng_set)
    print()
    print(f"Engine-only entries ({len(eng_only)}): {eng_only[:15]}")
    print(f"TV-only entries    ({len(tv_only)}): {tv_only[:15]}")


asyncio.run(main())
