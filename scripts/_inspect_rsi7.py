"""Inspect Strategy_RSI_L/S_7 blocks and run engine vs TV comparison."""

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
TV_CSV = r"c:\Users\roman\Downloads\z4.csv"

START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")

# ── params from z5.csv ──────────────────────────────────────────────────────
# ETHUSDT, 30m, TP=2.3%, SL=13.2%, leverage=10, position=100 USDT (fixed)
# commission=0.07%, slippage=0
TV_PARAMS = dict(
    symbol="ETHUSDT",
    interval="30",
    tp=0.023,
    sl=0.132,
    leverage=10,
    fixed_amount=100.0,
    taker_fee=0.0007,
    slippage=0.0,
    initial_capital=10_000.0,  # our test capital (TV uses 1M but trades are fixed 100 USDT)
)


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

    print(f"\n=== Strategy: {name} ===")
    print(f"  Blocks ({len(blocks)}):")
    for b in blocks:
        btype = b.get("type", "?")
        params = b.get("params", {})
        print(f"    [{btype}] {params}")

    graph = {
        "name": name,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if gp and gp.get("main_strategy"):
        graph["main_strategy"] = gp["main_strategy"]
        print(f"  main_strategy: {gp['main_strategy']}")
    return graph


def load_tv_trades():
    """Load TV reference trades from z4.csv."""
    rows = list(csv.DictReader(open(TV_CSV, encoding="utf-8-sig"), delimiter=";"))
    entries = [r for r in rows if "Entry" in r["Тип"]]
    exits = [r for r in rows if "Exit" in r["Тип"]]
    print(f"\n=== TV Reference: {len(exits)} trades ===")
    for i, (en, ex) in enumerate(zip(entries[:5], exits[:5])):
        print(
            f"  #{i + 1} {en['Тип']} {en['Дата и время']} → {ex['Дата и время']} "
            f"pnl={ex['Чистая прибыль / убыток USDT']} signal={en['Сигнал']}"
        )
    if len(exits) > 5:
        print(f"  ... ({len(exits)} total)")
    return entries, exits


async def main():
    entries, exits = load_tv_trades()
    graph = load_graph()

    # Fetch candles
    print(f"\nFetching ETHUSDT 30m candles {START_DATE} → {END_DATE} ...")
    svc = BacktestService()
    candles = await svc._fetch_historical_data(
        symbol=TV_PARAMS["symbol"],
        interval=TV_PARAMS["interval"],
        start_date=START_DATE,
        end_date=END_DATE,
    )
    print(f"  {len(candles)} bars")

    # Generate signals
    signals = StrategyBuilderAdapter(graph).generate_signals(candles)
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

    print(f"  Long entries: {le.sum()}, Short entries: {se.sum()}")
    print(f"  Long exits: {lx.sum()}, Short exits: {sx.sum()}")

    # Run engine
    result = FallbackEngineV4().run(
        BacktestInput(
            candles=candles,
            long_entries=le,
            long_exits=lx,
            short_entries=se,
            short_exits=sx,
            initial_capital=TV_PARAMS["initial_capital"],
            position_size=0.10,
            use_fixed_amount=True,
            fixed_amount=TV_PARAMS["fixed_amount"],
            leverage=TV_PARAMS["leverage"],
            stop_loss=TV_PARAMS["sl"],
            take_profit=TV_PARAMS["tp"],
            taker_fee=TV_PARAMS["taker_fee"],
            slippage=TV_PARAMS["slippage"],
            direction=TradeDirection.BOTH,
            pyramiding=1,
            interval=TV_PARAMS["interval"],
        )
    )

    trades = result.trades
    print(f"\n=== Engine: {len(trades)} trades ===")
    for t in trades[:5]:
        print(
            f"  {t.direction} {t.entry_time} → {t.exit_time} "
            f"ep={t.entry_price:.2f} xp={t.exit_price:.4f} pnl={t.pnl:.4f} reason={t.exit_reason}"
        )

    # Quick count comparison
    print(f"\n{'=' * 60}")
    print(f"TV trades:     {len(exits)}")
    print(f"Engine trades: {len(trades)}")
    print(f"Diff:          {len(exits) - len(trades)}")

    # Compare first few by date
    UTC3 = pd.Timedelta(hours=3)
    print("\nFirst 10 TV entry times (UTC):")
    for en in entries[:10]:
        dt = pd.Timestamp(en["Дата и время"].strip()) - UTC3
        print(f"  {dt}  {en['Тип']}  signal={en['Сигнал']}")

    print("\nFirst 10 Engine entry times:")
    for t in trades[:10]:
        print(f"  {t.entry_time}  {t.direction}  reason={t.exit_reason}")


asyncio.run(main())
