"""Quick check candle bars around trades 139 and 142."""

import asyncio
import sys
import warnings

import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")
from backend.backtesting.service import BacktestService


async def main():
    svc = BacktestService()
    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT",
        interval="30",
        start_date=pd.Timestamp("2025-01-01", tz="UTC"),
        end_date=pd.Timestamp("2026-02-24", tz="UTC"),
    )
    print(f"Candles: {len(candles)} bars, last={candles.index[-1]}")
    print()

    # Trade 139: long, entry 2026-02-03 19:30
    tp_139 = 2189.01 * 1.023
    print(f"=== Trade #139 (long) entry_px=2189.01 TP={tp_139:.2f} ===")
    for h in range(-2, 6):
        ts = pd.Timestamp("2026-02-03 19:30:00", tz="UTC") + pd.Timedelta(minutes=30 * h)
        if ts in candles.index:
            b = candles.loc[ts]
            hit = "TP_HIT" if b["high"] >= tp_139 else ""
            print(f"  {str(ts)[:19]}  O={b['open']:.2f} H={b['high']:.2f} L={b['low']:.2f} C={b['close']:.2f}  {hit}")
        else:
            print(f"  {str(ts)[:19]}  -- NOT IN DATA --")

    print()
    # Trade 142: short, entry 2026-02-06 06:30
    tp_142 = 1939.46 * (1 - 0.023)
    print(f"=== Trade #142 (short) entry_px=1939.46 TP={tp_142:.2f} ===")
    for h in range(-2, 6):
        ts = pd.Timestamp("2026-02-06 06:30:00", tz="UTC") + pd.Timedelta(minutes=30 * h)
        if ts in candles.index:
            b = candles.loc[ts]
            hit = "TP_HIT" if b["low"] <= tp_142 else ""
            print(f"  {str(ts)[:19]}  O={b['open']:.2f} H={b['high']:.2f} L={b['low']:.2f} C={b['close']:.2f}  {hit}")
        else:
            print(f"  {str(ts)[:19]}  -- NOT IN DATA --")


asyncio.run(main())
