import json
import sqlite3

conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
cursor = conn.execute(
    "SELECT id, name, builder_blocks, builder_connections FROM strategies WHERE name LIKE '%MACD_07%' AND is_deleted=0"
)
rows = cursor.fetchall()
print(f"Found {len(rows)} strategies matching MACD_07")
for row in rows:
    sid, name, blocks_raw, conns_raw = row
    print(f"\n=== {name} (id={sid}) ===")
    blocks = json.loads(blocks_raw) if blocks_raw else []
    conns = json.loads(conns_raw) if conns_raw else []
    print("BLOCKS:")
    for b in blocks:
        print(f"  id={b.get('id', '?')[:30]} type={b.get('type', '?')} params={json.dumps(b.get('params', {}))[:120]}")
    print("CONNECTIONS:")
    for c in conns:
        src = c.get("source", c.get("from", {}))
        tgt = c.get("target", c.get("to", {}))
        src_block = src.get("blockId", src.get("block_id", "?"))[:20] if isinstance(src, dict) else str(src)[:20]
        src_port = src.get("portId", src.get("port_id", "?")) if isinstance(src, dict) else "?"
        tgt_block = tgt.get("blockId", tgt.get("block_id", "?"))[:20] if isinstance(tgt, dict) else str(tgt)[:20]
        tgt_port = tgt.get("portId", tgt.get("port_id", "?")) if isinstance(tgt, dict) else "?"
        print(f"  {src_block}.{src_port} -> {tgt_block}.{tgt_port}")

conn.close()
