"""Find the gaps between consecutive trades to identify where the missing TV trade might be."""

import json
import sqlite3
from datetime import datetime

conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
c = conn.cursor()
c.execute("SELECT trades FROM backtests WHERE id = 'c634b8c8-aa35-45bf-9137-07d3cbe8ec61'")
row = c.fetchone()
conn.close()

trades = json.loads(row[0])

print("Looking for large gaps between trades (>7 days):")
print(f"\n{'#':3s} {'Entry':20s} {'Exit':20s} {'PnL':10s} {'Gap_before':15s}")
print("-" * 75)

prev_exit = None
for i, t in enumerate(trades, 1):
    entry = t.get("entry_time", "?")
    exit_time = t.get("exit_time", "?")
    pnl = t.get("pnl", 0)

    # Calculate gap from previous trade exit to this entry
    gap_str = ""
    if prev_exit and entry != "?":
        try:
            e = datetime.fromisoformat(str(entry))
            pe = datetime.fromisoformat(str(prev_exit))
            gap_days = (e - pe).total_seconds() / 86400
            if gap_days > 7:
                gap_str = f"*** {gap_days:.1f} days ***"
            else:
                gap_str = f"{gap_days:.1f}d"
        except Exception:
            pass

    if gap_str.startswith("***") or i <= 3 or i >= len(trades) - 2:
        print(f"{i:3d} {entry!s:20s} {exit_time!s:20s} {pnl:10.4f} {gap_str}")

    prev_exit = exit_time

print("\n\nAll gaps > 3 days:")
prev_exit = None
for i, t in enumerate(trades, 1):
    entry = t.get("entry_time", "?")
    exit_time = t.get("exit_time", "?")
    pnl = t.get("pnl", 0)
    side = t.get("side", "?")

    if prev_exit and entry != "?":
        try:
            e = datetime.fromisoformat(str(entry))
            pe = datetime.fromisoformat(str(prev_exit))
            gap_days = (e - pe).total_seconds() / 86400
            if gap_days > 3:
                print(f"  Gap {gap_days:.1f}d: after trade {i - 1} (exit {prev_exit}) → trade {i} {side} entry {entry}")
        except Exception:
            pass

    prev_exit = exit_time
