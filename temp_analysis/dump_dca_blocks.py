"""Dump Strategy_DCA_RSI_02 blocks to stdout and to dump_dca_blocks.txt."""
import sys, json, sqlite3, pathlib

DB = pathlib.Path("data.sqlite3")
OUT = pathlib.Path("temp_analysis/dump_dca_blocks.txt")

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute(
    "SELECT id, name, builder_blocks, builder_connections, builder_graph "
    "FROM strategies WHERE name='Strategy_DCA_RSI_02' AND is_deleted=0"
)
row = cur.fetchone()
conn.close()

lines = []
if not row:
    lines.append("ERROR: strategy not found")
else:
    sid, sname = row[0], row[1]
    bb = json.loads(row[2]) if row[2] else None
    bc = json.loads(row[3]) if row[3] else None
    bg = json.loads(row[4]) if row[4] else None

    lines.append(f"ID:   {sid}")
    lines.append(f"Name: {sname}")
    lines.append(f"builder_blocks:      {len(bb) if bb is not None else 'NULL'}")
    lines.append(f"builder_connections: {len(bc) if bc is not None else 'NULL'}")
    lines.append(f"builder_graph keys:  {list(bg.keys()) if bg else 'NULL'}")
    lines.append("")

    src = bb if bb is not None else (bg.get("blocks") if bg else [])
    src_name = "builder_blocks" if bb is not None else "builder_graph[blocks]"
    lines.append(f"=== Blocks from {src_name} ({len(src or [])} total) ===")
    for i, b in enumerate(src or []):
        lines.append(f"  [{i}] id={b.get('id','?')!r:30} type={b.get('type','?')!r:25} category={b.get('category','')!r:20}")
        params = b.get("params") or b.get("config") or {}
        if params:
            lines.append(f"       params keys: {list(params.keys())}")

    lines.append("")
    src_c = bc if bc is not None else (bg.get("connections") if bg else [])
    src_c_name = "builder_connections" if bc is not None else "builder_graph[connections]"
    lines.append(f"=== Connections from {src_c_name} ({len(src_c or [])} total) ===")
    for i, c in enumerate(src_c or []):
        lines.append(f"  [{i}] {json.dumps(c, ensure_ascii=False)}")

text = "\n".join(lines)
print(text)
OUT.write_text(text, encoding="utf-8")
print(f"\n[saved to {OUT}]")
