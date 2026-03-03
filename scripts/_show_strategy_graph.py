"""Show Strategy_MACD_04 connections and test other indicator blocks."""

import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")
cur = conn.cursor()
cur.execute("SELECT builder_graph FROM strategies WHERE name=?", ("Strategy_MACD_04",))
row = cur.fetchone()
g = json.loads(row[0])
conn.close()

print("=== BLOCKS ===")
for b in g.get("blocks", []):
    print(f"  [{b['type']}] id={b['id']}  params_keys={list(b.get('params', {}).keys())}")

print("\n=== CONNECTIONS ===")
for c in g.get("connections", []):
    src = c["source"]
    tgt = c["target"]
    src_block = next((b["type"] for b in g["blocks"] if b["id"] == src["blockId"]), "?")
    tgt_block = next((b["type"] for b in g["blocks"] if b["id"] == tgt["blockId"]), "?")
    print(f"  [{src_block}].{src['portId']}  -->  [{tgt_block}].{tgt['portId']}")
