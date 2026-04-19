import sqlite3

conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data\bybit_klines_15m.db")
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables in klines DB:", tables[:20])
btc_tables = [t for t in tables if "btc" in t.lower() or "kline" in t.lower()]
print("BTC-related:", btc_tables[:10])
conn.close()
