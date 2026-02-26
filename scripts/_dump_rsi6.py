import json
import sqlite3
import sys

conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
cur = conn.cursor()
cur.execute("SELECT builder_blocks, parameters FROM strategies WHERE id=?", ("5c03fd86-a821-4a62-a783-4d617bf25bc7",))
row = cur.fetchone()
blocks = json.loads(row[0]) if row[0] else []
params = json.loads(row[1]) if row[1] else {}
print("Strategy params:")
for k, v in sorted(params.items()):
    print(f"  {k}: {v}")
print()
for b in blocks:
    print(f"Block id={b.get('id')} type={b.get('type')}")
    for k, v in b.get("params", {}).items():
        print(f"  {k}: {v}")
conn.close()
