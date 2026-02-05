"""Find RSI values near 25.0 boundary"""
import sqlite3
from pathlib import Path

import pandas as pd

DB = Path("data.sqlite3")
conn = sqlite3.connect(DB)
df = pd.read_sql_query("""SELECT open_time, close_price FROM bybit_kline_audit 
    WHERE symbol='BTCUSDT' AND interval='15' AND market_type='spot' ORDER BY open_time""", conn)
conn.close()

df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')

# RSI calculation
close = df['close_price']
delta = close.diff()
gain = delta.where(delta > 0, 0.0)
loss = (-delta).where(delta < 0, 0.0)
avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()

for i in range(14, len(close)):
    avg_gain.iloc[i] = (avg_gain.iloc[i-1] * 13 + gain.iloc[i]) / 14
    avg_loss.iloc[i] = (avg_loss.iloc[i-1] * 13 + loss.iloc[i]) / 14

rs = avg_gain / avg_loss
df['rsi'] = 100 - (100 / (1 + rs))
df['prev_rsi'] = df['rsi'].shift(1)

print("="*70)
print("🔬 RSI VALUES NEAR 25.0 (Potential boundary cases)")
print("="*70)

# Find where RSI is very close to 25
boundary = df[(df['rsi'] >= 24.9) & (df['rsi'] <= 25.1)]
print(f"\nTotal bars with RSI between 24.9 and 25.1: {len(boundary)}")

print("\nThese cases:")
for _, row in boundary.iterrows():
    delta_25 = abs(row['rsi'] - 25)

    # Check if it's a crossover
    is_crossover = ""
    if not pd.isna(row['prev_rsi']):
        if row['prev_rsi'] <= 25 and row['rsi'] > 25:
            is_crossover = " ↗️ CROSSOVER UP"
        elif row['prev_rsi'] > 25 and row['rsi'] <= 25:
            is_crossover = " ↘️ CROSSOVER DOWN"

    print(f"  {row['datetime']} | RSI: {row['rsi']:.6f} | Δ from 25: {delta_25:.6f}{is_crossover}")

print("\n" + "="*70)
print("🎯 MOST CRITICAL: Crossovers where RSI is within 0.01 of 25")
print("="*70)

# Find crossovers near 25
critical = []
for i in range(1, len(df)):
    curr = df.iloc[i]['rsi']
    prev = df.iloc[i-1]['rsi']

    if pd.isna(curr) or pd.isna(prev):
        continue

    # Crossover and very close to 25
    if prev <= 25 and curr > 25:
        if abs(curr - 25) < 0.1 or abs(prev - 25) < 0.1:
            critical.append({
                'datetime': df.iloc[i]['datetime'],
                'prev_rsi': prev,
                'curr_rsi': curr,
                'delta_curr': curr - 25,
                'delta_prev': prev - 25
            })

print(f"\nCrossover cases near threshold: {len(critical)}")
for c in critical:
    print(f"  {c['datetime']} | {c['prev_rsi']:.6f} → {c['curr_rsi']:.6f} | curr-25={c['delta_curr']:.6f}")
