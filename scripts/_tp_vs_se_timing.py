"""
Deep check: What is the exact timing between prev trade TP exit and the 1st SE signal?

Key question: In the engine, when does the TP exit execute relative to when the
next entry signal is read?

With entry_on_next_bar_open=True:
- Bar i-1: signal generated (SE[i-1]=True)
- Bar i:   engine reads SE[i-1], enters at open[i]

But also with TP:
- Bar X:   TP condition detected → pending_short_exit=True
- Bar X+1: pending exit executes at open[X+1]
            exit_time = prev_bar_time = times[X]

CRITICAL QUESTION: If TP fires at bar X, and SE[X]=True, does the engine
enter at bar X+1 (reading SE[X]) simultaneously with the TP exit at X+1?

Or does the engine's execution ORDER (exits before entries) prevent this?

Let's check: For each UNKNOWN case, what is bar X (TP detection) vs the 1st SE bar?
"""

import asyncio
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.getcwd())

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
    sx = result.short_exits.values
    le = result.entries.values
    lx = result.exits.values
    idx = candles.index

    # Run backtest
    bi = BacktestInput(
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
    engine = FallbackEngineV4()
    out = engine.run(bi)
    trades = out.trades

    # UNKNOWN cases with their engine trade# (1-based)
    unknown_cases = [
        ("E#23", 23, "2025-02-22 10:30", "2025-02-22 13:30"),
        ("E#57", 57, "2025-05-09 15:00", "2025-05-09 19:00"),
        ("E#85", 85, "2025-08-16 01:00", "2025-08-16 13:30"),
        ("E#89", 89, "2025-08-27 02:30", "2025-08-27 12:00"),
        ("E#91", 91, "2025-09-02 11:00", "2025-09-02 18:00"),
        ("E#120", 120, "2025-11-25 00:00", "2025-11-25 05:00"),
    ]

    print("=" * 140)
    print("TP EXIT vs SE SIGNAL TIMING ANALYSIS")
    print("=" * 140)
    print()
    print("Engine bar loop order (entry_on_next_bar_open=True):")
    print("  At bar i:")
    print("    1. Execute pending exits (if pending_short_exit=True)")
    print("    2. Check SL/TP on current bar → set pending_short_exit=True")
    print("    3. Read short_entries[i-1] for entry signal")
    print("    4. If entry signal AND not pending_short_exit → enter at open[i]")
    print()

    for label, trade_1based, first_se_str, second_se_str in unknown_cases:
        prev_trade = trades[trade_1based - 2]  # 0-based: previous trade
        curr_trade = trades[trade_1based - 1]  # 0-based: the divergent trade

        # The previous trade's exit info
        prev_exit_time = pd.Timestamp(str(prev_trade.exit_time)).tz_localize(None)
        prev_exit_reason = prev_trade.exit_reason

        first_se = pd.Timestamp(first_se_str)
        second_se = pd.Timestamp(second_se_str)

        # Engine enters at first_se + 30min (next bar open)
        engine_entry_bar = first_se + pd.Timedelta(minutes=30)

        print(f"\n{'=' * 120}")
        print(f"{label}")
        print(f"  Prev trade #{trade_1based - 1}: {prev_trade.direction}")
        print(f"    Entry: {prev_trade.entry_time}")
        print(f"    Exit:  {prev_trade.exit_time} ({prev_exit_reason})")
        print(f"  1st SE bar: {first_se} → engine enters at: {engine_entry_bar}")
        print(f"  2nd SE bar: {second_se}")

        # KEY: What is the prev_exit_time relative to 1st SE?
        # With TP: exit_time = bar where TP was DETECTED (prev_bar_time)
        # The actual exit EXECUTES at the NEXT bar
        # So: exit executes at prev_exit_time + 30min

        tp_detection_bar = prev_exit_time  # This IS the TP detection bar in current code
        exit_execution_bar = prev_exit_time + pd.Timedelta(minutes=30)

        print(f"\n  TP TIMING:")
        print(f"    TP detected at bar:     {tp_detection_bar}")
        print(f"    Exit executes at bar:   {exit_execution_bar}")
        print(f"    1st SE signal bar:      {first_se}")
        print(f"    Engine entry bar:       {engine_entry_bar}")

        # How many bars between exit execution and engine entry?
        if exit_execution_bar <= engine_entry_bar:
            gap = (engine_entry_bar - exit_execution_bar) / pd.Timedelta(minutes=30)
            print(f"    Gap: {gap:.0f} bars between exit execution and engine entry")
        else:
            print(f"    !! Exit execution ({exit_execution_bar}) is AFTER engine entry ({engine_entry_bar})")

        # CRITICAL CHECK: Is the engine entering on the SAME bar where the exit executes?
        if exit_execution_bar == engine_entry_bar:
            print(f"    *** SAME BAR: Exit executes AND new entry at {engine_entry_bar}")
            print(f"    Engine order: exit first, then entry → this should work")
            print(f"    But TV might NOT allow entry on the same bar as exit!")
        elif tp_detection_bar == first_se:
            print(f"    *** TP detected on SAME bar as 1st SE signal!")
            print(f"    At bar {first_se}: TP fires → pending_exit. SE[{first_se}]=True")
            print(f"    At bar {engine_entry_bar}: exit executes. Entry reads SE[{first_se}]=True")
            print(f"    Engine: pending_short_exit blocks entry!")
        elif tp_detection_bar + pd.Timedelta(minutes=30) == first_se:
            print(f"    TP detected at {tp_detection_bar}, 1st SE at {first_se} (one bar later)")

        # Check what happens on the actual engine entry bar
        i_entry = idx.get_loc(engine_entry_bar) if engine_entry_bar in idx else None
        if i_entry is not None:
            # At this bar, engine reads SE[i_entry - 1] = SE at first_se
            se_signal = se[i_entry - 1]
            print(f"\n  ENGINE ENTRY BAR ({engine_entry_bar}):")
            print(f"    SE[i-1] = SE[{first_se}] = {se_signal}")
            print(f"    This bar is i={i_entry} in candles")

        # Now let's check: at the engine entry bar, was pending_short_exit True?
        # We can infer this from the TP timing
        # TP detected at bar X → pending_short_exit=True
        # At bar X+1: pending_short_exit executes (cleared AFTER exit)
        #   Then if SE[X]=True, engine tries to enter at X+1
        #   But the entry condition is: "not pending_short_exit"
        #   After exit execution, pending_short_exit is set back to False
        #   So the entry CAN happen at X+1

        # UNLESS: the TP detection happens AFTER the entry check in the bar loop!
        # Engine bar loop order at bar i:
        #   1. Execute pending exits → pending_short_exit = False
        #   2. SL/TP check → may set pending_short_exit = True
        #   3. Signal exits
        #   4. Signal entries (blocked by pending_short_exit)

        # So if TP fires at bar i (step 2), pending_short_exit=True
        # Then at step 4, entry is blocked!

        # KEY: At which bar does TP fire for the previous trade?
        # And is the 1st SE signal bar INSIDE the same bar where TP fires?

        # For entry_on_next_bar_open: engine enters at bar i, reads SE[i-1]
        # If TP fires at bar i:
        #   step 2: pending_short_exit = True
        #   step 4: can't enter (pending_short_exit is True)
        # So even though SE[i-1] is True, the entry is blocked!

        # Next bar (i+1):
        #   step 1: pending exit executes, pending_short_exit = False
        #   step 4: reads SE[i] — but SE[i] might be False!
        #   So no entry at i+1 unless SE[i] is also True

        # Wait, but our trades show the engine DOES enter. Let me check the actual
        # trade entry time vs the TP detection bar

        print(f"\n  DETAILED BAR ANALYSIS:")
        # Show bars around the transition
        window_start = tp_detection_bar - pd.Timedelta(hours=1)
        window_end = engine_entry_bar + pd.Timedelta(hours=1)
        w_mask = (idx >= window_start) & (idx <= window_end)

        for ts in idx[w_mask]:
            i = idx.get_loc(ts)
            markers = []
            if ts == tp_detection_bar:
                markers.append("TP_DETECTED")
            if ts == exit_execution_bar:
                markers.append("EXIT_EXECUTES")
            if ts == first_se:
                markers.append("1st_SE")
            if ts == engine_entry_bar:
                markers.append("ENGINE_ENTERS")
            se_val = se[i] if i < len(se) else "?"
            se_prev = se[i - 1] if i > 0 and i - 1 < len(se) else "?"
            print(f"    bar {ts}: SE={se_val}, SE_prev={se_prev}  {'  '.join(markers)}")

    # KEY PATTERN CHECK:
    print("\n\n" + "=" * 120)
    print("PATTERN SUMMARY: Is TP detection bar == (1st SE bar - 30min)?")
    print("If yes, then at the 1st SE bar:")
    print("  Engine: TP fires at step 2, blocks entry at step 4")
    print("  But current code shows engine DOES enter. Let's check why.")
    print("=" * 120)

    for label, trade_1based, first_se_str, second_se_str in unknown_cases:
        prev_trade = trades[trade_1based - 2]
        prev_exit_time = pd.Timestamp(str(prev_trade.exit_time)).tz_localize(None)
        first_se = pd.Timestamp(first_se_str)
        engine_entry_bar = first_se + pd.Timedelta(minutes=30)

        # engine entry time from actual trade
        curr_trade = trades[trade_1based - 1]
        actual_entry = pd.Timestamp(str(curr_trade.entry_time)).tz_localize(None)

        print(f"  {label}: TP_exit={prev_exit_time}, 1st_SE={first_se}, engine_entry={actual_entry}")
        diff = (first_se - prev_exit_time) / pd.Timedelta(minutes=30)
        print(f"    Gap between prev exit and 1st SE: {diff:.0f} bars")
        print(f"    Prev exit reason: {prev_trade.exit_reason}")


asyncio.run(main())
