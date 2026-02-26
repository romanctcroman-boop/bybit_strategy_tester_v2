"""Show the builder blocks for the RSI strategy."""

import json
import sqlite3

conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
c = conn.cursor()
c.execute("""
    SELECT builder_blocks, builder_connections, builder_graph
    FROM strategies
    WHERE id = '01cd8861-60eb-40dd-a9a9-8baa6f2db0fa'
""")
row = c.fetchone()
if row:
    blocks = json.loads(row[0]) if row[0] else []
    print("Builder blocks:")
    for b in blocks:
        block_type = b.get("type", b.get("id", "?"))
        params = b.get("params", b.get("config", {}))
        print(f"  [{block_type}] {json.dumps(params, indent=4)}")
else:
    print("Not found")
conn.close()
