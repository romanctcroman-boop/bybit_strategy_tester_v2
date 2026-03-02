"""Fine-tune Sortino formula."""

import json
import sqlite3
import sys
from datetime import datetime

import numpy as np

sys.path.insert(0, ".")
conn = sqlite3.connect("data.sqlite3")
row = conn.execute("SELECT trades FROM backtests WHERE id LIKE '68758d14%'").fetchone()
conn.close()
trades = json.loads(row[0])
capital = 10000.0
monthly: dict = {}
for t in trades:
    dt = datetime.fromisoformat(t["entry_time"].replace("Z", ""))
    k = (dt.year, dt.month)
    monthly.setdefault(k, 0.0)
    monthly[k] += t["pnl"]
m = np.array([monthly[k] / capital for k in sorted(monthly)])
N = len(m)
mean_m = np.mean(m)
rfr = 0.02 / 12

# Semi-deviation approaches
below = m[m < mean_m]
n_below = len(below)

# E: (r-mean)^2 summed, divided by (N_total - 1)
dd_E = np.sqrt(np.sum((below - mean_m) ** 2) / (N - 1))
print(f"E  semi-dev(below mean, /N-1):       {dd_E:.6f} -> Sortino={mean_m / dd_E:.4f}")

# E2: divided by N_total
dd_E2 = np.sqrt(np.sum((below - mean_m) ** 2) / N)
print(f"E2 semi-dev(below mean, /N):         {dd_E2:.6f} -> Sortino={mean_m / dd_E2:.4f}")

# E3: divided by (N_below - 1)
dd_E3 = np.sqrt(np.sum((below - mean_m) ** 2) / (n_below - 1))
print(f"E3 semi-dev(below mean, /N_neg-1):   {dd_E3:.6f} -> Sortino={mean_m / dd_E3:.4f}")

# F: below MAR=0, (r - 0)^2 / (N-1)
below_zero = m[m < 0]
dd_F = np.sqrt(np.sum(below_zero**2) / (N - 1))
print(f"F  semi-dev(below 0,   /N-1):        {dd_F:.6f} -> Sortino={mean_m / dd_F:.4f}")

# F2: below MAR=0, /N
dd_F2 = np.sqrt(np.sum(below_zero**2) / N)
print(f"F2 semi-dev(below 0,   /N):          {dd_F2:.6f} -> Sortino={mean_m / dd_F2:.4f}")

# G: TV exact: sqrt(sum(min(0, r-MAR)^2) / N), MAR=rfr
neg_rfr = np.minimum(0.0, m - rfr)
dd_G = np.sqrt(np.sum(neg_rfr**2) / N)
print(f"G  TV(MAR=rfr, /N):                  {dd_G:.6f} -> Sortino={(mean_m - rfr) / dd_G:.4f}")

# H: TV exact: sqrt(sum(min(0, r-MAR)^2) / (N-1)), MAR=rfr
dd_H = np.sqrt(np.sum(neg_rfr**2) / (N - 1))
print(f"H  TV(MAR=rfr, /N-1):                {dd_H:.6f} -> Sortino={(mean_m - rfr) / dd_H:.4f}")

# I: E with rfr
print(f"E+rfr: {(mean_m - rfr) / dd_E:.4f}")
print(f"E3+rfr: {(mean_m - rfr) / dd_E3:.4f}")

print(f"\nTV target Sortino = 0.587")
print(f"Closest so far: E = {mean_m / dd_E:.4f} (0.5769)")
