"""
Import BTCUSDH2026 data from TradingView CSV export into database.
This provides the data needed for LINEAR parity testing.

Usage:
    python scripts/import_tv_btcusdh2026.py
"""

import csv
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Config
TV_CSV_PATH = Path("d:/TV/BYBIT_BTCUSDH2026, 15 (1)f.csv")
DB_PATH = Path(__file__).resolve().parents[1] / "data.sqlite3"
SYMBOL = "BTCUSDH2026"
INTERVAL = "15"
MARKET_TYPE = "linear"  # Quarterly futures


def main():
    print("=" * 60)
    print("📥 BTCUSDH2026 TradingView CSV Importer")
    print("=" * 60)

    # Check CSV exists
    if not TV_CSV_PATH.exists():
        print(f"❌ CSV not found: {TV_CSV_PATH}")
        sys.exit(1)

    print(f"📄 Source: {TV_CSV_PATH}")
    print(f"🗄️ Database: {DB_PATH}")
    print()

    # Connect to database
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Count existing records
    cursor.execute(
        """
        SELECT COUNT(*) FROM bybit_kline_audit 
        WHERE symbol = ? AND interval = ?
    """,
        (SYMBOL, INTERVAL),
    )
    existing = cursor.fetchone()[0]
    print(f"📊 Existing {SYMBOL} records: {existing}")

    # Read and import CSV
    imported = 0
    skipped = 0

    with open(TV_CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                # Parse TradingView format
                time_str = row["time"]
                open_price = float(row["open"])
                high_price = float(row["high"])
                low_price = float(row["low"])
                close_price = float(row["close"])
                volume = 0.0  # TV export may not have volume

                # Parse ISO 8601 timestamp
                # Format: 2025-12-15T02:15:00+03:00
                dt = datetime.fromisoformat(time_str)

                # Convert to UTC
                timestamp_ms = int(dt.timestamp() * 1000)
                dt_utc = datetime.utcfromtimestamp(dt.timestamp())
                open_time_dt = dt_utc.isoformat() + "+00:00"

                # Insert or replace - include all required columns
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO bybit_kline_audit
                    (symbol, interval, open_time, open_time_dt, 
                     open_price, high_price, low_price, close_price, 
                     volume, turnover, raw, market_type, inserted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                    (
                        SYMBOL,
                        INTERVAL,
                        timestamp_ms,
                        open_time_dt,
                        open_price,
                        high_price,
                        low_price,
                        close_price,
                        volume,
                        0.0,
                        "{}",
                        MARKET_TYPE,  # turnover=0, raw=empty JSON
                    ),
                )

                imported += 1

            except Exception as e:
                print(f"⚠️ Row error: {e}")
                skipped += 1

    conn.commit()

    # Count after import
    cursor.execute(
        """
        SELECT COUNT(*) FROM bybit_kline_audit 
        WHERE symbol = ? AND interval = ?
    """,
        (SYMBOL, INTERVAL),
    )
    final_count = cursor.fetchone()[0]

    # Get date range
    cursor.execute(
        """
        SELECT MIN(open_time_dt), MAX(open_time_dt)
        FROM bybit_kline_audit 
        WHERE symbol = ? AND interval = ?
    """,
        (SYMBOL, INTERVAL),
    )
    date_range = cursor.fetchone()

    conn.close()

    print()
    print("=" * 60)
    print("✅ IMPORT COMPLETE")
    print("=" * 60)
    print(f"  Imported: {imported} candles")
    print(f"  Skipped:  {skipped}")
    print(f"  Total:    {final_count}")
    print(f"  Range:    {date_range[0]} to {date_range[1]}")
    print()
    print("🎯 You can now run LINEAR parity tests with this data!")


if __name__ == "__main__":
    main()
