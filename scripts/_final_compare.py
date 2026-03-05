"""
Final trade comparison for RSI_L/S_7: match by timestamp proximity (±30 min).
This correctly identifies which engine trades correspond to TV trades.
"""

import asyncio
import csv
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
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
TV_Z4_PATH = r"c:\Users\roman\Downloads\z4.csv"
WARMUP_BARS = 500


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
    return {
        "name": name,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
        **({"main_strategy": ms} if ms else {}),
    }


def load_tv_trades():
    """Load TV trades from z4.csv. Row pairs: (Exit, Entry). Timestamps UTC+3."""
    trades = []
    with open(TV_Z4_PATH, encoding="cp1251") as f:
        reader = csv.DictReader(f, delimiter=";")
        all_rows = list(reader)
    keys = list(all_rows[0].keys())
    for i in range(0, len(all_rows) - 1, 2):
        exit_row = all_rows[i]
        entry_row = all_rows[i + 1]
        try:
            ep = float(entry_row[keys[4]].replace(",", ".").strip())
            xp = float(exit_row[keys[4]].replace(",", ".").strip())
            side_raw = entry_row[keys[1]].strip().lower()
            side = "long" if "long" in side_raw or "покупка" in side_raw else "short"
            entry_ts = pd.to_datetime(entry_row[keys[2]].strip()) - pd.Timedelta(hours=3)
            exit_ts = pd.to_datetime(exit_row[keys[2]].strip()) - pd.Timedelta(hours=3)
            trades.append({"ep": ep, "xp": xp, "side": side, "entry_ts": entry_ts, "exit_ts": exit_ts})
        except (ValueError, KeyError, IndexError):
            pass
    return trades


async def run_engine():
    graph = load_graph()
    svc = BacktestService()
    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    warmup_ts_start = int(btc_start.timestamp() * 1000)
    warmup_ts_end = int(START_DATE.timestamp() * 1000)
    raw_warmup = await svc.adapter.get_historical_klines(
        "BTCUSDT", "30", warmup_ts_start, warmup_ts_end, market_type="linear"
    )
    if raw_warmup:
        df_w = pd.DataFrame(raw_warmup)
        for old, new in {
            "startTime": "timestamp",
            "open_time": "timestamp",
            "openPrice": "open",
            "highPrice": "high",
            "lowPrice": "low",
            "closePrice": "close",
        }.items():
            if old in df_w.columns and new not in df_w.columns:
                df_w = df_w.rename(columns={old: new})
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df_w.columns:
                df_w[col] = pd.to_numeric(df_w[col], errors="coerce")
        if df_w["timestamp"].dtype in ["int64", "float64"]:
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms")
        df_w = df_w.set_index("timestamp").sort_index()
        if btc_main.index.tz is None:
            df_w.index = df_w.index.tz_localize(None)
        btc_candles = pd.concat([df_w, btc_main]).sort_index()
        btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]
    else:
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
    return result.trades, candles


async def main():
    eng_trades, candles = await run_engine()
    tv_trades = load_tv_trades()
    print(f"Engine: {len(eng_trades)} trades")
    print(f"TV:     {len(tv_trades)} trades")
    print(f"Diff:   {len(eng_trades) - len(tv_trades)}")
    print()

    # Match each engine trade to the closest TV trade by (entry_ts, side)
    TOLERANCE = pd.Timedelta(minutes=30)  # ±1 bar
    tv_unmatched = list(range(len(tv_trades)))
    eng_unmatched = []
    eng_matched = []

    for et in eng_trades:
        et_ts = pd.Timestamp(et.entry_time)
        best_idx = None
        best_diff = TOLERANCE + pd.Timedelta(minutes=1)
        for i in tv_unmatched:
            tv = tv_trades[i]
            if tv["side"] != et.direction:
                continue
            diff = abs(et_ts - tv["entry_ts"])
            if diff <= TOLERANCE and diff < best_diff:
                best_diff = diff
                best_idx = i
        if best_idx is not None:
            tv_unmatched.remove(best_idx)
            eng_matched.append((et, tv_trades[best_idx], best_diff))
        else:
            eng_unmatched.append(et)

    tv_unmatched_trades = [tv_trades[i] for i in tv_unmatched]

    print(f"Engine matched to TV:  {len(eng_matched)}")
    print(f"Engine unmatched (extra): {len(eng_unmatched)}")
    print(f"TV unmatched (missing):   {len(tv_unmatched_trades)}")
    print()

    # Entry price accuracy on matched trades
    ep_diffs = [abs(em[0].entry_price - em[1]["ep"]) for em in eng_matched]
    print(f"Matched trades entry price diff: max={max(ep_diffs):.2f}  mean={sum(ep_diffs) / len(ep_diffs):.2f}")
    print()

    print("=== EXTRA ENGINE TRADES (no TV match within ±30min) ===")
    for et in eng_unmatched:
        ts = pd.Timestamp(et.entry_time)
        xt = pd.Timestamp(et.exit_time)
        print(f"  {et.direction:5s} {str(ts)[:16]} -> {str(xt)[:16]}  ep={et.entry_price:.2f}")

    print()
    print("=== MISSING TV TRADES (no engine match within ±30min) ===")
    for tv in tv_unmatched_trades:
        print(f"  {tv['side']:5s} entry={str(tv['entry_ts'])[:16]}  ep={tv['ep']:.2f}  exit={str(tv['exit_ts'])[:16]}")

    # Matched trades with large time offset (>0)
    print()
    print("=== MATCHED TRADES WITH TIMING OFFSET > 0 ===")
    offsets = [(em[2], em[0], em[1]) for em in eng_matched if em[2] > pd.Timedelta(0)]
    offsets.sort(key=lambda x: -x[0].total_seconds())
    for diff, et, tv in offsets[:15]:
        et_ts = pd.Timestamp(et.entry_time)
        print(
            f"  {et.direction:5s} Eng={str(et_ts)[:16]}  TV={str(tv['entry_ts'])[:16]}  offset={diff}  "
            f"ep_eng={et.entry_price:.2f}  ep_tv={tv['ep']:.2f}"
        )


asyncio.run(main())
