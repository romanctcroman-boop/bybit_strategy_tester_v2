"""Debug TV#2: trace what the engine produces around 2025-01-07 01:00 UTC."""

import json
import sqlite3
import sys
import warnings
from datetime import UTC, datetime

import numpy as np
import pandas as pd

sys.path.insert(0, "d:/bybit_strategy_tester_v2")
warnings.filterwarnings("ignore")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

DB_PATH = "d:/bybit_strategy_tester_v2/data.sqlite3"
STRATEGY_ID = "5c03fd86-a821-4a62-a783-4d617bf25bc7"


def load_ohlcv():
    conn = sqlite3.connect(DB_PATH)
    start_ms = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime(2026, 2, 25, tzinfo=UTC).timestamp() * 1000)
    df = pd.read_sql_query(
        "SELECT open_time, open_price as open, high_price as high, "
        "low_price as low, close_price as close, volume "
        "FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='30' AND market_type='linear' "
        "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
        conn,
        params=(start_ms, end_ms),
    )
    conn.close()
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("timestamp").drop(columns=["open_time"])


def load_bt_params():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT parameters, builder_blocks, timeframe FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cur.fetchone()
    conn.close()
    params = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
    blocks = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or [])
    sltp_block = next((b for b in blocks if b.get("type") == "static_sltp"), {})
    sltp_params = sltp_block.get("params", {})
    return {
        "slippage": float(params.get("_slippage", 0.0)),
        "taker_fee": float(params.get("_commission", 0.0007)),
        "leverage": int(params.get("_leverage", 10)),
        "pyramiding": int(params.get("_pyramiding", 1)),
        "take_profit": float(sltp_params.get("take_profit_percent", 1.5)) / 100.0,
        "stop_loss": float(sltp_params.get("stop_loss_percent", 9.1)) / 100.0,
        "interval": str(sltp_params.get("timeframe") or params.get("_timeframe") or "30"),
    }


ohlcv = load_ohlcv()
p = load_bt_params()

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute(
    "SELECT builder_blocks, builder_connections, builder_graph, name FROM strategies WHERE id=?", (STRATEGY_ID,)
)
row = cur.fetchone()
conn.close()
graph = {
    "name": row[3],
    "description": "",
    "blocks": json.loads(row[0]) if isinstance(row[0], str) else row[0],
    "connections": json.loads(row[1]) if isinstance(row[1], str) else row[1],
    "market_type": "linear",
    "direction": "both",
    "interval": "30",
}
bgr = json.loads(row[2]) if isinstance(row[2], str) else row[2]
if bgr and isinstance(bgr, dict) and bgr.get("main_strategy"):
    graph["main_strategy"] = bgr["main_strategy"]

adapter = StrategyBuilderAdapter(graph)
signals = adapter.generate_signals(ohlcv)


def to_bool(s):
    return np.asarray(s.values, dtype=bool) if s is not None else np.zeros(len(ohlcv), dtype=bool)


short_entries = to_bool(getattr(signals, "short_entries", None))
long_entries = to_bool(signals.entries)

# Check signals around bar 289 (00:30 UTC) and 290 (01:00 UTC)
bar_0030 = ohlcv.index.get_loc(pd.Timestamp("2025-01-07 00:30:00", tz="UTC"))
bar_0100 = ohlcv.index.get_loc(pd.Timestamp("2025-01-07 01:00:00", tz="UTC"))
bar_0130 = ohlcv.index.get_loc(pd.Timestamp("2025-01-07 01:30:00", tz="UTC"))

print(f"Bar 00:30 (idx={bar_0030}): short_entry={short_entries[bar_0030]}, long_entry={long_entries[bar_0030]}")
print(f"Bar 01:00 (idx={bar_0100}): short_entry={short_entries[bar_0100]}, long_entry={long_entries[bar_0100]}")
print(f"Bar 01:30 (idx={bar_0130}): short_entry={short_entries[bar_0130]}, long_entry={long_entries[bar_0130]}")

# Run the engine and get trades
bt_input = BacktestInput(
    candles=ohlcv,
    long_entries=long_entries,
    long_exits=to_bool(getattr(signals, "exits", None)),
    short_entries=short_entries,
    short_exits=to_bool(getattr(signals, "short_exits", None)),
    initial_capital=1_000_000.0,
    position_size=0.10,
    use_fixed_amount=True,
    fixed_amount=100.0,
    leverage=p["leverage"],
    stop_loss=p["stop_loss"],
    take_profit=p["take_profit"],
    taker_fee=p["taker_fee"],
    slippage=p["slippage"],
    direction=TradeDirection.BOTH,
    pyramiding=p["pyramiding"],
    interval=p["interval"],
)
engine = FallbackEngineV4()
result = engine.run(bt_input)
trades = result.trades

print(f"\nTotal engine trades: {len(trades)}")
print("\nFirst 5 trades:")
for i, t in enumerate(trades[:5]):
    print(
        f"  #{i + 1}: {t.direction} entry={t.entry_price:.1f} @ {t.entry_time} | exit={t.exit_price:.1f} @ {t.exit_time} | pnl={t.pnl:.2f}"
    )
