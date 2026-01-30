# -*- coding: utf-8 -*-
"""Debug V2 at bar 6319 to see why it doesn't enter."""
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

# Check signals around bar 6319
print("=== Signal timeline before bar 6319 ===")
for i in range(6040, 6325):
    if long_signals[i] or short_signals[i]:
        sig = "LONG" if long_signals[i] else "SHORT"
        print(f"Bar {i}: {sig} signal, open price at entry bar {i+1}: {ohlc['open'].iloc[i+1]:.2f}")

# Check OHLC at critical bars  
print("\n=== OHLC at bars 6044, 6319-6320, 6502-6503 ===")
for bar in [6044, 6319, 6320, 6502, 6503]:
    print(f"Bar {bar}: O={ohlc['open'].iloc[bar]:.2f} H={ohlc['high'].iloc[bar]:.2f} L={ohlc['low'].iloc[bar]:.2f} C={ohlc['close'].iloc[bar]:.2f} @ {ohlc['timestamp'].iloc[bar]}")
