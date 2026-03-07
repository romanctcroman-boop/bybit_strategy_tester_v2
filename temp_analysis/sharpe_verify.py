"""Verify Sharpe/Sortino from the 43 closed trades in updated CSV."""

import numpy as np
import pandas as pd

# Use the new export trades CSV
df = pd.read_csv(r"c:\Users\roman\Downloads\trades_18784362-fa1f-40ce-ae02-d6cf691e7a93.csv")
print(f"Total trades: {len(df)}")

# First 43 are closed, #44 is open
closed = df.iloc[:43]
initial_capital = 10000.0
rfr_m = 0.02 / 12

tc_times = pd.to_datetime(closed["Exit Time"])
cum_pnl = np.cumsum(closed["P&L"].values)
tc_equity = initial_capital + cum_pnl

tc_series = pd.Series(tc_equity, index=tc_times)
anchor = pd.Series([initial_capital], index=[tc_times.iloc[0] - pd.offsets.MonthEnd(1)])
combined = pd.concat([anchor, tc_series])
monthly_eq = combined.resample("ME").last().ffill()
monthly_r = monthly_eq.pct_change().dropna().values
N = len(monthly_r)
mean_r = np.mean(monthly_r)
std0 = np.std(monthly_r, ddof=0)
sharpe_ddof0 = (mean_r - rfr_m) / std0
std1 = np.std(monthly_r, ddof=1)
sharpe_ddof1 = (mean_r - rfr_m) / std1

sneg = np.minimum(0.0, monthly_r - rfr_m)
sdd = np.sqrt(np.sum(sneg**2) / N)
sortino = (mean_r - rfr_m) / sdd

print(f"\nMonthly equity points: {len(monthly_eq)}")
print(f"Monthly equity: {[f'{v:.2f}' for v in monthly_eq.values]}")
print(f"Monthly returns (N={N}):")
for i, (dt, r) in enumerate(zip(monthly_eq.index[1:], monthly_r)):
    print(f"  {dt.strftime('%Y-%m')}: {r * 100:+.4f}%")

print(f"\nMean monthly return: {mean_r:.6f}")
print(f"Std (ddof=0): {std0:.6f}")
print(f"Std (ddof=1): {std1:.6f}")
print()
print(f"Sharpe (ddof=0): {sharpe_ddof0:.4f}  (TV: 0.942, diff: {(sharpe_ddof0 - 0.942) / 0.942 * 100:+.2f}%)")
print(f"Sharpe (ddof=1): {sharpe_ddof1:.4f}  (TV: 0.942, diff: {(sharpe_ddof1 - 0.942) / 0.942 * 100:+.2f}%)")
print(f"Sortino:         {sortino:.4f}  (TV: 4.24, diff: {(sortino - 4.24) / 4.24 * 100:+.2f}%)")

# Also compute with last trade #44 included (as in our engine if it's marked open)
print("\n--- With trade #44 included as closed ---")
all_trades = df
tc_times_all = pd.to_datetime(all_trades["Exit Time"])
cum_pnl_all = np.cumsum(all_trades["P&L"].values)
tc_equity_all = initial_capital + cum_pnl_all

tc_series_all = pd.Series(tc_equity_all, index=tc_times_all)
anchor_all = pd.Series([initial_capital], index=[tc_times_all.iloc[0] - pd.offsets.MonthEnd(1)])
combined_all = pd.concat([anchor_all, tc_series_all])
monthly_eq_all = combined_all.resample("ME").last().ffill()
monthly_r_all = monthly_eq_all.pct_change().dropna().values
N_all = len(monthly_r_all)
mean_all = np.mean(monthly_r_all)
std0_all = np.std(monthly_r_all, ddof=0)
sharpe_all = (mean_all - rfr_m) / std0_all
sneg_all = np.minimum(0.0, monthly_r_all - rfr_m)
sdd_all = np.sqrt(np.sum(sneg_all**2) / N_all)
sortino_all = (mean_all - rfr_m) / sdd_all
print(f"Sharpe (ddof=0): {sharpe_all:.4f}")
print(f"Sortino:         {sortino_all:.4f}")
