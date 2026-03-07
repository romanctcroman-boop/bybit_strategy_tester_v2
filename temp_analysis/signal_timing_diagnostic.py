"""
Diagnostic: compare signal timestamps vs OHLCV timestamps to find timing offset.
Tests the Strategy_MACD_07 signal generation pipeline.
"""

import asyncio
import json
import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")


async def main():
    # Load the strategy
    import sqlite3

    conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
    cursor = conn.execute(
        "SELECT builder_blocks, builder_connections FROM strategies WHERE id = '963da4df-8e09-4c8e-a361-3143914b3581'"
    )
    row = cursor.fetchone()
    conn.close()

    blocks = json.loads(row[0])
    conns = json.loads(row[1])

    # Build strategy graph
    strategy_graph = {
        "name": "Strategy_MACD_07",
        "description": "",
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }

    # Fetch OHLCV with warmup (same as router does)
    from datetime import datetime, timedelta

    from backend.backtesting.service import BacktestService

    svc = BacktestService()
    start_date = datetime(2025, 3, 1)
    end_date = datetime(2025, 3, 15)
    warmup_start = start_date - timedelta(days=45)

    print(f"Fetching OHLCV from {warmup_start} to {end_date}...")
    ohlcv_full = await svc._fetch_historical_data(
        symbol="ETHUSDT",
        interval="30",
        start_date=warmup_start,
        end_date=end_date,
        market_type="linear",
    )

    print(f"Full OHLCV: {len(ohlcv_full)} bars, first={ohlcv_full.index[0]}, last={ohlcv_full.index[-1]}")

    # Generate signals on full data (with warmup)
    from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter

    adapter = StrategyBuilderAdapter(strategy_graph)
    signals = adapter.generate_signals(ohlcv_full)

    print("\nSignals on FULL OHLCV (with warmup):")
    print(f"  short_entries dtype: {type(signals.short_entries)}")
    print(f"  short_entries count: {signals.short_entries.sum()}")
    print("  First 5 short entry bars:")
    short_idx = signals.short_entries[signals.short_entries].index[:5]
    for ts in short_idx:
        bar_idx = list(ohlcv_full.index).index(ts)
        print(f"    [{bar_idx}] {ts} | close={ohlcv_full.loc[ts, 'close']:.4f}")

    # Now slice to start_date (as the router does)
    _cutoff = start_date
    _mask = ohlcv_full.index >= _cutoff
    _n_warmup = int((~_mask).sum())
    print(f"\nWarmup bars: {_n_warmup}")

    ohlcv_trimmed = ohlcv_full.loc[_mask].copy()
    print(f"Trimmed OHLCV: {len(ohlcv_trimmed)} bars, first={ohlcv_trimmed.index[0]}")

    # Slice signals
    _warm_index = ohlcv_trimmed.index
    for _attr in ("entries", "exits", "long_entries", "long_exits", "short_entries", "short_exits"):
        _arr = getattr(signals, _attr, None)
        if _arr is not None and hasattr(_arr, "loc"):
            _sliced = _arr.loc[_warm_index]
            setattr(signals, _attr, _sliced)

    print("\nSignals on TRIMMED OHLCV (from start_date):")
    print(f"  short_entries count: {signals.short_entries.sum()}")
    print("  First 5 short entry bars (SIGNAL BARS = where crossover detected):")
    short_idx2 = signals.short_entries[signals.short_entries].index[:5]
    for ts in short_idx2:
        bar_idx = list(ohlcv_trimmed.index).index(ts)
        print(f"    signal_bar [{bar_idx}] {ts} | close={ohlcv_trimmed.loc[ts, 'close']:.4f}")
        # Entry would be at bar_idx+1
        if bar_idx + 1 < len(ohlcv_trimmed):
            entry_ts = ohlcv_trimmed.index[bar_idx + 1]
            entry_open = ohlcv_trimmed.iloc[bar_idx + 1]["open"]
            print(f"    entry_bar  [{bar_idx + 1}] {entry_ts} | open={entry_open:.4f} (entry price)")

    print("\n\n=== CRITICAL CHECK: Signal/OHLCV alignment ===")
    print(f"OHLCV trimmed index[0]: {ohlcv_trimmed.index[0]}")
    print(f"short_entries index[0]: {signals.short_entries.index[0]}")
    print(f"Match: {ohlcv_trimmed.index[0] == signals.short_entries.index[0]}")


asyncio.run(main())
