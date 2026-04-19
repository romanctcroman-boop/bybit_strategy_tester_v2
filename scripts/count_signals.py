"""Count all BTC RSI crossings below 52 in the strategy period."""

import sqlite3

import numpy as np
import pandas as pd

DB_PATH = "d:\\bybit_strategy_tester_v2\\data.sqlite3"


def calculate_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder's RSI matching TradingView."""
    n = len(prices)
    rsi = np.full(n, np.nan)
    if n < period + 1:
        return rsi
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    if avg_loss < 1e-10:
        rsi[period] = 100.0
    else:
        rsi[period] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
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

rsi = calculate_rsi(df["close"].values, period=14)
df["rsi"] = rsi
df["rsi_prev"] = df["rsi"].shift(1)

# Find all crossings below 52 where RSI was in [50-70] (strategy conditions)
cross_short = (df["rsi_prev"] >= 52) & (df["rsi"] < 52) & (df["rsi"] >= 50) & (df["rsi"] <= 70)
# Actually: condition is rsi crosses below level=52, with range [50-70]
# Looking at the indicator handler: cross_short = (rsi_prev >= level) & (rsi < level)
# Then short_range_condition: rsi in [50, 70]
# Combined: cross_short AND short_range_condition
cross_short_with_range = cross_short & (df["rsi"] >= 50) & (df["rsi"] <= 70)

strategy_start = pd.Timestamp("2025-01-01", tz="UTC")
strategy_end = pd.Timestamp("2026-02-25", tz="UTC")

# Only in strategy period
mask = (df["dt"] >= strategy_start) & (df["dt"] <= strategy_end)
signals_in_period = df[mask & cross_short_with_range]

print(f"Total BTC RSI crosses below 52 (with range [50-70]) in strategy period: {len(signals_in_period)}")
print("\nAll signal bars:")
print(f"{'#':3s} {'Date/Time':22s} {'RSI_prev':10s} {'RSI':10s}")
for i, (_, row) in enumerate(signals_in_period.iterrows(), 1):
    print(f"{i:3d} {row['dt'].strftime('%Y-%m-%d %H:%M'):22s} {row['rsi_prev']:10.4f} {row['rsi']:10.4f}")
