"""
Deep investigation of 6 root divergences.

For roots #12,85,89,91,144 (engine fires EARLIER):
  1. Find the preceding trade's exit bar and RSI state there
  2. Check if RSI was ALREADY below 52 at the bar before engine's signal
  3. Trace RSI from prev exit to TV signal bar - find when crossunder re-arms

For root #9 (engine fires LATER):
  1. Check RSI at TV's signal bar more carefully
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
from backend.core.indicators.momentum import calculate_rsi

STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
CROSS_LEVEL = 52.0
ROOT_INDICES = [9, 12, 85, 89, 91, 144]  # 1-based


async def main():
    svc = BacktestService()

    # Load strategy
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

    # Fetch data
    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), START_DATE)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    # BTC RSI
    btc_rsi_arr = calculate_rsi(btc["close"].values, period=14)
    btc_rsi = pd.Series(btc_rsi_arr, index=btc.index)

    # Run engine
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
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

    result = FallbackEngineV4().run(
        BacktestInput(
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
    )
    trades = result.trades

    # Load TV trades
    tv_df = pd.read_csv(r"c:\Users\roman\Downloads\as4.csv", sep=";")
    tv_entries = (
        tv_df[tv_df["Тип"].str.contains("Entry|Вход", case=False, na=False)]
        .sort_values("№ Сделки")
        .reset_index(drop=True)
    )
    tv_exits = (
        tv_df[tv_df["Тип"].str.contains("Exit|Выход", case=False, na=False)]
        .sort_values("№ Сделки")
        .reset_index(drop=True)
    )
    tv_entries["ts_utc"] = pd.to_datetime(tv_entries["Дата и время"]) - pd.Timedelta(hours=3)
    tv_exits["ts_utc"] = pd.to_datetime(tv_exits["Дата и время"]) - pd.Timedelta(hours=3)

    def tv_side(row):
        s, t = str(row.get("Сигнал", "")), str(row.get("Тип", ""))
        if "short" in t.lower() or "коротк" in t.lower() or "RsiSE" in s:
            return "short"
        return "long"

    tv_entries["side"] = tv_entries.apply(tv_side, axis=1)

    print("=" * 140)
    print("INVESTIGATION OF 6 ROOT DIVERGENCES — RSI TRACE FROM PREV EXIT TO SIGNALS")
    print("=" * 140)

    for root_idx in ROOT_INDICES:
        idx = root_idx - 1

        eng_trade = trades[idx]
        tv_entry = tv_entries.iloc[idx]
        eng_entry_time = pd.Timestamp(str(eng_trade.entry_time)[:19])
        tv_entry_time = pd.Timestamp(str(tv_entry["ts_utc"])[:19])
        eng_signal_bar = eng_entry_time - pd.Timedelta(minutes=30)
        tv_signal_bar = tv_entry_time - pd.Timedelta(minutes=30)

        # Previous trade
        prev_trade = trades[idx - 1] if idx > 0 else None
        prev_exit_time = pd.Timestamp(str(prev_trade.exit_time)[:19]) if prev_trade else None
        tv_prev_exit = tv_exits.iloc[idx - 1] if idx > 0 else None
        tv_prev_exit_time = pd.Timestamp(str(tv_prev_exit["ts_utc"])[:19]) if tv_prev_exit is not None else None

        print(f"\n{'=' * 140}")
        print(f"ROOT #{root_idx}  |  Engine→{eng_trade.direction}  TV→{tv_entries.iloc[idx]['side']}")
        print(f"{'=' * 140}")
        print(f"  Prev trade #{root_idx - 1}:")
        if prev_trade:
            print(f"    Engine exit: {prev_exit_time}  reason={prev_trade.exit_reason}  dir={prev_trade.direction}")
            print(f"    TV exit:     {tv_prev_exit_time}")
            print(f"    Exits match: {str(prev_exit_time)[:16] == str(tv_prev_exit_time)[:16]}")
        print(f"  This trade #{root_idx}:")
        print(f"    Engine signal bar: {eng_signal_bar}  entry: {eng_entry_time}")
        print(f"    TV signal bar:     {tv_signal_bar}  entry: {tv_entry_time}")

        # CRITICAL: Check if the previous trade's exit bar is the SAME as
        # (or after) the engine's signal bar. If TP fills on the signal bar
        # but before entry_on_next_bar_open, that could affect the cross.
        if prev_exit_time and eng_signal_bar:
            bars_between = None
            if prev_exit_time <= eng_signal_bar:
                # Count bars between prev exit and engine signal
                mask = (btc_rsi.index >= prev_exit_time) & (btc_rsi.index <= eng_signal_bar)
                bars_between = mask.sum()
            print(f"  Bars from prev exit to engine signal: {bars_between}")

        # Trace RSI from prev exit to TV signal
        trace_start = (
            (prev_exit_time - pd.Timedelta(hours=1)) if prev_exit_time else (eng_signal_bar - pd.Timedelta(hours=3))
        )
        trace_end = max(eng_signal_bar, tv_signal_bar) + pd.Timedelta(hours=1)
        rsi_window = btc_rsi[(btc_rsi.index >= trace_start) & (btc_rsi.index <= trace_end)]

        if len(rsi_window) == 0:
            print("  [NO DATA]")
            continue

        print(f"\n  {'Bar':>22s}  {'RSI':>9s}  {'RSI_prev':>9s}  {'cross↓52':>9s}  {'RSI≥52':>6s}  {'Notes'}")
        print(f"  {'-' * 22}  {'-' * 9}  {'-' * 9}  {'-' * 9}  {'-' * 6}  {'-' * 50}")

        for j, (ts, rsi_val) in enumerate(rsi_window.items()):
            rsi_prev_val = rsi_window.iloc[j - 1] if j > 0 else np.nan
            cross_dn = not np.isnan(rsi_prev_val) and rsi_prev_val >= CROSS_LEVEL and rsi_val < CROSS_LEVEL
            above = rsi_val >= CROSS_LEVEL

            notes = []
            ts_str = str(ts)[:19]
            if prev_exit_time and ts_str == str(prev_exit_time)[:19]:
                notes.append("◀ PREV EXIT (eng)")
            if tv_prev_exit_time and ts_str == str(tv_prev_exit_time)[:19]:
                notes.append("◀ PREV EXIT (tv)")
            if ts_str == str(eng_signal_bar)[:19]:
                notes.append("🔴 ENGINE SIGNAL")
            if ts_str == str(tv_signal_bar)[:19]:
                notes.append("🟢 TV SIGNAL")
            if cross_dn:
                notes.append("** CROSS↓52 **")

            print(
                f"  {ts_str:>22s}  {rsi_val:9.4f}  {rsi_prev_val:9.4f}  {'YES' if cross_dn else '':>9s}  {'YES' if above else '':>6s}  {'  '.join(notes)}"
            )

        # Summary: find first bar where RSI >= 52 after prev exit,
        # then first crossunder after that
        if prev_exit_time:
            after_exit = btc_rsi[btc_rsi.index >= prev_exit_time]
            first_above = None
            first_cross = None
            for j in range(1, min(200, len(after_exit))):
                rval = after_exit.iloc[j]
                rprev = after_exit.iloc[j - 1]
                if rval >= CROSS_LEVEL and first_above is None:
                    first_above = (after_exit.index[j], rval)
                if first_above is not None and rprev >= CROSS_LEVEL and rval < CROSS_LEVEL:
                    first_cross = (after_exit.index[j], rval, rprev)
                    break

            print(f"\n  SUMMARY:")
            if first_above:
                print(f"    First RSI≥52 after prev exit: {first_above[0]}  RSI={first_above[1]:.4f}")
            if first_cross:
                ts_fc = str(first_cross[0])[:19]
                m_eng = ts_fc == str(eng_signal_bar)[:19]
                m_tv = ts_fc == str(tv_signal_bar)[:19]
                print(
                    f"    First cross↓52 after rearm:   {first_cross[0]}  RSI={first_cross[2]:.4f}→{first_cross[1]:.4f}"
                )
                print(f"    Matches engine signal: {m_eng}")
                print(f"    Matches TV signal:     {m_tv}")
            else:
                print(f"    First cross↓52 after rearm: NOT FOUND")

    print("\n\nDone.")


asyncio.run(main())
