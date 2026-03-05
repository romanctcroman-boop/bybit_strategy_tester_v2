import sqlite3

conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\bybit_klines_15m.db")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print([r[0] for r in tables])
# Get sample of first table
if tables:
    t = tables[0][0]
    cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
    print(f"\nTable {t} columns:", [c[1] for c in cols])
    row = conn.execute(f"SELECT * FROM {t} LIMIT 1").fetchone()
    print("Sample:", row)
