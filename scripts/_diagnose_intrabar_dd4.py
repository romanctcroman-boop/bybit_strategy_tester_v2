"""
Финальная диагностика: TV использует open[eb+1] как entry_price?
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

t1896 = next((t for t in closed if getattr(t, "entry_bar_index", None) == 1896), None)
ep1896 = getattr(t1896, "entry_price", 0)
qty1896 = getattr(t1896, "size", 0)
xb1896 = getattr(t1896, "exit_bar_index", None)
is_long1896 = any(x in str(getattr(t1896, "side", "")).lower() for x in ("buy", "long"))

cum_before_1896 = IC
for t in trades_sorted:
    if getattr(t, "entry_bar_index", 0) >= 1896:
        break
    cum_before_1896 += getattr(t, "pnl", 0) or 0

bar_hwm = 1913
print(
    f"Бар {bar_hwm} ({df.index[bar_hwm]}): "
    f"O={open_arr[bar_hwm]:.2f} H={high_arr[bar_hwm]:.2f} L={low_arr[bar_hwm]:.2f} C={close_arr[bar_hwm]:.2f}"
)
print(f"cum_before_1896 = {cum_before_1896:.4f}")
print(f"ep1896={ep1896:.2f}, qty1896={qty1896:.6f}, xb={xb1896}")
print()

# Наша eq_close[1913]
eq_c_ours = cum_before_1896 + (close_arr[bar_hwm] - ep1896) * qty1896
print(f"eq_close[1913] (ours)    = {eq_c_ours:.4f}  (matches 10197.9098)")
print(f"TV needed HWM            = 10193.5745")
print(f"Difference               = {eq_c_ours - 10193.5745:.4f}")
print()

# Гипотеза: TV entry_price = open[eb+1] (following bar open)
open_eb_plus1 = open_arr[1897]
print(f"open[1897] = {open_eb_plus1:.2f}  (следующий бар после сигнала)")
print(f"ep1896 (ours) = {ep1896:.2f}")
print(f"Разница entry prices: {ep1896 - open_eb_plus1:.2f}")

# TV qty с другим entry_price (same capital allocation)
qty_tv = 10000.0 * 0.1 * 10.0 / open_eb_plus1
print(f"qty_tv = {qty_tv:.6f}  (ours={qty1896:.6f})")

eq_c_tv_ep = cum_before_1896 + (close_arr[bar_hwm] - open_eb_plus1) * qty_tv
print(f"eq_close[1913] с TV entry+qty: {eq_c_tv_ep:.4f}  (TV: 10193.5745)")
print()

# Теперь проверим для worst bar 6393 с TV entry_price
# Нужно пересчитать ВСЕХ 128 сделок с TV entry_price (open[eb+1])
# и построить новый equity curve

print("=" * 60)
print("Пересчёт equity curve с TV entry_price = open[eb+1]")
print()

# Строим equity curve с TV entry_prices
trade_by_entry_tv = {}
trade_by_exit_tv = {}
tv_trades = []
cum_tv = IC
for t in trades_sorted:
    eb_t = getattr(t, "entry_bar_index", None)
    xb_t = getattr(t, "exit_bar_index", None)
    if eb_t is None or xb_t is None:
        continue
    side_t = getattr(t, "side", "")
    is_long_t = any(x in str(side_t).lower() for x in ("buy", "long"))

    # TV entry = open[eb+1] (next bar)
    ep_tv_t = open_arr[min(eb_t + 1, total_bars - 1)]
    qty_tv_t = 10000.0 * 0.1 * 10.0 / ep_tv_t

    # TV exit = как у нас (close or TP/SL hit)
    # Для простоты используем наш exit_price но с TV entry/qty
    xp_t = getattr(t, "exit_price", 0) or 0
    comm_rate = 0.0007
    if is_long_t:
        gross_tv = (xp_t - ep_tv_t) * qty_tv_t
    else:
        gross_tv = (ep_tv_t - xp_t) * qty_tv_t
    pnl_tv = gross_tv - (ep_tv_t * qty_tv_t + xp_t * qty_tv_t) * comm_rate

    tv_trades.append(
        {
            "eb": eb_t,
            "xb": xb_t,
            "ep": ep_tv_t,
            "xp": xp_t,
            "qty": qty_tv_t,
            "pnl": pnl_tv,
            "side": side_t,
            "is_long": is_long_t,
        }
    )

trade_by_entry_tv = {t["eb"]: t for t in tv_trades}
trade_by_exit_tv = {t["xb"]: t for t in tv_trades}

equity_close_tv = np.zeros(total_bars)
equity_low_tv = np.zeros(total_bars)
cum_pnl_tv = 0.0
cur_t_tv = None
for i in range(total_bars):
    if i in trade_by_exit_tv and cur_t_tv is not None:
        if trade_by_exit_tv[i] is cur_t_tv:
            cum_pnl_tv += cur_t_tv["pnl"]
            cur_t_tv = None
    if i in trade_by_entry_tv:
        cur_t_tv = trade_by_entry_tv[i]
    urpnl_c = urpnl_l = 0.0
    if cur_t_tv is not None:
        ep = cur_t_tv["ep"]
        qty = cur_t_tv["qty"]
        il = cur_t_tv["is_long"]
        urpnl_c = (close_arr[i] - ep) * qty if il else (ep - close_arr[i]) * qty
        urpnl_l = (low_arr[i] - ep) * qty if il else (ep - high_arr[i]) * qty
    equity_close_tv[i] = IC + cum_pnl_tv + urpnl_c
    equity_low_tv[i] = IC + cum_pnl_tv + urpnl_l

hwm_tv = np.maximum.accumulate(equity_close_tv)
dd_tv = hwm_tv - equity_low_tv
print(f"max_drawdown_intrabar_value (TV entry prices): {dd_tv.max():.4f}  TV=146.99")
idx_tv = int(np.argmax(dd_tv))
print(f"  worst bar: {idx_tv} ({df.index[idx_tv]})")
print(f"  HWM={hwm_tv[idx_tv]:.4f}  eq_low={equity_low_tv[idx_tv]:.4f}")
print()
print(f"HWM @ bar 1913 with TV entry_price: {equity_close_tv[bar_hwm]:.4f}  (TV needed: 10193.5745)")
print(f"HWM @ bar 6393: {hwm_tv[6393]:.4f}  (TV: 10193.5745)")
