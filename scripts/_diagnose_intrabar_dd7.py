"""
Диагностика dd7: TV HWM = max(equity_low) вместо max(equity_close)?
или TV HWM = min(equity_high, equity_low)?

Подсказка: TV HWM = 10193.5745
Наш equity_low[1913] = 10193.7470  (close bar to TV!)

Также проверим: TV max_drawdown = max(HWM(equity_low) - equity_low)?
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

trade_by_entry = {getattr(t, "entry_bar_index", 0): t for t in trades_sorted}
trade_by_exit = {getattr(t, "exit_bar_index", 0): t for t in trades_sorted}

tv_hwm_needed = 10193.5745
tv_dd = 146.99
bar_hwm = 1913

# Построим equity_close, equity_high, equity_low, equity_open
equity_close = np.zeros(total_bars)
equity_high = np.zeros(total_bars)  # LONG: equity_at_high, SHORT: equity_at_low_of_bar
equity_low = np.zeros(total_bars)  # LONG: equity_at_low, SHORT: equity_at_high_of_bar
equity_open = np.zeros(total_bars)

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
        # LONG: profit when price goes up → best at high, worst at low
        # SHORT: profit when price goes down → best at low, worst at high
        urpnl_c = (close_arr[i] - ep_cur) * qty_cur if il else (ep_cur - close_arr[i]) * qty_cur
        urpnl_h = (high_arr[i] - ep_cur) * qty_cur if il else (ep_cur - low_arr[i]) * qty_cur
        urpnl_l = (low_arr[i] - ep_cur) * qty_cur if il else (ep_cur - high_arr[i]) * qty_cur
        urpnl_o = (open_arr[i] - ep_cur) * qty_cur if il else (ep_cur - open_arr[i]) * qty_cur
    equity_close[i] = IC + cum_pnl + urpnl_c
    equity_high[i] = IC + cum_pnl + urpnl_h
    equity_low[i] = IC + cum_pnl + urpnl_l
    equity_open[i] = IC + cum_pnl + urpnl_o

print("Bar 1913 values:")
print(f"  equity_open  = {equity_open[bar_hwm]:.4f}")
print(f"  equity_high  = {equity_high[bar_hwm]:.4f}")
print(f"  equity_low   = {equity_low[bar_hwm]:.4f}  ← очень близко к TV HWM: {tv_hwm_needed}")
print(f"  equity_close = {equity_close[bar_hwm]:.4f}")
print(f"  TV HWM needed= {tv_hwm_needed}")
print(f"  equity_low vs TV: {equity_low[bar_hwm] - tv_hwm_needed:.4f}")
print()

# Вычислим все алгоритмы
print("=" * 70)

# Алгоритм A (текущий): HWM(close) - low
hwm_A = np.maximum.accumulate(equity_close)
dd_A = hwm_A - equity_low
idx_A = int(np.argmax(dd_A))
print(f"A: HWM(close) - low:           max_dd={dd_A.max():.4f}  bar={idx_A}  TV=146.99")

# Алгоритм K: HWM(high) - low  (используем equity_high для HWM)
hwm_K = np.maximum.accumulate(equity_high)
dd_K = hwm_K - equity_low
idx_K = int(np.argmax(dd_K))
print(f"K: HWM(high) - low:            max_dd={dd_K.max():.4f}  bar={idx_K}  TV=146.99")
print(f"   HWM @ bar 6393 = {hwm_K[6393]:.4f}  TV needed: {tv_hwm_needed}")

# Алгоритм L: HWM(max(close,low)) - low
equity_cl_max = np.maximum(equity_close, equity_low)
hwm_L = np.maximum.accumulate(equity_cl_max)
dd_L = hwm_L - equity_low
idx_L = int(np.argmax(dd_L))
print(f"L: HWM(max(close,low)) - low:  max_dd={dd_L.max():.4f}  bar={idx_L}  TV=146.99")

# Алгоритм M: HWM(min(close,high)) - low
# TV может использовать пессимистическое значение для HWM
equity_ch_min = np.minimum(equity_close, equity_high)
hwm_M = np.maximum.accumulate(equity_ch_min)
dd_M = hwm_M - equity_low
idx_M = int(np.argmax(dd_M))
print(f"M: HWM(min(close,high)) - low: max_dd={dd_M.max():.4f}  bar={idx_M}  TV=146.99")
print(f"   equity_ch_min[1913] = {equity_ch_min[bar_hwm]:.4f}")
print(f"   HWM @ bar 1913 = {equity_close[bar_hwm]:.4f} vs min(close,high)={equity_ch_min[bar_hwm]:.4f}")
print(f"   HWM @ bar 6393 = {hwm_M[6393]:.4f}  TV needed: {tv_hwm_needed}")
print()

# Алгоритм N: HWM обновляется только на EXIT барах
hwm_N = np.zeros(total_bars)
cur_hwm = IC
# HWM обновляется при каждом закрытии сделки + out-of-position bars
cum_pnl2 = 0.0
cur_t2 = None
for i in range(total_bars):
    if i in trade_by_exit and cur_t2 is not None:
        if trade_by_exit[i] is cur_t2:
            cum_pnl2 += getattr(cur_t2, "pnl", 0) or 0
            cur_hwm = max(cur_hwm, IC + cum_pnl2)
            cur_t2 = None
    if i in trade_by_entry:
        cur_t2 = trade_by_entry[i]
    if cur_t2 is None:
        # Out of position: update HWM with realized equity
        cur_hwm = max(cur_hwm, IC + cum_pnl2)
    hwm_N[i] = cur_hwm

dd_N = hwm_N - equity_low
idx_N = int(np.argmax(dd_N))
print(f"N: HWM only at exits/OoP:      max_dd={dd_N.max():.4f}  bar={idx_N}  TV=146.99")
print(f"   HWM @ bar 6393 = {hwm_N[6393]:.4f}  TV needed: {tv_hwm_needed}")
print()

# Ключевое наблюдение: equity_low[1913] = 10193.7470 ≈ 10193.5745 (diff = 0.1725)
# Что если TV считает equity_high = best unrealized (для шорта = ep-low)?
# А для HWM использует equity_high (best case)?
# Нет, это не имеет смысла...

# Анализ equity_low[1913]:
# t1896 is LONG, ep=87656.80, qty=0.011408
# equity_low[1913] = cum_before_1896 + (low[1913] - ep) * qty
# = 10192.8868 + (87732.20 - 87656.80) * 0.011408
# = 10192.8868 + 75.40 * 0.011408
# = 10192.8868 + 0.8602
# = 10193.7470
t1896 = next(t for t in closed if getattr(t, "entry_bar_index", None) == 1896)
ep1896 = getattr(t1896, "entry_price", 0)
qty1896 = getattr(t1896, "size", 0)
cum_before_1896 = IC
for t in trades_sorted:
    if getattr(t, "entry_bar_index", 0) >= 1896:
        break
    cum_before_1896 += getattr(t, "pnl", 0) or 0

print("Детальный расчёт equity_low[1913]:")
print(f"  cum_before_1896 = {cum_before_1896:.4f}")
print(f"  low[1913] = {low_arr[bar_hwm]:.2f},  ep1896 = {ep1896:.2f}")
print(f"  (low-ep)*qty = {(low_arr[bar_hwm] - ep1896) * qty1896:.4f}")
print(f"  equity_low[1913] = {equity_low[bar_hwm]:.4f}")
print(f"  TV HWM needed    = {tv_hwm_needed}")
print(f"  Разница          = {equity_low[bar_hwm] - tv_hwm_needed:.4f}")
print()

# А что если TV HWM = equity_low (т.е. TV считает drawdown как сколько упала low от HWM(low))?
# HWM = max(equity_low), dd = HWM - equity_low
# Это как "максимальный откат от ранее достигнутого low"
# Это нелогично но проверим
hwm_P = np.maximum.accumulate(equity_low)
dd_P = hwm_P - equity_low
idx_P = int(np.argmax(dd_P))
print(f"P: HWM(low) - low:             max_dd={dd_P.max():.4f}  bar={idx_P}  TV=146.99")
print(f"   HWM @ bar 6393 = {hwm_P[6393]:.4f}  TV needed: {tv_hwm_needed}")
print()

# Алгоритм Q: TV использует max(equity_open, equity_close) для HWM
equity_oc_max = np.maximum(equity_open, equity_close)
hwm_Q = np.maximum.accumulate(equity_oc_max)
dd_Q = hwm_Q - equity_low
idx_Q = int(np.argmax(dd_Q))
print(f"Q: HWM(max(open,close)) - low: max_dd={dd_Q.max():.4f}  bar={idx_Q}  TV=146.99")
print(f"   HWM @ bar 6393 = {hwm_Q[6393]:.4f}  TV needed: {tv_hwm_needed}")
print()

# Алгоритм R: equity_high для SHORT и equity_close для LONG (лучшее unrealized)
# Нет - это не имеет смысла для HWM

# ФИНАЛЬНАЯ проверка: разложим проблему с другой стороны
# TV dd = 146.99, наш dd = 151.3253, разница = 4.3353
# eq_low[6393] оба: 10046.5845 (совпадает!)
# Значит у TV HWM = 10193.5745, у нас = 10197.9098
# Разница HWM = 4.3353

# Что дает 4.3353?
# Посмотрим: у нас equity_close[1912] = 10195.0806
# Это ближе к TV HWM (разница = 10195.0806 - 10193.5745 = 1.5061)

# Что если TV HWM устанавливается на EXIT предыдущей сделки?
# Предыдущая сделка перед eb=1896 закрылась на... найдём
prev_t = None
for t in trades_sorted:
    if getattr(t, "entry_bar_index", 0) >= 1896:
        break
    prev_t = t
if prev_t:
    xb_prev = getattr(prev_t, "exit_bar_index", 0)
    pnl_prev = getattr(prev_t, "pnl", 0)
    print(f"Предыдущая сделка: eb={getattr(prev_t, 'entry_bar_index', 0)} xb={xb_prev} pnl={pnl_prev:.4f}")
    print(f"  equity at exit bar = {equity_close[xb_prev]:.4f}")
    print(f"  cum_before_1896 = {cum_before_1896:.4f}")
    print(f"  equity_high[xb_prev] = {equity_high[xb_prev]:.4f}")
    print()

# Посмотрим все значения equity_close[1893:1920] детально
print("Детальный equity[1893:1920]:")
print(f"{'bar':>5} {'eq_high':>12} {'eq_close':>12} {'eq_low':>12} {'is_entry':>8} {'is_exit':>7}")
for i in range(1893, 1920):
    note = "ENTRY" if i in trade_by_entry else ("EXIT" if i in trade_by_exit else "")
    print(f"{i:>5} {equity_high[i]:>12.4f} {equity_close[i]:>12.4f} {equity_low[i]:>12.4f} {note:>15}")
