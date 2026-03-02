"""
Narrow down the exact TV Sortino=0.587 formula.
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

# Monthly returns
monthly: dict = {}
for t in trades:
    dt = datetime.fromisoformat(t["entry_time"].replace("Z", ""))
    key = (dt.year, dt.month)
    monthly.setdefault(key, 0.0)
    monthly[key] += t["pnl"]

months = sorted(monthly.keys())
m = np.array([monthly[k] / capital for k in months])
mean_m = np.mean(m)
rfr_m = 0.02 / 12

print(f"Monthly returns ({len(m)} months):")
for i, (mo, r) in enumerate(zip(months, m)):
    print(f"  {mo[0]}-{mo[1]:02d}: {r:.6f}")

print(f"\nmean={mean_m:.6f}")

# Various Sortino variants
mar = 0.0

# Variant A: downside = only negative returns, std of those (ddof=1)
neg_only = m[m < mar]
if len(neg_only) > 1:
    dd_A = np.std(neg_only, ddof=1)
    print(f"\nA. std(negative only, ddof=1): {dd_A:.6f} → Sortino = {mean_m/dd_A:.4f}")

# Variant B: TV-style: sqrt(sum(min(0,r)^2)/N) — ALL N
neg = np.minimum(0, m)
dd_B = np.sqrt(np.sum(neg**2) / len(m))
print(f"B. sqrt(sum(min(0)^2)/N): {dd_B:.6f} → Sortino = {mean_m/dd_B:.4f}")

# Variant C: sqrt(sum(min(0,r)^2)/(N-1)) — ddof=1
dd_C = np.sqrt(np.sum(neg**2) / (len(m) - 1))
print(f"C. sqrt(sum(min(0)^2)/(N-1)): {dd_C:.6f} → Sortino = {mean_m/dd_C:.4f}")

# Variant D: semi-deviation = std of (r - mean) for r < mean (ddof=0)
below_mean = m[m < mean_m]
dd_D = np.sqrt(np.mean((below_mean - mean_m)**2))
print(f"D. semi-dev (r<mean, ddof=0): {dd_D:.6f} → Sortino = {mean_m/dd_D:.4f}")

# Variant E: semi-deviation all points (r - mean) where r < mean, ddof=1
dd_E = np.sqrt(np.sum((below_mean - mean_m)**2) / (len(m) - 1))
print(f"E. semi-dev (r<mean, ddof=1): {dd_E:.6f} → Sortino = {mean_m/dd_E:.4f}")

# Variant F: TV full formula with rfr
rfr_m = 0.02 / 12
print(f"\nWith RFR={rfr_m:.6f}:")
print(f"B+rfr: {(mean_m - rfr_m)/dd_B:.4f}")
print(f"C+rfr: {(mean_m - rfr_m)/dd_C:.4f}")
print(f"A+rfr: {(mean_m - rfr_m)/dd_A:.4f}")

# Variant G: trade-by-trade sortino (not monthly)
trade_r = np.array([p / capital for p in pnls])
mean_tr = np.mean(trade_r)
neg_tr = np.minimum(0, trade_r)
dd_G = np.sqrt(np.sum(neg_tr**2) / len(trade_r))
print(f"\nG. Trade-by-trade (TV formula): {mean_tr/dd_G:.4f}")

neg_only_tr = trade_r[trade_r < 0]
if len(neg_only_tr) > 1:
    dd_H = np.std(neg_only_tr, ddof=1)
    print(f"H. Trade-by-trade (std neg only): {mean_tr/dd_H:.4f}")

print(f"\nTV Gold Standard Sortino = 0.587")
