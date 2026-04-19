"""Debug klines around first trade entry for TV parity analysis."""

import json
import sqlite3
from datetime import datetime

# First, check klines DB structure
conn = sqlite3.connect("bybit_klines_15m.db")
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("Klines tables:", tables)

for tbl in tables[:3]:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})")]
    print(f"  {tbl}: {cols}")

# Look for BTCUSDT data around 2025-11-01
for tbl in tables:
    if "BTC" in tbl.upper() or "btc" in tbl.lower():
        try:
            rows = conn.execute(
                f"SELECT * FROM {tbl} WHERE open_time >= 1762000000000 AND open_time <= 1762100000000 LIMIT 5"
            ).fetchall()
            if rows:
                print(f"\nFound BTC data in {tbl}:")
                for r in rows:
                    print(" ", r)
                break
        except Exception as e:
            print(f"  Error in {tbl}: {e}")

conn.close()

# Also check main data.sqlite3 klines
conn2 = sqlite3.connect("data.sqlite3")
tables2 = [r[0] for r in conn2.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("\nMain DB tables:", tables2)
