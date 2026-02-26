"""Quick: show engine trades #9-#14 and TV trades #9-#14 to understand alignment."""

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
    trades = result.trades

    # Load and parse TV trades
    tv_csv = r"c:\Users\roman\Downloads\as4.csv"
    tv = pd.read_csv(tv_csv, sep=";")

    # Parse TV trades (entry/exit row pairs)
    tv_trades = []
    i = 0
    while i < len(tv) - 1:
        row1 = tv.iloc[i]
        row2 = tv.iloc[i + 1]

        # Determine which is entry and which is exit
        type1 = str(row1.get("Type", row1.get("type", "")))
        type2 = str(row2.get("Type", row2.get("type", "")))

        if "Entry" in type1 and "Exit" in type2:
            direction = "long" if "Long" in type1 else "short"
            entry_time_str = str(row1.get("Date/Time", row1.get("datetime", "")))
            exit_time_str = str(row2.get("Date/Time", row2.get("datetime", "")))
            profit = row2.get("Profit", row2.get("profit", 0))
            tv_trades.append(
                {
                    "direction": direction,
                    "entry_time": entry_time_str,
                    "exit_time": exit_time_str,
                    "profit": profit,
                }
            )
            i += 2
        else:
            i += 1

    print(f"Engine trades: {len(trades)}, TV trades: {len(tv_trades)}")
    print()

    # Show trades #6-#14 for both
    print(f"{'#':>3s}  {'Engine':^55s}  |  {'TV':^55s}")
    print(
        f"{'':>3s}  {'dir':6s} {'entry':20s} {'exit':20s} {'pnl':>8s}  |  {'dir':6s} {'entry':20s} {'exit':20s} {'pnl':>8s}"
    )
    print("-" * 130)

    for idx in range(5, min(16, max(len(trades), len(tv_trades)))):
        e_str = ""
        t_str = ""
        match = ""

        if idx < len(trades):
            t = trades[idx]
            e_str = f"{t.direction:6s} {str(t.entry_time)[:19]:20s} {str(t.exit_time)[:19]:20s} {t.pnl:8.2f}"

        if idx < len(tv_trades):
            tv_t = tv_trades[idx]
            t_str = f"{tv_t['direction']:6s} {tv_t['entry_time'][:19]:20s} {tv_t['exit_time'][:19]:20s} {str(tv_t['profit']):>8s}"

        # Check if entries match
        if idx < len(trades) and idx < len(tv_trades):
            e_entry = str(trades[idx].entry_time)[:16]
            tv_entry = tv_trades[idx]["entry_time"][:16]
            if e_entry == tv_entry or e_entry.replace("T", " ") == tv_entry.replace("T", " "):
                match = "✅"
            else:
                match = "❌"

        print(f"{idx + 1:3d}  {e_str}  |  {t_str}  {match}")


asyncio.run(main())
