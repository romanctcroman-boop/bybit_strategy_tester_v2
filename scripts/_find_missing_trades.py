"""
Find the 3 missing trades between our engine (118) and TV (121).

Strategy: 
- Our engine enters at close[signal_bar] (1 bar EARLY vs TV)
- TV enters at open[signal_bar+1] = close[signal_bar] (same price but TV's position
  starts 1 bar later)
- This means our position can block a signal that TV would catch:
  TV position closes at bar T, signal fires at bar T → TV enters at open[T+1]
  Our position also closes at bar T+1, but if signal also fires at bar T, we already
  entered at close[T] before we closed — this doesn't work.

The real mechanism:
- Because we enter at close[signal_bar] (= open[signal_bar+1]),
  if a position exits at bar X+1 (execution bar), and a NEW signal fires at bar X,
  we'll MISS it because our position is still open at bar X
  (exit is pending, executed at open of bar X+1, but we check exit at start of X+1).
  
  Actually the engine checks:
    1. Execute pending exits first
    2. Check SL/TP for open positions  
    3. Check new entries

  So if: pending_exit runs at bar X+1 (open), AND signal fires at bar X,
  then at bar X our position is still technically active (exit is pending).
  TV's position exits at bar X-1 detection bar, so at bar X TV has no open position.
  TV would CATCH the signal at bar X.

Let me trace through all signal bars and see where our position is still open
when a signal fires, that TV would have caught.
"""
import sys
from datetime import UTC, datetime

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

import sqlite3

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "8597c9e0-c147-4d9a-8025-92994b4cdf1b"


