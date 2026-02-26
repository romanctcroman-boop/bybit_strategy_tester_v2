import json
import sqlite3
import sys

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
conn = sqlite3.connect(DB_PATH)
rows = conn.execute(
    "SELECT id, name, created_at FROM strategies WHERE name LIKE '%RSI%' ORDER BY created_at DESC LIMIT 20"
).fetchall()
print("=== RSI strategies (newest first) ===")
for r in rows:
    print(r[0], "|", r[1], "|", r[2])

print()
# Find _10 specifically
row = conn.execute(
    "SELECT id, name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE name LIKE '%_10%'"
).fetchone()
if row:
    sid, sname, bb, bc, bg = row
    print(f"Found: {sname}  id={sid}")
    gp = json.loads(bg) if isinstance(bg, str) else (bg or {})
    ms = gp.get("main_strategy", {})
    blocks = json.loads(bb) if isinstance(bb, str) else (bb or [])
    print("main_strategy:", json.dumps(ms, indent=2, ensure_ascii=False))
    print("\nBlocks:")
    for blk in blocks:
        print(f"  type={blk.get('type')}  params={json.dumps(blk.get('params', {}), ensure_ascii=False)}")
else:
    print("Strategy_RSI_L/S_10 NOT found in DB")
conn.close()
