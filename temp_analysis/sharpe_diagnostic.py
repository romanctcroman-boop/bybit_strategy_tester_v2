"""
Diagnostic: reverse-engineer TV Sharpe/Sortino/Recovery from actual trade data.
Uses trades from CSV to compute monthly returns with different methods.
"""

import sys

import numpy as np
import pandas as pd

# TV reference values
TV_SHARPE = 0.942
TV_SORTINO = 4.24
TV_RECOVERY = 6.42
TV_NET_PROFIT = 1786.98

# Read trades from CSV
trades_csv = r"c:\Users\roman\Downloads\trades_21a4beef-c71a-4ccd-964a-9639203fc64a.csv"
df = pd.read_csv(trades_csv)

print(f"Total trades: {len(df)}")
print(f"Columns: {list(df.columns)}")
print()

initial_capital = 10000.0
rfr_annual = 0.02
rfr_monthly = rfr_annual / 12

# --- Method 1: Trade-close equity, monthly resample ---
print("=" * 70)
print("METHOD 1: Trade-close equity → monthly resample (current code)")
print("=" * 70)

# Build trade-close equity
tc_times = pd.to_datetime(df["Exit Time"])
tc_pnl = df["P&L"].values
cum_pnl = np.cumsum(tc_pnl)
tc_equity = initial_capital + cum_pnl

tc_series = pd.Series(tc_equity, index=tc_times)
# Anchor: initial capital one month before first trade
anchor = pd.Series([initial_capital], index=[tc_times.iloc[0] - pd.offsets.MonthEnd(1)])
combined = pd.concat([anchor, tc_series])
monthly_eq = combined.resample("ME").last().ffill()
monthly_r = monthly_eq.pct_change().dropna().values

N = len(monthly_r)
mean_r = np.mean(monthly_r)

# Sharpe (ddof=0)
std0 = np.std(monthly_r, ddof=0)
sharpe1 = (mean_r - rfr_monthly) / std0 if std0 > 1e-10 else 0

# Sortino (N denominator)
sneg = np.minimum(0.0, monthly_r - rfr_monthly)
sdd = np.sqrt(np.sum(sneg**2) / N)
sortino1 = (mean_r - rfr_monthly) / sdd if sdd > 1e-10 else 0

print(f"Monthly equity points: {len(monthly_eq)}")
print(f"Monthly returns (N={N}): {monthly_r}")
print(f"Mean monthly return: {mean_r:.6f}")
print(f"Std (ddof=0): {std0:.6f}")
print(f"Sharpe:  {sharpe1:.4f}  (TV: {TV_SHARPE}, diff: {(sharpe1 - TV_SHARPE) / TV_SHARPE * 100:+.2f}%)")
print(f"Sortino: {sortino1:.4f}  (TV: {TV_SORTINO}, diff: {(sortino1 - TV_SORTINO) / TV_SORTINO * 100:+.2f}%)")
print()

# --- Method 2: Trade-close equity, NO anchor ---
print("=" * 70)
print("METHOD 2: Trade-close equity, NO anchor (start from first trade)")
print("=" * 70)

monthly_eq2 = tc_series.resample("ME").last().ffill()
# Prepend initial capital as Jan 2025 value
monthly_eq2.loc[pd.Timestamp("2024-12-31")] = initial_capital
monthly_eq2 = monthly_eq2.sort_index()
monthly_r2 = monthly_eq2.pct_change().dropna().values

N2 = len(monthly_r2)
mean_r2 = np.mean(monthly_r2)
std02 = np.std(monthly_r2, ddof=0)
sharpe2 = (mean_r2 - rfr_monthly) / std02 if std02 > 1e-10 else 0
sneg2 = np.minimum(0.0, monthly_r2 - rfr_monthly)
sdd2 = np.sqrt(np.sum(sneg2**2) / N2)
sortino2 = (mean_r2 - rfr_monthly) / sdd2 if sdd2 > 1e-10 else 0

print(f"Monthly returns (N={N2}): {monthly_r2}")
print(f"Sharpe:  {sharpe2:.4f}  (TV: {TV_SHARPE}, diff: {(sharpe2 - TV_SHARPE) / TV_SHARPE * 100:+.2f}%)")
print(f"Sortino: {sortino2:.4f}  (TV: {TV_SORTINO}, diff: {(sortino2 - TV_SORTINO) / TV_SORTINO * 100:+.2f}%)")
print()

# --- Method 3: Try ddof=1 (sample std) ---
print("=" * 70)
print("METHOD 3: Trade-close monthly + ddof=1 (sample std)")
print("=" * 70)
std1 = np.std(monthly_r, ddof=1)
sharpe3 = (mean_r - rfr_monthly) / std1 if std1 > 1e-10 else 0
print(f"Sharpe (ddof=1):  {sharpe3:.4f}  (TV: {TV_SHARPE}, diff: {(sharpe3 - TV_SHARPE) / TV_SHARPE * 100:+.2f}%)")
print()

