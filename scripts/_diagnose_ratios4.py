"""
Definitive Sharpe/Sortino analysis using bar-by-bar equity curve from engine.
Uses ec.equity and ec.timestamps (10999 bars, 15-min).
"""

import datetime as dt
import json
import os
import sqlite3
import sys

import numpy as np

sys.path.insert(0, "d:\\bybit_strategy_tester_v2")
os.environ.setdefault("DATABASE_URL", "sqlite:///data.sqlite3")
from loguru import logger

logger.remove()

import pandas as pd

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB = "d:\\bybit_strategy_tester_v2\\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"
TV_SHARPE = 0.895
TV_SORTINO = 16.708

conn = sqlite3.connect(DB)
cur = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,))
cols = [d[0] for d in cur.description]
strat = dict(zip(cols, cur.fetchone(), strict=False))
conn.close()

bb = json.loads(strat["builder_blocks"])
bc = json.loads(strat["builder_connections"])
bg = json.loads(strat["builder_graph"])
g = {
    "name": strat["name"],
    "blocks": bb,
    "connections": bc,
    "market_type": "linear",
    "direction": "both",
    "interval": "15",
}
if bg and bg.get("main_strategy"):
    g["main_strategy"] = bg["main_strategy"]
adapter = StrategyBuilderAdapter(g)

conn2 = sqlite3.connect(DB)
start_ms = int(dt.datetime(2025, 11, 1, tzinfo=dt.UTC).timestamp() * 1000)
end_ms = int(dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC).timestamp() * 1000)
df = pd.read_sql_query(
    "SELECT open_time, open_price as open, high_price as high, low_price as low, close_price as close, volume "
    "FROM bybit_kline_audit WHERE symbol=? AND interval=? AND market_type=? AND open_time>=? AND open_time<=? ORDER BY open_time ASC",
    conn2,
    params=("BTCUSDT", "15", "linear", start_ms, end_ms),
)
conn2.close()
df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df = df.set_index("timestamp").drop(columns=["open_time"])

params_j = json.loads(strat["parameters"])
cfg = BacktestConfig(
    symbol="BTCUSDT",
    interval="15",
    start_date=dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
    end_date=dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC),
    initial_capital=10000.0,
    commission_value=float(params_j.get("_commission", 0.0007)),
    slippage=0.0,
    leverage=10.0,
    position_size=0.1,
    pyramiding=1,
    direction="both",
    stop_loss=0.032,
    take_profit=0.015,
)

engine = BacktestEngine()
result = engine.run(cfg, df, custom_strategy=adapter)

ec = result.equity_curve
ec_arr = np.array(ec.equity)
ts_arr = np.array(ec.timestamps)
ret_arr = np.array(ec.returns)  # bar returns (from engine)

print(f"Equity curve: N={len(ec_arr)}, returns N={len(ret_arr)}")
print(f"First equity: {ec_arr[:3]}")
print(f"Last equity:  {ec_arr[-3:]}")
print()

# Build pandas Series
ec_series = pd.Series(ec_arr, index=pd.DatetimeIndex(ts_arr))

# Bar returns (directly from engine)
bar_r = ret_arr  # already computed
# Also compute manually to verify
bar_r_manual = np.diff(ec_arr) / ec_arr[:-1]
bar_r_manual = np.nan_to_num(bar_r_manual)

print(f"Engine bar returns: mean={np.mean(bar_r):.8f}, std={np.std(bar_r, ddof=1):.8f}")
print(f"Manual bar returns: mean={np.mean(bar_r_manual):.8f}, std={np.std(bar_r_manual, ddof=1):.8f}")
print()

# Current implementation: Sharpe with rfr=2%, ppyr=8766
bar_m = np.mean(bar_r)
bar_s = np.std(bar_r, ddof=1)
rfr_period = 0.02 / 8766
sharpe_current = (bar_m - rfr_period) / bar_s * np.sqrt(8766)
print(f"Current Sharpe (bar, rfr=2%, ppyr=8766): {sharpe_current:.4f}  (TV: {TV_SHARPE})")

# Current Sortino
bar_neg = np.minimum(0.0, bar_r)
bar_dd = np.sqrt(np.sum(bar_neg**2) / len(bar_r))
sortino_current = bar_m / bar_dd * np.sqrt(8766) if bar_dd > 0 else float("inf")
print(f"Current Sortino (bar, rfr=0, ppyr=8766):  {sortino_current:.4f}  (TV: {TV_SORTINO})")
print()

# ─── Weekly resampling ────────────────────────────────────────────────────────
print("=" * 60)
print("WEEKLY RESAMPLING (bar-by-bar equity)")
print("=" * 60)

