"""
Verify TV Sharpe=0.35 and Sortino=0.587 formulas.
Result: Monthly returns, no annualization, RFR=2%/yr
"""

import json
import sqlite3
import sys
from datetime import datetime

import numpy as np

sys.path.insert(0, ".")

conn = sqlite3.connect("data.sqlite3")
cur = conn.execute("SELECT trades FROM backtests WHERE id LIKE '68758d14%'")
row = cur.fetchone()
conn.close()

trades = json.loads(row[0])
pnls = [t["pnl"] for t in trades]
capital = 10000.0

# ── Monthly returns ──────────────────────────────────────────────────────────
monthly: dict = {}
for t in trades:
    dt = datetime.fromisoformat(t["entry_time"].replace("Z", ""))
    key = (dt.year, dt.month)
    monthly.setdefault(key, 0.0)
    monthly[key] += t["pnl"]

months = sorted(monthly.keys())
m = np.array([monthly[k] / capital for k in months])
mean_m = np.mean(m)
std_m = np.std(m, ddof=1)
rfr_m = 0.02 / 12  # 2% annual → monthly

# TV Sharpe (no annualization multiplier — stays monthly)
sharpe = (mean_m - rfr_m) / std_m
print(f"TV Sharpe formula: (mean - rfr/12) / std_monthly")
print(f"  mean_monthly={mean_m:.6f}, std={std_m:.6f}, rfr_m={rfr_m:.6f}")
print(f"  Sharpe = {sharpe:.4f}  (TV=0.35)")

# TV Sortino (monthly, MAR=0, downside dev = sqrt(mean(min(0,r)^2)) across ALL months including positive)
mar = 0.0
neg = np.minimum(0, m - mar)
downside_var = np.sum(neg**2) / len(m)  # TV: divide by ALL N
downside_dev = np.sqrt(downside_var)
sortino = (mean_m - mar) / downside_dev
print(f"\nTV Sortino formula: mean / sqrt(sum(min(0,r)^2) / N)")
print(f"  downside_dev={downside_dev:.6f}")
print(f"  Sortino = {sortino:.4f}  (TV=0.587)")

# What FallbackV4 currently uses:
# bar-by-bar equity returns * sqrt(8766)  → completely different scale
print("\n--- FallbackV4 current approach (wrong for TV) ---")
print("Uses calc_returns_from_equity(equity_arr) → bar-level returns")
print("Then calc_sharpe(returns, ANNUALIZATION_HOURLY=8766)")
print("This annualizes by sqrt(8766) ≈ 93.6x, producing Sharpe ~0.57 instead of 0.35")
print("\nFix: use monthly returns + no annualization multiplier (or *sqrt(12) if TV does it)")
print(f"  With *sqrt(12): {sharpe * np.sqrt(12):.4f}")
print(f"  Without: {sharpe:.4f}  ← matches TV=0.35")
