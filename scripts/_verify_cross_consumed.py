"""
Verify hypothesis: TV skips crossunder if the RSI_prev bar (T-1 where SE[T]=True)
was DURING the previous trade (i.e., position was still open at T-1).

For each UNKNOWN case:
- 1st SE at bar T1: check if T1-30min was during the previous trade
- 2nd SE at bar T2: check if T2-30min was during the previous trade
"""

import asyncio
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())


async def main():
    from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
    from backend.backtesting.interfaces import BacktestInput, TradeDirection
    from backend.backtesting.service import BacktestService
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    svc = BacktestService()

    START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
    END_DATE = pd.Timestamp("2026-02-24T00:00:00", tz="UTC")

    # Load data
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
    idx = candles.index

    # Run backtest to get actual trade list
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

    # Compute BTC RSI for reference
    btc_close = btc["close"]
    btc_eth_aligned = btc_close.reindex(candles.index, method="ffill")
    delta = btc_eth_aligned.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    btc_rsi = 100 - (100 / (1 + rs))

    # UNKNOWN cases: (label, prev_trade_1based, eng_entry, tv_entry)
    # prev_trade_1based: the 1-based engine trade number for the DIVERGENT trade
    # We need the trade BEFORE it (prev_trade_1based - 2 for 0-based index)
    unknown_cases = [
        ("E#23", 23, "2025-02-22 11:00", "2025-02-22 15:00"),
        ("E#57", 57, "2025-05-09 15:30", "2025-05-09 19:30"),
        ("E#85", 85, "2025-08-16 01:30", "2025-08-16 14:00"),
        ("E#89", 89, "2025-08-27 03:00", "2025-08-27 12:30"),
        ("E#91", 91, "2025-09-02 11:30", "2025-09-02 18:30"),
        ("E#120", 120, "2025-11-25 00:30", "2025-11-25 05:30"),
    ]

    print("=" * 140)
    print("HYPOTHESIS: TV skips crossunder if RSI_prev bar was during previous trade")
    print("A crossunder at bar T means: BTC_RSI[T-1] >= 52 AND BTC_RSI[T] < 52")
    print("If bar T-1 was during the previous trade, TV considers this cross 'consumed'")
    print("=" * 140)

    for label, trade_1based, eng_entry_str, tv_entry_str in unknown_cases:
        prev_idx = trade_1based - 2  # 0-based index of the trade BEFORE the divergent one
        prev_trade = trades[prev_idx]
        prev_exit_time = pd.Timestamp(prev_trade.exit_time)
        prev_entry_time = pd.Timestamp(prev_trade.entry_time)
        # Make tz-naive for comparison with candles index
        if hasattr(prev_exit_time, "tzinfo") and prev_exit_time.tzinfo:
            prev_exit_time_naive = prev_exit_time.tz_localize(None)
        else:
            prev_exit_time_naive = prev_exit_time
        if hasattr(prev_entry_time, "tzinfo") and prev_entry_time.tzinfo:
            prev_entry_time_naive = prev_entry_time.tz_localize(None)
        else:
            prev_entry_time_naive = prev_entry_time

        eng_entry = pd.Timestamp(eng_entry_str)
        tv_entry = pd.Timestamp(tv_entry_str)

        print(f"\n{'=' * 100}")
        print(f"{label}: prev_trade #{prev_idx + 1} ({prev_trade.direction})")
        print(f"  Prev entry: {prev_trade.entry_time}")
        print(f"  Prev exit:  {prev_trade.exit_time} ({prev_trade.exit_reason})")
        print(f"  Engine entry: {eng_entry}, TV entry: {tv_entry}")

        # Find all SE=True bars between prev_exit and TV_entry + 1bar
        window = (idx >= prev_exit_time_naive - pd.Timedelta(hours=1)) & (idx <= tv_entry + pd.Timedelta(minutes=30))
        se_bars = []
        for ts in idx[window]:
            i = idx.get_loc(ts)
            if se[i]:
                se_bars.append((ts, i))

        print(f"  SE=True bars in window:")
        for ts, i in se_bars:
            prev_bar = ts - pd.Timedelta(minutes=30)
            # Was prev_bar during the previous trade?
            during_trade = prev_bar >= prev_entry_time_naive and prev_bar < prev_exit_time_naive

            rsi_at_i = btc_rsi.iloc[i] if i < len(btc_rsi) else np.nan
            rsi_prev_bar_idx = idx.get_loc(prev_bar) if prev_bar in idx else None
            rsi_at_prev = btc_rsi.iloc[rsi_prev_bar_idx] if rsi_prev_bar_idx is not None else np.nan

            status = "IN POSITION" if during_trade else "FLAT"
            marker = " *** SKIPPED BY TV" if during_trade and ts != tv_entry else ""
            print(f"    SE bar {ts}: BTC_RSI[{prev_bar}]={rsi_at_prev:.2f} -> BTC_RSI[{ts}]={rsi_at_i:.2f}")
            print(
                f"      prev_bar status: {status} (trade entered {prev_trade.entry_time}, exits {prev_trade.exit_time}){marker}"
            )

        # KEY CHECK: Was the 1st SE's prev bar during previous trade?
        if se_bars:
            first_se_ts, _ = se_bars[0]
            first_prev_bar = first_se_ts - pd.Timedelta(minutes=30)
            first_during = first_prev_bar >= prev_entry_time_naive and first_prev_bar < prev_exit_time_naive

            if len(se_bars) > 1:
                second_se_ts, _ = se_bars[1]
                second_prev_bar = second_se_ts - pd.Timedelta(minutes=30)
                second_during = second_prev_bar >= prev_entry_time_naive and second_prev_bar < prev_exit_time_naive
            else:
                second_during = None

            print(f"\n  VERDICT: 1st SE prev bar during trade? {first_during}")
            if second_during is not None:
                print(f"           2nd SE prev bar during trade? {second_during}")

            if first_during and (second_during is False or second_during is None):
                print(f"  ✅ HYPOTHESIS CONFIRMED for {label}")
            else:
                print(f"  ❌ HYPOTHESIS FAILED for {label}")


asyncio.run(main())
