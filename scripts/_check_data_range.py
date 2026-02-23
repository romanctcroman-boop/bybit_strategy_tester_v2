"""Check the latest available data bar in the database."""

import sqlite3
from datetime import UTC, datetime

conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
r = conn.execute(
    "SELECT MAX(open_time) FROM bybit_kline_audit WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear'"
).fetchone()
print("Max open_time ms:", r[0])
print("Max bar UTC:", datetime.fromtimestamp(r[0] / 1000, tz=UTC))

# Also check what bars exist near 2026-02-23
rows = conn.execute(
    "SELECT open_time FROM bybit_kline_audit WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
    "AND open_time >= 1740182400000 ORDER BY open_time ASC LIMIT 20"
).fetchall()
print("\nBars from 2026-02-22 00:00 UTC onwards:")
for row in rows:
    print(" ", datetime.fromtimestamp(row[0] / 1000, tz=UTC))
conn.close()
