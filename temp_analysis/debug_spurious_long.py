"""Find the spurious LONG trade in V4 on Jan 8."""

import json
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from loguru import logger

logger.remove()

conn = sqlite3.connect("data.sqlite3")
cur = conn.execute(
    "SELECT open_time, open_price, high_price, low_price, close_price, volume "
    "FROM bybit_kline_audit "
    "WHERE symbol='ETHUSDT' AND interval='30' AND market_type='linear' "
    "AND open_time_dt >= '2025-01-01' AND open_time_dt < '2026-03-01' "
    "ORDER BY open_time ASC"
)
rows = cur.fetchall()
ohlcv = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume"])
ohlcv["open_time"] = pd.to_datetime(ohlcv["open_time"], unit="ms", utc=True)
ohlcv = ohlcv.set_index("open_time").astype(float)

cur = conn.execute(
    "SELECT open_time, open_price, high_price, low_price, close_price, volume "
    "FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='30' AND market_type='linear' "
    "AND open_time_dt >= '2025-01-01' AND open_time_dt < '2026-03-01' "
    "ORDER BY open_time ASC"
)
btc_ohlcv = pd.DataFrame(cur.fetchall(), columns=["open_time", "open", "high", "low", "close", "volume"])
btc_ohlcv["open_time"] = pd.to_datetime(btc_ohlcv["open_time"], unit="ms", utc=True)
btc_ohlcv = btc_ohlcv.set_index("open_time").astype(float)

cur = conn.execute(
    "SELECT builder_blocks, builder_connections, builder_graph FROM strategies WHERE id LIKE '149454c2%'"
)
s_row = cur.fetchone()
conn.close()

builder_blocks = json.loads(s_row[0])
builder_connections = json.loads(s_row[1])
builder_graph_raw = json.loads(s_row[2]) if s_row[2] else {}
strategy_graph = {
    "name": "test",
    "blocks": builder_blocks,
    "connections": builder_connections,
    "market_type": "linear",
    "direction": "both",
    "interval": "30",
}
if builder_graph_raw.get("main_strategy"):
    strategy_graph["main_strategy"] = builder_graph_raw["main_strategy"]

from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

adapter = StrategyBuilderAdapter(strategy_graph, btcusdt_ohlcv=btc_ohlcv)
signals = adapter.generate_signals(ohlcv)
n = len(ohlcv)
se = np.asarray(signals.short_entries, dtype=bool)
le = np.asarray(signals.entries, dtype=bool)
lx = np.asarray(signals.exits, dtype=bool)
sx = np.asarray(signals.short_exits, dtype=bool)

# V4 spurious LONG: entry_time = 01/08 01:30 UTC+3 = 01/07 22:30 UTC
# entry_price = 3376.33
# With entry_on_next_bar_open=True, bar_i enters at open[i], reads signal from long_entries[i-1]
# So signal is at bar where open_time = 01/07 22:00 UTC, entry bar is 01/07 22:30 UTC

target_open = 3376.33
mask = abs(ohlcv["open"] - target_open) < 0.02
if mask.any():
    for ts in ohlcv.index[mask]:
        i = ohlcv.index.get_loc(ts)
        utc3 = ts + timedelta(hours=3)
        sig_bar = i - 1
        sig_utc3 = ohlcv.index[sig_bar] + timedelta(hours=3)
        print(f"V4 spurious LONG: bar[{i}] = {utc3.strftime('%Y-%m-%d %H:%M')} UTC+3")
        print(f"  entry_price = {ohlcv['open'].iloc[i]:.2f}")
        print(f"  Signal bar[{sig_bar}] = {sig_utc3.strftime('%Y-%m-%d %H:%M')} UTC+3")
        print(f"  long_entries[{sig_bar}] = {le[sig_bar]}")
        print(f"  long_entries[{i}] = {le[i]}")
        print(f"  short_entries[{sig_bar}] = {se[sig_bar]}")
        print()
        # Broader context
        lo = max(0, i - 8)
        hi = min(n - 1, i + 4)
        print(f"  Context [{lo}..{hi}]:")
        for b in range(lo, hi + 1):
            ts2 = ohlcv.index[b] + timedelta(hours=3)
            print(
                f"    [{b}] {ts2.strftime('%Y-%m-%d %H:%M')}  O={ohlcv['open'].iloc[b]:.2f}  C={ohlcv['close'].iloc[b]:.2f}  le={le[b]} se={se[b]} lx={lx[b]} sx={sx[b]}"
            )
else:
    print(f"open price {target_open} not found")

# Also: find exit of the FIRST short trade in V4
# V4 short exit: 01/08 01:00 UTC+3 = 01/08 00:00 - 01/07 22:00 UTC?
# First short: entered 01/03, exits 01/08 01:00 UTC+3
# That = 01/07 22:00 UTC
exit_utc = pd.Timestamp("2025-01-07 22:00:00", tz="UTC")
if exit_utc in ohlcv.index:
    i = ohlcv.index.get_loc(exit_utc)
    print(f"\nFirst short exit bar[{i}] = {exit_utc} UTC")
    print(f"  O={ohlcv['open'].iloc[i]:.2f}  C={ohlcv['close'].iloc[i]:.2f}")
    print(f"  TP for short entered at ~3433.46 with TP=2.3%: {3433.46 * (1 - 0.023):.2f}")
    # Check what entry_on_next_bar_open means for V4 in this bar:
    # V4 exits at bar i (TP hit during bar), then at bar i+1 it checks long_entries[i]
    print(f"\n  After exit at bar {i}:")
    for b in range(i - 2, i + 5):
        ts2 = ohlcv.index[b] + timedelta(hours=3)
        print(
            f"    [{b}] {ts2.strftime('%Y-%m-%d %H:%M')}  O={ohlcv['open'].iloc[b]:.4f}  C={ohlcv['close'].iloc[b]:.4f}  le={le[b]} se={se[b]} lx={lx[b]} sx={sx[b]}"
        )

# The same-bar check: V4 with entry_on_next_bar_open=True — when a trade exits on bar i
# via TP, V4 sets pending_short_exit/pending_long_exit to True on bar i, executes exit
# at start of bar i+1 open... or does it exit on bar i's TP price?
# Let's see what exited_this_bar does in V4
