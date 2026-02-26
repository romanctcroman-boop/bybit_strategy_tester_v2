"""Check the BTC RSI trajectory between prev trade exit and the two crossunder bars.
For each UNKNOWN case, trace the BTC RSI bar by bar from prev exit to TV entry.

HYPOTHESIS: Maybe these are cases where RSI crosses UNDER 52, but the PREVIOUS
trade was a SHORT that exited via TP/SL. After exit, RSI drops, crosses 52,
but this is just the "echo" of the previous trade's exit movement.
TV might have a mechanism to ignore the first cross after an exit.

OR: Maybe the cross_long (crossover 24) fired BETWEEN the two SE crosses,
and TV processes the long entry first, blocking the short entry.
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

    candles = await svc._fetch_historical_data(
        "ETHUSDT", "30", pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2026-02-24", tz="UTC")
    )
    btc = await svc._fetch_historical_data(
        "BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), pd.Timestamp("2026-02-24", tz="UTC")
    )
    btc = btc[~btc.index.duplicated(keep="last")]

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)
    le = np.asarray(signals.entries.values, dtype=bool)
    lx = np.asarray(signals.exits.values, dtype=bool)
    se = np.asarray(signals.short_entries.values, dtype=bool)
    sx = np.asarray(signals.short_exits.values, dtype=bool)
    times = candles.index

    rsi_arr = calculate_rsi(btc["close"].loc[candles.index], period=14)
    rsi = pd.Series(rsi_arr, index=candles.index)

    # BTC RSI with full warmup
    btc_rsi_full = pd.Series(calculate_rsi(btc["close"], period=14), index=btc.index)

    # UNKNOWN cases: (description, prev_exit_time, eng_signal_bar, tv_signal_bar)
    cases = [
        ("E#20/TV#22", "2025-02-21 19:00", "2025-02-22 10:30", "2025-02-22 14:30"),
        ("E#54/TV#56", "2025-05-09 14:30", "2025-05-09 15:00", "2025-05-09 19:00"),
        ("E#82/TV#85", "2025-08-15 15:30", "2025-08-16 01:00", "2025-08-16 13:30"),
        ("E#86/TV#89", "2025-08-25 19:00", "2025-08-27 02:30", "2025-08-27 12:00"),
        ("E#88/TV#91", "2025-09-01 20:30", "2025-09-02 11:00", "2025-09-02 18:00"),
        ("E#117/TV#119", "2025-11-24 17:30", "2025-11-25 00:00", "2025-11-25 05:00"),
    ]

    for desc, prev_exit, eng_sig, tv_sig in cases:
        prev_exit_ts = pd.Timestamp(prev_exit)
        eng_sig_ts = pd.Timestamp(eng_sig)
        tv_sig_ts = pd.Timestamp(tv_sig)

        print(f"\n{'=' * 90}")
        print(f"{desc}")
        print(f"Prev exit: {prev_exit}  |  Eng signal: {eng_sig}  |  TV signal: {tv_sig}")
        print(f"{'=' * 90}")

        # Find bars in range
        mask = (times >= prev_exit_ts - pd.Timedelta(hours=1)) & (times <= tv_sig_ts + pd.Timedelta(hours=1))
        range_idx = np.where(mask)[0]

        print(f"{'Bar':>4s}  {'Time':19s}  {'BTC RSI':>8s}  {'prev':>8s}  Cross↓52  SE   LE   LX   SX   Notes")
        print("-" * 90)

        for i in range_idx:
            ts = times[i]
            r = btc_rsi_full.get(ts, float("nan"))
            prev_r = btc_rsi_full.get(times[i - 1], float("nan")) if i > 0 else float("nan")
            cross = not np.isnan(prev_r) and prev_r >= 52 and r < 52

            notes = ""
            if ts == prev_exit_ts:
                notes = "← PREV EXIT"
            if ts == eng_sig_ts:
                notes += " ← ENG SIGNAL"
            if ts == tv_sig_ts:
                notes += " ← TV SIGNAL"

            se_val = se[i] if i < len(se) else False
            le_val = le[i] if i < len(le) else False
            lx_val = lx[i] if i < len(lx) else False
            sx_val = sx[i] if i < len(sx) else False

            marker = "YES" if cross else ""
            se_s = "SE" if se_val else ""
            le_s = "LE" if le_val else ""
            lx_s = "LX" if lx_val else ""
            sx_s = "SX" if sx_val else ""

            if cross or se_val or le_val or notes or ts == prev_exit_ts:
                print(
                    f"{i:4d}  {ts}  {r:8.4f}  {prev_r:8.4f}  {marker:8s}  {se_s:4s} {le_s:4s} {lx_s:4s} {sx_s:4s} {notes}"
                )

        # Count: how many SE crosses between prev exit and TV signal?
        mask2 = (times > prev_exit_ts) & (times <= tv_sig_ts)
        range2 = np.where(mask2)[0]
        se_count = sum(1 for i in range2 if se[i])
        le_count = sum(1 for i in range2 if le[i])
        cross_count = 0
        for i in range2:
            r = btc_rsi_full.get(times[i], float("nan"))
            prev_r = btc_rsi_full.get(times[i - 1], float("nan")) if i > 0 else float("nan")
            if not np.isnan(prev_r) and prev_r >= 52 and r < 52:
                cross_count += 1

        print(f"\n  Between prev exit and TV signal:")
        print(f"    Crossunders (BTC RSI >= 52 → < 52): {cross_count}")
        print(f"    SE=True signals: {se_count}")
        print(f"    LE=True signals: {le_count}")

        # KEY: Check if there's an LE signal between engine's SE and TV's SE
        mask3 = (times > eng_sig_ts) & (times < tv_sig_ts)
        range3 = np.where(mask3)[0]
        le_between = sum(1 for i in range3 if le[i])
        lx_between = sum(1 for i in range3 if lx[i])
        sx_between = sum(1 for i in range3 if sx[i])
        print(f"    LE between engine and TV signal: {le_between}")
        print(f"    LX between engine and TV signal: {lx_between}")
        print(f"    SX between engine and TV signal: {sx_between}")


asyncio.run(main())
