import sqlite3

con = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
cur = con.execute("PRAGMA table_info(bybit_kline_audit)")
cols = [r[1] for r in cur.fetchall()]
print("Columns:", cols)
r = con.execute(
    "SELECT COUNT(*), MIN(open_time), MAX(open_time) FROM bybit_kline_audit WHERE symbol='ETHUSDT' AND interval='30'"
).fetchone()
print("ETHUSDT 30m:", r)
con.close()
