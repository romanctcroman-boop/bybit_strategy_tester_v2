"""
Find exact Trade #24 from TradingView in our data
TradingView Trade #24: 2025-10-30 17:15:00 LONG at $108,080.40
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import sqlite3
import pandas as pd
import numpy as np

DB_PATH = project_root / "data.sqlite3"


def calculate_rsi_wilder(prices: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI matching TradingView"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    for i in range(period, len(prices)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


# Load data
conn = sqlite3.connect(DB_PATH)
query = """
SELECT open_time, open_price, high_price, low_price, close_price, volume
FROM bybit_kline_audit 
WHERE symbol = 'BTCUSDT' AND interval = '15' AND market_type = 'spot'
ORDER BY open_time ASC
"""
df = pd.read_sql_query(query, conn)
conn.close()

df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
df = df.sort_values('datetime').reset_index(drop=True)

# Calculate RSI
df['rsi'] = calculate_rsi_wilder(df['close_price'], period=14)
df['prev_rsi'] = df['rsi'].shift(1)

# Find crossover signals (LONG)
OVERSOLD = 30
df['long_signal'] = (df['prev_rsi'] <= OVERSOLD) & (df['rsi'] > OVERSOLD)

print("="*70)
print("🔍 FINDING TRADE #24 (2025-10-30 17:15)")
print("="*70)

# Find the exact bar
target_time = pd.Timestamp("2025-10-30 17:15:00")
target_price = 108080.40

# Search for bars around that time
mask = (df['datetime'] >= '2025-10-30 15:00') & (df['datetime'] <= '2025-10-30 20:00')
region = df[mask].copy()

print(f"\n📊 Bars around 2025-10-30 17:15:")
print("-"*70)
for _, row in region.iterrows():
    signal = "🟢 LONG" if row['long_signal'] else ""
    price_match = "💰 PRICE MATCH!" if abs(row['close_price'] - target_price) < 1 else ""
    print(f"  {row['datetime']} | Close: ${row['close_price']:.2f} | RSI: {row['prev_rsi']:.2f} → {row['rsi']:.2f} {signal} {price_match}")

# Find all LONG signals and number them
long_signals = df[df['long_signal']].reset_index()

print(f"\n📈 Finding signal around 2025-10-30:")
print("-"*70)

# Find signals around Oct 30
oct30_signals = long_signals[long_signals['datetime'].dt.date == pd.Timestamp('2025-10-30').date()]
print(f"LONG signals on Oct 30: {len(oct30_signals)}")
for _, sig in oct30_signals.iterrows():
    # Find which signal number this is
    sig_idx = long_signals[long_signals['index'] == sig['index']].index[0]
    print(f"  Signal #{sig_idx + 1}: {sig['datetime']} | Price: ${df.loc[sig['index'], 'close_price']:.2f} | RSI: {sig['prev_rsi']:.2f} → {sig['rsi']:.2f}")

# Check for the specific time
print("\n" + "="*70)
print("🎯 EXACT TIME ANALYSIS: 17:15")
print("="*70)

# TV uses Moscow time (UTC+3), so 17:15 MSK = 14:15 UTC
# But let's check both
for offset_name, hours in [("UTC", 0), ("UTC+3 (MSK)", -3)]:
    target = pd.Timestamp("2025-10-30 17:15:00") - pd.Timedelta(hours=hours)
    match = df[df['datetime'] == target]
    if not match.empty:
        row = match.iloc[0]
        print(f"\n{offset_name}: {target}")
        print(f"  Found: Yes")
        print(f"  Close: ${row['close_price']:.2f}")
        print(f"  RSI: {row['prev_rsi']:.4f} → {row['rsi']:.4f}")
        print(f"  LONG signal: {'YES 🟢' if row['long_signal'] else 'NO ❌'}")
    else:
        print(f"\n{offset_name}: {target} - NOT FOUND in data")

# Show summary
print("\n" + "="*70)
print("📋 SUMMARY: Trade #24 Analysis")  
print("="*70)
print("""
TradingView Trade #24:
  Entry: 2025-10-30 17:15 (likely UTC+3/MSK)
  Price: $108,080.40
  Type:  LONG
  
Our System:
  Check if we have a LONG signal at that exact time/price
  
Possible issues:
  1. Timezone difference (UTC vs MSK)
  2. RSI rounding at boundary
  3. Data gap in our database
""")
