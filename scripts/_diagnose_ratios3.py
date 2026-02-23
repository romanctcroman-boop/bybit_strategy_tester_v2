"""
Diagnose Sharpe/Sortino - Round 3
Focus on:
1. Closed-trade equity returns
2. TV Pine Script exact formula replication
3. Margin hypothesis: TV margin = qty_in_BTC * entry_price
4. Various annualization factors
"""

import datetime as dt
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "d:\\bybit_strategy_tester_v2")
os.environ.setdefault("DATABASE_URL", "sqlite:///data.sqlite3")
from loguru import logger

logger.remove()

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB = "d:\\bybit_strategy_tester_v2\\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"


def to_utc_ts(raw) -> pd.Timestamp:
    """Convert exit_time (ms int, aware/naive Timestamp, or str) to UTC Timestamp."""
    if isinstance(raw, (int, float)):
        return pd.Timestamp(int(raw), unit="ms", tz="UTC")
    if isinstance(raw, pd.Timestamp):
        return raw.tz_convert("UTC") if raw.tzinfo else raw.tz_localize("UTC")
    ts_tmp = pd.Timestamp(str(raw))
    return ts_tmp.tz_localize("UTC") if ts_tmp.tzinfo is None else ts_tmp.tz_convert("UTC")


TV_SHARPE = 0.895
TV_SORTINO = 16.708
TV_CAGR = 16.22  # %
TV_AVG_MARGIN = 852.53
TV_MAX_MARGIN = 1033.35
TV_ACCT_SIZE = 1180.34
TV_MAX_DD_INTRABAR = 146.99
TV_MAX_RUNUP_INTRABAR = 537.82

# ─── Load strategy ───────────────────────────────────────────────────────────
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

closed = sorted(
    [t for t in result.trades if not getattr(t, "is_open", False)],
    key=lambda x: x.exit_time if x.exit_time else 0,
)
open_trades = [t for t in result.trades if getattr(t, "is_open", False)]

print(f"Closed trades: {len(closed)}, Open trades: {len(open_trades)}")
print()

# ─── 1. Margin Analysis ───────────────────────────────────────────────────────
print("=" * 60)
print("MARGIN ANALYSIS")
print("=" * 60)
margins_notional = []
margins_divided = []
for t in closed:
    size = getattr(t, "size", 0) or 0
    ep = getattr(t, "entry_price", 0) or 0
    lev = cfg.leverage
    # Hypothesis A: TV margin = qty * entry_price (full notional)
    mA = size * ep
    # Hypothesis B: TV margin = qty * entry_price / leverage
    mB = size * ep / lev
    # Hypothesis C: position_size_pct * equity_at_entry (need equity tracking)
    margins_notional.append(mA)
    margins_divided.append(mB)

avg_notional = np.mean(margins_notional) if margins_notional else 0
max_notional = np.max(margins_notional) if margins_notional else 0
avg_divided = np.mean(margins_divided) if margins_divided else 0
max_divided = np.max(margins_divided) if margins_divided else 0

print("Hypothesis A (qty * entry_price = full notional):")
print(f"  avg = {avg_notional:.2f}  (TV: {TV_AVG_MARGIN})")
print(f"  max = {max_notional:.2f}  (TV: {TV_MAX_MARGIN})")
print("Hypothesis B (qty * entry_price / leverage):")
print(f"  avg = {avg_divided:.2f}  (TV: {TV_AVG_MARGIN})")
print(f"  max = {max_divided:.2f}  (TV: {TV_MAX_MARGIN})")

# Show a few samples
print("\nSample trades (size, entry_price, qty*ep, qty*ep/lev):")
for t in closed[:5]:
    sz = getattr(t, "size", 0) or 0
    ep = getattr(t, "entry_price", 0) or 0
    print(f"  size={sz:.6f}, entry={ep:.2f}, notional={sz * ep:.2f}, margin={sz * ep / cfg.leverage:.2f}")

print()

# ─── 2. Equity Curve Analysis ─────────────────────────────────────────────────
print("=" * 60)
print("EQUITY CURVE & RETURN SERIES")
print("=" * 60)

init_cap = 10000.0
eq = init_cap
trade_eq = [init_cap]
trade_times = [None]
for t in closed:
    eq += t.pnl
    trade_eq.append(eq)
    trade_times.append(t.exit_time)

trade_eq = np.array(trade_eq)
trade_returns = np.diff(trade_eq) / trade_eq[:-1]
N_trades = len(trade_returns)

