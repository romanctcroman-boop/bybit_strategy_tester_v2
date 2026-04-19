"""Inspect kline data and find where data is stored."""

import sqlite3

# Check klines DB
conn = sqlite3.connect("bybit_klines_15m.db")
rows = conn.execute("SELECT name, type FROM sqlite_master").fetchall()
print("bybit_klines_15m.db objects:", rows)
conn.close()

# Check main DB
conn = sqlite3.connect("data.sqlite3")
rows = conn.execute("SELECT name, type FROM sqlite_master WHERE type='table'").fetchall()
print("data.sqlite3 tables:", [r[0] for r in rows])
# Check kline-related
for r in rows:
    if "kline" in r[0].lower() or "ohlcv" in r[0].lower() or "candle" in r[0].lower() or "price" in r[0].lower():
        print(f"  Possible kline table: {r[0]}")
conn.close()
