"""Check timezone of candle index."""

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
    print(f"Index dtype: {candles.index.dtype}")
    print(f"Index tz: {candles.index.tz}")
    print(f"First: {candles.index[0]}  type={type(candles.index[0])}")
    print(f"Last:  {candles.index[-1]} type={type(candles.index[-1])}")
    print()

    # Try naive timestamp
    ts_naive = pd.Timestamp("2026-02-03 19:30:00")
    ts_utc = pd.Timestamp("2026-02-03 19:30:00", tz="UTC")
    print(f"Naive in index: {ts_naive in candles.index}")
    print(f"UTC in index:   {ts_utc in candles.index}")
    print()

    # Show last 10 bars
    print("Last 10 bars:")
    for ts in candles.index[-10:]:
        print(f"  {ts}")

    # Check Feb 3 area
    print()
    print("Bars near 2026-02-03:")
    mask = candles.index.date == pd.Timestamp("2026-02-03").date()
    feb3 = candles[mask]
    print(f"  Count: {len(feb3)}")
    if len(feb3) > 0:
        print(f"  First: {feb3.index[0]}")
        print(f"  Last:  {feb3.index[-1]}")
        # Show 19:00-21:00
        for ts in feb3.index:
            h = ts.hour if hasattr(ts, "hour") else pd.Timestamp(ts).hour
            if 18 <= h <= 22:
                b = candles.loc[ts]
                print(f"    {ts}  O={b['open']:.2f} H={b['high']:.2f} L={b['low']:.2f} C={b['close']:.2f}")


asyncio.run(main())
