import sqlite3

conn = sqlite3.connect("data.sqlite3")

# Check what symbols/intervals are available
cur = conn.execute("""
    SELECT symbol, interval, market_type, COUNT(*) as cnt,
           MIN(open_time_dt) as min_dt, MAX(open_time_dt) as max_dt
    FROM bybit_kline_audit
    GROUP BY symbol, interval, market_type
    ORDER BY symbol, interval
""")
rows = cur.fetchall()
print("Available kline data:")
for r in rows:
    print(f"  {r[0]:12s} {r[1]:5s} {r[2]:8s}  {r[3]:8d} rows  {r[4]} -> {r[5]}")

conn.close()
