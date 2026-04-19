"""Find Strategy_RSI_LS_11 in database and print full graph."""

import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")
cur = conn.cursor()

cur.execute("SELECT id, name, builder_graph FROM strategies WHERE is_deleted=0 ORDER BY created_at DESC")
rows = cur.fetchall()
print("=== Active (non-deleted) strategies ===")
for row in rows:
    sid, name, graph = row
    print(f"\nID: {sid}")
    print(f"Name: {name}")
    if graph:
        try:
            g = json.loads(graph)
            blocks = g.get("blocks", [])
            print(f"Blocks ({len(blocks)}):")
            for b in blocks:
                bt = b.get("type", "")
                bp = b.get("params", {})
                print(f"  type={bt}, params={json.dumps(bp)}")
        except Exception as e:
            print(f"  Graph error: {e}")

conn.close()
