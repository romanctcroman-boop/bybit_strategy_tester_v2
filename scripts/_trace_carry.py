"""
Trace carry mechanism activity in FallbackEngineV4.
Add debug prints to understand when carry fires and what effect it has.
"""

import asyncio
import json
import sqlite3
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"


async def main():
    svc = BacktestService()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br) if isinstance(br, str) else (br or [])
    conns = json.loads(cr) if isinstance(cr, str) else (cr or [])
    gp = json.loads(gr) if isinstance(gr, str) else (gr or {})
    ms = gp.get("main_strategy", {})
    graph = {
        "name": name,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if ms:
        graph["main_strategy"] = ms

    candles = await svc._fetch_historical_data(
        "ETHUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2020-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc = btc[~btc.index.duplicated(keep="last")]

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)
    le = np.asarray(signals.entries.values, dtype=bool)
    lx = np.asarray(signals.exits.values, dtype=bool)
    se = np.asarray(signals.short_entries.values, dtype=bool)
    sx = np.asarray(signals.short_exits.values, dtype=bool)

    # ════════════════════════════════════════════════════════════════════
    # Simulate the engine loop manually to trace carry mechanism
    # ════════════════════════════════════════════════════════════════════

    timestamps = candles.index
    open_prices = candles["open"].values
    high_prices = candles["high"].values
    low_prices = candles["low"].values
    close_prices = candles["close"].values

    # We need to trace when carry fires. Let's instrument the actual engine.
    # Instead of modifying the engine, let's replicate the key logic.

    # Run the actual engine to get trades
    engine = FallbackEngineV4()
    inp = BacktestInput(
        candles=candles,
        long_entries=le,
        long_exits=lx,
        short_entries=se,
        short_exits=sx,
        initial_capital=1_000_000.0,
        position_size=0.001,
        use_fixed_amount=False,
        leverage=1,
        stop_loss=0.132,
        take_profit=0.023,
        taker_fee=0.0007,
        slippage=0.0,
        direction=TradeDirection.BOTH,
        pyramiding=1,
        interval="30",
        entry_on_next_bar_open=True,
    )
    result = engine.run(inp)
    trades = result.trades

    print(f"Total trades: {len(trades)}")
    print()

    # Now trace the carry mechanism by simulating the relevant parts
    # We need: position state, pending_short_exit, pending_short_signal_carry, last_exit_bar

    # Build a simple position tracker from trades
    # For each bar, determine: is short position open? what trade?

    trade_entries = {}  # bar_idx -> trade_num (1-indexed)
    trade_exits = {}  # bar_idx -> trade_num (1-indexed)

    for t_idx, t in enumerate(trades):
        if t.direction != "short":
            continue
        entry_ts = pd.Timestamp(t.entry_time)
        exit_ts = pd.Timestamp(t.exit_time)
        # Find bar indices
        for i, ts in enumerate(timestamps):
            ts_naive = ts.tz_localize(None) if ts.tzinfo else ts
            et_naive = entry_ts.tz_localize(None) if entry_ts.tzinfo else entry_ts
            if ts_naive == et_naive:
                trade_entries[i] = t_idx + 1
            xt_naive = exit_ts.tz_localize(None) if exit_ts.tzinfo else exit_ts
            if ts_naive == xt_naive:
                trade_exits[i] = t_idx + 1

    # Now simulate carry logic
    pending_short_exit = False
    pending_short_signal_carry = False
    last_exit_bar = -999
    in_short_position = False
    current_short_trade = None

    carry_events = []

    for i in range(1, len(timestamps)):
        # Step 1: Pending exit execution (simplified)
        if pending_short_exit and in_short_position:
            # Execute pending exit
            in_short_position = False
            pending_short_exit = False
            last_exit_bar = i

        # Step 2: Check if trade entered/exited at this bar
        if i in trade_entries:
            in_short_position = True
            current_short_trade = trade_entries[i]

        # Actually we need to know exit_reason. Let's use a different approach.
        # The key question: when does the carry mechanism set pending_short_signal_carry=True?

        # With entry_on_next_bar_open, raw_signal = SE[i-1]
        raw_signal = se[i - 1] if i > 0 else False

        if raw_signal and pending_short_exit:
            carry_events.append(
                {
                    "bar": i,
                    "ts": str(timestamps[i])[:19],
                    "signal_bar": str(timestamps[i - 1])[:19],
                    "pending_exit": True,
                }
            )

    print(f"Carry events detected (raw_signal & pending_exit): {len(carry_events)}")
    for ev in carry_events:
        print(f"  Bar {ev['bar']}: ts={ev['ts']}, signal from {ev['signal_bar']}")

    # ════════════════════════════════════════════════════════════════════
    # Better approach: Check all bars where SE[i-1]=True and position is open
    # These are the bars where carry COULD matter
    # ════════════════════════════════════════════════════════════════════

    print()
    print("=" * 70)
    print("Bars where SE[i-1]=True (signal) and position might be open:")
    print("=" * 70)

    # Build position state from trades (both long and short)
    position_state = np.zeros(len(timestamps), dtype=int)  # 0=empty, 1=long, -1=short

    for t in trades:
        entry_ts = pd.Timestamp(t.entry_time)
        exit_ts = pd.Timestamp(t.exit_time)
        entry_i = None
        exit_i = None
        for i, ts in enumerate(timestamps):
            ts_n = ts.tz_localize(None) if ts.tzinfo else ts
            en = entry_ts.tz_localize(None) if entry_ts.tzinfo else entry_ts
            ex = exit_ts.tz_localize(None) if exit_ts.tzinfo else exit_ts
            if ts_n == en:
                entry_i = i
            if ts_n == ex:
                exit_i = i
        if entry_i is not None and exit_i is not None:
            direction_val = -1 if t.direction == "short" else 1
            for j in range(entry_i, exit_i + 1):
                position_state[j] = direction_val

    # For Root #144:
    # Trade #143: entry 2026-02-07 13:00, exit 2026-02-07 16:00 (TP)
    # But with pending exit system, the position is actually open from entry bar
    # until the bar AFTER TP detection (because exit executes at next bar).
    # exit_time=16:00 means TP detected at 16:00, exit executes at 16:30.
    # So position is open from 13:00 through 16:00 inclusive (closed at 16:30).

    # Actually, with pending exit:
    # TP is detected at bar X (exit_time = X due to same-bar fix)
    # Position closes at bar X+1 (pending exit executes)
    # So from the engine's perspective, position is "open" until X+1

    # Our position_state array marks entry_i through exit_i, which uses exit_time=16:00
    # So position_state[16:00] = -1, position_state[16:30] = 0
    # But actually the engine still has position at bar 16:00's processing
    # (pending exit fires at 16:30, not 16:00)
    # For carry analysis, we need to extend position by 1 bar

    print("\nRoot #144 area position state:")
    for i, ts in enumerate(timestamps):
        ts_str = str(ts)[:16]
        if "2026-02-07 12" <= ts_str <= "2026-02-07 18":
            signal_flag = f"SE[i-1]={se[i - 1]:d}" if i > 0 else "N/A"
            print(f"  {ts_str}  pos={position_state[i]:+d}  SE={se[i]:d}  {signal_flag}")

    # ════════════════════════════════════════════════════════════════════
    # Direct comparison: Trade #144 engine vs TV
    # ════════════════════════════════════════════════════════════════════
    print()
    print("=" * 70)
    print("Trade #144 comparison")
    print("=" * 70)

    t143 = trades[142]  # 0-indexed
    t144 = trades[143]
    print(
        f"Engine trade #143: {t143.direction} entry={t143.entry_time} exit={t143.exit_time} reason={t143.exit_reason}"
    )
    print(
        f"Engine trade #144: {t144.direction} entry={t144.entry_time} exit={t144.exit_time} reason={t144.exit_reason}"
    )
    print(f"TV trade #144:     short entry=2026-02-08 03:30 (UTC, from as4.csv)")
    print()

    # The gap: engine enters 16:30, TV enters 03:30 next day = 11 hours later
    # This means TV skips the carry signal and waits for the next valid SE=1
    # Next SE=1 is at 2026-02-08 03:00 → entry at 03:30 with entry_on_next_bar_open

    # If we DISABLE carry, the engine should also skip to 03:00 signal → entry at 03:30
    print("If carry disabled: engine would skip SE[15:30] (blocked by position)")
    print("  Next SE=1 after 16:00 is at 2026-02-08 03:00")
    print("  Entry would be at 2026-02-08 03:30 (matching TV!)")


asyncio.run(main())
