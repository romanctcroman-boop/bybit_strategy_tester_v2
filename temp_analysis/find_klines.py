import os
import sqlite3

for path in ["data.sqlite3", "bybit_klines_15m.db", "data/bybit_klines_15m.db", "cache/bybit_klines_15m.db"]:
    if os.path.exists(path):
        conn = sqlite3.connect(path)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f"{path}: {len(tables)} tables: {tables[:20]}")
        conn.close()
    else:
        print(f"{path}: NOT FOUND")
