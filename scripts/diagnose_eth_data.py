"""
Diagnose trade #1 mismatch. TV expects first trade entry at 2025-01-01T10:30 UTC (13:30+03).
Our first trade is at 2025-01-02T22:00 UTC at price 3433.46 - completely different.

Let's check:
1. What ETHUSDT 30m data we have around 2025-01-01
2. What the RSI values look like at that time
3. Whether signals are being generated for 2025-01-01
"""

import sqlite3
import sys

sys.path.insert(0, "d:\\bybit_strategy_tester_v2")

import numpy as np
import pandas as pd

from backend.core.indicators import calculate_rsi

# Connect to both databases
conn_main = sqlite3.connect("data.sqlite3")
conn_klines = sqlite3.connect("bybit_klines_15m.db")

# Check what ETHUSDT 30m data we have
cur_k = conn_klines.cursor()
cur_k.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur_k.fetchall()]
print("=== klines DB tables ===", tables[:15])

# Check for ETHUSDT 30m
for t in tables:
    if "ETH" in t.upper() and "30" in t:
        print(f"\nTable: {t}")
        cur_k.execute(f"SELECT MIN(open_time), MAX(open_time), COUNT(*) FROM '{t}'")
        r = cur_k.fetchone()
        print(f"  Range: {r[0]} to {r[1]}, count: {r[2]}")
        # Get first few rows
        cur_k.execute(f"SELECT open_time, open, high, low, close FROM '{t}' ORDER BY open_time LIMIT 5")
        for row in cur_k.fetchall():
            print(f"  {row}")

# Check if there's a main DB table with klines
cur_m = conn_main.cursor()
cur_m.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%kline%'")
kline_tables = [r[0] for r in cur_m.fetchall()]
print("\n=== main DB kline tables ===", kline_tables)

conn_main.close()
conn_klines.close()
