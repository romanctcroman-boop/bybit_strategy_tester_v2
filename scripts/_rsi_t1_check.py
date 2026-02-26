"""
Check RSI at bar T+1 for every engine short entry.
Tests: does TV require RSI to remain < 52 on the entry bar (T+1)?

Engine fires on signal bar T (crossunder detected), enters at close[T] = open[T+1].
TV with calc_on_every_tick: also fires signal at bar T close, enters at open[T+1].
BUT: if RSI at bar T+1 is ALREADY >= 52 again... does TV skip?
"""

import asyncio
import json
import os
import sqlite3
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
CROSS_SHORT_LEVEL = 52.0
CROSS_LONG_LEVEL = 24.0


def load_graph():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()
    _, br, cr, gr = row
    blocks = json.loads(br) if isinstance(br, str) else (br or [])
    conns = json.loads(cr) if isinstance(cr, str) else (cr or [])
    gp = json.loads(gr) if isinstance(gr, str) else (gr or {})
    ms = gp.get("main_strategy", {})
    return {
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
        "main_strategy": ms,
    }


async def main():
    graph = load_graph()
    svc = BacktestService()

    # Fetch ETH candles
    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    if candles.index.tz is not None:
        candles.index = candles.index.tz_localize(None)

    # Fetch BTC with warmup
    WARMUP_BARS = 500
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    btc_main = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    if btc_main.index.tz is None:
        btc_main.index = btc_main.index.tz_localize("UTC")

    warmup_start_ts = int(btc_start.timestamp() * 1000)
    warmup_end_ts = int(START_DATE.timestamp() * 1000)
    raw_warmup = await svc.adapter.get_historical_klines(
        symbol="BTCUSDT", interval="30", start_time=warmup_start_ts, end_time=warmup_end_ts, market_type="linear"
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
    for col in ["open", "high", "low", "close"]:
        if col in df_w.columns:
            df_w[col] = pd.to_numeric(df_w[col], errors="coerce")
    if "timestamp" in df_w.columns:
        if df_w["timestamp"].dtype in ["int64", "float64"]:
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms", utc=True)
        else:
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], utc=True)
        df_w = df_w.set_index("timestamp").sort_index()

    btc_candles = pd.concat([df_w, btc_main]).sort_index()
    btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]
    print(f"BTC bars: {len(btc_candles)}  [{btc_candles.index[0]} .. {btc_candles.index[-1]}]")

    # Generate signals
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_candles)
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
    print(f"Signals: long={le.sum()} short={se.sum()}")

    # Run engine (baseline)
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
    print(f"Engine trades: {len(trades)}")

    # Get BTC RSI aligned to ETH candle index
    from backend.core.indicators import calculate_rsi

    btc_close_full = btc_candles["close"].copy()
    if btc_close_full.index.tz is not None:
        btc_close_full.index = btc_close_full.index.tz_localize(None)
    rsi_full_arr = calculate_rsi(btc_close_full.values, period=14)
    rsi_full = pd.Series(rsi_full_arr, index=btc_close_full.index)
    rsi_aligned = rsi_full.reindex(candles.index, method="ffill").fillna(method="bfill")

    rsi_prev = rsi_aligned.shift(1)
    crossunder = (rsi_prev >= CROSS_SHORT_LEVEL) & (rsi_aligned < CROSS_SHORT_LEVEL)
    # crossover (long signals) not used in this script — long analysis omitted

    # Separate short and long trades
    short_trades = [t for t in trades if t.direction == "short"]
    long_trades = [t for t in trades if t.direction == "long"]
    candles_idx = list(candles.index)

    print(f"\n{'=' * 110}")
    print("SHORT TRADES — RSI[T-1], RSI[T], RSI[T+1], RSI[T+2] at each engine entry")
    print(f"{'=' * 110}")
    print(
        f"{'#':>3}  {'Entry T (engine)':20}  {'RSI[T-1]':9} {'RSI[T]':9} {'RSI[T+1]':9} {'RSI[T+2]':9}  {'T+1>=52':8}"
    )
    print(f"{'-' * 110}")

    short_t1_above = []
    short_t1_below = []
    for i, t in enumerate(short_trades):
        entry_t = pd.Timestamp(t.entry_time)
        if entry_t.tz is not None:
            entry_t = entry_t.tz_localize(None)
        try:
            pos = candles_idx.index(entry_t)
        except ValueError:
            diffs = [abs((ts - entry_t).total_seconds()) for ts in candles_idx]
            pos = int(np.argmin(diffs))

        t_m1 = candles_idx[pos - 1] if pos > 0 else None
        t_0 = candles_idx[pos]
        t_p1 = candles_idx[pos + 1] if pos + 1 < len(candles_idx) else None
        t_p2 = candles_idx[pos + 2] if pos + 2 < len(candles_idx) else None

        rsi_m1 = rsi_aligned.get(t_m1, float("nan")) if t_m1 else float("nan")
        rsi_0 = rsi_aligned.get(t_0, float("nan"))
        rsi_p1 = rsi_aligned.get(t_p1, float("nan")) if t_p1 else float("nan")
        rsi_p2 = rsi_aligned.get(t_p2, float("nan")) if t_p2 else float("nan")

        t1_above = rsi_p1 >= CROSS_SHORT_LEVEL
        if t1_above:
            short_t1_above.append(i)
        else:
            short_t1_below.append(i)

        tag = "YES>=52" if t1_above else "no<52  "
        print(f"{i + 1:>3}  {entry_t!s:20}  {rsi_m1:9.4f} {rsi_0:9.4f} {rsi_p1:9.4f} {rsi_p2:9.4f}  {tag}")

    print(f"\n{'=' * 110}")
    print("SUMMARY (SHORT TRADES):")
    print(f"  RSI[T+1] >= 52 (TV would skip): {len(short_t1_above)}")
    print(f"  RSI[T+1] < 52  (TV fires too):  {len(short_t1_below)}")
    print(f"  Total engine shorts:             {len(short_trades)}")

    print(f"\n{'=' * 110}")
    print("LONG TRADES — RSI[T-1], RSI[T], RSI[T+1] at each engine entry")
    print(f"{'=' * 110}")
    print(f"{'#':>3}  {'Entry T (engine)':20}  {'RSI[T-1]':9} {'RSI[T]':9} {'RSI[T+1]':9}  {'T+1<=24':8}")
    print(f"{'-' * 110}")

    long_t1_below = []
    long_t1_above = []
    for i, t in enumerate(long_trades):
        entry_t = pd.Timestamp(t.entry_time)
        if entry_t.tz is not None:
            entry_t = entry_t.tz_localize(None)
        try:
            pos = candles_idx.index(entry_t)
        except ValueError:
            diffs = [abs((ts - entry_t).total_seconds()) for ts in candles_idx]
            pos = int(np.argmin(diffs))

        t_m1 = candles_idx[pos - 1] if pos > 0 else None
        t_0 = candles_idx[pos]
        t_p1 = candles_idx[pos + 1] if pos + 1 < len(candles_idx) else None

        rsi_m1 = rsi_aligned.get(t_m1, float("nan")) if t_m1 else float("nan")
        rsi_0 = rsi_aligned.get(t_0, float("nan"))
        rsi_p1 = rsi_aligned.get(t_p1, float("nan")) if t_p1 else float("nan")

        t1_below = rsi_p1 <= CROSS_LONG_LEVEL
        if t1_below:
            long_t1_below.append(i)
        else:
            long_t1_above.append(i)

        tag = "YES<=24" if t1_below else "no>24  "
        print(f"{i + 1:>3}  {entry_t!s:20}  {rsi_m1:9.4f} {rsi_0:9.4f} {rsi_p1:9.4f}  {tag}")

    print(f"\n{'=' * 110}")
    print("SUMMARY (LONG TRADES):")
    print(f"  RSI[T+1] <= 24 (TV would skip): {len(long_t1_below)}")
    print(f"  RSI[T+1] > 24  (TV fires too):  {len(long_t1_above)}")
    print(f"  Total engine longs:              {len(long_trades)}")

    # =====================================================================
    # HYPOTHESIS TEST: apply RSI[T+1] confirmation filter
    # =====================================================================
    print(f"\n{'=' * 110}")
    print("HYPOTHESIS TEST: Apply 'RSI stays below/above level at T+1' confirmation filter")
    print("If this filter reduces trade count to ~147, hypothesis is correct.")
    print(f"{'=' * 110}")

    se_confirmed = se.copy()
    le_confirmed = le.copy()
    candles_arr = candles_idx

    for idx_i in range(len(se_confirmed)):
        if se_confirmed[idx_i]:
            t1_idx = idx_i + 1
            if t1_idx < len(candles_arr):
                t1_time = candles_arr[t1_idx]
                rsi_val = rsi_aligned.get(t1_time, float("nan"))
                if not np.isnan(rsi_val) and rsi_val >= CROSS_SHORT_LEVEL:
                    se_confirmed[idx_i] = False

    for idx_i in range(len(le_confirmed)):
        if le_confirmed[idx_i]:
            t1_idx = idx_i + 1
            if t1_idx < len(candles_arr):
                t1_time = candles_arr[t1_idx]
                rsi_val = rsi_aligned.get(t1_time, float("nan"))
                if not np.isnan(rsi_val) and rsi_val <= CROSS_LONG_LEVEL:
                    le_confirmed[idx_i] = False

    print(f"Original:  short={se.sum()} long={le.sum()}")
    print(f"Confirmed: short={se_confirmed.sum()} long={le_confirmed.sum()}")

    result2 = FallbackEngineV4().run(
        BacktestInput(
            candles=candles,
            long_entries=le_confirmed,
            long_exits=lx,
            short_entries=se_confirmed,
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
    print(f"\nWith confirmation filter: {len(result2.trades)} trades  (TV=147)")
    longs2 = [t for t in result2.trades if t.direction == "long"]
    shorts2 = [t for t in result2.trades if t.direction == "short"]
    print(f"  {len(longs2)} long, {len(shorts2)} short  (TV: ~31 long, ~116 short)")

    # Rebuild crossunder signals with confirmation (module-level simulation)
    print()
    print("=" * 100)
    print("SIMULATING: Apply RSI[T+1] < 52 confirmation filter")
    print("(Same as: engine fires only if RSI stays below level on the bar when order would fill)")
    print()

    rsi_at_t1 = rsi_aligned.shift(-1)  # RSI at bar T+1 (lookahead from signal bar T)
    cross_short_confirmed = crossunder & (rsi_at_t1 < cross_short_level)
    cross_long_level = 24.0
    rsi_prev_long = rsi_prev_aligned  # noqa: F841
    crossover_long = (rsi_prev_aligned <= cross_long_level) & (rsi_aligned > cross_long_level)
    rsi_at_t1_long = rsi_aligned.shift(-1)
    cross_long_confirmed = crossover_long & (rsi_at_t1_long > cross_long_level)

    print(f"Original short crossunders: {crossunder.sum()}")
    print(f"Confirmed short crossunders (RSI[T+1] < 52): {cross_short_confirmed.sum()}")
    print(f"Original long crossovers: {crossover_long.sum()}")
    print(f"Confirmed long crossovers (RSI[T+1] > 24): {cross_long_confirmed.sum()}")


asyncio.run(main())