for freq, label in [("W-SUN", "W-SUN"), ("W-MON", "W-MON"), ("W-SAT", "W-SAT"), ("W-FRI", "W-FRI")]:
    weekly_eq = ec_series.resample(freq).last().ffill()
    weekly_r = weekly_eq.pct_change().dropna()
    n = len(weekly_r)
    w = weekly_r.values
    wm = np.mean(w)
    ws = np.std(w, ddof=1)
    ws0 = np.std(w, ddof=0)
    wneg = np.minimum(0.0, w)
    n_neg = np.sum(wneg < 0)
    wdd_total = np.sqrt(np.sum(wneg**2) / n)
    wdd_neg = np.sqrt(np.sum(wneg**2) / n_neg) if n_neg > 0 else 0.0
    wdd_ddof1 = np.sqrt(np.sum(wneg**2) / (n - 1)) if n > 1 else 0.0

    print(f"\n{label}: N={n}, mean={wm:.6f}, std_ddof1={ws:.6f}, std_ddof0={ws0:.6f}")
    print(f"  n_neg={n_neg}, dd_total={wdd_total:.6f}, dd_neg={wdd_neg:.6f}, dd_ddof1={wdd_ddof1:.6f}")
    for rfr in [0.0, 0.02]:
        for ppyr in [52, 52.18, n * (365.25 / 7) / 1]:  # N_weeks * weeks_per_year / actual_weeks?
            if ws > 0:
                rfr_w = rfr / ppyr
                sh = (wm - rfr_w) / ws * np.sqrt(ppyr)
                # Sortino
                so_total = wm / wdd_total * np.sqrt(ppyr) if wdd_total > 0 else float("inf")
                so_neg = wm / wdd_neg * np.sqrt(ppyr) if wdd_neg > 0 else float("inf")
                so_ddof1 = wm / wdd_ddof1 * np.sqrt(ppyr) if wdd_ddof1 > 0 else float("inf")
                print(
                    f"  rfr={rfr:.2f}, ppyr={ppyr:.2f}: Sharpe={sh:.4f}"
                    f"  Sortino_total={so_total:.4f}  Sortino_neg={so_neg:.4f}  Sortino_ddof1={so_ddof1:.4f}"
                )

print()

# ─── Brute force: find annualization factors ──────────────────────────────────
print("=" * 60)
print("BRUTE FORCE: find ppyr that gives TV Sortino=16.708 (weekly W-SUN)")
print("=" * 60)

weekly_eq = ec_series.resample("W-SUN").last().ffill()
weekly_r_sun = weekly_eq.pct_change().dropna().values
wm = np.mean(weekly_r_sun)
wdd = np.sqrt(np.sum(np.minimum(0.0, weekly_r_sun) ** 2) / len(weekly_r_sun))
ws = np.std(weekly_r_sun, ddof=1)

print(f"W-SUN: N={len(weekly_r_sun)}, mean={wm:.6f}, dd_total={wdd:.6f}, std={ws:.6f}")
if wdd > 0:
    ppyr_sortino = (TV_SORTINO / (wm / wdd)) ** 2
    print(f"  For Sortino={TV_SORTINO} with dd_total: ppyr={ppyr_sortino:.2f}  (sqrt={np.sqrt(ppyr_sortino):.4f})")
    print(f"  52 × something = {ppyr_sortino} → something = {ppyr_sortino / 52:.4f}")
    print(f"  Is it N_weeks = {len(weekly_r_sun)}? {ppyr_sortino:.1f} vs {len(weekly_r_sun):.1f}")
if ws > 0:
    ppyr_sharpe = (TV_SHARPE / (wm / ws)) ** 2
    print(f"  For Sharpe={TV_SHARPE} with std: ppyr={ppyr_sharpe:.2f}  (sqrt={np.sqrt(ppyr_sharpe):.4f})")

print()

# ─── Check with non-zero bars only ────────────────────────────────────────────
print("=" * 60)
print("BAR RETURNS: NONZERO ONLY")
print("=" * 60)
nonzero_r = bar_r[bar_r != 0]
nz_n = len(nonzero_r)
nz_m = np.mean(nonzero_r)
nz_s = np.std(nonzero_r, ddof=1)
nz_neg = np.minimum(0.0, nonzero_r)
nz_dd = np.sqrt(np.sum(nz_neg**2) / nz_n)
nz_dd_neg = np.sqrt(np.sum(nz_neg**2) / np.sum(nz_neg < 0)) if np.sum(nz_neg < 0) > 0 else 0

print(f"Nonzero bar returns: N={nz_n}, mean={nz_m:.8f}, std={nz_s:.8f}, dd={nz_dd:.8f}, dd_neg={nz_dd_neg:.8f}")
print()

# Check if EC is a step function (equity only changes on trade exit)
changes = np.sum(np.abs(bar_r_manual) > 1e-10)
print(f"Bars with equity changes (returns != 0): {changes}")
print(f"Total bars: {len(bar_r_manual)}")
print(f"Bars with equity changes from engine: {np.sum(np.abs(bar_r) > 1e-10)}")
print()

