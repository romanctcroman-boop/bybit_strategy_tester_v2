"""
Analyze trades 139 and 142 — same entry time & price but different exit price/pnl.
This is a SAME-BAR EXIT issue in the engine.
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

START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")


async def main():
    svc = BacktestService()
    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )

    # Trade 139: Long entry 2026-02-03 19:30, engine exit 20:30, TV exit 20:00
    # Entry price 2189.01, TP target = 2189.01 * 1.023 = 2239.36
    tp_139 = 2189.01 * 1.023
    print(f"Trade #139 (long): entry_px=2189.01, TP={tp_139:.2f}")
    print()

    # Show bars around 2026-02-03 19:30 - 21:00
    for ts_str in [
        "2026-02-03 19:00:00",
        "2026-02-03 19:30:00",
        "2026-02-03 20:00:00",
        "2026-02-03 20:30:00",
        "2026-02-03 21:00:00",
    ]:
        ts = pd.Timestamp(ts_str, tz="UTC")
        if ts in candles.index:
            bar = candles.loc[ts]
            reaches_tp = bar["high"] >= tp_139
            print(
                f"  {ts_str}  O={bar['open']:.2f}  H={bar['high']:.2f}  L={bar['low']:.2f}  C={bar['close']:.2f}  {'→TP HIT!' if reaches_tp else ''}"
            )

    print()
    print("  Engine exits at 20:30 with exit_px=2247.37 (bar close, not TP level)")
    print(f"  TV exits at 20:00 with exit_px=2239.36 (exact TP level = {tp_139:.2f})")
    print("  → Engine uses CLOSE price on same-bar TP? TV uses exact TP level.")
    print()

    # Trade 142: Short entry 2026-02-06 06:30, engine exit 07:30, TV exit 07:00
    # Entry price 1939.46, TP target = 1939.46 * (1 - 0.023) = 1894.85
    tp_142 = 1939.46 * (1 - 0.023)
    print(f"Trade #142 (short): entry_px=1939.46, TP={tp_142:.2f}")
    print()

    for ts_str in [
        "2026-02-06 06:00:00",
        "2026-02-06 06:30:00",
        "2026-02-06 07:00:00",
        "2026-02-06 07:30:00",
        "2026-02-06 08:00:00",
    ]:
        ts = pd.Timestamp(ts_str, tz="UTC")
        if ts in candles.index:
            bar = candles.loc[ts]
            reaches_tp = bar["low"] <= tp_142
            print(
                f"  {ts_str}  O={bar['open']:.2f}  H={bar['high']:.2f}  L={bar['low']:.2f}  C={bar['close']:.2f}  {'→TP HIT!' if reaches_tp else ''}"
            )

    print()
    print("  Engine exits at 07:30 with exit_px=1902.62 (NOT TP level)")
    print(f"  TV exits at 07:00 with exit_px=1894.85 (exact TP level = {tp_142:.2f})")
    print()

    # Now check: when does the engine enter?
    # entry_on_next_bar_open=True means signal on bar N → enter at bar N+1 open
    # If signal fires on bar 19:00, entry is at bar 19:30 open
    # If TP is hit on the SAME bar as entry (bar 19:30), engine may use close instead of TP level

    # Let's check the signal bar for trade 139
    # Engine: entry=19:30 → signal must be at 19:00
    sig_bar_139 = pd.Timestamp("2026-02-03 19:00:00", tz="UTC")
    entry_bar_139 = pd.Timestamp("2026-02-03 19:30:00", tz="UTC")
    if entry_bar_139 in candles.index:
        bar = candles.loc[entry_bar_139]
        print(
            f"Trade 139 entry bar (19:30): O={bar['open']:.2f} H={bar['high']:.2f} L={bar['low']:.2f} C={bar['close']:.2f}"
        )
        print(f"  Entry at open = {bar['open']:.2f}, TP = {tp_139:.2f}")
        print(
            f"  High = {bar['high']:.2f} {'> TP' if bar['high'] >= tp_139 else '< TP'} → {'TP hit on ENTRY bar!' if bar['high'] >= tp_139 else 'TP not hit on entry bar'}"
        )
        print()

    # Check bar 20:00 (TV exit bar)
    tv_exit_139 = pd.Timestamp("2026-02-03 20:00:00", tz="UTC")
    if tv_exit_139 in candles.index:
        bar = candles.loc[tv_exit_139]
        print(
            f"Trade 139 TV exit bar (20:00): O={bar['open']:.2f} H={bar['high']:.2f} L={bar['low']:.2f} C={bar['close']:.2f}"
        )
        print(f"  High = {bar['high']:.2f} {'> TP' if bar['high'] >= tp_139 else '< TP'}")

    # Check bar 20:30 (engine exit bar)
    eng_exit_139 = pd.Timestamp("2026-02-03 20:30:00", tz="UTC")
    if eng_exit_139 in candles.index:
        bar = candles.loc[eng_exit_139]
        print(
            f"Trade 139 engine exit bar (20:30): O={bar['open']:.2f} H={bar['high']:.2f} L={bar['low']:.2f} C={bar['close']:.2f}"
        )
        print(f"  Engine exit_px = 2247.37 → this is close price ({bar['close']:.2f})")

    print()
    print("=" * 80)
    print("SAME-BAR EXIT ANALYSIS")
    print("=" * 80)
    print()
    print("Trade #139 (long):")
    print("  Signal bar: 19:00")
    print("  Entry bar:  19:30 (next bar open)")
    print("  Entry_px:   2189.01 (bar 19:30 open)")
    print(f"  TP target:  {tp_139:.2f}")

    # Find which bar TP is first reached
    for offset in range(10):
        ts = entry_bar_139 + pd.Timedelta(minutes=30 * offset)
        if ts in candles.index:
            bar = candles.loc[ts]
            if bar["high"] >= tp_139:
                print(f"  TP first reached: bar {str(ts)[:19]} (high={bar['high']:.2f})")
                print(f"  Bars since entry: {offset}")
                if offset == 0:
                    print("  *** SAME BAR AS ENTRY → Engine uses close price instead of TP level ***")
                break

    print()
    print("Trade #142 (short):")
    entry_bar_142 = pd.Timestamp("2026-02-06 06:30:00", tz="UTC")
    print("  Entry_px:   1939.46 (bar 06:30 open)")
    print(f"  TP target:  {tp_142:.2f}")

    for offset in range(10):
        ts = entry_bar_142 + pd.Timedelta(minutes=30 * offset)
        if ts in candles.index:
            bar = candles.loc[ts]
            if bar["low"] <= tp_142:
                print(f"  TP first reached: bar {str(ts)[:19]} (low={bar['low']:.2f})")
                print(f"  Bars since entry: {offset}")
                if offset == 0:
                    print("  *** SAME BAR AS ENTRY → Engine uses close price instead of TP level ***")
                break


asyncio.run(main())
