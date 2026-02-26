"""
NEW APPROACH: Look at this from TV's perspective.

For the 5 UNKNOWN cases, TV takes the 2nd crossunder. Let's check:
What if TV's PREVIOUS trade exits at a DIFFERENT time/price than ours?

If TV's prev trade has a slightly different exit (e.g., 1 bar later),
then the 1st crossunder might occur WHILE the TV position is still open,
so TV can't enter. The engine's prev trade already exited, so it CAN enter.

This would explain everything! Let's verify by comparing TV exit times
for the trades immediately preceding each UNKNOWN case.
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

    # Load TV CSV
    tv_csv_path = r"c:\Users\roman\Downloads\as4.csv"
    tv_df = pd.read_csv(tv_csv_path, sep=";")

    # Parse all TV trades
    tv_trades = []
    for trade_num in sorted(tv_df["№ Сделки"].unique()):
        grp = tv_df[tv_df["№ Сделки"] == trade_num]
        entry_row = grp[grp["Тип"].str.contains("Entry")]
        exit_row = grp[grp["Тип"].str.contains("Exit")]

        if entry_row.empty or exit_row.empty:
            continue

        entry_type = entry_row.iloc[0]["Тип"].strip()
        exit_type = exit_row.iloc[0]["Тип"].strip()

        entry_dt = pd.Timestamp(entry_row.iloc[0]["Дата и время"].strip()) - pd.Timedelta(hours=3)
        exit_dt = pd.Timestamp(exit_row.iloc[0]["Дата и время"].strip()) - pd.Timedelta(hours=3)

        entry_price = float(str(entry_row.iloc[0]["Цена USDT"]).replace("\xa0", "").replace(",", ".").replace(" ", ""))
        exit_price = float(str(exit_row.iloc[0]["Цена USDT"]).replace("\xa0", "").replace(",", ".").replace(" ", ""))

        tv_trades.append(
            {
                "num": trade_num,
                "entry_type": entry_type,
                "exit_type": exit_type,
                "entry_time": entry_dt,
                "exit_time": exit_dt,
                "entry_price": entry_price,
                "exit_price": exit_price,
            }
        )

    print(f"Parsed {len(tv_trades)} TV trades")

    # Map engine UNKNOWN trade numbers to their TV counterparts
    # From _count_crossunders_v2.py results:
    # E#23 → TV#22, E#85 → TV#85, E#89 → TV#89, E#91 → TV#91, E#120 → TV#119
    # But let's be more precise — find the TV trade that matches each engine trade entry

    unknown_cases = [
        {"eng_num": 23, "tv_num": 22},
        {"eng_num": 85, "tv_num": 85},
        {"eng_num": 89, "tv_num": 89},
        {"eng_num": 91, "tv_num": 91},
        {"eng_num": 120, "tv_num": 119},
    ]

    print("\n" + "=" * 140)
    print("COMPARISON: PREVIOUS TRADE EXIT TIMES — ENGINE vs TV")
    print("=" * 140)

    rsi_vals = None
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

    for case in unknown_cases:
        eng_num = case["eng_num"]
        tv_num = case["tv_num"]

        # Engine trades
        eng_trade = trades[eng_num - 1]
        eng_prev = trades[eng_num - 2]

        eng_entry = pd.Timestamp(str(eng_trade.entry_time))
        if eng_entry.tzinfo:
            eng_entry = eng_entry.tz_localize(None)

        eng_prev_exit = pd.Timestamp(str(eng_prev.exit_time))
        if eng_prev_exit.tzinfo:
            eng_prev_exit = eng_prev_exit.tz_localize(None)
        eng_prev_exit_exec = eng_prev_exit + pd.Timedelta(minutes=30)

        eng_prev_entry = pd.Timestamp(str(eng_prev.entry_time))
        if eng_prev_entry.tzinfo:
            eng_prev_entry = eng_prev_entry.tz_localize(None)

        # TV trades (tv_num is the current trade, tv_num-1 is the prev)
        tv_trade = next(t for t in tv_trades if t["num"] == tv_num)
        tv_prev = next(t for t in tv_trades if t["num"] == tv_num - 1)

        # TV uses entry_on_next_bar_open, so TV entry time = signal bar + 30min
        # TV exit time for TP = bar time when TP hit (the bar's open price range)
        # But TV CSV exit time is the actual exit time...

        # The 1st SE bar for this case
        first_se_bars = {
            23: pd.Timestamp("2025-02-22 10:30:00"),
            85: pd.Timestamp("2025-08-16 01:00:00"),
            89: pd.Timestamp("2025-08-27 02:30:00"),
            91: pd.Timestamp("2025-09-02 11:00:00"),
            120: pd.Timestamp("2025-11-25 00:00:00"),
        }
        first_se_bar = first_se_bars[eng_num]

        print(f"\n{'=' * 100}")
        print(f"UNKNOWN CASE: Engine #{eng_num} / TV #{tv_num}")
        print(f"{'=' * 100}")

        print(f"\n  PREVIOUS TRADE (before the entry discrepancy):")
        print(f"    Engine #{eng_num - 1}:")
        print(f"      Entry: {eng_prev_entry} @ {eng_prev.entry_price}")
        print(f"      Exit:  {eng_prev_exit} @ {eng_prev.exit_price} ({eng_prev.exit_reason})")
        print(f"      Exit exec bar: {eng_prev_exit_exec}")

        print(f"    TV #{tv_num - 1}:")
        print(f"      Entry: {tv_prev['entry_time']} @ {tv_prev['entry_price']}")
        print(f"      Exit:  {tv_prev['exit_time']} @ {tv_prev['exit_price']} ({tv_prev['exit_type']})")
        # TV exit exec = tv_prev exit_time (which is already the execution time)
        # Actually in TV CSV, the exit time is the bar close time when exit happened
        # With entry_on_next_bar_open for TP: exit at next bar open after TP detection

        # Check if engine prev entry matches TV prev entry
        entry_match = abs(eng_prev_entry - tv_prev["entry_time"]).total_seconds() < 1800
        exit_diff = (tv_prev["exit_time"] - eng_prev_exit).total_seconds() / 1800

        print(f"\n  COMPARISON:")
        print(f"    Prev entry match: {entry_match} (diff={eng_prev_entry - tv_prev['entry_time']})")
        print(f"    Prev exit diff:   {exit_diff:.1f} bars (TV exit - Engine exit)")
        if exit_diff != 0:
            print(f"    *** TV exits {exit_diff:.1f} bars LATER than engine!")

        print(f"\n  CURRENT TRADE:")
        print(f"    1st SE bar:      {first_se_bar}")
        print(f"    Engine entry:    {eng_entry} (takes 1st SE)")
        print(f"    TV entry:        {tv_trade['entry_time']} (takes 2nd SE)")

        # KEY QUESTION: Is the 1st SE bar BEFORE TV's prev exit time?
        if first_se_bar < tv_prev["exit_time"]:
            print(f"    ⚠️ 1st SE ({first_se_bar}) is BEFORE TV prev exit ({tv_prev['exit_time']})")
            print(f"       → TV position still OPEN at 1st SE! Can't enter!")
        elif first_se_bar == tv_prev["exit_time"]:
            print(f"    ⚠️ 1st SE ({first_se_bar}) is SAME BAR as TV prev exit ({tv_prev['exit_time']})")
            print(f"       → TV position closing on same bar as SE signal!")
        else:
            # Check if 1st SE signal bar is the same as TV exit bar
            # Remember: entry_on_next_bar_open means signal at bar N, entry at bar N+1
            # But also: with process_orders_on_close, exit happens at bar close
            # So if TV exits at bar X close, and SE signal is also at bar X...
            # The strategy evaluates (sees SE=true), then the exit order fills
            # But can the entry order fire while the exit is pending?
            # In TV: with process_orders_on_close, both happen at bar close
            # TP fills first (priority), then new entry would need to wait

            # Let's check: signal bar for engine entry
            se_signal_bar_time = first_se_bar  # the SE=True bar
            # Engine reads se[i-1] at bar i, so entry at bar i if se[i-1]=True
            # The SE signal fires at se_signal_bar_time, entry at se_signal_bar_time + 30min

            # For TV: the exit time in CSV might be next-bar-open for TP exit
            # Or it might be the bar where TP triggered

            print(
                f"    1st SE ({first_se_bar}) is {(first_se_bar - tv_prev['exit_time']).total_seconds() / 1800:.1f} bars AFTER TV prev exit"
            )
            # Check if maybe TV's pending exit blocks the next bar
            tv_exit_plus_one = tv_prev["exit_time"] + pd.Timedelta(minutes=30)
            se_entry_bar = first_se_bar + pd.Timedelta(minutes=30)
            if se_entry_bar <= tv_exit_plus_one:
                print(f"    ⚠️ SE entry bar ({se_entry_bar}) <= TV exit+1 bar ({tv_exit_plus_one})")


asyncio.run(main())
