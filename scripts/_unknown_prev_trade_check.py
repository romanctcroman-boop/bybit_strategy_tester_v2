"""
For each of the 5 UNKNOWN cases, check:
1. What is the previous trade in ENGINE? What is the previous trade in TV?
2. Do they match? (same direction, same entry_time, same exit_time)
3. If the previous trade differs — that explains why the SE window is different.

KEY HYPOTHESIS: Maybe the previous trade (the one exiting before the unknown entry)
is itself a "near match" — i.e. the engine entered/exited at a slightly different bar
than TV, which shifted the window for the next entry.
"""

import asyncio
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
os.chdir(r"d:\bybit_strategy_tester_v2")

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

TV_CSV = r"c:\Users\roman\Downloads\as4.csv"
STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")


def parse_tv_trades(csv_path):
    """Parse TV CSV into list of trade dicts."""
    tv_raw = pd.read_csv(csv_path, sep=";")
    trades = []
    for i in range(0, len(tv_raw), 2):
        exit_row = tv_raw.iloc[i]
        entry_row = tv_raw.iloc[i + 1]
        entry_type = str(entry_row["Тип"]).strip()
        direction = "short" if "short" in entry_type.lower() else "long"
        entry_msk = pd.Timestamp(str(entry_row["Дата и время"]).strip())
        exit_msk = pd.Timestamp(str(exit_row["Дата и время"]).strip())
        entry_utc = entry_msk - pd.Timedelta(hours=3)
        exit_utc = exit_msk - pd.Timedelta(hours=3)

        entry_price = float(str(entry_row["Цена USDT"]).replace("\xa0", "").replace(",", ".").replace(" ", ""))
        exit_price = float(str(exit_row["Цена USDT"]).replace("\xa0", "").replace(",", ".").replace(" ", ""))

        trades.append(
            {
                "tv_num": i // 2 + 1,
                "direction": direction,
                "entry_time": entry_utc,
                "exit_time": exit_utc,
                "entry_price": entry_price,
                "exit_price": exit_price,
            }
        )
    return trades


