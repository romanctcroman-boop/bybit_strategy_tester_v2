import sqlite3

conn = sqlite3.connect("data.sqlite3")

# List all tables
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print("=== All tables ===")
for row in cur.fetchall():
    print(f"  {row[0]}")

conn.close()
