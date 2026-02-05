"""Sync missing data: Weekly for all symbols + all intervals for MATICUSDT"""

import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

from backend.services.adapters.bybit import BybitAdapter
from backend.services.kline_db_service import KlineDBService


def main():
    adapter = BybitAdapter()
    db_service = KlineDBService()
    db_service.start()  # Start the write loop

    # All symbols that need Weekly data
    symbols_need_weekly = ["ADAUSDT", "AVAXUSDT", "BNBUSDT", "DOGEUSDT", "DOTUSDT", "LINKUSDT", "SOLUSDT", "XRPUSDT"]

    # MATICUSDT needs all intervals
    maticusdt_intervals = ["1", "5", "15", "30", "60", "240", "D", "W", "M"]

    total_added = 0

    # 1. Add Weekly data for symbols that don't have it
    print("=" * 60)
    print("Adding Weekly (W) data for symbols...")
    print("=" * 60)

    for symbol in symbols_need_weekly:
        try:
            klines = adapter.get_klines(
                symbol=symbol,
                interval="W",
                limit=200,  # ~4 years of weekly data
            )
            if klines:
                count = db_service.queue_klines(symbol, "W", klines)
                print(f"  {symbol}: W = {count} candles")
                total_added += count
            else:
                print(f"  {symbol}: W = NO DATA")
        except Exception as e:
            print(f"  {symbol}: W = ERROR: {e}")

    # 2. Add all intervals for MATICUSDT
    print("\n" + "=" * 60)
    print("Adding all intervals for MATICUSDT...")
    print("=" * 60)

    for interval in maticusdt_intervals:
        try:
            limit = 1000 if interval in ["1", "5"] else 500
            klines = adapter.get_klines(symbol="MATICUSDT", interval=interval, limit=limit)
            if klines:
                count = db_service.queue_klines("MATICUSDT", interval, klines)
                print(f"  MATICUSDT: {interval} = {count} candles")
                total_added += count
            else:
                print(f"  MATICUSDT: {interval} = NO DATA")
        except Exception as e:
            print(f"  MATICUSDT: {interval} = ERROR: {e}")

    # Wait for writes to complete
    import time

    time.sleep(3)
    db_service.stop()

    print("\n" + "=" * 60)
    print(f"Done! Total added: {total_added:,} candles")
    print("=" * 60)


if __name__ == "__main__":
    main()
