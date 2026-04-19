"""Compare engine vs TV trades for RSI_L/S_7."""

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
    """Load TV z4.csv trades (cp1251 encoded, semicolon-separated)."""
    trades = []
    with open(TV_Z4_PATH, encoding="cp1251") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            keys = list(row.keys())
            if len(keys) < 5:
                continue
            try:
                ep_raw = row[keys[4]].replace(",", ".").strip()
                side_raw = row[keys[1]].strip().lower()
                entry_raw = row[keys[2]].strip()
                ep = float(ep_raw)
                # Russian: "покупка" = buy/long, "продажа" = sell/short
                side = "long" if "покупка" in side_raw or "buy" in side_raw else "short"
                trades.append({"ep": ep, "side": side, "entry": entry_raw})
            except (ValueError, KeyError, IndexError):
                pass
    return trades


async def main():
    graph = load_graph()
    svc = BacktestService()

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)

    # Fetch BTC with warmup (same logic as _run_rsi7.py)
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

    eng_trades = result.trades
    tv_trades = load_tv_trades()

    print(f"Eng: {len(eng_trades)}, TV: {len(tv_trades)}")

    # TV timestamps are UTC+3 (Moscow time). Convert to UTC by -3h.
    # Also TV has 2 rows per trade (Entry + Exit), load_tv_trades() returns all rows.
    # Filter to only Entry rows (side != exit) — actually load_tv_trades returns all rows
    # including exits, but eps and sides are for entry rows only.
    # The z4.csv format: each trade has an Entry row and Exit row.
    # load_tv_trades collects them all (294 rows for 147 trades).
    # For timestamp comparison, shift TV time by -3h.

    # Re-read z4.csv to get proper entry/exit timestamps
    tv_entries = []
    with open(TV_Z4_PATH, encoding="cp1251") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            keys = list(row.keys())
            if len(keys) < 5:
                continue
            try:
                type_raw = row[keys[0]].strip() if keys else ""
                ep_raw = row[keys[4]].replace(",", ".").strip()
                side_raw = row[keys[1]].strip().lower()
                entry_raw = row[keys[2]].strip()
                # Only process "Entry" rows (not "Exit")
                if "вход" not in type_raw.lower() and "entry" not in type_raw.lower() and type_raw != "Вход":
                    # Check the third column for type if first doesn't match
                    pass
                ep = float(ep_raw)
                side = "long" if "покупка" in side_raw or "buy" in side_raw else "short"
                # Parse TV timestamp (UTC+3) → UTC
                tv_ts = pd.to_datetime(entry_raw, dayfirst=False) - pd.Timedelta(hours=3)
                tv_entries.append({"ep": ep, "side": side, "ts": tv_ts, "raw_ts": entry_raw})
            except (ValueError, KeyError, IndexError):
                pass

    # Since z4.csv has Entry+Exit rows, filter to first half (entries)
    # Actually the cleanest: take every other row starting from 0 (entries)
    tv_entry_only = tv_entries[::2]  # every other row = entry rows
    print(f"TV entry rows (every other): {len(tv_entry_only)}")

    # Build sets for comparison
    tv_eps = {round(t["ep"], 2) for t in tv_entry_only}
    eng_eps = {round(t.entry_price, 2) for t in eng_trades}

    extra_in_eng = sorted(eng_eps - tv_eps)
    missing_in_eng = sorted(tv_eps - eng_eps)

    print(f"Entry prices in Eng but NOT in TV ({len(extra_in_eng)}): {extra_in_eng}")
    print(f"Entry prices in TV but NOT in Eng ({len(missing_in_eng)}): {missing_in_eng}")

    # Show extra engine trades with times
    print(
        f"\nExtra engine trades (in Eng but NOT in TV) — total count: {len([t for t in eng_trades if round(t.entry_price, 2) in set(extra_in_eng)])}"
    )
    for t in eng_trades:
        ep = round(t.entry_price, 2)
        if ep in set(extra_in_eng):
            entry_ts = pd.Timestamp(t.entry_time)
            exit_ts = pd.Timestamp(t.exit_time)
            print(
                f"  {t.direction:5s} {str(entry_ts)[:16]} -> {str(exit_ts)[:16]}  ep={t.entry_price:.2f}  pnl={t.pnl:.2f}"
            )

    print(f"\nMissing in engine (TV entry rows not matched, {len(missing_in_eng)}):")
    for tv in tv_entry_only:
        if round(tv["ep"], 2) in set(missing_in_eng):
            print(f"  {tv['side']:5s} entry={tv['raw_ts']}  ep={tv['ep']:.2f}")


asyncio.run(main())
