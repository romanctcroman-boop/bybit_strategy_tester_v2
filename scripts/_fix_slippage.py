"""Update strategy slippage to 0.0 to match TradingView settings."""
import json
import sqlite3

STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"
conn = sqlite3.connect("data.sqlite3")

row = conn.execute("SELECT parameters FROM strategies WHERE id=?", (STRATEGY_ID,)).fetchone()
params = json.loads(row[0])
print("Before _slippage:", params.get("_slippage"))

params["_slippage"] = 0.0
conn.execute("UPDATE strategies SET parameters=? WHERE id=?", (json.dumps(params), STRATEGY_ID))
conn.commit()

row2 = conn.execute("SELECT parameters FROM strategies WHERE id=?", (STRATEGY_ID,)).fetchone()
params2 = json.loads(row2[0])
print("After  _slippage:", params2.get("_slippage"))
conn.close()
print("Done.")
