"""
Deep dive into anomalies #2 and #4 where rsi_prev < 52 but TV fires.
This means TV is NOT using a standard crossunder condition.
"""

import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from backend.core.indicators import calculate_rsi as wilder_rsi

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
ETH_CACHE = r"d:\bybit_strategy_tester_v2\data\eth_30m_cache.csv"


def load_btc():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT open_time, open_price, high_price, low_price, close_price FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='30' ORDER BY open_time"
    ).fetchall()
    conn.close()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df.set_index("ts")


btc = load_btc()
closes = btc["close"].values
idx = btc.index
P = 14

# Compute full RSI series
rsi_full = wilder_rsi(btc["close"], P)
rsi_s = pd.Series(rsi_full, index=idx)

# For each anomaly, print 20-bar RSI history
anomalies = [
    ("2025-02-19 15:30", "short", 52),
    ("2025-04-19 20:30", "short", 52),
]

for bar_str, direction, level in anomalies:
    t = pd.Timestamp(bar_str)
    # find position in index
    if t not in idx:
        print(f"{bar_str}: NOT IN INDEX")
        continue
    pos = idx.get_loc(t)
    start = max(0, pos - 20)
    end = pos + 5
    print(f"\n{'=' * 60}")
    print(f"Anomaly: {bar_str} ({direction}, level={level})")
    print(f"{'=' * 60}")
    print(f"{'Timestamp':<22} {'Close':>10} {'RSI':>10} {'Prev RSI':>10} {'Standard Cross':>15}")
    for i in range(start, min(end, len(idx))):
        ts = idx[i]
        rsi_val = rsi_s.iloc[i]
        prev_rsi = rsi_s.iloc[i - 1] if i > 0 else float("nan")
        cross = ">>> CROSS" if prev_rsi >= level and rsi_val < level else ""
        marker = "<<< TV" if ts == t else ""
        print(
            f"{ts!s:<22} {float(btc['close'].iloc[i]):>10.2f} {rsi_val:>10.4f} {prev_rsi:>10.4f} {cross:>15} {marker}"
        )

    print(f"\nRSI at bar T-1: {rsi_s.get(t - pd.Timedelta('30min'), float('nan')):.4f}")
    print(f"RSI at bar T  : {rsi_s.get(t, float('nan')):.4f}")

    # Check if there was a recent previous cross
    print("\nLooking for previous crossunder within last 30 bars:")
    for i in range(max(0, pos - 30), pos + 1):
        ts = idx[i]
        rsi_val = rsi_s.iloc[i]
        prev_rsi = rsi_s.iloc[i - 1] if i > 0 else float("nan")
        if prev_rsi >= level and rsi_val < level:
            print(f"  Cross at {ts}: prev={prev_rsi:.4f} -> {rsi_val:.4f}")
