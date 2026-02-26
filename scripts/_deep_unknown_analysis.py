"""Deep analysis of the 6 UNKNOWN skip-1st-cross cases.
Focus on: Why does TV enter on a bar where our SE=False?
Check RSI range at TV signal bar vs engine signal bar.
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

    # BTC: separate warmup + main (critical!)
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

    # BTC RSI with full warmup (aligned to ETH bars)
    btc_rsi_full = pd.Series(calculate_rsi(btc["close"], period=14), index=btc.index)

    # Get BTC RSI aligned to ETH times
    btc_rsi_eth = btc_rsi_full.reindex(candles.index)

    cross_short_level = 52
    short_rsi_more = 50  # range lower bound
    short_rsi_less = 70  # range upper bound

    # UNKNOWN cases with UPDATED numbering from _match_trades_v2.py
    # (eng_trade#, tv_trade#, prev_exit_utc, eng_entry_utc, tv_entry_utc)
    cases = [
        ("E#23/TV#22", "2025-02-22 11:00", "2025-02-22 15:00"),
        ("E#57/TV#56", "2025-05-09 15:30", "2025-05-09 19:30"),
        ("E#85/TV#85", "2025-08-16 01:30", "2025-08-16 14:00"),
        ("E#89/TV#89", "2025-08-27 03:00", "2025-08-27 12:30"),
        ("E#91/TV#91", "2025-09-02 11:30", "2025-09-02 18:30"),
        ("E#120/TV#119", "2025-11-25 00:30", "2025-11-25 05:30"),
    ]

    print("=" * 120)
    print("DEEP ANALYSIS: Why does TV skip the 1st valid crossunder?")
    print("=" * 120)

    for desc, eng_entry, tv_entry in cases:
        eng_entry_ts = pd.Timestamp(eng_entry, tz="UTC")
        tv_entry_ts = pd.Timestamp(tv_entry, tz="UTC")

        # Signal bars (entry - 1 bar = entry - 30min for 30m timeframe)
        eng_signal_ts = eng_entry_ts - pd.Timedelta(minutes=30)
        tv_signal_ts = tv_entry_ts - pd.Timedelta(minutes=30)

        print(f"\n{'=' * 120}")
        print(f"{desc}")
        print(f"  Engine entry: {eng_entry} (signal at {eng_signal_ts})")
        print(f"  TV entry:     {tv_entry} (signal at {tv_signal_ts})")
        print(f"{'=' * 120}")

        # Get RSI at engine signal bar and TV signal bar
        eng_sig_idx = candles.index.get_loc(eng_signal_ts) if eng_signal_ts in candles.index else None
        tv_sig_idx = candles.index.get_loc(tv_signal_ts) if tv_signal_ts in candles.index else None

        if eng_sig_idx is not None:
            rsi_eng = btc_rsi_eth.iloc[eng_sig_idx]
            rsi_eng_prev = btc_rsi_eth.iloc[eng_sig_idx - 1] if eng_sig_idx > 0 else float("nan")
            se_eng = se[eng_sig_idx]
            cross_eng = (rsi_eng_prev >= cross_short_level) and (rsi_eng < cross_short_level)
            range_eng = (rsi_eng >= short_rsi_more) and (rsi_eng <= short_rsi_less)
            print(f"\n  ENGINE signal bar ({eng_signal_ts}):")
            print(f"    BTC RSI = {rsi_eng:.4f}, prev = {rsi_eng_prev:.4f}")
            print(f"    Crossunder (prev≥52 & cur<52): {cross_eng}")
            print(f"    Range (50 ≤ rsi ≤ 70): {range_eng}  (rsi={rsi_eng:.4f})")
            print(f"    SE = {se_eng}")

        if tv_sig_idx is not None:
            rsi_tv = btc_rsi_eth.iloc[tv_sig_idx]
            rsi_tv_prev = btc_rsi_eth.iloc[tv_sig_idx - 1] if tv_sig_idx > 0 else float("nan")
            se_tv = se[tv_sig_idx]
            cross_tv = (rsi_tv_prev >= cross_short_level) and (rsi_tv < cross_short_level)
            range_tv = (rsi_tv >= short_rsi_more) and (rsi_tv <= short_rsi_less)
            print(f"\n  TV signal bar ({tv_signal_ts}):")
            print(f"    BTC RSI = {rsi_tv:.4f}, prev = {rsi_tv_prev:.4f}")
            print(f"    Crossunder (prev≥52 & cur<52): {cross_tv}")
            print(f"    Range (50 ≤ rsi ≤ 70): {range_tv}  (rsi={rsi_tv:.4f})")
            print(f"    SE = {se_tv}")
        else:
            print(f"\n  TV signal bar ({tv_signal_ts}): NOT FOUND IN INDEX!")
            # Try nearby bars
            for offset in [-30, 0, 30]:
                ts_try = tv_signal_ts + pd.Timedelta(minutes=offset)
                if ts_try in candles.index:
                    idx = candles.index.get_loc(ts_try)
                    rsi_try = btc_rsi_eth.iloc[idx]
                    rsi_try_prev = btc_rsi_eth.iloc[idx - 1] if idx > 0 else float("nan")
                    se_try = se[idx]
                    cross_try = (rsi_try_prev >= cross_short_level) and (rsi_try < cross_short_level)
                    range_try = (rsi_try >= short_rsi_more) and (rsi_try <= short_rsi_less)
                    print(
                        f"    Nearby bar {ts_try}: RSI={rsi_try:.4f}, prev={rsi_try_prev:.4f}, cross={cross_try}, range={range_try}, SE={se_try}"
                    )

        # NEW: Check ALL bars between engine signal and TV signal
        print(f"\n  ALL bars from engine signal to TV signal:")
        start_idx = eng_sig_idx if eng_sig_idx is not None else 0
        end_idx = tv_sig_idx if tv_sig_idx is not None else len(times) - 1

        print(
            f"  {'Bar':>5}  {'Time':19s}  {'BTC RSI':>8s}  {'prev RSI':>8s}  {'Cross↓52':>8s}  {'In Range':>8s}  {'SE':>4s}  {'LE':>4s}"
        )
        print(f"  {'-' * 85}")

        for i in range(max(0, start_idx - 2), min(len(times), end_idx + 3)):
            ts = times[i]
            r = btc_rsi_eth.iloc[i] if not pd.isna(btc_rsi_eth.iloc[i]) else float("nan")
            r_prev = btc_rsi_eth.iloc[i - 1] if i > 0 and not pd.isna(btc_rsi_eth.iloc[i - 1]) else float("nan")

            cross = (not np.isnan(r_prev)) and (r_prev >= cross_short_level) and (r < cross_short_level)
            in_range = (not np.isnan(r)) and (r >= short_rsi_more) and (r <= short_rsi_less)

            se_val = "SE" if (i < len(se) and se[i]) else ""
            le_val = "LE" if (i < len(le) and le[i]) else ""
            cross_str = "YES" if cross else ""
            range_str = "YES" if in_range else "NO"

            marker = ""
            if i == eng_sig_idx:
                marker = " ← ENG SIG"
            if i == tv_sig_idx:
                marker += " ← TV SIG"

            print(
                f"  {i:5d}  {ts}  {r:8.4f}  {r_prev:8.4f}  {cross_str:>8s}  {range_str:>8s}  {se_val:>4s}  {le_val:>4s}{marker}"
            )

    # CRITICAL: Check what happens when engine enters trade on the 1st cross.
    # After entry, the engine is IN a position. Next SE signals are ignored because
    # pyramiding=1. But TV doesn't enter on the 1st cross. Why?

    print("\n\n" + "=" * 120)
    print("HYPOTHESIS: TV uses process_orders_on_close=true semantics differently")
    print("=" * 120)
    print("""
