"""
Debug Sharpe: Trade-based returns approach for TV parity
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
m = result.metrics

closed = [t for t in result.trades if not getattr(t, "is_open", False)]
print(f"Closed trades: {len(closed)}")

target = 0.895

# === APPROACH 1: Trade PnL returns (PnL / initial_capital) ===
pnl_returns = np.array([getattr(t, "pnl", 0) / 10000.0 for t in closed])
print(
    f"\nTrade PnL returns: n={len(pnl_returns)}, mean={np.mean(pnl_returns):.6f}, std={np.std(pnl_returns, ddof=1):.6f}"
)
m1 = np.mean(pnl_returns)
s1 = np.std(pnl_returns, ddof=1)
sharpe_no_ann = m1 / s1 if s1 > 1e-10 else 0.0
print(f"  No annualization: {sharpe_no_ann:.4f}  (diff: {abs(sharpe_no_ann - target) / target * 100:.2f}%)")

# Annualized - how many trades/year?
# 128 trades in ~4 months = ~384 trades/year
trades_per_year = len(closed) / (115 / 365)  # 115 days
print(f"  Estimated trades/year: {trades_per_year:.1f}")
sharpe_ann = m1 / s1 * np.sqrt(trades_per_year) if s1 > 1e-10 else 0.0
print(f"  Annualized (sqrt({trades_per_year:.0f})): {sharpe_ann:.4f}")

# === APPROACH 2: Trade PnL returns (PnL / equity_at_entry) ===
pnl_pct_returns = np.array([getattr(t, "pnl_pct", 0) / 100.0 for t in closed])
print(
    f"\nTrade PnL% returns: n={len(pnl_pct_returns)}, mean={np.mean(pnl_pct_returns):.6f}, std={np.std(pnl_pct_returns, ddof=1):.6f}"
)
m2 = np.mean(pnl_pct_returns)
s2 = np.std(pnl_pct_returns, ddof=1)
sharpe_pct = m2 / s2 if s2 > 1e-10 else 0.0
print(f"  No annualization: {sharpe_pct:.4f}  (diff: {abs(sharpe_pct - target) / target * 100:.2f}%)")
sharpe_pct_ann = m2 / s2 * np.sqrt(trades_per_year) if s2 > 1e-10 else 0.0
print(f"  Annualized (sqrt({trades_per_year:.0f})): {sharpe_pct_ann:.4f}")

# === APPROACH 3: TV formula - annual return / std of trade returns ===
# "Sharpe = Annual_Return / Annualized_StdDev_of_Trade_Returns"
# where annualized via sqrt(trades_per_year)
net_profit_pct = m.net_profit / 10000.0  # ~4.8% for 4 months
annual_return = net_profit_pct * (365 / 115)
annual_std = s2 * np.sqrt(trades_per_year)
sharpe_tv3 = annual_return / annual_std if annual_std > 1e-10 else 0.0
print(f"\nTV-style (annual_return / annualized_std): {sharpe_tv3:.4f}")

# === APPROACH 4: Mean trade return / std, annualized via days ===
# TradingView docs: Sharpe = Average_Trade_Return / StdDev_Trade_Return * sqrt(N_per_year)
# where avg return is per trade, and we scale to yearly
rfr_per_trade = 0.02 / trades_per_year  # 2% annual / trades_per_year
print(f"\nWith rfr per trade: {rfr_per_trade:.6f}")
sharpe_rfr = (m2 - rfr_per_trade) / s2 * np.sqrt(trades_per_year) if s2 > 1e-10 else 0.0
print(f"  With rfr (2%): {sharpe_rfr:.4f}")

# === APPROACH 5: Compare each approach with ddof=0 ===
s2_0 = np.std(pnl_pct_returns, ddof=0)
print(f"\nWith ddof=0: std={s2_0:.6f}")
sharpe_ddof0 = m2 / s2_0 if s2_0 > 1e-10 else 0.0
print(f"  No annualization: {sharpe_ddof0:.4f}  (diff: {abs(sharpe_ddof0 - target) / target * 100:.2f}%)")

# === APPROACH 6: What if TV uses days-based returns? ===
# Trade returns grouped by day or week
equity_arr = np.array(result.equity_curve.equity)
timestamps = df.index.tolist()
ts_idx = pd.DatetimeIndex(timestamps)
ec_series = pd.Series(equity_arr, index=ts_idx)

# Compute returns at trade exit times
exit_equities = []
cum_eq = 10000.0
for t in closed:
    cum_eq += getattr(t, "pnl", 0)
    exit_equities.append(cum_eq)

exit_equities = np.array(exit_equities)
trade_seq_returns = np.diff(exit_equities) / exit_equities[:-1]
print(f"\nSequential trade equity returns: n={len(trade_seq_returns)}")
ts_m = np.mean(trade_seq_returns)
ts_s = np.std(trade_seq_returns, ddof=1)
sharpe_seq = ts_m / ts_s if ts_s > 1e-10 else 0.0
print(f"  No ann: {sharpe_seq:.4f}  (diff: {abs(sharpe_seq - target) / target * 100:.2f}%)")
sharpe_seq_ann = ts_m / ts_s * np.sqrt(trades_per_year) if ts_s > 1e-10 else 0.0
print(f"  Ann: {sharpe_seq_ann:.4f}")

# Reverse-engineer: what factor needed?
x_pct = (target * s2 / m2) ** 2
x_pnl = (target * s1 / m1) ** 2
print(
    f"\n>>> pnl_pct: need annualization factor {x_pct:.1f} ({np.sqrt(x_pct):.2f} per year -> {x_pct / trades_per_year:.3f} trades/bar)"
)
print(f">>> pnl/cap: need annualization factor {x_pnl:.1f}")

print(f"\nEngine sharpe_ratio: {m.sharpe_ratio:.4f}  (TV: 0.895)")

# Let's check: how many bars total is 115 days of 15-min bars?
total_bars = len(df)
bars_per_year = total_bars / (115 / 365)
print(f"\nBars in backtest: {total_bars}, bars/year equiv: {bars_per_year:.0f}")
print(f"sqrt(bars/year): {np.sqrt(bars_per_year):.2f}")
