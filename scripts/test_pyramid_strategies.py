"""Test pyramiding strategies"""
import sys

sys.path.insert(0, r'd:\bybit_strategy_tester_v2')

import numpy as np
import pandas as pd

from backend.backtesting.strategies import get_strategy, list_available_strategies

print('Available Strategies:')
print('=' * 60)
for s in list_available_strategies():
    pyr = ' [PYRAMIDING]' if s.get('supports_pyramiding') else ''
    print(f"  {s['name']:15} - {s['description']}{pyr}")

print()
print('Testing Grid Strategy...')
# Create test data
n = 100
dates = pd.date_range(start='2025-01-01', periods=n, freq='1h')
# Price drops then recovers
prices = 50000 - np.arange(n) * 50 + np.sin(np.arange(n) * 0.2) * 200

candles = pd.DataFrame({
    'open': prices,
    'high': prices + 50,
    'low': prices - 50,
    'close': prices + 10,
}, index=dates)

grid = get_strategy('grid', {'grid_levels': 5, 'grid_spacing': 1.0})
signals = grid.generate_signals(candles)
print(f'  Grid entries: {signals.entries.sum()}')
print(f'  Grid exits: {signals.exits.sum()}')

print()
print('Testing DCA Strategy...')
dca = get_strategy('dca', {'entry_interval': 10, 'max_entries': 5})
signals = dca.generate_signals(candles)
print(f'  DCA entries: {signals.entries.sum()}')
print(f'  DCA exits: {signals.exits.sum()}')

print()
print('Testing Martingale Strategy...')
mart = get_strategy('martingale', {'max_entries': 4})
signals = mart.generate_signals(candles)
print(f'  Martingale entries: {signals.entries.sum()}')
print(f'  Martingale exits: {signals.exits.sum()}')

print()
print('All pyramiding strategies work!')
