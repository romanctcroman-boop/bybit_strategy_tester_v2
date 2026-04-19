"""Check strategy config and run live signal generation to match trades."""

import asyncio
import json
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, "D:/bybit_strategy_tester_v2")

STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"


def check_strategy_config():
    conn = sqlite3.connect("data.sqlite3")
    row = conn.execute(
        "SELECT name, parameters, builder_blocks, builder_connections FROM strategies WHERE id=?", (STRATEGY_ID,)
    ).fetchone()
    conn.close()
    if row:
        params = json.loads(row[1]) if row[1] else {}
        blocks = json.loads(row[2]) if row[2] else {}
        json.loads(row[3]) if row[3] else {}
        print(f"Strategy: {row[0]}")
        print(f"Parameters:\n{json.dumps(params, indent=2)[:600]}")
        print(f"\nBlocks:\n{json.dumps(blocks, indent=2)[:800]}")
    else:
        print("Strategy not found!")


async def run_live_signals():
    from backend.backtesting.service import BacktestService
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    conn = sqlite3.connect("data.sqlite3")
    row = conn.execute(
        "SELECT parameters, builder_blocks, builder_connections FROM strategies WHERE id=?", (STRATEGY_ID,)
    ).fetchone()
    conn.close()
    # Build config dict that StrategyBuilderAdapter expects
    builder_blocks = json.loads(row[1]) if row[1] else {}
    builder_connections = json.loads(row[2]) if row[2] else {}
    config = {
        "builder_blocks": builder_blocks,
        "builder_connections": builder_connections,
    }

    svc = BacktestService()
    ohlcv = await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="15",
        start_date=pd.Timestamp("2025-11-01", tz="UTC"),
        end_date=pd.Timestamp("2026-02-23", tz="UTC"),
    )

    adapter = StrategyBuilderAdapter(config)
    signals_df = adapter.generate_signals(ohlcv)

    idx_utc = ohlcv.index.tz_convert("UTC").tz_localize(None) if ohlcv.index.tz is not None else ohlcv.index

    long_sig = signals_df.get("long_entries", pd.Series(False, index=ohlcv.index))
    short_sig = signals_df.get("short_entries", pd.Series(False, index=ohlcv.index))

    # First 20 signals of each type
    nov1 = pd.Timestamp("2025-11-01")
    nov8 = pd.Timestamp("2025-11-08")
    mask = (idx_utc >= nov1) & (idx_utc < nov8)

    long_times = idx_utc[mask][long_sig[mask].values]
    short_times = idx_utc[mask][short_sig[mask].values]

    print(f"\nLive signals Nov 1-7 UTC (Long={len(long_times)}, Short={len(short_times)}):")
    print("Long signal bars:")
    for t in long_times:
        print(f"  UTC {t}  =>  entry_bar {t + pd.Timedelta(minutes=15)}")
    print("Short signal bars:")
    for t in short_times:
        print(f"  UTC {t}  =>  entry_bar {t + pd.Timedelta(minutes=15)}")

    # Check Nov 1 01:45 specifically
    t_check = pd.Timestamp("2025-11-01 01:45")
    if t_check in idx_utc:
        pos = list(idx_utc).index(t_check)
        s = short_sig.iloc[pos] if pos < len(short_sig) else False
        l = long_sig.iloc[pos] if pos < len(long_sig) else False
        print(f"\nNov 1 01:45 UTC: long_sig={l}, short_sig={s}")

    # Show signals dict keys
    print("\nSignal keys:", list(signals_df.keys()) if isinstance(signals_df, dict) else "Series")


check_strategy_config()
asyncio.run(run_live_signals())
