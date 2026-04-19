import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")
cur = conn.cursor()

cur.execute("SELECT id, name, created_at FROM strategies WHERE name LIKE '%RSI%' ORDER BY created_at DESC LIMIT 30")
rows = cur.fetchall()
print("=== RSI Strategies ===")
for r in rows:
    print(r[0], "|", r[1], "|", r[2])

print("\n=== Backtests for RSI strategies ===")
if rows:
    for strat_id, name, _ in rows:
        cur.execute(
            "SELECT id, strategy_id, created_at, symbol, timeframe FROM backtests WHERE strategy_id=? ORDER BY created_at DESC LIMIT 5",
            (strat_id,),
        )
        bts = cur.fetchall()
        if bts:
            print(f"\n{name} ({strat_id}):")
            for b in bts:
                print("  BT:", b)

conn.close()
