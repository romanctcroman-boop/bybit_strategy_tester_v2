"""Query backtest results via API endpoint."""

import sys

sys.path.insert(0, "d:\\bybit_strategy_tester_v2")

import sqlite3

# Direct SQLite query - avoid SQLAlchemy quoting issues
conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cursor.fetchall()]
print("Tables:", tables)

# Find backtest-related tables
backtest_tables = [t for t in tables if "backtest" in t.lower() or "trade" in t.lower()]
print("Backtest tables:", backtest_tables)

# Check schema of backtest tables
for t in backtest_tables:
    cursor.execute(f"PRAGMA table_info({t})")
    cols = [(r[1], r[2]) for r in cursor.fetchall()]
    print(f"\nTable {t}: {cols[:8]}")

conn.close()
