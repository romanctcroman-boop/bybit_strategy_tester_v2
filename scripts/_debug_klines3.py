"""Check klines databases."""

import sqlite3

for db in ["data/klines.db", "data/bybit_klines_15m.db"]:
    try:
        conn = sqlite3.connect(db)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"{db}: {[t[0] for t in tables[:10]]}")
        for tbl in [t[0] for t in tables[:5]]:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})")]
            count = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"  {tbl}: cols={cols[:6]}, rows={count}")
        conn.close()
    except Exception as e:
        print(f"{db}: ERROR {e}")
