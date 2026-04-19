"""Compare exit times/prices between our engine and TV for first 10 trades."""

import sys

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import sqlite3
from datetime import datetime

import pandas as pd

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"

# Our engine results (from _rerun_rsi4.py output)
our_trades = [
    ("short", "2025-11-01T11:15:00", 110003.6, "2025-11-03T03:15:00", 108353.5, "TP"),
    ("long", "2025-11-03T05:00:00", 107903.8, "2025-11-04T06:00:00", 104666.7, "SL"),
    ("long", "2025-11-04T06:00:00", 104835.7, "2025-11-04T17:15:00", 101690.6, "SL"),
    ("long", "2025-11-04T18:30:00", 101212.5, "2025-11-05T12:30:00", 102730.7, "TP"),
    ("short", "2025-11-05T20:45:00", 103789.8, "2025-11-06T14:45:00", 102233.0, "TP"),
    ("long", "2025-11-06T16:45:00", 100806.7, "2025-11-07T03:15:00", 102318.8, "TP"),
    ("short", "2025-11-07T04:30:00", 101766.1, "2025-11-07T11:15:00", 100239.6, "TP"),
    ("long", "2025-11-07T11:30:00", 100110.0, "2025-11-07T16:30:00", 101611.6, "TP"),
    ("short", "2025-11-08T02:30:00", 103087.8, "2025-11-08T14:15:00", 101541.5, "TP"),
    ("short", "2025-11-08T21:00:00", 101983.3, "2025-11-09T20:15:00", 105042.8, "SL"),
]

# TV CSV data (UTC+3 times)
tv_trades = [
    (1, "short", "2025-11-01 14:30", 110003.6, "TP", "2025-11-03 06:00", 108353.5),
    (2, "long", "2025-11-03 08:15", 107903.8, "SL", "2025-11-04 08:45", 104666.6),
    (3, "long", "2025-11-04 09:15", 104835.7, "SL", "2025-11-04 20:00", 101690.6),
    (4, "long", "2025-11-04 21:45", 101212.5, "TP", "2025-11-05 15:15", 102730.7),
    (5, "short", "2025-11-06 00:00", 103789.8, "TP", "2025-11-06 17:30", 102232.9),
    (6, "long", "2025-11-06 20:00", 100806.7, "TP", "2025-11-07 05:15", 102260.8),
    (7, "short", "2025-11-07 07:45", 101766.1, "TP", "2025-11-07 13:15", 100232.2),
    (8, "long", "2025-11-07 14:45", 100110.0, "TP", "2025-11-08 03:45", 101576.4),
    (9, "short", "2025-11-08 05:45", 103087.8, "TP", "2025-11-08 16:15", 101533.5),
    (10, "short", "2025-11-09 00:15", 101983.3, "SL", "2025-11-09 23:00", 105142.8),
]


def utc3_to_utc(s):
    """Convert UTC+3 string to naive UTC datetime."""
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M")
    return dt - pd.Timedelta(hours=3)


def get_bars(conn, start_utc, end_utc):
    start_ms = (
        int(start_utc.timestamp() * 1000)
        if hasattr(start_utc, "timestamp")
        else int(pd.Timestamp(start_utc).timestamp() * 1000)
    )
    end_ms = (
        int(end_utc.timestamp() * 1000)
        if hasattr(end_utc, "timestamp")
        else int(pd.Timestamp(end_utc).timestamp() * 1000)
    )
    df = pd.read_sql_query(
        "SELECT open_time, open_price, high_price, low_price, close_price FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
        "AND open_time >= ? AND open_time <= ? ORDER BY open_time",
        conn,
        params=(start_ms, end_ms),
    )
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms")
    return df


print("=" * 100)
print("EXIT TIME/PRICE COMPARISON: Our Engine vs TV")
print("=" * 100)
print(
    f"{'#':<3} {'T':<6} {'our_exit_utc':<22} {'our_px':<12} {'tv_exit_utc':<22} {'tv_px':<12} {'px_diff':<10} {'t_diff'}"
)
print("-" * 100)

conn = sqlite3.connect(DB_PATH)

for i, (our, tv) in enumerate(zip(our_trades, tv_trades)):
    tv_exit_utc = utc3_to_utc(tv[5])
    our_exit_ts = pd.Timestamp(our[3])
    px_diff = our[4] - tv[6]
    t_diff_min = (our_exit_ts - pd.Timestamp(tv_exit_utc)).total_seconds() / 60
    print(
        f"{i + 1:<3} {our[0]:<6} {str(our_exit_ts)[:19]:<22} {our[4]:<12.1f} {str(tv_exit_utc)[:19]:<22} {tv[6]:<12.1f} {px_diff:<10.2f} {t_diff_min:+.0f}min"
    )

print()
print("=== Detailed analysis for TP trades with price differences ===")

# Check trades where prices differ significantly (TP trades)
tp_trades = [
    (i, our, tv) for i, (our, tv) in enumerate(zip(our_trades, tv_trades)) if our[5] == "TP" and abs(our[4] - tv[6]) > 1
]

for idx, our, tv in tp_trades:
    print(f"\nTrade #{idx + 1} ({our[0]}) entry={our[2]}")
    entry = our[2]
    direction = our[0]
    tp_pct = 0.015
    sl_pct = 0.03

    if direction == "long":
        tp_theoretical = entry * (1 + tp_pct)
        sl_theoretical = entry * (1 - sl_pct)
    else:
        tp_theoretical = entry * (1 - tp_pct)
        sl_theoretical = entry * (1 + sl_pct)

    print(f"  TP theoretical = {tp_theoretical:.4f}")
    print(f"  Our exit price = {our[4]:.4f}")
    print(f"  TV  exit price = {tv[6]:.4f}")
    print(f"  Diff = {our[4] - tv[6]:.4f}")

    # TV entry bar time (UTC+3 - 3h = UTC)
    tv_entry_utc = utc3_to_utc(tv[2])
    tv_exit_utc = utc3_to_utc(tv[5])
    our_exit_ts = pd.Timestamp(our[3])

    # Show bars around the TP hit
    start_ts = tv_exit_utc - pd.Timedelta(hours=1)
    end_ts = tv_exit_utc + pd.Timedelta(hours=1)
    bars = get_bars(conn, start_ts, end_ts)
    print(f"  Bars around TV exit {tv_exit_utc} UTC:")
    for _, row in bars.iterrows():
        marker = ""
        if direction == "long" and row["high_price"] >= tp_theoretical:
            marker = " ← TP TOUCHED"
        elif direction == "short" and row["low_price"] <= tp_theoretical:
            marker = " ← TP TOUCHED"
        if row["ts"] == our_exit_ts.replace(tzinfo=None):
            marker += " ← OUR_EXIT"
        tv_exit_bar = pd.Timestamp(tv_exit_utc)
        if abs((row["ts"] - tv_exit_bar).total_seconds()) < 60:
            marker += " ← TV_EXIT_BAR"
        print(
            f"    {str(row['ts'])[:19]:20} O={row['open_price']:10.1f} H={row['high_price']:10.1f} L={row['low_price']:10.1f} C={row['close_price']:10.1f}{marker}"
        )

conn.close()
