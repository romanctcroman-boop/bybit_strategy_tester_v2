"""
Dump all TV trades around the Feb 12 divergence with their timestamps.
"""

import csv

import pandas as pd

TV_FILE = r"c:\Users\roman\Downloads\z4.csv"
with open(TV_FILE, encoding="cp1251") as f:
    reader = csv.reader(f, delimiter=";")
    rows = list(reader)


def utc3_to_utc(s):
    dt = pd.to_datetime(s.strip())
    return dt - pd.Timedelta(hours=3)


print(f"Total rows: {len(rows)} (header + {len(rows) - 1} data rows)")
print(f"Trades: {(len(rows) - 1) // 2}")
print()

# Print all trades
print(f"{'#':>4}  {'Type':12}  {'TV Time (UTC+3)':18}  {'UTC Time':18}  {'Signal':8}  {'Price':>8}")
for i in range(1, len(rows), 2):
    exit_row = rows[i]
    if i + 1 >= len(rows):
        break
    entry_row = rows[i + 1]
    try:
        trade_id = exit_row[0]
        exit_type = exit_row[1]  # 'Exit short' or 'Exit long'
        exit_time = exit_row[2]
        exit_sig = exit_row[3]
        entry_type = entry_row[1]  # 'Entry short' or 'Entry long'
        entry_time = entry_row[2]
        entry_sig = entry_row[3]
        entry_price = entry_row[4]
        entry_utc = utc3_to_utc(entry_time)
        print(
            f"{trade_id:>4}  {entry_type:12}  {entry_time:18}  {str(entry_utc)[:16]:18}  {entry_sig:8}  {entry_price:>8}"
        )
    except (IndexError, ValueError) as e:
        print(f"  ROW {i} ERROR: {e}  {rows[i]}")
