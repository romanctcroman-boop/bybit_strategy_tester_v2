import json
import sqlite3

conn = sqlite3.connect("D:/bybit_strategy_tester_v2/data.sqlite3")
cur = conn.cursor()

cur.execute(
    """
    SELECT id, name, builder_blocks
    FROM strategies
    WHERE name LIKE '%RSI_L%S%3%' AND is_deleted=0
    ORDER BY updated_at DESC LIMIT 1
    """
)
r = cur.fetchone()
if not r:
    print("No strategy found")
    conn.close()
    raise SystemExit

sid, name, blocks_raw = r
print(f"Strategy: {name} ({sid})")
blocks = json.loads(blocks_raw) if blocks_raw else []
for b in blocks:
    btype = b.get("type", "?")
    cfg = b.get("params") or b.get("config") or b.get("data") or {}
    print(f"  [{btype}] {json.dumps(cfg, indent=2)}")

conn.close()
