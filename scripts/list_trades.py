"""List all trades from the c634b8c8 backtest (slippage=0, 150 trades) with entry times."""

import json
import sqlite3
from datetime import datetime

conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
c = conn.cursor()
c.execute("SELECT trades FROM backtests WHERE id = 'c634b8c8-aa35-45bf-9137-07d3cbe8ec61'")
row = c.fetchone()
conn.close()

trades = json.loads(row[0])
print(f"Total: {len(trades)} trades")
print(f"\n{'#':3s} {'Entry':20s} {'Side':5s} {'EP':10s} {'XP':10s} {'PnL':10s} {'Exit comment'}")
print("-" * 75)
for i, t in enumerate(trades, 1):
    entry = t.get("entry_time", "?")
    side = t.get("side", "?")
    ep = t.get("entry_price", 0)
    xp = t.get("exit_price", 0) or t.get("exit_price", 0)
    pnl = t.get("pnl", 0) or t.get("profit", 0)
    comment = t.get("exit_comment", "") or t.get("exit_type", "") or ""
    print(f"{i:3d} {entry!s:20s} {side:5s} {ep:10.4f} {xp:10.4f} {pnl:10.4f} {comment}")
