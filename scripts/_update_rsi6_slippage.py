"""Update Strategy_RSI_L\\S_6 in DB: set _slippage=0.0 to match TV export."""

import json
import sqlite3

STRATEGY_ID = "5c03fd86-a821-4a62-a783-4d617bf25bc7"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT name, parameters FROM strategies WHERE id=?", (STRATEGY_ID,))
row = cur.fetchone()
print(f"Strategy: {row[0]}")
params = json.loads(row[1])

print(f"Before: _slippage = {params['_slippage']}")
params["_slippage"] = 0.0
print(f"After:  _slippage = {params['_slippage']}")

cur.execute(
    "UPDATE strategies SET parameters=?, updated_at=datetime('now') WHERE id=?",
    (json.dumps(params), STRATEGY_ID),
)
conn.commit()

# Verify
cur.execute("SELECT parameters FROM strategies WHERE id=?", (STRATEGY_ID,))
verified = json.loads(cur.fetchone()[0])
assert verified["_slippage"] == 0.0, "Update failed!"
print("DB updated and verified OK")
conn.close()
