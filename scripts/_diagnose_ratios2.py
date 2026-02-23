"""
Диагностика Sharpe/Sortino v2 — исчерпывающий поиск.
TV: Sharpe=0.895, Sortino=16.708
"""

import datetime as dt
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///data.sqlite3")

from loguru import logger

logger.remove()

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB = "data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"
TV_SHARPE = 0.895
TV_SORTINO = 16.708

conn = sqlite3.connect(DB)
cur = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,))
cols = [d[0] for d in cur.description]
row = cur.fetchone()
conn.close()
strat = dict(zip(cols, row, strict=False))

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
    "SELECT open_time, open_price as open, high_price as high, low_price as low, "
    "close_price as close, volume FROM bybit_kline_audit "
    "WHERE symbol=? AND interval=? AND market_type=? AND open_time>=? AND open_time<=? ORDER BY open_time ASC",
    conn2,
    params=("BTCUSDT", "15", "linear", start_ms, end_ms),
)
conn2.close()
df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df = df.set_index("timestamp").drop(columns=["open_time"])

params = json.loads(strat["parameters"])
cfg = BacktestConfig(
    symbol="BTCUSDT",
    interval="15",
    start_date=dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
    end_date=dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC),
    initial_capital=10000.0,
    commission_value=float(params.get("_commission", 0.0007)),
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
m = result.metrics
all_trades = result.trades
closed = [t for t in all_trades if not getattr(t, "is_open", False)]
ec = result.equity_curve
equity_arr = np.array(ec.equity) if ec and ec.equity else None
ts_list = ec.timestamps if ec and ec.timestamps else []

print(f"\n{'=' * 60}")
print(f"Current: Sharpe={m.sharpe_ratio:.4f}  Sortino={m.sortino_ratio:.4f}")
print(f"TV:      Sharpe={TV_SHARPE}           Sortino={TV_SORTINO}")
print(f"{'=' * 60}\n")

if equity_arr is None:
    print("No equity curve!")
    sys.exit(1)

# ─── Build all return series ─────────────────────────────────────────────────

# 1. Bar-by-bar returns (all bars)
bar_returns = np.diff(equity_arr) / equity_arr[:-1]
bar_returns = np.nan_to_num(bar_returns, nan=0.0, posinf=0.0, neginf=0.0)

# 2. Bar-by-bar returns (NON-ZERO only — bars in position)
nonzero_bar = bar_returns[bar_returns != 0.0]

# 3. Trade-by-trade % returns (pnl_pct/100)
trade_returns = np.array([t.pnl_pct / 100.0 for t in closed])

# 4. Equity resampled
eq_df = pd.DataFrame({"equity": equity_arr}, index=pd.to_datetime(ts_list))
weekly_r = eq_df["equity"].resample("W").last().pct_change().dropna().values
monthly_r = eq_df["equity"].resample("ME").last().pct_change().dropna().values
daily_r = eq_df["equity"].resample("D").last().pct_change().dropna().values

print(
    f"Samples: bar={len(bar_returns)}, nonzero={len(nonzero_bar)}, "
    f"trade={len(trade_returns)}, weekly={len(weekly_r)}, "
    f"monthly={len(monthly_r)}, daily={len(daily_r)}"
)


def sharpe(r, rfr_annual=0.02, ppyr=None):
    """Standard Sharpe: (mean - rfr_period) / std * sqrt(ppyr)"""
    if len(r) < 2:
        return float("nan")
    m, s = np.mean(r), np.std(r, ddof=1)
    if s < 1e-12:
        return float("inf") if m > 0 else float("nan")
    if ppyr is None:
        return m / s
    rfr = rfr_annual / ppyr
    return (m - rfr) / s * np.sqrt(ppyr)


def sortino(r, rfr_annual=0.0, ppyr=None):
    """Sortino: (mean - MAR) / downside_dev * sqrt(ppyr)
    TV uses sum(min(0,r)^2)/N for downside variance (divide by N, not neg count)
    """
    if len(r) < 2:
        return float("nan")
    m = np.mean(r)
    neg = np.minimum(0.0, r)
    dd_var = np.sum(neg**2) / len(r)
    dd = np.sqrt(dd_var)
    if dd < 1e-12:
        return float("inf") if m > 0 else float("nan")
    if ppyr is None:
        return m / dd
    return (m - rfr_annual / ppyr) / dd * np.sqrt(ppyr)


