import sqlite3

conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\bybit_klines_15m.db")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])
if tables:
    tbl = tables[0][0]
    cols = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
    print("Columns:", [c[1] for c in cols])
    cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()
    print("Count:", cnt[0])
    sample = conn.execute(f"SELECT * FROM {tbl} LIMIT 3").fetchall()
    print("Sample:", sample[:2])
conn.close()
