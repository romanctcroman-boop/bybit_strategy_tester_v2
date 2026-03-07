import sqlite3
import json

# Connect to database
conn = sqlite3.connect("data.sqlite3")
cur = conn.cursor()

# First query: Find DCA+RSI strategies
print("=== Query 1: DCA+RSI strategies ===")
cur.execute("SELECT id, name, builder_blocks FROM strategies WHERE name LIKE '%DCA%RSI%' AND is_deleted=0")
rows = cur.fetchall()
if not rows:
    print("No strategies found matching '%DCA%RSI%'")
else:
    for r in rows:
        blocks = json.loads(r[2]) if r[2] else []
        block_types = [(b.get('type','?'), b.get('category','')) for b in blocks]
        print(f"ID: {r[0]}")
        print(f"Name: {r[1]}")
        print(f"Block types: {block_types}")
        print()

# Second query: Check specific ID
print("\n=== Query 2: Check specific ID ===")
cur.execute("SELECT id, name FROM strategies WHERE id='f46c7cc3-1098-483a-a177-67b7867dd72e'")
row = cur.fetchone()
print(f"ID f46c7cc3: {row}")

# Third query: List all strategies with 'DCA' or 'RSI' in name
print("\n=== Query 3: All strategies with 'DCA' or 'RSI' ===")
cur.execute("SELECT id, name FROM strategies WHERE (name LIKE '%DCA%' OR name LIKE '%RSI%') AND is_deleted=0 ORDER BY updated_at DESC LIMIT 20")
rows = cur.fetchall()
for r in rows:
    print(f"ID: {str(r[0])[:8]}... | Name: {r[1]}")

conn.close()
