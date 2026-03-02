"""Compare entry prices between V4 and Numba to understand time offset."""

import json
import sqlite3
import sys
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

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

adapter = StrategyBuilderAdapter(strategy_graph, btcusdt_ohlcv=btc_ohlcv)
signals = adapter.generate_signals(ohlcv)
n = len(ohlcv)
le = np.asarray(signals.entries, dtype=bool)
se = np.asarray(signals.short_entries, dtype=bool)
lx = np.asarray(signals.exits, dtype=bool)
sx = np.asarray(signals.short_exits, dtype=bool)


def make_input():
    return BacktestInput(
        candles=ohlcv,
        long_entries=le,
        short_entries=se,
        long_exits=lx,
        short_exits=sx,
        initial_capital=10000.0,
        position_size=0.1,
        use_fixed_amount=True,
        fixed_amount=100.0,
        leverage=10,
        stop_loss=0.132,
        take_profit=0.023,
        taker_fee=0.0007,
        slippage=0.0,
        direction=TradeDirection.BOTH,
        pyramiding=1,
        entry_on_next_bar_open=True,
        breakeven_enabled=False,
    )


out_v4 = FallbackEngineV4().run(make_input())
out_nb = NumbaEngineV2().run(make_input())


def get_trades(out):
    trades = []
    for t in out.trades:
        if isinstance(t, dict):
            d = t.get("direction", "")
            ep = t.get("entry_price", 0)
            et = t.get("entry_time", "")
            pnl = t.get("pnl", 0)
        else:
            d = str(getattr(t, "direction", ""))
            ep = float(getattr(t, "entry_price", 0))
            et = str(getattr(t, "entry_time", ""))
            pnl = float(getattr(t, "pnl", 0))
        trades.append({"direction": d.lower(), "entry_time": et, "entry_price": round(ep, 4), "pnl": round(pnl, 4)})
    return trades


v4_trades = get_trades(out_v4)
nb_trades = get_trades(out_nb)

v4_short = [t for t in v4_trades if t["direction"] == "short"]
nb_short = [t for t in nb_trades if t["direction"] == "short"]

print(f"V4 short: {len(v4_short)}, Numba short: {len(nb_short)}")
print()

# Match by entry_price (actual fill price should be identical if same trade)
v4_eps = {}
for t in v4_short:
    k = t["entry_price"]
    v4_eps.setdefault(k, []).append(t)

nb_eps = {}
for t in nb_short:
    k = t["entry_price"]
    nb_eps.setdefault(k, []).append(t)

# Find prices in Numba but not in V4
missing_prices = set(nb_eps.keys()) - set(v4_eps.keys())
extra_prices = set(v4_eps.keys()) - set(nb_eps.keys())
print(f"Entry prices in Numba but NOT in V4 ({len(missing_prices)} prices):")
for p in sorted(missing_prices):
    for t in nb_eps[p]:
        print(f"  entry_price={p}, entry_time={t['entry_time']}, pnl={t['pnl']}")

print()
print(f"Entry prices in V4 but NOT in Numba ({len(extra_prices)} prices):")
for p in sorted(extra_prices):
    for t in v4_eps[p]:
        print(f"  entry_price={p}, entry_time={t['entry_time']}, pnl={t['pnl']}")

print()
# Show first 10 of each for comparison
print("=== First 10 Numba SHORT trades (sorted by entry_time) ===")
for i, t in enumerate(sorted(nb_short, key=lambda x: x["entry_time"])[:10]):
    print(f"  [{i + 1}] time={t['entry_time']}  ep={t['entry_price']}  pnl={t['pnl']}")

print()
print("=== First 10 V4 SHORT trades (sorted by entry_time) ===")
for i, t in enumerate(sorted(v4_short, key=lambda x: x["entry_time"])[:10]):
    print(f"  [{i + 1}] time={t['entry_time']}  ep={t['entry_price']}  pnl={t['pnl']}")

print()
# Check for SAME price but different time (would confirm 1-bar offset is just indexing)
common_prices = set(v4_eps.keys()) & set(nb_eps.keys())
print(f"Prices in common: {len(common_prices)}")
print(f"Prices only in Numba: {len(missing_prices)}")
print(f"Prices only in V4: {len(extra_prices)}")
