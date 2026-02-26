"""Check if SE fires at the bar BEFORE prev exit (TP detection bar).
In TV: TP is detected intra-bar on bar X, position closes on bar X.
Entry from bar X-1's signal would fill at bar X's OPEN, but position is still open
(TP hasn't fired yet at OPEN), so entry is BLOCKED by pyramiding=1.

In our engine: TP detected at bar X → pending exit at bar X+1.
On bar X, if SE[X-1] fires, entry would be at bar X (with entry_on_next_bar_open).
But position is still open! Wait...

Actually: with same-bar TP fix, pending exit fires at BAR X (not X+1).
The engine's flow at bar X:
  1. Execute pending exits (TP from bar X-1's check) → position clears
  2. Check entries → SE[X-1]=True, position empty → entry fires

In TV's flow at bar X:
  1. Pending entry from bar X-1's signal fills at bar X's OPEN → blocked by pyramiding
  2. TP/SL check intra-bar → position closes
  3. Strategy evaluates at close → new signal may generate

So the key difference: TV checks pending ENTRY at bar OPEN first, then TP/SL intra-bar.
Our engine checks pending EXIT first, then entries.

For roots #12/#85/#89/#91: Let me check if there's an SE signal 1 bar before prev exit.
"""

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

    open_prices = candles["open"].values
    high_prices = candles["high"].values
    low_prices = candles["low"].values
    close_prices = candles["close"].values

    # For each root, check the TP detection bar (bar before exit)
    roots_data = {
        9: {"tv_signal": "2025-01-28 08:00"},  # TV signal bar from _check_range_filter.py
        12: {"tv_signal": "2025-02-07 05:00"},
        85: {"tv_signal": "2025-08-16 13:30"},
        89: {"tv_signal": "2025-08-27 12:00"},
        91: {"tv_signal": "2025-09-02 18:00"},
        144: {"tv_signal": "2026-02-08 03:00"},
    }

    for root_idx in [12, 85, 89, 91, 144]:  # Focus on same-bar pattern roots
        print(f"\n{'=' * 70}")
        print(f"ROOT #{root_idx}")
        print(f"{'=' * 70}")

        e_trade = engine_trades[root_idx - 1]
        prev_trade = engine_trades[root_idx - 2]

        prev_exit = pd.Timestamp(prev_trade.exit_time)
        prev_entry_price = prev_trade.entry_price

        # Find prev exit bar index
        prev_exit_idx = None
        for idx_c, ts in enumerate(candles.index):
            if ts == prev_exit:
                prev_exit_idx = idx_c
                break

        if prev_exit_idx is None:
            print(f"  Could not find prev exit bar!")
            continue

        print(f"Prev trade #{root_idx - 1}: {prev_trade.direction}, entry_price={prev_entry_price:.2f}")
        print(f"  Entry: {prev_trade.entry_time}")
        print(f"  Exit:  {prev_trade.exit_time} ({prev_trade.exit_reason})")

        # For a short trade with TP=2.3%, TP level = entry_price * (1 - 0.023)
        if prev_trade.direction == "short":
            tp_level = prev_entry_price * (1 - 0.023)
        else:
            tp_level = prev_entry_price * (1 + 0.023)

        print(f"  TP level: {tp_level:.2f}")

        # Check: on which bar was TP actually hit?
        # TP is hit when low <= tp_level (for short) during the bar
        # With same-bar TP fix: exit_time = the bar where TP was first detected
        # That bar's low should be <= tp_level
        tp_bar = prev_exit_idx
        if prev_trade.direction == "short":
            print(
                f"  Bar {candles.index[tp_bar]}: low={low_prices[tp_bar]:.2f}, "
                f"TP hit={'YES' if low_prices[tp_bar] <= tp_level else 'NO'}"
            )

        # Check bar BEFORE exit (where TP detection might have been queued)
        if tp_bar > 0:
            prev_bar = tp_bar - 1
            print(
                f"  Bar before exit {candles.index[prev_bar]}: "
                f"low={low_prices[prev_bar]:.2f}, "
                f"TP hit={'YES' if low_prices[prev_bar] <= tp_level else 'NO'}"
            )

        # KEY CHECK: SE signal at exit bar and bar before exit
        print(f"\n  SE at bars around exit:")
        for k in range(max(0, tp_bar - 3), min(len(se), tp_bar + 4)):
            ts = candles.index[k]
            marker = ""
            if k == tp_bar:
                marker = " ← EXIT BAR"
            if k == tp_bar - 1:
                marker = " ← BAR BEFORE EXIT"
            print(
                f"    {ts}: SE={int(se[k])}, open={open_prices[k]:.2f}, "
                f"high={high_prices[k]:.2f}, low={low_prices[k]:.2f}, "
                f"close={close_prices[k]:.2f}{marker}"
            )

        # Engine's entry signal bar
        e_entry = pd.Timestamp(e_trade.entry_time)
        for idx_c, ts in enumerate(candles.index):
            if ts == e_entry:
                sig_bar = idx_c - 1
                break

        print(f"\n  Engine fires SE at bar: {candles.index[sig_bar]}")
        print(f"  Engine entry at bar: {e_entry}")

        # How many bars between prev exit and engine signal?
        bars_gap = sig_bar - prev_exit_idx
        print(f"  Bars from prev exit to engine signal: {bars_gap}")

        # NEW KEY INSIGHT: check the engine's bar processing at exit bar
        # At exit bar (idx=tp_bar):
        #   1. Execute pending exits: TP from bar tp_bar-1 → position closes
        #   2. Check current bar TP/SL: N/A (position empty)
        #   3. Check entries: se[tp_bar-1] (with entry_on_next_bar_open) → if True, entry fires!
        # BUT: in TV, at bar tp_bar:
        #   1. Pending ENTRY from bar tp_bar-1 fills at OPEN → BLOCKED by pyramiding (position still open!)
        #   2. TP/SL fires intra-bar → position closes
        #   3. Strategy evaluates at close → new signals

        # So the question is: does se[tp_bar - 1] fire?
        # If so, it's the SAME bug as root #144!

        # Wait, but root #12's prev exit is 2025-02-05 18:30 and engine signal is 2025-02-06 14:00.
        # That's 20 hours gap. The SE signal fires long after exit.
        # So this is NOT a same-bar exit+entry issue for these roots.

        # Then WHY does TV skip the 1st signal?
        # Maybe TV also fires the 1st signal but the resulting trade exits differently?

        # Let me check: what happens if we simulate the engine's trade from the 1st signal
        # What's the TP and SL for that trade?
        entry_price = open_prices[sig_bar + 1]  # entry on next bar open
        tp_for_trade = entry_price * (1 - 0.023) if e_trade.direction == "short" else entry_price * (1 + 0.023)
        sl_for_trade = entry_price * (1 + 0.132) if e_trade.direction == "short" else entry_price * (1 - 0.132)

        print(
            f"\n  Engine trade #{root_idx}: entry_price={entry_price:.2f}, "
            f"TP_level={tp_for_trade:.2f}, SL_level={sl_for_trade:.2f}"
        )
        print(f"  Actual exit: {e_trade.exit_time}, reason={e_trade.exit_reason}, exit_price={e_trade.exit_price:.2f}")

        # Now check: TV's trade from the 2nd signal would have different entry/exit
        tv_sig = pd.Timestamp(roots_data[root_idx]["tv_signal"])
        tv_sig_idx = None
        for idx_c, ts in enumerate(candles.index):
            if ts == tv_sig:
                tv_sig_idx = idx_c
                break
        if tv_sig_idx is not None:
            tv_entry_price = open_prices[tv_sig_idx + 1]
            tv_tp = tv_entry_price * (1 - 0.023)
            tv_sl = tv_entry_price * (1 + 0.132)
            print(
                f"\n  TV trade would enter at: {candles.index[tv_sig_idx + 1]}, "
                f"price={tv_entry_price:.2f}, TP={tv_tp:.2f}, SL={tv_sl:.2f}"
            )


asyncio.run(main())
