"""Check backtest parameters and trades from DB."""

import json
import sqlite3
import sys

sys.path.insert(0, "D:/bybit_strategy_tester_v2")

STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"

conn = sqlite3.connect("data.sqlite3")
rows = conn.execute(
    "SELECT strategy_type, parameters, start_date, end_date, total_trades, created_at "
    "FROM backtests WHERE strategy_id=? ORDER BY created_at DESC LIMIT 5",
    (STRATEGY_ID,),
).fetchall()

print("Recent backtests:")
for r in rows:
    params = json.loads(r[1]) if r[1] else {}
    print(f"  created: {r[5]}, type: {r[0]}, trades: {r[4]}, dates: {r[2]}-{r[3]}")
    print(f"  params: {json.dumps(params)[:400]}")
    print()

# Get most recent backtest trades
row = conn.execute(
    "SELECT trades FROM backtests WHERE strategy_id=? ORDER BY created_at DESC LIMIT 1",
    (STRATEGY_ID,),
).fetchone()
trades = json.loads(row[0]) if row else []
conn.close()

print(f"\nMost recent backtest: {len(trades)} trades")
if trades:
    print("First 5 trades:")
    for t in trades[:5]:
        print(f"  side={t.get('side')}  entry={t.get('entry_time')}  price={t.get('entry_price')}")
