# -*- coding: utf-8 -*-
"""
Detailed DCA Grid Strategy Test
Shows how RSI entries, TP, and SL work step by step
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from backend.backtesting.strategies import get_strategy

print("=" * 70)
print("DCA GRID STRATEGY - DETAILED TEST")
print("=" * 70)

# Create test data with clear price movements
np.random.seed(42)
n = 200
dates = pd.date_range(start='2025-01-01', periods=n, freq='1h')

# Create price with trending + mean-reversion pattern
base_price = 100000
trend = np.cumsum(np.random.randn(n) * 100)  # Random walk

# Add some strong dips for RSI oversold signals
trend[30:35] -= 3000   # First dip
trend[60:65] -= 2500   # Second dip  
trend[90:95] -= 2000   # Third dip
trend[130:140] += 5000 # Recovery spike (TP trigger)

prices = base_price + trend
prices = np.maximum(prices, 90000)  # Floor at 90k

candles = pd.DataFrame({
    'open': prices,
    'high': prices + np.random.uniform(50, 200, n),
    'low': prices - np.random.uniform(50, 200, n),
    'close': prices + np.random.uniform(-100, 100, n),
}, index=dates)

print(f"\nData: {n} bars")
print(f"Price range: ${candles['low'].min():.0f} - ${candles['high'].max():.0f}")

# ============================================
# Test 1: DCA LONG with sl_mode='last_order'
# ============================================
print("\n" + "=" * 70)
print("TEST 1: DCA LONG, sl_mode='last_order'")
print("=" * 70)

dca = get_strategy('dca', {
    'entry_interval': 10,
    'max_entries': 6,
    'take_profit': 3.0,
    'stop_loss': 5.0,
    'sl_mode': 'last_order',
    '_direction': 'long',
    'rsi_period': 14,
    'rsi_oversold': 35,
})

signals = dca.generate_signals(candles)

# Show RSI values and signals
rsi = dca._calculate_rsi(candles['close'])

print(f"\nParameters:")
print(f"  Entry interval: {dca.entry_interval} bars")
print(f"  Max entries: {dca.max_entries}")
print(f"  Take Profit: {dca.take_profit*100}% from average")
print(f"  Stop Loss: {dca.stop_loss*100}% from LAST ORDER price")
print(f"  RSI oversold: {dca.rsi_oversold}")

# Find entry signals
entry_bars = np.where(signals.entries)[0]
exit_bars = np.where(signals.exits)[0]

print(f"\n--- Signal Analysis ---")
print(f"Total Entry signals: {len(entry_bars)}")
print(f"Total Exit signals: {len(exit_bars)}")

if len(entry_bars) > 0:
    print("\n--- Entry Signals (RSI < 35) ---")
    for i, bar in enumerate(entry_bars[:10], 1):
        price = candles['close'].iloc[bar]
        rsi_val = rsi.iloc[bar]
        print(f"  Order #{i}: Bar {bar}, Price ${price:.2f}, RSI={rsi_val:.1f}")

if len(exit_bars) > 0:
    print("\n--- Exit Signals ---")
    for bar in exit_bars[:5]:
        price = candles['close'].iloc[bar]
        print(f"  Exit at Bar {bar}, Price ${price:.2f}")

# ============================================
# Test 2: DCA LONG with sl_mode='average'
# ============================================
print("\n" + "=" * 70)
print("TEST 2: DCA LONG, sl_mode='average'")
print("=" * 70)

dca_avg = get_strategy('dca', {
    'entry_interval': 10,
    'max_entries': 6,
    'take_profit': 3.0,
    'stop_loss': 5.0,
    'sl_mode': 'average',
    '_direction': 'long',
})

signals_avg = dca_avg.generate_signals(candles)

entry_bars_avg = np.where(signals_avg.entries)[0]
exit_bars_avg = np.where(signals_avg.exits)[0]

print(f"\nParameters:")
print(f"  Stop Loss: {dca_avg.stop_loss*100}% from AVERAGE price")

print(f"\n--- Signal Analysis ---")
print(f"Total Entry signals: {len(entry_bars_avg)}")
print(f"Total Exit signals: {len(exit_bars_avg)}")

# ============================================
# Detailed simulation showing TP/SL calculation
# ============================================
print("\n" + "=" * 70)
print("SIMULATION: How TP and SL are calculated")
print("=" * 70)

# Manual simulation to show calculations
print("\nScenario: 3 DCA orders filled")
entry_prices = [100000, 97000, 95000]  # Price dropped, we accumulated

avg_price = sum(entry_prices) / len(entry_prices)
last_order_price = entry_prices[-1]

print(f"\n  Order 1: Entry at ${entry_prices[0]:,.0f}")
print(f"  Order 2: Entry at ${entry_prices[1]:,.0f}")
print(f"  Order 3: Entry at ${entry_prices[2]:,.0f}")
print(f"\n  Average Price: ${avg_price:,.2f}")
print(f"  Last Order Price: ${last_order_price:,.0f}")

# Calculate TP/SL for both modes
tp_pct = 3.0 / 100
sl_pct = 5.0 / 100

tp_price = avg_price * (1 + tp_pct)
sl_from_avg = avg_price * (1 - sl_pct)
sl_from_last = last_order_price * (1 - sl_pct)

print(f"\n  TP (3% from average): ${tp_price:,.2f}")
print(f"  SL (5% from average): ${sl_from_avg:,.2f}")
print(f"  SL (5% from last order): ${sl_from_last:,.2f}")

print(f"\n  Difference in SL:")
print(f"    sl_mode='average':    SL at ${sl_from_avg:,.2f}")
print(f"    sl_mode='last_order': SL at ${sl_from_last:,.2f}")
print(f"    Last order mode is ${sl_from_avg - sl_from_last:,.2f} LOWER (more conservative)")

print("\n" + "=" * 70)
print("✅ DCA GRID TEST COMPLETED!")
print("=" * 70)
