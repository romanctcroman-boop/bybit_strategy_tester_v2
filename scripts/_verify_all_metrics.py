"""
Full verification of all fixed metrics vs TV benchmark.
"""

import datetime as dt
import json
import os
import sqlite3
import sys

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

print("=" * 65)
print("METRIC COMPARISON: Engine vs TradingView Benchmark")
print("=" * 65)
print(f"{'Metric':<35} {'Engine':>12} {'TV Target':>12} {'Diff%':>7}")
print("-" * 65)

tv_targets = [
    ("net_profit", m.net_profit, 482.16),
    ("gross_profit", m.gross_profit, 1384.65),
    ("gross_loss", m.gross_loss, 902.50),
    ("profit_factor", m.profit_factor, 1.534),
    ("total_trades", m.total_trades, 128),
    ("win_rate", m.win_rate, 78.91),
    ("sortino_ratio", m.sortino_ratio, 16.708),
    ("sharpe_ratio", m.sharpe_ratio, 0.895),
    ("avg_margin_used", m.avg_margin_used, 852.53),
    ("max_margin_used", m.max_margin_used, 1033.35),
    ("account_size_required", m.account_size_required, 1180.34),
    ("max_drawdown_intrabar_value", m.max_drawdown_intrabar_value, 146.99),
    ("max_runup_intrabar_value", m.max_runup_intrabar_value, 537.82),
    ("max_drawdown_intrabar", m.max_drawdown_intrabar, 1.44),
    ("max_runup_intrabar", m.max_runup_intrabar, 5.38),
    ("open_pnl", m.open_pnl, -10.93),
    ("cagr", m.cagr, 16.22),
]

for name, got, tv in tv_targets:
    diff_pct = abs(got - tv) / abs(tv) * 100 if tv != 0 else abs(got) * 100
    status = "✅" if diff_pct < 2.0 else "⚠️" if diff_pct < 10.0 else "❌"
    print(f"{status} {name:<33} {got:>12.4f} {tv:>12.4f} {diff_pct:>6.2f}%")

print("-" * 65)
print(
    f"\nTotal trades: {len(result.trades)}, Closed: {len([t for t in result.trades if not getattr(t, 'is_open', False)])}"
)