# Bar-by-bar equity (build from trade list)
# Build bar equity curve using the engine's equity_curve if available
bar_returns_series = None
if hasattr(result, "equity_curve") and result.equity_curve is not None:
    ec = result.equity_curve
    if hasattr(ec, "__len__") and len(ec) > 0:
        ec_arr = np.array(ec)
        bar_returns_series = np.diff(ec_arr) / ec_arr[:-1]
        bar_returns_series = np.nan_to_num(bar_returns_series)
        print(f"Bar equity curve found: N={len(ec_arr)} bars, returns N={len(bar_returns_series)}")

print(f"Closed-trade equity returns: N={N_trades}")
print(f"  Equity range: {trade_eq.min():.2f} to {trade_eq.max():.2f}")
print(f"  Mean return: {np.mean(trade_returns):.6f}")
print(f"  Std return:  {np.std(trade_returns, ddof=1):.6f}")
print()

# ─── 3. Sharpe/Sortino from trade returns ─────────────────────────────────────
print("=" * 60)
print("SHARPE / SORTINO FROM TRADE RETURNS")
print("=" * 60)

tr = trade_returns
m = np.mean(tr)
s_ddof1 = np.std(tr, ddof=1)
s_ddof0 = np.std(tr, ddof=0)
neg = np.minimum(0.0, tr)
# Downside deviation (TV: divide by total N)
dd_total = np.sqrt(np.sum(neg**2) / len(tr))
# Downside deviation (divide by N_neg)
n_neg = np.sum(neg < 0)
dd_neg = np.sqrt(np.sum(neg**2) / n_neg) if n_neg > 0 else 0.0
# Downside deviation (divide by N-1)
dd_ddof1 = np.sqrt(np.sum(neg**2) / (len(tr) - 1)) if len(tr) > 1 else 0.0

print(f"Trade returns: N={len(tr)}, mean={m:.6f}")
print(f"  std(ddof=1)={s_ddof1:.6f}, std(ddof=0)={s_ddof0:.6f}")
print(f"  dd(total N)={dd_total:.6f}, dd(N_neg={n_neg})={dd_neg:.6f}, dd(ddof1)={dd_ddof1:.6f}")
print()

# Backtest duration
n_days = (dt.datetime(2026, 2, 23) - dt.datetime(2025, 11, 1)).days  # 114 days
n_years = n_days / 365.25
trades_per_year = N_trades / n_years

print(f"Backtest: {n_days} days = {n_years:.4f} years")
print(f"Trades per year (annualized): {trades_per_year:.2f}")
print()

annualization_factors = [
    ("sqrt(N_trades)", np.sqrt(N_trades)),
    ("sqrt(trades_per_year)", np.sqrt(trades_per_year)),
    ("sqrt(52) = weekly", np.sqrt(52)),
    ("sqrt(365)", np.sqrt(365)),
    ("sqrt(252) = business days", np.sqrt(252)),
    ("sqrt(12) = monthly", np.sqrt(12)),
    ("sqrt(4) = quarterly", np.sqrt(4)),
]

print("Sharpe from trade returns (rfr=0):")
for name, ann in annualization_factors:
    if s_ddof1 > 0:
        sh = m / s_ddof1 * ann
        print(f"  [{name:35s}] = {sh:.4f}  (TV: {TV_SHARPE})")

print()
print("Sharpe from trade returns (rfr=2%, annualized):")
for name, ann in annualization_factors:
    if s_ddof1 > 0:
        rfr_per_trade = 0.02 / (ann**2)
        sh = (m - rfr_per_trade) / s_ddof1 * ann
        print(f"  [{name:35s}] = {sh:.4f}  (TV: {TV_SHARPE})")

print()
print("Sortino from trade returns (rfr=0):")
for name, ann in annualization_factors:
    so_total = m / dd_total * ann if dd_total > 0 else float("inf")
    so_neg = m / dd_neg * ann if dd_neg > 0 else float("inf")
    print(f"  [{name:35s}] dd_total={so_total:.4f}, dd_neg={so_neg:.4f}  (TV: {TV_SORTINO})")

print()

# ─── 4. Brute-force ppyr for trade returns ────────────────────────────────────
print("=" * 60)
print("BRUTE FORCE ppyr FOR TRADE RETURNS (rfr=0)")
print("=" * 60)
if s_ddof1 > 0:
    ppyr_sharpe_trade = (TV_SHARPE / (m / s_ddof1)) ** 2
    print(
        f"Trade returns: For Sharpe={TV_SHARPE} with rfr=0: ppyr={ppyr_sharpe_trade:.1f} (sqrt={np.sqrt(ppyr_sharpe_trade):.3f})"
    )
    print(f"  Note: sqrt(ppyr_sharpe_trade) = {np.sqrt(ppyr_sharpe_trade):.4f}")
    print(f"  Note: trades_per_year = {trades_per_year:.2f}")
    print(f"  Note: N_trades = {N_trades}")

