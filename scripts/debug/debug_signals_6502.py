"""Debug signals around bar 6502 (Trade 45 exit bar)"""

import sys
from datetime import datetime
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.kline_service import KlineService
from backend.strategies import RSIStrategy

# Load data
db_path = Path(__file__).resolve().parents[2] / "data.sqlite3"
service = KlineService(str(db_path))
candles = service.get_candles("BTCUSDT", "15m", datetime(2025, 1, 1), datetime(2025, 1, 11))

data = np.array([[c.timestamp, c.open, c.high, c.low, c.close, c.volume] for c in candles])

# Generate signals
strategy = RSIStrategy(period=21, overbought=70, oversold=25)
signals = strategy.generate_signals(data)

print("=== Signals around Trade 45 exit bar ===")
print("Trade 45 is LONG, entered at bar 6320, exited by TP at bar 6502")
print(f"Total bars: {len(data)}")
print()

# Trade 45 entry
entry_bar = 6320
entry_price = data[entry_bar + 1, 1]  # Open of next bar
tp_price = entry_price * 1.015  # 1.5% TP
print(f"Trade 45 entry signal at bar {entry_bar}")
print(f"  Entry price (next bar open): {entry_price:.2f}")
print(f"  TP price: {tp_price:.2f}")
print()

# Check bar 6502 - where TP hits
exit_bar = 6502
print(f"Bar {exit_bar} (TP hit bar):")
print(
    f"  Open={data[exit_bar, 1]:.2f}, High={data[exit_bar, 2]:.2f}, Low={data[exit_bar, 3]:.2f}, Close={data[exit_bar, 4]:.2f}"
)
print(f"  TP price {tp_price:.2f} <= High {data[exit_bar, 2]:.2f}? {tp_price <= data[exit_bar, 2]}")
print()

print("=== All ENTRY signals from bar 6498 to 6525 ===")
for i in range(6498, min(6530, len(data) - 1)):
    le = signals["long_entry"][i]
    se = signals["short_entry"][i]

    if le or se:
        ts = datetime.fromtimestamp(data[i, 0] / 1000)
        direction = "LONG" if le else "SHORT"
        entry_price_next = data[i + 1, 1] if i + 1 < len(data) else 0
        print(f"Bar {i}: {ts} - {direction} signal, entry price would be {entry_price_next:.2f}")
        print(f"  Current bar: O={data[i, 1]:.2f} H={data[i, 2]:.2f} L={data[i, 3]:.2f} C={data[i, 4]:.2f}")

print()
print("=== Signal at bar 6502 specifically ===")
i = 6502
print(f"long_entry[{i}] = {signals['long_entry'][i]}")
print(f"short_entry[{i}] = {signals['short_entry'][i]}")
print(f"long_exit[{i}] = {signals['long_exit'][i]}")
print(f"short_exit[{i}] = {signals['short_exit'][i]}")
