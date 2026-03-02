"""Test monthly bucketing by exit_time vs entry_time for Sharpe/Sortino."""

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


def compute_sharpe_sortino(monthly_returns):
    m = np.array(monthly_returns)
    N = len(m)
    mean_m = np.mean(m)
    rfr = 0.02 / 12
    std_m = np.std(m, ddof=1)

    # Sharpe (TV confirmed)
    sharpe = (mean_m - rfr) / std_m

    # Sortino - test H formula: sqrt(sum(min(0, r-rfr)^2) / (N-1))
    neg_rfr = np.minimum(0.0, m - rfr)
    dd_H = np.sqrt(np.sum(neg_rfr**2) / (N - 1))
    sortino_H = (mean_m - rfr) / dd_H if dd_H > 0 else 0.0

    # Also E: below-mean semi-dev
    below = m[m < mean_m]
    dd_E = np.sqrt(np.sum((below - mean_m) ** 2) / (N - 1))
    sortino_E = mean_m / dd_E if dd_E > 0 else 0.0

    return sharpe, sortino_H, sortino_E, m.tolist()


# By entry_time
print("=== By ENTRY_TIME ===")
monthly: dict = {}
for t in trades:
    dt = datetime.fromisoformat(t["entry_time"].replace("Z", ""))
    k = (dt.year, dt.month)
    monthly.setdefault(k, 0.0)
    monthly[k] += t["pnl"]
sh, so_H, so_E, mr = compute_sharpe_sortino([monthly[k] / capital for k in sorted(monthly)])
print(f"Sharpe={sh:.4f}  Sortino_H={so_H:.4f}  Sortino_E={so_E:.4f}  ({len(mr)} months)")

# By exit_time
print("\n=== By EXIT_TIME ===")
monthly2: dict = {}
for t in trades:
    ex = t.get("exit_time", t.get("entry_time", ""))
    dt = datetime.fromisoformat(ex.replace("Z", ""))
    k = (dt.year, dt.month)
    monthly2.setdefault(k, 0.0)
    monthly2[k] += t["pnl"]
sh2, so_H2, so_E2, mr2 = compute_sharpe_sortino([monthly2[k] / capital for k in sorted(monthly2)])
print(f"Sharpe={sh2:.4f}  Sortino_H={so_H2:.4f}  Sortino_E={so_E2:.4f}  ({len(mr2)} months)")

print("\nTV: Sharpe=0.35, Sortino=0.587")
