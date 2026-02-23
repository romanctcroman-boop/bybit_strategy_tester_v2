"""
Диагностика dd8: Финальное — поиск точного алгоритма TV для HWM.

Key observation:
- equity_high[1917] = 10193.5895 ≈ TV HWM = 10193.5745 (разница = 0.015!)
- equity_low[1913]  = 10193.7470 (разница = 0.1725)

Что такое equity_high[1917]?
Bar 1917 (2025-11-20 23:15): H=87848.00 (for LONG trade eb=1896)
equity_high[1917] = cum_before_1896 + (87848.00 - 87656.80) * qty1896
                  = 10192.8868 + 191.20 * 0.011408
                  = 10192.8868 + 2.18...

Подождите, посмотрим HWM(equity_high):
HWM @ bar 6393 нужен 10193.5745.
Из алгоритма K: HWM(high)[6393] = 10199.2092 (слишком высокий).

Новая идея: может TV строит equity_curve по-другому для open trades:
TV urpnl = min(high, close) - entry  (т.е. берет пессимистическое внутрибарное значение)

Или TV строит equity_curve: для КАЖДОГО бара использует open цену (не close)?
equity_tv[i] = cum + urpnl_at_open[i+1]?

Проверим систематически все комбинации.
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
SID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"

conn = sqlite3.connect(DB)
cur = conn.execute("SELECT * FROM strategies WHERE id=?", (SID,))
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
sms = int(dt.datetime(2025, 11, 1, tzinfo=dt.UTC).timestamp() * 1000)
ems = int(dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC).timestamp() * 1000)
df = pd.read_sql_query(
    "SELECT open_time, open_price as open, high_price as high, low_price as low,"
    " close_price as close, volume "
    "FROM bybit_kline_audit WHERE symbol=? AND interval=? AND market_type=? "
    "AND open_time>=? AND open_time<=? ORDER BY open_time ASC",
    conn2,
    params=("BTCUSDT", "15", "linear", sms, ems),
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
closed = [t for t in result.trades if not getattr(t, "is_open", False)]
trades_sorted = sorted(closed, key=lambda t: getattr(t, "entry_bar_index", 0) or 0)

high_arr = df["high"].values
low_arr = df["low"].values
close_arr = df["close"].values
open_arr = df["open"].values
total_bars = len(close_arr)
IC = 10000.0
comm_rate = 0.0007

trade_by_entry = {getattr(t, "entry_bar_index", 0): t for t in trades_sorted}
trade_by_exit = {getattr(t, "exit_bar_index", 0): t for t in trades_sorted}

tv_hwm_needed = 10193.5745
tv_dd = 146.99

# Посмотрим на bar 1917 детально
bar_1917 = 1917
t1896 = next(t for t in closed if getattr(t, "entry_bar_index", None) == 1896)
ep1896 = getattr(t1896, "entry_price", 0)
qty1896 = getattr(t1896, "size", 0)
cum_before_1896 = IC
for t in trades_sorted:
    if getattr(t, "entry_bar_index", 0) >= 1896:
        break
    cum_before_1896 += getattr(t, "pnl", 0) or 0

print(f"Bar 1917: O={open_arr[1917]:.2f} H={high_arr[1917]:.2f} L={low_arr[1917]:.2f} C={close_arr[1917]:.2f}")
eq_h_1917 = cum_before_1896 + (high_arr[1917] - ep1896) * qty1896
print(f"equity_high[1917] = {eq_h_1917:.4f}  TV HWM = {tv_hwm_needed}")
print(f"Разница = {eq_h_1917 - tv_hwm_needed:.4f}")
print()

# Может TV использует OPEN следующего бара как HWM source?
# equity_open[i+1] = cum + (open[i+1] - ep) * qty
# Проверим разные сдвиги: eq @ open[t] для t in 1910..1920
print("equity @ open[t] для t in 1907..1920 (LONG trade eb=1896):")
for bar_i in range(1907, 1921):
    if bar_i < total_bars:
        eq_open_t = cum_before_1896 + (open_arr[bar_i] - ep1896) * qty1896
        marker = " ← близко к TV!" if abs(eq_open_t - tv_hwm_needed) < 0.5 else ""
        print(f"  bar {bar_i}: open={open_arr[bar_i]:.2f}  eq={eq_open_t:.4f}{marker}")

print()

# Что если TV equity curve строится на основе open следующего бара?
# Т.е. bar i имеет equity = cum + (open[i] - ep) * qty
# (а не close[i])
# И HWM = max(equity_open_shifted)
# А dd = HWM - (worst of open[i])

# Построим equity_open_arr
equity_open_arr = np.zeros(total_bars)
equity_open_low = np.zeros(total_bars)  # low using open as base price
cum_pnl = 0.0
cur_t = None
for i in range(total_bars):
    if i in trade_by_exit and cur_t is not None:
        if trade_by_exit[i] is cur_t:
            cum_pnl += getattr(cur_t, "pnl", 0) or 0
            cur_t = None
    if i in trade_by_entry:
        cur_t = trade_by_entry[i]
    urpnl_o = urpnl_l = 0.0
    if cur_t is not None:
        ep_cur = getattr(cur_t, "entry_price", 0)
        qty_cur = getattr(cur_t, "size", 0)
        il = any(x in str(getattr(cur_t, "side", "")).lower() for x in ("buy", "long"))
        urpnl_o = (open_arr[i] - ep_cur) * qty_cur if il else (ep_cur - open_arr[i]) * qty_cur
        urpnl_l = (low_arr[i] - ep_cur) * qty_cur if il else (ep_cur - high_arr[i]) * qty_cur
    equity_open_arr[i] = IC + cum_pnl + urpnl_o
    equity_open_low[i] = IC + cum_pnl + urpnl_l

# Алгоритм R: HWM(open) - low
hwm_R = np.maximum.accumulate(equity_open_arr)
dd_R = hwm_R - equity_open_low
idx_R = int(np.argmax(dd_R))
print(f"R: HWM(open) - low_open: max_dd={dd_R.max():.4f}  bar={idx_R}  TV=146.99")
print(f"   HWM @ bar 6393 = {hwm_R[6393]:.4f}  TV: {tv_hwm_needed}")
print(f"   eq_open[1917] = {equity_open_arr[1917]:.4f}")
print()

# Построим все 4 equity curves
equity_close_arr = np.zeros(total_bars)
equity_high_arr = np.zeros(total_bars)
equity_low_arr = np.zeros(total_bars)
cum_pnl = 0.0
cur_t = None
for i in range(total_bars):
    if i in trade_by_exit and cur_t is not None:
        if trade_by_exit[i] is cur_t:
            cum_pnl += getattr(cur_t, "pnl", 0) or 0
            cur_t = None
    if i in trade_by_entry:
        cur_t = trade_by_entry[i]
    urpnl_c = urpnl_h = urpnl_l = urpnl_o = 0.0
    if cur_t is not None:
        ep_cur = getattr(cur_t, "entry_price", 0)
        qty_cur = getattr(cur_t, "size", 0)
        il = any(x in str(getattr(cur_t, "side", "")).lower() for x in ("buy", "long"))
        urpnl_c = (close_arr[i] - ep_cur) * qty_cur if il else (ep_cur - close_arr[i]) * qty_cur
        urpnl_h = (high_arr[i] - ep_cur) * qty_cur if il else (ep_cur - low_arr[i]) * qty_cur
        urpnl_l = (low_arr[i] - ep_cur) * qty_cur if il else (ep_cur - high_arr[i]) * qty_cur
        urpnl_o = (open_arr[i] - ep_cur) * qty_cur if il else (ep_cur - open_arr[i]) * qty_cur
    equity_close_arr[i] = IC + cum_pnl + urpnl_c
    equity_high_arr[i] = IC + cum_pnl + urpnl_h
    equity_low_arr[i] = IC + cum_pnl + urpnl_l
    equity_open_arr[i] = IC + cum_pnl + urpnl_o

# Проверим TV HWM @ bar 6393 для всех комбинаций:
print("HWM @ bar 6393 для разных equity_close sources:")
for label, arr in [
    ("close", equity_close_arr),
    ("high", equity_high_arr),
    ("low", equity_low_arr),
    ("open", equity_open_arr),
]:
    hwm = np.maximum.accumulate(arr)
    print(f"  HWM({label})[6393] = {hwm[6393]:.4f}")

print(f"\nTV HWM needed: {tv_hwm_needed}")
print()

# Главная гипотеза: TV использует equity_close для HWM НО
# НЕ включает бары где произошел вход/выход в HWM обновление
# (т.е. entry/exit bars пропускаются при обновлении HWM)
# Проверим это более детально:

# Бар 1896 — entry bar. На этом баре equity_close = 10192.8868 (urpnl=0 т.к. ep=close)
# Бар 1897..1950 — in-position bars
# Пики происходят на bars 1912, 1913, 1914, 1915

# Проверим: если TV НЕ обновляет HWM на EXIT BARS
print("HWM skip exit bars:")
hwm_skip_exit = np.zeros(total_bars)
cur_hwm = IC
for i in range(total_bars):
    if i not in trade_by_exit:
        cur_hwm = max(cur_hwm, equity_close_arr[i])
    hwm_skip_exit[i] = cur_hwm
dd_skip_exit = hwm_skip_exit - equity_low_arr
print(f"  max_dd = {dd_skip_exit.max():.4f}  TV=146.99")
print(f"  HWM @ bar 6393 = {hwm_skip_exit[6393]:.4f}")
print()

# Проверим: если TV НЕ обновляет HWM на ENTRY + EXIT BARS
print("HWM skip entry+exit bars:")
hwm_skip_ee = np.zeros(total_bars)
cur_hwm = IC
for i in range(total_bars):
    if i not in trade_by_entry and i not in trade_by_exit:
        cur_hwm = max(cur_hwm, equity_close_arr[i])
    hwm_skip_ee[i] = cur_hwm
dd_skip_ee = hwm_skip_ee - equity_low_arr
print(f"  max_dd = {dd_skip_ee.max():.4f}  TV=146.99")
print(f"  HWM @ bar 6393 = {hwm_skip_ee[6393]:.4f}")
print()

# Проверим алгоритм P (HWM(low)) более детально
hwm_P = np.maximum.accumulate(equity_low_arr)
dd_P = hwm_P - equity_low_arr
idx_P = int(np.argmax(dd_P))
print(f"P: HWM(low) - low: max_dd={dd_P.max():.4f}  bar={idx_P}  TV=146.99")
print(f"   HWM @ bar 6393 = {hwm_P[6393]:.4f}  TV: {tv_hwm_needed}")
print(f"   equity_low_arr max before 6393: {equity_low_arr[:6393].max():.4f} @ bar {equity_low_arr[:6393].argmax()}")
print()

# Проверим: TV max_drawdown_intrabar = max over bars of (HWM(close) - min_in_bar_equity_low)
# Но HWM устанавливается ТОЛЬКО когда нет открытой сделки (реализованная equity)
# Алгоритм N2: HWM = max realized equity (at exit or out-of-position)
# dd = HWM - equity_low (for ANY bar including in-position)
hwm_N2 = np.zeros(total_bars)
cur_hwm_n2 = IC
cum_pnl2 = 0.0
cur_t2 = None
for i in range(total_bars):
    if i in trade_by_exit and cur_t2 is not None:
        if trade_by_exit[i] is cur_t2:
            pnl_exit = getattr(cur_t2, "pnl", 0) or 0
            cum_pnl2 += pnl_exit
            # HWM обновляем ПОСЛЕ закрытия сделки
            cur_hwm_n2 = max(cur_hwm_n2, IC + cum_pnl2)
            cur_t2 = None
    if i in trade_by_entry:
        cur_t2 = trade_by_entry[i]
    if cur_t2 is None:
        cur_hwm_n2 = max(cur_hwm_n2, IC + cum_pnl2)
    hwm_N2[i] = cur_hwm_n2

dd_N2 = hwm_N2 - equity_low_arr
idx_N2 = int(np.argmax(dd_N2))
print(f"N2: HWM=realized(after exit) - low: max_dd={dd_N2.max():.4f}  bar={idx_N2}  TV=146.99")
print(f"    HWM @ bar 6393 = {hwm_N2[6393]:.4f}  TV: {tv_hwm_needed}")
print()

# А что если TV обновляет HWM ПРИ ВХОДЕ (включает entry bar equity)?
# В этот момент, для entry bar, equity = cum_realized (т.к. urpnl=0)
# Потом внутри позиции HWM не обновляется
# При выходе: HWM обновляется на cum_realized_after_exit

# Алгоритм O (TV hypothesis):
# HWM обновляется ТОЛЬКО при реализованных событиях:
# 1) На entry bar: HWM = max(HWM, cum_realized_before_entry)
# 2) На exit bar: HWM = max(HWM, cum_realized_after_exit)
# 3) Out of position: HWM = max(HWM, cum_realized)
# dd[i] = HWM[i] - equity_low[i]

hwm_O = np.zeros(total_bars)
cur_hwm_o = IC
cum_pnl3 = 0.0
cur_t3 = None
entry_hwm_updated: set[int] = set()
for i in range(total_bars):
    # СНАЧАЛА обрабатываем выход
    if i in trade_by_exit and cur_t3 is not None:
        if trade_by_exit[i] is cur_t3:
            pnl3 = getattr(cur_t3, "pnl", 0) or 0
            cum_pnl3 += pnl3
            cur_hwm_o = max(cur_hwm_o, IC + cum_pnl3)
            cur_t3 = None
    # Затем обрабатываем вход
    if i in trade_by_entry:
        # Перед входом: обновляем HWM на основе реализованной equity
        cur_hwm_o = max(cur_hwm_o, IC + cum_pnl3)
        cur_t3 = trade_by_entry[i]
    # Если нет позиции: обновляем HWM
    if cur_t3 is None:
        cur_hwm_o = max(cur_hwm_o, IC + cum_pnl3)
    hwm_O[i] = cur_hwm_o

dd_O = hwm_O - equity_low_arr
idx_O = int(np.argmax(dd_O))
print(f"O: HWM=realized(at events) - low: max_dd={dd_O.max():.4f}  bar={idx_O}  TV=146.99")
print(f"   HWM @ bar 6393 = {hwm_O[6393]:.4f}  TV: {tv_hwm_needed}")

# Итого, проверим промежуток между N (146.3023) и TV (146.99)
# Разница = 0.6877 = entry commission для eb=1896
# Что если TV включает equity = realized + entry_comm_paid_at_entry?
# Т.е. при входе: HWM = max(HWM, IC + cum_realized + entry_comm_of_new_trade)

ep1896 = getattr(next(t for t in closed if getattr(t, "entry_bar_index", None) == 1896), "entry_price", 0)
qty1896_val = getattr(next(t for t in closed if getattr(t, "entry_bar_index", None) == 1896), "size", 0)
entry_comm_1896 = ep1896 * qty1896_val * comm_rate

print()
print(f"entry_comm_1896 = {entry_comm_1896:.4f}")
print(f"N alg HWM = {hwm_N2[6393]:.4f}")
print(f"N alg HWM + entry_comm_1896 = {hwm_N2[6393] + entry_comm_1896:.4f}")
print(f"TV HWM = {tv_hwm_needed}")
print()

# Алгоритм S: при ВХОДЕ в позицию, HWM += entry_commission
hwm_S = np.zeros(total_bars)
cur_hwm_s = IC
cum_pnl4 = 0.0
cur_t4 = None
for i in range(total_bars):
    if i in trade_by_exit and cur_t4 is not None:
        if trade_by_exit[i] is cur_t4:
            pnl4 = getattr(cur_t4, "pnl", 0) or 0
            cum_pnl4 += pnl4
            cur_hwm_s = max(cur_hwm_s, IC + cum_pnl4)
            cur_t4 = None
    if i in trade_by_entry:
        t_new = trade_by_entry[i]
        ep_new = getattr(t_new, "entry_price", 0)
        qty_new = getattr(t_new, "size", 0)
        e_comm = ep_new * qty_new * comm_rate
        # При входе: HWM = realized + entry_comm (margin заморожена)
        cur_hwm_s = max(cur_hwm_s, IC + cum_pnl4 + e_comm)
        cur_t4 = t_new
    if cur_t4 is None:
        cur_hwm_s = max(cur_hwm_s, IC + cum_pnl4)
    hwm_S[i] = cur_hwm_s

dd_S = hwm_S - equity_low_arr
idx_S = int(np.argmax(dd_S))
print(f"S: HWM=realized+entry_comm @ entry - low: max_dd={dd_S.max():.4f}  bar={idx_S}  TV=146.99")
print(f"   HWM @ bar 6393 = {hwm_S[6393]:.4f}  TV: {tv_hwm_needed}")
print(f"   HWM @ bar 1896 (entry eb=1896): {hwm_S[1896]:.4f}")
