"""Check strategy slippage config and what _compare_all_metrics uses."""
import sqlite3
import json

conn = sqlite3.connect("data.sqlite3")
row = conn.execute(
    "SELECT id, name, parameters FROM strategies WHERE id='5a1741ac-ad9e-4285-a9d6-58067c56407a'"
).fetchone()
if row:
    print("id:", row[0])
    print("name:", row[1])
    params = json.loads(row[2])
    print("_slippage:", params.get("_slippage", "NOT SET"))
    print("_commission:", params.get("_commission", "NOT SET"))
    print("_leverage:", params.get("_leverage", "NOT SET"))
    print("all param keys:", list(params.keys()))
conn.close()
