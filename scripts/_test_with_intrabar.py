"""
Run full backtest WITH intra-bar (5m BTC data) and compare against TV.
Previous approach was catastrophic (too many trades), but that was with 1m data.
Let's try with 5m data and see the trade count.
"""

import asyncio
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.getcwd())

import numpy as np
import pandas as pd


async def main():
    from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
    from backend.backtesting.interfaces import BacktestInput, TradeDirection
    from backend.backtesting.service import BacktestService
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    svc = BacktestService()

    START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
    END_DATE = pd.Timestamp("2026-02-24T00:00:00", tz="UTC")

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), START_DATE)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    btc_5m = await svc._fetch_historical_data("BTCUSDT", "5", START_DATE, END_DATE)
    print(f"BTC 5m bars: {len(btc_5m)}")

    db_conn = sqlite3.connect("data.sqlite3")
    row = db_conn.execute(
        "SELECT builder_blocks, builder_connections FROM strategies WHERE id='dd2969a2-bbba-410e-b190-be1e8cc50b21'"
    ).fetchone()
    blocks = json.loads(row[0])
    connections = json.loads(row[1])

    # WITHOUT intra-bar (baseline)
    graph1 = {"blocks": blocks, "connections": connections, "name": "RSI_LS_10"}
    adapter1 = StrategyBuilderAdapter(graph1, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    result1 = adapter1.generate_signals(candles)

    bi1 = BacktestInput(
        candles=candles,
        long_entries=result1.entries.values,
        long_exits=result1.exits.values,
        short_entries=result1.short_entries.values,
        short_exits=result1.short_exits.values,
        initial_capital=1_000_000.0,
        position_size=0.001,
        use_fixed_amount=False,
        leverage=1,
        stop_loss=0.132,
        take_profit=0.023,
        taker_fee=0.0007,
        slippage=0.0,
        direction=TradeDirection.BOTH,
        pyramiding=1,
        interval="30",
        entry_on_next_bar_open=True,
    )
    out1 = FallbackEngineV4().run(bi1)
    print(f"\nWITHOUT intra-bar: {len(out1.trades)} trades")

    # WITH intra-bar (5m data)
    graph2 = {"blocks": blocks, "connections": connections, "name": "RSI_LS_10"}
    adapter2 = StrategyBuilderAdapter(graph2, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=btc_5m)
    result2 = adapter2.generate_signals(candles)

    bi2 = BacktestInput(
        candles=candles,
        long_entries=result2.entries.values,
        long_exits=result2.exits.values,
        short_entries=result2.short_entries.values,
        short_exits=result2.short_exits.values,
        initial_capital=1_000_000.0,
        position_size=0.001,
        use_fixed_amount=False,
        leverage=1,
        stop_loss=0.132,
        take_profit=0.023,
        taker_fee=0.0007,
        slippage=0.0,
        direction=TradeDirection.BOTH,
        pyramiding=1,
        interval="30",
        entry_on_next_bar_open=True,
    )
    out2 = FallbackEngineV4().run(bi2)
    print(f"WITH intra-bar (5m): {len(out2.trades)} trades")
    print(f"TV target: 151 trades (150 closed + 1 open)")

    # Quick comparison: if trade counts are close, show first few entries
    for label, trades in [("NO_IB", out1.trades), ("WITH_IB", out2.trades)]:
        print(f"\n{label} first 10 entries:")
        for i, t in enumerate(trades[:10]):
            print(f"  #{i + 1}: {t.direction} entry={t.entry_time} price={t.entry_price:.2f}")

    # Show entries around the 6 UNKNOWN divergences
    targets = {
        "E#23": pd.Timestamp("2025-02-22"),
        "E#57": pd.Timestamp("2025-05-09"),
        "E#85": pd.Timestamp("2025-08-16"),
        "E#89": pd.Timestamp("2025-08-27"),
        "E#91": pd.Timestamp("2025-09-02"),
        "E#120": pd.Timestamp("2025-11-25"),
    }

    for label, target_date in targets.items():
        print(f"\n--- {label} (around {target_date.date()}) ---")
        for name, trades in [("NO_IB", out1.trades), ("IB_5m", out2.trades)]:
            for i, t in enumerate(trades):
                et = pd.Timestamp(t.entry_time)
                if hasattr(et, "tz") and et.tz:
                    et = et.tz_localize(None)
                if abs((et - target_date).total_seconds()) < 86400:  # within 1 day
                    print(f"  {name} #{i + 1}: {t.direction} entry={t.entry_time} exit={t.exit_time} {t.exit_reason}")


asyncio.run(main())
