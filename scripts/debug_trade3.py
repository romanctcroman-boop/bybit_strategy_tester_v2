"""Debug Trade 3 specifically."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import sqlite3
import pandas as pd
import numpy as np

# Load data  
db_path = ROOT / "data.sqlite3"
conn = sqlite3.connect(str(db_path))
df = pd.read_sql(
    """SELECT open_time, open_price as open, high_price as high,
       low_price as low, close_price as close, volume
    FROM bybit_kline_audit WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time DESC LIMIT 200""", conn)
conn.close()
df = df.sort_values("open_time").reset_index(drop=True)
df["datetime"] = pd.to_datetime(df["open_time"], unit="ms")

# Trade 3 details from logs
entry_price = 94591.67
tp_pct = 0.04
leverage = 10.0
tp_price = entry_price * (1 + tp_pct / leverage)

print(f"Trade 3 Analysis:")
print(f"  Entry price: {entry_price}")
print(f"  TP price (calculated): {tp_price:.2f}")
print(f"  FB exit: 95037.00")

# Find entry bar (where close ≈ entry price)
entry_idx = None
for i, row in df.iterrows():
    if abs(row['close'] - 94591.67 / 1.0005) < 10:  # entry with slippage
        entry_idx = i
        print(f"\nFound potential entry bar at index {i}: {row['datetime']}")
        print(f"  O={row['open']:.2f} H={row['high']:.2f} L={row['low']:.2f} C={row['close']:.2f}")

# Check bars after entry for TP trigger
if entry_idx:
    print(f"\nBars after entry (looking for TP trigger where high >= {tp_price:.2f}):")
    for i in range(entry_idx + 1, min(entry_idx + 20, len(df))):
        row = df.iloc[i]
        tp_hit = row['high'] >= tp_price
        marker = " <-- TP HIT!" if tp_hit else ""
        print(f"  Bar {i}: H={row['high']:.2f} L={row['low']:.2f} C={row['close']:.2f}{marker}")
        if tp_hit:
            print(f"\n  Clamped exit: max({row['low']:.2f}, min({row['high']:.2f}, {tp_price:.2f})) = {max(row['low'], min(row['high'], tp_price)):.2f}")
            print(f"  Close price: {row['close']:.2f}")
            break