def sortino_std(r, rfr_annual=0.0, ppyr=None):
    """Sortino with std of negative returns (ddof=1) instead of sum/N"""
    if len(r) < 2:
        return float("nan")
    m = np.mean(r)
    negs = r[r < 0]
    if len(negs) < 1:
        return float("inf") if m > 0 else float("nan")
    dd = np.std(negs, ddof=1)
    if dd < 1e-12:
        return float("nan")
    if ppyr is None:
        return m / dd
    return (m - rfr_annual / ppyr) / dd * np.sqrt(ppyr)


print(f"\n{'─' * 60}")
print(f"{'Method':<50} {'Sharpe':>8} {'Sortino':>9}")
print(f"{'─' * 60}")
print(f"{'TV TARGET':<50} {TV_SHARPE:>8.4f} {TV_SORTINO:>9.4f}")
print(f"{'─' * 60}")


def row(label, r, rfr=0.02, ppyr=None, sortino_fn=sortino):
    sh = sharpe(r, rfr, ppyr)
    so = sortino_fn(r, 0.0, ppyr)
    marker_sh = "  <== MATCH!" if abs(sh - TV_SHARPE) < 0.05 else ""
    marker_so = "  <== MATCH!" if abs(so - TV_SORTINO) < 0.1 else ""
    print(f"{label:<50} {sh:>8.4f}{marker_sh}")
    print(f"{'':50} {'Sortino:':>8} {so:>9.4f}{marker_so}")
    print()


# ── Bar-by-bar ────────────────────────────────────────────────────────────────
row("bar all, rfr=2%, ppyr=8766 [current]", bar_returns, 0.02, 8766)
row("bar all, rfr=0%, ppyr=8766", bar_returns, 0.0, 8766)
row("bar all, rfr=2%, ppyr=35040 (15min)", bar_returns, 0.02, 35040)
row("bar all, rfr=0%, ppyr=35040", bar_returns, 0.0, 35040)
row("bar all, no annualization", bar_returns, 0.0, None)

# ── Bar nonzero ───────────────────────────────────────────────────────────────
row("bar nonzero, rfr=2%, ppyr=8766", nonzero_bar, 0.02, 8766)
row("bar nonzero, rfr=0%, ppyr=8766", nonzero_bar, 0.0, 8766)
row("bar nonzero, rfr=2%, ppyr=35040", nonzero_bar, 0.02, 35040)
row("bar nonzero, no annualization", nonzero_bar, 0.0, None)

# ── Trade returns ─────────────────────────────────────────────────────────────
trades_per_year = len(trade_returns) / (89 / 365.25)  # backtest ~89 days
row(f"trade, rfr=2%, ppyr=trades/yr={trades_per_year:.0f}", trade_returns, 0.02, trades_per_year)
row(f"trade, rfr=0%, ppyr={trades_per_year:.0f}", trade_returns, 0.0, trades_per_year)
row("trade, rfr=2%, ppyr=52", trade_returns, 0.02, 52)
row("trade, rfr=0%, ppyr=52", trade_returns, 0.0, 52)
row("trade, rfr=2%, ppyr=12", trade_returns, 0.02, 12)
row("trade, rfr=0%, ppyr=12", trade_returns, 0.0, 12)
row("trade, no annualization", trade_returns, 0.0, None)

# ── Weekly equity ─────────────────────────────────────────────────────────────
row("weekly, rfr=2%, ppyr=52", weekly_r, 0.02, 52)
row("weekly, rfr=0%, ppyr=52", weekly_r, 0.0, 52)
row("weekly, rfr=2%, ppyr=52, sortino_std", weekly_r, 0.02, 52, sortino_std)
row("weekly, rfr=0%, ppyr=52, sortino_std", weekly_r, 0.0, 52, sortino_std)
row("weekly, no annualization", weekly_r, 0.0, None)

