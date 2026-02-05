"""Replace MATICUSDT with POLUSDT in database and sync historical data"""

import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import sqlite3
import time

from backend.services.adapters.bybit import BybitAdapter
from backend.services.kline_db_service import KlineDBService


def main():
    # Step 1: Delete old MATICUSDT data
    print("=" * 60)
    print("Step 1: Removing old MATICUSDT data...")
    print("=" * 60)

    conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM bybit_kline_audit WHERE symbol = 'MATICUSDT'")
    count = cur.fetchone()[0]
    print(f"  Found {count:,} MATICUSDT records")

    cur.execute("DELETE FROM bybit_kline_audit WHERE symbol = 'MATICUSDT'")
    conn.commit()
    print(f"  Deleted {count:,} MATICUSDT records")
    conn.close()

    # Step 2: Load POLUSDT historical data
    print("\n" + "=" * 60)
    print("Step 2: Loading POLUSDT historical data...")
    print("=" * 60)

    adapter = BybitAdapter()
    db_service = KlineDBService()
    db_service.start()

    symbol = "POLUSDT"
    days = 396

    intervals = {
        "1": min(days * 24 * 60, 50000),
        "5": min(days * 24 * 12, 50000),
        "15": min(days * 24 * 4, 40000),
        "30": days * 24 * 2,
        "60": days * 24,
        "240": days * 6,
        "D": days,
        "W": 200,
    }

    total_added = 0

    for interval, total_candles in intervals.items():
        try:
            print(f"\n  Fetching {symbol} {interval}... (total={total_candles:,})")

            klines = adapter.get_klines_historical(
                symbol=symbol, interval=interval, total_candles=total_candles, market_type="linear"
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
    print("Done! MATICUSDT replaced with POLUSDT")
    print(f"Total added: {total_added:,} candles")
    print("=" * 60)


if __name__ == "__main__":
    main()
