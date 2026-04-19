"""
Deep debug: trace exact signals generated during backtest for Strategy_RSI_L/S_3.
"""

import asyncio
import json
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, "D:/bybit_strategy_tester_v2")

STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"


async def main():
    from backend.backtesting.service import BacktestService
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    # Load strategy from DB
    conn = sqlite3.connect("data.sqlite3")
    row = conn.execute(
        "SELECT name, parameters, builder_blocks, builder_connections, "
        "stop_loss_pct, take_profit_pct, direction, position_size "
        "FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()

    name = row[0]
    params = json.loads(row[1]) if row[1] else {}
    builder_blocks = json.loads(row[2]) if row[2] else []
    builder_connections = json.loads(row[3]) if row[3] else []
    sl_pct = row[4]
    tp_pct = row[5]
    direction = row[6]
    pos_size = row[7]

    print(f"Strategy: {name}")
    print(f"SL={sl_pct}, TP={tp_pct}, direction={direction}, pos_size={pos_size}")
    print(f"Params: {params}")
    print()

    # Build config for adapter - StrategyBuilderAdapter expects {"blocks": [...], "connections": [...]}
    strategy_config = {
        "blocks": builder_blocks,
        "connections": builder_connections,
        "stop_loss_pct": sl_pct,
        "take_profit_pct": tp_pct,
    }

    svc = BacktestService()
    ohlcv = await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="15",
        start_date=pd.Timestamp("2025-11-01", tz="UTC"),
        end_date=pd.Timestamp("2026-02-23", tz="UTC"),
    )

    adapter = StrategyBuilderAdapter(strategy_config)
    signals_df = adapter.generate_signals(ohlcv)

    print(f"Signals type: {type(signals_df)}")
    from backend.backtesting.strategies import SignalResult

    if isinstance(signals_df, SignalResult):
        long_entries = signals_df.entries
        short_entries = signals_df.short_entries
        print(f"Long entries total: {long_entries.sum() if long_entries is not None else 0}")
        print(f"Short entries total: {short_entries.sum() if short_entries is not None else 0}")
    elif isinstance(signals_df, pd.DataFrame):
        long_entries = signals_df.get("long_entries") or signals_df.get("entries")
        short_entries = signals_df.get("short_entries")
    elif isinstance(signals_df, pd.Series):
        long_entries = signals_df == 1
        short_entries = signals_df == -1
    else:
        print(f"Unknown signal type: {type(signals_df)}")
        return

    idx_utc = ohlcv.index.tz_convert("UTC").tz_localize(None) if ohlcv.index.tz is not None else ohlcv.index

    nov1 = pd.Timestamp("2025-11-01")
    nov8 = pd.Timestamp("2025-11-08")
    mask = (idx_utc >= nov1) & (idx_utc < nov8)

    print("\nSignals Nov 1-7 UTC:")
    if long_entries is not None:
        long_times = idx_utc[mask][long_entries[mask].values.astype(bool)]
        print(f"Long entries ({len(long_times)}):")
        for t in long_times:
            print(f"  UTC {t}  =>  entry_bar {t + pd.Timedelta(minutes=15)}")

    if short_entries is not None:
        short_times = idx_utc[mask][short_entries[mask].values.astype(bool)]
        print(f"Short entries ({len(short_times)}):")
        for t in short_times:
            print(f"  UTC {t}  =>  entry_bar {t + pd.Timedelta(minutes=15)}")


asyncio.run(main())
