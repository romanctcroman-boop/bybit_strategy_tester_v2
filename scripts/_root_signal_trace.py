"""Deep analysis: for each root divergence, verify preceding trade is truly identical,
and check exactly which signals the engine would see after prev exit."""

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

    # Root trades (1-indexed): #9, #12, #85, #89, #91, #144
    roots = [9, 12, 85, 89, 91, 144]

    for root_idx in roots:
        print(f"\n{'=' * 70}")
        print(f"ROOT #{root_idx}")
        print(f"{'=' * 70}")

        e_trade = engine_trades[root_idx - 1]  # 0-indexed
        prev_trade = engine_trades[root_idx - 2] if root_idx > 1 else None

        # Engine trade info
        print(f"\nEngine trade #{root_idx}:")
        print(f"  Direction: {e_trade.direction}")
        print(f"  Entry: {e_trade.entry_time}")
        print(f"  Exit:  {e_trade.exit_time}")
        print(f"  Entry price: {e_trade.entry_price}")

        if prev_trade:
            print(f"\nPrevious trade #{root_idx - 1}:")
            print(f"  Direction: {prev_trade.direction}")
            print(f"  Entry: {prev_trade.entry_time}")
            print(f"  Exit:  {prev_trade.exit_time}")
            print(f"  Exit reason: {prev_trade.exit_reason}")

        # Find corresponding TV trade
        # TV times are Moscow (UTC+3)
        # Engine entry time
        e_entry = pd.Timestamp(e_trade.entry_time)

        # For roots, check what signal bar corresponds to the entry
        # With entry_on_next_bar_open=True, signal is at bar i-1, entry at bar i
        signal_bar_idx = None
        for idx_c, ts in enumerate(candles.index):
            if ts == e_entry:
                signal_bar_idx = idx_c - 1  # signal was at previous bar
                break

        if signal_bar_idx is not None:
            signal_ts = candles.index[signal_bar_idx]
            print(f"\nEngine signal bar: {signal_ts}")
            print(f"  SE[signal_bar] = {se[signal_bar_idx]}")

        # Check: after prev trade exit, when does the position become empty?
        if prev_trade and e_trade.direction == "short":
            prev_exit = pd.Timestamp(prev_trade.exit_time)
            # Find prev_exit bar index
            prev_exit_idx = None
            for idx_c, ts in enumerate(candles.index):
                if ts == prev_exit:
                    prev_exit_idx = idx_c
                    break

            if prev_exit_idx is not None:
                # Now trace SE signals from prev exit bar onward
                print(f"\nPrev exit bar idx: {prev_exit_idx} = {candles.index[prev_exit_idx]}")

                # Key question: was there a pending exit on the bar AFTER prev exit?
                # If prev exit was TP/SL, the exit might be "pending" and execute at next bar
                print(f"Prev exit reason: {prev_trade.exit_reason}")

                # With same-bar TP fix, exit time = the bar where TP was triggered
                # Not the bar after. So position is clear from prev_exit_idx onwards.

                # But with entry_on_next_bar_open:
                # The first POSSIBLE entry is the bar AFTER the first SE signal bar after prev exit
                # I.e., SE[k]=True where k >= prev_exit_idx → entry at bar k+1
                # BUT: can k == prev_exit_idx? Can we fire a signal on the same bar as exit?

                print(f"\nSE signals from prev exit bar onward:")
                count = 0
                for k in range(prev_exit_idx, min(prev_exit_idx + 100, len(se))):
                    if se[k]:
                        count += 1
                        ts = candles.index[k]
                        entry_bar = candles.index[k + 1] if k + 1 < len(candles) else "END"
                        marker = " ← ENGINE ENTRY" if k + 1 < len(candles) and candles.index[k + 1] == e_entry else ""
                        print(f"  SE=1 at bar {ts}, entry would be {entry_bar}{marker}")
                        if count >= 10:
                            print(f"  ... (showing first 10)")
                            break

                # KEY INSIGHT: check if the signal fires on the SAME bar as prev exit
                if prev_exit_idx < len(se) and se[prev_exit_idx]:
                    print(f"\n*** SIGNAL ON SAME BAR AS PREV EXIT! ***")
                    print(f"  Bar: {candles.index[prev_exit_idx]}")
                    print(
                        f"  This means: with entry_on_next_bar_open, entry would be at {candles.index[prev_exit_idx + 1]}"
                    )
                    print(f"  But prev trade exits at this bar (pending from bar before)")
                    print(f"  In TV: entry at bar+1 OPEN would find position still open (exit happens intra-bar)")
                    print(f"  So TV blocks this entry (pyramiding=1), engine allows it")


asyncio.run(main())
