"""Check first trades from new backtest."""

import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")
row = conn.execute("SELECT trades FROM backtests WHERE id=?", ("4d48fc0a-71cb-468b-b55a-0a6156cea940",)).fetchone()
trades = json.loads(row[0])
conn.close()

print(f"Total trades: {len(trades)}")
print("First 8:")
for t in trades[:8]:
    print(f"  side={t['side']:4s}  entry={t['entry_time']}  exit={t['exit_time']}  price={t['entry_price']:.2f}")
