"""Quick check: what are the first few engine trade entry times?
If entry_on_next_bar_open=True and signal at bar 26 (13:00),
entry should be at bar 27 (13:30), using open of bar 27.
"""

import asyncio
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
os.chdir(r"d:\bybit_strategy_tester_v2")

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")


async def main():
    svc = BacktestService()

    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?",
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

    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    btc_warmup = await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="30",
        start_date=pd.Timestamp("2020-01-01", tz="UTC"),
        end_date=START_DATE,
    )
    btc_main = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
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
            initial_capital=1_000_000.0,
            position_size=0.001,
            use_fixed_amount=False,
            leverage=1,
            stop_loss=0.132,
            take_profit=0.023,
            taker_fee=0.0007,
            slippage=0.0,
            direction=TradeDirection.BOTH,
            pyramiding=1,
            interval="30",
            entry_on_next_bar_open=True,
        )
    )

    times = candles.index
    if times.tz is not None:
        times = times.tz_localize(None)

    print(f"Total trades: {len(result.trades)}")
    print()
    print("First 25 engine trades — entry time vs signal bar:")
    print(
        f"{'#':>4}  {'Dir':5s}  {'EntryTime':20s}  {'EntryPrice':>12}  {'SE[entry]':>9}  {'SE[entry-1]':>11}  {'Bar idx':>8}"
    )

    for idx, t in enumerate(result.trades[:25], 1):
        entry_str = str(t.entry_time)[:19]
        entry_ts = pd.Timestamp(entry_str)

        # Find bar index
        pos = np.where(times == entry_ts)[0]
        if len(pos) > 0:
            bi = pos[0]
            se_at = se[bi]
            se_prev = se[bi - 1] if bi > 0 else False
        else:
            bi = -1
            se_at = "?"
            se_prev = "?"

        dir_str = "SHORT" if "short" in str(t.direction).lower() else "LONG"
        print(
            f"  {idx:3d}  {dir_str:5s}  {entry_str:20s}  {t.entry_price:12.2f}  {str(se_at):>9}  {str(se_prev):>11}  {bi:>8}"
        )

    # Also check: does entry price match bar's open or close?
    print()
    print("Price verification (first 10 trades):")
    print(f"{'#':>4}  {'EntryPrice':>12}  {'Bar Open':>12}  {'Bar Close':>12}  {'Prev Close':>12}  {'Match':>8}")
    for idx, t in enumerate(result.trades[:10], 1):
        entry_str = str(t.entry_time)[:19]
        entry_ts = pd.Timestamp(entry_str)
        pos = np.where(times == entry_ts)[0]
        if len(pos) > 0:
            bi = pos[0]
            bar_open = candles.iloc[bi]["open"]
            bar_close = candles.iloc[bi]["close"]
            prev_close = candles.iloc[bi - 1]["close"] if bi > 0 else 0
            match = (
                "OPEN"
                if abs(t.entry_price - bar_open) < 0.01
                else ("CLOSE" if abs(t.entry_price - bar_close) < 0.01 else "OTHER")
            )
            print(
                f"  {idx:3d}  {t.entry_price:12.2f}  {bar_open:12.2f}  {bar_close:12.2f}  {prev_close:12.2f}  {match:>8}"
            )


asyncio.run(main())
