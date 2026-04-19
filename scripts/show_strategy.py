"""Show strategy configuration."""

import json
import sqlite3

conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
c = conn.cursor()
c.execute("""
    SELECT id, name, symbol, timeframe, parameters, config
    FROM strategies
    WHERE id = '01cd8861-60eb-40dd-a9a9-8baa6f2db0fa'
""")
row = c.fetchone()
if row:
    print(f"ID: {row[0]}")
    print(f"Name: {row[1]}")
    print(f"Symbol: {row[2]}, TF: {row[3]}")
    if row[4]:
        params = json.loads(row[4])
        print(f"Parameters: {json.dumps(params, indent=2)}")
    if row[5]:
        config = json.loads(row[5])
        print(f"Config keys: {list(config.keys())}")
        # Show relevant backtest settings
        for key in ["slippage", "commission", "leverage", "position_size", "stop_loss", "take_profit"]:
            if key in config:
                print(f"  {key}: {config[key]}")
else:
    print("Strategy not found")

# Check strategy columns
c.execute("PRAGMA table_info(strategies)")
print("\nStrategy columns:", [r[1] for r in c.fetchall()])
conn.close()
