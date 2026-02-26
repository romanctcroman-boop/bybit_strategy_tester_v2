"""Compare trade entry times: TV vs Ours by matching prices to klines."""

import sqlite3
from datetime import datetime, timezone

conn = sqlite3.connect("data.sqlite3")

# Check bybit_kline_audit columns
cols = [r[1] for r in conn.execute("PRAGMA table_info(bybit_kline_audit)")]
print("bybit_kline_audit cols:", cols)

# Get distinct intervals
intervals = conn.execute("SELECT DISTINCT interval, symbol, market_type FROM bybit_kline_audit LIMIT 20").fetchall()
print("Distinct interval/symbol/market_type:", intervals[:10])

# Get count for BTCUSDT 15m (column is 'interval')
cnt = conn.execute("SELECT COUNT(*) FROM bybit_kline_audit WHERE symbol='BTCUSDT' AND interval='15'").fetchone()
print(f"BTCUSDT interval=15 rows: {cnt[0]}")

# Get first few rows to understand timestamp format
rows = conn.execute(
    "SELECT open_time, open_price, high_price, low_price, close_price FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='15' ORDER BY open_time LIMIT 5"
).fetchall()
print("\nFirst 5 rows:")
for r in rows:
    print(" ", r)

# Find bars around TV trade 1 entry: 2025-11-01 14:30 UTC
ts_1101_1430 = int(datetime(2025, 11, 1, 14, 30, tzinfo=timezone.utc).timestamp() * 1000)
ts_1101_0600 = int(datetime(2025, 11, 1, 6, 0, tzinfo=timezone.utc).timestamp() * 1000)
print(f"\nts range: {ts_1101_0600} - {ts_1101_1430 + 900000}")

rows = conn.execute(
    "SELECT open_time, open_price, high_price, low_price, close_price FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='15' AND open_time >= ? AND open_time <= ? ORDER BY open_time",
    (ts_1101_0600, ts_1101_1430 + 900000),
).fetchall()

print(f"Found {len(rows)} bars:")
for r in rows:
    dt = datetime.fromtimestamp(r[0] / 1000, tz=timezone.utc)
    print(f"  {dt.strftime('%Y-%m-%d %H:%M')}  O={r[1]:.1f}  H={r[2]:.1f}  L={r[3]:.1f}  C={r[4]:.1f}")

conn.close()
