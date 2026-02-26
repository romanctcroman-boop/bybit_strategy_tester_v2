import json
import sqlite3

db = sqlite3.connect("data.sqlite3")
row = db.execute(
    "SELECT builder_blocks, builder_connections FROM strategies WHERE id='dd2969a2-bbba-410e-b190-be1e8cc50b21'"
).fetchone()
blocks = json.loads(row[0])
connections = json.loads(row[1])

print("=== BLOCKS ===")
for b in blocks:
    print(json.dumps(b, indent=2))

print("\n=== CONNECTIONS ===")
for c in connections:
    print(json.dumps(c, indent=2))
