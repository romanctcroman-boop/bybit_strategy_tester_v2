"""
Проверяем гипотезу H: TV строит HWM от REALIZED equity (без unrealized PnL),
а просадку считает к equity_low (с unrealized).
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
    "SELECT open_time, open_price as open, high_price as high, low_price as low,"
    " close_price as close, volume "
    "FROM bybit_kline_audit WHERE symbol=? AND interval=? AND market_type=? "
    "AND open_time>=? AND open_time<=? ORDER BY open_time ASC",
    conn2,
    params=("BTCUSDT", "15", "linear", start_ms, end_ms),
)
conn2.close()
df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df = df.set_index("timestamp").drop(columns=["open_time"])

cfg = BacktestConfig(
    symbol="BTCUSDT",
    interval="15",
    start_date=dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
    end_date=dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC),
    initial_capital=10000.0,
    commission_value=0.0007,
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

high_arr = df["high"].values
low_arr = df["low"].values
close_arr = df["close"].values
total_bars = len(close_arr)
initial_capital = 10000.0

trade_by_entry = {}
trade_by_exit = {}
for t in closed:
    eb = getattr(t, "entry_bar_index", None)
    xb = getattr(t, "exit_bar_index", None)
    if eb is not None:
        trade_by_entry[eb] = t
    if xb is not None:
        trade_by_exit[xb] = t

# Сделка eb=1896 создаёт глобальный HWM
t1896 = next((t for t in closed if getattr(t, "entry_bar_index", None) == 1896), None)
print(
    "Сделка eb=1896:",
    getattr(t1896, "side", ""),
    "ep=",
    getattr(t1896, "entry_price", 0),
    "xb=",
    getattr(t1896, "exit_bar_index", None),
    "pnl=",
    round(getattr(t1896, "pnl", 0), 4),
)

# Бар 1913 — где создаётся HWM=10197.91
bar_hwm = 1913
print(
    f"Бар {bar_hwm} ({df.index[bar_hwm]}): "
    f"H={high_arr[bar_hwm]:.2f} L={low_arr[bar_hwm]:.2f} C={close_arr[bar_hwm]:.2f}"
)
print()

# ── ГИПОТЕЗА H: HWM строится от REALIZED equity (без unrealized PnL) ──
equity_realized = np.zeros(total_bars)
cum_r = initial_capital
current_t = None
for i in range(total_bars):
    if i in trade_by_exit and current_t is not None:
        tr = trade_by_exit[i]
        if tr is current_t:
            cum_r += getattr(tr, "pnl", 0) or 0
            current_t = None
    if i in trade_by_entry:
        current_t = trade_by_entry[i]
    equity_realized[i] = cum_r  # realized only, no unrealized

hwm_realized = np.maximum.accumulate(equity_realized)

# equity_low = realized_pnl + unrealized_low
equity_low = np.zeros(total_bars)
cum_pnl2 = 0.0
current_t2 = None
for i in range(total_bars):
    if i in trade_by_exit and current_t2 is not None:
        tr = trade_by_exit[i]
        if tr is current_t2:
            cum_pnl2 += getattr(tr, "pnl", 0) or 0
            current_t2 = None
    if i in trade_by_entry:
        current_t2 = trade_by_entry[i]
    urpnl_l = 0.0
    if current_t2 is not None:
        ep = getattr(current_t2, "entry_price", 0) or 0
        qty = getattr(current_t2, "size", 0) or 0
        is_long = any(x in str(getattr(current_t2, "side", "")).lower() for x in ("buy", "long"))
        urpnl_l = (low_arr[i] - ep) * qty if is_long else (ep - high_arr[i]) * qty
    equity_low[i] = initial_capital + cum_pnl2 + urpnl_l

dd_realized = hwm_realized - equity_low
print(f"Алг H (HWM=realized, dd→eq_low):      {dd_realized.max():.4f}  TV=146.99")
idx_h = int(np.argmax(dd_realized))
print(f"  worst bar={idx_h} ({df.index[idx_h]})")
print(f"  HWM[{idx_h}]={hwm_realized[idx_h]:.4f}  eq_low={equity_low[idx_h]:.4f}")
print(f"  HWM @ bar 6393 = {hwm_realized[6393]:.4f}  (нужно 10193.57)")
print()

# ── ГИПОТЕЗА I: HWM строится от equity_close, но equity_close считает
#    реализованный PnL МИНУС комиссию ВЫХОДА для незакрытых сделок ──
# (т.е. TV отражает pending комиссию в equity)
comm_rate = 0.0007
equity_close_pending_comm = np.zeros(total_bars)
cum_pnl3 = 0.0
current_t3 = None
for i in range(total_bars):
    if i in trade_by_exit and current_t3 is not None:
        tr = trade_by_exit[i]
        if tr is current_t3:
            cum_pnl3 += getattr(tr, "pnl", 0) or 0
            current_t3 = None
    if i in trade_by_entry:
        current_t3 = trade_by_entry[i]
    urpnl_c = 0.0
    pending_comm = 0.0
    if current_t3 is not None:
        ep = getattr(current_t3, "entry_price", 0) or 0
        qty = getattr(current_t3, "size", 0) or 0
        is_long = any(x in str(getattr(current_t3, "side", "")).lower() for x in ("buy", "long"))
        urpnl_c = (close_arr[i] - ep) * qty if is_long else (ep - close_arr[i]) * qty
        # Pending exit commission at current close price
        pending_comm = close_arr[i] * qty * comm_rate
    equity_close_pending_comm[i] = initial_capital + cum_pnl3 + urpnl_c - pending_comm

hwm_pcomm = np.maximum.accumulate(equity_close_pending_comm)
dd_pcomm = hwm_pcomm - equity_low
print(f"Алг I (HWM=eq_close-pending_comm, dd→eq_low): {dd_pcomm.max():.4f}")
idx_i = int(np.argmax(dd_pcomm))
print(f"  worst bar={idx_i} ({df.index[idx_i]})")
print(f"  HWM @ bar 6393 = {hwm_pcomm[6393]:.4f}")
print(f"  eq_close_pcomm @ bar 1913 = {equity_close_pending_comm[bar_hwm]:.4f} (наш HWM = {10197.9098:.4f})")
print()

# ── ГИПОТЕЗА J: TV HWM = max(equity_close) ТОЛЬКО на барах ЗАКРЫТИЯ (exit bars)
#    между сделками (realized equity peaks only) ──
exit_bars = set(trade_by_exit.keys())
equity_close_full = np.zeros(total_bars)
cum_pnl4 = 0.0
current_t4 = None
for i in range(total_bars):
    if i in trade_by_exit and current_t4 is not None:
        tr = trade_by_exit[i]
        if tr is current_t4:
            cum_pnl4 += getattr(tr, "pnl", 0) or 0
            current_t4 = None
    if i in trade_by_entry:
        current_t4 = trade_by_entry[i]
    urpnl_c = 0.0
    if current_t4 is not None:
        ep = getattr(current_t4, "entry_price", 0) or 0
        qty = getattr(current_t4, "size", 0) or 0
        is_long = any(x in str(getattr(current_t4, "side", "")).lower() for x in ("buy", "long"))
        urpnl_c = (close_arr[i] - ep) * qty if is_long else (ep - close_arr[i]) * qty
    equity_close_full[i] = initial_capital + cum_pnl4 + urpnl_c

# HWM только от closed bars equity
equity_at_exit = np.where(
    np.array([i in exit_bars for i in range(total_bars)]),
    equity_realized,  # realized (after pnl booked)
    np.nan,
)
hwm_j_series = pd.Series(equity_at_exit).ffill().fillna(initial_capital).values
dd_j = hwm_j_series - equity_low
print(f"Алг J (HWM=realized @ exit bars only, ffill): {dd_j.max():.4f}")
print()

# ── ИТОГ ──
print("=" * 55)
needed_hwm = 146.99 + equity_low[6393]
print(f"Для TV=146.99 при bar=6393 нужен HWM = {needed_hwm:.4f}")
print(f"Наш HWM (глобальный equity_close)    = {np.maximum.accumulate(equity_close_full)[6393]:.4f}")
print(f"Наш realized HWM                      = {hwm_realized[6393]:.4f}")
print()
print("Значит TV HWM создаётся на баре 1913 (сделка eb=1896, LONG),")
print("но его значение у TV =", needed_hwm, "(наше =", 10197.9098, ")")
print()
print("Разница:", 10197.9098 - needed_hwm, "= exactly 4.3353")
print()
print("Проверим: на баре 1913 (exit сделки eb=1896):")
xb_1896 = getattr(t1896, "exit_bar_index", None)
pnl_1896 = getattr(t1896, "pnl", 0) or 0
print(f"  xb_1896 = {xb_1896} (exit bar)")
print("  bar_hwm = 1913 (where HWM is achieved)")
print(f"  Эти бары {'СОВПАДАЮТ' if xb_1896 == bar_hwm else f'НЕ совпадают (xb={xb_1896}, hwm_bar=1913)'}")
if xb_1896 != bar_hwm:
    print()
    print("HWM создаётся ВНУТРИ сделки, а не на exit.")
    print("Значит TV считает unrealized PnL так же как мы,")
    print("НО использует HIGH bar для HWM (favorable price)?")
    ep_1896 = getattr(t1896, "entry_price", 0)
    qty_1896 = getattr(t1896, "size", 0)
    is_long_1896 = any(x in str(getattr(t1896, "side", "")).lower() for x in ("buy", "long"))

    # Найдём cum_before_1896
    trades_sorted = sorted(closed, key=lambda t: getattr(t, "entry_bar_index", 0) or 0)
    cum_before_1896 = initial_capital
    for t in trades_sorted:
        if getattr(t, "entry_bar_index", 0) >= 1896:
            break
        cum_before_1896 += getattr(t, "pnl", 0) or 0

    for b in [1912, 1913, 1914]:
        if b >= total_bars:
            continue
        eq_h = (
            cum_before_1896 + (high_arr[b] - ep_1896) * qty_1896
            if is_long_1896
            else cum_before_1896 + (ep_1896 - low_arr[b]) * qty_1896
        )
        eq_c = (
            cum_before_1896 + (close_arr[b] - ep_1896) * qty_1896
            if is_long_1896
            else cum_before_1896 + (ep_1896 - close_arr[b]) * qty_1896
        )
        print(f"  bar {b}: eq_high={eq_h:.4f}  eq_close={eq_c:.4f}  H={high_arr[b]:.2f} C={close_arr[b]:.2f}")
