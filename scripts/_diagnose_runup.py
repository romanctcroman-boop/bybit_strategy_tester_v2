"""
Investigate TV max_runup more carefully.
TV max_runup = 537.82 = 5.38% of 10000.
Current close-based: 482.83 (4.83%).
Gap: 54.99 = ?

Hypothesis: TV runup is equity_at_peak - equity_at_trough (not just peak - initial)
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
ec_arr = np.array(result.equity_curve.equity)
total_bars = len(ec_arr)
close_arr = df["close"].values
high_arr = df["high"].values
low_arr = df["low"].values

# Build trade maps
trade_by_entry = {}
trade_by_exit = {}
for t in closed_trades:
    eb = getattr(t, "entry_bar_index", None)
    xb = getattr(t, "exit_bar_index", None)
    if eb is not None:
        trade_by_entry[eb] = t
    if xb is not None:
        trade_by_exit[xb] = t

# Rebuild equity with intrabar prices
equity_close_r = np.zeros(total_bars)
equity_high_r = np.zeros(total_bars)
equity_low_r = np.zeros(total_bars)
cum_pnl = 0.0
current_trade = None

for i in range(total_bars):
    if i in trade_by_exit and current_trade is not None:
        tr = trade_by_exit[i]
        if tr is current_trade:
            cum_pnl += getattr(tr, "pnl", 0) or 0
            current_trade = None
    if i in trade_by_entry:
        current_trade = trade_by_entry[i]

    urpnl_c = urpnl_h = urpnl_l = 0.0
    if current_trade is not None:
        ep = getattr(current_trade, "entry_price", 0) or 0
        qty = getattr(current_trade, "size", 0) or 0
        side_str = str(getattr(current_trade, "side", "")).lower()
        is_long = any(x in side_str for x in ("buy", "long"))
        if is_long:
            urpnl_c = (close_arr[i] - ep) * qty
            urpnl_h = (high_arr[i] - ep) * qty
            urpnl_l = (low_arr[i] - ep) * qty
        else:
            urpnl_c = (ep - close_arr[i]) * qty
            urpnl_h = (ep - low_arr[i]) * qty  # short: low = favorable
            urpnl_l = (ep - high_arr[i]) * qty  # short: high = adverse

    equity_close_r[i] = INITIAL_CAPITAL + cum_pnl + urpnl_c
    equity_high_r[i] = INITIAL_CAPITAL + cum_pnl + urpnl_h
    equity_low_r[i] = INITIAL_CAPITAL + cum_pnl + urpnl_l

# === TV max_runup analysis ===
# TV max_runup = peak equity FROM trough (not from initial capital)
# Definition: max(equity - trough) where trough = accumulative minimum up to that point
# AKA: "max runup from valley"

print("=== MAX RUNUP ANALYSIS ===\n")

# Approach 1: max(equity_high) - initial_capital
r1 = equity_high_r.max() - INITIAL_CAPITAL
print(f"[1] max(equity_high) - initial = {r1:.4f}  (TV: 537.82)")

# Approach 2: max(equity_close) - min(equity_close) up to that point
trough_close = np.minimum.accumulate(equity_close_r)
runup_from_trough = equity_close_r - trough_close
r2 = float(runup_from_trough.max())
print(f"[2] max(equity_close - trough_close) = {r2:.4f}  (TV: 537.82)")

# Approach 3: max(equity_high) - min(equity_low) up to that point
trough_low = np.minimum.accumulate(equity_low_r)
runup_3 = equity_high_r - trough_low
r3 = float(runup_3.max())
print(f"[3] max(equity_high - trough_low) = {r3:.4f}  (TV: 537.82)")

# Approach 4: max(equity_high - trough_high)
trough_high = np.minimum.accumulate(equity_high_r)
runup_4 = equity_high_r - trough_high
r4 = float(runup_4.max())
print(f"[4] max(equity_high - trough_high) = {r4:.4f}  (TV: 537.82)")

# Approach 5: EC from engine, trough from low equity
trough_ec = np.minimum.accumulate(ec_arr)
runup_5 = ec_arr - trough_ec
r5 = float(runup_5.max())
print(f"[5] max(EC_engine - trough_EC) = {r5:.4f}  (TV: 537.82)")

# Approach 6: EC from engine (high intrabar version)
# What if TV runup = max(ec_with_intrabar_highs) - min(ec_with_intrabar_lows) so far?
r6 = equity_high_r.max() - equity_low_r.min()
print(f"[6] max(equity_high) - min(equity_low) = {r6:.4f}  (TV: 537.82)")

# Approach 7: metrics_calculator max_runup_value (close-based from engine)
r7_val = getattr(result.metrics, "max_runup_value", 0)
print(f"[7] engine max_runup_value (close, metrics_calc) = {r7_val:.4f}  (TV: 537.82)")

# Find bar where max runup_from_trough occurs
trough_low2 = np.minimum.accumulate(equity_low_r)
runup_2b = equity_high_r - trough_low2
peak_bar = int(np.argmax(runup_2b))
print(f"\nPeak runup [3] at bar {peak_bar}:")
print(f"  equity_high[{peak_bar}] = {equity_high_r[peak_bar]:.4f}")
print(f"  trough_low up to bar {peak_bar} = {trough_low2[peak_bar]:.4f}")
print(f"  runup = {runup_2b[peak_bar]:.4f}")

# Check what the MFE approach gives
mfe_values = [getattr(t, "mfe", 0) or 0 for t in closed_trades]
print(f"\nMax MFE per trade: max={max(mfe_values):.4f}  (current intrabar runup: 40.74)")
print(f"All MFE values: {sorted(mfe_values, reverse=True)[:5]}")

# What if runup = cumulative PnL peak using intrabar highs?
# = equity_high.max() but starting from start
r_peak = equity_high_r.max() - equity_high_r[0]
print(f"\n[8] equity_high.max() - equity_high[0] = {r_peak:.4f}")
r_peak2 = equity_high_r.max() - INITIAL_CAPITAL
print(f"[9] equity_high.max() - initial_capital = {r_peak2:.4f}")

print("\n\n=== INTRABAR RUNUP PER-TRADE (TV-STYLE) ===")
# TV might compute runup per-trade and take cumulative
# For each trade: equity_at_best_intrabar - equity_at_entry
# Then cumulate across trades
cumulative_runup_capital = INITIAL_CAPITAL
max_cumulative_capital = INITIAL_CAPITAL
for t in sorted(closed_trades, key=lambda x: getattr(x, "entry_bar_index", 0)):
    eb = getattr(t, "entry_bar_index", None)
    xb = getattr(t, "exit_bar_index", None)
    ep = getattr(t, "entry_price", 0) or 0
    qty = getattr(t, "size", 0) or 0
    pnl = getattr(t, "pnl", 0) or 0
    mfe = getattr(t, "mfe", 0) or 0
    if eb is None or xb is None:
        continue
    # During this trade, best equity = cumulative capital before trade + mfe
    best_eq = cumulative_runup_capital + mfe
    if best_eq > max_cumulative_capital:
        max_cumulative_capital = best_eq
    cumulative_runup_capital += pnl

r_cumulative = max_cumulative_capital - INITIAL_CAPITAL
print(f"Cumulative capital + MFE approach: max = {max_cumulative_capital:.4f}")
print(f"max_runup_value (this approach) = {r_cumulative:.4f}  (TV: 537.82)")