# ── Monthly equity ────────────────────────────────────────────────────────────
row("monthly, rfr=2%, ppyr=12", monthly_r, 0.02, 12)
row("monthly, rfr=0%, ppyr=12", monthly_r, 0.0, 12)
row("monthly, no annualization", monthly_r, 0.0, None)

# ── Daily equity ──────────────────────────────────────────────────────────────
row("daily, rfr=2%, ppyr=365", daily_r, 0.02, 365)
row("daily, rfr=0%, ppyr=365", daily_r, 0.0, 365)
row("daily, no annualization", daily_r, 0.0, None)

# ─── Special searches ────────────────────────────────────────────────────────
print(f"\n{'=' * 60}")
print("SPECIAL: TV might Sharpe = CAGR / annualized_vol")
print(f"{'=' * 60}")
cagr_pct = m.cagr  # e.g. 15.87
# annualized vol from bar_returns (hourly):
ann_vol_hourly = np.std(bar_returns, ddof=1) * np.sqrt(8766) * 100
ann_vol_15min = np.std(bar_returns, ddof=1) * np.sqrt(35040) * 100
ann_vol_weekly = np.std(weekly_r, ddof=1) * np.sqrt(52) * 100
ann_vol_daily = np.std(daily_r, ddof=1) * np.sqrt(365) * 100
print(f"CAGR: {cagr_pct:.4f}%")
print(f"Annualized vol (hourly): {ann_vol_hourly:.4f}%  → Sharpe=CAGR/vol = {cagr_pct / ann_vol_hourly:.4f}")
print(f"Annualized vol (15min):  {ann_vol_15min:.4f}%  → Sharpe=CAGR/vol = {cagr_pct / ann_vol_15min:.4f}")
print(f"Annualized vol (weekly): {ann_vol_weekly:.4f}%  → Sharpe=CAGR/vol = {cagr_pct / ann_vol_weekly:.4f}")
print(f"Annualized vol (daily):  {ann_vol_daily:.4f}%  → Sharpe=CAGR/vol = {cagr_pct / ann_vol_daily:.4f}")

# TV Sharpe = 0.895, find what vol gives CAGR/vol = 0.895
needed_vol = cagr_pct / TV_SHARPE
print(f"\nFor TV Sharpe=0.895, needed vol = {needed_vol:.4f}%")

print(f"\n{'=' * 60}")
print("SPECIAL: Try different ddof for Sortino")
print(f"{'=' * 60}")
# weekly with ddof=0 vs ddof=1 in downside_variance
wr = weekly_r
mean_wr = np.mean(wr)
neg_wr = np.minimum(0.0, wr)
dd_var_N = np.sum(neg_wr**2) / len(wr)  # div by N
dd_var_N1 = np.sum(neg_wr**2) / (len(wr) - 1)  # div by N-1
dd_N = np.sqrt(dd_var_N)
dd_N1 = np.sqrt(dd_var_N1)
so_N = mean_wr / dd_N * np.sqrt(52)
so_N1 = mean_wr / dd_N1 * np.sqrt(52)
print(f"Weekly Sortino (div N={len(wr)}) * sqrt(52) = {so_N:.4f}  (TV: {TV_SORTINO})")
print(f"Weekly Sortino (div N-1={len(wr) - 1}) * sqrt(52) = {so_N1:.4f}  (TV: {TV_SORTINO})")

# ─── Brute-force search: find ppyr for Sharpe=0.895 using bar_returns ─────────
print(f"\n{'=' * 60}")
print("BRUTE FORCE: find ppyr for Sharpe=0.895 using bar_returns (rfr=0)")
print(f"{'=' * 60}")
m_r, s_r = np.mean(bar_returns), np.std(bar_returns, ddof=1)
# sh = m/s * sqrt(ppyr) = 0.895
# ppyr = (0.895 * s / m)^2
if m_r > 0 and s_r > 0:
    needed_ppyr_sh = (TV_SHARPE * s_r / m_r) ** 2
    print(f"bar_returns: For Sharpe=0.895 with rfr=0: ppyr = {needed_ppyr_sh:.1f}")
    print(f"  (sqrt(ppyr) = {np.sqrt(needed_ppyr_sh):.2f})")

