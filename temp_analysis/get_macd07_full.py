import json
import sqlite3

conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
cursor = conn.execute("SELECT id, name, builder_blocks FROM strategies WHERE name LIKE '%MACD_07%' AND is_deleted=0")
rows = cursor.fetchall()
for row in rows:
    sid, name, blocks_raw = row
    print(f"\n=== {name} (id={sid}) ===")
    blocks = json.loads(blocks_raw) if blocks_raw else []
    for b in blocks:
        if b.get("type") == "macd":
            print("FULL MACD PARAMS:")
            print(json.dumps(b.get("params", {}), indent=2))

conn.close()