# ─── Monthly returns ──────────────────────────────────────────────────────────
print("=" * 60)
print("MONTHLY RESAMPLING")
print("=" * 60)
monthly_eq = ec_series.resample("ME").last().ffill()
monthly_r = monthly_eq.pct_change().dropna()
n = len(monthly_r)
m_r = monthly_r.values
mm = np.mean(m_r)
ms = np.std(m_r, ddof=1)
mneg = np.minimum(0.0, m_r)
mdd = np.sqrt(np.sum(mneg**2) / n)
print(f"Monthly: N={n}, mean={mm:.6f}, std={ms:.6f}, dd={mdd:.6f}")
for rfr in [0.0, 0.02]:
    for ppyr in [12, 12.17]:
        rfr_m = rfr / ppyr
        sh = (mm - rfr_m) / ms * np.sqrt(ppyr) if ms > 0 else 0
        so = mm / mdd * np.sqrt(ppyr) if mdd > 0 else 0
        print(f"  rfr={rfr}, ppyr={ppyr}: Sharpe={sh:.4f}  Sortino={so:.4f}")

print()

# ─── Sharpe/Sortino with TV CAGR ─────────────────────────────────────────────
print("=" * 60)
print("CAGR-BASED RATIOS")
print("=" * 60)

final_eq = ec_arr[-1]
n_days = (dt.datetime(2026, 2, 23) - dt.datetime(2025, 11, 1)).days
n_years = n_days / 365.25
our_cagr = ((final_eq / 10000.0) ** (1.0 / n_years) - 1) * 100
TV_CAGR = 16.22

print(f"Final equity: {final_eq:.2f}, CAGR: {our_cagr:.4f}%  (TV: {TV_CAGR}%)")
print()

for freq, label, ppyr in [("W-SUN", "Weekly-SUN", 52), ("D", "Daily", 365)]:
    resampled = ec_series.resample(freq).last().ffill()
    rets = resampled.pct_change().dropna().values
    if len(rets) == 0:
        continue
    neg_r = np.minimum(0.0, rets)
    dd_total_ann = np.sqrt(np.sum(neg_r**2) / len(rets)) * np.sqrt(ppyr) * 100
    dd_ddof1_ann = np.sqrt(np.sum(neg_r**2) / (len(rets) - 1)) * np.sqrt(ppyr) * 100 if len(rets) > 1 else 0
    print(f"{label}: N={len(rets)}, dd_ann_total={dd_total_ann:.4f}%, dd_ann_ddof1={dd_ddof1_ann:.4f}%")
    for cagr_val, cagr_name in [(our_cagr, "ours"), (TV_CAGR, "TV")]:
        if dd_total_ann > 0:
            so = cagr_val / dd_total_ann
            print(
                f"  CAGR_{cagr_name}={cagr_val:.4f}% / dd_ann_total={dd_total_ann:.4f}% = {so:.4f}  (TV Sortino: {TV_SORTINO})"
            )
        if dd_ddof1_ann > 0:
            so2 = cagr_val / dd_ddof1_ann
            print(
                f"  CAGR_{cagr_name}={cagr_val:.4f}% / dd_ann_ddof1={dd_ddof1_ann:.4f}% = {so2:.4f}  (TV Sortino: {TV_SORTINO})"
            )

print()

# ─── Key summary ─────────────────────────────────────────────────────────────
print("=" * 60)
print("SUMMARY OF BEST CANDIDATES")
print("=" * 60)

weekly_eq_sun = ec_series.resample("W-SUN").last().ffill()
wr_sun = weekly_eq_sun.pct_change().dropna().values
wm = np.mean(wr_sun)
ws = np.std(wr_sun, ddof=1)
wdd = np.sqrt(np.sum(np.minimum(0.0, wr_sun) ** 2) / len(wr_sun))

print(f"Current: Sharpe={sharpe_current:.4f}, Sortino={sortino_current:.4f}")
print(f"TV:      Sharpe={TV_SHARPE},    Sortino={TV_SORTINO}")
print()
print(f"Weekly W-SUN (N={len(wr_sun)}):")
for pp in [52, len(wr_sun)]:
    sh = wm / ws * np.sqrt(pp) if ws > 0 else 0
    so = wm / wdd * np.sqrt(pp) if wdd > 0 else 0
    print(f"  ppyr={pp}: Sharpe={sh:.4f}, Sortino={so:.4f}")

print()
print("Differences:")
print(f"  Sharpe: TV={TV_SHARPE}, best_weekly={wm / ws * np.sqrt(52):.4f}")
print(f"  Sortino: TV={TV_SORTINO}, best_weekly={wm / wdd * np.sqrt(52):.4f}")
