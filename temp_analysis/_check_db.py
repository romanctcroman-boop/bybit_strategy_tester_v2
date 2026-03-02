import sqlite3

conn = sqlite3.connect("data.sqlite3")

# Tables
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%kline%'")
print("Kline tables:", [r[0] for r in cur.fetchall()])

# ETHUSDT 30m range
cur = conn.execute(
    "SELECT MIN(open_time_dt), MAX(open_time_dt), COUNT(*) "
    "FROM bybit_kline_audit WHERE symbol='ETHUSDT' AND interval='30' AND market_type='linear'"
)
r = cur.fetchone()
print(f"ETHUSDT 30m: min={r[0]}, max={r[1]}, count={r[2]}")

# BTCUSDT 30m range
cur = conn.execute(
    "SELECT MIN(open_time_dt), MAX(open_time_dt), COUNT(*) "
    "FROM bybit_kline_audit WHERE symbol='BTCUSDT' AND interval='30' AND market_type='linear'"
)
r = cur.fetchone()
print(f"BTCUSDT 30m: min={r[0]}, max={r[1]}, count={r[2]}")

# What columns does bybit_kline_audit have?
cur = conn.execute("PRAGMA table_info(bybit_kline_audit)")
cols = [row[1] for row in cur.fetchall()]
print(f"Columns: {cols}")

conn.close()
