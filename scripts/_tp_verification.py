"""
BAR MAGNIFIER HYPOTHESIS:

TradingView's bar magnifier uses lower timeframe data to more precisely
determine WHEN within a bar the SL/TP is hit.

With bar magnifier enabled (default), if the TP level is hit at a specific
point within the bar, TV might record the exit at a DIFFERENT time than
our bar-close based detection.

BUT — from the comparison, TV and engine exit times match EXACTLY (0 bars diff).
So the bar magnifier doesn't change the EXIT bar.

HOWEVER: bar magnifier might affect the EXIT PRICE differently. If the TP
fills at a slightly different price within the bar, the TP % might be
slightly different, which could cascade to slightly different capital,
which could affect the NEXT trade's position size... but no, with
position_size=0.001 (fractional), this doesn't affect entry/exit timing.

NEW HYPOTHESIS: What about TradingView's "recalculate after order fills"?

In TV strategy settings, there's a checkbox "Recalculate after order fills"
(similar to calc_on_order_fills=true in Pine). When enabled:
- After a TP/SL fill, the strategy recalculates ALL indicators on that same bar
- This means RSI might be recomputed, and the crossunder detection runs again

With default settings, calc_on_order_fills=false, but recalculate_after_order=true
might be a different thing.

Actually, let me look at the TV strategy settings more carefully.

In TradingView strategy properties:
- "Recalculate: After order is filled" - this is process_orders_on_close

Actually no. Let me check the actual Pine Script strategy() parameters:
1. calc_on_every_tick — recalc on each tick
2. calc_on_order_fills — recalc when an order fills
3. process_orders_on_close — orders process at bar close instead of next bar open

If calc_on_order_fills=true:
- When a TP fills, the strategy recalculates
- This could detect a new crossunder on the same bar
- And issue a new entry order
- Which would execute at the next bar's open

Actually, let's check if the TV CSV shows any pattern where the TV entry
matches the bar AFTER the TP fill vs 2 bars after.

For our engine with pending_exit:
- Bar X: TP condition met → pending_short_exit=True
- Bar X+1: pending exit executes, position flat. ALSO: checks se[X]
  (signal from bar X). But blocked by pending_short_exit.
  After exit executes: pending_short_exit=False. But entry check already passed.
- Bar X+2: checks se[X+1]. If True → entry at X+2

For TV with process_orders_on_close:
- Bar X: strategy code runs (sees RSI crossunder or not), issues entry if crossunder
  Then: TP order fills (position closes)
  Then: if calc_on_order_fills=true: strategy recalculates, sees crossunder again
  Then: entry order from recalculation fires at bar X+1 open

So with calc_on_order_fills=true, TV could enter 1 bar EARLIER than our engine
when TP and SE are on the same bar. But that's the opposite of what we see
(TV enters LATER, not earlier).

Wait — no. Let me reconsider.

TV without calc_on_order_fills:
- Bar X close: strategy runs once. If TP condition met AND SE crossunder:
  Both TP exit and entry signal happen.
  TP fills (closes position), entry fires (new position at bar X+1 open)

TV with calc_on_order_fills:
- Bar X close: strategy runs. TP fills.
  Strategy recalculates. If SE crossunder still true, entry fires.
  Same result as without.

Hmm, in both cases the behavior should be the same for bar-close evaluation.

Let me look at this from yet another angle. The TV CSV exit time is the
exit bar time. But what does "exit time" mean for TP?

TV TP exit: The TP is a limit order. In backtesting:
- Without bar magnifier: TP fills at bar close if low <= TP price (for short)
  or high >= TP price (for long). Fill price = TP level.
- With bar magnifier: TV looks at 1m bars within the 30m bar to find
  exactly when the TP level was hit. Exit time = the 30m bar time,
  but the fill happens at the 1m bar where it was hit.

This means the strategy might see different bars as the "exit bar" with vs
without bar magnifier. With bar magnifier, a TP that would normally hit
on bar X might instead be detected on bar X+1 if the 1m data shows the
low was actually not reached on bar X but on bar X+1.

OR: with bar magnifier, a TP hit on bar X's first 1m candle means the
strategy has the ENTIRE rest of bar X to evaluate and potentially fire
a new entry — which wouldn't happen without bar magnifier.

Let me check: for the cases where TV and engine agree on exit time,
could bar magnifier cause a different interpretation of WHEN within
the bar the TP was hit, affecting what happens next?

Actually, let me think more simply.

SCENARIO A (No bar magnifier, our engine):
- 30m bar X: Low reaches TP → TP detected.
  pending_short_exit=True
- 30m bar X+1: Exit executes. But entry signal from bar X is blocked
  by pending_short_exit.
  If se[X+1]=True after exit, entry fires at X+2.

SCENARIO B (TV with bar magnifier):
- 30m bar X, 1m bar X:05: Low reaches TP → TP fills immediately
  Position is now FLAT within bar X.
- 30m bar X close: strategy evaluates. Position is FLAT.
  If crossunder at bar X: can enter! Entry at bar X+1 open.

This would cause TV to enter EARLIER than our engine, not later.
But we see TV entering LATER. So this doesn't explain it.

Unless... the bar magnifier shows that the TP was hit on a LATER bar
than our engine detects it, not earlier!

Let me check: do we have cases where our engine's TP detection is
maybe happening 1 bar too early?

CHECKING: For each TP exit in the 5 UNKNOWN cases, verify that the
30m bar's low actually reaches the TP price.
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

    lows = candles["low"].values
    highs = candles["high"].values
    opens = candles["open"].values
    closes = candles["close"].values
    idx_arr = candles.index

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

    # For 5 UNKNOWN cases, check prev trade TP verification
    prev_trade_nums = [22, 84, 88, 90]  # prev trade for E#23, E#85, E#89, E#91
    # E#120's prev is a long trade (#119), different TP direction

    print("=" * 140)
    print("TP EXIT VERIFICATION FOR PREV TRADES OF 5 UNKNOWN CASES")
    print("=" * 140)

    for eng_num in [23, 85, 89, 91, 120]:
        prev_trade = trades[eng_num - 2]
        exit_time = pd.Timestamp(str(prev_trade.exit_time))
        if exit_time.tzinfo:
            exit_time = exit_time.tz_localize(None)

        entry_price = prev_trade.entry_price
        exit_price = prev_trade.exit_price
        direction = prev_trade.direction

        # Calculate expected TP level
        if direction == "short":
            tp_level = entry_price * (1 - 0.023)  # Short TP = entry * (1 - TP%)
        else:
            tp_level = entry_price * (1 + 0.023)  # Long TP = entry * (1 + TP%)

        # Find the exit bar position
        exit_pos = None
        for j, ts in enumerate(idx_arr):
            if ts == exit_time:
                exit_pos = j
                break

        print(f"\nPrev Trade #{eng_num - 1} ({direction}):")
        print(f"  Entry: {prev_trade.entry_time} @ {entry_price}")
        print(f"  Exit:  {exit_time} @ {exit_price}")
        print(f"  Expected TP level: {tp_level:.5f}")
        print(f"  Exit reason: {prev_trade.exit_reason}")

        if exit_pos is not None:
            # Check the exit bar and surrounding bars
            for j in range(max(0, exit_pos - 1), min(len(idx_arr), exit_pos + 3)):
                bar_time = idx_arr[j]
                o, h, l, c = opens[j], highs[j], closes[j], lows[j]
                se_val = se[j]
                tp_hit = False
                if direction == "short":
                    tp_hit = l <= tp_level
                else:
                    tp_hit = h >= tp_level

                marker = ""
                if j == exit_pos:
                    marker = " ← EXIT BAR (TP detect)"
                if j == exit_pos + 1:
                    marker = " ← EXIT EXEC BAR"

                print(f"  {bar_time}: O={o:.2f} H={h:.2f} L={l:.2f} C={c:.2f} | TP_hit={tp_hit} | SE={se_val}{marker}")

                # For the exit bar, check how deep the low is below TP
                if j == exit_pos and direction == "short":
                    penetration = tp_level - l
                    print(f"    TP penetration: {penetration:.2f} ({penetration / entry_price * 100:.4f}%)")

    # IMPORTANT CHECK: For E#120, the prev trade is a LONG trade
    # Let's also look at what happens between these trades
    print("\n\n" + "=" * 140)
    print("KEY INSIGHT: Let's check the SAME-BAR TP issue from TV's perspective")
    print("=" * 140)
    print("""
    In our engine:
    - Bar X: TP condition met → pending_short_exit=True
    - Bar X+1: Exit executes (open price). Entry blocked by pending_short_exit.
    
    In TV with process_orders_on_close=true:
    - Bar X: Strategy code runs. TP fills at bar close. 
      Entry signal also evaluates at bar close.
      Since position is being closed by TP at bar close, 
      can an entry signal fire on the SAME bar?
      
    Actually in TV: 
    - Orders from PREVIOUS bar execute at THIS bar's open
    - Strategy code runs at THIS bar's close
    - New orders from this bar execute at NEXT bar's open
    
    For TP: The TP is a standing order. It fills when price reaches the level.
    With bar magnifier: it fills at the 1m candle where price reaches TP.
    Without bar magnifier: it fills at bar close if the condition was met.
    
    KEY: In TV, the TP order fills DURING the bar (intra-bar).
    After it fills, the position is FLAT.
    At bar close, the strategy code runs.
    If there's a crossunder at bar close, the strategy can see it and issue entry.
    The entry order executes at the NEXT bar's open.
    
    In our engine:
    The TP check happens in the bar loop.
    If TP condition met → pending_short_exit=True.
    On the SAME bar iteration (later in the loop), entry is blocked by pending_short_exit.
    
    So the difference is:
    - TV: TP fills mid-bar → position flat → bar-close strategy code can issue entry
    - Engine: TP detected → pending exit set → entry blocked on same bar
    
    But this should only affect the case where TP and SE are on the SAME bar!
    
    Let me check: Is there a case where the TP bar (bar X) has a crossunder,
    but our engine blocks the entry because pending_short_exit is True?
    
    Actually, with entry_on_next_bar_open=True:
    - Engine reads se[i-1] at bar i
    - If TP detected at bar X: pending_short_exit=True
    - At bar X+1: exit executes, pending_short_exit cleared
      But entry check reads se[X] (which was the TP bar)
      Wait: the check at bar X+1 is `se[X+1-1] = se[X]`
      And pending_short_exit might already be False after exit execution...
      
    Let me re-read the engine code to understand the exact order.
    """)


asyncio.run(main())
