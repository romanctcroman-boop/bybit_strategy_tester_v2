"""
Диагностика расхождения max_drawdown_intrabar.
Мы: 151.33, TV: 146.99 — разница 4.34 (2.95%)

Задача: найти какой бар/сделка даёт расхождение и почему.
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
trades = result.trades
closed = [t for t in trades if not getattr(t, "is_open", False)]

print(f"Trades: {len(trades)} total, {len(closed)} closed")
metrics = result.metrics
if metrics is not None:
    print(f"Engine max_drawdown_intrabar_value = {metrics.max_drawdown_intrabar_value:.4f}")
    print("TV target                          = 146.9900")
    print(f"Difference                         = {metrics.max_drawdown_intrabar_value - 146.99:.4f}")
print()

# ── Вариант A: наш текущий алгоритм (HWM от close, просадка к low) ──────────
initial_capital = 10000.0
high_arr = df["high"].values
low_arr = df["low"].values
close_arr = df["close"].values
total_bars = len(close_arr)

# Индексируем сделки
trade_by_entry = {}
trade_by_exit = {}
for t in closed:
    eb = getattr(t, "entry_bar_index", None)
    xb = getattr(t, "exit_bar_index", None)
    if eb is not None:
        trade_by_entry[eb] = t
    if xb is not None:
        trade_by_exit[xb] = t

equity_close = np.zeros(total_bars)
equity_low = np.zeros(total_bars)
equity_high = np.zeros(total_bars)
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

    urpnl_c = urpnl_l = urpnl_h = 0.0
    if current_trade is not None:
        ep = getattr(current_trade, "entry_price", 0) or 0
        qty = getattr(current_trade, "size", 0) or 0
        side_str = str(getattr(current_trade, "side", "")).lower()
        is_long = any(x in side_str for x in ("buy", "long"))
        if is_long:
            urpnl_c = (close_arr[i] - ep) * qty
            urpnl_l = (low_arr[i] - ep) * qty
            urpnl_h = (high_arr[i] - ep) * qty
        else:
            urpnl_c = (ep - close_arr[i]) * qty
            urpnl_l = (ep - high_arr[i]) * qty  # worst for short
            urpnl_h = (ep - low_arr[i]) * qty  # best for short

    equity_close[i] = initial_capital + cum_pnl + urpnl_c
    equity_low[i] = initial_capital + cum_pnl + urpnl_l
    equity_high[i] = initial_capital + cum_pnl + urpnl_h

# ── Алгоритм A (текущий): HWM(close) → low ──
hwm_a = np.maximum.accumulate(equity_close)
dd_a = hwm_a - equity_low
idx_a = int(np.argmax(dd_a))
val_a = float(dd_a[idx_a])
ts_a = df.index[idx_a]

print("=" * 60)
print("Алгоритм A (текущий): HWM(equity_close) → equity_low")
print(f"  max_dd = {val_a:.4f}  @ бар {idx_a} ({ts_a})")
print(f"  HWM    = {hwm_a[idx_a]:.4f}")
print(f"  eq_low = {equity_low[idx_a]:.4f}")
print()

# ── Алгоритм B: HWM(max(close,high)) → low ──
equity_max = np.maximum(equity_close, equity_high)
hwm_b = np.maximum.accumulate(equity_max)
dd_b = hwm_b - equity_low
idx_b = int(np.argmax(dd_b))
val_b = float(dd_b[idx_b])
ts_b = df.index[idx_b]

print("Алгоритм B: HWM(max(equity_close, equity_high)) → equity_low")
print(f"  max_dd = {val_b:.4f}  @ бар {idx_b} ({ts_b})")
print()

# ── Алгоритм C: только бары ВНУТРИ позиции ──
# TV считает drawdown только когда есть открытая позиция
in_position = np.zeros(total_bars, dtype=bool)
current_trade2 = None
for i in range(total_bars):
    if i in trade_by_exit and current_trade2 is not None:
        tr = trade_by_exit[i]
        if tr is current_trade2:
            current_trade2 = None
    if i in trade_by_entry:
        current_trade2 = trade_by_entry[i]
    in_position[i] = current_trade2 is not None

hwm_c = np.maximum.accumulate(np.where(in_position, equity_close, np.nan))
# forward-fill HWM через flat периоды
hwm_c_filled = pd.Series(hwm_c).ffill().fillna(initial_capital).values
dd_c = hwm_c_filled - equity_low
dd_c_in = np.where(in_position, dd_c, 0.0)
idx_c = int(np.argmax(dd_c_in))
val_c = float(dd_c_in[idx_c])
ts_c = df.index[idx_c]

print("Алгоритм C: HWM только внутри позиций → equity_low (только in-position)")
print(f"  max_dd = {val_c:.4f}  @ бар {idx_c} ({ts_c})")
print()

# ── Алгоритм D: TV-style — HWM(equity+MFE per trade) ──
# TV считает так: для каждой сделки max_drawdown = equity_before_trade - min(equity_low) за время сделки
# т.е. HWM = equity перед входом + MFE
print("Алгоритм D: per-trade (TV-style, equity_before - min_equity_during_trade)")
trades_sorted = sorted(closed, key=lambda t: getattr(t, "entry_bar_index", 0) or 0)
cum_d = initial_capital
max_dd_d = 0.0
best_trade_d = None
for t in trades_sorted:
    eb = getattr(t, "entry_bar_index", None)
    xb = getattr(t, "exit_bar_index", None)
    pnl = getattr(t, "pnl", 0) or 0
    qty = getattr(t, "size", 0) or 0
    ep = getattr(t, "entry_price", 0) or 0
    side_str = str(getattr(t, "side", "")).lower()
    is_long = any(x in side_str for x in ("buy", "long"))

    if eb is None or xb is None:
        cum_d += pnl
        continue

    # Equity-low array for this trade's bars
    trade_eq_low = []
    for b in range(eb, min(xb + 1, total_bars)):
        if is_long:
            urpnl = (low_arr[b] - ep) * qty
        else:
            urpnl = (ep - high_arr[b]) * qty
        trade_eq_low.append(cum_d + urpnl)

    if trade_eq_low:
        min_eq = min(trade_eq_low)
        dd = cum_d - min_eq  # drawdown from equity_before_entry
        if dd > max_dd_d:
            max_dd_d = dd
            best_trade_d = t

    cum_d += pnl

print(f"  max_dd = {max_dd_d:.4f}")
if best_trade_d:
    print(
        f"  worst trade: #{getattr(best_trade_d, 'entry_bar_index', None)} "
        f"entry={getattr(best_trade_d, 'entry_price', 0):.2f} "
        f"side={getattr(best_trade_d, 'side', '')}"
    )
print()

print("=" * 60)
print("TV target = 146.99")
print("Closest to TV:")
results = [("A (current)", val_a), ("B (HWM+high)", val_b), ("C (in-pos only)", val_c), ("D (per-trade)", max_dd_d)]
for name, val in sorted(results, key=lambda x: abs(x[1] - 146.99)):
    diff = val - 146.99
    print(f"  {name:<20}: {val:.4f}  (diff={diff:+.4f})")

print()
# ── Показать топ-5 баров с наибольшей просадкой по алгоритму A ──
print("Топ-5 баров по dd_a (текущий алгоритм):")
top5 = np.argsort(dd_a)[-5:][::-1]
for idx in top5:
    ts = df.index[idx]
    t_active = None
    # Find which trade is active at this bar
    for t in closed:
        eb = getattr(t, "entry_bar_index", None) or 0
        xb = getattr(t, "exit_bar_index", None) or 0
        if eb <= idx <= xb:
            t_active = t
            break
    trade_info = ""
    if t_active:
        trade_info = (
            f"trade eb={getattr(t_active, 'entry_bar_index', None)} "
            f"ep={getattr(t_active, 'entry_price', 0):.2f} "
            f"side={getattr(t_active, 'side', '')}"
        )
    print(
        f"  bar {idx:4d} {ts}  dd={dd_a[idx]:.4f}  "
        f"hwm={hwm_a[idx]:.4f} eq_low={equity_low[idx]:.4f}  "
        f"close={close_arr[idx]:.2f} low={low_arr[idx]:.2f}  {trade_info}"
    )
