"""Диагностика Sharpe/Sortino: находим формулу TV. TV: Sharpe=0.895, Sortino=16.708"""

import datetime as dt
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///data.sqlite3")

from loguru import logger

logger.remove()

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB = "data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"
TV_SHARPE = 0.895
TV_SORTINO = 16.708

conn = sqlite3.connect(DB)
row = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,)).fetchone()
cols = [d[0] for d in conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,)).description]
conn.close()
strat = dict(zip(cols, row, strict=False))

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
    "close_price as close, volume FROM bybit_kline_audit "
    "WHERE symbol=? AND interval=? AND market_type=? AND open_time>=? AND open_time<=? ORDER BY open_time ASC",
    conn2,
    params=("BTCUSDT", "15", "linear", start_ms, end_ms),
)
conn2.close()
df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df = df.set_index("timestamp").drop(columns=["open_time"])

params = json.loads(strat["parameters"])
cfg = BacktestConfig(
    symbol="BTCUSDT",
    interval="15",
    start_date=dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
    end_date=dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC),
    initial_capital=10000.0,
    commission_value=float(params.get("_commission", 0.0007)),
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
m = result.metrics
all_trades = result.trades
closed = [t for t in all_trades if not getattr(t, "is_open", False)]
ec = result.equity_curve
equity_arr = np.array(ec.equity) if ec and ec.equity else None
ts_list = ec.timestamps if ec and ec.timestamps else []

print("\n=== Current Ratios ===")
print(f"Sharpe:  {m.sharpe_ratio:.4f}  (TV: {TV_SHARPE})")
print(f"Sortino: {m.sortino_ratio:.4f}  (TV: {TV_SORTINO})")
if equity_arr is not None and len(equity_arr) > 1:
    bar_returns = np.diff(equity_arr) / equity_arr[:-1]
    bar_returns = np.nan_to_num(bar_returns, nan=0.0, posinf=0.0, neginf=0.0)
    mean_r = np.mean(bar_returns)
    std_r = np.std(bar_returns, ddof=1)
    neg_r = np.minimum(0, bar_returns)
    dd_var = np.sum(neg_r**2) / len(bar_returns)
    dd_dev = np.sqrt(dd_var)
    print(f"\n=== Bar-by-bar returns (N={len(bar_returns)}) ===")
    print(f"Mean: {mean_r:.8f}, Std: {std_r:.8f}, Downside dev: {dd_dev:.8f}")
    if std_r > 0:
        for freq, ppyr in [("minutely15", 35040), ("hourly", 8766), ("daily", 365.25), ("weekly", 52), ("monthly", 12)]:
            print(f"  Sharpe *sqrt({ppyr}): {mean_r / std_r * np.sqrt(ppyr):.4f}  [{freq}]")
    if dd_dev > 0:
        for freq, ppyr in [("minutely15", 35040), ("hourly", 8766), ("daily", 365.25), ("weekly", 52), ("monthly", 12)]:
            print(f"  Sortino *sqrt({ppyr}): {mean_r / dd_dev * np.sqrt(ppyr):.4f}  [{freq}]")

# --- Method 2: Trade-by-trade PnL% ---
trade_returns = np.array([t.pnl_pct / 100.0 for t in closed])
print(f"\n=== Trade-by-trade pnl_pct (N={len(trade_returns)}) ===")
mean_r = np.mean(trade_returns)
std_r = np.std(trade_returns, ddof=1)
neg_r = np.minimum(0, trade_returns)
dd_var = np.sum(neg_r**2) / len(trade_returns)
dd_dev = np.sqrt(dd_var)
print(f"Mean: {mean_r:.6f}, Std: {std_r:.6f}, Downside dev: {dd_dev:.6f}")
wins_neg = sum(1 for r in trade_returns if r < 0)
print(f"Negative returns: {wins_neg}/{len(trade_returns)}")
if std_r > 0:
    print(f"Sharpe (no annualization): {mean_r / std_r:.4f}")
    for n, ppyr in [("12", 12), ("52", 52), ("365", 365.25), (f"N={len(trade_returns)}", len(trade_returns))]:
        print(f"  Sharpe * sqrt({n}): {mean_r / std_r * np.sqrt(ppyr):.4f}")
if dd_dev > 0:
    print(f"Sortino (no annualization): {mean_r / dd_dev:.4f}")
    for n, ppyr in [("12", 12), ("52", 52), ("365", 365.25), (f"N={len(trade_returns)}", len(trade_returns))]:
        print(f"  Sortino * sqrt({n}): {mean_r / dd_dev * np.sqrt(ppyr):.4f}")
else:
    print("No negative trade returns → Sortino = inf!")

# --- Method 3: Monthly equity returns ---
if equity_arr is not None and ts_list:
    eq_df = pd.DataFrame({"equity": equity_arr}, index=pd.to_datetime(ts_list))
    monthly = eq_df["equity"].resample("ME").last()
    monthly_r = monthly.pct_change().dropna()
    print(f"\n=== Monthly equity returns (N={len(monthly_r)}) ===")
    print(f"Monthly returns: {monthly_r.values.round(5)}")
    if len(monthly_r) >= 2:
        mr = monthly_r.values
        mean_mr = np.mean(mr)
        std_mr = np.std(mr, ddof=1)
        neg_mr = np.minimum(0, mr)
        dd_var_m = np.sum(neg_mr**2) / len(mr)
        dd_dev_m = np.sqrt(dd_var_m)
        print(f"Mean: {mean_mr:.6f}, Std: {std_mr:.6f}, Downside dev: {dd_dev_m:.6f}")
        if std_mr > 0:
            print(f"Sharpe * sqrt(12): {mean_mr / std_mr * np.sqrt(12):.4f}  (TV: {TV_SHARPE})")
        if dd_dev_m > 0:
            print(f"Sortino * sqrt(12): {mean_mr / dd_dev_m * np.sqrt(12):.4f}  (TV: {TV_SORTINO})")
        else:
            print(f"No negative monthly returns -> Sortino = inf (TV: {TV_SORTINO})")

    # Weekly
    weekly = eq_df["equity"].resample("W").last()
    weekly_r = weekly.pct_change().dropna()
    print(f"\n=== Weekly equity returns (N={len(weekly_r)}) ===")
    if len(weekly_r) >= 2:
        wr = weekly_r.values
        mean_wr = np.mean(wr)
        std_wr = np.std(wr, ddof=1)
        neg_wr = np.minimum(0, wr)
        dd_var_w = np.sum(neg_wr**2) / len(wr)
        dd_dev_w = np.sqrt(dd_var_w)
        print(f"Mean: {mean_wr:.6f}, Std: {std_wr:.6f}, Downside dev: {dd_dev_w:.6f}")
        if std_wr > 0:
            print(f"Sharpe * sqrt(52): {mean_wr / std_wr * np.sqrt(52):.4f}  (TV: {TV_SHARPE})")
        if dd_dev_w > 0:
            print(f"Sortino * sqrt(52): {mean_wr / dd_dev_w * np.sqrt(52):.4f}  (TV: {TV_SORTINO})")
        else:
            print(f"No negative weekly returns -> Sortino = inf (TV: {TV_SORTINO})")