In Pine Script with process_orders_on_close=true:
  - Bar closes → signals evaluated → orders processed AT BAR CLOSE
  
But our engine uses entry_on_next_bar_open=true:
  - Bar[i-1] closes → signal detected → entry at bar[i] OPEN
  
These SHOULD be equivalent for bar-close data. But what if TV evaluates 
the signal AND checks if the position can be opened in a single atomic step
at bar close, while our engine detects the signal at bar close and then 
enters at the NEXT bar?

The difference would matter if: between the signal bar close and the next 
bar open, something changes that would prevent entry. But since we're using 
bar-close data, nothing changes...

UNLESS: TV uses calc_on_every_tick=true or calc_on_order_fills=true, which 
would re-evaluate on each tick/fill, potentially changing behavior.
    """)

    # Check another hypothesis: Does TV check the ENTRY bar's RSI (not signal bar)?
    print("=" * 120)
    print("HYPOTHESIS: TV checks RSI at ENTRY bar (not signal bar)")
    print("=" * 120)

    for desc, eng_entry, tv_entry in cases:
        eng_entry_ts = pd.Timestamp(eng_entry, tz="UTC")
        tv_entry_ts = pd.Timestamp(tv_entry, tz="UTC")

        eng_entry_idx = candles.index.get_loc(eng_entry_ts) if eng_entry_ts in candles.index else None
        tv_entry_idx = candles.index.get_loc(tv_entry_ts) if tv_entry_ts in candles.index else None

        if eng_entry_idx is not None:
            rsi_eng_entry = btc_rsi_eth.iloc[eng_entry_idx]
            range_eng_entry = (rsi_eng_entry >= short_rsi_more) and (rsi_eng_entry <= short_rsi_less)
        else:
            rsi_eng_entry = float("nan")
            range_eng_entry = None

        if tv_entry_idx is not None:
            rsi_tv_entry = btc_rsi_eth.iloc[tv_entry_idx]
            range_tv_entry = (rsi_tv_entry >= short_rsi_more) and (rsi_tv_entry <= short_rsi_less)
        else:
            rsi_tv_entry = float("nan")
            range_tv_entry = None

        print(f"\n  {desc}:")
        print(f"    Engine entry bar RSI: {rsi_eng_entry:.4f}  in range: {range_eng_entry}")
        print(f"    TV entry bar RSI:     {rsi_tv_entry:.4f}  in range: {range_tv_entry}")


asyncio.run(main())
