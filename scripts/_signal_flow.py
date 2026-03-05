"""
Run engine, compare which of the 600 signals actually result in trades.
Then compare with TV's 147 trades to find the real difference.
"""

import asyncio
import json
import sqlite3
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import numpy as np
import pandas as pd
from loguru import logger

logger.remove()

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.indicator_handlers import calculate_rsi
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"


def load_graph():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
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
    return graph


# TV trades (entry open-time = bar_open[T+1], entry_price = close[T] = open[T+1])
# These are the entry open-times from z4.csv — converting TV's entry time to
# our bar_open_time convention (TV shows bar_open[T+1], we show bar_open[T])
# So to compare: TV_entry_time - 30min = our signal bar_open_time
TV_ENTRIES_RAW = [
    # (direction, TV_entry_open_time, entry_price, exit_price)
    ("short", "2025-01-01 13:30", 3334.62, "2025-01-08 17:00"),
    ("short", "2025-01-09 00:00", 3322.53, "2025-01-09 13:30"),
    ("short", "2025-01-09 17:30", 3285.67, "2025-01-09 19:30"),
    ("short", "2025-01-10 21:00", 3257.99, "2025-01-13 06:30"),
    ("long", "2025-01-13 13:30", 3075.39, "2025-01-14 00:00"),
    ("short", "2025-01-14 16:30", 3191.83, "2025-01-27 05:30"),
    ("long", "2025-01-27 08:00", 3068.83, "2025-01-27 14:30"),
    ("short", "2025-01-27 16:30", 3117.00, "2025-01-27 18:30"),
    ("short", "2025-01-28 18:00", 3165.71, "2025-01-28 20:30"),
    ("short", "2025-01-29 05:00", 3122.65, "2025-02-02 11:30"),
]


