"""Sync MATICUSDT historical data from 2025-01-01"""

import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import time

from backend.services.adapters.bybit import BybitAdapter
from backend.services.kline_db_service import KlineDBService


def main():
    adapter = BybitAdapter()
    db_service = KlineDBService()
    db_service.start()

    symbol = "MATICUSDT"

    # Calculate total candles needed from 2025-01-01 to 2026-01-31 (~396 days)
    days = 396
    intervals = {
        "1": days * 24 * 60,  # 570,240 candles
        "5": days * 24 * 12,  # 114,048 candles
        "15": days * 24 * 4,  # 38,016 candles
        "30": days * 24 * 2,  # 19,008 candles
        "60": days * 24,  # 9,504 candles
        "240": days * 6,  # 2,376 candles
        "D": days,  # 396 candles
        "W": 60,  # ~52 candles
    }

    total_added = 0

    print("=" * 60)
    print(f"Syncing {symbol} historical data (~{days} days)")
    print("=" * 60)

    for interval, total_candles in intervals.items():
        try:
            print(f"\n  Fetching {symbol} {interval}... (total={total_candles:,})")

            # Use get_klines_historical with correct signature
            klines = adapter.get_klines_historical(
                symbol=symbol,
                interval=interval,
                total_candles=min(total_candles, 50000),  # Cap to avoid timeout
                market_type="linear",
            )

            if klines:
                count = db_service.queue_klines(symbol, interval, klines)
                print(f"  {symbol}: {interval} = {count:,} candles")
                total_added += count
            else:
                print(f"  {symbol}: {interval} = NO DATA")

        except Exception as e:
            print(f"  {symbol}: {interval} = ERROR: {e}")

    # Wait for writes
    print("\nWaiting for writes to complete...")
    time.sleep(5)
    db_service.stop()

    print("\n" + "=" * 60)
    print(f"Done! Total added: {total_added:,} candles")
    print("=" * 60)


if __name__ == "__main__":
    main()
