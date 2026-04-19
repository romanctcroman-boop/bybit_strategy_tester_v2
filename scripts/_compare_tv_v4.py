"""
Check exit times of our engine trades vs TV to understand divergence.
"""

import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"
TV_CSV = r"C:\Users\roman\Downloads\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-02-23.csv"


def load_ohlcv_like_service():
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
    df = df.set_index("timestamp").drop(columns=["open_time"])
    return df


def load_tv_trades():
    df = pd.read_csv(TV_CSV, encoding="utf-8-sig")
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
    df = df[df["type"].notna() & df["price"].notna()]
    df["datetime"] = pd.to_datetime(df["datetime"], dayfirst=False)
    df["utc"] = df["datetime"].apply(lambda x: x.replace(tzinfo=UTC) - timedelta(hours=3))
    df["direction"] = df["type"].apply(lambda x: "long" if "long" in x.lower() else "short")
    df["is_entry"] = df["type"].apply(lambda x: "entry" in x.lower())
    return df


def main():

    strat_conn = sqlite3.connect(DB_PATH)
    cursor = strat_conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cursor.fetchone()
    col_names = [d[0] for d in cursor.description]
    strat_conn.close()
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

    ohlcv = load_ohlcv_like_service()

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

    engine = BacktestEngine()
    result = engine.run(config, ohlcv, custom_strategy=adapter)

    # Load TV trades
    tv = load_tv_trades()
    tv_entries = tv[tv["is_entry"]].sort_values("trade_num").reset_index(drop=True)
    tv_exits = tv[~tv["is_entry"]].sort_values("trade_num").reset_index(drop=True)

    side_map = {"buy": "long", "sell": "short", "long": "long", "short": "short"}

    print(f"Engine trades: {len(result.trades)}")
    print(f"TV trades: {len(tv_entries)}")

    print("\n=== TRADE-BY-TRADE COMPARISON (engine actual result) ===")
    print(
        f"{'#':>3} {'Dir':6} | {'Our entry UTC':22} {'Our exit UTC':22} {'ExitReason':12} | {'TV entry UTC':22} {'TV exit UTC':22} {'TVsig':8} | {'Match':10}"
    )

    max_trades = max(len(result.trades), len(tv_entries))
    for i in range(min(25, max_trades)):
        # Our trade
        if i < len(result.trades):
            t = result.trades[i]
            our_entry = t.entry_time
            our_exit = t.exit_time
            our_dir = side_map.get(str(t.side).lower(), "?")
            our_exit_comment = getattr(t, "exit_comment", "") or ""
            if hasattr(our_entry, "replace") and our_entry.tzinfo is None:
                our_entry = our_entry.replace(tzinfo=UTC)
            if hasattr(our_exit, "replace") and our_exit.tzinfo is None:
                our_exit = our_exit.replace(tzinfo=UTC)
            our_entry_tv_eq = our_entry + timedelta(minutes=15) if our_entry else None
            f"entry={our_entry} exit={our_exit} ({our_exit_comment[:8]})"
        else:
            our_dir = "?"
            our_entry = None
            our_exit = None
            our_entry_tv_eq = None

        # TV trade
        if i < len(tv_entries):
            tv_row = tv_entries.iloc[i]
            tv_exit_row = tv_exits[tv_exits["trade_num"] == tv_row["trade_num"]]
            tv_entry_time = tv_row["utc"]
            tv_exit_time = tv_exit_row["utc"].iloc[0] if not tv_exit_row.empty else None
            tv_exit_sig = tv_exit_row["signal"].iloc[0] if not tv_exit_row.empty else "?"
            tv_dir = tv_row["direction"]
        else:
            tv_entry_time = None
            tv_exit_time = None
            tv_exit_sig = "?"
            tv_dir = "?"

        # Match check
        if our_entry_tv_eq and tv_entry_time:
            diff_min = abs((our_entry_tv_eq - tv_entry_time).total_seconds()) / 60
            match_str = "MATCH" if diff_min == 0 else f"DIFF({diff_min:.0f}m)"
        else:
            match_str = "N/A"

        our_entry_str = str(our_entry)[:22] if our_entry else "N/A"
        our_exit_str = str(our_exit)[:22] if our_exit else "N/A"
        tv_entry_str = str(tv_entry_time)[:22] if tv_entry_time else "N/A"
        tv_exit_str = str(tv_exit_time)[:22] if tv_exit_time else "N/A"

        dir_str = our_dir if our_dir == tv_dir else f"{our_dir}/{tv_dir}"
        print(
            f"{i + 1:>3} {dir_str:8} | {our_entry_str:22} {our_exit_str:22} {our_exit_comment[:12]:12} | {tv_entry_str:22} {tv_exit_str:22} {tv_exit_sig[:8]:8} | {match_str}"
        )


if __name__ == "__main__":
    main()
