import sqlite3

conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
cur = conn.cursor()

# Count UNKNOWN records
cur.execute("SELECT COUNT(*) FROM bybit_kline_audit WHERE interval = 'UNKNOWN'")
cnt = cur.fetchone()[0]
print(f"UNKNOWN records found: {cnt}")

# Delete them
cur.execute("DELETE FROM bybit_kline_audit WHERE interval = 'UNKNOWN'")
conn.commit()

print(f"Deleted {cnt} UNKNOWN records")
conn.close()
