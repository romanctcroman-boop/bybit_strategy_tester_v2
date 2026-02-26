"""
Cascade test: block only the 07:30 Feb 12 signal and see if engine gives 147 trades.
Also tests blocking all 22 known extra signals.
Uses the exact API from _run_rsi7.py (FallbackEngineV4 + BacktestInput).
"""

import asyncio
import json
import os
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
TV_FILE = r"c:\Users\roman\Downloads\z4.csv"

EXTRA_ENTRIES = [
    "2025-02-12 07:30",
    "2025-02-15 00:00",
    "2025-02-17 13:00",
    "2025-02-18 04:30",
    "2025-02-19 18:00",
    "2025-03-30 05:30",
    "2025-03-31 12:00",
    "2025-04-20 02:00",
    "2025-05-11 20:30",
    "2025-05-13 07:30",
    "2025-05-19 01:30",
    "2025-06-22 07:00",
    "2025-06-24 19:00",
    "2025-07-03 04:30",
    "2025-07-04 23:00",
    "2025-07-11 18:00",
    "2025-07-13 09:30",
    "2025-07-24 09:30",
    "2025-08-16 01:00",
    "2025-08-27 02:30",
    "2025-09-02 11:00",
    "2025-11-25 00:00",
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


def load_tv_trades():
    """Load TV trades from z4.csv (row pairs: exit then entry, UTC+3 timestamps)."""
    import csv

    if not os.path.exists(TV_FILE):
        return None
    with open(TV_FILE, encoding="cp1251") as f:
        reader = csv.DictReader(f, delimiter=";")
        all_rows = list(reader)
    if not all_rows:
        return None
    keys = list(all_rows[0].keys())
    records = []
    for i in range(0, len(all_rows) - 1, 2):
        exit_row = all_rows[i]
        entry_row = all_rows[i + 1]
        try:
            ep = float(entry_row[keys[4]].replace(",", ".").strip())
            side_raw = entry_row[keys[1]].strip().lower()
            side = "long" if "long" in side_raw or "покупка" in side_raw else "short"
            entry_ts = pd.to_datetime(entry_row[keys[2]].strip()) - pd.Timedelta(hours=3)
            exit_ts = pd.to_datetime(exit_row[keys[2]].strip()) - pd.Timedelta(hours=3)
            records.append({"direction": side, "entry_utc": entry_ts, "exit_utc": exit_ts, "entry_price": ep})
        except (ValueError, KeyError, IndexError):
            pass
    df = pd.DataFrame(records)
    df["entry_utc"] = pd.to_datetime(df["entry_utc"], utc=True)
    return df.sort_values("entry_utc").reset_index(drop=True)


def compare_trades(engine_trades, tv_df, label):
    PRICE_TOL = 0.005
    TIME_TOL = pd.Timedelta(hours=1)

    def to_ts(t):
        ts = pd.Timestamp(t)
        return ts.tz_localize("UTC") if ts.tzinfo is None else ts

    ev = sorted(
        [{"dir": t.direction, "time": to_ts(t.entry_time), "ep": t.entry_price} for t in engine_trades],
        key=lambda x: x["time"],
    )
    tv_v = (
        tv_df[["direction", "entry_utc", "entry_price"]]
        .rename(columns={"entry_utc": "time", "entry_price": "ep"})
        .to_dict("records")
    )

    tv_used = [False] * len(tv_v)
    matched, extra_e = 0, []
    for e in ev:
        found = False
        for j, tv in enumerate(tv_v):
            if tv_used[j]:
                continue
            if (
                tv["direction"] == e["dir"]
                and abs(e["time"] - tv["time"]) <= TIME_TOL
                and abs(e["ep"] - tv["ep"]) / tv["ep"] < PRICE_TOL
            ):
                tv_used[j] = True
                matched += 1
                found = True
                break
        if not found:
            extra_e.append(e)

    missing_tv = [tv for j, tv in enumerate(tv_v) if not tv_used[j]]

    print(f"\n[{label}]  engine={len(ev)}  matched={matched}  extra={len(extra_e)}  missing={len(missing_tv)}")
    if extra_e:
        print("  Extra engine:")
        for e in extra_e:
            print(f"    {e['dir'][:5]}  {str(e['time'])[:16]}  ep={e['ep']:.2f}")
    if missing_tv:
        print("  Missing TV:")
        for tv in missing_tv:
            print(f"    {tv['direction'][:5]}  {str(tv['time'])[:16]}  ep={tv['ep']:.2f}")
    return matched, extra_e, missing_tv


async def run_engine(candles, le, se, lx=None, sx=None):
    n = len(candles)
    le_a = np.asarray(le, dtype=bool)
    se_a = np.asarray(se, dtype=bool)
    lx_a = np.zeros(n, dtype=bool) if lx is None else np.asarray(lx, dtype=bool)
    sx_a = np.zeros(n, dtype=bool) if sx is None else np.asarray(sx, dtype=bool)
    result = FallbackEngineV4().run(
        BacktestInput(
            candles=candles,
            long_entries=le_a,
            long_exits=lx_a,
            short_entries=se_a,
            short_exits=sx_a,
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
    return result.trades


async def main():
    graph = load_graph()
    tv_df = load_tv_trades()
    if tv_df is None:
        print(f"ERROR: TV file not found at {TV_FILE}")
        return
    print(f"TV trades: {len(tv_df)}")

    svc = BacktestService()

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    print(f"ETH candles: {len(candles)}")

    WARMUP_BARS = 500
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc_warmup = None
    try:
        raw = await svc.adapter.get_historical_klines(
            symbol="BTCUSDT",
            interval="30",
            start_time=int(btc_start.timestamp() * 1000),
            end_time=int(START_DATE.timestamp() * 1000),
            market_type="linear",
        )
        if raw:
            dfw = pd.DataFrame(raw)
            col_map = {
                "startTime": "timestamp",
                "open_time": "timestamp",
                "openPrice": "open",
                "highPrice": "high",
                "lowPrice": "low",
                "closePrice": "close",
            }
            for old, new in col_map.items():
                if old in dfw.columns and new not in dfw.columns:
                    dfw = dfw.rename(columns={old: new})
            for col in ["open", "high", "low", "close", "volume"]:
                if col in dfw.columns:
                    dfw[col] = pd.to_numeric(dfw[col], errors="coerce")
            if "timestamp" in dfw.columns:
                dfw["timestamp"] = (
                    pd.to_datetime(dfw["timestamp"], unit="ms", utc=True)
                    if dfw["timestamp"].dtype in ["int64", "float64"]
                    else pd.to_datetime(dfw["timestamp"], utc=True)
                )
                dfw = dfw.set_index("timestamp").sort_index()
            btc_warmup = dfw
            print(f"BTC warmup: {len(dfw)} bars")
    except Exception as e:
        print(f"WARNING: warmup failed: {e}")

    if btc_warmup is not None and len(btc_warmup) > 0:
        if btc_main.index.tz is None:
            btc_main.index = btc_main.index.tz_localize("UTC")
        if btc_warmup.index.tz is None:
            btc_warmup.index = btc_warmup.index.tz_localize("UTC")
        btc_candles = pd.concat([btc_warmup, btc_main]).sort_index()
        btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]
    else:
        btc_candles = btc_main
    print(f"BTC total: {len(btc_candles)} bars")

    # Signals
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_candles)
    signals = adapter.generate_signals(candles)
    le_arr = np.asarray(signals.entries.values, dtype=bool)
    se_arr = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(le_arr), dtype=bool)
    )
    lx_arr = (
        np.asarray(signals.exits.values, dtype=bool) if signals.exits is not None else np.zeros(len(le_arr), dtype=bool)
    )
    sx_arr = (
        np.asarray(signals.short_exits.values, dtype=bool)
        if signals.short_exits is not None
        else np.zeros(len(le_arr), dtype=bool)
    )
    print(f"Signals: {le_arr.sum()} long, {se_arr.sum()} short")

    # RUN 1: Baseline
    trades1 = await run_engine(candles, le_arr, se_arr, lx_arr, sx_arr)
    compare_trades(trades1, tv_df, "BASELINE")

    # RUN 2: Block only 2025-02-12 07:30
    se2 = se_arr.copy()
    TARGET = pd.Timestamp("2025-02-12 07:30")  # tz-naive to match candles index
    if TARGET in candles.index:
        idx = candles.index.get_loc(TARGET)
        se2[idx] = False
        print(f"\nBlocked signal at {TARGET} (candle idx={idx})")
    else:
        # Try tz-aware fallback
        TARGET_UTC = pd.Timestamp("2025-02-12 07:30", tz="UTC")
        if TARGET_UTC in candles.index:
            idx = candles.index.get_loc(TARGET_UTC)
            se2[idx] = False
            print(f"\nBlocked signal at {TARGET_UTC} (candle idx={idx})")
        else:
            print(f"\nWARN: {TARGET} not in candles index (tz={candles.index.tz})")
            print(f"  Nearby: {candles.index[candles.index.get_indexer([TARGET], method='nearest')[0]]}")

    trades2 = await run_engine(candles, le_arr, se2, lx_arr, sx_arr)
    compare_trades(trades2, tv_df, "BLOCKED_0730_ONLY")

    # RUN 3: Block all 22 known extras
    se3 = se_arr.copy()
    blocked = 0
    for ts_str in EXTRA_ENTRIES:
        # Try tz-naive first (matches candle index), then tz-aware
        for ts in [pd.Timestamp(ts_str), pd.Timestamp(ts_str, tz="UTC")]:
            if ts in candles.index:
                se3[candles.index.get_loc(ts)] = False
                blocked += 1
                break
    print(f"\nBlocked {blocked}/{len(EXTRA_ENTRIES)} signals")
    trades3 = await run_engine(candles, le_arr, se3, lx_arr, sx_arr)
    compare_trades(trades3, tv_df, "BLOCKED_ALL_22")

    # Summary
    print("\n" + "=" * 60)
    print(f"TV:          {len(tv_df)} trades")
    print(f"Baseline:    {len(trades1)} trades  (diff={len(trades1) - len(tv_df):+d})")
    print(f"Blocked-1:   {len(trades2)} trades  (diff={len(trades2) - len(tv_df):+d})")
    print(f"Blocked-all: {len(trades3)} trades  (diff={len(trades3) - len(tv_df):+d})")


asyncio.run(main())
