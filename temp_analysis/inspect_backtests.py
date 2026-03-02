import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")
strategy_id = "149454c2-76ca-42d7-8f32-c2329dc396ac"

# Inspect backtests table
cur = conn.execute("PRAGMA table_info(backtests)")
cols_bt = [c[1] for c in cur.fetchall()]
print("=== backtests columns ===")
for c in cols_bt:
    print(f"  {c}")

# Get last 3 backtests for Strategy-A2
print(f"\n=== Backtests for Strategy-A2 ===")
cur = conn.execute(
    "SELECT * FROM backtests WHERE strategy_id = ? ORDER BY created_at DESC LIMIT 3",
    (strategy_id,),
)
rows = cur.fetchall()
if not rows:
    print("  No backtests found for this strategy ID")
else:
    for row in rows:
        bt = dict(zip(cols_bt, row, strict=False))
        print(f"\n  BT ID: {bt.get('id', '')[:8]}...")
        for k in [
            "status",
            "total_trades",
            "net_profit",
            "win_rate",
            "sharpe_ratio",
            "profit_factor",
            "start_date",
            "end_date",
            "created_at",
            "config",
        ]:
            v = bt.get(k)
            if k == "config" and v:
                try:
                    v = json.dumps(json.loads(v), indent=4)
                except Exception:
                    pass
            print(f"    {k}: {v}")

# Inspect trades table
print("\n=== trades columns ===")
cur = conn.execute("PRAGMA table_info(trades)")
cols_tr = [c[1] for c in cur.fetchall()]
for c in cols_tr:
    print(f"  {c}")

# Most recent backtest ID for A2 (try all strategies to see if any trades exist)
print("\n=== Sample of most recent backtest IDs in backtests table ===")
cur = conn.execute("SELECT id, strategy_id, created_at FROM backtests ORDER BY created_at DESC LIMIT 10")
for r in cur.fetchall():
    print(f"  {str(r[0])[:8]}... | strategy: {str(r[1])[:8]}... | {r[2]}")

conn.close()
