"""Debug equity tracking between VBT and FB."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Simulate exactly what FB does for first 2 trades
initial_cash = 10000.0
leverage = 10.0
position_size = 1.0
taker_fee = 0.0004
slippage = 0.0005

# Trade 1: SHORT entry at 91151.40, exit at 90786.80
entry1 = 91151.40 * (1 - slippage)  # Short entry - slippage down
print(f"Trade 1 Entry price (with slippage): {entry1:.4f}")

# Entry sizing like FB
allocated_capital = initial_cash * position_size
size1 = allocated_capital / (entry1 * (1 + taker_fee))
print(f"Trade 1 Size: {size1:.8f}")

# Entry: reduce cash
position_value1 = size1 * entry1
fees_entry1 = position_value1 * taker_fee
cash_after_entry1 = initial_cash - position_value1 - fees_entry1
print(f"Cash after entry 1: {cash_after_entry1:.4f}")

# Exit Trade 1
exit1 = 90786.80  # TP price
position_value_exit1 = size1 * exit1
fees_exit1 = position_value_exit1 * taker_fee

# For short: pnl = (entry - exit) * size * leverage - fees
pnl1 = (entry1 - exit1) * size1 * leverage - fees_exit1
print(f"Trade 1 PnL: {pnl1:.4f}")

# Cash after exit (for short: cash += position_value + pnl)
cash_after_exit1 = cash_after_entry1 + position_value_exit1 + pnl1
print(f"Cash after exit 1: {cash_after_exit1:.4f}")
print(f"Equity after Trade 1: {cash_after_exit1:.4f}")

# Trade 2: SHORT entry at 90753.00
entry2_raw = 90753.00
entry2 = entry2_raw * (1 - slippage)

allocated_capital2 = cash_after_exit1 * position_size
size2 = allocated_capital2 / (entry2 * (1 + taker_fee))
print(f"\nTrade 2 Expected size (FB style): {size2:.8f}")

# What VBT gives
vbt_size2 = 0.110498  # From test output
print(f"Trade 2 VBT size: {vbt_size2:.8f}")
print(f"Difference: {size2 - vbt_size2:.8f}")
