"""Show Strategy_DCA_RSI_02 blocks and connections from DB."""

import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")
cur = conn.cursor()
cur.execute(
    "SELECT id, name, builder_blocks, builder_connections "
    "FROM strategies WHERE name LIKE '%DCA%RSI%02%' OR name LIKE '%DCA_RSI_02%'"
)
rows = cur.fetchall()
if not rows:
    print("Strategy not found. Listing all DCA strategies:")
    cur.execute("SELECT id, name FROM strategies WHERE name LIKE '%DCA%'")
    for r in cur.fetchall():
        print(f"  ID={r[0]}  Name={r[1]}")
else:
    for r in rows:
        print(f"ID: {r[0]}")
        print(f"Name: {r[1]}")
        blocks = json.loads(r[2]) if r[2] else []
        connections = json.loads(r[3]) if r[3] else []
        print(f"\n=== BLOCKS ({len(blocks)}) ===")
        for b in blocks:
            print(json.dumps(b, indent=2, ensure_ascii=False))
        print(f"\n=== CONNECTIONS ({len(connections)}) ===")
        for c in connections:
            print(json.dumps(c, ensure_ascii=False))
        print("---")
conn.close()
