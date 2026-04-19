"""Match engine trades to TV trades by entry_time to find missing/extra/divergent trades."""

import asyncio
import json
import sqlite3
import sys
import warnings
from datetime import timedelta

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

TV_CSV = r"c:\Users\roman\Downloads\as4.csv"


def parse_tv_trades(csv_path):
    """Parse TV trades from as4.csv."""
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

    # Convert engine trades to comparable dicts
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
            }
        )

    # Match by entry_time within 30-min tolerance
    matched_tv = set()
    matched_eng = set()
    matches = []

    for e in engine_list:
        best_match = None
        best_diff = timedelta(hours=999)
        for t in tv_trades:
            if t["tv_num"] in matched_tv:
                continue
            if t["direction"] != e["direction"]:
                continue
            diff = abs(e["entry_time"] - t["entry_time"])
            if diff < best_diff and diff <= timedelta(hours=24):
                best_diff = diff
                best_match = t
        if best_match and best_diff == timedelta(0):
            # Exact match
            matches.append(("exact", e, best_match))
            matched_tv.add(best_match["tv_num"])
            matched_eng.add(e["eng_num"])

    # Second pass: near matches (within 24h, same direction)
    for e in engine_list:
        if e["eng_num"] in matched_eng:
            continue
        best_match = None
        best_diff = timedelta(hours=999)
        for t in tv_trades:
            if t["tv_num"] in matched_tv:
                continue
            if t["direction"] != e["direction"]:
                continue
            diff = abs(e["entry_time"] - t["entry_time"])
            if diff < best_diff and diff <= timedelta(hours=48):
                best_diff = diff
                best_match = t
        if best_match:
            matches.append(("near", e, best_match, best_diff))
            matched_tv.add(best_match["tv_num"])
            matched_eng.add(e["eng_num"])

    # Unmatched
    unmatched_eng = [e for e in engine_list if e["eng_num"] not in matched_eng]
    unmatched_tv = [t for t in tv_trades if t["tv_num"] not in matched_tv]

    # ============= REPORT =============
    exact = [m for m in matches if m[0] == "exact"]
    near = [m for m in matches if m[0] == "near"]

    print("\n=== MATCHING RESULTS ===")
    print(f"Exact entry match: {len(exact)}")
    print(f"Near match (within 48h): {len(near)}")
    print(f"Unmatched ENGINE trades: {len(unmatched_eng)}")
    print(f"Unmatched TV trades: {len(unmatched_tv)}")

    # Exact matches with exit differences
    exit_diff = []
    for m in exact:
        e, t = m[1], m[2]
        if e["exit_time"] != t["exit_time"]:
            exit_diff.append((e, t))
    print(f"\nExact entry match but DIFFERENT exit: {len(exit_diff)}")
    for e, t in exit_diff:
        print(
            f"  E#{e['eng_num']:3d} / TV#{t['tv_num']:3d}: {e['direction']:5s}  "
            f"entry={e['entry_time']}  exit: E={e['exit_time']} vs TV={t['exit_time']}"
        )

    # Near matches (shifted entry)
    if near:
        print("\nNEAR MATCHES (shifted entries):")
        for m in near:
            e, t, diff = m[1], m[2], m[3]
            print(
                f"  E#{e['eng_num']:3d} / TV#{t['tv_num']:3d}: {e['direction']:5s}  "
                f"E_entry={e['entry_time']}  TV_entry={t['entry_time']}  diff={diff}"
            )

    # Unmatched engine trades (engine has, TV doesn't)
    if unmatched_eng:
        print("\nENGINE-ONLY trades (engine has, TV doesn't):")
        for e in unmatched_eng:
            print(
                f"  E#{e['eng_num']:3d}: {e['direction']:5s} entry={e['entry_time']} exit={e['exit_time']} pnl={e['pnl']:.2f}"
            )

    # Unmatched TV trades (TV has, engine doesn't)
    if unmatched_tv:
        print("\nTV-ONLY trades (TV has, engine doesn't):")
        for t in unmatched_tv:
            print(
                f"  TV#{t['tv_num']:3d}: {t['direction']:5s} entry={t['entry_time']} exit={t['exit_time']} pnl={t['pnl']:.2f}"
            )

    # Full aligned comparison
    print(f"\n\n{'=' * 130}")
    print("FULL ALIGNED COMPARISON (matched by entry time)")
    print(f"{'=' * 130}")

    # Build alignment: combine all in chronological order
    all_events = []
    for m in matches:
        if m[0] == "exact":
            e, t = m[1], m[2]
            entry_match = "✅"
            exit_match = "✅" if e["exit_time"] == t["exit_time"] else "⏱️"
            all_events.append(
                (
                    e["entry_time"],
                    e["eng_num"],
                    t["tv_num"],
                    e["direction"],
                    entry_match,
                    exit_match,
                    e["exit_time"],
                    t["exit_time"],
                )
            )
        else:
            e, t = m[1], m[2]
            all_events.append(
                (
                    min(e["entry_time"], t["entry_time"]),
                    e["eng_num"],
                    t["tv_num"],
                    e["direction"],
                    "❌",
                    "?",
                    e["exit_time"],
                    t["exit_time"],
                )
            )

    for e in unmatched_eng:
        all_events.append((e["entry_time"], e["eng_num"], None, e["direction"], "🔴ENG", "", e["exit_time"], None))
    for t in unmatched_tv:
        all_events.append((t["entry_time"], None, t["tv_num"], t["direction"], "🔴TV", "", None, t["exit_time"]))

    all_events.sort(key=lambda x: x[0])

    print(f"{'Time':>20s}  {'E#':>4s} {'TV#':>4s} {'Dir':5s} Entry Exit  {'Engine Exit':>20s}  {'TV Exit':>20s}")
    print("-" * 130)
    for ev in all_events:
        t, en, tn, d, em, xm, ee, te = ev
        en_s = str(en) if en else "-"
        tn_s = str(tn) if tn else "-"
        ee_s = str(ee)[:19] if ee else "-"
        te_s = str(te)[:19] if te else "-"
        print(f"{str(t)[:19]:>20s}  {en_s:>4s} {tn_s:>4s} {d:5s} {em:5s} {xm:5s}  {ee_s:>20s}  {te_s:>20s}")


asyncio.run(main())
