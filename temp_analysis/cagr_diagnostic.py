"""
CAGR diagnostic: verify what values _build_performance_metrics receives.

TV reference:
  CAGR = 15.00%
  Period: 1 Jan 2025 – 6 Mar 2026 = 430 days
  Net Profit = $1,786.98
  Initial = $10,000
  Final = $11,786.98
  (11786.98/10000)^(365.25/430) - 1 = 14.99% ≈ 15.00%
"""

import math

initial = 10_000.0

# TV values
tv_net = 1786.98
tv_final = initial + tv_net  # 11786.98

# Full backtest window
from datetime import datetime

start = datetime(2025, 1, 1)
end = datetime(2026, 3, 6)
days = (end - start).days
years = (end - start).total_seconds() / (365.25 * 24 * 3600)
print(f"Full window: {start.date()} → {end.date()}")
print(f"Days: {days}, Years: {years:.6f}")
cagr_tv = (pow(tv_final / initial, 1 / years) - 1) * 100
print(f"TV CAGR = ({tv_final}/{initial})^(1/{years:.4f}) - 1 = {cagr_tv:.2f}%")
print()

# Our values (from last export)
our_net = 1787.66
our_final = initial + our_net  # 11787.66
# If years were right (1.1773), CAGR would be:
cagr_ours_correct = (pow(our_final / initial, 1 / years) - 1) * 100
print(f"Our final = {our_final}")
print(f"With correct years ({years:.4f}): CAGR = {cagr_ours_correct:.2f}%")
print()

# What years would produce CAGR = 15.28%?
# 15.28/100 = (our_final/initial)^(1/y) - 1
# 1.1528 = (1.178766)^(1/y)
# 1/y = ln(1.1528) / ln(1.178766)
# y = ln(1.178766) / ln(1.1528)
target_cagr = 0.1528
y_implied = math.log(our_final / initial) / math.log(1 + target_cagr)
print(f"For CAGR=15.28%: implied years = {y_implied:.4f}")
print(f"  implied days = {y_implied * 365.25:.1f}")
print()

# Check common timestamp-based calculations
# If using first trade entry → last trade exit
# Typical: first entry ~2025-01-10, last exit ~2026-03-04
print("=== Possible date ranges ===")
for desc, s, e in [
    ("Full window", datetime(2025, 1, 1), datetime(2026, 3, 6)),
    ("Typical trades", datetime(2025, 1, 10), datetime(2026, 3, 4)),
    ("First bar → last bar", datetime(2025, 1, 1, 0, 0), datetime(2026, 3, 6, 0, 0)),
    ("end_date midnight", datetime(2025, 1, 1, 0, 0), datetime(2026, 3, 6, 0, 0)),
    ("end_date end-of-day", datetime(2025, 1, 1, 0, 0), datetime(2026, 3, 6, 23, 59, 59)),
    # What if end_date is 'today' = current bar, not end of range?
    ("end_date=2026-03-05", datetime(2025, 1, 1), datetime(2026, 3, 5)),
    ("end_date=2026-03-04", datetime(2025, 1, 1), datetime(2026, 3, 4)),
    # With specific hours
    ("2025-01-01 → 2026-03-06 00:00", datetime(2025, 1, 1, 0, 0), datetime(2026, 3, 6, 0, 0)),
]:
    d = (e - s).total_seconds() / (365.25 * 24 * 3600)
    c = (pow(our_final / initial, 1 / d) - 1) * 100
    dd = (e - s).days
    print(f"  {desc:40s}: {dd} days, {d:.4f} yr → CAGR = {c:.2f}%")

print()
# Reverse: what end_date gives 15.28%?
# y = ln(1.178766) / ln(1.1528) = 1.157
# days = 1.157 * 365.25 = 422.7
print(f"15.28% implies ~{y_implied * 365.25:.0f} days from start")
from datetime import timedelta

implied_end = start + timedelta(days=y_implied * 365.25)
print(f"Implied end_date = {implied_end}")
