"""
For ALL 151 engine trades (not just the 6 UNKNOWN), check:
1. How many crossunders occur between the previous trade exit and THIS trade entry?
2. Is this trade entered on the 1st, 2nd, 3rd, etc. crossunder after the previous exit?

Hypothesis: If most trades enter on the 1st crossunder, the 6 UNKNOWN cases are anomalies.
If there's a pattern (e.g., TV always skips when RSI was below 52 during prev trade exit),
we can find it.
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
    le = result.entries.values
    sx = result.short_exits.values
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

    # Compute BTC RSI for cross detection
    btc_close = btc["close"]
    delta = btc_close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    btc_rsi_full = 100 - (100 / (1 + rs))
    btc_rsi = btc_rsi_full.reindex(candles.index, method="ffill")

    # For each SHORT trade, count how many SE crossunders occurred between
    # previous trade exit and this trade's entry signal bar
    cross_short_level = 52.0
    cross_long_level = 24.0

    short_trades = [(i, t) for i, t in enumerate(trades) if t.direction == "short"]

    print("=" * 120)
    print("CROSSUNDER COUNT BETWEEN PREV EXIT AND ENTRY SIGNAL FOR ALL SHORT TRADES")
    print("=" * 120)

    crossunder_counts = []
    for idx_t, (trade_idx, trade) in enumerate(short_trades):
        entry_time = pd.Timestamp(str(trade.entry_time))
        if hasattr(entry_time, "tzinfo") and entry_time.tzinfo:
            entry_time = entry_time.tz_localize(None)

        # The signal bar is entry_time - 30min (entry_on_next_bar_open)
        signal_bar = entry_time - pd.Timedelta(minutes=30)

        # Find previous trade (any direction)
        if trade_idx > 0:
            prev_trade = trades[trade_idx - 1]
            prev_exit = pd.Timestamp(str(prev_trade.exit_time))
            if hasattr(prev_exit, "tzinfo") and prev_exit.tzinfo:
                prev_exit = prev_exit.tz_localize(None)
            # Exit execution bar is prev_exit + 30min
            prev_exit_exec = prev_exit + pd.Timedelta(minutes=30)
        else:
            prev_exit_exec = idx[0]  # Start of data

        # Count SE crossunders between prev_exit_exec and signal_bar
        mask = (idx >= prev_exit_exec) & (idx <= signal_bar)
        n_se_in_window = int(se[mask].sum()) if mask.any() else 0

        # Count RSI crossunders (regardless of range condition)
        rsi_prev_s = btc_rsi.shift(1)
        cross_mask = (rsi_prev_s >= cross_short_level) & (btc_rsi < cross_short_level)
        n_rsi_crosses = int(cross_mask[mask].sum()) if mask.any() else 0

        crossunder_counts.append(n_se_in_window)

        # Only print non-trivial cases (>1 crossunder)
        if n_se_in_window > 1:
            print(
                f"  Trade #{trade_idx + 1}: {n_se_in_window} SE signals between "
                f"{prev_exit_exec} and {signal_bar} "
                f"(entry: {entry_time}, {n_rsi_crosses} RSI crosses)"
            )

    # Statistics
    from collections import Counter

    count_dist = Counter(crossunder_counts)
    print("\n\nDISTRIBUTION OF SE COUNT BETWEEN PREV EXIT AND ENTRY:")
    for k in sorted(count_dist.keys()):
        print(f"  {k} SE signals: {count_dist[k]} trades ({100 * count_dist[k] / len(short_trades):.1f}%)")

    # So for trades where SE count = 1, the engine enters on the FIRST and ONLY crossunder
    # For trades where SE count > 1, the engine enters on the FIRST of multiple

    # Now let's check the TV trades: how many TV trades have SE count > 1?
    # Load TV CSV
    tv_csv_path = r"c:\Users\roman\Downloads\as4.csv"
    tv_df = pd.read_csv(tv_csv_path, sep=";")
    print(f"\n\nTV CSV columns: {tv_df.columns.tolist()}")
    print(f"TV CSV shape: {tv_df.shape}")
    print(f"First rows:\n{tv_df.head(4)}")

    # Parse TV trades
    # The CSV has exit row first, entry row second for each pair
    # Let's get all entry rows for short trades
    # Need to identify the format...


asyncio.run(main())
