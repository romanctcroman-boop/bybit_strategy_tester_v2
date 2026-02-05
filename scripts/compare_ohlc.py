"""Compare TV OHLC with downloaded OHLC."""
import pandas as pd

# Load TV OHLC (has timezone +03:00)
tv = pd.read_csv('d:/TV/BYBIT_BTCUSDT.P, 15 (3).csv')
print('=== TV OHLC ===')
print(f'Date range: {tv["time"].iloc[0]} to {tv["time"].iloc[-1]}')
print(f'Total bars: {len(tv)}')

# Load our downloaded OHLC
our = pd.read_csv('d:/TV/BYBIT_BTCUSDT.P_15m_full.csv')
our['timestamp'] = pd.to_datetime(our['timestamp'], utc=True)
print('\n=== Our OHLC ===')
print(f'Date range: {our["timestamp"].iloc[0]} to {our["timestamp"].iloc[-1]}')
print(f'Total bars: {len(our)}')

# Convert TV time to UTC for comparison
tv['time_utc'] = pd.to_datetime(tv['time']).dt.tz_convert('UTC').dt.tz_localize(None)

# Compare overlapping period
# Find common timestamps
our['timestamp_naive'] = our['timestamp'].dt.tz_localize(None)
merged = pd.merge(tv, our, left_on='time_utc', right_on='timestamp_naive', suffixes=('_tv', '_our'))

print('\n=== Overlap ===')
print(f'Common bars: {len(merged)}')

if len(merged) > 0:
    # Compare open prices
    merged['open_diff'] = abs(merged['open_tv'] - merged['open_our'])
    mismatches = merged[merged['open_diff'] > 0.01]

    print(f'Open price mismatches (>0.01): {len(mismatches)}')

    if len(mismatches) > 0:
        print('\nFirst 10 mismatches:')
        for i, row in mismatches.head(10).iterrows():
            print(f"  {row['time_utc']}: TV={row['open_tv']:.2f} vs Our={row['open_our']:.2f} (diff={row['open_diff']:.2f})")
    else:
        print('\nAll open prices match!')
