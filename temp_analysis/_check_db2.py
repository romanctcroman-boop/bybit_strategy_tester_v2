"""Check all available data sources for pre-2025 ETHUSDT klines."""

import sqlite3

conn = sqlite3.connect("data.sqlite3")

# All tables
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print("All tables:", tables)

# Check bybit_klines_15m.db separately
import os

if os.path.exists("bybit_klines_15m.db"):
    conn2 = sqlite3.connect("bybit_klines_15m.db")
    cur2 = conn2.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print("bybit_klines_15m.db tables:", [r[0] for r in cur2.fetchall()])
    conn2.close()

conn.close()
