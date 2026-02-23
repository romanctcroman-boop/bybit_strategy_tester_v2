"""
Диагностика dd6: Когда именно TV начинает считать unrealized PnL?

Если TV вход выполняется на баре eb (на close), то unrealized начинается с eb+1.
У нас: entry_bar = eb, unrealized начинается с eb.

Т.е. на bar eb:
- Наш алгоритм: eq_close[eb] = cum + (close[eb] - ep) * qty
  Но entry_price = close[eb], значит urpnl = 0 на bar eb
- TV: тоже начинает с eb, но, возможно, на bar eb urpnl=0 (так как только что вошли)

Фактически:
- close[1896] = 87656.80 = ep1896 (подтверждено открытием dd4)
- Поэтому urpnl[1896] = 0 у нас тоже (правильно)

Тогда: TV и мы должны давать одинаковый eq_close[1913].
Но TV даёт 10193.5745, мы даём 10197.9098.

Значит HWM создаётся в другой точке или другой сделкой для TV.

Проверим: может TV вообще не использует max_drawdown = HWM - low,
а использует другое определение?

TV TradingView Pine Script max drawdown:
strategy.max_drawdown - Maximum equity drawdown value for the whole trading interval
Это может быть определено иначе чем HWM(equity_close) - min(equity_low)

Проверим: может TV считает drawdown только по close bars (без intrabar low)?
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

bar_hwm = 1913
tv_hwm_needed = 10193.5745
tv_dd = 146.99

# Построим детальный equity curve вокруг bar 1913
print("Equity close вокруг bar 1913 (наш алгоритм A):")
print(f"{'bar':>5} {'date':>25} {'eq_close':>12} {'eq_low':>12} {'note':>20}")

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
    if cur_t is not None:
        ep_cur = getattr(cur_t, "entry_price", 0)
        qty_cur = getattr(cur_t, "size", 0)
        il = any(x in str(getattr(cur_t, "side", "")).lower() for x in ("buy", "long"))
        urpnl_c = (close_arr[i] - ep_cur) * qty_cur if il else (ep_cur - close_arr[i]) * qty_cur
        urpnl_l = (low_arr[i] - ep_cur) * qty_cur if il else (ep_cur - high_arr[i]) * qty_cur
    eq_c = IC + cum_pnl + urpnl_c
    eq_l = IC + cum_pnl + urpnl_l

    if 1905 <= i <= 1920:
        note = ""
        if i in trade_by_entry:
            note = f"ENTRY eb={i}"
        elif i in trade_by_exit:
            note = f"EXIT xb={i}"
        elif cur_t is not None:
            note = f"in_trade eb={getattr(cur_t, 'entry_bar_index', 0)}"
        print(f"{i:>5} {df.index[i]!s:>25} {eq_c:>12.4f} {eq_l:>12.4f} {note:>20}")

print()

# Теперь найдём топ-5 HWM баров
equity_close_A = np.zeros(total_bars)
equity_low_A = np.zeros(total_bars)
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
    if cur_t is not None:
        ep_cur = getattr(cur_t, "entry_price", 0)
        qty_cur = getattr(cur_t, "size", 0)
        il = any(x in str(getattr(cur_t, "side", "")).lower() for x in ("buy", "long"))
        urpnl_c = (close_arr[i] - ep_cur) * qty_cur if il else (ep_cur - close_arr[i]) * qty_cur
        urpnl_l = (low_arr[i] - ep_cur) * qty_cur if il else (ep_cur - high_arr[i]) * qty_cur
    equity_close_A[i] = IC + cum_pnl + urpnl_c
    equity_low_A[i] = IC + cum_pnl + urpnl_l

# Топ-10 максимумов equity_close перед bar 6393
print("Топ-10 equity_close значений (все бары до 6393):")
idx_top = np.argsort(equity_close_A[:6393])[::-1][:10]
for i in idx_top:
    is_in_trade = i in trade_by_entry or any(
        getattr(t, "entry_bar_index", 0) <= i <= getattr(t, "exit_bar_index", 0) for t in trades_sorted
    )
    print(f"  bar={i:5d} ({df.index[i]}) eq_close={equity_close_A[i]:.4f}")

print()
print(f"TV HWM needed = {tv_hwm_needed}")
print()

# Ключевой вопрос: какой бар дает eq_close = tv_hwm_needed = 10193.5745?
# Найдём все бары где eq_close близко к 10193.5745
close_to_tv = np.where(np.abs(equity_close_A[:6393] - tv_hwm_needed) < 5.0)[0]
if len(close_to_tv) > 0:
    print(f"Бары с eq_close близким к TV HWM ({tv_hwm_needed} ± 5):")
    for i in close_to_tv:
        print(f"  bar={i:5d} ({df.index[i]}) eq_close={equity_close_A[i]:.4f}")
else:
    print("Нет баров близких к TV HWM!")

print()
print("=" * 70)
print("АНАЛИЗ: где именно мы расходимся с TV")
print("=" * 70)

# TV dd = HWM - eq_low[6393]
# eq_low[6393] = 10046.5845 (совпадает!)
# TV dd = 146.99 → TV HWM = 10193.5745
# Наш HWM = 10197.9098 (bar 1913)

# Вопрос: какое значение equity_close TV имеет на bar 1913?
# Если TV equity_close[1913] = 10193.5745, то что происходит на bar 1913?

# Проверка: может TV вход выполняется на открытии бара (не на закрытии предыдущего)?
# Т.е. TV entry_bar = bar 1897 (следующий бар после сигнала), но entryPrice = open[1897]
# Тогда на bar 1913 сделка ещё не открыта если...
# Нет, 1897 < 1913, сделка всё равно открыта

# Другая идея: TV использует entry bar = 1897 (не 1896)
# и entry_price = open[1897] = 87656.80 (совпадает с close[1896])
# Но qty = capital / open[1897] (то же самое)
# Тогда eq_close[1913] та же

# Попробуем: TV вход на bar 1897 с open[1897] = 87656.80, но
# на bar 1897 urpnl = (close[1897] - 87656.80) * qty
# vs у нас на bar 1896 urpnl = 0 (entry bar)
# Но это не влияет на bar 1913...

# Главное: что дает TV equity = 10193.5745 на bar 1913?
# 10193.5745 = cum_before_1896 + urpnl_tv[1913]
# 10193.5745 - 10192.8868 = 0.6877 = urpnl_tv[1913]
# Наш urpnl[1913] = 5.023

# Значит TV считает urpnl = 0.6877 вместо 5.023 на bar 1913?
# Это невозможно с ep=87656.80 и close=88097.10

# НОВАЯ ГИПОТЕЗА: TV HWM не равен 10193.5745
# TV просто имеет max_dd = 146.99 но пара (HWM, eq_low) другая!
# Может eq_low[6393] у TV отличается от 10046.5845?

# Вычислим: если TV HWM = наш HWM = 10197.9098, то
# TV eq_low[6393] = 10197.9098 - 146.99 = 10050.9198
eq_low_tv_if_hwm_ours = 10197.9098 - tv_dd
print("Если TV HWM = наш HWM (10197.9098):")
print(f"  TV eq_low[6393] = {eq_low_tv_if_hwm_ours:.4f}")
print(f"  Наш eq_low[6393] = {equity_low_A[6393]:.4f}")
print(f"  Разница = {equity_low_A[6393] - eq_low_tv_if_hwm_ours:.4f}")
print()

# Может TV eq_low использует другую цену (не high для шорта)?
t6324 = next((t for t in closed if getattr(t, "entry_bar_index", None) == 6324), None)
if t6324:
    ep6324 = getattr(t6324, "entry_price", 0)
    qty6324 = getattr(t6324, "size", 0)
    xb6324 = getattr(t6324, "exit_bar_index", None)
    cum_before_6324 = IC
    for t in trades_sorted:
        if getattr(t, "entry_bar_index", 0) >= 6324:
            break
        cum_before_6324 += getattr(t, "pnl", 0) or 0

    print("Bar 6393 trade info (SHORT eb=6324):")
    print(f"  ep={ep6324:.2f}, qty={qty6324:.6f}")
    print(f"  O={open_arr[6393]:.2f} H={high_arr[6393]:.2f} L={low_arr[6393]:.2f} C={close_arr[6393]:.2f}")
    print(f"  cum_before_6324 = {cum_before_6324:.4f}")
    print()

    urpnl_to_high = (ep6324 - high_arr[6393]) * qty6324  # SHORT: ep-high
    urpnl_to_open = (ep6324 - open_arr[6393]) * qty6324  # SHORT: ep-open
    urpnl_to_close = (ep6324 - close_arr[6393]) * qty6324  # SHORT: ep-close
    urpnl_to_low = (ep6324 - low_arr[6393]) * qty6324  # SHORT: ep-low (gain)

    eq_low_high = cum_before_6324 + urpnl_to_high
    eq_low_open = cum_before_6324 + urpnl_to_open
    eq_low_close = cum_before_6324 + urpnl_to_close
    eq_low_low = cum_before_6324 + urpnl_to_low

    print(f"  eq_low_to_high  = {eq_low_high:.4f}  (worst for SHORT)  ← текущий")
    print(f"  eq_low_to_open  = {eq_low_open:.4f}")
    print(f"  eq_low_to_close = {eq_low_close:.4f}")
    print(f"  eq_low_to_low   = {eq_low_low:.4f}   (best for SHORT)")
    print()

    # TV dd = 146.99: значит eq_low_tv = tv_hwm - 146.99
    # Если tv_hwm = 10197.9098: eq_low_tv = 10050.9198
    # Если tv_hwm = 10193.5745: eq_low_tv = 10046.5845 = eq_low_high !!!
    eq_low_tv = tv_hwm_needed - tv_dd
    print(f"  TV eq_low = {eq_low_tv:.4f}")
    print(f"  eq_low_to_high = {eq_low_high:.4f}  ({'✅ MATCH!' if abs(eq_low_high - eq_low_tv) < 0.01 else '❌'})")
    print()

    # Значит TV HWM = 10193.5745 и TV eq_low = 10046.5845
    # наш HWM = 10197.9098 (выше) и наш eq_low = 10046.5845 (совпадает)
    # Значит TV просто имеет МЕНЬШИЙ HWM к моменту bar 6393

    # Найдём: возможно TV не считает unrealized PnL на баре ENTRY?
    # Если TV entry bar = 1896 и не включает его в equity:
    print("=" * 70)
    print("ФИНАЛЬНАЯ ГИПОТЕЗА: TV не включает entry bar в equity HWM")
    print("Т.е. HWM обновляется только начиная с entry_bar + 1")
    print()

    # Алгоритм TV: HWM обновляется на каждом баре КРОМЕ entry bar
    equity_close_TV = np.zeros(total_bars)
    equity_low_TV = np.zeros(total_bars)
    cum_pnl2 = 0.0
    cur_t2 = None
    for i in range(total_bars):
        if i in trade_by_exit and cur_t2 is not None:
            if trade_by_exit[i] is cur_t2:
                cum_pnl2 += getattr(cur_t2, "pnl", 0) or 0
                cur_t2 = None
        if i in trade_by_entry:
            cur_t2 = trade_by_entry[i]
        urpnl_c = urpnl_l = 0.0
        if cur_t2 is not None:
            ep_cur = getattr(cur_t2, "entry_price", 0)
            qty_cur = getattr(cur_t2, "size", 0)
            il = any(x in str(getattr(cur_t2, "side", "")).lower() for x in ("buy", "long"))
            urpnl_c = (close_arr[i] - ep_cur) * qty_cur if il else (ep_cur - close_arr[i]) * qty_cur
            urpnl_l = (low_arr[i] - ep_cur) * qty_cur if il else (ep_cur - high_arr[i]) * qty_cur
        equity_close_TV[i] = IC + cum_pnl2 + urpnl_c
        equity_low_TV[i] = IC + cum_pnl2 + urpnl_l

    # HWM только на NOT entry bars
    hwm_TV = np.zeros(total_bars)
    current_hwm = IC
    for i in range(total_bars):
        if i not in trade_by_entry:
            current_hwm = max(current_hwm, equity_close_TV[i])
        hwm_TV[i] = current_hwm

    dd_TV_test = hwm_TV - equity_low_TV
    print(f"HWM skip entry bars: max_dd = {dd_TV_test.max():.4f}  TV=146.99")
    idx_tv_test = int(np.argmax(dd_TV_test))
    print(f"  worst bar: {idx_tv_test}, HWM={hwm_TV[idx_tv_test]:.4f}, eq_low={equity_low_TV[idx_tv_test]:.4f}")
    print(f"  HWM @ bar 6393: {hwm_TV[6393]:.4f}  (TV: {tv_hwm_needed})")
    print(f"  HWM @ bar 1913: {equity_close_TV[bar_hwm]:.4f} → included: {bar_hwm not in trade_by_entry}")
