"""Show full details of first few trades in the backtest."""

import json
import sqlite3

conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
cursor = conn.cursor()

bt_id = "bbab7cbc-dd59-4b53-9f46-24f8d24b8f95"
cursor.execute("SELECT trades FROM backtests WHERE id = ?", (bt_id,))
row = cursor.fetchone()
trades = json.loads(row[0])
print(f"Total trades: {len(trades)}")

# Show full first trade
print("\n--- Trade 1 (full) ---")
print(json.dumps(trades[0], indent=2))

print("\n--- Trade 2 (full) ---")
print(json.dumps(trades[1], indent=2))

# Summarize entry prices
print("\n--- All entry times and prices ---")
for i, t in enumerate(trades, 1):
    entry_time = t.get("entry_time", "?")
    ep = t.get("entry_price", 0)
    xp = t.get("exit_price", 0)
    side = t.get("side", "?")
    pnl = t.get("pnl", 0)
    print(
        f"  {i:3}. {side:4} entry={entry_time}  ep={float(ep):>10.4f}  xp={float(xp):>10.4f}  pnl={float(pnl):>10.4f}"
    )

conn.close()
