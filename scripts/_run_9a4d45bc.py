"""
Run strategy 9a4d45bc with canonical params (commission=0.0007, slippage=0)
and compare total trade count vs UI result (102 closed trades).
"""

import asyncio
import json
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "9a4d45bc-0f41-484e-bfee-40a15011c729"


def load_strategy_graph() -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cursor.fetchone()
    col_names = [d[0] for d in cursor.description]
    conn.close()
    strat = dict(zip(col_names, row, strict=True))
    blocks = (
        json.loads(strat["builder_blocks"]) if isinstance(strat["builder_blocks"], str) else strat["builder_blocks"]
    )
    conns = (
        json.loads(strat["builder_connections"])
        if isinstance(strat["builder_connections"], str)
        else strat["builder_connections"]
    )
    graph_raw = (
        json.loads(strat["builder_graph"]) if isinstance(strat["builder_graph"], str) else strat["builder_graph"]
    )
    graph = {
        "name": strat["name"],
        "description": strat.get("description") or "",
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if graph_raw and isinstance(graph_raw, dict) and graph_raw.get("main_strategy"):
        graph["main_strategy"] = graph_raw["main_strategy"]
    return graph


async def fetch_candles():
    svc = BacktestService()
    return await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="30",
        start_date=pd.Timestamp("2025-01-01", tz="UTC"),
        end_date=pd.Timestamp("2026-02-24", tz="UTC"),
    )


def main():
    candles = asyncio.run(fetch_candles())
    print(f"Candles: {len(candles)} bars  {candles.index[0]} .. {candles.index[-1]}")

    adapter = StrategyBuilderAdapter(load_strategy_graph())
    signals = adapter.generate_signals(candles)

    long_entries = np.asarray(signals.entries.values, dtype=bool)
    short_entries = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(long_entries), dtype=bool)
    )
    long_exits = (
        np.asarray(signals.exits.values, dtype=bool)
        if signals.exits is not None
        else np.zeros(len(long_entries), dtype=bool)
    )
    short_exits = (
        np.asarray(signals.short_exits.values, dtype=bool)
        if signals.short_exits is not None
        else np.zeros(len(long_entries), dtype=bool)
    )

    bt_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10_000.0,
        position_size=0.10,
        use_fixed_amount=True,
        fixed_amount=100.0,
        leverage=10,
        stop_loss=0.091,
        take_profit=0.015,
        taker_fee=0.0007,
        slippage=0.0,
        direction=TradeDirection.BOTH,
        pyramiding=1,
        interval="30",
    )

    result = FallbackEngineV4().run(bt_input)
    trades = result.trades
    print(f"\nEngine trades: {len(trades)}")
    print(f"Net profit: {result.metrics.net_profit:.2f}")
    print(f"Win rate: {result.metrics.win_rate:.1f}%")
    print()
    print(f"{'#':<4} {'side':<6} {'entry_time':<22} {'ep':>9}  {'exit_time':<22} {'xp':>10}  {'pnl':>9}  exit_reason")
    print("-" * 100)
    for i, t in enumerate(trades):
        print(
            f"{i + 1:<4} {t.direction:<6} {str(t.entry_time)[:19]:<22} {t.entry_price:>9.1f}  "
            f"{str(t.exit_time)[:19]:<22} {t.exit_price:>10.4f}  {t.pnl:>9.2f}  {t.exit_reason}"
        )


if __name__ == "__main__":
    main()