# --- Method 4: Anchored at 2025-01-01 (exact config start_date) ---
print("=" * 70)
print("METHOD 4: Anchor at 2025-01-01 (config start_date)")
print("=" * 70)
anchor4 = pd.Series([initial_capital], index=[pd.Timestamp("2025-01-01")])
combined4 = pd.concat([anchor4, tc_series])
monthly_eq4 = combined4.resample("ME").last().ffill()
monthly_r4 = monthly_eq4.pct_change().dropna().values

N4 = len(monthly_r4)
mean_r4 = np.mean(monthly_r4)
std04 = np.std(monthly_r4, ddof=0)
sharpe4 = (mean_r4 - rfr_monthly) / std04 if std04 > 1e-10 else 0
sneg4 = np.minimum(0.0, monthly_r4 - rfr_monthly)
sdd4 = np.sqrt(np.sum(sneg4**2) / N4)
sortino4 = (mean_r4 - rfr_monthly) / sdd4 if sdd4 > 1e-10 else 0

print(f"Monthly equity: {monthly_eq4.values}")
print(f"Monthly returns (N={N4}): {monthly_r4}")
print(f"Sharpe:  {sharpe4:.4f}  (TV: {TV_SHARPE}, diff: {(sharpe4 - TV_SHARPE) / TV_SHARPE * 100:+.2f}%)")
print(f"Sortino: {sortino4:.4f}  (TV: {TV_SORTINO}, diff: {(sortino4 - TV_SORTINO) / TV_SORTINO * 100:+.2f}%)")
print()

# --- Method 5: RFR=0 (some TV versions use 0) ---
print("=" * 70)
print("METHOD 5: Trade-close monthly + RFR=0")
print("=" * 70)
sharpe5 = mean_r / std0 if std0 > 1e-10 else 0
sneg5 = np.minimum(0.0, monthly_r)
sdd5 = np.sqrt(np.sum(sneg5**2) / N)
sortino5 = mean_r / sdd5 if sdd5 > 1e-10 else 0
print(f"Sharpe (rfr=0):  {sharpe5:.4f}  (TV: {TV_SHARPE}, diff: {(sharpe5 - TV_SHARPE) / TV_SHARPE * 100:+.2f}%)")
print(f"Sortino (rfr=0): {sortino5:.4f}  (TV: {TV_SORTINO}, diff: {(sortino5 - TV_SORTINO) / TV_SORTINO * 100:+.2f}%)")
print()

# --- Method 6: Trade PnL returns (not monthly equity) ---
print("=" * 70)
print("METHOD 6: Per-trade returns (PnL / equity_before_trade)")
print("=" * 70)
trade_returns = []
eq = initial_capital
for pnl in tc_pnl:
    ret = pnl / eq if eq > 0 else 0
    trade_returns.append(ret)
    eq += pnl
trade_returns = np.array(trade_returns)

mean_tr = np.mean(trade_returns)
std_tr = np.std(trade_returns, ddof=0)
sharpe6 = mean_tr / std_tr if std_tr > 1e-10 else 0
sneg6 = np.minimum(0.0, trade_returns)
sdd6 = np.sqrt(np.sum(sneg6**2) / len(trade_returns))
sortino6 = mean_tr / sdd6 if sdd6 > 1e-10 else 0
print(f"Per-trade returns: mean={mean_tr:.6f}, std={std_tr:.6f}")
print(f"Sharpe (per-trade):  {sharpe6:.4f}  (TV: {TV_SHARPE})")
print(f"Sortino (per-trade): {sortino6:.4f}  (TV: {TV_SORTINO})")
print()

# --- Recovery analysis ---
print("=" * 70)
print("RECOVERY FACTOR ANALYSIS")
print("=" * 70)
net_profit = tc_equity[-1] - initial_capital
print(f"Net profit: ${net_profit:.2f}")
print(f"TV Recovery = {TV_RECOVERY} → TV MaxDD = ${net_profit / TV_RECOVERY:.2f}")

# Trade-exit equity DD
te_arr = np.array([initial_capital] + list(tc_equity))
te_peak = np.maximum.accumulate(te_arr)
te_dd = te_peak - te_arr
max_dd_trade_exit = float(np.max(te_dd))
recovery_te = net_profit / max_dd_trade_exit if max_dd_trade_exit > 0 else 0
print(f"Trade-exit MaxDD: ${max_dd_trade_exit:.2f} → Recovery: {recovery_te:.4f}")

# Intrabar DD (from dynamics CSV)
max_dd_intrabar = 283.02
recovery_ib = net_profit / max_dd_intrabar
print(f"Intrabar MaxDD:   ${max_dd_intrabar:.2f} → Recovery: {recovery_ib:.4f}")

# What if TV uses max_dd_close from dynamics?
max_dd_close = 266.75
recovery_cl = net_profit / max_dd_close
print(f"Close MaxDD:      ${max_dd_close:.2f} → Recovery: {recovery_cl:.4f}")

print()
print(f"TV implied MaxDD for Recovery {TV_RECOVERY}: ${net_profit / TV_RECOVERY:.2f}")
print(f"None of our values match. Closest: intrabar ${max_dd_intrabar:.2f} (recovery {recovery_ib:.3f})")
