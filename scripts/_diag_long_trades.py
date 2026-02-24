"""Diagnose long losing trades in engine vs TV."""
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
WARMUP_BARS = 500


async def run():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br)
    conns = json.loads(cr)
    graph = {
        "name": name, "blocks": blocks, "connections": conns,
        "market_type": "linear", "direction": "both", "interval": "30",
    }
    svc = BacktestService()
    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    warmup_ts_start = int(btc_start.timestamp() * 1000)
    warmup_ts_end = int(START_DATE.timestamp() * 1000)
    raw_warmup = await svc.adapter.get_historical_klines(
        "BTCUSDT", "30", warmup_ts_start, warmup_ts_end, market_type="linear"
    )
    if raw_warmup:
        df_w = pd.DataFrame(raw_warmup)
        # Handle multiple possible column naming conventions from Bybit API
        col_map = {
            "startTime": "timestamp", "open_time": "timestamp", "t": "timestamp",
            "openPrice": "open", "o": "open",
            "highPrice": "high", "h": "high",
            "lowPrice": "low", "l": "low",
            "closePrice": "close", "c": "close",
            "volume": "volume", "v": "volume",
        }
        df_w = df_w.rename(columns={k: v for k, v in col_map.items() if k in df_w.columns})
        if "timestamp" not in df_w.columns:
            # Try first column as timestamp
            df_w = df_w.rename(columns={df_w.columns[0]: "timestamp"})
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df_w.columns:
                df_w[col] = pd.to_numeric(df_w[col], errors="coerce")
        if "timestamp" in df_w.columns and df_w["timestamp"].dtype in ["int64", "float64"]:
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms")
        elif "timestamp" in df_w.columns:
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"])
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
    se = np.asarray(signals.short_entries.values, dtype=bool)
    lx = np.asarray(signals.exits.values, dtype=bool)
    sx = np.asarray(signals.short_exits.values, dtype=bool)
    result = FallbackEngineV4().run(BacktestInput(
        candles=candles, long_entries=le, long_exits=lx, short_entries=se, short_exits=sx,
        initial_capital=1_000_000.0, position_size=0.10, use_fixed_amount=True, fixed_amount=100.0,
        leverage=10, stop_loss=0.132, take_profit=0.023, taker_fee=0.0007, slippage=0.0,
        direction=TradeDirection.BOTH, pyramiding=1, interval="30",
    ))

    trades = result.trades
    long_closed = [t for t in trades if t.direction == "long" and not getattr(t, "is_open", False)]
    long_losing = [t for t in long_closed if t.pnl < 0]

    print(f"Long closed: {len(long_closed)}, Long losing: {len(long_losing)}")
    print()
    print("=== ALL LONG TRADES ===")
    for t in long_closed:
        ts_in = pd.Timestamp(t.entry_time)
        ts_out = pd.Timestamp(t.exit_time)
        print(f"  {str(ts_in)[:16]} -> {str(ts_out)[:16]}  ep={t.entry_price:.2f}  xp={t.exit_price:.2f}  pnl={t.pnl:.2f}  reason={t.exit_reason}")

    print()
    print("=== ALL SHORT LOSERS ===")
    short_losing = [t for t in trades if t.direction == "short" and t.pnl < 0]
    for t in short_losing:
        ts_in = pd.Timestamp(t.entry_time)
        ts_out = pd.Timestamp(t.exit_time)
        print(f"  {str(ts_in)[:16]} -> {str(ts_out)[:16]}  ep={t.entry_price:.2f}  xp={t.exit_price:.2f}  pnl={t.pnl:.2f}  reason={t.exit_reason}")


asyncio.run(run())
