import sqlite3

import pandas as pd

conn = sqlite3.connect("data.sqlite3")
# Check bybit_kline_audit columns
cols = [r[1] for r in conn.execute("PRAGMA table_info(bybit_kline_audit)").fetchall()]
print("bybit_kline_audit columns:", cols)
# Check BTC 30m range
row = conn.execute(
    "SELECT MIN(open_time), MAX(open_time), COUNT(*) FROM bybit_kline_audit WHERE symbol='BTCUSDT' AND interval='30'"
).fetchone()
print(f"BTC 30m: rows={row[2]}, min={pd.to_datetime(row[0], unit='ms')}, max={pd.to_datetime(row[1], unit='ms')}")
conn.close()
