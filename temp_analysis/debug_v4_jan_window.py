"""Find WHY FallbackV4 misses 3 trades in Jan 8-10 2025 range."""

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

from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

adapter = StrategyBuilderAdapter(strategy_graph, btcusdt_ohlcv=btc_ohlcv)
signals = adapter.generate_signals(ohlcv)
n = len(ohlcv)
se = np.asarray(signals.short_entries, dtype=bool)
le = np.asarray(signals.entries, dtype=bool)

# The 3 missing trades have entry_price = open[i+1] for Numba
# i.e. the signal bar is in the index just before the entry:
# ep=3322.53 → Jan 8, 23:00 UTC
# ep=3285.67 → Jan 9, 17:00 UTC
# ep=3257.99 → Jan 10, 20:30 UTC
# Find these bars
target_entry_prices = [3322.53, 3285.67, 3257.99]
print("Finding bars with these open prices (these are entry bars for Numba):")
for ep in target_entry_prices:
    mask = abs(ohlcv["open"] - ep) < 0.01
    idx = ohlcv.index[mask]
    if len(idx) > 0:
        for ts in idx:
            i = ohlcv.index.get_loc(ts)
            utc3 = ts + timedelta(hours=3)
            signal_bar = i - 1
            sig_utc3 = ohlcv.index[signal_bar] + timedelta(hours=3)
            print(f"\n  ep={ep}: bar[{i}] = {utc3.strftime('%Y-%m-%d %H:%M')} UTC+3")
            print(f"    Signal bar[{signal_bar}] = {sig_utc3.strftime('%Y-%m-%d %H:%M')} UTC+3: se={se[signal_bar]}")
            print(f"    (This bar[{i}]): se={se[i]}")
            # Show context
            lo = max(0, i - 5)
            hi = min(n - 1, i + 3)
            print(f"    Context bars [{lo}..{hi}]:")
            for b in range(lo, hi + 1):
                ts2 = ohlcv.index[b] + timedelta(hours=3)
                print(
                    f"      [{b}] {ts2.strftime('%Y-%m-%d %H:%M')}  O={ohlcv['open'].iloc[b]:.2f} H={ohlcv['high'].iloc[b]:.2f} L={ohlcv['low'].iloc[b]:.2f} C={ohlcv['close'].iloc[b]:.2f}  se={se[b]} le={le[b]}"
                )
    else:
        print(f"  ep={ep}: NOT FOUND in ohlcv!")

# Now find what happens in V4 around Jan 2-14
# Check what trade is open in V4 during Jan 8-14
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2


def make_input():
    return BacktestInput(
        candles=ohlcv,
        long_entries=le,
        short_entries=se,
        long_exits=np.asarray(signals.exits, dtype=bool),
        short_exits=np.asarray(signals.short_exits, dtype=bool),
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


print("\n\nRunning V4...")
out_v4 = FallbackEngineV4().run(make_input())
print("Running Numba...")
out_nb = NumbaEngineV2().run(make_input())


def get_trades(out, direction="short"):
    trades = []
    for t in out.trades:
        if isinstance(t, dict):
            d = t.get("direction", "")
            ep = t.get("entry_price", 0)
            et = t.get("entry_time", "")
            xt = t.get("exit_time", "")
            pnl = t.get("pnl", 0)
            xr = t.get("exit_reason", "")
        else:
            d = str(getattr(t, "direction", ""))
            ep = float(getattr(t, "entry_price", 0))
            et = str(getattr(t, "entry_time", ""))
            xt = str(getattr(t, "exit_time", ""))
            pnl = float(getattr(t, "pnl", 0))
            xr = str(getattr(t, "exit_reason", ""))
        if d.lower() == direction:
            trades.append(
                {
                    "entry_time": et,
                    "exit_time": xt,
                    "entry_price": round(ep, 4),
                    "pnl": round(pnl, 4),
                    "exit_reason": xr,
                }
            )
    return sorted(trades, key=lambda x: x["entry_time"])


print("\n=== Jan trades in V4 ===")
v4_jan = [t for t in get_trades(out_v4, "short") if "2025-01" in t["entry_time"]]
for t in v4_jan:
    et = (
        pd.Timestamp(t["entry_time"]).tz_localize("UTC")
        if "+" not in t["entry_time"] and "Z" not in t["entry_time"]
        else pd.Timestamp(t["entry_time"])
    )
    xt = (
        pd.Timestamp(t["exit_time"]).tz_localize("UTC")
        if "+" not in t["exit_time"] and "Z" not in t["exit_time"]
        else pd.Timestamp(t["exit_time"])
    )
    et3 = (et + timedelta(hours=3)).strftime("%m/%d %H:%M")
    xt3 = (xt + timedelta(hours=3)).strftime("%m/%d %H:%M")
    print(f"  SHORT ep={t['entry_price']:.2f} [{et3} → {xt3}]  pnl={t['pnl']:.2f}  {t['exit_reason']}")

print()
print("=== Jan trades in Numba ===")
nb_jan = [t for t in get_trades(out_nb, "short") if "2025-01" in t["entry_time"]]
for t in nb_jan:
    et = pd.Timestamp(t["entry_time"])
    xt = pd.Timestamp(t["exit_time"])
    et3 = (et + timedelta(hours=3)).strftime("%m/%d %H:%M")
    xt3 = (xt + timedelta(hours=3)).strftime("%m/%d %H:%M")
    print(f"  SHORT ep={t['entry_price']:.2f} [{et3} → {xt3}]  pnl={t['pnl']:.2f}  {t['exit_reason']}")

# Also show ALL V4 trades in this window (including longs)
print()
print("=== ALL V4 trades in Jan 2 - Jan 15 window ===")
for t in out_v4.trades:
    if isinstance(t, dict):
        et_str = t.get("entry_time", "")
    else:
        et_str = str(getattr(t, "entry_time", ""))
    if "2025-01-0" in et_str or "2025-01-1" in et_str:
        if isinstance(t, dict):
            d = t.get("direction", "")
            ep = t.get("entry_price", 0)
            xt_str = t.get("exit_time", "")
            pnl = t.get("pnl", 0)
            xr = t.get("exit_reason", "")
        else:
            d = str(getattr(t, "direction", ""))
            ep = float(getattr(t, "entry_price", 0))
            xt_str = str(getattr(t, "exit_time", ""))
            pnl = float(getattr(t, "pnl", 0))
            xr = str(getattr(t, "exit_reason", ""))
        et = pd.Timestamp(et_str)
        xt = pd.Timestamp(xt_str)
        et3 = (et + timedelta(hours=3)).strftime("%m/%d %H:%M")
        xt3 = (xt + timedelta(hours=3)).strftime("%m/%d %H:%M")
        print(f"  {d.upper():5s} ep={ep:.2f} [{et3} → {xt3}]  pnl={pnl:.2f}  {xr}")
