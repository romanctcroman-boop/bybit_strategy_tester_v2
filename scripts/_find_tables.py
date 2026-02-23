import sqlite3

conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("All tables:", [t[0] for t in tables])

# also check kline db
try:
    conn2 = sqlite3.connect(r"d:\bybit_strategy_tester_v2\bybit_klines_15m.db")
    t2 = conn2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("klines DB tables:", [t[0] for t in t2])
    conn2.close()
except Exception as e:
    print(f"klines DB error: {e}")

conn.close()
