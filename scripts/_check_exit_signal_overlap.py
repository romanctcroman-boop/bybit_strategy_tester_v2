"""
Check: for roots #12/#85/#89/#91, does a crossunder signal fire on the SAME bar
where the prev trade exits via TP?

If the prev trade exits via pending_exit at bar X, and SE[X-1]=True,
then with entry_on_next_bar_open, the entry would be at bar X.
But the position is still "open" when bar X starts (pending exit clears it during
the bar). Can the engine enter on the same bar the exit executes?

Also check: what is the prev trade's exit_time for each root?
"""

import asyncio
import json
import sqlite3
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.core.indicators.momentum import calculate_rsi


async def main():
    svc = BacktestService()
    conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?",
        ("dd2969a2-bbba-410e-b190-be1e8cc50b21",),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    graph = {
        "name": name,
        "blocks": json.loads(br),
        "connections": json.loads(cr),
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    ms = json.loads(gr).get("main_strategy", {})
    if ms:
        graph["main_strategy"] = ms

    candles = await svc._fetch_historical_data(
        "ETHUSDT", "30", pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2026-02-24", tz="UTC")
    )
    btc = await svc._fetch_historical_data(
        "BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), pd.Timestamp("2026-02-24", tz="UTC")
    )
    btc = btc[~btc.index.duplicated(keep="last")]

    # Compute BTC RSI
    btc_rsi_arr = calculate_rsi(btc["close"].values, period=14)
    btc_rsi = pd.Series(btc_rsi_arr, index=btc.index)

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)
    le = np.asarray(signals.entries.values, dtype=bool)
    lx = np.asarray(signals.exits.values, dtype=bool)
    se = np.asarray(signals.short_entries.values, dtype=bool)
    sx = np.asarray(signals.short_exits.values, dtype=bool)

    result = FallbackEngineV4().run(
        BacktestInput(
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
    )
    trades = result.trades

    # TV entry timestamps (UTC) for each root
    tv_entries = {
        12: pd.Timestamp("2025-02-07 05:30:00"),
        85: pd.Timestamp("2025-08-16 14:00:00"),
        89: pd.Timestamp("2025-08-27 12:30:00"),
        91: pd.Timestamp("2025-09-02 18:30:00"),
    }

    for root_tv_idx in [12, 85, 89, 91]:
        # Find the engine trade that corresponds to this root
        tv_entry = tv_entries[root_tv_idx]

        # Find engine trade closest to this area
        best_trade_idx = None
        best_dist = float("inf")
        for i, t in enumerate(trades):
            et = (
                pd.Timestamp(t.entry_time).tz_localize(None)
                if pd.Timestamp(t.entry_time).tzinfo
                else pd.Timestamp(t.entry_time)
            )
            tv_n = tv_entry.tz_localize(None) if tv_entry.tzinfo else tv_entry
            dist = abs((et - tv_n).total_seconds())
            if dist < best_dist and t.direction == "short":
                # Check it's within a reasonable range (5 days)
                if dist < 5 * 86400:
                    best_dist = dist
                    best_trade_idx = i

        if best_trade_idx is None:
            print(f"\nRoot #{root_tv_idx}: No matching engine trade found")
            continue

        eng_trade = trades[best_trade_idx]
        prev_trade = trades[best_trade_idx - 1] if best_trade_idx > 0 else None

        print(f"\n{'=' * 80}")
        print(f"ROOT #{root_tv_idx} (TV trade #{root_tv_idx})")
        print(f"{'=' * 80}")

        if prev_trade:
            prev_exit = pd.Timestamp(prev_trade.exit_time)
            prev_exit_n = prev_exit.tz_localize(None) if prev_exit.tzinfo else prev_exit
            print(
                f"Prev trade #{best_trade_idx}: {prev_trade.direction} exit={prev_exit_n} reason={prev_trade.exit_reason}"
            )

            # Find bar index of prev exit
            prev_exit_idx = None
            for ci, ts in enumerate(candles.index):
                ts_n = ts.tz_localize(None) if ts.tzinfo else ts
                if ts_n == prev_exit_n:
                    prev_exit_idx = ci
                    break

            if prev_exit_idx is not None:
                print(f"Prev exit bar idx: {prev_exit_idx}")

                # With pending exit, TP detected at bar X, exit executes at bar X+1
                # exit_time = bar X (prev_bar_time). So position closes at bar X+1.
                # That means at bar X+1's entry processing, position is empty.

                tp_detect_bar = prev_exit_idx  # This is where TP was detected (exit_time)
                exit_execute_bar = tp_detect_bar + 1  # This is where pending exit runs

                print(f"TP detected at bar: {candles.index[tp_detect_bar]} (exit_time)")
                print(f"Pending exit executes at bar: {candles.index[exit_execute_bar]}")

                # Check signals around exit area
                print(f"\nSignals around exit bar:")
                for k in range(max(0, tp_detect_bar - 2), min(len(candles), tp_detect_bar + 5)):
                    ts = candles.index[k]
                    ts_n = ts.tz_localize(None) if ts.tzinfo else ts
                    btc_rsi_val = btc_rsi.get(ts_n, np.nan)
                    if np.isnan(btc_rsi_val):
                        btc_rsi_val = btc_rsi.get(ts, np.nan)

                    marker = ""
                    if k == tp_detect_bar:
                        marker = " ← TP_DETECTED (exit_time)"
                    if k == exit_execute_bar:
                        marker = " ← EXIT_EXECUTES (position clears)"

                    # With entry_on_next_bar_open: signal at bar k fires entry at bar k+1
                    # So SE[k] would cause entry at k+1
                    entry_bar = f"→entry@{str(candles.index[k + 1])[:16]}" if k + 1 < len(candles) and se[k] else ""

                    print(f"  [{k:5d}] {str(ts_n)[:19]}  SE={se[k]:d}  BTC_RSI={btc_rsi_val:.4f}  {entry_bar}{marker}")

                # KEY CHECK: Is there an SE signal at the exit_execute_bar?
                # With entry_on_next_bar_open, the entry at bar i uses SE[i-1]
                # So at exit_execute_bar (i), the engine checks SE[i-1] = SE[tp_detect_bar]
                print(f"\n  SE at TP detect bar [{tp_detect_bar}]: {se[tp_detect_bar]}")
                print(f"  SE at exit execute bar [{exit_execute_bar}]: {se[exit_execute_bar]}")
                print(
                    f"  → With entry_on_next_bar_open, entry at exit_execute_bar uses SE[{tp_detect_bar}] = {se[tp_detect_bar]}"
                )

                if se[tp_detect_bar]:
                    print(f"\n  ⚠️ SIGNAL AT TP DETECT BAR! The engine would try to enter at exit_execute_bar.")
                    print(f"  But pending_short_exit is cleared BEFORE entry processing → entry proceeds!")
                    print(f"  In TV: TP fires intra-bar → position closes → strategy evals at bar close")
                    print(f"  TV sees SE[tp_detect_bar] at bar close → queues entry for next bar")
                    print(f"  But TV ALSO sees the position just closed → it can enter!")
                    print(f"  So both engine and TV should enter at exit_execute_bar... unless TV behaves differently")

        print(
            f"\nEngine trade #{best_trade_idx + 1}: {eng_trade.direction} entry={eng_trade.entry_time} exit={eng_trade.exit_time}"
        )
        print(f"TV trade #{root_tv_idx}: short entry={tv_entry}")


asyncio.run(main())
