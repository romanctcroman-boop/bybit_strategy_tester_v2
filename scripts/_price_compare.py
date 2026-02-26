"""
Compare engine vs TV trades by entry price (tolerance 0.02).
This avoids timestamp offset issues from bar-open vs bar-close timing.
"""

import asyncio
import csv
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
TV_Z4_PATH = r"c:\Users\roman\Downloads\z4.csv"
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
    blocks = json.loads(br)
    conns = json.loads(cr)
    gp = json.loads(gr)
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
        except Exception:
            pass
    return trades


async def run_engine():
    graph = load_graph()
    svc = BacktestService()
    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)

    WARMUP_BARS = 500
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    warmup_start_ts = int(btc_start.timestamp() * 1000)
    warmup_end_ts = int(START_DATE.timestamp() * 1000)
    raw_warmup = await svc.adapter.get_historical_klines(
        "BTCUSDT", "30", warmup_start_ts, warmup_end_ts, market_type="linear"
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
        if btc_main.index.tz is None:
            btc_main.index = btc_main.index.tz_localize("UTC")
        if df_w.index.tz is None:
            df_w.index = df_w.index.tz_localize("UTC")
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
    trades, candles = await run_engine()
    tv = load_tv_trades()

    # Match by entry price (tolerance 0.02 USDT)
    tv_matched: set[int] = set()
    eng_matched: set[int] = set()
    pairs: list[tuple] = []

    PRICE_TOL = 0.02

    for i, t in enumerate(trades):
        for j, tvt in enumerate(tv):
            if j in tv_matched:
                continue
            if tvt["side"] == t.direction and abs(tvt["ep"] - t.entry_price) <= PRICE_TOL:
                tv_matched.add(j)
                eng_matched.add(i)
                pairs.append(
                    (
                        i,
                        j,
                        t.direction,
                        t.entry_time,
                        tvt["entry_ts"],
                        t.exit_time,
                        tvt["exit_ts"],
                        t.entry_price,
                        tvt["ep"],
                        t.exit_price,
                        tvt["xp"],
                    )
                )
                break

    eng_extra = [(i, t) for i, t in enumerate(trades) if i not in eng_matched]
    tv_miss = [(j, t) for j, t in enumerate(tv) if j not in tv_matched]

    print(f"Engine: {len(trades)} trades, TV: {len(tv)} trades")
    print(f"Matched by price (tol={PRICE_TOL}): {len(pairs)}")
    print(f"Extra engine (no TV match): {len(eng_extra)}")
    print(f"Missing TV (no engine match): {len(tv_miss)}")
    print()

    # Show entry time diffs for matched
    time_diffs = []
    for _, _, side, et, tvt_ts, xt, tvx_ts, ep, tvep, xp, tvxp in pairs:
        et_naive = et.replace(tzinfo=None) if hasattr(et, "tz") and et.tz else et
        tvt_naive = tvt_ts.replace(tzinfo=None) if hasattr(tvt_ts, "tz") and tvt_ts.tz else tvt_ts
        diff = (et_naive - tvt_naive).total_seconds() / 60
        time_diffs.append(diff)

    import statistics

    if time_diffs:
        print(f"Entry time diff stats (engine - TV, minutes):")
        print(
            f"  min={min(time_diffs):.0f}  max={max(time_diffs):.0f}  mean={statistics.mean(time_diffs):.1f}  median={statistics.median(time_diffs):.0f}"
        )
        from collections import Counter

        cnt = Counter(int(d) for d in time_diffs)
        for diff_val, count in sorted(cnt.items()):
            print(f"  {diff_val:+4d} min: {count} trades")
    print()

    # Show exit time diffs
    exit_diffs = []
    for _, _, side, et, tvt_ts, xt, tvx_ts, ep, tvep, xp, tvxp in pairs:
        xt_naive = xt.replace(tzinfo=None) if hasattr(xt, "tz") and xt.tz else xt
        tvx_naive = tvx_ts.replace(tzinfo=None) if hasattr(tvx_ts, "tz") and tvx_ts.tz else tvx_ts
        diff = (xt_naive - tvx_naive).total_seconds() / 60
        exit_diffs.append(diff)

    if exit_diffs:
        print(f"Exit time diff stats (engine - TV, minutes):")
        from collections import Counter

        cnt = Counter(int(d) for d in exit_diffs)
        for diff_val, count in sorted(cnt.items()):
            print(f"  {diff_val:+4d} min: {count} trades")
    print()

    print("=== EXTRA ENGINE TRADES (no price match in TV) ===")
    for i, t in eng_extra[:15]:
        print(
            f"  {t.direction:5s} {str(t.entry_time)[:16]} ep={t.entry_price:.2f}  "
            f"xp={t.exit_price:.2f}  {t.exit_reason}"
        )

    print()
    print("=== MISSING TV TRADES (no price match in engine) ===")
    for j, tvt in tv_miss[:15]:
        print(f"  {tvt['side']:5s} {tvt['entry_ts']}  ep={tvt['ep']:.2f}  xp={tvt['xp']:.2f}")


asyncio.run(main())
