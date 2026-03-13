import sqlite3

for db in (r"d:\bybit_strategy_tester_v2\data.sqlite3", r"d:\bybit_strategy_tester_v2\bybit_klines_15m.db"):
    print(f"\n=== {db} ===")
    try:
        c = sqlite3.connect(db)
        tables = c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        for r in tables:
            # also count rows
            cnt = c.execute(f"SELECT COUNT(*) FROM [{r[0]}]").fetchone()[0]
            print(f"  {r[0]}  ({cnt} rows)")
        c.close()
    except Exception as e:
        print("  ERROR:", e)
