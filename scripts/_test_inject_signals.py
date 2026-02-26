"""
Test: manually inject the 6 known intra-bar anomaly signal bars into the
engine's signal arrays and check whether trade count changes from 151 → 147.

The 6 anomaly bars (UTC, tz-naive) where TV fires due to calc_on_every_tick:
  SHORT: 2025-02-12 09:30, 2025-02-19 15:30, 2025-04-19 20:30, 2025-06-14 01:00
  LONG:  2025-03-28 17:30, 2025-07-25 04:30
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

# Known intra-bar signal bars (tz-naive UTC, matching candles.index tz)
INTRABAR_SHORT_BARS = [
    pd.Timestamp("2025-02-12 09:30"),
    pd.Timestamp("2025-02-19 15:30"),
    pd.Timestamp("2025-04-19 20:30"),
    pd.Timestamp("2025-06-14 01:00"),
]
INTRABAR_LONG_BARS = [
    pd.Timestamp("2025-03-28 17:30"),
    pd.Timestamp("2025-07-25 04:30"),
]


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


async def run_engine(candles, le, se, lx, sx, label=""):
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
    longs = [t for t in trades if t.direction == "long"]
    shorts = [t for t in trades if t.direction == "short"]
    print(f"{label}: {len(trades)} trades ({len(longs)}L + {len(shorts)}S)")
    return trades


async def main():
    graph = load_graph()

    print(f"Fetching ETHUSDT 30m {START_DATE} -> {END_DATE} ...")
    svc = BacktestService()
    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    tz_str = str(candles.index.tz) if candles.index.tz else "tz-naive"
    print(f"  {len(candles)} bars  [{candles.index[0]} .. {candles.index[-1]}]  ({tz_str})")

    # Fetch BTC 30m with warmup
    WARMUP_BARS = 500
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    print(f"Fetching BTCUSDT 30m with {WARMUP_BARS}-bar warmup from {btc_start} ...")
    btc_candles_main = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
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
        print(f"  WARNING: warmup fetch failed: {e}")

    if btc_candles_warmup is not None and len(btc_candles_warmup) > 0:
        if btc_candles_main.index.tz is None:
            btc_candles_main.index = btc_candles_main.index.tz_localize("UTC")
        if btc_candles_warmup.index.tz is None:
            btc_candles_warmup.index = btc_candles_warmup.index.tz_localize("UTC")
        btc_candles = pd.concat([btc_candles_warmup, btc_candles_main]).sort_index()
        btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]
    else:
        btc_candles = btc_candles_main
    print(f"  Total BTC: {len(btc_candles)} bars  [{btc_candles.index[0]} .. {btc_candles.index[-1]}]")

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

    print(f"\nOriginal signals: long_entries={le.sum()}  short_entries={se.sum()}")

    # ── Baseline ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("BASELINE (no injection):")
    baseline_trades = await run_engine(candles, le.copy(), se.copy(), lx.copy(), sx.copy(), label="  Baseline")
    print(f"  TV target: 147 trades (31L + 115S)")

    # ── Normalise candles.index to tz-naive for bar lookup ────────────────────
    candle_idx = candles.index
    if candle_idx.tz is not None:
        candle_idx_naive = candle_idx.tz_localize(None)
    else:
        candle_idx_naive = candle_idx

    # ── Inject intra-bar SHORT signals ────────────────────────────────────────
    le_inj = le.copy()
    se_inj = se.copy()
    injected_s = 0
    injected_l = 0
    missing_bars = []

    for bar in INTRABAR_SHORT_BARS:
        bar_tz_naive = pd.Timestamp(bar)
        try:
            pos = candle_idx_naive.get_loc(bar_tz_naive)
            if not se_inj[pos]:
                se_inj[pos] = True
                injected_s += 1
                print(f"  [INJECT SHORT] bar={bar}  pos={pos}  (was False)")
            else:
                print(f"  [ALREADY SHORT] bar={bar}  pos={pos}")
        except KeyError:
            missing_bars.append(bar)
            print(f"  [NOT IN INDEX] bar={bar}")

    for bar in INTRABAR_LONG_BARS:
        bar_tz_naive = pd.Timestamp(bar)
        try:
            pos = candle_idx_naive.get_loc(bar_tz_naive)
            if not le_inj[pos]:
                le_inj[pos] = True
                injected_l += 1
                print(f"  [INJECT LONG] bar={bar}  pos={pos}  (was False)")
            else:
                print(f"  [ALREADY LONG] bar={bar}  pos={pos}")
        except KeyError:
            missing_bars.append(bar)
            print(f"  [NOT IN INDEX] bar={bar}")

    print(f"\nInjected: {injected_s} SHORT + {injected_l} LONG  |  Missing bars: {len(missing_bars)}")
    print(f"Updated signals: long_entries={le_inj.sum()}  short_entries={se_inj.sum()}")

    # ── With injection ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("WITH INJECTED INTRA-BAR SIGNALS:")
    injected_trades = await run_engine(candles, le_inj, se_inj, lx.copy(), sx.copy(), label="  Injected")
    print(f"  TV target: 147 trades (31L + 115S)")

    # ── Diff trades ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("TRADE DIFF (injected vs baseline):")
    b_entries = {(t.direction, str(t.entry_time)[:16]) for t in baseline_trades}
    i_entries = {(t.direction, str(t.entry_time)[:16]) for t in injected_trades}
    added = sorted(i_entries - b_entries)
    removed = sorted(b_entries - i_entries)
    print(f"  Added trades: {len(added)}")
    for x in added[:20]:
        print(f"    + {x[0]:5s} {x[1]}")
    print(f"  Removed trades: {len(removed)}")
    for x in removed[:20]:
        print(f"    - {x[0]:5s} {x[1]}")

    # ── Compare with TV entries ───────────────────────────────────────────────
    try:
        tv = pd.read_csv(r"c:\Users\roman\Downloads\z4.csv", sep=";")
        ent = tv[tv["Тип"].str.startswith("Entry")].copy()
        ent["ts_utc"] = pd.to_datetime(ent["Дата и время"]) - pd.Timedelta(hours=3)
        tv_entries = set(ent["ts_utc"].dt.strftime("%Y-%m-%d %H:%M"))

        print(f"\n" + "=" * 60)
        print("TV vs ENGINE (injected) entry comparison:")
        i_entry_times = {str(t.entry_time)[:16].replace("T", " "): t.direction for t in injected_trades}
        tv_entry_set = set(tv_entries)
        eng_set = set(i_entry_times.keys())
        tv_only = sorted(tv_entry_set - eng_set)
        eng_only = sorted(eng_set - tv_entry_set)
        print(f"  TV entries: {len(tv_entry_set)}")
        print(f"  Engine entries: {len(eng_set)}")
        print(f"  In TV but not Engine ({len(tv_only)}):")
        for x in tv_only[:20]:
            print(f"    TV:  {x}")
        print(f"  In Engine but not TV ({len(eng_only)}):")
        for x in eng_only[:20]:
            print(f"    Eng: {x}  [{i_entry_times[x]}]")
    except FileNotFoundError:
        print("  TV CSV not found — skipping comparison")

    print()
    print("=" * 60)
    print(f"RESULT: baseline={len(baseline_trades)}  injected={len(injected_trades)}  TV=147")
    delta = len(injected_trades) - 147
    if delta == 0:
        print("  ✅ PERFECT MATCH — injection gives exactly 147 trades!")
    else:
        print(f"  {'↓' if delta < 0 else '↑'} diff={delta:+d} from TV target")


asyncio.run(main())
