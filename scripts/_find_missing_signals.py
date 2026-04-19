"""
Identify the 5 missing trades: TV has 129, we have 124.
Compare TV entries to our engine entries to find which TV trades we skip.
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
    end_ms = int(datetime(2026, 2, 23, tzinfo=UTC).timestamp() * 1000)
    df = pd.read_sql_query(
        "SELECT open_time, open_price as open, high_price as high, "
        "low_price as low, close_price as close, volume "
        "FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
        "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
        conn,
        params=(start_ms, end_ms),
    )
    conn.close()
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("timestamp").drop(columns=["open_time"])


def load_tv_entries():
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
    entries = df[df["type"].str.startswith("Entry")].copy()
    entries["dt_utc"] = pd.to_datetime(entries["datetime"], format="%Y-%m-%d %H:%M", utc=False)
    entries["dt_utc"] = entries["dt_utc"].apply(lambda x: x.replace(tzinfo=None) - pd.Timedelta(hours=3))
    entries["dt_utc"] = pd.to_datetime(entries["dt_utc"], utc=True)
    entries["side"] = entries["type"].apply(lambda x: "buy" if "long" in x.lower() else "sell")
    # TV entry bar = dt_utc - 15min (since TV shows bar OPEN, signal was at previous bar close)
    entries["signal_bar_utc"] = entries["dt_utc"] - pd.Timedelta(minutes=15)
    return entries.sort_values("trade_num").reset_index(drop=True)


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

    import numpy as np

    long_arr = np.asarray(signals.entries.values, dtype=bool)
    short_arr = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(long_arr), dtype=bool)
    )

    tv_entries = load_tv_entries()

    print(f"TV total entries: {len(tv_entries)}")
    print(f"Our long signals: {long_arr.sum()}, short signals: {short_arr.sum()}")
    print()

    # Check each TV signal bar: does our signal array have a signal there?
    print("=== TV ENTRIES AND WHETHER WE HAVE SIGNAL AT THAT BAR ===")
    print(f"{'TV#':<5} {'Side':<5} {'TV Entry+15min (UTC)':<30} {'Signal bar (UTC)':<30} {'Our signal?':<12} {'Close'}")
    missing = []
    for _, tv in tv_entries.iterrows():
        signal_bar = tv["signal_bar_utc"]
        if signal_bar in ohlcv.index:
            idx = ohlcv.index.get_loc(signal_bar)
            our_long = bool(long_arr[idx])
            our_short = bool(short_arr[idx])
            our_sig = our_long if tv["side"] == "buy" else our_short
            close = ohlcv["close"].iloc[idx]
            if not our_sig:
                missing.append({"tv_num": tv["trade_num"], "side": tv["side"], "bar": signal_bar, "close": close})
                print(
                    f"{tv['trade_num']:<5} {tv['side']:<5} {str(tv['dt_utc'])[:28]:<30} {str(signal_bar)[:28]:<30} {'MISSING!':<12} {close:.2f}"
                )
        else:
            print(
                f"{tv['trade_num']:<5} {tv['side']:<5} {str(tv['dt_utc'])[:28]:<30} {str(signal_bar)[:28]:<30} {'NOT IN DATA'}"
            )

    print(f"\nTotal TV entries without our signal: {len(missing)}")
    for m in missing:
        print(f"  Trade #{m['tv_num']}: {m['side']} at signal bar {m['bar']} (close={m['close']:.2f})")


if __name__ == "__main__":
    main()
