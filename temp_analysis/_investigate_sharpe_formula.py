"""
Investigate which Sharpe formula matches TV=0.35
"""

import json
import sqlite3
import sys
from datetime import datetime

import numpy as np

sys.path.insert(0, ".")

# Load reference trades from DB
conn = sqlite3.connect("data.sqlite3")
cur = conn.execute("SELECT trades FROM backtests WHERE id LIKE '68758d14%'")
row = cur.fetchone()
conn.close()

trades = json.loads(row[0])
pnls = [t["pnl"] for t in trades]
print(f"Trades: {len(trades)}, net={sum(pnls):.4f}")

capital = 10000.0
notional = capital * 0.1  # = 1000 USDT per trade

# ── 1. Trade-by-trade: pnl / capital ─────────────────────────────────────────
r = np.array([p / capital for p in pnls])
mean_r, std_r = np.mean(r), np.std(r, ddof=1)
print(f"\n1. Trade-by-trade (pnl/capital):")
print(f"   mean={mean_r:.6f}  std={std_r:.6f}")
print(f"   Sharpe (raw, no rfr):           {mean_r / std_r:.4f}")
print(f"   Sharpe * sqrt(12):              {mean_r / std_r * np.sqrt(12):.4f}")
print(f"   Sharpe * sqrt(155):             {mean_r / std_r * np.sqrt(155):.4f}")

# ── 2. Trade-by-trade: pnl / notional ────────────────────────────────────────
r2 = np.array([p / notional for p in pnls])
mean_r2, std_r2 = np.mean(r2), np.std(r2, ddof=1)
print(f"\n2. Trade-by-trade (pnl/notional=1000):")
print(f"   Sharpe raw: {mean_r2 / std_r2:.4f}")

# ── 3. Monthly equity returns ─────────────────────────────────────────────────
monthly: dict = {}
for t in trades:
    dt = datetime.fromisoformat(t["entry_time"].replace("Z", ""))
    key = (dt.year, dt.month)
    monthly.setdefault(key, 0.0)
    monthly[key] += t["pnl"]

months = sorted(monthly.keys())
monthly_returns = [monthly[m] / capital for m in months]
print(f"\n3. Monthly returns ({len(monthly_returns)} months): {[f'{r:.4f}' for r in monthly_returns]}")

m = np.array(monthly_returns)
mean_m, std_m = np.mean(m), np.std(m, ddof=1)
rfr_m = 0.02 / 12
print(f"   mean={mean_m:.6f}  std={std_m:.6f}")
print(f"   Sharpe monthly raw (rfr=2%/yr):    {(mean_m - rfr_m) / std_m:.4f}")
print(f"   Sharpe monthly * sqrt(12) (rfr):   {(mean_m - rfr_m) / std_m * np.sqrt(12):.4f}")
print(f"   Sharpe monthly * sqrt(12) (no rfr): {mean_m / std_m * np.sqrt(12):.4f}")

# ── 4. TV formula: SQN-like (sqrt(N) * mean/std) ─────────────────────────────
print(f"\n4. TV SQN-like formula (sqrt(N) * mean/std):")
print(f"   trade returns: {np.sqrt(len(pnls)) * mean_r / std_r:.4f}")

# ── 5. BacktestEngine uses MetricsCalculator with HOURLY equity curve ─────────
# Let's simulate what BacktestEngine produces: 20350-bar equity array
# For this we need to load equity_curve from the DB backtest result
conn2 = sqlite3.connect("data.sqlite3")
cur2 = conn2.execute("SELECT equity_curve FROM backtests WHERE id LIKE '68758d14%'")
row2 = cur2.fetchone()
conn2.close()

if row2 and row2[0]:
    equity_data = json.loads(row2[0])
    print(f"\n5. Equity curve from DB ({len(equity_data)} points):")

    equity = np.array(equity_data, dtype=float)
    # Compute bar-level returns
    bar_returns = np.diff(equity) / np.maximum(equity[:-1], 1.0)
    bar_returns = bar_returns[np.isfinite(bar_returns)]
    mean_bar = np.mean(bar_returns)
    std_bar = np.std(bar_returns, ddof=1)
    # ANNUALIZATION_HOURLY = 8766 (30m bars = 17532 per year)
    ann_30m = 17532.0  # 365.25*24*2
    ann_hourly = 8766.0

    rfr_period = 0.02 / ann_hourly
    sh_hourly = (mean_bar - rfr_period) / std_bar * np.sqrt(ann_hourly)
    sh_30m = (mean_bar - 0.02 / ann_30m) / std_bar * np.sqrt(ann_30m)
    sh_raw = mean_bar / std_bar
    print(f"   bar returns: mean={mean_bar:.8f}  std={std_bar:.8f}")
    print(f"   Sharpe (ANNUALIZATION_HOURLY=8766):  {sh_hourly:.4f}")
    print(f"   Sharpe (ANNUALIZATION_30m=17532):    {sh_30m:.4f}")
    print(f"   Sharpe raw (no ann):                 {sh_raw:.4f}")
else:
    print("\n5. No equity_curve in DB for this backtest")

print(f"\nTV Gold Standard Sharpe = 0.35")
print(f"TV Gold Standard Sortino = 0.587")
