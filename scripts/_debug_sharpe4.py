"""
Find the exact annualization factor that gives TV Sharpe = 0.895.
"""

import datetime as dt
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd
from scipy.optimize import brentq

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
os.environ.setdefault("DATABASE_URL", "sqlite:///data.sqlite3")

from loguru import logger

logger.remove()

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"
TV_SHARPE = 0.895

# ── Load strategy ────────────────────────────────────────────────────────────
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

# ── Load OHLCV ──────────────────────────────────────────────────────────────
conn2 = sqlite3.connect(DB)
start_ms = int(dt.datetime(2025, 11, 1, tzinfo=dt.UTC).timestamp() * 1000)
end_ms = int(dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC).timestamp() * 1000)
df = pd.read_sql_query(
    "SELECT open_time, open_price as open, high_price as high, low_price as low, "
    "close_price as close, volume "
    "FROM bybit_kline_audit WHERE symbol=? AND interval=? AND market_type=? "
    "AND open_time>=? AND open_time<=? ORDER BY open_time ASC",
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

# ── Run backtest ─────────────────────────────────────────────────────────────
engine = BacktestEngine()
result = engine.run(cfg, df, custom_strategy=adapter)
ec = result.equity_curve
equity_arr = np.array(ec.equity)
timestamps = ec.timestamps
_ts_idx = pd.DatetimeIndex(timestamps)
ec_series = pd.Series(equity_arr, index=_ts_idx)

print(f"Engine sharpe_ratio : {result.metrics.sharpe_ratio:.4f}  (TV: {TV_SHARPE})")
print(f"Engine sortino_ratio: {result.metrics.sortino_ratio:.4f}  (TV: 16.708)")
print(f"Bars: {len(equity_arr)}, Period: {_ts_idx[0].date()} → {_ts_idx[-1].date()}")
print()

# ── Bar-by-bar returns ───────────────────────────────────────────────────────
bar_r = ec_series.pct_change().dropna().values
bar_r = bar_r[np.isfinite(bar_r)]
m = np.mean(bar_r)
s = np.std(bar_r, ddof=1)
print(f"Bar count: {len(bar_r)}, Mean: {m:.10f}, Std: {s:.10f}")

# ── Spot-check known factors ─────────────────────────────────────────────────
print("\nFactor sweep (with rfr = 0.02/ppyr):")
for ppyr in [2190, 4380, 5256, 6480, 8766, 17532, 26298, 35064]:
    rfr_p = 0.02 / ppyr
    val = (m - rfr_p) / s * ppyr**0.5
    diff = abs(val - TV_SHARPE) / TV_SHARPE * 100
    mark = "[OK]" if diff < 2 else ("[~~]" if diff < 10 else "")
    print(f"  sqrt({ppyr:6d}): sharpe={val:.4f}  ({diff:.2f}% diff) {mark}")

print("\nFactor sweep (NO rfr):")
for ppyr in [2190, 4380, 5256, 6480, 8766, 17532, 26298, 35064]:
    val = m / s * ppyr**0.5
    diff = abs(val - TV_SHARPE) / TV_SHARPE * 100
    mark = "[OK]" if diff < 2 else ("[~~]" if diff < 10 else "")
    print(f"  sqrt({ppyr:6d}): sharpe={val:.4f}  ({diff:.2f}% diff) {mark}")

# ── Find EXACT factor ────────────────────────────────────────────────────────
print("\nFinding exact annualization factor for TV 0.895...")


def f_rfr(x):
    return (m - 0.02 / x) / s * x**0.5 - TV_SHARPE


def f_norfr(x):
    return m / s * x**0.5 - TV_SHARPE


try:
    x_rfr = brentq(f_rfr, 100, 1e8)
    print(f"  With rfr:    factor={x_rfr:.1f}  sqrt={x_rfr**0.5:.4f}  ppyr={x_rfr:.1f}")
    # What frequency is this? 15-min bars per year = 365.25 * 24 * 4 = 35064
    # Hourly: 8766, Daily: 365.25
    print("  Comparison: 8766 (hourly), 35064 (15min), 365.25 (daily)")
except Exception as e:
    print(f"  Could not solve with rfr: {e}")

try:
    x_norfr = brentq(f_norfr, 100, 1e8)
    print(f"  No rfr:      factor={x_norfr:.1f}  sqrt={x_norfr**0.5:.4f}  ppyr={x_norfr:.1f}")
except Exception as e:
    print(f"  Could not solve no rfr: {e}")

# ── Try using daily-resampled returns ────────────────────────────────────────
print("\n" + "=" * 65)
print("DAILY-RESAMPLED RETURNS")
print("=" * 65)
daily_eq = ec_series.resample("D").last().ffill()
daily_r = daily_eq.pct_change().dropna().values
daily_r = daily_r[np.isfinite(daily_r)]
dm = np.mean(daily_r)
ds = np.std(daily_r, ddof=1)
print(f"Daily return count: {len(daily_r)}, Mean: {dm:.8f}, Std: {ds:.8f}")

for ppyr in [252, 365, 365.25]:
    rfr_p = 0.02 / ppyr
    val = (dm - rfr_p) / ds * ppyr**0.5
    diff = abs(val - TV_SHARPE) / TV_SHARPE * 100
    mark = "[OK]" if diff < 2 else ("[~~]" if diff < 10 else "")
    print(f"  Daily sqrt({ppyr}): sharpe={val:.4f}  ({diff:.2f}% diff) {mark}")

# no rfr
for ppyr in [252, 365, 365.25]:
    val = dm / ds * ppyr**0.5
    diff = abs(val - TV_SHARPE) / TV_SHARPE * 100
    mark = "[OK]" if diff < 2 else ("[~~]" if diff < 10 else "")
    print(f"  Daily sqrt({ppyr}) no rfr: sharpe={val:.4f}  ({diff:.2f}% diff) {mark}")


# What factor solves for daily?
def f_daily_rfr(x):
    return (dm - 0.02 / x) / ds * x**0.5 - TV_SHARPE


def f_daily_norfr(x):
    return dm / ds * x**0.5 - TV_SHARPE


try:
    x_d = brentq(f_daily_rfr, 1, 1e6)
    print(f"\n  Daily exact factor (rfr): {x_d:.2f}  (365.25 days/yr or {x_d:.2f}?)")
except Exception as e:
    print(f"  Daily exact factor (rfr) failed: {e}")

try:
    x_d2 = brentq(f_daily_norfr, 1, 1e6)
    print(f"  Daily exact factor (no rfr): {x_d2:.2f}")
except Exception as e:
    print(f"  Daily exact factor (no rfr) failed: {e}")

# ── Non-zero bar returns (only bars where equity changed) ────────────────────
print("\n" + "=" * 65)
print("NON-ZERO BAR RETURNS (active bars only)")
print("=" * 65)
nonzero_r = bar_r[bar_r != 0.0]
nz_m = np.mean(nonzero_r)
nz_s = np.std(nonzero_r, ddof=1)
years_val = ((_ts_idx[-1] - _ts_idx[0]).total_seconds()) / (365.25 * 24 * 3600)
ppyr_nz = len(nonzero_r) / years_val
print(f"Non-zero bars: {len(nonzero_r)} of {len(bar_r)}, ppyr={ppyr_nz:.1f}")

for ppyr in [ppyr_nz, 8766, 35064]:
    rfr_p = 0.02 / ppyr
    val = (nz_m - rfr_p) / nz_s * ppyr**0.5
    diff = abs(val - TV_SHARPE) / TV_SHARPE * 100
    mark = "[OK]" if diff < 2 else ("[~~]" if diff < 10 else "")
    print(f"  ppyr={ppyr:.0f}: sharpe={val:.4f}  ({diff:.2f}% diff) {mark}")
