import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")
rows = conn.execute(
    "SELECT id, status, total_trades, created_at FROM backtests ORDER BY created_at DESC LIMIT 5"
).fetchall()
for r in rows:
    print(r)
print()
# Check specific backtest
bt_id = "4d48fc0a-71cb-468b-b55a-0a6156cea940"
row = conn.execute("SELECT id, status, total_trades, created_at, trades FROM backtests WHERE id=?", (bt_id,)).fetchone()
if row:
    print(f"ID: {row[0]}")
    print(f"Status: {row[1]}")
    print(f"Total trades: {row[2]}")
    print(f"Created at: {row[3]}")
    trades_raw = row[4]
    if trades_raw:
        trades = json.loads(trades_raw)
        print(f"Trades count in JSON: {len(trades)}")
        print("\nFirst 3 trades:")
        for t in trades[:3]:
            print(
                f"  side={t.get('side')} entry_time={t.get('entry_time')} entry_price={t.get('entry_price')} pnl={t.get('pnl')}"
            )
    else:
        print("No trades JSON")
conn.close()
