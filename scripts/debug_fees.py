"""
Deep debug: position size and fee calculation differences
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ============ PARAMETERS ============
initial_capital = 10000.0
entry_price = 94970.52  # First trade entry
taker_fee = 0.0004
slippage = 0.0001
position_size_frac = 1.0

# ============ FALLBACK LOGIC ============
print("=" * 60)
print("FALLBACK LOGIC (from engine.py lines 1335-1343)")
print("=" * 60)

# From Fallback engine:
# allocated_capital = cash * config.position_size
# entry_size = allocated_capital / (entry_price * (1 + config.taker_fee))
# position_value = entry_size * entry_price
# fees = position_value * config.taker_fee
# cash -= position_value + fees

fb_entry_price = entry_price * (1 + slippage)  # Apply slippage
fb_allocated = initial_capital * position_size_frac
fb_entry_size = fb_allocated / (fb_entry_price * (1 + taker_fee))
fb_position_value = fb_entry_size * fb_entry_price
fb_fees = fb_position_value * taker_fee
fb_cash_after = initial_capital - fb_position_value - fb_fees

print(f"Entry price (with slippage): {fb_entry_price:.6f}")
print(f"Allocated capital: {fb_allocated:.2f}")
print(f"Entry size:        {fb_entry_size:.8f}")
print(f"Position value:    {fb_position_value:.2f}")
print(f"Entry fees:        {fb_fees:.4f}")
print(f"Cash after entry:  {fb_cash_after:.4f}")

# ============ NUMBA LOGIC ============
print("\n" + "=" * 60)
print("NUMBA LOGIC (from numba_engine.py lines 93-100)")
print("=" * 60)

# From Numba engine:
# entry_price = price * (1.0 + slippage)
# allocated_capital = cash * position_size_frac
# entry_size = allocated_capital / (entry_price * (1.0 + taker_fee))
# position_value = entry_size * entry_price
# fees = position_value * taker_fee
# cash -= position_value + fees

numba_entry_price = entry_price * (1.0 + slippage)
numba_allocated = initial_capital * position_size_frac
numba_entry_size = numba_allocated / (numba_entry_price * (1.0 + taker_fee))
numba_position_value = numba_entry_size * numba_entry_price
numba_fees = numba_position_value * taker_fee
numba_cash_after = initial_capital - numba_position_value - numba_fees

print(f"Entry price (with slippage): {numba_entry_price:.6f}")
print(f"Allocated capital: {numba_allocated:.2f}")
print(f"Entry size:        {numba_entry_size:.8f}")
print(f"Position value:    {numba_position_value:.2f}")
print(f"Entry fees:        {numba_fees:.4f}")
print(f"Cash after entry:  {numba_cash_after:.4f}")

# ============ COMPARISON ============
print("\n" + "=" * 60)
print("COMPARISON")
print("=" * 60)
print(f"Entry size diff:  {abs(fb_entry_size - numba_entry_size):.12f}")
print(f"Fees diff:        {abs(fb_fees - numba_fees):.8f}")
print(f"Cash diff:        {abs(fb_cash_after - numba_cash_after):.8f}")

# Now simulate the PnL diff
print("\n" + "=" * 60)
print("PnL SIMULATION (First short trade, hit SL)")
print("=" * 60)

exit_price = 97829.42
leverage = 1.0

# FALLBACK PnL
# For short: pnl = (entry_price - exit_price) * entry_size * leverage - fees
fb_exit_fees = fb_entry_size * exit_price * taker_fee
fb_pnl = (fb_entry_price - exit_price) * fb_entry_size * leverage - fb_fees - fb_exit_fees
print(f"Fallback PnL: {fb_pnl:.4f}")
print(f"  Entry fee: {fb_fees:.4f}, Exit fee: {fb_exit_fees:.4f}")

# NUMBA PnL (check line 207-208, 214-215)
# if is_long:
#     pnl = (exit_price - entry_price) * entry_size * leverage - fees
# else:
#     pnl = (entry_price - exit_price) * entry_size * leverage - fees
numba_exit_fees = numba_entry_size * exit_price * taker_fee
numba_pnl = (numba_entry_price - exit_price) * numba_entry_size * leverage - numba_exit_fees
print(f"\nNumba PnL (current): {numba_pnl:.4f}")
print(f"  Only exit fee: {numba_exit_fees:.4f}")

# Wait - I see the issue! Numba only subtracts exit fees, not entry fees!
# Let's verify by adding entry fees
numba_pnl_fixed = (numba_entry_price - exit_price) * numba_entry_size * leverage - numba_fees - numba_exit_fees
print(f"\nNumba PnL (with both fees): {numba_pnl_fixed:.4f}")
print(f"  Entry fee: {numba_fees:.4f}, Exit fee: {numba_exit_fees:.4f}")

print("\n" + "=" * 60)
print("CONCLUSION")
print("=" * 60)
print(f"PnL diff (current): {abs(fb_pnl - numba_pnl):.4f}")
print(f"PnL diff (fixed):   {abs(fb_pnl - numba_pnl_fixed):.4f}")