async def main():
    svc = BacktestService()
    conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
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

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), START_DATE)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)
    le = np.asarray(signals.entries.values, dtype=bool)
    se = np.asarray(signals.short_entries.values, dtype=bool)
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

    engine_trades = result.trades
    tv_trades = parse_tv_trades(TV_CSV)

    print(f"Engine: {len(engine_trades)} trades, TV: {len(tv_trades)} trades")

    # FIRST: Build the full match mapping (same as _match_trades_v2.py)
    engine_list = []
    for idx, t in enumerate(engine_trades):
        entry_str = str(t.entry_time)[:19].replace("T", " ")
        exit_str = str(t.exit_time)[:19].replace("T", " ")
        engine_list.append(
            {
                "eng_num": idx + 1,
                "direction": t.direction,
                "entry_time": pd.Timestamp(entry_str),
                "exit_time": pd.Timestamp(exit_str),
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "exit_reason": getattr(t, "exit_reason", "unknown"),
            }
        )

    # Build eng_num → tv_num mapping
    matched_tv = set()
    eng_to_tv = {}
    tv_to_eng = {}
    tol = pd.Timedelta(minutes=30)

    # Exact matches first
    for e in engine_list:
        for t in tv_trades:
            if t["tv_num"] in matched_tv:
                continue
            diff = abs(e["entry_time"] - t["entry_time"])
            if diff <= tol and e["direction"] == t["direction"]:
                eng_to_tv[e["eng_num"]] = t["tv_num"]
                tv_to_eng[t["tv_num"]] = e["eng_num"]
                matched_tv.add(t["tv_num"])
                break

    # Near matches
    matched_eng_set = set(eng_to_tv.keys())
    for e in engine_list:
        if e["eng_num"] in matched_eng_set:
            continue
        for t in tv_trades:
            if t["tv_num"] in matched_tv:
                continue
            diff = abs(e["entry_time"] - t["entry_time"])
            if diff <= pd.Timedelta(hours=48) and e["direction"] == t["direction"]:
                eng_to_tv[e["eng_num"]] = t["tv_num"]
                tv_to_eng[t["tv_num"]] = e["eng_num"]
                matched_tv.add(t["tv_num"])
                matched_eng_set.add(e["eng_num"])
                break

    # The 5 UNKNOWN cases (engine trade numbers)
    unknown_eng_nums = [23, 85, 89, 91, 120]

    print("\n" + "=" * 140)
    print("UNKNOWN CASES: PREVIOUS TRADE COMPARISON (ENGINE vs TV)")
    print("=" * 140)

    for eng_num in unknown_eng_nums:
        tv_num = eng_to_tv.get(eng_num)
        if tv_num is None:
            print(f"\nE#{eng_num}: No TV match found!")
            continue

        # Current trade
        eng_curr = engine_list[eng_num - 1]
        tv_curr = next(t for t in tv_trades if t["tv_num"] == tv_num)

        # Previous trade in engine sequence
        eng_prev = engine_list[eng_num - 2]
        eng_prev_tv_num = eng_to_tv.get(eng_num - 1)

        # Previous trade in TV sequence
        tv_prev = next(t for t in tv_trades if t["tv_num"] == tv_num - 1)
        tv_prev_eng_num = tv_to_eng.get(tv_num - 1)

        print(f"\n{'=' * 140}")
        print(f"UNKNOWN: E#{eng_num} ↔ TV#{tv_num}")
        print(f"  Engine entry: {eng_curr['entry_time']}  TV entry: {tv_curr['entry_time']}")
        print(f"  Entry diff: {abs(eng_curr['entry_time'] - tv_curr['entry_time'])}")

        print(f"\n  PREVIOUS TRADE (in engine sequence: E#{eng_num - 1}):")
        print(f"    Dir: {eng_prev['direction']}  Entry: {eng_prev['entry_time']}  Exit: {eng_prev['exit_time']}")
        print(f"    Exit reason: {eng_prev['exit_reason']}")
        print(f"    Mapped to TV#{eng_prev_tv_num}")

        print(f"\n  PREVIOUS TRADE (in TV sequence: TV#{tv_num - 1}):")
        print(f"    Dir: {tv_prev['direction']}  Entry: {tv_prev['entry_time']}  Exit: {tv_prev['exit_time']}")
        print(f"    Mapped to E#{tv_prev_eng_num}")

        # Check if the previous trades match
        if eng_prev_tv_num == tv_num - 1:
            # Same previous trade — check exit timing
            eng_exit = eng_prev["exit_time"]
            tv_exit = tv_prev["exit_time"]
            exit_diff = abs(eng_exit - tv_exit)
            if exit_diff <= pd.Timedelta(minutes=30):
                print("\n  ✅ Previous trades MATCH (same trade, same exit timing)")
                print(f"     Exit diff: {exit_diff}")
            else:
                print("\n  ⚠️ Previous trades SAME but EXIT TIMING DIFFERS!")
                print(f"     Engine prev exit: {eng_exit}")
                print(f"     TV prev exit:     {tv_exit}")
                print(f"     Exit diff: {exit_diff}")
        else:
            print("\n  ❌ Previous trades DIFFER!")
            print(f"     Engine's prev (E#{eng_num - 1}) maps to TV#{eng_prev_tv_num}")
            print(f"     TV's prev (TV#{tv_num - 1}) maps to E#{tv_prev_eng_num}")
            # This means the trade sequences are shifted — check what happened
            if tv_prev_eng_num and tv_prev_eng_num != eng_num - 1:
                shift_eng = engine_list[tv_prev_eng_num - 1]
                print(f"\n     TV's prev trade (TV#{tv_num - 1}) is actually engine's E#{tv_prev_eng_num}")
                print(f"       entry: {shift_eng['entry_time']}  exit: {shift_eng['exit_time']}")


asyncio.run(main())
