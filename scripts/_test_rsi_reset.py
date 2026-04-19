"""
Test hypothesis: TV requires RSI to "reset" above cross_short_level (52) after a trade
exit before allowing a new short entry. I.e., after a short position is closed, the next
short entry requires RSI to first go above 52 and THEN cross below 52 again.

This is different from just requiring a crossunder — it requires a FRESH crossunder after
the RSI has been above the level post-exit.

Implementation: After each short trade exit, set a flag "need_reset=True".
While need_reset is True, suppress all SE signals.
When BTC RSI goes above cross_short_level (52), clear the flag.
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

    se_orig = result.short_entries.values.copy()
    le_orig = result.entries.values.copy()
    sx = result.short_exits.values.copy()
    lx = result.exits.values.copy()
    idx = candles.index

    # Compute BTC RSI (same as engine: full series then reindex)
    btc_close = btc["close"]
    delta = btc_close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    btc_rsi_full = 100 - (100 / (1 + rs))
    btc_rsi = btc_rsi_full.reindex(candles.index, method="ffill")

    cross_short_level = 52.0
    cross_long_level = 24.0

    # === TEST 1: Baseline (no modification) ===
    bi_base = BacktestInput(
        candles=candles,
        long_entries=le_orig,
        long_exits=lx,
        short_entries=se_orig,
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
    out_base = engine.run(bi_base)
    print(f"BASELINE: {len(out_base.trades)} trades")

    # === TEST 2: Post-exit RSI reset for shorts ===
    # After each short trade exit, suppress SE signals until RSI goes above cross_short_level
    # We need to run the engine iteratively with modified signals. But since our engine
    # takes pre-computed signals, we need a different approach.

    # Approach: Run baseline, get trade exits. Then for each short exit, find when RSI
    # goes back above 52 AFTER the exit, and suppress SE signals between exit and reset.
    # Then re-run the engine with modified signals. Iterate until stable.

    se_modified = se_orig.copy()
    le_modified = le_orig.copy()

    MAX_ITERATIONS = 10
    for iteration in range(MAX_ITERATIONS):
        # Run engine with current signals
        bi = BacktestInput(
            candles=candles,
            long_entries=le_modified,
            long_exits=lx,
            short_entries=se_modified,
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
        out = engine.run(bi)
        trades = out.trades

        # Now apply RSI reset suppression
        se_new = se_orig.copy()  # Always start from original signals
        le_new = le_orig.copy()

        suppressed_count = 0

        for trade in trades:
            if trade.direction == "short":
                exit_time = pd.Timestamp(str(trade.exit_time))
                if hasattr(exit_time, "tzinfo") and exit_time.tzinfo:
                    exit_time = exit_time.tz_localize(None)

                # Find the bar index of the exit execution
                # With pending exits: TP detected at bar X, exit executes at X+1
                # exit_time in trade = bar X (prev_bar_time)
                # So the actual exit execution is at exit_time + 30min
                exit_exec_bar = exit_time + pd.Timedelta(minutes=30)

                if exit_exec_bar not in idx:
                    continue
                exit_idx = idx.get_loc(exit_exec_bar)

                # Find when RSI goes above cross_short_level after exit
                reset_idx = None
                for j in range(exit_idx, len(idx)):
                    if btc_rsi.iloc[j] >= cross_short_level:
                        reset_idx = j
                        break

                if reset_idx is not None and reset_idx > exit_idx:
                    # Suppress SE between exit and reset
                    for j in range(exit_idx, reset_idx):
                        if se_new[j]:
                            se_new[j] = False
                            suppressed_count += 1

            elif trade.direction == "long":
                exit_time = pd.Timestamp(str(trade.exit_time))
                if hasattr(exit_time, "tzinfo") and exit_time.tzinfo:
                    exit_time = exit_time.tz_localize(None)

                exit_exec_bar = exit_time + pd.Timedelta(minutes=30)

                if exit_exec_bar not in idx:
                    continue
                exit_idx = idx.get_loc(exit_exec_bar)

                # Find when RSI goes below cross_long_level after exit
                reset_idx = None
                for j in range(exit_idx, len(idx)):
                    if btc_rsi.iloc[j] <= cross_long_level:
                        reset_idx = j
                        break

                if reset_idx is not None and reset_idx > exit_idx:
                    for j in range(exit_idx, reset_idx):
                        if le_new[j]:
                            le_new[j] = False
                            suppressed_count += 1

        print(f"  Iteration {iteration + 1}: {len(trades)} trades, suppressed {suppressed_count} signals")

        # Check convergence
        if np.array_equal(se_new, se_modified) and np.array_equal(le_new, le_modified):
            print(f"  Converged after {iteration + 1} iterations")
            break

        se_modified = se_new
        le_modified = le_new

    # Final result
    bi_final = BacktestInput(
        candles=candles,
        long_entries=le_modified,
        long_exits=lx,
        short_entries=se_modified,
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
    out_final = engine.run(bi_final)

    print(f"\nFINAL WITH RSI RESET: {len(out_final.trades)} trades (target: 151 TV trades)")

    # Show details of trades around the 6 UNKNOWN cases
    unknown_engine_entries = [
        "2025-02-22 11:00",  # E#23 engine
        "2025-05-09 15:30",  # E#57 engine
        "2025-08-16 01:30",  # E#85 engine
        "2025-08-27 03:00",  # E#89 engine
        "2025-09-02 11:30",  # E#91 engine
        "2025-11-25 00:30",  # E#120 engine
    ]
    unknown_tv_entries = [
        "2025-02-22 15:00",  # E#23 TV
        "2025-05-09 19:30",  # E#57 TV
        "2025-08-16 14:00",  # E#85 TV
        "2025-08-27 12:30",  # E#89 TV
        "2025-09-02 18:30",  # E#91 TV
        "2025-11-25 05:30",  # E#120 TV
    ]

    print("\n\nChecking UNKNOWN cases in modified result:")
    for eng_entry, tv_entry in zip(unknown_engine_entries, unknown_tv_entries):
        eng_ts = pd.Timestamp(eng_entry)
        tv_ts = pd.Timestamp(tv_entry)

        # Find matching trade
        found_eng = False
        found_tv = False
        for t in out_final.trades:
            t_entry = pd.Timestamp(str(t.entry_time))
            if hasattr(t_entry, "tzinfo") and t_entry.tzinfo:
                t_entry = t_entry.tz_localize(None)

            if abs((t_entry - eng_ts).total_seconds()) < 60:
                found_eng = True
            if abs((t_entry - tv_ts).total_seconds()) < 60:
                found_tv = True

        status = ""
        if found_tv and not found_eng:
            status = "✅ FIXED! Now matches TV"
        elif found_eng and not found_tv:
            status = "❌ Still uses engine entry"
        elif found_eng and found_tv:
            status = "?? Both found"
        else:
            status = "?? Neither found"

        print(f"  Engine={eng_entry}, TV={tv_entry}: eng_found={found_eng}, tv_found={found_tv}  {status}")

    # Also compare total trade count breakdown
    short_trades = [t for t in out_final.trades if t.direction == "short"]
    long_trades = [t for t in out_final.trades if t.direction == "long"]
    print(f"\nFinal breakdown: {len(long_trades)}L + {len(short_trades)}S = {len(out_final.trades)} total")
    print(f"TV reference: 29L + 121S = 150 closed + 1 open = 151")


asyncio.run(main())
