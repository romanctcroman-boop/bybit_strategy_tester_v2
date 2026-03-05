"""
For the 5 UNKNOWN cases (excluding E#57):
Check if the TP detection bar has SE=True.

TV's process_orders_on_close model:
1. Strategy code runs (RSI computed, crossunder detected)
2. Orders execute (TP fills, position closes)

So if SE fires on the same bar as TP, the strategy code sees the crossunder
while the position is STILL OPEN. The entry order would be issued, but
then the TP fill happens. In TV, the TP fill takes priority, and the
entry order might be CANCELLED because you can't enter while exiting.

But our engine: TP detection happens first (in bar loop), then
pending_short_exit=True blocks the entry signal on that bar.
The entry then fires on the NEXT SE bar.

Wait — but our engine uses entry_on_next_bar_open=True, so:
- Bar X: TP detected → pending_short_exit=True
- Bar X+1: pending exit executes → position closes
- Bar X+1: also checks if short_entries[X] was True (signal from bar X)
  - But pending_short_exit blocks this!
- Bar X+2: checks short_entries[X+1]

Hmm, but what if in TV:
- Bar X: strategy code detects crossunder AND TP condition
- TP order fills (position closes)
- Entry order from crossunder fires (new position opens)
- But process_orders_on_close means: strategy code runs FIRST,
  then TP fills, then entry fills

Let me check whether the TP trigger bar overlaps with the 1st SE bar.
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

    se = result.short_entries.values
    idx_arr = candles.index

    # Run backtest
    bi = BacktestInput(
        candles=candles,
        long_entries=result.entries.values,
        long_exits=result.exits.values,
        short_entries=se,
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

    # Compute BTC RSI
    btc_close = btc["close"]
    delta = btc_close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    btc_rsi_full = 100 - (100 / (1 + rs))
    btc_rsi = btc_rsi_full.reindex(candles.index, method="ffill")
    rsi_vals = btc_rsi.values

    lows = candles["low"].values
    highs = candles["high"].values
    opens = candles["open"].values
    closes = candles["close"].values

    skipped_trade_nums = [23, 85, 89, 91, 120]
    skipped_1st_se_bars = [
        pd.Timestamp("2025-02-22 10:30:00"),
        pd.Timestamp("2025-08-16 01:00:00"),
        pd.Timestamp("2025-08-27 02:30:00"),
        pd.Timestamp("2025-09-02 11:00:00"),
        pd.Timestamp("2025-11-25 00:00:00"),
    ]

    print("=" * 140)
    print("TP DETECTION vs 1st SE TIMING ANALYSIS")
    print("=" * 140)

    for eng_num, first_se_bar in zip(skipped_trade_nums, skipped_1st_se_bars, strict=True):
        # Previous trade (the one that exits via TP before this entry)
        prev_trade = trades[eng_num - 2]
        curr_trade = trades[eng_num - 1]

        exit_time = pd.Timestamp(str(prev_trade.exit_time))
        if exit_time.tzinfo:
            exit_time = exit_time.tz_localize(None)

        # TP detection bar = exit_time (the bar where TP condition is met)
        tp_detect_bar = exit_time
        # Exit execution bar = exit_time + 30min (pending exit executes next bar)
        tp_exec_bar = exit_time + pd.Timedelta(minutes=30)

        # Entry time of current trade
        entry_time = pd.Timestamp(str(curr_trade.entry_time))
        if entry_time.tzinfo:
            entry_time = entry_time.tz_localize(None)
        signal_bar = entry_time - pd.Timedelta(minutes=30)

        # Check: TP entry price and exit price of prev trade
        exit_reason = getattr(prev_trade, "exit_type", getattr(prev_trade, "exit_reason", "unknown"))
        print(f"\nEngine Trade #{eng_num}:")
        print(f"  Prev trade exit: reason={exit_reason}, exit_time={exit_time}")
        print(f"    entry_price={prev_trade.entry_price}, exit_price={prev_trade.exit_price}")
        print(f"    TP detect bar: {tp_detect_bar}")
        print(f"    TP exec bar:   {tp_exec_bar}")

        # Find positions
        tp_det_pos = None
        for j, ts in enumerate(idx_arr):
            if ts == tp_detect_bar:
                tp_det_pos = j
                break

        first_se_pos = None
        for j, ts in enumerate(idx_arr):
            if ts == first_se_bar:
                first_se_pos = j
                break

        if tp_det_pos is not None:
            print(f"    At TP detect bar ({tp_detect_bar}):")
            print(
                f"      OHLC: O={opens[tp_det_pos]}, H={highs[tp_det_pos]}, L={lows[tp_det_pos]}, C={closes[tp_det_pos]}"
            )
            print(f"      SE={se[tp_det_pos]}, RSI={rsi_vals[tp_det_pos]:.2f}")
            # Check SE on the bar AFTER TP detection (the exec bar)
            if tp_det_pos + 1 < len(se):
                print(f"    At TP exec bar ({idx_arr[tp_det_pos + 1]}):")
                print(
                    f"      SE={se[tp_det_pos + 1]}, RSI prev={rsi_vals[tp_det_pos]:.2f}, RSI curr={rsi_vals[tp_det_pos + 1]:.2f}"
                )

        print(f"  1st SE bar:     {first_se_bar} (SE={se[first_se_pos] if first_se_pos is not None else '?'})")
        print(f"  Engine entry:   {entry_time} (signal bar: {signal_bar})")

        # Check if SE is True at TP detect bar or TP exec bar
        if tp_det_pos is not None:
            tp_det_se = se[tp_det_pos]
            tp_exec_se = se[tp_det_pos + 1] if tp_det_pos + 1 < len(se) else False
            if tp_det_se:
                print("  *** SE=True AT TP detect bar! Position still open when signal fires!")
            if tp_exec_se:
                print("  *** SE=True AT TP exec bar!")

        # Check bars between TP exec and first SE
        if tp_det_pos is not None and first_se_pos is not None:
            gap = first_se_pos - (tp_det_pos + 1)  # bars between exec and first SE
            print(f"  Gap from TP exec bar to 1st SE: {gap} bars")

            # Show SE bars from TP detect to beyond first SE
            print("  SE trace from TP detect-2 to 1st SE+2:")
            start = max(0, tp_det_pos - 2)
            end = min(len(se), first_se_pos + 3)
            for j in range(start, end):
                marker = ""
                if j == tp_det_pos:
                    marker = " ← TP DETECT"
                if j == tp_det_pos + 1:
                    marker = " ← TP EXEC"
                if j == first_se_pos:
                    marker = " ← 1st SE"
                print(f"    {idx_arr[j]}: SE={se[j]}, RSI={rsi_vals[j]:.2f}{marker}")


asyncio.run(main())
