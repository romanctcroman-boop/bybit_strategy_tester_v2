# -*- coding: utf-8 -*-
"""Debug Trade 46 entry_price discrepancy."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import numpy as np

# Monkey-patch PyramidingManager to trace close_position
from backend.backtesting.pyramiding import PyramidingManager, PyramidPosition

original_close_all = PyramidPosition.close_all

def traced_close_all(self):
    if self.entries:
        print(f"  [TRACE] close_all() direction={self.direction}")
        print(f"    entry_count={len(self.entries)}")
        for i, e in enumerate(self.entries):
            print(f"    entry[{i}]: price={e.entry_price:.2f}, size={e.size:.6f}, bar_idx={e.entry_bar_idx}")
        print(f"    avg_entry_price={self.avg_entry_price:.2f}")
    return original_close_all(self)

PyramidPosition.close_all = traced_close_all

# Load data
ohlc = pd.read_csv('d:/TV/BYBIT_BTCUSDT.P_15m_full.csv')
ohlc['timestamp'] = pd.to_datetime(ohlc['timestamp'], utc=True).dt.tz_localize(None)
long_signals = np.load('d:/TV/long_signals.npy')
short_signals = np.load('d:/TV/short_signals.npy')

from backend.backtesting.interfaces import BacktestInput, TradeDirection
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

print("Running V3 with tracing...")
print("Looking for trade with entry around 89596 or 90810...")
print()

v3 = FallbackEngineV3()
r3 = v3.run(input_data)

print(f"\nV3: {len(r3.trades)} trades")

# Find Trade 46
for i, t in enumerate(r3.trades):
    if 89500 < t.entry_price < 91000 and t.direction == "long":
        print(f"\nTrade {i+1}: {t.direction}")
        print(f"  entry_price: {t.entry_price:.2f}")
        print(f"  exit_price: {t.exit_price:.2f}")
        print(f"  pnl: {t.pnl:.2f}")
