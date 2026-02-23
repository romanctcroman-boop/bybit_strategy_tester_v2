"""Debug trade #100: check signals at bar 9313-9316."""

import datetime as dt
import json
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()

DB = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRAT = "5a1741ac-ad9e-4285-a9d6-58067c56407a"

conn = sqlite3.connect(DB)
row = conn.execute("SELECT * FROM strategies WHERE id=?", (STRAT,)).fetchone()
cols = [d[0] for d in conn.execute("SELECT * FROM strategies WHERE id=?", (STRAT,)).description]
conn.close()
strat = dict(zip(cols, row, strict=False))
sg = json.loads(strat["builder_graph"])
sg.update(
    {
        "name": strat["name"],
        "description": "",
        "blocks": json.loads(strat["builder_blocks"]),
        "connections": json.loads(strat["builder_connections"]),
        "market_type": "linear",
        "direction": "both",
        "interval": "15",
    }
)

conn2 = sqlite3.connect(DB)
df = pd.read_sql_query(
    "SELECT open_time, open_price as [open], high_price as high, low_price as low, "
    "close_price as close, volume FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
    "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
    conn2,
    params=(
        int(dt.datetime(2025, 11, 1, tzinfo=dt.UTC).timestamp() * 1000),
        int(dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC).timestamp() * 1000),
    ),
)
conn2.close()
df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
ohlcv = df.set_index("timestamp").drop(columns=["open_time"])

from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

adapter = StrategyBuilderAdapter(sg)
sig_result = adapter.generate_signals(ohlcv)
# SignalResult has entries, exits, short_entries, short_exits arrays
import numpy as np

entries = np.asarray(sig_result.entries) if hasattr(sig_result, "entries") else None
exits = np.asarray(sig_result.exits) if hasattr(sig_result, "exits") else None
short_entries = np.asarray(sig_result.short_entries) if hasattr(sig_result, "short_entries") else None
short_exits = np.asarray(sig_result.short_exits) if hasattr(sig_result, "short_exits") else None
print(
    f"SignalResult attrs: entries={entries is not None}, exits={exits is not None}, "
    f"short_entries={short_entries is not None}, short_exits={short_exits is not None}"
)

# Print signals around bar 9313
EBAR = 9313
print(f"\nSignals around entry bar {EBAR}:")
for b in range(max(0, EBAR - 1), min(len(ohlcv), EBAR + 6)):
    en = bool(entries[b]) if entries is not None else "?"
    ex = bool(exits[b]) if exits is not None else "?"
    se = bool(short_entries[b]) if short_entries is not None else "?"
    sx = bool(short_exits[b]) if short_exits is not None else "?"
    ts = ohlcv.index[b]
    o = ohlcv.iloc[b]["open"]
    h = ohlcv.iloc[b]["high"]
    lo = ohlcv.iloc[b]["low"]
    c = ohlcv.iloc[b]["close"]
    marker = " <<< ENTRY" if b == EBAR else ""
    print(
        f"  bar[{b}] {ts.strftime('%m-%d %H:%M')} O={o:.0f} H={h:.0f} L={lo:.0f} C={c:.0f} | "
        f"entry={en} exit={ex} s_entry={se} s_exit={sx}{marker}"
    )
