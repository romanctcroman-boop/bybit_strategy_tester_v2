"""Check if trade #11's TP timing differs between engine and TV.
Maybe the issue is: our engine exits trade #11 ONE BAR EARLIER than TV,
freeing up the position to catch an earlier signal."""

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
        exit_price = float(str(exit_row["Цена USDT"]).replace(",", ".").strip())
        tv_trades.append(
            {
                "num": trade_num,
                "direction": direction,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "entry_price": entry_price,
                "exit_price": exit_price,
            }
        )

    open_prices = candles["open"].values
    high_prices = candles["high"].values
    low_prices = candles["low"].values
    close_prices = candles["close"].values

    # Detailed analysis of the preceding trades for each root
    for root_idx in [12, 85, 89, 91]:
        prev_idx = root_idx - 1  # trade before root
        et = engine_trades[prev_idx - 1]  # 0-indexed
        tt = tv_trades[prev_idx - 1]

        print(f"\n{'=' * 70}")
        print(f"TRADE #{prev_idx} (precedes Root #{root_idx})")
        print(f"{'=' * 70}")

        print(
            f"  Engine: {et.direction}, entry={pd.Timestamp(et.entry_time)}, "
            f"exit={pd.Timestamp(et.exit_time)}, reason={et.exit_reason}"
        )
        print(f"  Engine: entry_price={et.entry_price:.2f}, exit_price={et.exit_price:.2f}")
        print(f"  TV:     {tt['direction']}, entry={tt['entry_time']}, exit={tt['exit_time']}")
        print(f"  TV:     entry_price={tt['entry_price']:.2f}, exit_price={tt['exit_price']:.2f}")

        # Check timing match
        engine_exit = pd.Timestamp(et.exit_time)
        tv_exit = tt["exit_time"]
        print(f"\n  Exit time match: {engine_exit == tv_exit}")
        if engine_exit != tv_exit:
            print(f"  *** EXIT TIME DIFFERS! Engine={engine_exit}, TV={tv_exit}")
            print(f"  *** Δ = {tv_exit - engine_exit}")

        # Entry time match
        engine_entry = pd.Timestamp(et.entry_time)
        tv_entry = tt["entry_time"]
        print(f"  Entry time match: {engine_entry == tv_entry}")

        # Check TP level
        if et.direction == "short":
            tp_level = et.entry_price * (1 - 0.023)
        else:
            tp_level = et.entry_price * (1 + 0.023)
        print(f"  TP level: {tp_level:.2f}")

        # Find exit bar in candles
        exit_idx = None
        for idx_c, ts in enumerate(candles.index):
            if ts == engine_exit:
                exit_idx = idx_c
                break

        if exit_idx:
            # Show OHLC at exit bar and bar before
            for k in [exit_idx - 2, exit_idx - 1, exit_idx, exit_idx + 1]:
                ts = candles.index[k]
                marker = ""
                if k == exit_idx:
                    marker = " ← ENGINE EXIT"
                    if et.direction == "short":
                        tp_hit = low_prices[k] <= tp_level
                        marker += f" (TP {'HIT' if tp_hit else 'MISS'}: low={low_prices[k]:.2f} vs TP={tp_level:.2f})"
                elif k == exit_idx - 1:
                    if et.direction == "short":
                        tp_hit = low_prices[k] <= tp_level
                        marker = f" ← PREV BAR (TP {'HIT' if tp_hit else 'MISS'}: low={low_prices[k]:.2f} vs TP={tp_level:.2f})"

                print(
                    f"    {ts}: O={open_prices[k]:.2f} H={high_prices[k]:.2f} "
                    f"L={low_prices[k]:.2f} C={close_prices[k]:.2f}{marker}"
                )

        # TV exit bar
        tv_exit_idx = None
        for idx_c, ts in enumerate(candles.index):
            if ts == tv_exit:
                tv_exit_idx = idx_c
                break

        if tv_exit_idx and tv_exit_idx != exit_idx:
            print(f"\n  TV exits at different bar!")
            print(f"  TV exit bar {tv_exit}:")
            k = tv_exit_idx
            print(
                f"    {candles.index[k]}: O={open_prices[k]:.2f} H={high_prices[k]:.2f} "
                f"L={low_prices[k]:.2f} C={close_prices[k]:.2f}"
            )


asyncio.run(main())
