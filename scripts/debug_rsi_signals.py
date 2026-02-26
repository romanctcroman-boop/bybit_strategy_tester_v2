"""
Deep debug: run Strategy_RSI_LS_11 signal generation and check first signals.
Compare with TV's expected first trade at 2025-01-01T10:30 UTC.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "d:\\bybit_strategy_tester_v2")

import pandas as pd


async def main():
    from backend.backtesting.service import BacktestService
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    svc = BacktestService()
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 1, 10, tzinfo=timezone.utc)

    # Strategy graph from DB
    strategy_graph = {
        "name": "Strategy_RSI_LS_11",
        "interval": "30",
        "blocks": [
            {
                "id": "price_input",
                "type": "price",
                "category": "input",
                "name": "PRICE",
                "x": 50,
                "y": 200,
                "params": {"source": "close"},
            },
            {
                "id": "rsi_block",
                "type": "rsi",
                "category": "indicator",
                "name": "RSI",
                "x": 400,
                "y": 100,
                "params": {
                    "period": 14,
                    "source": "close",
                    "timeframe": "30",
                    "use_btc_source": True,
                    "use_long_range": True,
                    "long_rsi_more": 28,
                    "long_rsi_less": 70,
                    "use_short_range": True,
                    "short_rsi_more": 50,
                    "short_rsi_less": 70,
                    "use_cross_level": True,
                    "cross_long_level": 24,
                    "cross_short_level": 52,
                    "opposite_signal": False,
                    "use_cross_memory": False,
                    "cross_memory_bars": 5,
                },
            },
            {
                "id": "static_sltp",
                "type": "static_sltp",
                "category": "exit",
                "name": "Static SL/TP",
                "x": 400,
                "y": 300,
                "params": {"take_profit_percent": 2.3, "stop_loss_percent": 13.2, "sl_type": "average_price"},
            },
            {
                "id": "strategy_node",
                "type": "strategy",
                "category": "output",
                "name": "STRATEGY",
                "x": 700,
                "y": 200,
                "params": {},
            },
        ],
        "connections": [
            {
                "id": "c1",
                "source": {"blockId": "rsi_block", "portId": "long"},
                "target": {"blockId": "strategy_node", "portId": "entry_long"},
            },
            {
                "id": "c2",
                "source": {"blockId": "rsi_block", "portId": "short"},
                "target": {"blockId": "strategy_node", "portId": "entry_short"},
            },
            {
                "id": "c3",
                "source": {"blockId": "static_sltp", "portId": "config"},
                "target": {"blockId": "strategy_node", "portId": "exit_config"},
            },
        ],
    }

    # Fetch ETH data
    print("Fetching ETHUSDT 30m...")
    eth_ohlcv = await svc._fetch_historical_data(
        symbol="ETHUSDT", interval="30", start_date=start, end_date=end, market_type="linear"
    )
    print(f"ETH data: {len(eth_ohlcv)} bars, {eth_ohlcv.index[0]} to {eth_ohlcv.index[-1]}")

    # Fetch BTC data with warmup
    import pandas as _pd

    warmup_delta = _pd.Timedelta(minutes=500 * 30)
    btc_start = start - warmup_delta
    print(f"\nFetching BTCUSDT 30m with warmup from {btc_start}...")
    btc_ohlcv = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=btc_start, end_date=end, market_type="linear"
    )
    print(f"BTC data: {len(btc_ohlcv)} bars, {btc_ohlcv.index[0]} to {btc_ohlcv.index[-1]}")

    # Create adapter WITH BTC
    adapter = StrategyBuilderAdapter(strategy_graph, btcusdt_ohlcv=btc_ohlcv)

    # Generate signals
    print("\nGenerating signals...")
    signals = adapter.generate_signals(eth_ohlcv)

    # Check entry signals
    entries = signals.entries  # long
    short_entries = signals.short_entries  # short

    print(f"\nLong entries: {entries.sum() if entries is not None else 0}")
    print(f"Short entries: {short_entries.sum() if short_entries is not None else 0}")

    if short_entries is not None and short_entries.sum() > 0:
        first_short = eth_ohlcv[short_entries].head(10)
        print("\nFirst 10 short entry bars:")
        print(first_short[["close"]].to_string())
        print("\nClose prices at signal bars:")
        for ts, row in first_short.iterrows():
            print(f"  {ts}: close={row['close']:.2f}")

    if entries is not None and entries.sum() > 0:
        first_long = eth_ohlcv[entries].head(10)
        print("\nFirst 10 long entry bars:")
        for ts, row in first_long.iterrows():
            print(f"  {ts}: close={row['close']:.2f}")

    # Show BTC RSI around TV's first signal bar
    import numpy as np

    from backend.core.indicators import calculate_rsi

    # TV says: first entry at 2025-01-01T10:30 UTC (bar with close=3334.62)
    # Signal should fire on bar 2025-01-01T13:00 UTC (open of next bar is entry)
    btc_close = btc_ohlcv["close"]
    btc_rsi_arr = calculate_rsi(btc_close.values, period=14)
    btc_rsi = pd.Series(btc_rsi_arr, index=btc_close.index)

    # Filter to the strategy period
    btc_rsi_strategy = btc_rsi.loc["2025-01-01":"2025-01-02"]
    print("\nBTC RSI for first 2 days of strategy:")
    print(btc_rsi_strategy.head(30).to_string())

    # Show ETH RSI cross-level for those bars
    eth_rsi_arr = calculate_rsi(eth_ohlcv["close"].values, period=14)
    eth_rsi = pd.Series(eth_rsi_arr, index=eth_ohlcv.index)
    print("\nETH RSI for first 2 days:")
    print(eth_rsi.head(30).to_string())


asyncio.run(main())
