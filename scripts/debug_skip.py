"""Debug skip logic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from backend.backtesting.pyramiding import PyramidingManager

# Test the skip logic
pm = PyramidingManager(pyramiding=1)

# Simulate: immediate_close on bar 6502, then add_entry with entry_bar=6503
print("=== Simulating rollover scenario ===")
print(f"Initial: _last_long_close_bar = {pm._last_long_close_bar}")

# Simulate add_entry for long at bar 6045
pm.add_entry("long", 89506.40, 0.001, 100.0, 6045, pd.Timestamp.now())
print(f"After add_entry(6045): has_position = {pm.has_position('long')}")

# Simulate immediate_close at bar 6502
from datetime import datetime

pm.immediate_close("long", 90940.35, 6502, datetime.now(), "take_profit", 0.0007)
print(f"After immediate_close(6502): _last_long_close_bar = {pm._last_long_close_bar}")
print(f"  pending_long_trade = {pm.pending_long_trade is not None}")
print(f"  skip_pending_long_trade = {pm.skip_pending_long_trade}")

# Simulate add_entry at bar 6503 (signal was at 6502)
print("\nBefore add_entry(6503): signal_bar would be 6502")
pm.add_entry("long", 90810.90, 0.001, 100.0, 6503, pd.Timestamp.now())
print(f"After add_entry(6503): skip_pending_long_trade = {pm.skip_pending_long_trade}")
