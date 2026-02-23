"""
Детальная диагностика сделки на баре 6324 (short ep=93934.40).
Проверяем: как TV считает HWM и что именно даёт +4.33 разницу.
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

high_arr = df["high"].values
low_arr = df["low"].values
close_arr = df["close"].values
open_arr = df["open"].values
total_bars = len(close_arr)
initial_capital = 10000.0

# Находим сделку eb=6324
t_focus = None
for t in closed:
    if getattr(t, "entry_bar_index", None) == 6324:
        t_focus = t
        break

if t_focus is None:
    print("Сделка eb=6324 не найдена!")
    sys.exit(1)

eb = t_focus.entry_bar_index
xb = t_focus.exit_bar_index
ep = t_focus.entry_price
xp = getattr(t_focus, "exit_price", 0) or 0
qty = t_focus.size
side = getattr(t_focus, "side", "")
pnl = getattr(t_focus, "pnl", 0) or 0
mae = getattr(t_focus, "mae", 0) or 0
mfe = getattr(t_focus, "mfe", 0) or 0

print("Фокусная сделка:")
print(f"  eb={eb}, xb={xb}  ({df.index[eb]} → {df.index[xb]})")
print(f"  entry={ep:.2f}, exit={xp:.2f}, side={side}, qty={qty:.6f}")
print(f"  pnl={pnl:.4f}, MAE={mae:.4f}, MFE={mfe:.4f}")
print()

# Считаем cumulative PnL перед этой сделкой (equity_before)
trades_sorted = sorted(closed, key=lambda t: getattr(t, "entry_bar_index", 0) or 0)
cum_before = initial_capital
for t in trades_sorted:
    if getattr(t, "entry_bar_index", 0) >= eb:
        break
    cum_before += getattr(t, "pnl", 0) or 0
print(f"Equity перед сделкой: {cum_before:.4f}")
print()

# Показываем OHLC данные за время сделки + equity_low/high/close
print(
    f"{'Bar':>5} {'Timestamp':<25} {'O':>8} {'H':>8} {'L':>8} {'C':>8}  "
    f"{'eq_close':>10} {'eq_low':>10} {'eq_high':>10}  {'dd_from_hwm':>11}"
)

is_long = any(x in str(side).lower() for x in ("buy", "long"))

# Рассчитываем глобальный HWM на момент начала сделки
trade_by_entry = {}
trade_by_exit = {}
for t in closed:
    _eb = getattr(t, "entry_bar_index", None)
    _xb = getattr(t, "exit_bar_index", None)
    if _eb is not None:
        trade_by_entry[_eb] = t
    if _xb is not None:
        trade_by_exit[_xb] = t

equity_close_arr = np.zeros(total_bars)
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
    urpnl_c = 0.0
    if current_trade is not None:
        _ep = getattr(current_trade, "entry_price", 0) or 0
        _qty = getattr(current_trade, "size", 0) or 0
        _side = str(getattr(current_trade, "side", "")).lower()
        _is_long = any(x in _side for x in ("buy", "long"))
        if _is_long:
            urpnl_c = (close_arr[i] - _ep) * _qty
        else:
            urpnl_c = (_ep - close_arr[i]) * _qty
    equity_close_arr[i] = initial_capital + cum_pnl + urpnl_c

hwm_before_trade = float(np.max(equity_close_arr[:eb])) if eb > 0 else initial_capital
print(f"HWM до входа в сделку: {hwm_before_trade:.4f}")
print()

# Печатаем бары внутри сделки
hwm_running = hwm_before_trade
for i in range(max(0, eb - 2), min(total_bars, xb + 3)):
    in_trade = eb <= i <= xb
    if is_long:
        eq_c = cum_before + (close_arr[i] - ep) * qty
        eq_l = cum_before + (low_arr[i] - ep) * qty
        eq_h = cum_before + (high_arr[i] - ep) * qty
    else:
        eq_c = cum_before + (ep - close_arr[i]) * qty
        eq_l = cum_before + (ep - high_arr[i]) * qty  # worst for short
        eq_h = cum_before + (ep - low_arr[i]) * qty  # best for short

    if in_trade:
        hwm_running = max(hwm_running, eq_c)
        dd = hwm_running - eq_l
    else:
        dd = 0.0

    marker = "◀ WORST" if abs(dd - 151.3253) < 0.01 else ("←entry" if i == eb else ("←exit" if i == xb else ""))
    if in_trade or i in (eb - 1, eb - 2):
        print(
            f"  {i:5d} {df.index[i]!s:<25} {open_arr[i]:8.2f} {high_arr[i]:8.2f} {low_arr[i]:8.2f} {close_arr[i]:8.2f}  "
            f"{eq_c:10.4f} {eq_l:10.4f} {eq_h:10.4f}  {dd:11.4f}  {marker}"
        )

print()
print("=" * 60)
print("Гипотезы расхождения:")
print()

# Гипотеза 1: TV использует Open вместо Low на баре входа
if is_long:
    eq_l_entry_open = cum_before + (open_arr[eb] - ep) * qty
else:
    eq_l_entry_open = cum_before + (ep - open_arr[eb]) * qty
print(f"H1: на баре входа (eb={eb}) worst = open_price вместо low/high:")
print(f"    open={open_arr[eb]:.2f}, ep={ep:.2f}")
print(f"    equity_worst_with_open = {eq_l_entry_open:.4f}")
print()

# Гипотеза 2: TV включает комиссию в equity перед расчётом HWM
comm_entry = ep * qty * 0.0007
print("H2: TV вычитает комиссию входа из equity_before:")
print(f"    comm_entry = {comm_entry:.4f}")
print(f"    equity_after_comm = {cum_before - comm_entry:.4f}")
print("    (это смещает HWM вниз, уменьшая drawdown)")
print()

# Гипотеза 3: TV считает HWM включая открытую сделку на ВЫСОКОМ (best)
# На баре перед максимальным drawdown — был ли предыдущий HWM создан intrabar high?
# Найдём бар где достигается HWM=10197.91
hwm_target = 10197.9098
for i in range(total_bars):
    if abs(equity_close_arr[i] - hwm_target) < 1.0:
        print(f"H3: HWM {hwm_target:.4f} достигается на баре {i} ({df.index[i]})")
        # Проверим intrabar high на этом баре
        _t_at = None
        for t in closed:
            _eb = getattr(t, "entry_bar_index", 0) or 0
            _xb = getattr(t, "exit_bar_index", 0) or 0
            if _eb <= i <= _xb:
                _t_at = t
                break
        if _t_at:
            _ep2 = getattr(_t_at, "entry_price", 0) or 0
            _qty2 = getattr(_t_at, "size", 0) or 0
            _side2 = str(getattr(_t_at, "side", "")).lower()
            _long2 = any(x in _side2 for x in ("buy", "long"))
            cum_at = initial_capital
            for t2 in trades_sorted:
                if getattr(t2, "entry_bar_index", 0) >= getattr(_t_at, "entry_bar_index", 0):
                    break
                cum_at += getattr(t2, "pnl", 0) or 0
            if _long2:
                eq_high_at = cum_at + (high_arr[i] - _ep2) * _qty2
            else:
                eq_high_at = cum_at + (_ep2 - low_arr[i]) * _qty2
            eq_close_at = equity_close_arr[i]
            print(
                f"    trade eb={getattr(_t_at, 'entry_bar_index', None)} side={getattr(_t_at, 'side', '')} ep={_ep2:.2f}"
            )
            print(f"    eq_close[{i}] = {eq_close_at:.4f}")
            print(f"    eq_high[{i}]  = {eq_high_at:.4f}  (если TV использует intrabar high для HWM)")
            diff_if_high = eq_high_at - hwm_target
            print(f"    Разница HWM если high: {diff_if_high:+.4f}")
            if eq_high_at < hwm_target - 0.01:
                print(f"    => HWM={hwm_target:.4f} создаётся НЕ intrabar high, а eq_close на другом баре")
        break
