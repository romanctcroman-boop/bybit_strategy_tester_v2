import sqlite3

conn = sqlite3.connect("data.sqlite3")

# First inspect the strategies table schema
cur = conn.execute("PRAGMA table_info(strategies)")
print("=== strategies columns ===")
for col in cur.fetchall():
    print(f"  {col[1]} ({col[2]})")

print()
cur = conn.execute("SELECT id, name, updated_at FROM strategies ORDER BY updated_at DESC LIMIT 20")
print("=== Recent strategies ===")
for row in cur.fetchall():
    print(f"ID: {str(row[0])[:8]}... | Name: {row[1]} | Updated: {row[2]}")
conn.close()
