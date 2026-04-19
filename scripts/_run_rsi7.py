"""
Run Strategy_RSI_L/S_7 (ETHUSDT 30m) and compare signal count vs TV.
TV reference: z2.csv = 146 total trades (145 closed + 1 open)
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

    print(f"Strategy: {name}")
    for b in blocks:
        btype = b.get("type", "?")
        params = b.get("params", {})
        print(f"  block [{btype}]: {json.dumps(params, ensure_ascii=False)}")

    ms = gp.get("main_strategy", {})
    if ms:
        print(f"  main_strategy: {json.dumps(ms, ensure_ascii=False)}")

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


async def main():
    graph = load_graph()

    print(f"\nFetching ETHUSDT 30m {START_DATE} -> {END_DATE} ...")
    svc = BacktestService()
    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT",
        interval="30",
        start_date=START_DATE,
        end_date=END_DATE,
    )
    print(f"  {len(candles)} bars  [{candles.index[0]} .. {candles.index[-1]}]")

    # Fetch BTCUSDT for use_btc_source RSI — include 500 warmup bars (500×30m ≈ 10.4 days)
    # so Wilder RSI is stable by the time the strategy period begins.
    # The DB only holds data from 2025-01-01, so we fetch warmup bars directly via the
    # Bybit API and prepend them to the in-range DB data.
    WARMUP_BARS = 500
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    print(f"Fetching BTCUSDT 30m for RSI source (with {WARMUP_BARS}-bar warmup from {btc_start}) ...")

    # In-range BTC from DB (fast)
    btc_candles_main = await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="30",
        start_date=START_DATE,
        end_date=END_DATE,
    )

    # Warmup bars from Bybit API (pre-DB-range)
    btc_candles_warmup = None
    try:
        warmup_start_ts = int(btc_start.timestamp() * 1000)
        warmup_end_ts = int(START_DATE.timestamp() * 1000)
        raw_warmup = await svc.adapter.get_historical_klines(
            symbol="BTCUSDT",
            interval="30",
            start_time=warmup_start_ts,
            end_time=warmup_end_ts,
            market_type="linear",
        )
        if raw_warmup:
            df_w = pd.DataFrame(raw_warmup)
            # Normalise column names (adapter may use open_time or startTime)
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
            btc_candles_warmup = df_w
            print(f"  Warmup from API: {len(df_w)} bars  [{df_w.index[0]} .. {df_w.index[-1]}]")
    except Exception as e:
        print(f"  WARNING: warmup fetch failed: {e} — proceeding without warmup")

    # Concatenate warmup + main, deduplicate on index
    if btc_candles_warmup is not None and len(btc_candles_warmup) > 0:
        # Normalise tz: DB data may be tz-naive; make both UTC-aware
        if btc_candles_main.index.tz is None:
            btc_candles_main.index = btc_candles_main.index.tz_localize("UTC")
        if btc_candles_warmup.index.tz is None:
            btc_candles_warmup.index = btc_candles_warmup.index.tz_localize("UTC")
        btc_candles = pd.concat([btc_candles_warmup, btc_candles_main]).sort_index()
        btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]
    else:
        btc_candles = btc_candles_main

    print(f"  Total BTC bars (warmup+main): {len(btc_candles)}  [{btc_candles.index[0]} .. {btc_candles.index[-1]}]")

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

    print(f"\nSignals: long_entries={le.sum()}  short_entries={se.sum()}")
    print(f"         long_exits={lx.sum()}    short_exits={sx.sum()}")

    # Show first 5 long entry times
    long_entry_times = candles.index[le][:5]
    short_entry_times = candles.index[se][:5]
    print(f"\nFirst 5 long entries:  {list(long_entry_times)}")
    print(f"First 5 short entries: {list(short_entry_times)}")

    result = FallbackEngineV4().run(
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
        )
    )

    trades = result.trades
    print(f"\n{'=' * 60}")
    print("TV  trades: 145 (closed) + 1 open = 146 total")
    print(f"Eng trades: {len(trades)}")
    print(f"Diff:       {146 - len(trades)}")
    print()

    # Breakdown
    longs = [t for t in trades if t.direction == "long"]
    shorts = [t for t in trades if t.direction == "short"]
    print(f"Engine: {len(longs)} long, {len(shorts)} short")
    print("TV:     31 long, 115 short")
    print()

    # First 10 engine trades
    print("First 10 engine trades:")
    for t in trades[:10]:
        print(
            f"  {t.direction:5s} {str(t.entry_time)[:16]} -> {str(t.exit_time)[:16]}  "
            f"ep={t.entry_price:.2f}  pnl={t.pnl:.2f}  {t.exit_reason}"
        )

    # TV first 10 trades from z4.csv (hardcoded from attachment)
    print("\nFirst 10 TV trades (from z4.csv):")
    tv_sample = [
        ("short", "2025-01-01 13:30", "2025-01-08 17:00", 3334.62, 3257.92, 21.61),
        ("short", "2025-01-09 00:00", "2025-01-09 13:30", 3322.53, 3246.11, 21.61),
        ("short", "2025-01-09 17:30", "2025-01-09 19:30", 3285.67, 3210.09, 21.62),
        ("short", "2025-01-10 21:00", "2025-01-13 06:30", 3257.99, 3183.05, 21.62),
        ("long", "2025-01-13 13:30", "2025-01-14 00:00", 3075.39, 3146.13, 21.58),
        ("short", "2025-01-14 16:30", "2025-01-27 05:30", 3191.83, 3118.41, 21.61),
        ("long", "2025-01-27 08:00", "2025-01-27 14:30", 3068.83, 3139.42, 21.58),
        ("short", "2025-01-27 16:30", "2025-01-27 18:30", 3117.00, 3045.30, 21.62),
        ("short", "2025-01-28 18:00", "2025-01-28 20:30", 3165.71, 3092.89, 21.61),
        ("short", "2025-01-29 05:00", "2025-02-02 11:30", 3122.65, 3050.82, 21.62),
    ]
    for side, en, ex, ep, xp, pnl in tv_sample:
        print(f"  {side:5s} {en} -> {ex}  ep={ep:.2f}  pnl={pnl:.2f}")


asyncio.run(main())
