import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")

# Get full Strategy-A2 row
cur = conn.execute("SELECT * FROM strategies WHERE name = 'Strategy-A2' ORDER BY updated_at DESC LIMIT 1")
row = cur.fetchone()
cur2 = conn.execute("PRAGMA table_info(strategies)")
cols = [c[1] for c in cur2.fetchall()]

print("=== Strategy-A2 fields ===")
for col, val in zip(cols, row):
    if val is not None and val != "" and val is not False:
        if col in ("parameters", "builder_graph", "builder_blocks", "builder_connections", "tags"):
            try:
                parsed = json.loads(val) if isinstance(val, str) else val
                print(f"{col}:")
                print(json.dumps(parsed, indent=2, ensure_ascii=False))
            except Exception:
                print(f"{col}: {val}")
        else:
            print(f"{col}: {val}")

# Also check backtests table
print("\n=== backtest_results table columns ===")
cur = conn.execute("PRAGMA table_info(backtest_results)")
for c in cur.fetchall():
    print(f"  {c[1]} ({c[2]})")

# Get last backtest for Strategy-A2
strategy_id = row[0]
print(f"\n=== Last backtest for Strategy-A2 (id={strategy_id[:8]}...) ===")
cur = conn.execute(
    "SELECT id, status, total_trades, net_profit, win_rate, sharpe_ratio, "
    "profit_factor, start_date, end_date, created_at FROM backtest_results "
    "WHERE strategy_id = ? ORDER BY created_at DESC LIMIT 3",
    (strategy_id,),
)
for r in cur.fetchall():
    print(
        f"  BT_ID: {str(r[0])[:8]}... | status: {r[1]} | trades: {r[2]} | "
        f"net_profit: {r[3]} | win_rate: {r[4]} | sharpe: {r[5]} | PF: {r[6]} | "
        f"{r[7]} → {r[8]} | created: {r[9]}"
    )

conn.close()
