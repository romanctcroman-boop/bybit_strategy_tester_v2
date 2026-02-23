"""
🔬 Test: What if TradingView uses oversold=25?
"""
import sqlite3
from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parent.parent
DB_PATH = project_root / "data.sqlite3"


def calculate_rsi_wilder(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    for i in range(period, len(close)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# Load data
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("""
    SELECT open_time, close_price FROM bybit_kline_audit
    WHERE symbol='BTCUSDT' AND interval='15' AND market_type='spot'
    ORDER BY open_time ASC
""", conn)
conn.close()

df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
df['rsi'] = calculate_rsi_wilder(df['close_price'], 14)

# Check around the missing LONG signal at 10:15
print("="*60)
print("🔬 RSI VALUES AROUND 2025-10-05 10:15")
print("="*60)

mask = (df['datetime'] >= '2025-10-05 09:00') & (df['datetime'] <= '2025-10-05 12:00')
region = df[mask]

for _i, row in region.iterrows():
    rsi = row['rsi']

    # Check thresholds
    below_30 = "◀─ Below 30" if rsi < 30 else ""
    below_25 = "◀─ Below 25!" if rsi < 25 else ""

    print(f"{row['datetime']} | RSI: {rsi:.4f} {below_30} {below_25}")

print("\n" + "="*60)
print("📊 COUNT SIGNALS WITH DIFFERENT THRESHOLDS")
print("="*60)

for threshold in [30, 28, 25]:
    signals = 0
    prev_rsi = None
    for _, row in df.iterrows():
        curr_rsi = row['rsi']
        if prev_rsi is not None and not pd.isna(prev_rsi) and not pd.isna(curr_rsi):
            if prev_rsi <= threshold and curr_rsi > threshold:
                signals += 1
        prev_rsi = curr_rsi
    print(f"  Oversold={threshold}: {signals} LONG signals")

# Check the specific signal at 10:15
print("\n" + "="*60)
print("🎯 THE KEY BAR: 2025-10-05 10:15")
print("="*60)

key_bar = df[df['datetime'] == '2025-10-05 10:15:00']
if not key_bar.empty:
    row = key_bar.iloc[0]
    idx = key_bar.index[0]
    prev_row = df.iloc[idx - 1]

    print(f"Previous bar (10:00): RSI = {prev_row['rsi']:.4f}")
    print(f"Current bar (10:15):  RSI = {row['rsi']:.4f}")
    print()
    print("Crossover check:")
    print(f"  prev_rsi <= 30: {prev_row['rsi']:.4f} <= 30 = {prev_row['rsi'] <= 30}")
    print(f"  curr_rsi >  30: {row['rsi']:.4f} > 30 = {row['rsi'] > 30}")
    print()
    print(f"  prev_rsi <= 25: {prev_row['rsi']:.4f} <= 25 = {prev_row['rsi'] <= 25}")
    print(f"  curr_rsi >  25: {row['rsi']:.4f} > 25 = {row['rsi'] > 25}")
    print()
    print("Result:")
    print(f"  With oversold=30: {'LONG SIGNAL!' if prev_row['rsi'] <= 30 and row['rsi'] > 30 else 'No signal'}")
    print(f"  With oversold=25: {'LONG SIGNAL!' if prev_row['rsi'] <= 25 and row['rsi'] > 25 else 'No signal'}")
