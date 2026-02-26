"""Compare engine (no 5m) trades against TV CSV."""

import asyncio
import json
import sqlite3
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
import numpy as np, pandas as pd
from loguru import logger

logger.remove()
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
TV_CSV = r"c:\Users\roman\Downloads\z4.csv"


async def run():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?", (STRATEGY_ID,)
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    gp = json.loads(gr) if isinstance(gr, str) else (gr or {})
    graph = {
        "name": name,
        "blocks": json.loads(br) if isinstance(br, str) else (br or []),
        "connections": json.loads(cr) if isinstance(cr, str) else (cr or []),
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
        "main_strategy": gp.get("main_strategy", {}),
    }
    svc = BacktestService()
    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )

    # BTC 30m with warmup
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
        if "timestamp" in df_w.columns:
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms", utc=True)
            df_w = df_w.set_index("timestamp").sort_index()
        if btc_main.index.tz is None:
            btc_main.index = btc_main.index.tz_localize("UTC")
        if df_w.index.tz is None:
            df_w.index = df_w.index.tz_localize("UTC")
        btc_candles = pd.concat([df_w, btc_main]).sort_index()
        btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]
        print(f"BTC 30m: {len(btc_candles)} bars (with {WARMUP}-bar warmup)")
    except Exception as e:
        print(f"Warmup fail: {e}")
        btc_candles = btc_main

    # NO 5m data - pure bar-close signals only
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_candles, btcusdt_5m_ohlcv=None)
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
    print(f"Signals: {le.sum()} long  {se.sum()} short")

    r = FallbackEngineV4().run(
        BacktestInput(
            candles=candles,
            long_entries=le,
            long_exits=lx,
            short_entries=se,
            short_exits=sx,
            initial_capital=10000,
            position_size=0.10,
            use_fixed_amount=True,
            fixed_amount=100,
            leverage=10,
            stop_loss=0.132,
            take_profit=0.023,
            taker_fee=0.0007,
            slippage=0,
            direction=TradeDirection.BOTH,
            pyramiding=1,
            interval="30",
            entry_on_next_bar_open=True,
        )
    )
    trd = r.trades
    longs = [t for t in trd if t.direction == "long"]
    shorts = [t for t in trd if t.direction == "short"]
    print(f"Engine trades: {len(trd)} ({len(longs)}L + {len(shorts)}S)")

    # Load TV CSV
    tv = pd.read_csv(TV_CSV, sep=";")
    tv_ent = tv[tv["Тип"].str.startswith("Entry")].copy()
    tv_ent["ts_utc"] = pd.to_datetime(tv_ent["Дата и время"]) - pd.Timedelta(hours=3)
    tv_ent["side"] = tv_ent["Сигнал"].map({"RsiSE": "short", "RsiLE": "long"})
    # Price column
    price_col = "Цена USDT"
    tv_ent["ep"] = tv_ent[price_col].astype(str).str.replace(",", ".").apply(lambda x: float(x) if x.strip() else 0.0)

    tv_rows = list(tv_ent.itertuples())
    print(
        f"TV entries: {len(tv_rows)} ({sum(1 for r in tv_rows if r.side == 'long')}L + {sum(1 for r in tv_rows if r.side == 'short')}S)"
    )

    # Compare ALL entries
    print("\n" + "=" * 90)
    print(
        f"{'#':3s}  {'Eng side':8s}  {'Eng time':16s}  {'TV side':8s}  {'TV time':16s}  time_ok  {'Eng ep':10s}  {'TV ep':10s}  ep_ok"
    )
    ok_time = ok_ep = ok_both = 0
    max_rows = max(len(trd), len(tv_rows))
    for i in range(min(max_rows, 50)):
        t = trd[i] if i < len(trd) else None
        tv_row = tv_rows[i] if i < len(tv_rows) else None
        eng_time = str(t.entry_time)[:16] if t else "---"
        tv_time = str(tv_row.ts_utc)[:16] if tv_row else "---"
        eng_side = t.direction if t else "---"
        tv_side = tv_row.side if tv_row else "---"
        tv_ep = tv_row.ep if tv_row else 0.0
        eng_ep = t.entry_price if t else 0.0
        tm = eng_time == tv_time and eng_side == tv_side
        ep_ok = abs(eng_ep - tv_ep) < 1.0 if tv_ep > 0 else None
        ok_time += int(tm)
        ok_ep += int(ep_ok) if ep_ok is not None else 0
        ok_both += int(tm and ep_ok) if ep_ok is not None else 0
        ep_str = "OK" if ep_ok else ("DIFF" if ep_ok is not None else "N/A")
        mismatch = "" if (tm and (ep_ok or ep_ok is None)) else " <<<"
        print(
            f"{i + 1:3d}  {eng_side:8s}  {eng_time:16s}  {tv_side:8s}  {tv_time:16s}  {'OK' if tm else 'DIFF':7s}  {eng_ep:10.2f}  {tv_ep:10.2f}  {ep_str}{mismatch}"
        )

    print(f"\nTime+side matches: {ok_time}/{min(len(trd), len(tv_rows))}")
    print(f"Entry price matches (+-1): {ok_ep}/{min(len(trd), len(tv_rows))}")


asyncio.run(run())
