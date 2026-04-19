"""
Check TV entry prices vs OHLCV data to understand if TV enters at close or open.
Also analyze what signals our engine generates vs what TV has.
"""

import csv
import sqlite3
import sys

TV_CSV = r"C:\Users\roman\Downloads\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-02-23.csv"

# Load TV trades (entries only)
tv_entries = []
with open(TV_CSV, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        if row.get("\ufeff№ Сделки", row.get("№ Сделки", "")).strip() == "":
            continue
        trade_type = row.get("Тип", "")
        if "Entry" not in trade_type:
            continue
        dt_str = row.get("Дата и время", "")
        price = float(row.get("Цена USDT", 0))
        signal = row.get("Сигнал", "")
        tv_entries.append({"dt_str": dt_str, "price": price, "signal": signal, "type": trade_type})

print(f"TV entries: {len(tv_entries)}")
print("\nFirst 5 TV entries:")
for e in tv_entries[:5]:
    print(f"  {e['dt_str']} | {e['type']:12} | {e['signal']:8} | price={e['price']:.1f}")

# Now look at OHLCV data for these entry bars
# DB has bybit_klines_15m.db
import os

db_files = ["bybit_klines_15m.db", "data.sqlite3"]
kline_conn = None
for dbf in db_files:
    if os.path.exists(dbf):
        conn = sqlite3.connect(dbf)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        tables = [t[0] for t in tables]
        print(f"\nDB {dbf}: tables = {tables[:10]}")
        if any("kline" in t.lower() or "ohlcv" in t.lower() for t in tables):
            kline_conn = conn
            kline_db = dbf
            kline_tables = [t for t in tables if "kline" in t.lower() or "ohlcv" in t.lower()]
            print(f"  Kline tables: {kline_tables}")
        conn.close()

if not kline_conn:
    print("No kline DB found, checking data.sqlite3 tables more carefully...")
    conn = sqlite3.connect("data.sqlite3")
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"data.sqlite3 tables: {[t[0] for t in tables]}")
    conn.close()
    sys.exit(1)
