"""Show strategy configuration from strategies table."""

import json
import sqlite3

conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
c = conn.cursor()
c.execute("""
    SELECT id, name, symbol, timeframe, direction, initial_capital, position_size,
           stop_loss_pct, take_profit_pct, parameters
    FROM strategies
    WHERE id = '01cd8861-60eb-40dd-a9a9-8baa6f2db0fa'
""")
row = c.fetchone()
if row:
    print(f"ID: {row[0]}")
    print(f"Name: {row[1]}")
    print(f"Symbol: {row[2]}, TF: {row[3]}")
    print(f"Direction: {row[4]}")
    print(f"Initial capital: {row[5]}")
    print(f"Position size: {row[6]}")
    print(f"SL: {row[7]}, TP: {row[8]}")
    if row[9]:
        params = json.loads(row[9])
        print(f"Parameters: {json.dumps(params, indent=2)}")
else:
    print("Strategy not found")
conn.close()
