"""
Debug script: Replicate EXACTLY what BacktestService._fetch_historical_data does,
then run the engine's _run_fallback manually and trace the first trade.
"""

import json
import sqlite3
import sys
from datetime import UTC, datetime

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"


def load_strategy():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cursor.fetchone()
    col_names = [d[0] for d in cursor.description]
    conn.close()
    return dict(zip(col_names, row, strict=True))


def load_ohlcv_like_service():
    """Replicate BacktestService._fetch_historical_data via direct SQL."""
    conn = sqlite3.connect(DB_PATH)
    start_ms = int(datetime(2025, 11, 1, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime(2026, 2, 23, tzinfo=UTC).timestamp() * 1000)

    df = pd.read_sql_query(
        "SELECT open_time, open_price as open, high_price as high, "
        "low_price as low, close_price as close, volume "
        "FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
        "AND open_time >= ? AND open_time <= ? "
        "ORDER BY open_time ASC",
        conn,
        params=(start_ms, end_ms),
    )
    conn.close()

    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    df = df.drop(columns=["open_time"])
    print(f"Loaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    return df


def main():
    strat = load_strategy()

    builder_blocks = (
        json.loads(strat["builder_blocks"]) if isinstance(strat["builder_blocks"], str) else strat["builder_blocks"]
    )
    builder_connections = (
        json.loads(strat["builder_connections"])
        if isinstance(strat["builder_connections"], str)
        else strat["builder_connections"]
    )
    builder_graph_raw = (
        json.loads(strat["builder_graph"]) if isinstance(strat["builder_graph"], str) else strat["builder_graph"]
    )

    strategy_graph = {
        "name": strat["name"],
        "description": strat.get("description") or "",
        "blocks": builder_blocks,
        "connections": builder_connections,
        "market_type": "linear",
        "direction": "both",
        "interval": "15",
    }
    if builder_graph_raw and builder_graph_raw.get("main_strategy"):
        strategy_graph["main_strategy"] = builder_graph_raw["main_strategy"]

    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    adapter = StrategyBuilderAdapter(strategy_graph)

    ohlcv = load_ohlcv_like_service()

    # Generate signals
    signals = adapter.generate_signals(ohlcv)

    long_arr = np.asarray(signals.entries.values, dtype=bool)
    short_arr = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(long_arr), dtype=bool)
    )

    print(f"\nSignals: long={long_arr.sum()}, short={short_arr.sum()}")
    print(f"First short signal bar: {np.where(short_arr)[0][0] if short_arr.sum() > 0 else 'NONE'}")
    print(f"First long signal bar: {np.where(long_arr)[0][0] if long_arr.sum() > 0 else 'NONE'}")

    # Check bar 7 specifically
    print(f"\nBar 7 (01:45 UTC): long={long_arr[7]} short={short_arr[7]}")

    # Now ACTUALLY run the engine to see what it returns
    from datetime import datetime

    from backend.backtesting.engine import BacktestEngine
    from backend.backtesting.models import BacktestConfig, StrategyType

    config = BacktestConfig(
        symbol="BTCUSDT",
        interval="15",
        start_date=datetime(2025, 11, 1, tzinfo=UTC),
        end_date=datetime(2026, 2, 23, tzinfo=UTC),
        strategy_type=StrategyType.CUSTOM,
        strategy_params={},
        initial_capital=10000.0,
        position_size=0.1,
        leverage=10.0,
        direction="both",
        stop_loss=0.032,
        take_profit=0.015,
        taker_fee=0.0007,
        maker_fee=0.0007,
        slippage=0.0005,
        pyramiding=1,
        market_type="linear",
    )

    print("\n=== RUNNING BacktestEngine.run() ===")
    engine = BacktestEngine()
    result = engine.run(config, ohlcv, custom_strategy=adapter)

    if result.trades:
        print(f"\nTotal trades from engine: {len(result.trades)}")
        print("\nFirst 5 trades:")
        for t in result.trades[:5]:
            print(f"  side={t.side} entry_time={t.entry_time} entry_price={t.entry_price:.4f}")
    else:
        print("No trades returned!")


if __name__ == "__main__":
    main()
