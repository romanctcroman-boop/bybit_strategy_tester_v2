"""
Verify CAGR and Recovery fix calculations match TV.

TV reference (from screenshots):
  CAGR = 15.00%
  Recovery = 6.44
  Net Profit (closed) = $1,786.98
  Unrealized PnL = +$36.77
  Total PnL = $1,823.56
  Max DD intrabar = $283.03
  Initial Capital = $10,000
  Period: 1 Jan 2025 – 6 Mar 2026T23:59:59
"""

from datetime import datetime

initial = 10_000.0

# TV values
tv_net_closed = 1786.98
tv_unrealized = 36.77
tv_total_pnl = 1823.56  # = 1786.98 + 36.77 ≈ 1823.75 (TV rounds)
tv_max_dd_intrabar = 283.03

# Our values
our_net_closed = 1787.66
our_max_dd_intrabar = 283.02  # approximately same as TV

# Period
start = datetime(2025, 1, 1, 0, 0, 0)
end = datetime(2026, 3, 6, 23, 59, 59)
years = (end - start).total_seconds() / (365.25 * 24 * 3600)
print(f"Period: {start} → {end}")
print(f"Years: {years:.6f}")
print()

# === CAGR ===
print("=== CAGR Fix ===")
# BEFORE (using equity[-1] with unrealized):
# equity[-1] ≈ 10000 + 1787.66 + ~36 = ~11823
our_unrealized_approx = 36.77  # approximate
equity_last_before = initial + our_net_closed + our_unrealized_approx
cagr_before = (pow(equity_last_before / initial, 1 / years) - 1) * 100
print(f"BEFORE: equity[-1]=${equity_last_before:.2f} → CAGR = {cagr_before:.2f}%")

# AFTER (using closed-only final capital):
closed_final = initial + our_net_closed
cagr_after = (pow(closed_final / initial, 1 / years) - 1) * 100
print(f"AFTER:  closed_final=${closed_final:.2f} → CAGR = {cagr_after:.2f}%")

# TV reference
tv_cagr = (pow((initial + tv_net_closed) / initial, 1 / years) - 1) * 100
print(f"TV:     final=${initial + tv_net_closed:.2f} → CAGR = {tv_cagr:.2f}%")
print(f"Delta:  our {cagr_after:.2f}% vs TV 15.00% = {(cagr_after - 15.0) / 15.0 * 100:.2f}%")
print()

# === Recovery ===
print("=== Recovery Fix ===")
# BEFORE (using closed net_profit only):
recovery_before = our_net_closed / our_max_dd_intrabar
print(f"BEFORE: ${our_net_closed:.2f} / ${our_max_dd_intrabar:.2f} = {recovery_before:.3f}")

# AFTER (using total PnL = equity[-1] - initial):
# equity[-1] includes unrealized
our_total_pnl = our_net_closed + our_unrealized_approx
recovery_after = our_total_pnl / our_max_dd_intrabar
print(f"AFTER:  ${our_total_pnl:.2f} / ${our_max_dd_intrabar:.2f} = {recovery_after:.3f}")

# TV reference
tv_recovery = tv_total_pnl / tv_max_dd_intrabar
print(f"TV:     ${tv_total_pnl:.2f} / ${tv_max_dd_intrabar:.2f} = {tv_recovery:.3f}")
print(f"Delta:  our {recovery_after:.3f} vs TV 6.44 = {(recovery_after - 6.44) / 6.44 * 100:.2f}%")
print()

print("=== Summary ===")
print(
    f"CAGR:     {cagr_after:.2f}% vs TV 15.00% → Δ {abs(cagr_after - 15.0):.2f}% ({(cagr_after - 15.0) / 15.0 * 100:+.2f}%)"
)
print(
    f"Recovery: {recovery_after:.3f} vs TV 6.44 → Δ {abs(recovery_after - 6.44):.3f} ({(recovery_after - 6.44) / 6.44 * 100:+.2f}%)"
)
