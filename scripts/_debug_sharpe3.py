"""
Debug Sharpe ratio using TV's documented formula:
SR = (MR - RFR) / SD * sqrt(12)
Where:
- MR = average MONTHLY return  (TV docs: "MR is the average return for a monthly trading period")
- RFR = 2% annually = 2/12 = 0.1667% per month
- SD = standard deviation of monthly returns (ddof=1)
"""

import datetime as dt
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

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
TV_SORTINO = 16.708

# Load strategy
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

# Load OHLCV
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

# Run backtest
engine = BacktestEngine()
result = engine.run(cfg, df, custom_strategy=adapter)

ec = result.equity_curve
equity_arr = np.array(ec.equity) if ec is not None else None
timestamps = ec.timestamps if ec is not None else None

print(f"Equity array: {len(equity_arr) if equity_arr is not None else 'N/A'} elements")
print(f"Timestamps: {len(timestamps) if timestamps is not None else 'N/A'} elements")
print(f"Engine sharpe_ratio: {result.metrics.sharpe_ratio:.4f}  (TV: {TV_SHARPE})")
print(f"Engine sortino_ratio: {result.metrics.sortino_ratio:.4f}  (TV: {TV_SORTINO})")

if equity_arr is not None and timestamps is not None:
    _ts_idx = pd.DatetimeIndex(timestamps)
    ec_series = pd.Series(equity_arr, index=_ts_idx)

    print(f"\nEquity: start={equity_arr[0]:.2f}, end={equity_arr[-1]:.2f}")
    print(f"Period: {_ts_idx[0].date()} to {_ts_idx[-1].date()}")

    rfr_annual = 0.02

    # ── MONTHLY Sharpe (TV documented: MR = monthly average return) ──────────
    print("\n" + "=" * 65)
    print("MONTHLY SHARPE (TV docs formula)")
    print("=" * 65)

    rfr_monthly = rfr_annual / 12

    monthly_eq_me = ec_series.resample("ME").last().ffill()
    monthly_r_me = monthly_eq_me.pct_change().dropna()
    mr_me = monthly_r_me.mean()
    sd_me = monthly_r_me.std(ddof=1)
    sharpe_me = (mr_me - rfr_monthly) / sd_me * np.sqrt(12)

    print(f"\nMonth-end (ME) periods: {len(monthly_r_me)}")
    print(f"Monthly returns: {[f'{x * 100:.3f}%' for x in monthly_r_me.values]}")
    print(f"Monthly mean: {mr_me * 100:.4f}%, std(ddof=1): {sd_me * 100:.4f}%")
    print(f"Sharpe (ME, rfr=2%, sqrt12): {sharpe_me:.4f}  (TV: {TV_SHARPE})")
    diff_me = abs(sharpe_me - TV_SHARPE) / TV_SHARPE * 100
    print(f"Diff from TV: {diff_me:.2f}%")

    sharpe_me_norfr = mr_me / sd_me * np.sqrt(12)
    print(f"Sharpe (ME, rfr=0%, sqrt12): {sharpe_me_norfr:.4f}")

    # ddof=0
    sd_me_pop = monthly_r_me.std(ddof=0)
    sharpe_me_pop = (mr_me - rfr_monthly) / sd_me_pop * np.sqrt(12)
    print(f"Sharpe (ME, rfr=2%, ddof=0, sqrt12): {sharpe_me_pop:.4f}")

    # MS (month-start)
    monthly_eq_ms = ec_series.resample("MS").first()
    monthly_r_ms = monthly_eq_ms.pct_change().dropna()
    mr_ms = monthly_r_ms.mean()
    sd_ms = monthly_r_ms.std(ddof=1)
    sharpe_ms = (mr_ms - rfr_monthly) / sd_ms * np.sqrt(12)
    print(f"\nMonth-start (MS) periods: {len(monthly_r_ms)}")
    print(f"Sharpe (MS, rfr=2%, sqrt12): {sharpe_ms:.4f}  (TV: {TV_SHARPE})")

    # ── MONTHLY Sortino check ─────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("MONTHLY SORTINO")
    print("=" * 65)
    neg_r_me = np.minimum(0.0, monthly_r_me.values)
    dd_me = np.sqrt(np.sum(neg_r_me**2) / len(monthly_r_me))
    if dd_me > 1e-10:
        sortino_me = (mr_me - rfr_monthly) / dd_me * np.sqrt(12)
        print(f"Sortino (ME, rfr=2%, sqrt12): {sortino_me:.4f}  (TV: {TV_SORTINO})")
    else:
        print("No negative monthly returns => Sortino = inf")

    # ── Weekly check ──────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("WEEKLY (for comparison)")
    print("=" * 65)
    rfr_weekly = rfr_annual / 52
    weekly_eq = ec_series.resample("W-SUN").last().ffill()
    weekly_r = weekly_eq.pct_change().dropna()
    wm = weekly_r.mean()
    wsd = weekly_r.std(ddof=1)
    wneg = np.minimum(0.0, weekly_r.values)
    wdd = np.sqrt(np.sum(wneg**2) / len(weekly_r))

    sharpe_w52 = (wm - rfr_weekly) / wsd * np.sqrt(52)
    sharpe_w57 = (wm - rfr_weekly) / wsd * np.sqrt(57.2)
    if wdd > 1e-10:
        sortino_w57 = (wm - rfr_weekly) / wdd * np.sqrt(57.2)
        print(f"Weekly Sortino (rfr=2%, sqrt57.2): {sortino_w57:.4f}  (TV: {TV_SORTINO})")
    print(f"Weekly Sharpe (rfr=2%, sqrt52): {sharpe_w52:.4f}  (TV: {TV_SHARPE})")
    print(f"Weekly Sharpe (rfr=2%, sqrt57.2): {sharpe_w57:.4f}")

    # ── Factor sweep ─────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("MONTHLY FACTOR SWEEP to find TV 0.895")
    print("=" * 65)
    for fac in [10, 11, 12, 13, 14, 15]:
        s = (mr_me - rfr_annual / fac) / sd_me * np.sqrt(fac)
        diff = abs(s - TV_SHARPE) / TV_SHARPE * 100
        mark = "[OK]" if diff < 2 else ""
        print(f"  Monthly sqrt({fac:2d}) rfr=annual/{fac:2d}: {s:.4f}  ({diff:.2f}% diff) {mark}")

    # Also try weekly but with same rfr structure
    print("\nWeekly factor sweep:")
    for fac_w in [48, 50, 52, 54, 57.2]:
        s = (wm - rfr_annual / fac_w) / wsd * np.sqrt(fac_w)
        diff = abs(s - TV_SHARPE) / TV_SHARPE * 100
        mark = "[OK]" if diff < 2 else ""
        print(f"  Weekly sqrt({fac_w}): {s:.4f}  ({diff:.2f}% diff) {mark}")

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("SUMMARY")
    print("=" * 65)
    candidates = [
        ("Monthly ME (rfr=2%, sqrt12)", sharpe_me),
        ("Monthly ME (rfr=0%, sqrt12)", sharpe_me_norfr),
        ("Monthly ME (rfr=2%, ddof=0, sqrt12)", sharpe_me_pop),
        ("Monthly MS (rfr=2%, sqrt12)", sharpe_ms),
        ("Weekly W-SUN (rfr=2%, sqrt52)", sharpe_w52),
        ("Weekly W-SUN (rfr=2%, sqrt57.2)", sharpe_w57),
        ("Engine (bar-by-bar sqrt8766)", result.metrics.sharpe_ratio),
    ]
    for name, val in candidates:
        diff = abs(val - TV_SHARPE) / TV_SHARPE * 100
        marker = "[OK]" if diff < 3.0 else ("[~~]" if diff < 10.0 else "[!!]")
        print(f"{marker} {name:50s}: {val:.4f}  ({diff:.2f}% diff from TV {TV_SHARPE})")
