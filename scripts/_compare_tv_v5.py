"""
Full comparison: Our engine (post-RSI-fix) vs TV CSV.
Counts total matches and shows first divergence point.
"""

import json
import sqlite3
import sys
from datetime import UTC, datetime

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"
TV_CSV = r"C:\Users\roman\Downloads\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-02-23.csv"


def load_ohlcv():
    conn = sqlite3.connect(DB_PATH)
    start_ms = int(datetime(2025, 11, 1, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime(2026, 2, 23, 23, 59, tzinfo=UTC).timestamp() * 1000)
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


def load_tv_trades():
    """Load TV trades from CSV (2 rows per trade, Russian column names)."""
    df = pd.read_csv(TV_CSV, encoding="utf-8-sig")
    # Rename to English
    df.columns = [
        "trade_num",
        "type",
        "datetime",
        "signal",
        "price",
        "size_qty",
        "size_price",
        "pnl_usd",
        "pnl_pct",
        "fav_usd",
        "fav_pct",
        "max_adv_usd",
        "max_adv_pct",
        "cum_pnl_usd",
        "cum_pnl_pct",
    ]
    # Filter entry rows only
    entries = df[df["type"].str.startswith("Entry")].copy()
    # Convert MSK timestamp (UTC+3) to UTC
    entries["dt_utc"] = pd.to_datetime(entries["datetime"], format="%Y-%m-%d %H:%M", utc=False)
    entries["dt_utc"] = entries["dt_utc"].apply(lambda x: x.replace(tzinfo=None) - pd.Timedelta(hours=3))
    entries["dt_utc"] = pd.to_datetime(entries["dt_utc"], utc=True)
    entries["side"] = entries["type"].apply(lambda x: "buy" if "long" in x.lower() else "sell")
    # Get exit info
    exits = df[df["type"].str.startswith("Exit")].copy()
    exits["exit_utc"] = pd.to_datetime(exits["datetime"], format="%Y-%m-%d %H:%M", utc=False)
    exits["exit_utc"] = exits["exit_utc"].apply(lambda x: x.replace(tzinfo=None) - pd.Timedelta(hours=3))
    exits["exit_utc"] = pd.to_datetime(exits["exit_utc"], utc=True)
    exits["exit_signal"] = exits["signal"]
    # Merge by trade_num
    tv = entries.merge(exits[["trade_num", "exit_utc", "exit_signal"]], on="trade_num", how="left")
    tv = tv.sort_values("trade_num").reset_index(drop=True)
    return tv


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

    from backend.backtesting.engine import BacktestEngine
    from backend.backtesting.models import BacktestConfig

    params = json.loads(strat["parameters"]) if isinstance(strat["parameters"], str) else strat["parameters"]

    config = BacktestConfig(
        symbol="BTCUSDT",
        interval="15",
        start_date=datetime(2025, 11, 1, tzinfo=UTC),
        end_date=datetime(2026, 2, 23, 23, 59, tzinfo=UTC),
        initial_capital=10000.0,
        commission_value=float(params.get("_commission", 0.0007)),
        slippage=float(params.get("_slippage", 0.0005)),
        leverage=float(params.get("_leverage", 10.0)),
        position_size=0.1,
        pyramiding=int(params.get("_pyramiding", 1)),
        direction="both",
        stop_loss=0.032,
        take_profit=0.015,
    )

    engine = BacktestEngine()
    result = engine.run(config, ohlcv, custom_strategy=adapter)

    our_trades = result.trades
    tv_trades = load_tv_trades()

    print(f"Our trades: {len(our_trades)}")
    print(f"TV trades: {len(tv_trades)}")
    print()

    # Compare trade by trade (our entry +15min = TV entry)
    matches = 0
    entry_matches = 0
    print(
        f"{'#':<4} {'Dir':<5} {'Our Entry+15m':<28} {'TV Entry UTC':<28} {'E.Match':<8} {'Our Exit':<28} {'TV Exit':<28} {'X.Match'}"
    )
    max_compare = min(len(our_trades), len(tv_trades))
    first_diff = None
    for i in range(max_compare):
        our = our_trades[i]
        tv = tv_trades.iloc[i]

        our_entry = pd.Timestamp(our.entry_time) + pd.Timedelta(minutes=15)
        tv_entry = tv["dt_utc"]
        our_exit = pd.Timestamp(our.exit_time)
        tv_exit = tv["exit_utc"]

        entry_match = abs((our_entry - tv_entry).total_seconds()) < 60
        exit_match = abs((our_exit - tv_exit).total_seconds()) < 60

        if entry_match and exit_match:
            matches += 1
        if entry_match:
            entry_matches += 1
        if not entry_match and first_diff is None:
            first_diff = i + 1

        em = "Y" if entry_match else "N"
        xm = "Y" if exit_match else f"N{int((our_exit - tv_exit).total_seconds() // 60)}m"
        print(
            f"{i + 1:<4} {our.side:<5} {str(our_entry)[:25]:<28} {str(tv_entry)[:25]:<28} {em:<8} {str(our_exit)[:25]:<28} {str(tv_exit)[:25]:<28} {xm}"
        )

    print()
    print(f"Entry matches: {entry_matches}/{max_compare}")
    print(f"Full matches (entry+exit): {matches}/{max_compare}")
    if first_diff:
        print(f"First divergence at trade #{first_diff}")
    else:
        print("All compared trades match!")
    print(f"Missing trades vs TV: {len(tv_trades) - len(our_trades)}")


if __name__ == "__main__":
    main()
