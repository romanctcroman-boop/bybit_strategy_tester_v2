import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")
row = conn.execute("SELECT builder_blocks FROM strategies WHERE id='dd2969a2-bbba-410e-b190-be1e8cc50b21'").fetchone()
blocks = json.loads(row[0])
for b in blocks:
    print(f"Block: type={b.get('type')}, indicator={b.get('indicator')}, id={b.get('id')}")
    if "params" in b:
        print(f"  params={json.dumps(b['params'], indent=4)}")
    if "settings" in b:
        print(f"  settings={json.dumps(b['settings'], indent=4)}")
conn.close()
