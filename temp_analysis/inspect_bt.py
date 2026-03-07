import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get most recent backtest
BT_ID = "e4e67c82-1258-4ce5-bb80-48c22ebbe019"
cur.execute("SELECT * FROM backtests WHERE id=?", (BT_ID,))
src = dict(cur.fetchone())
print(f"id={src['id']}  symbol={src['symbol']}  trades={src['total_trades']}")

# Equity curve
ec = json.loads(src["equity_curve"]) if src["equity_curve"] else {}
print(f"equity_curve keys: {list(ec.keys()) if isinstance(ec, dict) else type(ec)}")
if isinstance(ec, dict):
    for k, v in ec.items():
        sample = v[:3] if isinstance(v, list) else v
        print(f"  {k}: {sample}  (len={len(v) if isinstance(v, list) else '-'})")

# Trades JSON in backtests table
tj = json.loads(src["trades"]) if src["trades"] else None
if tj:
    print(f"\ntrades JSON: {len(tj)} entries")
    print("Keys:", list(tj[0].keys()))
    print("Trade[0]:", {k: tj[0][k] for k in list(tj[0].keys())})
else:
    print("\nNo trades JSON in backtests table")

# Trades table
cur.execute("SELECT * FROM trades WHERE backtest_id=? LIMIT 3", (BT_ID,))
trows = [dict(r) for r in cur.fetchall()]
print(f"\ntrades table rows: {len(trows)}")
if trows:
    print("Keys:", list(trows[0].keys()))
    print("Row[0]:", trows[0])

conn.close()
