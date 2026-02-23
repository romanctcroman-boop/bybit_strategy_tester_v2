import sqlite3

conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(tables)
conn.close()