if dd_total > 0:
    ppyr_sortino_trade = (TV_SORTINO / (m / dd_total)) ** 2
    print(
        f"Trade returns: For Sortino={TV_SORTINO} with rfr=0: ppyr={ppyr_sortino_trade:.1f} (sqrt={np.sqrt(ppyr_sortino_trade):.3f})"
    )
    print(f"  Note: sqrt(ppyr_sortino_trade) = {np.sqrt(ppyr_sortino_trade):.4f}")

print()

# ─── 5. TV Pine Script exact formula attempt ──────────────────────────────────
print("=" * 60)
print("TV PINE SCRIPT EXACT FORMULA")
print("=" * 60)

# TV Pine Script strategy.sharpe_ratio formula (from Pine Script v5 docs):
# strategy.sharpe_ratio = (strategy.net_profit - strategy.gross_loss) / strategy.max_drawdown
# Actually that's NOT the formula. TV uses:
# strategy.performance.sharpe_ratio = sqrt(252) * mean(daily_returns) / stdev(daily_returns)

# Let's build daily equity from trade close times
eq = init_cap
trade_close_equity = {}
for t in closed:
    eq += t.pnl
    if t.exit_time:
        ts = to_utc_ts(t.exit_time).floor("D")
        trade_close_equity[ts] = eq

# Build daily equity curve: carry forward last known equity each day
all_days = pd.date_range(
    start=pd.Timestamp("2025-11-01", tz="UTC"),
    end=pd.Timestamp("2026-02-23", tz="UTC"),
    freq="D",
)
daily_eq = []
last_eq = init_cap
for d in all_days:
    if d in trade_close_equity:
        last_eq = trade_close_equity[d]
    daily_eq.append(last_eq)

daily_eq = np.array(daily_eq)
daily_r = np.diff(daily_eq) / daily_eq[:-1]
daily_r = np.nan_to_num(daily_r)
daily_neg = np.minimum(0.0, daily_r)

d_m = np.mean(daily_r)
d_s = np.std(daily_r, ddof=1)
d_s0 = np.std(daily_r, ddof=0)
d_dd_total = np.sqrt(np.sum(daily_neg**2) / len(daily_r))
d_dd_ddof1 = np.sqrt(np.sum(daily_neg**2) / (len(daily_r) - 1))

print(f"Daily equity returns: N={len(daily_r)}")
print(f"  mean={d_m:.6f}, std(ddof=1)={d_s:.6f}, std(ddof=0)={d_s0:.6f}")
print(f"  dd_total={d_dd_total:.6f}, dd_ddof1={d_dd_ddof1:.6f}")
print()
print("Daily approaches:")
for rfr in [0.0, 0.02]:
    for ppyr in [252, 365, 365.25, 114]:
        if d_s > 0:
            rfr_d = rfr / ppyr
            sh = (d_m - rfr_d) / d_s * np.sqrt(ppyr)
            print(f"  rfr={rfr:.2f}, ppyr={ppyr:.0f}: Sharpe={sh:.4f}")
        if d_dd_total > 0:
            so = d_m / d_dd_total * np.sqrt(ppyr) if ppyr else 0
            print(f"  rfr={rfr:.2f}, ppyr={ppyr:.0f}: Sortino(dd_total)={so:.4f}")

print()

# ─── 6. Weekly equity returns ─────────────────────────────────────────────────
print("=" * 60)
print("WEEKLY EQUITY RETURNS (W-SUN vs W-MON)")
print("=" * 60)

