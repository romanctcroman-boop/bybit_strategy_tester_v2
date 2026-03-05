"""
Debug: Find which 3 trades are missing in FallbackEngineV4 vs NumbaEngineV2.

FallbackV4  → 152 trades (short=121)
NumbaV2     → 155 trades (short=124)

3 short trades are missing from V4. This script finds them.
"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from loguru import logger

logger.remove()

# ─── Load data ────────────────────────────────────────────────────────────────
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
    "name": "Strategy-A2 (debug)",
    "blocks": builder_blocks,
    "connections": builder_connections,
    "market_type": "linear",
    "direction": "both",
    "interval": "30",
}
if builder_graph_raw.get("main_strategy"):
    strategy_graph["main_strategy"] = builder_graph_raw["main_strategy"]

from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

adapter = StrategyBuilderAdapter(strategy_graph, btcusdt_ohlcv=btc_ohlcv)
signals = adapter.generate_signals(ohlcv)

n = len(ohlcv)
le = np.asarray(signals.entries, dtype=bool)
se = np.asarray(signals.short_entries, dtype=bool)
lx = np.asarray(signals.exits, dtype=bool)
sx = np.asarray(signals.short_exits, dtype=bool)

fixed_margin = (10000.0 * 0.1) / 10  # = 100


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
        fixed_amount=fixed_margin,
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


# ─── Run both engines ─────────────────────────────────────────────────────────
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

print("Running FallbackEngineV4...")
out_v4 = FallbackEngineV4().run(make_input())
print(f"  V4: {len(out_v4.trades)} trades")

print("Running NumbaEngineV2...")
out_nb = NumbaEngineV2().run(make_input())
print(f"  Numba: {len(out_nb.trades)} trades")
print()


# ─── Extract trades as dicts ──────────────────────────────────────────────────
def trade_to_dict(t):
    if isinstance(t, dict):
        return t
    return {
        "direction": getattr(t, "direction", "?"),
        "entry_time": str(getattr(t, "entry_time", "")),
        "exit_time": str(getattr(t, "exit_time", "")),
        "entry_price": round(float(getattr(t, "entry_price", 0)), 4),
        "exit_price": round(float(getattr(t, "exit_price", 0)), 4),
        "pnl": round(float(getattr(t, "pnl", 0)), 4),
        "exit_reason": str(getattr(t, "exit_reason", "")),
    }


v4_trades = [trade_to_dict(t) for t in out_v4.trades]
nb_trades = [trade_to_dict(t) for t in out_nb.trades]

# Separate by direction
v4_short = [t for t in v4_trades if str(t.get("direction", "")).lower() == "short"]
nb_short = [t for t in nb_trades if str(t.get("direction", "")).lower() == "short"]

print(f"SHORT trades: V4={len(v4_short)}, Numba={len(nb_short)}")
print()

# ─── Find missing trades ──────────────────────────────────────────────────────
# Use entry_time as key for matching
v4_entry_times = {t["entry_time"] for t in v4_short}
nb_entry_times = {t["entry_time"] for t in nb_short}

missing_in_v4 = [t for t in nb_short if t["entry_time"] not in v4_entry_times]
extra_in_v4 = [t for t in v4_short if t["entry_time"] not in nb_entry_times]

print(f"Missing in V4 (in Numba but not in V4): {len(missing_in_v4)}")
for t in missing_in_v4:
    entry_dt = datetime.fromisoformat(t["entry_time"].replace("Z", "").replace("+00:00", ""))
    entry_utc3 = entry_dt + timedelta(hours=3)
    exit_dt = datetime.fromisoformat(t["exit_time"].replace("Z", "").replace("+00:00", ""))
    exit_utc3 = exit_dt + timedelta(hours=3)
    print(
        f"  ENTRY {entry_utc3.strftime('%Y-%m-%d %H:%M')} UTC+3 | EXIT {exit_utc3.strftime('%Y-%m-%d %H:%M')} UTC+3 | pnl={t['pnl']:.2f} | reason={t['exit_reason']}"
    )

print()
print(f"Extra in V4 (in V4 but not in Numba): {len(extra_in_v4)}")
for t in extra_in_v4:
    entry_dt = datetime.fromisoformat(t["entry_time"].replace("Z", "").replace("+00:00", ""))
    entry_utc3 = entry_dt + timedelta(hours=3)
    print(f"  ENTRY {entry_utc3.strftime('%Y-%m-%d %H:%M')} UTC+3 | pnl={t['pnl']:.2f} | reason={t['exit_reason']}")

# ─── Show trades around the missing entries ────────────────────────────────────
print()
print("=" * 70)
print("Numba SHORT trades sorted by entry_time:")
for i, t in enumerate(sorted(nb_short, key=lambda x: x["entry_time"])):
    mark = " ◄ MISSING FROM V4" if t["entry_time"] in {m["entry_time"] for m in missing_in_v4} else ""
    entry_dt = datetime.fromisoformat(t["entry_time"].replace("Z", "").replace("+00:00", ""))
    entry_utc3 = entry_dt + timedelta(hours=3)
    print(
        f"  [{i + 1:3d}] {entry_utc3.strftime('%Y-%m-%d %H:%M')} | {t['exit_reason']:<15s} | pnl={t['pnl']:8.2f}{mark}"
    )

print()
print("=" * 70)
print("V4 SHORT trades sorted by entry_time:")
for i, t in enumerate(sorted(v4_short, key=lambda x: x["entry_time"])):
    mark = " ◄ EXTRA vs Numba" if t["entry_time"] in {m["entry_time"] for m in extra_in_v4} else ""
    entry_dt = datetime.fromisoformat(t["entry_time"].replace("Z", "").replace("+00:00", ""))
    entry_utc3 = entry_dt + timedelta(hours=3)
    print(
        f"  [{i + 1:3d}] {entry_utc3.strftime('%Y-%m-%d %H:%M')} | {t['exit_reason']:<15s} | pnl={t['pnl']:8.2f}{mark}"
    )

# ─── Investigate the bars just before missing trades ─────────────────────────
print()
print("=" * 70)
print("Context around missing entries (signal array at those bars):")
for m in missing_in_v4:
    entry_time = m["entry_time"].replace("Z", "+00:00")
    entry_dt = pd.Timestamp(entry_time)
    # Find bar index (this is bar i where trade was entered = bar after signal)
    if entry_dt in ohlcv.index:
        i = ohlcv.index.get_loc(entry_dt)
        # Signal should have fired on bar i-1
        signal_bar = i - 1
        utc3_signal = ohlcv.index[signal_bar] + timedelta(hours=3)
        utc3_entry = ohlcv.index[i] + timedelta(hours=3)
        print(f"\n  Entry bar[{i}] = {utc3_entry.strftime('%Y-%m-%d %H:%M')} UTC+3")
        print(f"  Signal bar[{signal_bar}] = {utc3_signal.strftime('%Y-%m-%d %H:%M')} UTC+3")
        print(f"  Signal: short_entries[{signal_bar}]={se[signal_bar]}, short_entries[{i}]={se[i]}")
        # Show a window of 5 bars around the signal
        lo = max(0, signal_bar - 2)
        hi = min(n - 1, i + 2)
        print(f"  Bars [{lo}..{hi}]:")
        for b in range(lo, hi + 1):
            ts = ohlcv.index[b] + timedelta(hours=3)
            print(
                f"    [{b}] {ts.strftime('%Y-%m-%d %H:%M')} O={ohlcv['open'].iloc[b]:.2f} H={ohlcv['high'].iloc[b]:.2f} L={ohlcv['low'].iloc[b]:.2f} C={ohlcv['close'].iloc[b]:.2f}  se={se[b]} le={le[b]}"
            )
    else:
        print(f"\n  Entry time {entry_dt} NOT found in ohlcv index!")
        # Try finding nearest
        closest = ohlcv.index[np.argmin(np.abs((ohlcv.index - entry_dt).total_seconds()))]
        print(f"  Nearest bar: {closest}")
