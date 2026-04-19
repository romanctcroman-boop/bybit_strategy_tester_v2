"""Show backtest parameters."""

import json
import sqlite3

conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
c = conn.cursor()
c.execute("SELECT parameters FROM backtests WHERE id='bbab7cbc-dd59-4b53-9f46-24f8d24b8f95'")
row = c.fetchone()
params = json.loads(row[0])
print(json.dumps(params, indent=2))
conn.close()
