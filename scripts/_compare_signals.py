"""Compare signal counts: no intrabar vs 1m intrabar vs TV."""

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB_PATH = ROOT / "data.sqlite3"
STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"
START = pd.Timestamp("2025-01-01", tz="UTC")
END = pd.Timestamp("2026-02-24", tz="UTC")


async def main():
    svc = BacktestService()

    # Load strategy graph
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br) if isinstance(br, str) else (br or [])
    conns_ = json.loads(cr) if isinstance(cr, str) else (cr or [])
    gp = json.loads(gr) if isinstance(gr, str) else (gr or {})
    ms = gp.get("main_strategy", {})
    graph = {
        "name": name,
        "blocks": blocks,
        "connections": conns_,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if ms:
        graph["main_strategy"] = ms

    # Fetch data
    candles = await svc._fetch_historical_data(symbol="ETHUSDT", interval="30", start_date=START, end_date=END)
    btc_start = pd.Timestamp("2020-01-01", tz="UTC")
    btc_warmup = await svc._fetch_historical_data(symbol="BTCUSDT", interval="30", start_date=btc_start, end_date=START)
    btc_main = await svc._fetch_historical_data(symbol="BTCUSDT", interval="30", start_date=START, end_date=END)
    btc_candles = pd.concat([btc_warmup, btc_main]).sort_index()
    btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]

    btc_1m = await svc._fetch_historical_data(symbol="BTCUSDT", interval="1", start_date=START, end_date=END)
    btc_5m = await svc._fetch_historical_data(symbol="BTCUSDT", interval="5", start_date=START, end_date=END)
    print(f"BTC 1m: {len(btc_1m)} bars")
    print(f"BTC 5m: {len(btc_5m)} bars")

    # --- No intrabar ---
    adapter_none = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_candles, btcusdt_5m_ohlcv=None)
    sig_none = adapter_none.generate_signals(candles)
    le_none = sig_none.entries.values.astype(bool)
    se_none = (
        sig_none.short_entries.values.astype(bool)
        if sig_none.short_entries is not None
        else np.zeros(len(le_none), bool)
    )

    # --- 5m intrabar ---
    adapter_5m = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_candles, btcusdt_5m_ohlcv=btc_5m)
    sig_5m = adapter_5m.generate_signals(candles)
    le_5m = sig_5m.entries.values.astype(bool)
    se_5m = sig_5m.short_entries.values.astype(bool) if sig_5m.short_entries is not None else np.zeros(len(le_5m), bool)

    # --- 1m intrabar ---
    adapter_1m = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_candles, btcusdt_5m_ohlcv=btc_1m)
    sig_1m = adapter_1m.generate_signals(candles)
    le_1m = sig_1m.entries.values.astype(bool)
    se_1m = sig_1m.short_entries.values.astype(bool) if sig_1m.short_entries is not None else np.zeros(len(le_1m), bool)

    print()
    print(f"{'Mode':<20} {'long_entries':>12} {'short_entries':>14}")
    print("-" * 50)
    print(f"{'No intrabar':<20} {le_none.sum():>12} {se_none.sum():>14}")
    print(f"{'5m intrabar':<20} {le_5m.sum():>12} {se_5m.sum():>14}")
    print(f"{'1m intrabar':<20} {le_1m.sum():>12} {se_1m.sum():>14}")
    print(f"{'TV reference':<20} {'~29':>12} {'~121':>14}")

    # Extra signals
    extra_long_5m = (le_5m & ~le_none).sum()
    extra_short_5m = (se_5m & ~se_none).sum()
    extra_long_1m = (le_1m & ~le_none).sum()
    extra_short_1m = (se_1m & ~se_none).sum()

    print()
    print(f"Extra signals from 5m:  +{extra_long_5m} long, +{extra_short_5m} short")
    print(f"Extra signals from 1m:  +{extra_long_1m} long, +{extra_short_1m} short")

    # Show where extra 1m signals fire
    if extra_long_1m + extra_short_1m > 0:
        print()
        print("Extra 1m signal bars (first 20):")
        extra_mask = (le_1m & ~le_none) | (se_1m & ~se_none)
        extra_indices = candles.index[extra_mask]
        for idx in extra_indices[:20]:
            is_long = le_1m[candles.index.get_loc(idx)] and not le_none[candles.index.get_loc(idx)]
            is_short = se_1m[candles.index.get_loc(idx)] and not se_none[candles.index.get_loc(idx)]
            side = "LONG" if is_long else "SHORT"
            print(f"  {idx}  {side}")


asyncio.run(main())
