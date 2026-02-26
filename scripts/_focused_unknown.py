"""Focused analysis of the 6 UNKNOWN skip-1st-cross cases.
Check what's different between the 1st SE (engine fires) and 2nd SE (TV fires).
KEY QUESTION: Is there an SX (short exit) signal between the two SEs?
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
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.core.indicators.momentum import calculate_rsi


async def main():
    svc = BacktestService()
    conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?",
        ("dd2969a2-bbba-410e-b190-be1e8cc50b21",),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    graph = {
        "name": name,
        "blocks": json.loads(br),
        "connections": json.loads(cr),
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    ms = json.loads(gr).get("main_strategy", {})
    if ms:
        graph["main_strategy"] = ms

    START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
    END_DATE = pd.Timestamp("2026-02-24", tz="UTC")

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)

    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), START_DATE)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)
    le = np.asarray(signals.entries.values, dtype=bool)
    lx = np.asarray(signals.exits.values, dtype=bool)
    se = np.asarray(signals.short_entries.values, dtype=bool)
    sx = np.asarray(signals.short_exits.values, dtype=bool)
    times = candles.index

    # BTC RSI with full warmup
    btc_rsi_full = pd.Series(calculate_rsi(btc["close"], period=14), index=btc.index)

    cross_short_level = 52
    short_rsi_more = 50
    short_rsi_less = 70

    # Cases: (desc, prev_exit_utc, eng_signal_bar_utc, tv_signal_bar_utc)
    # Signal bar = entry_bar - 30min (because entry_on_next_bar_open)
    cases = [
        ("E#23/TV#22", "2025-02-21 19:00", "2025-02-22 10:30", "2025-02-22 14:30"),
        ("E#57/TV#56", "2025-05-09 14:30", "2025-05-09 15:00", "2025-05-09 19:00"),
        ("E#85/TV#85", "2025-08-15 15:30", "2025-08-16 01:00", "2025-08-16 13:30"),
        ("E#89/TV#89", "2025-08-25 19:00", "2025-08-27 02:30", "2025-08-27 12:00"),
        ("E#91/TV#91", "2025-09-01 20:30", "2025-09-02 11:00", "2025-09-02 18:00"),
        ("E#120/TV#119", "2025-11-24 17:30", "2025-11-25 00:00", "2025-11-25 05:00"),
    ]

    print("=" * 110)
    print("FOCUSED ANALYSIS: 6 UNKNOWN skip-1st-cross cases")
    print("=" * 110)

    for desc, prev_exit, eng_sig, tv_sig in cases:
        prev_exit_ts = pd.Timestamp(prev_exit)
        eng_sig_ts = pd.Timestamp(eng_sig)
        tv_sig_ts = pd.Timestamp(tv_sig)
        # Make tz-aware if index is tz-aware
        if candles.index.tz is not None:
            prev_exit_ts = prev_exit_ts.tz_localize(candles.index.tz)
            eng_sig_ts = eng_sig_ts.tz_localize(candles.index.tz)
            tv_sig_ts = tv_sig_ts.tz_localize(candles.index.tz)

        print(f"\n{'=' * 110}")
        print(f"{desc}")
        print(f"  Prev exit:    {prev_exit}")
        print(f"  Eng signal:   {eng_sig} → entry at {eng_sig_ts + pd.Timedelta(minutes=30)}")
        print(f"  TV signal:    {tv_sig} → entry at {tv_sig_ts + pd.Timedelta(minutes=30)}")

        # Get indices
        eng_idx = candles.index.get_loc(eng_sig_ts) if eng_sig_ts in candles.index else None
        tv_idx = candles.index.get_loc(tv_sig_ts) if tv_sig_ts in candles.index else None
        prev_exit_idx = candles.index.get_loc(prev_exit_ts) if prev_exit_ts in candles.index else None

        if eng_idx is None or tv_idx is None:
            print("  INDEX NOT FOUND!")
            continue

        # Check SE, LE, LX, SX between prev exit and TV signal
        print(f"\n  Signals between prev exit ({prev_exit}) and TV signal ({tv_sig}):")
        se_bars = []
        sx_bars = []
        le_bars = []
        lx_bars = []
        for i in range(prev_exit_idx + 1 if prev_exit_idx else 0, tv_idx + 1):
            ts = times[i]
            if se[i]:
                se_bars.append((i, ts))
            if sx[i]:
                sx_bars.append((i, ts))
            if le[i]:
                le_bars.append((i, ts))
            if lx[i]:
                lx_bars.append((i, ts))

        print(f"    SE bars ({len(se_bars)}): {[(str(ts), idx) for idx, ts in se_bars]}")
        print(f"    SX bars ({len(sx_bars)}): {[(str(ts), idx) for idx, ts in sx_bars]}")
        print(f"    LE bars ({len(le_bars)}): {[(str(ts), idx) for idx, ts in le_bars]}")
        print(f"    LX bars ({len(lx_bars)}): {[(str(ts), idx) for idx, ts in lx_bars]}")

        # For each SE bar, check RSI details
        print(f"\n  RSI at each SE bar:")
        for idx, ts in se_bars:
            rsi_val = btc_rsi_full.get(ts, float("nan"))
            rsi_prev = btc_rsi_full.get(times[idx - 1], float("nan")) if idx > 0 else float("nan")
            cross = (not np.isnan(rsi_prev)) and rsi_prev >= cross_short_level and rsi_val < cross_short_level
            in_range = (not np.isnan(rsi_val)) and rsi_val >= short_rsi_more and rsi_val <= short_rsi_less
            print(
                f"    [{idx}] {ts}: RSI={rsi_val:.4f}, prev={rsi_prev:.4f}, cross↓52={cross}, range[50,70]={in_range}"
            )

        # KEY: Check SX between 1st SE and 2nd SE
        if len(se_bars) >= 2:
            first_se_idx = se_bars[0][0]
            second_se_idx = se_bars[1][0]
            sx_between = [(idx, ts) for idx, ts in sx_bars if first_se_idx < idx < second_se_idx]
            le_between = [(idx, ts) for idx, ts in le_bars if first_se_idx < idx < second_se_idx]
            lx_between = [(idx, ts) for idx, ts in lx_bars if first_se_idx < idx < second_se_idx]
            print(f"\n  Between 1st SE and 2nd SE:")
            print(f"    SX: {[(str(ts), idx) for idx, ts in sx_between]}")
            print(f"    LE: {[(str(ts), idx) for idx, ts in le_between]}")
            print(f"    LX: {[(str(ts), idx) for idx, ts in lx_between]}")

        # NEW: Check previous trade exit
        # What was the previous trade? Was it a SHORT or LONG?
        # If prev trade was SHORT and it exited, the engine is flat.
        # So the 1st SE should fire. Why does TV skip it?

        # Check if there are crossunders between the two SEs where SE=False
        if len(se_bars) >= 2:
            first_se_idx = se_bars[0][0]
            second_se_idx = se_bars[1][0]
            print(f"\n  Crossunders ↓52 between 1st SE and 2nd SE (where SE=False):")
            for i in range(first_se_idx + 1, second_se_idx):
                rsi_val = btc_rsi_full.get(times[i], float("nan"))
                rsi_prev = btc_rsi_full.get(times[i - 1], float("nan")) if i > 0 else float("nan")
                cross = (not np.isnan(rsi_prev)) and rsi_prev >= cross_short_level and rsi_val < cross_short_level
                in_range = (not np.isnan(rsi_val)) and rsi_val >= short_rsi_more and rsi_val <= short_rsi_less
                if cross:
                    print(
                        f"    [{i}] {times[i]}: RSI={rsi_val:.4f}, prev={rsi_prev:.4f}, "
                        f"cross=True, range={in_range}, SE={se[i]}"
                    )

        # CRITICAL CHECK: Does the PREVIOUS trade end at prev_exit?
        # And what type was it (long/short)?
        # Let's check signals at the prev exit bar
        if prev_exit_idx is not None:
            print(f"\n  At prev exit bar [{prev_exit_idx}] {prev_exit}:")
            print(f"    SE={se[prev_exit_idx]}, SX={sx[prev_exit_idx]}, LE={le[prev_exit_idx]}, LX={lx[prev_exit_idx]}")
            # Check if SX fired at exit bar (meaning a short exited)
            rsi_exit = btc_rsi_full.get(prev_exit_ts, float("nan"))
            print(f"    BTC RSI: {rsi_exit:.4f}")


asyncio.run(main())
