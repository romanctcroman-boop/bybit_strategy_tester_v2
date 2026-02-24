"""
Find the 5 extra trades in engine vs TV for RSI_L/S_7.
TV z4.csv: Exit row first, then Entry row for each trade number.
TV timestamps are UTC+3 (subtract 3h for UTC).
Engine has 151 trades, TV has 146.
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
    """
    Load TV z4.csv trades.
    Format: row pairs (Exit, Entry) per trade. Timestamps UTC+3.
    Returns list of dicts with: ep, exit_price, side, entry_ts, exit_ts (all UTC).
    """
    trades = []
    with open(TV_Z4_PATH, encoding="cp1251") as f:
        reader = csv.DictReader(f, delimiter=";")
        all_rows = list(reader)

    keys = list(all_rows[0].keys())
    # Pattern: Exit row first, then Entry row
    for i in range(0, len(all_rows) - 1, 2):
        exit_row = all_rows[i]
        entry_row = all_rows[i + 1]
        try:
            ep = float(entry_row[keys[4]].replace(",", ".").strip())
            xp = float(exit_row[keys[4]].replace(",", ".").strip())
            side_raw = entry_row[keys[1]].strip().lower()
            side = "long" if "long" in side_raw or "покупка" in side_raw else "short"
            entry_ts_raw = entry_row[keys[2]].strip()
            exit_ts_raw = exit_row[keys[2]].strip()
            # TV timestamps are UTC+3 → subtract 3h for UTC
            entry_ts = pd.to_datetime(entry_ts_raw) - pd.Timedelta(hours=3)
            exit_ts = pd.to_datetime(exit_ts_raw) - pd.Timedelta(hours=3)
            trades.append(
                {
                    "ep": ep,
                    "xp": xp,
                    "side": side,
                    "entry_ts": entry_ts,
                    "exit_ts": exit_ts,
                }
            )
        except (ValueError, KeyError, IndexError):
            pass
    return trades


async def run_engine():
    graph = load_graph()
    svc = BacktestService()

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)

    # Fetch BTC with 500-bar warmup
    WARMUP_BARS = 500
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
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms", utc=True)
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
    return result.trades


async def main():
    eng_trades = await run_engine()
    tv_trades = load_tv_trades()

    print(f"Engine: {len(eng_trades)} trades")
    print(f"TV:     {len(tv_trades)} trades  (from z4.csv, entry rows)")
    print(f"Diff:   {len(eng_trades) - len(tv_trades)}")
    print()

    # Build TV entry price set (rounded to 2 dp)
    tv_ep_set = {round(t["ep"], 2) for t in tv_trades}
    # Build TV (ep, side) set
    tv_pair_set = {(round(t["ep"], 2), t["side"]) for t in tv_trades}

    # Find extra engine trades: not matched to any TV trade by (ep, side)
    extra = []
    matched = []
    for t in eng_trades:
        key = (round(t.entry_price, 2), t.direction)
        if key in tv_pair_set:
            matched.append(t)
        else:
            extra.append(t)

    print(f"Engine trades matched to TV by (ep, side): {len(matched)}")
    print(f"Engine trades with no TV match (extra):    {len(extra)}")
    print()

    # Show the extra trades
    print("=== EXTRA ENGINE TRADES (not in TV by entry_price+side) ===")
    for t in extra:
        entry_ts = pd.Timestamp(t.entry_time)
        exit_ts = pd.Timestamp(t.exit_time)
        print(
            f"  {t.direction:5s} {str(entry_ts)[:16]} -> {str(exit_ts)[:16]}  ep={t.entry_price:.2f}  pnl={t.pnl:.2f}"
        )

    print()
    # Show TV trades not in engine
    eng_pair_set = {(round(t.entry_price, 2), t.direction) for t in eng_trades}
    missing = [t for t in tv_trades if (round(t["ep"], 2), t["side"]) not in eng_pair_set]
    print(f"=== MISSING TV TRADES (in TV but not in Engine) === ({len(missing)})")
    for t in missing:
        print(f"  {t['side']:5s} entry={t['entry_ts']}  ep={t['ep']:.2f}  exit={t['exit_ts']}")


asyncio.run(main())
