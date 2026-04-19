"""Show ALL TV trades #8-#14 and ALL engine trades #8-#14 side by side."""

import asyncio
import json
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4 as FallbackEngine
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter


async def main():
    svc = BacktestService()
    conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
        ("dd2969a2-bbba-410e-b190-be1e8cc50b21",),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br)
    conns = json.loads(cr)
    gp = json.loads(gr)
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
        "ETHUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc_warmup = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2020-01-01", tz="UTC"),
        pd.Timestamp("2025-01-01", tz="UTC"),
    )
    btc_main = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)

    le = np.asarray(signals.entries.values, dtype=bool)
    lx = np.asarray(signals.exits.values, dtype=bool)
    se = np.asarray(signals.short_entries.values, dtype=bool)
    sx = np.asarray(signals.short_exits.values, dtype=bool)

    engine = FallbackEngine()
    inp = BacktestInput(
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
    result = engine.run(inp)
    engine_trades = result.trades

    # Parse TV trades
    tv_raw = pd.read_csv(r"c:\Users\roman\Downloads\as4.csv", sep=";")
    tv_trades = []
    for i in range(0, len(tv_raw), 2):
        exit_row = tv_raw.iloc[i]
        entry_row = tv_raw.iloc[i + 1]
        trade_num = int(str(exit_row["№ Сделки"]).strip())
        entry_type = str(entry_row["Тип"]).strip()
        direction = "short" if "short" in entry_type.lower() else "long"
        entry_time = pd.Timestamp(str(entry_row["Дата и время"]).strip()) - pd.Timedelta(hours=3)
        exit_time = pd.Timestamp(str(exit_row["Дата и время"]).strip()) - pd.Timedelta(hours=3)
        entry_price = float(str(entry_row["Цена USDT"]).replace(",", ".").strip())
        exit_signal = str(exit_row["Сигнал"]).strip()
        tv_trades.append(
            {
                "num": trade_num,
                "direction": direction,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "entry_price": entry_price,
                "exit_signal": exit_signal,
            }
        )

    # Show side-by-side for ranges around roots
    ranges = [(7, 15), (83, 93), (142, 150)]

    for start, end in ranges:
        print(f"\n{'=' * 90}")
        print(f"TRADES #{start}-#{end}")
        print(f"{'=' * 90}")
        print(f"{'#':>4} | {'Dir':>5} | {'Engine Entry':>20} | {'TV Entry':>20} | {'Match':>5} | Notes")
        print("-" * 90)

        for idx in range(start, end + 1):
            if idx > len(engine_trades) or idx > len(tv_trades):
                break

            et = engine_trades[idx - 1]
            tt = tv_trades[idx - 1]

            e_entry = pd.Timestamp(et.entry_time).strftime("%Y-%m-%d %H:%M")
            t_entry = tt["entry_time"].strftime("%Y-%m-%d %H:%M")

            dir_match = et.direction == tt["direction"]
            time_match = pd.Timestamp(et.entry_time) == tt["entry_time"]

            match = "✓" if (dir_match and time_match) else "✗"

            notes = ""
            if not dir_match:
                notes = f"DIR: E={et.direction}, TV={tt['direction']}"
            elif not time_match:
                diff = tt["entry_time"] - pd.Timestamp(et.entry_time)
                notes = f"TIME: Δ={diff}"

            print(f"{idx:4d} | {et.direction:>5} | {e_entry:>20} | {t_entry:>20} | {match:>5} | {notes}")

    # Also check: is trade #9 the first divergence?
    print(f"\n{'=' * 90}")
    print("Checking first divergence point...")
    for idx in range(1, len(engine_trades) + 1):
        if idx > len(tv_trades):
            break
        et = engine_trades[idx - 1]
        tt = tv_trades[idx - 1]
        e_entry = pd.Timestamp(et.entry_time)
        t_entry = tt["entry_time"]
        if e_entry != t_entry or et.direction != tt["direction"]:
            print(f"First divergence at trade #{idx}:")
            print(f"  Engine: {et.direction}, entry={e_entry}, exit={pd.Timestamp(et.exit_time)}")
            print(f"  TV:     {tt['direction']}, entry={t_entry}, exit={tt['exit_time']}")
            break


asyncio.run(main())
