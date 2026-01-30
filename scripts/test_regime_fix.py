"""Full module test for regime detection"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

print("Starting full module test...")

import os
# Disable numba parallel to avoid hanging
os.environ['NUMBA_NUM_THREADS'] = '1'

import numpy as np
import pandas as pd
import sqlite3

print("Loading data...")

conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
df = pd.read_sql("""
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume 
    FROM bybit_kline_audit 
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    AND open_time >= 1735689600000 AND open_time < 1737504000000
    ORDER BY open_time ASC
""", conn)
conn.close()
df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
df.set_index('open_time', inplace=True)

print(f'Data: {len(df)} bars')

print("Testing KMeansRegimeDetector module...")

from backend.ml.regime_detection import KMeansRegimeDetector

detector = KMeansRegimeDetector(n_regimes=3)
result = detector.fit_predict(df)

print(f'Regimes detected: {result.n_regimes}')
print(f'Current regime: {result.current_regime_name}')
print('Regime distribution:')
for i, name in enumerate(result.regime_names):
    freq = np.mean(result.regimes == i) * 100
    stats = result.regime_stats.get(i, {})
    mean_ret = stats.get("mean_return", 0) * 100
    print(f'  {name}: {freq:.1f}%, mean_ret={mean_ret:.4f}%')

print('✅ Full regime detection module test passed!')
