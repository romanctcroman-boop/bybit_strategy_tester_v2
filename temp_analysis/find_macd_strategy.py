import sqlite3

conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
cur = conn.cursor()

# Find MACD strategies
cur.execute("""
    SELECT id, name, strategy_type, is_deleted, created_at
    FROM strategies
    WHERE LOWER(strategy_type) LIKE '%macd%'
       OR LOWER(name) LIKE '%macd%'
    ORDER BY created_at DESC
    LIMIT 30
""")
rows = cur.fetchall()
print(f"MACD strategies found: {len(rows)}")
for r in rows:
    print(f"  id={r[0]} name={r[1]} type={r[2]} deleted={r[3]} created={r[4]}")

# Also show all strategy types
print("\nAll strategy types:")
cur.execute("SELECT DISTINCT strategy_type, COUNT(*) as cnt FROM strategies GROUP BY strategy_type ORDER BY cnt DESC")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

conn.close()
