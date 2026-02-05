import sqlite3
from pathlib import Path

# Find databases
dbs = [
    Path("bybit_klines_15m.db"),
    Path("backend/bybit_klines_15m.db"),
    Path("data.sqlite3"),
    Path("backend/data.sqlite3"),
]

for db in dbs:
    if db.exists():
        print(f"\n📁 {db}")
        conn = sqlite3.connect(db)
        tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f"   Tables: {tables}")

        if 'bybit_kline_audit' in tables:
            # Count rows
            count = conn.execute("SELECT COUNT(*) FROM bybit_kline_audit").fetchone()[0]
            print(f"   Rows in bybit_kline_audit: {count}")

            # Check for SPOT data
            spot_count = conn.execute("SELECT COUNT(*) FROM bybit_kline_audit WHERE market_type = 'spot'").fetchone()[0]
            print(f"   SPOT rows: {spot_count}")

            # Sample data
            sample = conn.execute("SELECT symbol, interval, market_type, COUNT(*) as cnt FROM bybit_kline_audit GROUP BY symbol, interval, market_type LIMIT 10").fetchall()
            print("   Data summary:")
            for row in sample:
                print(f"      {row}")

        conn.close()
