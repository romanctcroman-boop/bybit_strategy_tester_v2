"""Compute BTC RSI for the entire warmup period and show values Jan 1."""

import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd

DB_PATH = "d:\\bybit_strategy_tester_v2\\data.sqlite3"


def calculate_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder's RSI matching TradingView implementation."""
    n = len(prices)
    rsi = np.full(n, np.nan)
    if n < period + 1:
        return rsi
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    # SMA seed
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    # Start RSI at position `period`
    if avg_loss < 1e-10:
        rsi[period] = 100.0
    else:
        rsi[period] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    # Wilder smoothing
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss < 1e-10:
            rsi[i + 1] = 100.0
        else:
            rsi[i + 1] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return rsi


conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("""
    SELECT open_time, close_price
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '30' AND market_type = 'linear'
    ORDER BY open_time ASC
""")
rows = c.fetchall()
conn.close()

df = pd.DataFrame(rows, columns=["ts_ms", "close"])
df["dt"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True)
print(f"Total BTC 30m bars: {len(df)}")
print(f"First: {df.dt.iloc[0]}")
print(f"Last: {df.dt.iloc[-1]}")

# Calculate RSI on all bars
rsi = calculate_rsi(df["close"].values, period=14)
df["rsi"] = rsi

# Jan 1 bars
jan1_start = pd.Timestamp("2025-01-01 00:00:00", tz="UTC")
jan1_end = pd.Timestamp("2025-01-01 16:00:00", tz="UTC")
mask = (df.dt >= jan1_start) & (df.dt <= jan1_end)
jan1_df = df[mask]

print("\nBTC RSI on Jan 1, 2025 (all bars):")
print(f"{'Time':12s} {'Close':12s} {'RSI':8s}")
prev_rsi = None
for _, row in jan1_df.iterrows():
    r = row["rsi"]
    flag = ""
    if prev_rsi is not None and prev_rsi >= 52 and r < 52:
        flag = " <-- CROSS BELOW 52"
    print(f"  {row['dt'].strftime('%H:%M'):12s} {row['close']:12.2f} {r:8.4f}{flag}")
    prev_rsi = r

# Also show last 5 bars before Jan 1
dec31_mask = (df["dt"] >= pd.Timestamp("2024-12-31 20:00:00", tz="UTC")) & (df["dt"] < jan1_start)
print("\nLast bars of Dec 31:")
for _, row in df[dec31_mask].iterrows():
    print(f"  {row['dt'].strftime('%Y-%m-%d %H:%M'):20s} {row['close']:12.2f} {row['rsi']:8.4f}")
