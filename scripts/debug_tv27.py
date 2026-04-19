"""Debug TV#27 same-bar entry+exit."""

import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

DB_PATH = "d:/bybit_strategy_tester_v2/data.sqlite3"

conn = sqlite3.connect(DB_PATH)
# Get bars around 2025-03-03 14:00 UTC
start_ms = int(pd.Timestamp("2025-03-03 13:00:00", tz="UTC").timestamp() * 1000)
end_ms = int(pd.Timestamp("2025-03-03 16:00:00", tz="UTC").timestamp() * 1000)
df = pd.read_sql_query(
    "SELECT open_time, open_price as open, high_price as high, "
    "low_price as low, close_price as close "
    "FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='30' AND market_type='linear' "
    "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
    conn,
    params=(start_ms, end_ms),
)
conn.close()

df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
print("Bars around TV#27 entry (2025-03-03 14:00 UTC):")
print(df[["ts", "open", "high", "low", "close"]].to_string())

# TV#26 is short entry @ 93061.1, exit @ 2025-03-03 06:30 UTC
# TV#27 is short entry @ 93163.9, TV exit @ 2025-03-03 15:00 UTC (= 18:00 UTC+3)
#
# entry bar 14:00 UTC: open should be ~93163.9
# TP for short = 93163.9 * (1 - 0.015) = 91766.4
# The bar 14:00 UTC: does low <= 91766.4? Let's check

entry_bar = df[abs(df["open"] - 93163.9) < 50]
print("\nEntry bar candidates:")
print(entry_bar[["ts", "open", "high", "low", "close"]].to_string())

print(f"\nTP price = {93163.9 * (1 - 0.015):.1f}")
print("If low of 14:00 bar is <= 91766.4, TP triggers same bar")

# TV exit price = 89270.3 (bar close)
# If this is the close of bar 14:00, that's a huge drop
