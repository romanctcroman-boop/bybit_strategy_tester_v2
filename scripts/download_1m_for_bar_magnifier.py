"""
🔧 DOWNLOAD 1-MINUTE DATA FOR BAR MAGNIFIER
=============================================
Downloads 1m BTCUSDT.P data from Bybit API for Bar Magnifier testing.

Range: Oct 1, 2025 - Jan 24, 2026 (~116 days = ~167,040 bars)
"""
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Output file
OUTPUT_FILE = Path("d:/TV/BYBIT_BTCUSDT.P, 1.csv")

# Date range matching the 15m data
START_DATE = datetime(2025, 10, 1, tzinfo=UTC)
END_DATE = datetime(2026, 1, 24, 23, 59, tzinfo=UTC)

START_TS = int(START_DATE.timestamp() * 1000)
END_TS = int(END_DATE.timestamp() * 1000)


async def download_1m_data():
    """Download 1-minute data from Bybit API."""
    from backend.services.adapters.bybit import BybitAdapter

    adapter = BybitAdapter()

    symbol = "BTCUSDT"
    interval = "1"
    market_type = "linear"

    print("=" * 70)
    print(f"📥 DOWNLOADING {symbol} 1m LINEAR DATA FOR BAR MAGNIFIER")
    print("=" * 70)
    print(f"\n📅 Date range: {START_DATE.date()} to {END_DATE.date()}")

    # Calculate expected bars
    total_minutes = int((END_TS - START_TS) / 60000)
    print(f"   Expected ~{total_minutes:,} bars")

    try:
        print("\n📡 Fetching data from Bybit API...")
        print("   This may take a few minutes for 1m data...")

        all_candles = []
        current_start = START_TS
        batch_size = 1000  # Bybit max limit
        batch_count = 0

        while current_start < END_TS:
            batch_count += 1

            candles = await adapter.get_historical_klines(
                symbol=symbol,
                interval=interval,
                start_time=current_start,
                end_time=END_TS,
                limit=batch_size,
                market_type=market_type,
            )

            if not candles:
                print("   ⚠️ No more data available")
                break

            all_candles.extend(candles)

            # Move to next batch
            last_ts = candles[-1].get('open_time', candles[-1].get('timestamp', current_start))
            if isinstance(last_ts, str):
                last_ts = int(pd.to_datetime(last_ts).timestamp() * 1000)

            current_start = last_ts + 60000  # +1 minute

            if batch_count % 10 == 0:
                print(f"   Batch {batch_count}: {len(all_candles):,} candles so far...")

        print(f"\n   ✅ Fetched {len(all_candles):,} candles total")

        if all_candles:
            # Convert to DataFrame
            df = pd.DataFrame(all_candles)

            # Normalize column names
            column_map = {
                'open_time': 'timestamp',
                'open_price': 'open',
                'high_price': 'high',
                'low_price': 'low',
                'close_price': 'close',
            }
            df.rename(columns=column_map, inplace=True)

            # Parse timestamp
            if 'timestamp' in df.columns:
                if df['timestamp'].dtype == 'int64':
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                else:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])

            # Sort by time
            df.sort_values('timestamp', inplace=True)
            df.drop_duplicates(subset='timestamp', keep='first', inplace=True)

            # Save to CSV
            print(f"\n💾 Saving to {OUTPUT_FILE}...")
            df.to_csv(OUTPUT_FILE, index=False)
            print(f"   ✅ Saved {len(df):,} rows")

            # Show sample
            print("\n📊 Sample data:")
            print(df.head())

            return df

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise

    print("\n" + "=" * 70)
    print("✅ 1-MINUTE DATA DOWNLOAD COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    df = asyncio.run(download_1m_data())
