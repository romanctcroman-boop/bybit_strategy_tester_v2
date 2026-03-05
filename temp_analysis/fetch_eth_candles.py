"""
Check where ETHUSDT 30m klines are stored and diagnose signal timing.
"""

# Check the kline service DB
import sys

import pandas as pd

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

from backend.services.kline_db import KlineDB

db = KlineDB("d:/bybit_strategy_tester_v2/data.sqlite3")
# Try fetching ETHUSDT 30m candles for march 2026
import asyncio


async def get_data():
    candles = await db.get_candles(
        symbol="ETHUSDT",
        interval="30",
        start_ms=int(pd.Timestamp("2026-03-03", tz="UTC").timestamp() * 1000),
        end_ms=int(pd.Timestamp("2026-03-05", tz="UTC").timestamp() * 1000),
    )
    return candles


data = asyncio.run(get_data())
print(f"Got {len(data)} candles")
if data:
    df = pd.DataFrame(data)
    print(df.head())