for freq, label in [("W-SUN", "W-SUN (Sun)"), ("W-MON", "W-MON (Mon)"), ("W-SAT", "W-SAT (Sat)")]:
    eq = init_cap
    trade_close_eq_ts = {}
    for t in closed:
        eq += t.pnl
        if t.exit_time:
            ts = to_utc_ts(t.exit_time)
            trade_close_eq_ts[ts] = eq

    # Build bar-by-bar equity DataFrame
    eq_series = pd.Series(init_cap, index=df.index[:1])
    eq = init_cap
    eq_dict = {}
    for t in closed:
        if t.exit_time:
            ts = to_utc_ts(t.exit_time)
            eq += t.pnl
            eq_dict[ts] = eq

    # Resample to weekly
    all_ts = sorted(eq_dict.keys())
    if not all_ts:
        continue

    eq_ts_series = pd.Series(eq_dict)
    eq_ts_series = eq_ts_series.sort_index()

    # Extend with start/end
    eq_full = pd.Series({pd.Timestamp("2025-11-01 00:00:00", tz="UTC"): init_cap, **eq_dict})
    eq_full = eq_full.sort_index()

    # Resample to weekly using last value
    weekly_eq = eq_full.resample(freq).last().ffill()
    weekly_r = weekly_eq.pct_change().dropna()
    w_m = np.mean(weekly_r.values)
    w_s = np.std(weekly_r.values, ddof=1)
    w_s0 = np.std(weekly_r.values, ddof=0)
    w_neg = np.minimum(0.0, weekly_r.values)
    w_dd_total = np.sqrt(np.sum(w_neg**2) / len(weekly_r))
    w_dd_neg = np.sqrt(np.sum(w_neg**2) / np.sum(w_neg < 0)) if np.sum(w_neg < 0) > 0 else 0
    w_dd_ddof1 = np.sqrt(np.sum(w_neg**2) / (len(weekly_r) - 1)) if len(weekly_r) > 1 else 0

    print(f"\n{label}: N={len(weekly_r)}, mean={w_m:.6f}")
    print(f"  std(ddof=1)={w_s:.6f}, std(ddof=0)={w_s0:.6f}")
    print(f"  dd_total={w_dd_total:.6f}, dd_neg={w_dd_neg:.6f}, dd_ddof1={w_dd_ddof1:.6f}")
    for rfr in [0.0, 0.02]:
        for ppyr in [52, 52.18]:
            if w_s > 0:
                rfr_w = rfr / ppyr
                sh = (w_m - rfr_w) / w_s * np.sqrt(ppyr)
                print(f"  rfr={rfr:.2f}, ppyr={ppyr:.2f}: Sharpe(ddof1)={sh:.4f}  (TV:{TV_SHARPE})")
            if w_dd_total > 0:
                so = w_m / w_dd_total * np.sqrt(ppyr)
                print(f"  rfr={rfr:.2f}, ppyr={ppyr:.2f}: Sortino(dd_total)={so:.4f}  (TV:{TV_SORTINO})")
            if w_dd_ddof1 > 0:
                so2 = w_m / w_dd_ddof1 * np.sqrt(ppyr)
                print(f"  rfr={rfr:.2f}, ppyr={ppyr:.2f}: Sortino(ddof1)={so2:.4f}  (TV:{TV_SORTINO})")

print()

# ─── 7. CAGR-based Sortino ─────────────────────────────────────────────────────
print("=" * 60)
print("CAGR-BASED SORTINO")
print("=" * 60)

# Final equity
final_eq = init_cap
for t in closed:
    final_eq += t.pnl

our_cagr = ((final_eq / init_cap) ** (1.0 / n_years) - 1) * 100
print(f"Final equity: {final_eq:.2f}")
print(f"Our CAGR: {our_cagr:.4f}%  (TV: {TV_CAGR}%)")
print()

# Try CAGR / annualized_downside_vol for various return frequencies
for freq, label in [("W-SUN", "Weekly-SUN"), ("D", "Daily")]:
    eq_dict = {}
    eq = init_cap
    for t in closed:
        if t.exit_time:
            ts = to_utc_ts(t.exit_time)
            eq += t.pnl
            eq_dict[ts] = eq

    eq_full = pd.Series({pd.Timestamp("2025-11-01 00:00:00", tz="UTC"): init_cap, **eq_dict})
    eq_full = eq_full.sort_index()
    resampled = eq_full.resample(freq).last().ffill()
    rets = resampled.pct_change().dropna()
    if len(rets) == 0:
        continue

    neg_r = np.minimum(0.0, rets.values)
    # annualized downside vol
    ppyr = 52 if "W" in freq else 365
    dd_total_ann = np.sqrt(np.sum(neg_r**2) / len(rets)) * np.sqrt(ppyr)
    dd_ddof1_ann = (np.sqrt(np.sum(neg_r**2) / (len(rets) - 1)) * np.sqrt(ppyr)) if len(rets) > 1 else 0

    print(f"{label}: N={len(rets)}")
    for cagr_val, cagr_name in [(our_cagr, "our_CAGR"), (TV_CAGR, "TV_CAGR")]:
        if dd_total_ann > 0:
            sortino_cagr = cagr_val / dd_total_ann
            print(
                f"  CAGR={cagr_name}({cagr_val:.4f}%) / dd_ann_total({dd_total_ann:.4f}%) = {sortino_cagr:.4f}  (TV: {TV_SORTINO})"
            )
        if dd_ddof1_ann > 0:
            sortino_cagr2 = cagr_val / dd_ddof1_ann
            print(
                f"  CAGR={cagr_name}({cagr_val:.4f}%) / dd_ann_ddof1({dd_ddof1_ann:.4f}%) = {sortino_cagr2:.4f}  (TV: {TV_SORTINO})"
            )

