"""Match engine trades (151) to TV trades (151) by entry_time.
Uses separate warmup+main BTC data loading (same as _check_entry_timing.py) which gives 151 trades.
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
        pnl = float(str(exit_row["Чистая прибыль / убыток USDT"]).replace(",", ".").strip())
        trades.append(
            {
                "tv_num": i // 2 + 1,
                "direction": direction,
                "entry_time": entry_utc,
                "exit_time": exit_utc,
                "pnl": pnl,
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

    # Separate warmup+main (gives 151 trades — matches TV count)
    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), START_DATE)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    print(f"ETH: {len(candles)} bars  BTC: {len(btc)} bars")

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

    # Convert engine trades
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
                "pnl": t.pnl,
                "entry_price": t.entry_price,
            }
        )

    # Match by entry_time
    matched_tv = set()
    matched_eng = set()
    exact_matches = []
    near_matches = []
    tol = pd.Timedelta(minutes=30)

    for e in engine_list:
        for t in tv_trades:
            if t["tv_num"] in matched_tv:
                continue
            diff = abs(e["entry_time"] - t["entry_time"])
            if diff <= tol and e["direction"] == t["direction"]:
                exact_matches.append((e, t))
                matched_tv.add(t["tv_num"])
                matched_eng.add(e["eng_num"])
                break

    # Near matches (within 48h)
    for e in engine_list:
        if e["eng_num"] in matched_eng:
            continue
        for t in tv_trades:
            if t["tv_num"] in matched_tv:
                continue
            diff = abs(e["entry_time"] - t["entry_time"])
            if diff <= pd.Timedelta(hours=48) and e["direction"] == t["direction"]:
                near_matches.append((e, t))
                matched_tv.add(t["tv_num"])
                matched_eng.add(e["eng_num"])
                break

    eng_only = [e for e in engine_list if e["eng_num"] not in matched_eng]
    tv_only = [t for t in tv_trades if t["tv_num"] not in matched_tv]

    # Exit mismatches
    exit_mismatches = []
    for e, t in exact_matches:
        e_exit = e["exit_time"]
        t_exit = t["exit_time"]
        if abs(e_exit - t_exit) > pd.Timedelta(minutes=30):
            exit_mismatches.append((e, t))

    print(f"\nExact entry match: {len(exact_matches)}")
    print(f"Near match (within 48h): {len(near_matches)}")
    print(f"Unmatched ENGINE trades: {len(eng_only)}")
    print(f"Unmatched TV trades: {len(tv_only)}")
    print(f"Exact entry match but DIFFERENT exit: {len(exit_mismatches)}")

    if near_matches:
        print("\nNEAR MATCHES:")
        for e, t in near_matches:
            diff = abs(e["entry_time"] - t["entry_time"])
            print(
                f"  E#{e['eng_num']:3d}/TV#{t['tv_num']:3d}: {e['direction']:5s}  "
                f"E_entry={e['entry_time']}  TV_entry={t['entry_time']}  diff={diff}"
            )

    if eng_only:
        print("\nENGINE-ONLY:")
        for e in eng_only:
            print(
                f"  E#{e['eng_num']:3d}: {e['direction']:5s}  entry={e['entry_time']}  exit={e['exit_time']}  pnl={e['pnl']:.2f}"
            )

    if tv_only:
        print("\nTV-ONLY:")
        for t in tv_only:
            print(
                f"  TV#{t['tv_num']:3d}: {t['direction']:5s}  entry={t['entry_time']}  exit={t['exit_time']}  pnl={t['pnl']:.2f}"
            )

    if exit_mismatches:
        print("\nEXIT MISMATCHES:")
        for e, t in exit_mismatches:
            print(
                f"  E#{e['eng_num']:3d}/TV#{t['tv_num']:3d}: {e['direction']:5s}  "
                f"entry={e['entry_time']}  exit: E={e['exit_time']} vs TV={t['exit_time']}"
            )

    # PnL comparison for exact matches
    pnl_diffs = []
    for e, t in exact_matches:
        pnl_diffs.append(abs(e["pnl"] - t["pnl"]))

    if pnl_diffs:
        perfect = sum(1 for d in pnl_diffs if d < 0.01)
        close = sum(1 for d in pnl_diffs if d < 0.1)
        print(f"\nPnL comparison for {len(exact_matches)} exact matches:")
        print(f"  Perfect (<0.01): {perfect}/{len(exact_matches)}")
        print(f"  Close (<0.1): {close}/{len(exact_matches)}")
        print(f"  Max PnL diff: {max(pnl_diffs):.4f}")
        print(f"  Mean PnL diff: {sum(pnl_diffs) / len(pnl_diffs):.4f}")


asyncio.run(main())
