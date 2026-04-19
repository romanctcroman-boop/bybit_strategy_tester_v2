"""Check the strategy definition in DB for calc_on_every_tick and related params."""

import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")
c = conn.cursor()

# List tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print("Tables:", tables)

# Find strategy table
for t in tables:
    if "strateg" in t.lower():
        print(f"\nFound strategy table: {t}")
        c.execute(f"PRAGMA table_info({t})")
        cols = c.fetchall()
        print("  Columns:", [col[1] for col in cols])

# Try to find our strategy
for t in tables:
    if "strateg" in t.lower():
        c.execute(f"SELECT * FROM {t} WHERE id LIKE '%dd2969a2%'")
        rows = c.fetchall()
        if rows:
            print(f"\nStrategy found in {t}:")
            c.execute(f"PRAGMA table_info({t})")
            cols = [col[1] for col in c.fetchall()]
            for row in rows:
                for col_name, val in zip(cols, row):
                    if isinstance(val, str) and len(val) > 200:
                        try:
                            parsed = json.loads(val)
                            print(f"  {col_name}: {json.dumps(parsed, indent=4)[:1000]}")
                        except:
                            print(f"  {col_name}: {val[:200]}...")
                    else:
                        print(f"  {col_name}: {val}")

conn.close()
