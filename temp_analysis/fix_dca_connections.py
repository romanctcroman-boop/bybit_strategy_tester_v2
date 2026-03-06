"""Fix DCA Test Strategy: add missing connection block_2.config -> main_strategy.dca_grid"""

import json
import sqlite3

DB = "data.sqlite3"
SID = "5a389284-5ab8-423d-8f05-61d87d4fc4c2"

conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute("SELECT builder_connections FROM strategies WHERE id=?", (SID,))
row = cur.fetchone()
conns = json.loads(row[0]) if row and row[0] else []

print(f"Current connections ({len(conns)}):")
for c in conns:
    src = c.get("source", {})
    tgt = c.get("target", {})
    print(f"  {src.get('blockId', '?')}.{src.get('portId', '?')} -> {tgt.get('blockId', '?')}.{tgt.get('portId', '?')}")

# Check if DCA connection already exists
already_exists = any(
    c.get("source", {}).get("blockId") == "block_2" and c.get("target", {}).get("portId") == "dca_grid" for c in conns
)

if already_exists:
    print("\nDCA connection already exists!")
else:
    new_conn = {
        "id": "conn_dca_block2_grid",
        "source": {"blockId": "block_2", "portId": "config"},
        "target": {"blockId": "main_strategy", "portId": "dca_grid"},
    }
    conns.append(new_conn)
    cur.execute("UPDATE strategies SET builder_connections=? WHERE id=?", (json.dumps(conns), SID))
    conn.commit()
    print(f"\nAdded DCA connection! Total connections now: {len(conns)}")
    for c in conns:
        src = c.get("source", {})
        tgt = c.get("target", {})
        print(
            f"  {src.get('blockId', '?')}.{src.get('portId', '?')} -> {tgt.get('blockId', '?')}.{tgt.get('portId', '?')}"
        )

conn.close()
