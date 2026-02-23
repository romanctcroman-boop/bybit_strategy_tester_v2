"""
Comprehensive diagnostic for intrabar dd/runup + margin using engine result.
Tests the exact formulas to be implemented in engine.py.
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

# ── Load strategy ──────────────────────────────────────────────────────────────
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

# ── Load OHLCV ─────────────────────────────────────────────────────────────────
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
print(f"Total trades: {len(trades)}, Closed: {len(closed_trades)}")

ec_arr = np.array(result.equity_curve.equity)
total_bars = len(ec_arr)
close_arr = df["close"].values
high_arr = df["high"].values
low_arr = df["low"].values
print(f"EC length: {total_bars}, DF length: {len(df)}")

# ── Current metrics ────────────────────────────────────────────────────────────
print("\n=== CURRENT METRICS ===")
m = result.metrics
print(f"max_runup_intrabar_value:   {m.max_runup_intrabar_value:.4f}  (TV: 537.82)")
print(f"max_drawdown_intrabar_value:{m.max_drawdown_intrabar_value:.4f}  (TV: 146.99)")
print(f"avg_margin_used:            {m.avg_margin_used:.4f}  (TV: 852.53)")
print(f"max_margin_used:            {m.max_margin_used:.4f}  (TV: 1033.35)")
print(f"account_size_required:      {m.account_size_required:.4f}  (TV: 1180.34)")

# ── Build equity with OHLC intrabar prices ─────────────────────────────────────
print("\n=== EQUITY-BASED INTRABAR APPROACH ===")

# Build trade maps by bar index
trade_by_entry = {}
trade_by_exit = {}
for t in closed_trades:
    eb = getattr(t, "entry_bar_index", None)
    xb = getattr(t, "exit_bar_index", None)
    if eb is not None:
        trade_by_entry[eb] = t
    if xb is not None:
        trade_by_exit[xb] = t

print(f"Trades with bar indices: {len(trade_by_entry)}")

# Build equity using intrabar HIGH prices (best case for longs, worst for shorts)
# and LOW prices (worst case for longs, best for shorts)
equity_close_rebuilt = np.zeros(total_bars)
equity_high_intrabar = np.zeros(total_bars)
equity_low_intrabar = np.zeros(total_bars)

cum_pnl = 0.0
current_trade = None

for i in range(total_bars):
    # Exit event: process before entry for same-bar trades
    if i in trade_by_exit and current_trade is not None:
        tr = trade_by_exit[i]
        if tr is current_trade:
            cum_pnl += getattr(tr, "pnl", 0) or 0
            current_trade = None

    # Entry event
    if i in trade_by_entry:
        current_trade = trade_by_entry[i]

    # Compute unrealized PnL at close, high, low
    urpnl_close = 0.0
    urpnl_high = 0.0
    urpnl_low = 0.0

    if current_trade is not None:
        ep = getattr(current_trade, "entry_price", 0) or 0
        qty = getattr(current_trade, "size", 0) or 0
        side_str = str(getattr(current_trade, "side", "")).lower()
        is_long = any(x in side_str for x in ("buy", "long"))

        if is_long:
            urpnl_close = (close_arr[i] - ep) * qty
            urpnl_high = (high_arr[i] - ep) * qty  # Best intrabar
            urpnl_low = (low_arr[i] - ep) * qty  # Worst intrabar
        else:
            urpnl_close = (ep - close_arr[i]) * qty
            urpnl_high = (ep - low_arr[i]) * qty  # Best intrabar (short: low = favorable)
            urpnl_low = (ep - high_arr[i]) * qty  # Worst intrabar (short: high = adverse)

    equity_close_rebuilt[i] = INITIAL_CAPITAL + cum_pnl + urpnl_close
    equity_high_intrabar[i] = INITIAL_CAPITAL + cum_pnl + urpnl_high
    equity_low_intrabar[i] = INITIAL_CAPITAL + cum_pnl + urpnl_low

# Compare rebuilt vs EC
print(f"\nEquity close rebuilt: max={equity_close_rebuilt.max():.4f}, final={equity_close_rebuilt[-1]:.4f}")
print(f"EC from engine:       max={ec_arr.max():.4f},               final={ec_arr[-1]:.4f}")
diff = np.abs(equity_close_rebuilt - ec_arr).max()
print(f"Max diff between rebuilt and EC: {diff:.6f}")

# Max runup using intrabar highs
max_runup_value = float(equity_high_intrabar.max() - INITIAL_CAPITAL)
max_runup_pct = max_runup_value / INITIAL_CAPITAL * 100
print("\n--- INTRABAR RUNUP ---")
print(f"equity_high max:           {equity_high_intrabar.max():.4f}")
print(f"max_runup_intrabar_value:  {max_runup_value:.4f}  (TV: 537.82)")
print(f"max_runup_intrabar_pct:    {max_runup_pct:.4f}%  (TV: 5.38%)")
print(f"Close-based runup:         {equity_close_rebuilt.max() - INITIAL_CAPITAL:.4f}")

# Max drawdown using intrabar lows
# TV: HWM from close equity, drawdown to intrabar lows
hwm_close = np.maximum.accumulate(equity_close_rebuilt)
dd_to_low = hwm_close - equity_low_intrabar
max_dd_value = float(dd_to_low.max())
max_dd_pct = max_dd_value / INITIAL_CAPITAL * 100
print("\n--- INTRABAR DRAWDOWN ---")
print(f"max(HWM_close - equity_low): {max_dd_value:.4f}  (TV: 146.99)")
print(f"max_dd_intrabar_pct:         {max_dd_pct:.4f}%  (TV: 1.47%)")

# Alternative: HWM from high equity
hwm_high = np.maximum.accumulate(equity_high_intrabar)
dd_from_high_hwm = hwm_high - equity_low_intrabar
max_dd_from_high = float(dd_from_high_hwm.max())
print(f"Alt: max(HWM_high - equity_low): {max_dd_from_high:.4f}")

# Close-based drawdown
dd_close = hwm_close - equity_close_rebuilt
print(f"Close-based drawdown:            {dd_close.max():.4f}")

# Account size required
account_size = 0.0  # will be computed with correct margin
print(f"\nWith new max_dd_intrabar={max_dd_value:.4f} and TV max_margin=1033.35:")
print(f"  account_size_required would be: {1033.35 + max_dd_value:.4f}  (TV: 1180.34)")

# ── MARGIN: Bar-by-bar MVS approach ───────────────────────────────────────────
print("\n=== MARGIN (BAR-BY-BAR MVS) ===")
mvs_bar = np.zeros(total_bars)
for t in closed_trades:
    eb = getattr(t, "entry_bar_index", None)
    xb = getattr(t, "exit_bar_index", None)
    qty = abs(getattr(t, "size", 0) or 0)
    if eb is None or xb is None or qty == 0:
        continue
    for b in range(eb, min(xb + 1, total_bars)):
        mvs_bar[b] = qty * close_arr[b]  # MVS = qty * close, margin_pct=100%

avg_margin = float(mvs_bar.mean())
max_margin = float(mvs_bar.max())
n_pos_bars = int(np.sum(mvs_bar > 0))
print(f"avg_margin_used (all {total_bars} bars): {avg_margin:.4f}  (TV: 852.53)")
print(f"max_margin_used:                         {max_margin:.4f}  (TV: 1033.35)")
print(f"Bars in position: {n_pos_bars} / {total_bars}")
print(f"account_size_required = {max_margin:.4f} + {max_dd_value:.4f} = {max_margin + max_dd_value:.4f}  (TV: 1180.34)")

# ── Summary ────────────────────────────────────────────────────────────────────
print("\n=== SUMMARY ===")
metrics_table = [
    ("max_runup_intrabar_value", max_runup_value, 537.82),
    ("max_runup_intrabar_pct", max_runup_pct, 5.38),
    ("max_dd_intrabar_value", max_dd_value, 146.99),
    ("max_dd_intrabar_pct", max_dd_pct, 1.47),
    ("avg_margin_used", avg_margin, 852.53),
    ("max_margin_used", max_margin, 1033.35),
    ("account_size_required", max_margin + max_dd_value, 1180.34),
]
for name, computed, tv in metrics_table:
    diff_pct = abs(computed - tv) / tv * 100
    status = "✅" if diff_pct < 2.0 else "⚠️" if diff_pct < 5.0 else "❌"
    print(f"  {status} {name}: {computed:.4f} vs TV {tv:.2f} ({diff_pct:.2f}% diff)")
