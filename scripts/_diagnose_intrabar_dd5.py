"""
Диагностика dd5: TV вычитает комиссию входа из equity при расчёте HWM?
Анализируем точный расчёт equity_close[1913] с разными моделями комиссий.

HWM нужен: 10193.5745
Наш HWM:   10197.9098
Разница:    4.3353

cum_before_1896 = 10192.8868 (реализованный + IC, без торговли eb=1896)
ep1896 = 87656.80, qty1896 = 0.011408
close[1913] = 88097.10

urpnl_gross = (88097.10 - 87656.80) * 0.011408 = 5.0230

Наш алгоритм: eq = IC + cum_realized + urpnl_gross
TV нужен:     10193.5745 = cum_before_1896 + ?

? = 10193.5745 - 10192.8868 = 0.6877

Значит TV добавляет только 0.6877 к realized_equity в момент бара 1913.

Проверяем: 0.6877 = ?
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

t1896 = next((t for t in closed if getattr(t, "entry_bar_index", None) == 1896), None)
ep1896 = getattr(t1896, "entry_price", 0)
xp1896 = getattr(t1896, "exit_price", 0)
qty1896 = getattr(t1896, "size", 0)
xb1896 = getattr(t1896, "exit_bar_index", None)

cum_before_1896 = IC
for t in trades_sorted:
    if getattr(t, "entry_bar_index", 0) >= 1896:
        break
    cum_before_1896 += getattr(t, "pnl", 0) or 0

bar_hwm = 1913

# Комиссии для сделки 1896
entry_comm_1896 = ep1896 * qty1896 * comm_rate
exit_comm_1896 = xp1896 * qty1896 * comm_rate
total_comm_1896 = entry_comm_1896 + exit_comm_1896
gross_pnl_1896 = (xp1896 - ep1896) * qty1896  # LONG

print("=" * 70)
print("АНАЛИЗ TRADE eb=1896 (LONG)")
print("=" * 70)
print(f"ep={ep1896:.2f}, xp={xp1896:.2f}, qty={qty1896:.6f}, xb={xb1896}")
print(f"entry_comm = {entry_comm_1896:.4f}")
print(f"exit_comm  = {exit_comm_1896:.4f}")
print(f"total_comm = {total_comm_1896:.4f}")
print(f"gross_pnl  = {gross_pnl_1896:.4f}")
print(f"net_pnl    = {gross_pnl_1896 - total_comm_1896:.4f}")
print()

print("=" * 70)
print("КЛЮЧЕВЫЕ ЗНАЧЕНИЯ ДЛЯ BAR 1913")
print("=" * 70)
print(f"close[1913] = {close_arr[bar_hwm]:.2f}")
print(f"cum_before_1896 = {cum_before_1896:.4f}")
print(f"urpnl_gross[1913] = (close-ep)*qty = {(close_arr[bar_hwm] - ep1896) * qty1896:.4f}")
print()

tv_hwm_needed = 10193.5745
missing = tv_hwm_needed - cum_before_1896
print(f"TV HWM needed    = {tv_hwm_needed}")
print(f"our realized HWM = {cum_before_1896:.4f}")
print(f"Gap (TV - ours)  = {missing:.4f}")
print()

# Гипотезы что добавляет TV к realized equity:
print("ГИПОТЕЗЫ что TV добавляет к realized equity при открытой позиции:")
print(
    f"  entry_comm_1896            = {entry_comm_1896:.4f}  ({'✅' if abs(entry_comm_1896 - missing) < 0.01 else '❌'})"
)
print(
    f"  exit_comm_1896             = {exit_comm_1896:.4f}  ({'✅' if abs(exit_comm_1896 - missing) < 0.01 else '❌'})"
)
print(
    f"  total_comm_1896            = {total_comm_1896:.4f}  ({'✅' if abs(total_comm_1896 - missing) < 0.01 else '❌'})"
)
print()

# TV equity = IC + cum_realized + urpnl_gross - entry_comm?
eq_tv_v1 = cum_before_1896 + (close_arr[bar_hwm] - ep1896) * qty1896 - entry_comm_1896
print(f"TV_eq_v1 (gross - entry_comm)    = {eq_tv_v1:.4f}  TV: {tv_hwm_needed}")

# TV equity = IC + cum_realized + urpnl_gross - total_comm?
eq_tv_v2 = cum_before_1896 + (close_arr[bar_hwm] - ep1896) * qty1896 - total_comm_1896
print(f"TV_eq_v2 (gross - total_comm)    = {eq_tv_v2:.4f}  TV: {tv_hwm_needed}")

# TV equity (net) = cum_realized + (close-ep)*qty - entry_comm
# т.е. уже учтена entry_comm в unrealized
# urpnl_net = (close-ep)*qty - entry_comm_at_current_price?
exit_comm_at_close = close_arr[bar_hwm] * qty1896 * comm_rate
eq_tv_v3 = cum_before_1896 + (close_arr[bar_hwm] - ep1896) * qty1896 - entry_comm_1896 - exit_comm_at_close
print(f"TV_eq_v3 (gross - both comms at close) = {eq_tv_v3:.4f}  TV: {tv_hwm_needed}")

print()

# Попробуем найти какое значение X решает уравнение:
# cum_before_1896 + X * (close[1913] - ep1896) * qty1896 = tv_hwm_needed
# X = (tv_hwm_needed - cum_before_1896) / ((close[1913] - ep1896) * qty1896)
urpnl_gross_bar = (close_arr[bar_hwm] - ep1896) * qty1896
X = missing / urpnl_gross_bar
print(f"Для eq={tv_hwm_needed}: нужно urpnl * {X:.6f}")
print(f"  Это означает fraction = {X:.6f} от gross urpnl")
print()

# А что если TV считает unrealized как (close-ep)*qty но вычитает entry_comm ДО unrealized?
# т.е. cum_tv = cum_realized - entry_comm_1896 + gross_urpnl
eq_tv_v4 = (cum_before_1896 - entry_comm_1896) + urpnl_gross_bar
print(f"TV_eq_v4 (cum_realized - entry_comm + gross_urpnl) = {eq_tv_v4:.4f}  TV: {tv_hwm_needed}")

# А если в cum_before_1896 УЖЕ включена entry_comm как расход?
# Посмотрим pnl предыдущих трейдов детально
print()
print("=" * 70)
print("ПРОВЕРЯЕМ: что входит в cum_before_1896")
print("=" * 70)
cum_check = IC
for t in trades_sorted:
    eb_t = getattr(t, "entry_bar_index", 0)
    if eb_t >= 1896:
        break
    pnl = getattr(t, "pnl", 0) or 0
    cum_check += pnl
print(f"cum_before_1896 (sum of pnl) = {cum_check:.4f}")
print()

# Сравним с тем как engine хранит cum_pnl
# Проверим первые несколько сделок
print("Первые 3 сделки до eb=1896:")
for t in trades_sorted[:3]:
    ep_t = getattr(t, "entry_price", 0)
    xp_t = getattr(t, "exit_price", 0)
    qty_t = getattr(t, "size", 0)
    pnl_t = getattr(t, "pnl", 0) or 0
    gross_t = (xp_t - ep_t) * qty_t
    comm_t = (ep_t + xp_t) * qty_t * comm_rate
    side_t = getattr(t, "side", "")
    print(
        f"  eb={getattr(t, 'entry_bar_index', 0)} pnl={pnl_t:.4f} gross={gross_t:.4f} comm={comm_t:.4f} side={side_t}"
    )

print()
print("=" * 70)
print("ПОЛНЫЙ EQUITY CURVE C РАЗНЫМИ МОДЕЛЯМИ КОМИССИЙ")
print("=" * 70)

# Модель A (текущая): eq = IC + cum_net_pnl + urpnl_gross
# Модель F: eq = IC + cum_net_pnl + urpnl_net (= urpnl_gross - entry_comm)
# Модель G: eq = IC + cum_net_pnl + urpnl_gross - entry_comm_open

# Построим equity curves
equity_close_A = np.zeros(total_bars)
equity_low_A = np.zeros(total_bars)
equity_close_F = np.zeros(total_bars)
equity_low_F = np.zeros(total_bars)
equity_close_G = np.zeros(total_bars)
equity_low_G = np.zeros(total_bars)

trade_by_entry = {getattr(t, "entry_bar_index", 0): t for t in trades_sorted}
trade_by_exit = {getattr(t, "exit_bar_index", 0): t for t in trades_sorted}

cum_pnl = 0.0
cur_t = None

for i in range(total_bars):
    # Закрытие
    if i in trade_by_exit and cur_t is not None:
        if trade_by_exit[i] is cur_t:
            cum_pnl += getattr(cur_t, "pnl", 0) or 0
            cur_t = None
    # Открытие
    if i in trade_by_entry:
        cur_t = trade_by_entry[i]

    urpnl_c = urpnl_l = 0.0
    entry_comm_open = 0.0
    if cur_t is not None:
        ep_cur = getattr(cur_t, "entry_price", 0)
        qty_cur = getattr(cur_t, "size", 0)
        il = any(x in str(getattr(cur_t, "side", "")).lower() for x in ("buy", "long"))
        entry_comm_open = ep_cur * qty_cur * comm_rate
        urpnl_c = (close_arr[i] - ep_cur) * qty_cur if il else (ep_cur - close_arr[i]) * qty_cur
        urpnl_l = (low_arr[i] - ep_cur) * qty_cur if il else (ep_cur - high_arr[i]) * qty_cur

    equity_close_A[i] = IC + cum_pnl + urpnl_c
    equity_low_A[i] = IC + cum_pnl + urpnl_l
    # Модель F: вычитаем entry_comm из unrealized (эмулируем TV)
    equity_close_F[i] = IC + cum_pnl + urpnl_c - entry_comm_open
    equity_low_F[i] = IC + cum_pnl + urpnl_l - entry_comm_open
    # Модель G: HWM от F, но dd к low F
    equity_close_G[i] = IC + cum_pnl + urpnl_c - entry_comm_open
    equity_low_G[i] = IC + cum_pnl + urpnl_l - entry_comm_open

# A
hwm_A = np.maximum.accumulate(equity_close_A)
dd_A = hwm_A - equity_low_A
print(f"A (текущий):                    max_dd={dd_A.max():.4f}  TV=146.99")

# F
hwm_F = np.maximum.accumulate(equity_close_F)
dd_F = hwm_F - equity_low_F
print(f"F (urpnl - entry_comm):         max_dd={dd_F.max():.4f}  TV=146.99")
idx_F = int(np.argmax(dd_F))
print(f"  worst bar F: {idx_F}, HWM={hwm_F[idx_F]:.4f}, eq_low={equity_low_F[idx_F]:.4f}")
print(f"  HWM @ bar 1913: {equity_close_F[bar_hwm]:.4f}  (TV: {tv_hwm_needed})")
print(f"  HWM @ bar 6393: {hwm_F[6393]:.4f}  (TV: {tv_hwm_needed})")
print()

# Теперь попробуем: equity включает entry_comm но без exit_comm в unrealized
# tv_eq = IC + cum_net + urpnl_gross - entry_comm_pending
# Т.е. entry_comm уже уплачена (и учтена в cum_net нет, она в pending)
# Когда позиция открыта: TV вычитает entry_comm из equity сразу при входе
# Идея: TV subtracts BOTH entry_comm and exit_comm from equity (как маржинальный учёт)
# urpnl_tv = (close - ep) * qty - entry_comm - exit_comm_at_close
equity_close_H2 = np.zeros(total_bars)
equity_low_H2 = np.zeros(total_bars)
cum_pnl = 0.0
cur_t = None
for i in range(total_bars):
    if i in trade_by_exit and cur_t is not None:
        if trade_by_exit[i] is cur_t:
            cum_pnl += getattr(cur_t, "pnl", 0) or 0
            cur_t = None
    if i in trade_by_entry:
        cur_t = trade_by_entry[i]
    urpnl_c = urpnl_l = 0.0
    entry_comm_open = 0.0
    if cur_t is not None:
        ep_cur = getattr(cur_t, "entry_price", 0)
        qty_cur = getattr(cur_t, "size", 0)
        il = any(x in str(getattr(cur_t, "side", "")).lower() for x in ("buy", "long"))
        entry_comm_open = ep_cur * qty_cur * comm_rate
        exit_comm_c = close_arr[i] * qty_cur * comm_rate
        exit_comm_l = (low_arr[i] if il else high_arr[i]) * qty_cur * comm_rate
        urpnl_c = (
            (close_arr[i] - ep_cur) * qty_cur - entry_comm_open - exit_comm_c
            if il
            else (ep_cur - close_arr[i]) * qty_cur - entry_comm_open - exit_comm_c
        )
        urpnl_l = (
            (low_arr[i] - ep_cur) * qty_cur - entry_comm_open - exit_comm_l
            if il
            else (ep_cur - high_arr[i]) * qty_cur - entry_comm_open - exit_comm_l
        )
    equity_close_H2[i] = IC + cum_pnl + urpnl_c
    equity_low_H2[i] = IC + cum_pnl + urpnl_l

hwm_H2 = np.maximum.accumulate(equity_close_H2)
dd_H2 = hwm_H2 - equity_low_H2
print(f"H2 (urpnl - entry - exit_comm_dynamic): max_dd={dd_H2.max():.4f}  TV=146.99")
idx_H2 = int(np.argmax(dd_H2))
print(f"  HWM @ bar 1913: {equity_close_H2[bar_hwm]:.4f}  (TV: {tv_hwm_needed})")
print(f"  HWM @ bar 6393: {hwm_H2[6393]:.4f}  (TV: {tv_hwm_needed})")
print()

# Отладка: что именно на bar 6393 у TV
t6324 = next((t for t in closed if getattr(t, "entry_bar_index", None) == 6324), None)
if t6324:
    ep6324 = getattr(t6324, "entry_price", 0)
    qty6324 = getattr(t6324, "size", 0)
    xb6324 = getattr(t6324, "exit_bar_index", None)
    is_long6324 = any(x in str(getattr(t6324, "side", "")).lower() for x in ("buy", "long"))
    print("=" * 70)
    print("Trade eb=6324 (SHORT) @ bar 6393:")
    print(f"  ep={ep6324:.2f}, qty={qty6324:.6f}, xb={xb6324}")
    print(f"  high[6393]={high_arr[6393]:.2f}, low[6393]={low_arr[6393]:.2f}")
    urpnl_worst = (ep6324 - high_arr[6393]) * qty6324  # SHORT
    entry_comm_6324 = ep6324 * qty6324 * comm_rate
    exit_comm_h = high_arr[6393] * qty6324 * comm_rate
    print(f"  urpnl_gross(short, to high) = {urpnl_worst:.4f}")
    print(f"  entry_comm_6324 = {entry_comm_6324:.4f}")
    print(f"  exit_comm_at_high = {exit_comm_h:.4f}")

    cum_before_6324 = IC
    for t in trades_sorted:
        if getattr(t, "entry_bar_index", 0) >= 6324:
            break
        cum_before_6324 += getattr(t, "pnl", 0) or 0

    eq_low_6393_A = cum_before_6324 + urpnl_worst
    eq_low_6393_F = cum_before_6324 + urpnl_worst - entry_comm_6324
    eq_low_6393_H2 = cum_before_6324 + urpnl_worst - entry_comm_6324 - exit_comm_h
    print(f"  eq_low[6393] model A  = {IC + eq_low_6393_A:.4f}")
    print(f"  eq_low[6393] model F  = {IC + eq_low_6393_F:.4f}")
    print(f"  eq_low[6393] model H2 = {IC + eq_low_6393_H2:.4f}")
    print()
    print(f"  TV dd = 146.99  → eq_low_tv = {tv_hwm_needed - 146.99:.4f}")
    print(f"  Our eq_low[6393] (A)  = {equity_low_A[6393]:.4f}")
    print(f"  Our eq_low[6393] (F)  = {equity_low_F[6393]:.4f}")
    print(f"  Our eq_low[6393] (H2) = {equity_low_H2[6393]:.4f}")
