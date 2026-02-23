"""Debug trade #100 to understand TV TP calculation."""

import datetime as dt
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
conn = sqlite3.connect(DB_PATH)

# Trade 100: entry long at 2026-02-06 00:30 UTC, entry=61334.10
# TV TP hit at 62923.80 (2026-02-06 03:45 Moscow = 00:45 UTC)
start_ms = int(dt.datetime(2026, 2, 5, 23, 45, tzinfo=dt.UTC).timestamp() * 1000)
end_ms = int(dt.datetime(2026, 2, 6, 2, 0, tzinfo=dt.UTC).timestamp() * 1000)
df = pd.read_sql_query(
    "SELECT open_time, open_price, high_price, low_price, close_price "
    "FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
    "AND open_time >= ? AND open_time <= ? ORDER BY open_time",
    conn,
    params=(start_ms, end_ms),
)
conn.close()

df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
print("Bars around trade 100 entry (2026-02-06 00:30 UTC):")
print(df[["time", "open_price", "high_price", "low_price", "close_price"]].to_string())
print()

entry_price = 61334.10
print(f"Entry price (close of 00:30 bar): {entry_price}")
print(f"TP 1.5% from close (signal_price): {entry_price * 1.015:.2f}")
print("TV actual TP hit price: 62923.80")
print(f"62923.80 / 61334.10 - 1 = {62923.80 / 61334.10 - 1:.4%}")
print()
print("Same-bar re-entry scenario:")
print("Trade 99 SL exit bar: 2026-02-06 00:00 UTC (Moscow 03:00)")
print("Trade 100 re-entry bar: 2026-02-06 00:30 UTC (Moscow 03:30) -- next bar")
print()
# Check the entry bar's OPEN
mask = df["time"] == pd.Timestamp("2026-02-06 00:30", tz="UTC")
row = df[mask]
if not row.empty:
    open_p = float(row["open_price"].iloc[0])
    close_p = float(row["close_price"].iloc[0])
    high_p = float(row["high_price"].iloc[0])
    print(f"00:30 bar: open={open_p}, high={high_p}, close={close_p}")
    print(f"TP from OPEN: {open_p * 1.015:.2f}")
    print(f"TP from CLOSE: {close_p * 1.015:.2f}")

# Check 00:45 bar (TV TP exit time Moscow 03:45 = UTC 00:45)
mask2 = df["time"] == pd.Timestamp("2026-02-06 00:45", tz="UTC")
row2 = df[mask2]
if not row2.empty:
    high2 = float(row2["high_price"].iloc[0])
    close2 = float(row2["close_price"].iloc[0])
    print(f"\n00:45 bar (TV TP hit bar): high={high2}, close={close2}")
    print(f"Does 62923.80 <= high? {high2 >= 62923.80}")
    print(f"close={close2}")
