"""
DEEP ANALYSIS: What makes the 5 skipped 1st crossunders different from
the 109 normal crossunders that DO trigger trades?

Hypothesis: Maybe TV has a minimum RSI drop threshold, or requires RSI to
have been above the level for a minimum number of bars before the cross counts.

Check for each of the 109+5 first crossunders:
- RSI drop magnitude (prev - curr)
- How many consecutive bars RSI was above 52 before the crossunder
- The previous bar's RSI distance from 52 (how firmly above)
- Whether the crossunder was "barely" below 52 or significantly below
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

    # The 5 skipped 1st crossunder bars (from previous analysis)
    skipped_bars = [
        pd.Timestamp("2025-02-22 10:30:00"),  # E#23
        pd.Timestamp("2025-08-16 01:00:00"),  # E#85
        pd.Timestamp("2025-08-27 02:30:00"),  # E#89
        pd.Timestamp("2025-09-02 11:00:00"),  # E#91
        pd.Timestamp("2025-11-25 00:00:00"),  # E#120
    ]
    skipped_set = set(skipped_bars)

    # Near/engine-only/cascade trades to skip in "normal" analysis
    skip_trades = {9, 12, 23, 57, 58, 59, 60, 85, 89, 91, 92, 120}

    # Collect features for NORMAL crossunders (109 exact-match trades)
    normal_features = []
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

        # Find signal bar position
        pos = None
        for j, ts in enumerate(idx_arr):
            if ts == signal_bar:
                pos = j
                break
        if pos is None or pos < 2:
            continue

        rsi_prev = rsi_vals[pos - 1]  # bar before signal bar
        rsi_curr = rsi_vals[pos]  # signal bar RSI
        drop = rsi_prev - rsi_curr
        margin_below = 52.0 - rsi_curr  # how far below 52

        # Count consecutive bars RSI was above 52 before crossunder
        consec_above = 0
        for k in range(pos - 1, -1, -1):
            if rsi_vals[k] >= 52.0:
                consec_above += 1
            else:
                break

        # Distance of prev bar RSI from 52
        dist_from_52 = rsi_prev - 52.0

        normal_features.append(
            {
                "trade_num": trade_num,
                "signal_bar": signal_bar,
                "rsi_prev": rsi_prev,
                "rsi_curr": rsi_curr,
                "drop": drop,
                "margin_below": margin_below,
                "consec_above": consec_above,
                "dist_from_52": dist_from_52,
            }
        )

    # Collect features for SKIPPED crossunders
    skipped_features = []
    for sb in skipped_bars:
        pos = None
        for j, ts in enumerate(idx_arr):
            if ts == sb:
                pos = j
                break
        if pos is None or pos < 2:
            continue

        rsi_prev = rsi_vals[pos - 1]
        rsi_curr = rsi_vals[pos]
        drop = rsi_prev - rsi_curr
        margin_below = 52.0 - rsi_curr

        consec_above = 0
        for k in range(pos - 1, -1, -1):
            if rsi_vals[k] >= 52.0:
                consec_above += 1
            else:
                break

        dist_from_52 = rsi_prev - 52.0

        skipped_features.append(
            {
                "signal_bar": sb,
                "rsi_prev": rsi_prev,
                "rsi_curr": rsi_curr,
                "drop": drop,
                "margin_below": margin_below,
                "consec_above": consec_above,
                "dist_from_52": dist_from_52,
            }
        )

    # Print comparison
    nf = pd.DataFrame(normal_features)
    sf = pd.DataFrame(skipped_features)

    print("=" * 120)
    print("SKIPPED 1st CROSSUNDERS (5 cases)")
    print("=" * 120)
    for f in skipped_features:
        print(
            f"  {f['signal_bar']}: RSI {f['rsi_prev']:.2f}→{f['rsi_curr']:.2f}, "
            f"drop={f['drop']:.2f}, below_52={f['margin_below']:.2f}, "
            f"consec_above={f['consec_above']}, dist_from_52={f['dist_from_52']:.2f}"
        )

    print("\n" + "=" * 120)
    print("STATISTICS COMPARISON")
    print("=" * 120)
    for col in ["drop", "margin_below", "consec_above", "dist_from_52", "rsi_prev"]:
        n_vals = nf[col]
        s_vals = sf[col]
        print(f"\n  {col}:")
        print(
            f"    Normal  (109): min={n_vals.min():.2f}, max={n_vals.max():.2f}, "
            f"mean={n_vals.mean():.2f}, median={n_vals.median():.2f}"
        )
        print(
            f"    Skipped  (5):  min={s_vals.min():.2f}, max={s_vals.max():.2f}, "
            f"mean={s_vals.mean():.2f}, median={s_vals.median():.2f}"
        )

    # Check: are ALL skipped crossunders below normal thresholds?
    print("\n\n" + "=" * 120)
    print("THRESHOLD ANALYSIS: Can we find a threshold that separates skipped from normal?")
    print("=" * 120)

    # For each feature, check if there's a threshold that separates all 5 skipped
    # from all 109 normal
    for col in ["drop", "margin_below", "consec_above", "dist_from_52", "rsi_prev"]:
        s_max = sf[col].max()
        s_min = sf[col].min()
        n_below_smax = (nf[col] <= s_max).sum()
        n_above_smin = (nf[col] >= s_min).sum()
        print(f"\n  {col}:")
        print(f"    Skipped range: [{s_min:.2f}, {s_max:.2f}]")
        print(f"    Normal trades with {col} <= skipped_max ({s_max:.2f}): {n_below_smax} of 109")
        print(f"    Normal trades with {col} >= skipped_min ({s_min:.2f}): {n_above_smin} of 109")

    # NEW: Check "bars since exit" — maybe TV has a minimum cooldown
    print("\n\n" + "=" * 120)
    print("BARS SINCE PREVIOUS EXIT")
    print("=" * 120)

    # For skipped crossunders: bars between prev_exit_exec and the crossunder
    skipped_trade_nums = [23, 85, 89, 91, 120]
    for eng_num, sb in zip(skipped_trade_nums, skipped_bars):
        prev_trade = trades[eng_num - 2]
        exit_time = pd.Timestamp(str(prev_trade.exit_time))
        if exit_time.tzinfo:
            exit_time = exit_time.tz_localize(None)
        exit_exec = exit_time + pd.Timedelta(minutes=30)
        bars_gap = int((sb - exit_exec).total_seconds() / 1800)
        print(f"  E#{eng_num}: exit_exec={exit_exec}, 1st_SE={sb}, gap={bars_gap} bars")

    # For normal trades: bars between prev_exit_exec and entry signal
    normal_gaps = []
    for f in normal_features:
        trade_num = f["trade_num"]
        trade = trades[trade_num - 1]
        if trade_num > 1:
            prev_trade = trades[trade_num - 2]
            exit_time = pd.Timestamp(str(prev_trade.exit_time))
            if exit_time.tzinfo:
                exit_time = exit_time.tz_localize(None)
            exit_exec = exit_time + pd.Timedelta(minutes=30)
            bars_gap = int((f["signal_bar"] - exit_exec).total_seconds() / 1800)
        else:
            bars_gap = 999
        normal_gaps.append(bars_gap)

    ng = np.array(normal_gaps)
    print(f"\n  Normal gaps: min={ng.min()}, max={ng.max()}, mean={ng.mean():.1f}, median={np.median(ng):.1f}")
    # Show distribution of small gaps
    for threshold in [1, 2, 3, 5, 10, 20, 30]:
        count = (ng <= threshold).sum()
        print(f"    Normal trades with gap <= {threshold}: {count}")


asyncio.run(main())