print()

# ─── 8. TV-style: strategy.sharpe_ratio == Calmar-like? ──────────────────────
print("=" * 60)
print("ALTERNATIVE RATIO FORMULAS")
print("=" * 60)

# Max drawdown value (current)
max_dd_value = getattr(result, "max_drawdown", 0) or 0
net_profit = sum(t.pnl for t in closed)
print(f"Net profit: {net_profit:.2f}")
print(f"Max drawdown value: {max_dd_value:.2f}")
if max_dd_value != 0:
    print(f"Calmar = CAGR/max_dd = {our_cagr}/{max_dd_value:.2f} = {our_cagr / max_dd_value:.4f}")
    print(f"Profit factor-like = net_profit/max_dd = {net_profit / abs(max_dd_value):.4f}")

# Check performance metrics object
pm = result.performance_metrics if hasattr(result, "performance_metrics") else None
if pm:
    print(f"\nPerformanceMetrics.sharpe_ratio = {getattr(pm, 'sharpe_ratio', 'N/A')}")
    print(f"PerformanceMetrics.sortino_ratio = {getattr(pm, 'sortino_ratio', 'N/A')}")
    print(f"PerformanceMetrics.avg_margin_used = {getattr(pm, 'avg_margin_used', 'N/A')}")
    print(f"PerformanceMetrics.max_margin_used = {getattr(pm, 'max_margin_used', 'N/A')}")

print()

# ─── 9. Check key trade sizes ─────────────────────────────────────────────────
print("=" * 60)
print("KEY TRADE DATA (first 10 + last 5)")
print("=" * 60)
print(f"{'#':>3} {'side':>5} {'size':>12} {'entry':>10} {'qty*ep':>12} {'qty*ep/lev':>12} {'pnl':>10}")
for i, t in enumerate(closed[:10] + closed[-5:]):
    sz = getattr(t, "size", 0) or 0
    ep = getattr(t, "entry_price", 0) or 0
    notional = sz * ep
    margin = notional / cfg.leverage
    side = getattr(t, "direction", "?")
    pnl = getattr(t, "pnl", 0)
    print(f"{i + 1:3d} {side!s:>5} {sz:>12.6f} {ep:>10.2f} {notional:>12.2f} {margin:>12.2f} {pnl:>10.4f}")

print("\nAll margins (qty*ep/lev):")
all_margins = []
for t in closed:
    sz = getattr(t, "size", 0) or 0
    ep = getattr(t, "entry_price", 0) or 0
    all_margins.append(sz * ep / cfg.leverage)
all_margins = np.array(all_margins)
print(f"  min={all_margins.min():.2f}, max={all_margins.max():.2f}, mean={all_margins.mean():.2f}")
print(f"  TV: avg={TV_AVG_MARGIN}, max={TV_MAX_MARGIN}")
print()

# ─── 10. Hypothesis: TV margin = position_size_pct * equity_at_entry ──────────
print("=" * 60)
print("HYPOTHESIS: TV margin = position_size_pct * equity_at_entry")
print("=" * 60)
eq = init_cap
margins_equity = []
for t in closed:
    margin_equity = eq * cfg.position_size  # 10% of equity at entry
    margins_equity.append(margin_equity)
    eq += t.pnl  # update equity after trade closes

margins_equity = np.array(margins_equity)
print(f"  avg_margin_equity = {margins_equity.mean():.2f}  (TV: {TV_AVG_MARGIN})")
print(f"  max_margin_equity = {margins_equity.max():.2f}  (TV: {TV_MAX_MARGIN})")
print()

# Hypothesis: TV margin = position_size_pct * equity_at_entry / leverage
margins_equity_lev = margins_equity / cfg.leverage
print("Hypothesis: position_size_pct * equity / leverage:")
print(f"  avg = {margins_equity_lev.mean():.2f}  (TV: {TV_AVG_MARGIN})")
print(f"  max = {margins_equity_lev.max():.2f}  (TV: {TV_MAX_MARGIN})")
print()

print("Done.")
