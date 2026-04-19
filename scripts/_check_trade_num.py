"""Quick check: how many trades does the engine produce, and what are trades around Root #144 (TV numbering)?"""

import asyncio
import json
import sqlite3
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter


async def main():
    svc = BacktestService()
    conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?",
        ("dd2969a2-bbba-410e-b190-be1e8cc50b21",),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    graph = {
        "name": name,
        "blocks": json.loads(br),
        "connections": json.loads(cr),
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    ms = json.loads(gr).get("main_strategy", {})
    if ms:
        graph["main_strategy"] = ms

    candles = await svc._fetch_historical_data(
        "ETHUSDT", "30", pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2026-02-24", tz="UTC")
    )
    btc = await svc._fetch_historical_data(
        "BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), pd.Timestamp("2026-02-24", tz="UTC")
    )
    btc = btc[~btc.index.duplicated(keep="last")]

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)
    le = np.asarray(signals.entries.values, dtype=bool)
    lx = np.asarray(signals.exits.values, dtype=bool)
    se = np.asarray(signals.short_entries.values, dtype=bool)
    sx = np.asarray(signals.short_exits.values, dtype=bool)

    engine = FallbackEngineV4()
    result = engine.run(
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
    trades = result.trades
    print(f"Total trades: {len(trades)}")
    print(f"Candles: {len(candles)} from {candles.index[0]} to {candles.index[-1]}")
    print()

    # Find the trade that enters around 2026-02-07 16:00-16:30
    target = pd.Timestamp("2026-02-07 16:00")
    for i, t in enumerate(trades):
        entry_ts = pd.Timestamp(t.entry_time)
        if entry_ts.tz_localize(None) if entry_ts.tzinfo else entry_ts >= target:
            if i > 0:
                tp = trades[i - 1]
                print(
                    f"Trade #{i}: {tp.direction:5s} entry={str(tp.entry_time)[:19]} exit={str(tp.exit_time)[:19]} reason={tp.exit_reason}"
                )
            print(
                f"Trade #{i + 1}: {t.direction:5s} entry={str(t.entry_time)[:19]} exit={str(t.exit_time)[:19]} reason={t.exit_reason}"
            )
            if i + 1 < len(trades):
                tn = trades[i + 1]
                print(
                    f"Trade #{i + 2}: {tn.direction:5s} entry={str(tn.entry_time)[:19]} exit={str(tn.exit_time)[:19]} reason={tn.exit_reason}"
                )
            break

    # Also find trade entering at 2026-02-07 16:30 specifically
    print()
    print("Looking for entry at 2026-02-07 16:30...")
    target2 = pd.Timestamp("2026-02-07 16:30")
    for i, t in enumerate(trades):
        entry_ts = (
            pd.Timestamp(t.entry_time).tz_localize(None)
            if pd.Timestamp(t.entry_time).tzinfo
            else pd.Timestamp(t.entry_time)
        )
        if abs((entry_ts - target2).total_seconds()) < 60:
            print(
                f"  FOUND: Trade #{i + 1}: {t.direction} entry={t.entry_time} exit={t.exit_time} reason={t.exit_reason}"
            )

    # Root #144 in TV = trade #144 in TV (1-indexed)
    # TV trade #144: short, entry 2026-02-08 03:30 (UTC)
    # The root divergence is: TV enters at 03:30, engine enters EARLIER

    # Let's also check trades around Root #9 (TV trade #9)
    print()
    print("Trades around Root #9 area (2025-01-28):")
    target9 = pd.Timestamp("2025-01-28")
    for i, t in enumerate(trades):
        entry_ts = (
            pd.Timestamp(t.entry_time).tz_localize(None)
            if pd.Timestamp(t.entry_time).tzinfo
            else pd.Timestamp(t.entry_time)
        )
        if entry_ts.date() == target9.date():
            print(
                f"  Trade #{i + 1}: {t.direction:5s} entry={str(t.entry_time)[:19]} exit={str(t.exit_time)[:19]} reason={t.exit_reason}"
            )


asyncio.run(main())
