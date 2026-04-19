"""Debug TV#2 carry-over signal issue."""

import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import sqlite3

import numpy as np
import pandas as pd

# Load the OHLCV data
conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
df = pd.read_sql_query(
    """
    SELECT timestamp, open, high, low, close, volume FROM klines_30m
    WHERE symbol='BTCUSDT' AND timestamp >= '2025-01-06 22:00:00' AND timestamp <= '2025-01-07 03:00:00'
    ORDER BY timestamp
""",
    conn,
)
conn.close()

print("OHLCV bars around TV#2:")
print(df.to_string())

# TV#1 closes at 2025-01-07 00:30 UTC (which is the exit bar for TV#1 trade)
# TV#2 enters at entry_price=101996.9 with exit_time=2025-01-07 11:30 UTC

# RSI_6 strategy params from the backtest
# RSI period=6, need to figure out when the short signal fires
# Let's load more data for RSI computation
conn2 = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
df_full = pd.read_sql_query(
    """
    SELECT timestamp, open, high, low, close FROM klines_30m
    WHERE symbol='BTCUSDT' AND timestamp >= '2025-01-01 00:00:00' AND timestamp <= '2025-01-07 02:00:00'
    ORDER BY timestamp
""",
    conn2,
)
conn2.close()


# Compute RSI-6
def compute_rsi(close, period=6):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


rsi = compute_rsi(df_full["close"], 6)
df_full["rsi"] = rsi

# Show last 10 bars
tail = df_full.tail(15)
print("\nLast 15 bars with RSI:")
print(tail[["timestamp", "open", "high", "low", "close", "rsi"]].to_string())

# Find which bar has close=101996.9 (TV#2 entry)
mask = abs(df_full["open"] - 101996.9) < 5
print("\nBars near TV#2 entry price 101996.9:")
print(df_full[mask][["timestamp", "open", "high", "low", "close", "rsi"]].to_string())