async def main():
    graph = load_graph()
    svc = BacktestService()
    START = pd.Timestamp("2025-01-01", tz="UTC")
    END = pd.Timestamp("2026-02-24", tz="UTC")
    candles = await svc._fetch_historical_data("ETHUSDT", "30", START, END)
    WARMUP = 500
    btc_start = START - pd.Timedelta(minutes=WARMUP * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START, END)
    warmup_start_ts = int(btc_start.timestamp() * 1000)
    warmup_end_ts = int(START.timestamp() * 1000)
    raw_warmup = await svc.adapter.get_historical_klines(
        symbol="BTCUSDT",
        interval="30",
        start_time=warmup_start_ts,
        end_time=warmup_end_ts,
        market_type="linear",
    )
    df_w = pd.DataFrame(raw_warmup)
    col_map = {
        "startTime": "timestamp",
        "open_time": "timestamp",
        "openPrice": "open",
        "highPrice": "high",
        "lowPrice": "low",
        "closePrice": "close",
    }
    for old, new in col_map.items():
        if old in df_w.columns and new not in df_w.columns:
            df_w = df_w.rename(columns={old: new})
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df_w.columns:
            df_w[col] = pd.to_numeric(df_w[col], errors="coerce")
    if "timestamp" in df_w.columns:
        if df_w["timestamp"].dtype in ["int64", "float64"]:
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms", utc=True)
        else:
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], utc=True)
        df_w = df_w.set_index("timestamp").sort_index()
    if btc_main.index.tz is None:
        btc_main.index = btc_main.index.tz_localize("UTC")
    btc_all = pd.concat([df_w, btc_main]).sort_index()
    btc_all = btc_all[~btc_all.index.duplicated(keep="last")]

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_all)
    signals = adapter.generate_signals(candles)
    le = np.asarray(signals.entries.values, dtype=bool)
    se = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(le), dtype=bool)
    )
    lx = np.asarray(signals.exits.values, dtype=bool) if signals.exits is not None else np.zeros(len(le), dtype=bool)
    sx = (
        np.asarray(signals.short_exits.values, dtype=bool)
        if signals.short_exits is not None
        else np.zeros(len(le), dtype=bool)
    )

    # Recompute RSI
    btc_close = btc_all["close"].copy()
    if candles.index.tz is None and btc_close.index.tz is not None:
        btc_close.index = btc_close.index.tz_localize(None)
    btc_rsi_arr = calculate_rsi(btc_close.values, period=14)
    btc_rsi = pd.Series(btc_rsi_arr, index=btc_close.index)
    rsi = btc_rsi.reindex(candles.index, method="ffill")

    result = FallbackEngineV4().run(
        BacktestInput(
            candles=candles,
            long_entries=le,
            long_exits=lx,
            short_entries=se,
            short_exits=sx,
            initial_capital=10_000.0,
            position_size=0.10,
            use_fixed_amount=True,
            fixed_amount=100.0,
            leverage=10,
            stop_loss=0.132,
            take_profit=0.023,
            taker_fee=0.0007,
            slippage=0.0,
            direction=TradeDirection.BOTH,
            pyramiding=1,
            interval="30",
        )
    )

    trades = result.trades
    print(f"Engine: {len(trades)} trades")

    # For each engine trade, find the matching signal
    # Engine entry_time = bar_open_time[signal_bar], entry_price = close[signal_bar]
    # TV entry_time = bar_open_time[signal_bar + 1]

    # Build a set of (entry_time, direction) for engine trades
    eng_entries = {}
    for t in trades:
        key = (pd.Timestamp(t.entry_time), t.direction)
        eng_entries[key] = t

    # Build signal times
    short_signal_times = [candles.index[i] for i in range(len(candles)) if se[i]]
    long_signal_times = [candles.index[i] for i in range(len(candles)) if le[i]]

    print("\nEngine entries that match signal times:")
    print(f"  All signal times count: short={len(short_signal_times)}, long={len(long_signal_times)}")

    # For each engine trade, check if its entry_time is in signal_times
    matched_signals = 0
    unmatched_trades = []
    for t in trades:
        et = pd.Timestamp(t.entry_time)
        if t.direction == "short":
            if et in short_signal_times:
                matched_signals += 1
            else:
                unmatched_trades.append(t)
        else:
            if et in long_signal_times:
                matched_signals += 1
            else:
                unmatched_trades.append(t)

    print(f"  Engine trades with matching signal: {matched_signals}")
    print(f"  Engine trades WITHOUT matching signal: {len(unmatched_trades)}")
    for t in unmatched_trades[:10]:
        print(f"    {t.direction} entry={t.entry_time} price={t.entry_price:.2f} exit={t.exit_reason}")

    # Now simulate what TV does: "entry on next bar" approach
    # In TV: entry_price = open[T+1] = close[T], but entry is ALLOWED on the NEXT bar
    # So if position is open on bar T when signal fires, TV would check:
    #   - is the position closed by the time bar T+1 opens?
    # With our engine, if TP/SL hit happens on bar T, position closes AND signal fires on bar T+1

    # Let's check: for the first 20 engine trades, find the signals that WERE active
    # and the signals between trades (which were "consumed" while position was open)
    print("\n\nFirst 20 engine short trades and signals between them:")
    short_trades = [t for t in trades if t.direction == "short"]

    for idx, trade in enumerate(short_trades[:20]):
        et = pd.Timestamp(trade.entry_time)
        xt = pd.Timestamp(trade.exit_time)

        # Find which signal matched this trade (entry_time = signal bar open time)
        # entry_price should equal close of that bar
        signal_idx = None
        for si, st in enumerate(short_signal_times):
            if st == et:
                signal_idx = si
                break

        # Signals that fired while this trade was open (blocked by pyramiding)
        signals_during_trade = [st for st in short_signal_times if et < st < xt]

        # Next signal after trade closes
        next_signals = [st for st in short_signal_times if st >= xt]
        next_sig = next_signals[0] if next_signals else None

        rsi_at_entry = float(rsi.loc[et]) if et in rsi.index else float("nan")
        print(
            f"\nTrade {idx + 1}: entry={str(et)[:16]}  exit={str(xt)[:16]}  ep={trade.entry_price:.2f}  RSI@entry={rsi_at_entry:.4f}  reason={trade.exit_reason}"
        )
        print(f"  Signals blocked during trade: {len(signals_during_trade)}")
        if signals_during_trade:
            for bs in signals_during_trade[:3]:
                rsi_b = float(rsi.loc[bs]) if bs in rsi.index else float("nan")
                print(f"    blocked: {str(bs)[:16]}  RSI={rsi_b:.4f}")
            if len(signals_during_trade) > 3:
                print(f"    ... and {len(signals_during_trade) - 3} more")
        if next_sig:
            rsi_ns = float(rsi.loc[next_sig]) if next_sig in rsi.index else float("nan")
            print(f"  Next signal after close: {str(next_sig)[:16]}  RSI={rsi_ns:.4f}  (gap={next_sig - xt})")


asyncio.run(main())
