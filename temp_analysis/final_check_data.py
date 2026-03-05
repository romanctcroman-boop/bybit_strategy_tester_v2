import sqlite3

conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")

print("ETHUSDT 30m date range:")
rows = conn.execute("""
    SELECT MIN(open_time_dt), MAX(open_time_dt), COUNT(*) 
    FROM bybit_kline_audit 
    WHERE symbol = 'ETHUSDT' AND CAST(interval AS TEXT) = '30'
""").fetchall()
for r in rows:
    print(f"  Min: {r[0]}, Max: {r[1]}, Count: {r[2]}")

print("\nBTCUSDT 30m date range:")
rows = conn.execute("""
    SELECT MIN(open_time_dt), MAX(open_time_dt), COUNT(*) 
    FROM bybit_kline_audit 
    WHERE symbol = 'BTCUSDT' AND CAST(interval AS TEXT) = '30'
""").fetchall()
for r in rows:
    print(f"  Min: {r[0]}, Max: {r[1]}, Count: {r[2]}")

print("\nSample ETHUSDT 30m (first 5 bars):")
rows = conn.execute("""
    SELECT open_time_dt, open_price, high_price, low_price, close_price 
    FROM bybit_kline_audit 
    WHERE symbol = 'ETHUSDT' AND CAST(interval AS TEXT) = '30'
    ORDER BY open_time_dt 
    LIMIT 5
""").fetchall()
for r in rows:
    print(f"  {r}")

conn.close()
