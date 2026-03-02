"""Debug: check equity_curve length vs candles.index length for V2/V3 engines."""

import warnings

warnings.filterwarnings("ignore")
import sys

sys.path.insert(0, ".")

import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from backend.config.database_policy import DATA_START_DATE

conn = sqlite3.connect("data.sqlite3")
df = pd.read_sql("SELECT * FROM klines WHERE symbol='ETHUSDT' AND interval='30' ORDER BY open_time", conn)
conn.close()
df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
df.set_index("open_time", inplace=True)
warmup_start = datetime(2024, 12, 1, tzinfo=timezone.utc)
df = df[df.index >= warmup_start]
warmup_bars = len(df[df.index < DATA_START_DATE])
data_slice = df[warmup_bars:]
n = len(data_slice)

print(f"n: {n}")
print(f"candles.index length: {len(data_slice.index)}")

# Simulate what V2/V3 equity_curve looks like: [capital] + one append per loop step
# Loop is range(1, n) which has n-1 iterations
eq = [10000.0]
for i in range(1, n):
    eq.append(10000.0)
print(f"equity_curve length (V2/V3 style): {len(eq)}")
print(f"Match: {len(eq) == len(data_slice.index)}")
print()

# Now with full warmup included (V2/V3 pass candles WITH warmup)
full_n = len(df)
eq_full = [10000.0]
for i in range(1, full_n):
    eq_full.append(10000.0)
print(f"Full df n: {full_n}")
print(f"equity_curve (full): {len(eq_full)}")
