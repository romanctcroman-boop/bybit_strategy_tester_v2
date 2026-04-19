"""
Quickly check: with warmup BTC, no 5m intra-bar, entry_on_next_bar_open=True → how many trades?
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
    # Load strategy graph
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?",
        (STRATEGY_ID,),
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
    print(f"ETH 30m: {len(candles)} bars")

    # Fetch BTC with 500-bar warmup (using the same approach as _run_rsi7_next_bar.py)
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
        col_map = {
            "startTime": "timestamp",
            "openPrice": "open",
            "highPrice": "high",
            "lowPrice": "low",
            "closePrice": "close",
        }
        for o, n in col_map.items():
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
        if isinstance(btc_main.index, pd.RangeIndex):
            btc_main = btc_main.reset_index(drop=True)
        if btc_main.index.tz is None:
            btc_main.index = btc_main.index.tz_localize("UTC")
        if df_w.index.tz is None:
            df_w.index = df_w.index.tz_localize("UTC")
        btc_candles = pd.concat([df_w, btc_main]).sort_index()
        btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]
        print(f"BTC 30m: {len(btc_candles)} bars (with {WARMUP_BARS}-bar warmup)")
    except Exception as e:
        print(f"BTC warmup failed: {e}")
        btc_candles = btc_main

    # Generate signals WITHOUT 5m intra-bar
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
    print(f"Signals (no 5m): {le.sum()} long  {se.sum()} short")

    def run_engine(next_bar_open: bool, label: str):
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
                entry_on_next_bar_open=next_bar_open,
            )
        )
        trd = r.trades
        longs = [t for t in trd if t.direction == "long"]
        shorts = [t for t in trd if t.direction == "short"]
        print(f"{label}: {len(trd)} trades ({len(longs)}L + {len(shorts)}S)")
        return trd

    base_trades = run_engine(False, "BASELINE (next_bar_open=False)")
    next_trades = run_engine(True, "NEXT_BAR  (next_bar_open=True )")

    # Compare first 20 vs TV
    tv = pd.read_csv(TV_CSV, sep=";")
    tv_ent = tv[tv["Тип"].str.startswith("Entry")].copy()
    tv_ent["ts_utc"] = pd.to_datetime(tv_ent["Дата и время"]) - pd.Timedelta(hours=3)
    tv_ent["side"] = tv_ent["Сигнал"].map({"RsiSE": "short", "RsiLE": "long"})
    tv_ent["ep"] = (
        tv_ent["Цена USDT"].astype(str).str.replace(",", ".").apply(lambda x: float(x.strip()) if x.strip() else 0.0)
    )

    tv_rows = list(tv_ent.itertuples())
    print(
        f"\nTV: {len(tv_rows)} entries ({sum(1 for r in tv_rows if r.side == 'long')}L + {sum(1 for r in tv_rows if r.side == 'short')}S)"
    )

    print("\n" + "=" * 90)
    print(
        f"{'#':3s}  {'Eng side':8s}  {'Eng time':16s}  {'TV side':8s}  {'TV time':16s}  time_ok  {'Eng ep':10s}  {'TV ep':10s}  ep_ok"
    )
    ok_time = ok_ep = 0
    for i in range(min(30, len(next_trades), len(tv_rows))):
        t = next_trades[i]
        tv_row = tv_rows[i]
        eng_time = str(t.entry_time)[:16]
        tv_time = str(tv_row.ts_utc)[:16]
        eng_side = t.direction
        tv_side = tv_row.side
        tv_ep = tv_row.ep
        tm = eng_time == tv_time and eng_side == tv_side
        ep_ok = abs(t.entry_price - tv_ep) < 1.0 if tv_ep > 0 else None
        ok_time += int(tm)
        ok_ep += int(ep_ok) if ep_ok is not None else 0
        ep_str = "OK" if ep_ok else ("DIFF" if ep_ok is not None else "N/A")
        mark = "" if (tm and ep_ok is not False) else " <<<"
        print(
            f"{i + 1:3d}  {eng_side:8s}  {eng_time:16s}  {tv_side:8s}  {tv_time:16s}  {'OK' if tm else 'DIFF':7s}  {t.entry_price:10.2f}  {tv_ep:10.2f}  {ep_str}{mark}"
        )

    print(f"\nTime+side matches: {ok_time}/{min(30, len(next_trades), len(tv_rows))}")
    print(f"Entry price matches (+-1): {ok_ep}/{min(30, len(next_trades), len(tv_rows))}")
    print(f"\nFINAL: Engine={len(next_trades)}, TV={len(tv_rows)}, diff={len(tv_rows) - len(next_trades)}")


asyncio.run(main())
