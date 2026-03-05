"""
Check when the first RSI signal appears with current data (no warmup).
Also check what happens if we prepend pre-2025 data from Bybit API.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3

import numpy as np
import pandas as pd
from loguru import logger

logger.remove()

# Load ETHUSDT 30m data (current — starts 2025-01-01)
conn = sqlite3.connect("data.sqlite3")
cur = conn.execute(
    "SELECT open_time, open_price, high_price, low_price, close_price, volume "
    "FROM bybit_kline_audit "
    "WHERE symbol='ETHUSDT' AND interval='30' AND market_type='linear' "
    "AND open_time_dt >= '2025-01-01' AND open_time_dt < '2026-03-01' "
    "ORDER BY open_time ASC"
)
rows = cur.fetchall()

# Load BTC 30m
cur = conn.execute(
    "SELECT open_time, open_price, high_price, low_price, close_price, volume "
    "FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='30' AND market_type='linear' "
    "AND open_time_dt >= '2025-01-01' AND open_time_dt < '2026-03-01' "
    "ORDER BY open_time ASC"
)
btc_rows = cur.fetchall()
conn.close()

ohlcv = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume"])
ohlcv["open_time"] = pd.to_datetime(ohlcv["open_time"], unit="ms", utc=True)
ohlcv = ohlcv.set_index("open_time").astype(float)

btc_ohlcv = pd.DataFrame(btc_rows, columns=["open_time", "open", "high", "low", "close", "volume"])
btc_ohlcv["open_time"] = pd.to_datetime(btc_ohlcv["open_time"], unit="ms", utc=True)
btc_ohlcv = btc_ohlcv.set_index("open_time").astype(float)

# Load strategy
conn2 = sqlite3.connect("data.sqlite3")
cur = conn2.execute(
    "SELECT builder_blocks, builder_connections, builder_graph FROM strategies WHERE id LIKE '149454c2%'"
)
s_row = cur.fetchone()
conn2.close()

builder_blocks = json.loads(s_row[0])
builder_connections = json.loads(s_row[1])
builder_graph_raw = json.loads(s_row[2])

strategy_graph = {
    "name": "Strategy-A2 (debug)",
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

le = np.asarray(signals.entries, dtype=bool) if signals.entries is not None else np.zeros(len(ohlcv), dtype=bool)
se = (
    np.asarray(signals.short_entries, dtype=bool)
    if signals.short_entries is not None
    else np.zeros(len(ohlcv), dtype=bool)
)

# Find first signals
first_long_idx = np.argmax(le) if le.any() else -1
first_short_idx = np.argmax(se) if se.any() else -1

print(f"Data starts: {ohlcv.index[0]} (UTC), {ohlcv.index[0].tz_convert('Etc/GMT-3')} (UTC+3)")
print(f"Total candles: {len(ohlcv)}")
print()

if first_long_idx >= 0:
    t = ohlcv.index[first_long_idx]
    from datetime import timedelta

    t3 = t + timedelta(hours=3)
    print(f"First LONG signal: bar#{first_long_idx} = {t} UTC = {t3.strftime('%Y-%m-%d %H:%M')} UTC+3")
    print(f"  Previous 5 bars: {[str(ohlcv.index[max(0, first_long_idx - i)]) for i in range(5, 0, -1)]}")
else:
    print("No LONG signals found")

if first_short_idx >= 0:
    t = ohlcv.index[first_short_idx]
    from datetime import timedelta

    t3 = t + timedelta(hours=3)
    print(f"First SHORT signal: bar#{first_short_idx} = {t} UTC = {t3.strftime('%Y-%m-%d %H:%M')} UTC+3")
else:
    print("No SHORT signals found")

print()
print(f"Total long signals: {le.sum()}")
print(f"Total short signals: {se.sum()}")

# Print first 5 short signals to understand the pattern
print()
print("First 5 SHORT signal bars (UTC+3):")
count = 0
for i, v in enumerate(se):
    if v:
        t = ohlcv.index[i]
        from datetime import timedelta

        t3 = t + timedelta(hours=3)
        print(f"  bar#{i}: {t3.strftime('%Y-%m-%d %H:%M')}")
        count += 1
        if count >= 5:
            break

# TV says first_entry is 2025-01-01 16:30 UTC+3 = 2025-01-01 13:30 UTC
# That's bar index = 13:30 / 0:30 = 27
target_utc = datetime(2025, 1, 1, 13, 30, tzinfo=UTC)
target_bar = ohlcv.index.searchsorted(target_utc)
print()
print(f"TV target bar (2025-01-01 16:30 UTC+3 = 13:30 UTC): index={target_bar}")
if target_bar < len(ohlcv):
    print(f"  Bar at index {target_bar}: {ohlcv.index[target_bar]}")
    print(f"  Signal at target: long={le[target_bar]}, short={se[target_bar]}")
    # Check surrounding bars
    for i in range(max(0, target_bar - 2), min(len(ohlcv), target_bar + 5)):
        from datetime import timedelta

        t3 = ohlcv.index[i] + timedelta(hours=3)
        print(f"    bar#{i} {t3.strftime('%Y-%m-%d %H:%M')}: long={le[i]}, short={se[i]}")
