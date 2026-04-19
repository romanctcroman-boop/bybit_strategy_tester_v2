"""
Run backtest directly and get detailed trade list.
Uses the same code path as the API but captures trades.
"""

import sys

sys.path.insert(0, "d:\\bybit_strategy_tester_v2")

import asyncio
from datetime import UTC, datetime, timezone

import pandas as pd


async def main():
    # Load strategy from DB
    import sqlite3

    from backend.backtesting.engine import BacktestEngine
    from backend.backtesting.models import BacktestConfig, StrategyType
    from backend.backtesting.service import BacktestService
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
    c = conn.cursor()
    c.execute(
        "SELECT builder_blocks, builder_connections, builder_graph FROM strategies WHERE id = '01cd8861-60eb-40dd-a9a9-8baa6f2db0fa'"
    )
    row = c.fetchone()
    conn.close()

    import json

    blocks = json.loads(row[0]) if row[0] else []
    connections = json.loads(row[1]) if row[1] else []
    builder_graph = json.loads(row[2]) if row[2] else {}

    strategy_graph = {
        "blocks": blocks,
        "connections": connections,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if builder_graph.get("main_strategy"):
        strategy_graph["main_strategy"] = builder_graph["main_strategy"]

    adapter = StrategyBuilderAdapter(strategy_graph)

    # Load BTC OHLCV with warmup
    svc = BacktestService()
    start_date = datetime(2025, 1, 1, tzinfo=UTC)
    end_date = datetime(2026, 2, 25, tzinfo=UTC)

    _btc_start = start_date - pd.Timedelta(minutes=500 * 30)
    btc_ohlcv = await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="30",
        start_date=_btc_start,
        end_date=end_date,
        market_type="linear",
    )
    print(f"BTC OHLCV: {len(btc_ohlcv)} bars")
    adapter = StrategyBuilderAdapter(strategy_graph, btcusdt_ohlcv=btc_ohlcv)

    # Load ETH OHLCV
    eth_ohlcv = await svc._fetch_historical_data(
        symbol="ETHUSDT",
        interval="30",
        start_date=start_date,
        end_date=end_date,
        market_type="linear",
    )
    print(f"ETH OHLCV: {len(eth_ohlcv)} bars")

    config = BacktestConfig(
        symbol="ETHUSDT",
        interval="30",
        start_date=start_date,
        end_date=end_date,
        strategy_type=StrategyType.CUSTOM,
        strategy_params={},
        initial_capital=10000.0,
        position_size=0.1,
        leverage=10,
        direction="both",
        stop_loss=0.132,
        take_profit=0.023,
        taker_fee=0.0007,
        maker_fee=0.0007,
        slippage=0.0,
        pyramiding=1,
        market_type="linear",
    )

    engine = BacktestEngine()
    result = engine.run(config, eth_ohlcv, custom_strategy=adapter)

    trades = result.trades or []
    print(f"\nTotal trades: {len(trades)}")
    print(f"Net profit: {result.metrics.net_profit:.4f}")
    print(f"Win rate: {result.metrics.win_rate:.4f}")
    print()

    # Print all trades
    print(
        f"{'#':3s} {'Side':5s} {'Entry':10s} {'Exit':10s} {'PnL':10s} {'Entry time':25s} {'Exit time':25s} {'ExitReason':20s}"
    )
    print("-" * 130)
    for i, t in enumerate(trades, 1):
        side = getattr(t, "side", "N/A")
        side_str = str(side.value) if hasattr(side, "value") else str(side)
        entry_price = getattr(t, "entry_price", 0)
        exit_price = getattr(t, "exit_price", 0)
        pnl = getattr(t, "pnl", 0)
        entry_time = getattr(t, "entry_time", None)
        exit_time = getattr(t, "exit_time", None)
        exit_comment = getattr(t, "exit_comment", "") or ""
        print(
            f"{i:3d} {side_str:5s} {entry_price:10.4f} {exit_price:10.4f} {pnl:10.4f} {entry_time!s:25s} {exit_time!s:25s} {exit_comment:20s}"
        )


asyncio.run(main())
