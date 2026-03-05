"""
Get EXACT prev trade exit details for 6 UNKNOWN cases.
KEY QUESTION: When exactly does the previous trade exit (TP price check)?
"""

import asyncio
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.getcwd())

import numpy as np
import pandas as pd


async def main():
    from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
    from backend.backtesting.interfaces import BacktestInput, TradeDirection
    from backend.backtesting.service import BacktestService
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    svc = BacktestService()

    START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
    END_DATE = pd.Timestamp("2026-02-24T00:00:00", tz="UTC")

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), START_DATE)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    db_conn = sqlite3.connect("data.sqlite3")
    row = db_conn.execute(
        "SELECT builder_blocks, builder_connections FROM strategies WHERE id='dd2969a2-bbba-410e-b190-be1e8cc50b21'"
    ).fetchone()
    blocks = json.loads(row[0])
    connections = json.loads(row[1])

    graph = {"blocks": blocks, "connections": connections, "name": "RSI_LS_10"}
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    result = adapter.generate_signals(candles)

    bi = BacktestInput(
        candles=candles,
        long_entries=result.entries.values,
        long_exits=result.exits.values,
        short_entries=result.short_entries.values,
        short_exits=result.short_exits.values,
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
    engine = FallbackEngineV4()
    out = engine.run(bi)
    trades = out.trades

    # Divergent trade numbers (1-based)
    div_trades = [23, 57, 85, 89, 91, 120]

    for t_num in div_trades:
        # Previous trade (the one that exits before the divergent entry)
        prev = trades[t_num - 2]  # 0-based index = t_num - 2
        curr = trades[t_num - 1]  # 0-based index = t_num - 1

        print(f"\n{'=' * 80}")
        print(f"DIVERGENT TRADE E#{t_num}")
        print(f"  Current trade (divergent): entry={curr.entry_time}, exit={curr.exit_time}, {curr.exit_reason}")
        print(f"  Entry price: {curr.entry_price:.2f}")
        print(f"  Previous trade E#{t_num - 1}: {prev.direction}")
        print(f"    entry={prev.entry_time}, price={prev.entry_price:.2f}")
        print(f"    exit={prev.exit_time}, price={prev.exit_price:.2f}")
        print(f"    exit_reason={prev.exit_reason}")

        # For short TP: tp_price = entry_price * (1 - take_profit)
        # For long TP: tp_price = entry_price * (1 + take_profit)
        if str(prev.direction) in ("short", "TradeDirection.SHORT"):
            tp_price = prev.entry_price * (1 - 0.023)
            print(f"    TP level (short): {tp_price:.2f}")
        else:
            tp_price = prev.entry_price * (1 + 0.023)
            print(f"    TP level (long): {tp_price:.2f}")

        # Check which bar TP actually fires on
        exit_t = pd.Timestamp(prev.exit_time)
        if hasattr(exit_t, "tz") and exit_t.tz:
            exit_t = exit_t.tz_localize(None)

        # In our engine with entry_on_next_bar_open=True:
        # - TP detected at bar X (checking high/low against TP level)
        # - pending_exit set at bar X
        # - Exit executes at bar X+1
        # - exit_time = bar X+1's timestamp
        # So TP detection bar = exit_time - 30min

        tp_detection_bar = exit_t - pd.Timedelta(minutes=30)
        print(f"    TP detection bar (estimated): {tp_detection_bar}")
        print(f"    Exit execution bar: {exit_t}")

        # Verify: check candle data at TP detection bar
        if tp_detection_bar in candles.index:
            bar_data = candles.loc[tp_detection_bar]
            if str(prev.direction) in ("short", "TradeDirection.SHORT"):
                reaches = bar_data["low"] <= tp_price
                print(f"    Bar {tp_detection_bar}: low={bar_data['low']:.2f}, TP={tp_price:.2f}, reaches={reaches}")
            else:
                reaches = bar_data["high"] >= tp_price
                print(f"    Bar {tp_detection_bar}: high={bar_data['high']:.2f}, TP={tp_price:.2f}, reaches={reaches}")

            # Also check the bar before to make sure TP doesn't fire earlier
            prev_bar = tp_detection_bar - pd.Timedelta(minutes=30)
            if prev_bar in candles.index:
                prev_bar_data = candles.loc[prev_bar]
                if str(prev.direction) in ("short", "TradeDirection.SHORT"):
                    prev_reaches = prev_bar_data["low"] <= tp_price
                    print(
                        f"    Bar {prev_bar}: low={prev_bar_data['low']:.2f}, TP={tp_price:.2f}, reaches={prev_reaches}"
                    )
                else:
                    prev_reaches = prev_bar_data["high"] >= tp_price
                    print(
                        f"    Bar {prev_bar}: high={prev_bar_data['high']:.2f}, TP={tp_price:.2f}, reaches={prev_reaches}"
                    )

        # Gap from exit to engine entry
        eng_entry_t = pd.Timestamp(curr.entry_time)
        if hasattr(eng_entry_t, "tz") and eng_entry_t.tz:
            eng_entry_t = eng_entry_t.tz_localize(None)
        gap_bars = (eng_entry_t - exit_t) / pd.Timedelta(minutes=30)
        print(f"    Gap from exit to engine entry: {gap_bars:.0f} bars ({eng_entry_t - exit_t})")


asyncio.run(main())