m_r2, s_r2 = np.mean(bar_returns), np.std(bar_returns, ddof=1)
rfr2 = 0.02
for ppyr_test in [8766, 35040, 365, 52, 12, 4, 1]:
    sh2 = (m_r2 - rfr2 / ppyr_test) / s_r2 * np.sqrt(ppyr_test)
    print(f"  rfr=2%, ppyr={ppyr_test}: Sharpe={sh2:.4f}")

# ─── Brute-force: find ppyr for Sortino=16.708 using bar_returns ─────────────
print(f"\n{'=' * 60}")
print("BRUTE FORCE: find ppyr for Sortino=16.708 using bar_returns (rfr=0)")
print(f"{'=' * 60}")
neg_bar = np.minimum(0.0, bar_returns)
dd_bar = np.sqrt(np.sum(neg_bar**2) / len(bar_returns))
if dd_bar > 0 and np.mean(bar_returns) > 0:
    needed_ppyr_so = (TV_SORTINO * dd_bar / np.mean(bar_returns)) ** 2
    print(f"bar_returns: For Sortino=16.708 with rfr=0: ppyr = {needed_ppyr_so:.1f}")
    print(f"  (sqrt(ppyr) = {np.sqrt(needed_ppyr_so):.2f})")

# ─── CAGR-based approach for Sortino ─────────────────────────────────────────
print(f"\n{'=' * 60}")
print("SPECIAL: TV Sortino = CAGR / Downside-Vol")
print(f"{'=' * 60}")
# downside vol from bar returns
neg_bar2 = np.minimum(0.0, bar_returns)
# annualized downside vol (hourly) = sqrt(sum(neg^2)/N) * sqrt(8766)
dd_ann_hourly = np.sqrt(np.sum(neg_bar2**2) / len(bar_returns)) * np.sqrt(8766) * 100
dd_ann_15min = np.sqrt(np.sum(neg_bar2**2) / len(bar_returns)) * np.sqrt(35040) * 100
dd_ann_weekly = np.sqrt(np.sum(np.minimum(0.0, weekly_r) ** 2) / len(weekly_r)) * np.sqrt(52) * 100
print(f"CAGR: {cagr_pct:.4f}%")
print(f"Downside vol (hourly): {dd_ann_hourly:.4f}%  → Sortino=CAGR/dd_vol = {cagr_pct / dd_ann_hourly:.4f}")
print(f"Downside vol (15min):  {dd_ann_15min:.4f}%  → Sortino=CAGR/dd_vol = {cagr_pct / dd_ann_15min:.4f}")
print(f"Downside vol (weekly): {dd_ann_weekly:.4f}%  → Sortino=CAGR/dd_vol = {cagr_pct / dd_ann_weekly:.4f}")

needed_dd_vol = cagr_pct / TV_SORTINO
print(f"\nFor TV Sortino=16.708, needed downside vol = {needed_dd_vol:.4f}%")
print(f"Ratio dd_ann_weekly / needed = {dd_ann_weekly / needed_dd_vol:.4f}")

# ─── Weekly with different start/end alignment ───────────────────────────────
print(f"\n{'=' * 60}")
print("SPECIAL: Weekly resampling variations")
print(f"{'=' * 60}")
for freq in ["W-MON", "W-SUN", "W-SAT", "W"]:
    wr_v = eq_df["equity"].resample(freq).last().pct_change().dropna().values
    if len(wr_v) < 2:
        continue
    m_v = np.mean(wr_v)
    s_v = np.std(wr_v, ddof=1)
    neg_v = np.minimum(0.0, wr_v)
    dd_v = np.sqrt(np.sum(neg_v**2) / len(wr_v))
    sh_v = (m_v / s_v * np.sqrt(52)) if s_v > 0 else 0
    so_v = (m_v / dd_v * np.sqrt(52)) if dd_v > 0 else float("inf")
    print(f"  {freq}: N={len(wr_v)}, Sharpe*√52={sh_v:.4f}, Sortino*√52={so_v:.4f}")
