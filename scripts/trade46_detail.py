# -*- coding: utf-8 -*-
"""Find Trade 46 entry bar discrepancy."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import numpy as np

# Load data
ohlc = pd.read_csv('d:/TV/BYBIT_BTCUSDT.P_15m_full.csv')
ohlc['timestamp'] = pd.to_datetime(ohlc['timestamp'], utc=True).dt.tz_localize(None)
long_signals = np.load('d:/TV/long_signals.npy')
short_signals = np.load('d:/TV/short_signals.npy')

from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3

candles = ohlc.reset_index(drop=True)
input_data = BacktestInput(
    candles=candles, candles_1m=None, initial_capital=1_000_000.0,
    use_fixed_amount=True, fixed_amount=100.0, leverage=10,
    take_profit=0.015, stop_loss=0.03, taker_fee=0.0007,
    direction=TradeDirection.BOTH,
    long_entries=long_signals, short_entries=short_signals,
    use_bar_magnifier=False,
)

v2 = FallbackEngineV2()
r2 = v2.run(input_data)
v3 = FallbackEngineV3()
r3 = v3.run(input_data)

t2 = r2.trades[45]  # Trade 46 (0-indexed)
t3 = r3.trades[45]

print("Trade 46 comparison:")
print(f"\n=== V2 ===")
print(f"  entry_time: {t2.entry_time}")
print(f"  exit_time: {t2.exit_time}")  
print(f"  entry_price: {t2.entry_price:.2f}")
print(f"  exit_price: {t2.exit_price:.2f}")
print(f"  exit_reason: {t2.exit_reason}")
print(f"  duration_bars: {t2.duration_bars}")

print(f"\n=== V3 ===")
print(f"  entry_time: {t3.entry_time}")
print(f"  exit_time: {t3.exit_time}")
print(f"  entry_price: {t3.entry_price:.2f}")
print(f"  exit_price: {t3.exit_price:.2f}")
print(f"  exit_reason: {t3.exit_reason}")
print(f"  duration_bars: {t3.duration_bars}")

# Find bar indices for these prices
print("\n=== OHLC Analysis ===")
# V2 entry at 90810.90
v2_entry_bars = ohlc[abs(ohlc['open'] - 90810.90) < 1].index.tolist()
print(f"Bars with open near 90810.90: {v2_entry_bars}")

# V3 entry at 89596.40
v3_entry_bars = ohlc[abs(ohlc['open'] - 89596.40) < 1].index.tolist()
print(f"Bars with open near 89596.40: {v3_entry_bars}")

# Trades 44-47 for context
print("\n=== Trades 44-47 context ===")
for i in range(43, 47):
    t2_ = r2.trades[i]
    t3_ = r3.trades[i]
    print(f"Trade {i+1}: V2 entry={t2_.entry_price:.2f} ({t2_.direction}), V3 entry={t3_.entry_price:.2f} ({t3_.direction})")
