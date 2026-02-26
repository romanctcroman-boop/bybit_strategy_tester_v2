"""
For each of the 6 UNKNOWN cases, count SE crossunders between:
1. prev exit execution bar → engine entry signal bar (should be 1)
2. prev exit execution bar → TV entry signal bar (should be 1 or more)

Also: for ALL 121 short trades that are exact matches, verify they ALL
enter on the 1st crossunder (confirming that "1st crossunder" is the normal behavior).

This tells us: is our engine ALWAYS correct in taking the 1st crossunder?
Or is TV sometimes skipping the 1st?
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
    idx = candles.index

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
    idx_arr = candles.index

    # Load TV trades
    tv_csv_path = r"c:\Users\roman\Downloads\as4.csv"
    tv_df = pd.read_csv(tv_csv_path, sep=";")

    # Parse TV short entries
    entry_rows = tv_df[tv_df["Тип"].str.strip() == "Entry short"]
    tv_short_entries = []
    for _, row in entry_rows.iterrows():
        dt_str = row["Дата и время"].strip()
        # Parse Moscow time (UTC+3)
        dt = pd.Timestamp(dt_str) - pd.Timedelta(hours=3)
        price = float(str(row["Цена USDT"]).replace("\xa0", "").replace(",", ".").replace(" ", ""))
        tv_short_entries.append((int(row["№ Сделки"]), dt, price))

    print(f"Engine short trades: {sum(1 for t in trades if t.direction == 'short')}")
    print(f"TV short entries: {len(tv_short_entries)}")

    # For the 6 UNKNOWN cases, we know the engine trade numbers
    # E#23, E#57, E#85, E#89, E#91, E#120
    unknown_engine = [23, 57, 85, 89, 91, 120]

    print("\n" + "=" * 140)
    print("ANALYSIS: SE COUNT BETWEEN PREV EXIT AND ENTRY FOR 6 UNKNOWN CASES")
    print("=" * 140)

    # Build a lookup: bar index → position in candles index
    idx_list = list(idx_arr)
    idx_pos = {t: i for i, t in enumerate(idx_list)}

    for eng_trade_num in unknown_engine:
        trade = trades[eng_trade_num - 1]  # 0-indexed
        prev_trade = trades[eng_trade_num - 2] if eng_trade_num > 1 else None

        entry_time = pd.Timestamp(str(trade.entry_time))
        if entry_time.tzinfo:
            entry_time = entry_time.tz_localize(None)
        signal_bar = entry_time - pd.Timedelta(minutes=30)

        if prev_trade:
            exit_time = pd.Timestamp(str(prev_trade.exit_time))
            if exit_time.tzinfo:
                exit_time = exit_time.tz_localize(None)
            # Exit execution bar (for pending exit, exit_time is the detection bar,
            # execution is next bar)
            exit_exec_bar = exit_time + pd.Timedelta(minutes=30)
        else:
            exit_exec_bar = idx_arr[0]

        # Count SE crossunders from exit_exec_bar to signal_bar (inclusive)
        mask_eng = (idx_arr >= exit_exec_bar) & (idx_arr <= signal_bar)
        n_se_to_engine = int(se[mask_eng].sum())

        # Find matching TV trade
        # Look for TV trade with closest entry time to our engine entry
        eng_entry_utc = entry_time
        best_tv = None
        best_diff = pd.Timedelta(hours=999)
        for tv_num, tv_dt, tv_price in tv_short_entries:
            diff = abs(tv_dt - eng_entry_utc)
            if diff < best_diff:
                best_diff = diff
                best_tv = (tv_num, tv_dt, tv_price)

        if best_tv:
            tv_num, tv_entry_dt, _ = best_tv
            tv_signal_bar = tv_entry_dt - pd.Timedelta(minutes=30)

            # Count SE from exit_exec to TV signal bar
            mask_tv = (idx_arr >= exit_exec_bar) & (idx_arr <= tv_signal_bar)
            n_se_to_tv = int(se[mask_tv].sum())

            # List all SE bars in the window up to TV entry
            se_bars_in_window = idx_arr[mask_tv & (se == True)]

            # Get RSI at each SE bar
            rsi_at_se_bars = []
            for sb in se_bars_in_window:
                pos = idx_pos.get(sb)
                if pos and pos > 0:
                    rsi_prev = rsi_vals[pos - 1]
                    rsi_curr = rsi_vals[pos]
                    rsi_at_se_bars.append((sb, rsi_prev, rsi_curr))

            print(f"\nEngine Trade #{eng_trade_num} (Short)")
            print(f"  Prev exit exec bar:    {exit_exec_bar}")
            print(f"  Engine signal bar:     {signal_bar} → entry: {entry_time}")
            print(f"  TV signal bar:         {tv_signal_bar} → entry: {tv_entry_dt} (TV #{tv_num})")
            print(f"  SE count to ENGINE:    {n_se_to_engine}")
            print(f"  SE count to TV:        {n_se_to_tv}")
            if n_se_to_tv > 1:
                print(f"  TV SKIPS {n_se_to_tv - 1} crossunder(s)")
            print(f"  SE bars in window (to TV):")
            for sb, rsi_p, rsi_c in rsi_at_se_bars:
                marker = "← ENGINE" if sb == signal_bar else ""
                marker2 = "← TV" if sb == tv_signal_bar else ""
                print(f"    {sb}: RSI {rsi_p:.2f} → {rsi_c:.2f} (drop={rsi_p - rsi_c:.2f}) {marker} {marker2}")

    # Now: for all EXACT match short trades, verify they all enter on 1st crossunder
    print("\n\n" + "=" * 140)
    print("VERIFICATION: EXACT MATCH SHORT TRADES — ALL ENTER ON 1ST SE?")
    print("=" * 140)

    # The known near-match engine trade numbers (from summary)
    near_match_eng = {9, 23, 57, 60, 85, 89, 91, 120}  # near matches
    engine_only = {12, 58, 59, 92}  # engine-only
    skip_trades = near_match_eng | engine_only

    multi_se_count = 0
    single_se_count = 0
    zero_se_count = 0

    for i, t in enumerate(trades):
        if t.direction != "short":
            continue
        trade_num = i + 1
        if trade_num in skip_trades:
            continue

        entry_time = pd.Timestamp(str(t.entry_time))
        if entry_time.tzinfo:
            entry_time = entry_time.tz_localize(None)
        signal_bar = entry_time - pd.Timedelta(minutes=30)

        if i > 0:
            prev_t = trades[i - 1]
            exit_time = pd.Timestamp(str(prev_t.exit_time))
            if exit_time.tzinfo:
                exit_time = exit_time.tz_localize(None)
            exit_exec_bar = exit_time + pd.Timedelta(minutes=30)
        else:
            exit_exec_bar = idx_arr[0]

        mask = (idx_arr >= exit_exec_bar) & (idx_arr <= signal_bar)
        n_se = int(se[mask].sum())

        if n_se == 0:
            zero_se_count += 1
            print(f"  ⚠️ Trade #{trade_num}: 0 SE signals! exit_exec={exit_exec_bar}, signal_bar={signal_bar}")
        elif n_se == 1:
            single_se_count += 1
        else:
            multi_se_count += 1
            # Find all SE bars
            se_bars = idx_arr[mask & (se == True)]
            print(f"  ⚠️ Trade #{trade_num}: {n_se} SE signals! First: {se_bars[0]}, Signal: {signal_bar}")

    print(f"\nExact-match short trades:")
    print(f"  1 SE (normal):    {single_se_count}")
    print(f"  0 SE (anomaly):   {zero_se_count}")
    print(f"  >1 SE (multi):    {multi_se_count}")


asyncio.run(main())
