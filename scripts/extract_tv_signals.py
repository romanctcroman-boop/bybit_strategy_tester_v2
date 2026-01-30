# -*- coding: utf-8 -*-
"""Extract TV entry signals from trade CSV and map to OHLC bars."""
import pandas as pd
import numpy as np

# Load OHLC - use full data file
ohlc = pd.read_csv('d:/TV/BYBIT_BTCUSDT.P_15m_full.csv')
ohlc['timestamp'] = pd.to_datetime(ohlc['timestamp'], utc=True)
# Remove timezone for comparison
ohlc['timestamp'] = ohlc['timestamp'].dt.tz_localize(None)
print(f'OHLC bars: {len(ohlc)}')
print(f'First bar: {ohlc.iloc[0]["timestamp"]}')
print(f'Last bar: {ohlc.iloc[-1]["timestamp"]}')

# Load trades
trades = pd.read_csv('d:/TV/RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-01-24.csv')
entries = trades[trades['Тип'].str.contains('Вход')]
print(f'\nTotal entries: {len(entries)}')

# Get long/short entry times  
long_entries = entries[entries['Тип'].str.contains('длинную')]
short_entries = entries[entries['Тип'].str.contains('короткую')]
print(f'Long entries: {len(long_entries)}')
print(f'Short entries: {len(short_entries)}')

# Convert to entry datetime arrays
long_times = pd.to_datetime(long_entries['Дата и время']).values
short_times = pd.to_datetime(short_entries['Дата и время']).values

# Print first few entry times for debugging
print(f'\nFirst long entry: {long_times[0] if len(long_times) > 0 else "N/A"}')
print(f'First short entry: {short_times[0] if len(short_times) > 0 else "N/A"}')

# Create signal arrays matching OHLC
# Signal should be on the bar BEFORE entry (TV enters on next bar open)
n = len(ohlc)
long_signals = np.zeros(n, dtype=bool)
short_signals = np.zeros(n, dtype=bool)

matched_long = 0
matched_short = 0

for entry_time in long_times:
    # Find the bar where this entry happened
    entry_ts = pd.Timestamp(entry_time).tz_localize(None)
    mask = ohlc['timestamp'] == entry_ts
    if mask.any():
        idx = ohlc[mask].index[0]
        # Signal was on the PREVIOUS bar
        if idx > 0:
            long_signals[idx - 1] = True
            matched_long += 1

for entry_time in short_times:
    entry_ts = pd.Timestamp(entry_time).tz_localize(None)
    mask = ohlc['timestamp'] == entry_ts
    if mask.any():
        idx = ohlc[mask].index[0]
        if idx > 0:
            short_signals[idx - 1] = True
            matched_short += 1

print(f'\nLong signals matched: {matched_long}/{len(long_times)}')
print(f'Short signals matched: {matched_short}/{len(short_times)}')
print(f'Total signals: {long_signals.sum() + short_signals.sum()}')

# Save for testing
np.save('d:/TV/long_signals.npy', long_signals)
np.save('d:/TV/short_signals.npy', short_signals)
print('\nSignals saved to d:/TV/')