def load_ohlcv():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM bybit_kline_audit
        WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear'
          AND open_time >= ? AND open_time < ?
        ORDER BY open_time ASC
        """,
        (
            int(datetime(2025, 11, 1, tzinfo=UTC).timestamp() * 1000),
            int(datetime(2026, 2, 23, tzinfo=UTC).timestamp() * 1000),
        ),
    )
    rows = cursor.fetchall()
    conn.close()
    df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume"])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df.set_index("open_time", inplace=True)
    return df


def get_signals(ohlcv):
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT builder_blocks, builder_connections, builder_graph, name FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cursor.fetchone()
    conn.close()

    import json
    builder_blocks = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    builder_connections = json.loads(row[1]) if isinstance(row[1], str) else row[1]
    builder_graph_raw = json.loads(row[2]) if isinstance(row[2], str) else row[2]

    strategy_graph = {
        "name": row[3],
        "description": "",
        "blocks": builder_blocks,
        "connections": builder_connections,
        "market_type": "linear",
        "direction": "both",
        "interval": "15",
    }
    if builder_graph_raw and isinstance(builder_graph_raw, dict) and builder_graph_raw.get("main_strategy"):
        strategy_graph["main_strategy"] = builder_graph_raw["main_strategy"]

    adapter = StrategyBuilderAdapter(strategy_graph)
    signals = adapter.generate_signals(ohlcv)
    long_arr = np.asarray(signals.entries.values, dtype=bool)
    short_arr = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(long_arr), dtype=bool)
    )
    return long_arr, short_arr


def run_backtest_with_signal_trace(ohlcv, long_arr, short_arr):
    """
    Run a manual simulation of the engine, tracking all signals and
    whether they were blocked or executed. Returns list of:
    (signal_bar, direction, was_executed, block_reason)
    """
    sl_pct = 0.03
    tp_pct = 0.015
    
    times = ohlcv.index
    closes = ohlcv["close"].values
    highs = ohlcv["high"].values
    lows = ohlcv["low"].values
    
    n = len(times)
    
    # State
    long_open = False
    short_open = False
    long_entry_price = 0.0
    long_sl = 0.0
    long_tp = 0.0
    short_entry_price = 0.0
    short_sl = 0.0
    short_tp = 0.0
    
    pending_long_exit = False
    pending_short_exit = False
    pending_long_exit_price = 0.0
    pending_short_exit_price = 0.0
    
    trades = []         # completed trades
    skipped = []        # signals that were skipped (position still open)
    
    long_entry_bar = -1
    short_entry_bar = -1
    
    for i in range(n):
        t = times[i]
        c = closes[i]
        h = highs[i]
        lo = lows[i]
        
        # 1. Execute pending exits
        if pending_long_exit and long_open:
            pnl = (pending_long_exit_price / long_entry_price - 1) * (100 / 1.015)  # approx
            trades.append((long_entry_bar, i, "long", long_entry_price, pending_long_exit_price))
            long_open = False
            pending_long_exit = False
        
        if pending_short_exit and short_open:
            trades.append((short_entry_bar, i, "short", short_entry_price, pending_short_exit_price))
            short_open = False
            pending_short_exit = False
        
        # 2. Check SL/TP for open positions
        if long_open:
            if lo <= long_sl:
                pending_long_exit = True
                pending_long_exit_price = long_sl
            elif h >= long_tp:
                pending_long_exit = True
                pending_long_exit_price = long_tp
        
        if short_open:
            if h >= short_sl:
                pending_short_exit = True
                pending_short_exit_price = short_sl
            elif lo <= short_tp:
                pending_short_exit = True
                pending_short_exit_price = short_tp
        
        # 3. Check new signals — pyramiding=1, so block if already open or pending
        if long_arr[i]:
            if long_open or pending_long_exit:
                skipped.append((i, t, "long", c, "long_already_open"))
            else:
                # Enter at close[i]
                long_open = True
                long_entry_price = c
                long_sl = c * (1 - sl_pct)
                long_tp = c * (1 + tp_pct)
                long_entry_bar = i
        
        if short_arr[i]:
            if short_open or pending_short_exit:
                skipped.append((i, t, "short", c, "short_already_open"))
            else:
                # Enter at close[i]
                short_open = True
                short_entry_price = c
                short_sl = c * (1 + sl_pct)
                short_tp = c * (1 - tp_pct)
                short_entry_bar = i
    
    return trades, skipped


def main():
    print("=== Finding 3 missing trades: signal blocked analysis ===")
    
    ohlcv = load_ohlcv()
    long_arr, short_arr = get_signals(ohlcv)
    
    print(f"Total signals: {long_arr.sum()} long, {short_arr.sum()} short = {long_arr.sum() + short_arr.sum()} total")
    print()
    
    trades, skipped = run_backtest_with_signal_trace(ohlcv, long_arr, short_arr)
    
    print(f"Simulated trades: {len(trades)}")
    print(f"Skipped signals: {len(skipped)}")
    print()
    
    if skipped:
        print("=== Skipped signals (position still open when signal fired) ===")
        print(f"{'#':<4} {'time (UTC)':<22} {'side':<7} {'close':<10} {'reason'}")
        print("-" * 60)
        for j, (idx, t, side, price, reason) in enumerate(skipped):
            print(f"{j+1:<4} {str(t)[:19]:<22} {side:<7} {price:<10.1f} {reason}")
    
    print()
    print("=== Detailed skip analysis: what PREV trade was blocking? ===")
    times = ohlcv.index
    closes = ohlcv["close"].values
    
    for idx, t, side, price, reason in skipped:
        # Find which trade was blocking
        # Trade is blocking if it started before idx and exits >= idx
        blocking = [tr for tr in trades if tr[0] < idx <= tr[1] and tr[2] == side]
        if blocking:
            blocker = blocking[-1]
            bt = times[blocker[0]]
            et = times[blocker[1]]
            print(f"  Signal: {side} @ {str(t)[:19]} price={price:.1f}")
            print(f"  Blocked by: {blocker[2]} entry={str(bt)[:19]} exit={str(et)[:19]} entry_p={blocker[3]:.1f}")
            print()


if __name__ == "__main__":
    main()
