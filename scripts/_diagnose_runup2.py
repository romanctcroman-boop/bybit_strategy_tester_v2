"""
Investigate TV max_runup: close-to-close vs intrabar.
TV:
  - "от закрытия до закрытия" (close-to-close) = 176.81 (1.77%)
  - "внутри бара" (intrabar) = 537.82 (5.13% of equity peak = 5.38% of initial)

The "close-to-close" value 176.81 likely means: max run from equity trough to equity peak
using only close prices. But our calc gives 557. So maybe it's PER-TRADE runup?

Or: "close-to-close" = based on trade-level PnL cumulation, not bar-by-bar equity?
Let's compute per-trade cumulative equity and find max runup from trough.
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
INITIAL_CAPITAL = 10000.0

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
    initial_capital=INITIAL_CAPITAL,
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

trades = result.trades
closed_trades = [t for t in trades if not getattr(t, "is_open", False)]
closed_trades_sorted = sorted(closed_trades, key=lambda x: getattr(x, "entry_bar_index", 0) or 0)

ec_arr = np.array(result.equity_curve.equity)
close_arr = df["close"].values
high_arr = df["high"].values
low_arr = df["low"].values
total_bars = len(ec_arr)

print("=== TRADE-LEVEL RUNUP ANALYSIS ===\n")
print("TV close-to-close max_runup = 176.81")
print("TV intrabar max_runup = 537.82 (5.13% of equity, 5.38% of initial)\n")

# Approach A: Trade-level equity, max runup from trough (close-to-close)
trade_equity = [INITIAL_CAPITAL]
for t in closed_trades_sorted:
    pnl = getattr(t, "pnl", 0) or 0
    trade_equity.append(trade_equity[-1] + pnl)
trade_equity_arr = np.array(trade_equity)
trough_te = np.minimum.accumulate(trade_equity_arr)
runup_te = trade_equity_arr - trough_te
max_runup_te = float(runup_te.max())
print(f"[A] Trade-level equity, max(eq - trough) = {max_runup_te:.4f}  (TV close-to-close: 176.81)")

# Approach B: Per-trade max runup (MFE-based), cumulative equity + MFE
# This is what engine currently does for max_runup_intrabar: max(mfe) per trade = 40.74
max_mfe = max(getattr(t, "mfe", 0) or 0 for t in closed_trades_sorted)
print(f"[B] max(MFE per trade) = {max_mfe:.4f}  (TV intrabar: 537.82)")

# Approach C: Trade-level with per-trade MFE as best equity during trade
# For each trade: best possible equity = cumulative_before_trade + MFE
cum_before = INITIAL_CAPITAL
max_equity_with_mfe = INITIAL_CAPITAL
min_equity_before_trade = INITIAL_CAPITAL
for t in closed_trades_sorted:
    pnl = getattr(t, "pnl", 0) or 0
    mfe = getattr(t, "mfe", 0) or 0
    best_eq = cum_before + mfe
    if best_eq > max_equity_with_mfe:
        max_equity_with_mfe = best_eq
    cum_before += pnl

max_runup_C = max_equity_with_mfe - INITIAL_CAPITAL
print(f"[C] Cumulative equity + max(MFE), peak - initial = {max_runup_C:.4f}  (TV: 537.82)")

# Approach D: Same as C but track trough too
cum = INITIAL_CAPITAL
trough_d = INITIAL_CAPITAL
max_runup_D = 0.0
for t in closed_trades_sorted:
    pnl = getattr(t, "pnl", 0) or 0
    mfe = getattr(t, "mfe", 0) or 0
    mae = getattr(t, "mae", 0) or 0
    # During this trade, equity goes to min (cum + mae) and max (cum + mfe)
    eq_worst = cum - mae  # Worst point during trade (equity drops by mae)
    eq_best = cum + mfe  # Best point during trade

    if eq_worst < trough_d:
        trough_d = eq_worst
    runup = eq_best - trough_d
    if runup > max_runup_D:
        max_runup_D = runup
    cum += pnl

print(f"[D] Intrabar peak/trough tracking per-trade: max_runup = {max_runup_D:.4f}  (TV: 537.82)")

# Approach E: Cumulative with MFE, max(peak - trough) where trough uses MAE
cum = INITIAL_CAPITAL
trough_e = INITIAL_CAPITAL
max_runup_e = 0.0
for t in closed_trades_sorted:
    pnl = getattr(t, "pnl", 0) or 0
    mfe = getattr(t, "mfe", 0) or 0
    mae = getattr(t, "mae", 0) or 0
    # After N trades, equity_at_close = cum + pnl (after this trade)
    # Worst point using close equity (not intrabar)
    eq_close_after = cum + pnl
    if eq_close_after < trough_e:
        trough_e = eq_close_after
    # Best intrabar = cum + mfe
    eq_best = cum + mfe
    runup = eq_best - trough_e
    if runup > max_runup_e:
        max_runup_e = runup
    cum += pnl

print(f"[E] Close trough, MFE peak: max_runup = {max_runup_e:.4f}  (TV: 537.82)")

# Approach F: what if TV intrabar = max(MFE) across all bars?
# bar-by-bar, find the maximum unrealized PnL at any point
trade_by_entry = {}
trade_by_exit = {}
for t in closed_trades:
    eb = getattr(t, "entry_bar_index", None)
    xb = getattr(t, "exit_bar_index", None)
    if eb is not None:
        trade_by_entry[eb] = t
    if xb is not None:
        trade_by_exit[xb] = t

cum_pnl = 0.0
current_trade = None
max_equity_f = INITIAL_CAPITAL
min_equity_before_f = INITIAL_CAPITAL

equity_high = np.zeros(total_bars)
equity_low = np.zeros(total_bars)

for i in range(total_bars):
    if i in trade_by_exit and current_trade is not None:
        tr = trade_by_exit[i]
        if tr is current_trade:
            cum_pnl += getattr(tr, "pnl", 0) or 0
            current_trade = None
    if i in trade_by_entry:
        current_trade = trade_by_entry[i]

    urpnl_h = 0.0
    urpnl_l = 0.0
    if current_trade is not None:
        ep = getattr(current_trade, "entry_price", 0) or 0
        qty = getattr(current_trade, "size", 0) or 0
        side_str = str(getattr(current_trade, "side", "")).lower()
        is_long = any(x in side_str for x in ("buy", "long"))
        if is_long:
            urpnl_h = (high_arr[i] - ep) * qty
            urpnl_l = (low_arr[i] - ep) * qty
        else:
            urpnl_h = (ep - low_arr[i]) * qty
            urpnl_l = (ep - high_arr[i]) * qty

    equity_high[i] = INITIAL_CAPITAL + cum_pnl + urpnl_h
    equity_low[i] = INITIAL_CAPITAL + cum_pnl + urpnl_l

# Max runup: max(equity_high - min(equity_low up to bar))
trough_low = np.minimum.accumulate(equity_low)
runup_f = equity_high - trough_low
max_runup_F = float(runup_f.max())
print(f"[F] Bar-by-bar max(equity_high - trough_low): {max_runup_F:.4f}  (TV intrabar: 537.82)")

trough_ec = np.minimum.accumulate(ec_arr)
runup_g = ec_arr - trough_ec
max_runup_G = float(runup_g.max())
print(f"[G] Bar-by-bar max(EC - trough_EC): {max_runup_G:.4f}  (TV close-to-close: 176.81 or intrabar: 537.82)")

# What about the TV close-to-close = 176.81?
# This should be: max(equity_close - trough_close), but only counting trade_close events?
# Let's compute trade-exit level equity and find max(eq - min_eq_so_far)
exit_eq = []
running_eq = INITIAL_CAPITAL
for t in closed_trades_sorted:
    running_eq += getattr(t, "pnl", 0) or 0
    exit_eq.append(running_eq)

exit_eq_arr = np.array(exit_eq)
trough_exit = np.minimum.accumulate(exit_eq_arr)
runup_exit = exit_eq_arr - trough_exit
max_runup_exit = float(runup_exit.max())
print(f"\n[H] Trade exit equity max(eq - trough): {max_runup_exit:.4f}  (TV close-to-close: 176.81)")

# Try with initial capital as first value
exit_eq_with_init = np.concatenate([[INITIAL_CAPITAL], exit_eq_arr])
trough_with_init = np.minimum.accumulate(exit_eq_with_init)
runup_with_init = exit_eq_with_init - trough_with_init
max_runup_H2 = float(runup_with_init.max())
print(f"[I] Trade exit + initial, max(eq - trough): {max_runup_H2:.4f}  (TV close-to-close: 176.81)")

# Check equity at exit bars only
print(f"\nFirst 5 trade PnLs: {[round(getattr(t, 'pnl', 0) or 0, 2) for t in closed_trades_sorted[:5]]}")
print(f"First 5 exit equities: {[round(v, 2) for v in exit_eq[:5]]}")
print(f"Min exit equity: {min(exit_eq):.4f}, at trade #{exit_eq.index(min(exit_eq))}")
