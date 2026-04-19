"""Quick diagnostic for engine metrics."""

import asyncio
import json
import sqlite3
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="ERROR")
import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")


async def run():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?", (STRATEGY_ID,)
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br)
    conns = json.loads(cr)
    gp = json.loads(gr)
    graph = {
        "name": name,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    svc = BacktestService()
    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_main)
    signals = adapter.generate_signals(candles)
    le = np.asarray(signals.entries.values, dtype=bool)
    se = np.asarray(signals.short_entries.values, dtype=bool)
    lx = np.asarray(signals.exits.values, dtype=bool)
    sx = np.asarray(signals.short_exits.values, dtype=bool)
    result = FallbackEngineV4().run(
        BacktestInput(
            candles=candles,
            long_entries=le,
            long_exits=lx,
            short_entries=se,
            short_exits=sx,
            initial_capital=1_000_000.0,
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
    m = result.metrics
    print(f"max_drawdown={m.max_drawdown}")
    print(f"total={m.total_trades}, net_pnl={m.net_profit:.2f}")
    t0 = result.trades[0]
    flds = [f for f in dir(t0) if not f.startswith("_")]
    print(f"Trade0 fields: {flds}")
    for f in flds:
        v = getattr(t0, f, None)
        if v is not None and not callable(v):
            print(f"  {f}: {v}")


asyncio.run(run())
