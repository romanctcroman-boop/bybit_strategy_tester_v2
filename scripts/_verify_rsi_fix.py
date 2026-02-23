"""
Verify the fix: run actual strategy adapter and count signals with the new RSI formula.
Then compare against TV trade count (129 trades).
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


def load_ohlcv():
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
    return df.set_index("timestamp").drop(columns=["open_time"])


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cursor.fetchone()
    col_names = [d[0] for d in cursor.description]
    conn.close()
    strat = dict(zip(col_names, row, strict=True))

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

    ohlcv = load_ohlcv()
    signals = adapter.generate_signals(ohlcv)

    long_arr = np.asarray(signals.entries.values, dtype=bool)
    short_arr = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(long_arr), dtype=bool)
    )

    print(f"Total long signals: {long_arr.sum()}")
    print(f"Total short signals: {short_arr.sum()}")

    # Check bar 212 specifically (05:00 UTC Nov 3 — TV's Trade #2 signal)
    bar_212_ts = pd.Timestamp("2025-11-03 05:00:00", tz="UTC")
    idx_212 = ohlcv.index.get_loc(bar_212_ts) if bar_212_ts in ohlcv.index else None
    if idx_212 is not None:
        print(f"\nBar 212 ({bar_212_ts}): long={long_arr[idx_212]}, short={short_arr[idx_212]}")

    # Show all long signals on Nov 3
    print("\n=== LONG SIGNALS ON NOV 3 UTC ===")
    nov3_start = pd.Timestamp("2025-11-03 00:00:00", tz="UTC")
    nov3_end = pd.Timestamp("2025-11-04 00:00:00", tz="UTC")
    for i, ts in enumerate(ohlcv.index):
        if nov3_start <= ts < nov3_end and long_arr[i]:
            print(f"  Bar {i}: {ts} close={ohlcv['close'].iloc[i]:.2f} → TV entry={ts + pd.Timedelta(minutes=15)}")

    # Now run the full backtest engine and count trades
    print("\n=== RUNNING FULL BACKTEST ===")
    from backend.backtesting.engine import BacktestEngine
    from backend.backtesting.models import BacktestConfig

    params = json.loads(strat["parameters"]) if isinstance(strat["parameters"], str) else strat["parameters"]

    config = BacktestConfig(
        symbol="BTCUSDT",
        interval="15",
        start_date=datetime(2025, 11, 1, tzinfo=UTC),
        end_date=datetime(2026, 2, 23, tzinfo=UTC),
        initial_capital=10000.0,
        commission_value=float(params.get("_commission", 0.0007)),
        slippage=float(params.get("_slippage", 0.0005)),
        leverage=float(params.get("_leverage", 10.0)),
        position_size=0.1,
        pyramiding=int(params.get("_pyramiding", 1)),
        direction="both",
        stop_loss=0.032,  # SL=3.2%
        take_profit=0.015,  # TP=1.5%
    )

    engine = BacktestEngine()
    result = engine.run(config, ohlcv, custom_strategy=adapter)

    print(f"Total trades: {len(result.trades)}")
    print(f"Result type: {type(result)}")
    print(f"Result fields: {[f for f in dir(result) if not f.startswith('_')]}")
    if hasattr(result, "metrics") and result.metrics:
        m = result.metrics
        print(f"Metrics type: {type(m)}")
        print(f"Metrics fields: {[f for f in dir(m) if not f.startswith('_')][:20]}")

    # Compare first 5 trades vs TV
    print("\n=== FIRST 10 TRADES (Our Engine) ===")
    print(f"{'#':<3} {'Dir':<6} {'Entry UTC':<32} {'Exit UTC':<32} {'Type':<20} {'TV+15min'}")
    for i, trade in enumerate(result.trades[:10]):
        entry_ts = pd.Timestamp(trade.entry_time)
        exit_ts = pd.Timestamp(trade.exit_time)
        tv_entry = entry_ts + pd.Timedelta(minutes=15)
        direction = trade.side
        exit_type = trade.exit_comment or "?"
        print(f"{i + 1:<3} {direction:<6} {entry_ts!s:<32} {exit_ts!s:<32} {exit_type:<20} {tv_entry}")


if __name__ == "__main__":
    main()
