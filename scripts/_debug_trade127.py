"""Investigate trade #127 entry mismatch: TV=17:30 UTC Feb19, ours=22:00 UTC Feb19."""

import json
import sqlite3
import sys
from datetime import UTC, datetime

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"


def load_ohlcv(start, end):
    conn = sqlite3.connect(DB_PATH)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    df = pd.read_sql_query(
        "SELECT open_time, open_price as open, high_price as high, "
        "low_price as low, close_price as close, volume "
        "FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
        "AND open_time >= ? AND open_time <= ? "
        "ORDER BY open_time ASC",
        conn,
        params=(start_ms, end_ms),
    )
    conn.close()
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("timestamp").drop(columns=["open_time"])


conn = sqlite3.connect(DB_PATH)
row = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,)).fetchone()
col_names = [d[0] for d in conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,)).description]
conn.close()
strat = dict(zip(col_names, row, strict=False))

builder_blocks = (
    json.loads(strat["builder_blocks"]) if isinstance(strat["builder_blocks"], str) else strat["builder_blocks"]
)
builder_connections = (
    json.loads(strat["builder_connections"])
    if isinstance(strat["builder_connections"], str)
    else strat["builder_connections"]
)
builder_graph_raw = (
    json.loads(strat["builder_graph"]) if isinstance(strat["builder_graph"], str) else strat["builder_graph"]
)

strategy_graph = {
    "name": strat["name"],
    "description": strat.get("description") or "",
    "blocks": builder_blocks,
    "connections": builder_connections,
    "market_type": "linear",
    "direction": "both",
    "interval": "15",
}
if builder_graph_raw and builder_graph_raw.get("main_strategy"):
    strategy_graph["main_strategy"] = builder_graph_raw["main_strategy"]

from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.core.indicators import calculate_rsi

adapter = StrategyBuilderAdapter(strategy_graph)

# Load data covering Feb 19 area
ohlcv = load_ohlcv(
    datetime(2025, 11, 1, tzinfo=UTC),
    datetime(2026, 2, 23, 23, 59, tzinfo=UTC),
)

signals = adapter.generate_signals(ohlcv)

# Focus on Feb 19 2026 UTC
focus_start = pd.Timestamp("2026-02-19 15:00:00", tz="UTC")
focus_end = pd.Timestamp("2026-02-19 23:00:00", tz="UTC")

long_arr = signals.long_entry.values
short_arr = signals.short_exit.values if hasattr(signals, "short_exit") else None

# Check signals around TV trade #126 exit (17:15 UTC) and TV trade #127 entry (17:30 UTC)
# TV trade #126: Entry long 14:15 UTC, Exit 17:15 UTC (TP)
# TV trade #127: Entry short 17:30 UTC (signal bar = 17:15 UTC)

close = ohlcv["close"]
rsi_arr = calculate_rsi(close.values, period=14)
rsi = pd.Series(rsi_arr, index=close.index)

print("Bars around Feb 19 2026 15:00-23:00 UTC:")
print(f"{'Bar UTC':<30} {'Close':>10} {'RSI':>8} {'LongSig':>8} {'ShortSig':>9}")
for ts in ohlcv.loc[focus_start:focus_end].index:
    idx = ohlcv.index.get_loc(ts)
    c = ohlcv.loc[ts, "close"]
    r = rsi.iloc[idx]
    l = long_arr[idx]

    # Get short signal from signals object
    if hasattr(signals, "short_entry") and signals.short_entry is not None:
        s = signals.short_entry.values[idx]
    else:
        s = False

    marker = " <-- TV#127 entry signal" if str(ts).startswith("2026-02-19 17:15") else ""
    marker += " <-- TV#126 exit" if str(ts).startswith("2026-02-19 17:00") else ""
    print(f"{ts!s:<30} {c:>10.2f} {r:>8.2f} {l!s:>8} {s!s:>9}{marker}")

print()
print("Checking where OUR engine found trade #126 exit and #127 entry...")
# Run full backtest and look at trades 125-128
from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig

params = json.loads(strat["parameters"]) if isinstance(strat["parameters"], str) else strat["parameters"]

config = BacktestConfig(
    symbol="BTCUSDT",
    interval="15",
    start_date=datetime(2025, 11, 1, tzinfo=UTC),
    end_date=datetime(2026, 2, 23, 23, 59, tzinfo=UTC),
    initial_capital=10000.0,
    commission_value=float(params.get("_commission", 0.0007)),
    slippage=float(params.get("_slippage", 0.0005)),
    leverage=float(params.get("_leverage", 10.0)),
    position_size=0.1,
    pyramiding=int(params.get("_pyramiding", 1)),
    direction="both",
    stop_loss=0.032,
    take_profit=0.015,
)

engine = BacktestEngine()
result = engine.run(config, ohlcv, custom_strategy=adapter)
trades = result.trades

print("\nOur trades #124-129:")
for i, t in enumerate(trades[123:], start=124):
    entry_ts = pd.Timestamp(t.entry_time) + pd.Timedelta(minutes=15)
    exit_ts = pd.Timestamp(t.exit_time)
    print(f"  Trade #{i}: {t.side} entry={entry_ts} exit={exit_ts} reason={t.exit_reason}")
