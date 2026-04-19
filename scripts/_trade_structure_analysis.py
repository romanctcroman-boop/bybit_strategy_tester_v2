"""
Trade structure analysis: Engine vs TV (as4.csv).
Categorizes each of 150 trades by match quality.
"""

import asyncio
import json
import os
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
from backend.backtesting.interfaces import BacktestInput, ExitReason, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")


async def main():
    svc = BacktestService()

    # Load strategy
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?", (STRATEGY_ID,)
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
    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    btc_warmup = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=pd.Timestamp("2020-01-01", tz="UTC"), end_date=START_DATE
    )
    btc_main = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    # Signals
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

    # Run engine
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
    as4_path = r"c:\Users\roman\Downloads\as4.csv"
    if not os.path.exists(as4_path):
        print("[ERROR] as4.csv not found")
        return

    tv_df = pd.read_csv(as4_path, sep=";")
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
        if "long" in t.lower() or "длинн" in t.lower() or "RsiLE" in s:
            return "long"
        return "?"

    def parse_float(val):
        if pd.isna(val):
            return 0.0
        return float(str(val).replace(",", ".").replace("\xa0", "").strip())

    tv_entries["side"] = tv_entries.apply(tv_side, axis=1)
    tv_exits["pnl_tv"] = tv_exits["Чистая прибыль / убыток USDT"].apply(parse_float)
    tv_entries["entry_px"] = tv_entries["Цена USDT"].apply(parse_float)
    tv_exits["exit_px"] = tv_exits["Цена USDT"].apply(parse_float)

    # ══════════════════════════════════════════════════════════════════════════
    # STRUCTURAL ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    n = min(len(trades), len(tv_entries), len(tv_exits))

    # Categorize each trade
    cat_perfect = []  # dir + entry + exit + pnl all match
    cat_time_only = []  # dir matches but entry/exit time shifted (cascade from prior divergence)
    cat_dir_diff = []  # direction mismatch
    cat_root_div = []  # first divergence in a chain

    # First: identify which trades have matching direction AND entry time
    match_info = []
    for i in range(n):
        t = trades[i]
        tv_e = tv_entries.iloc[i]
        tv_x = tv_exits.iloc[i]

        e_dir = t.direction[:5]
        tv_dir = tv_e["side"][:5]
        e_et = str(t.entry_time)[:19].replace("T", " ")
        tv_et = str(tv_e["ts_utc"])[:19]
        e_xt = str(t.exit_time)[:19].replace("T", " ")
        tv_xt = str(tv_x["ts_utc"])[:19]
        e_pnl = t.pnl or 0
        tv_pnl = tv_x["pnl_tv"]
        e_ep = t.entry_price or 0
        tv_ep = tv_e["entry_px"]
        e_xp = t.exit_price or 0
        tv_xp = tv_x["exit_px"]

        dir_ok = e_dir == tv_dir
        et_ok = e_et == tv_et
        xt_ok = e_xt == tv_xt
        pnl_ok = abs(e_pnl - tv_pnl) < 0.5
        ep_ok = abs(e_ep - tv_ep) < 0.1
        xp_ok = abs(e_xp - tv_xp) < 0.1
        pnl_d = e_pnl - tv_pnl

        match_info.append(
            {
                "i": i + 1,
                "dir_ok": dir_ok,
                "et_ok": et_ok,
                "xt_ok": xt_ok,
                "pnl_ok": pnl_ok,
                "ep_ok": ep_ok,
                "xp_ok": xp_ok,
                "e_dir": e_dir,
                "tv_dir": tv_dir,
                "e_et": e_et,
                "tv_et": tv_et,
                "e_xt": e_xt,
                "tv_xt": tv_xt,
                "pnl_d": pnl_d,
                "e_ep": e_ep,
                "tv_ep": tv_ep,
                "e_xp": e_xp,
                "tv_xp": tv_xp,
                "e_pnl": e_pnl,
                "tv_pnl": tv_pnl,
                "exit_reason": str(t.exit_reason).split(".")[-1] if t.exit_reason else "",
            }
        )

    # ── Category assignment ──────────────────────────────────────────────────
    # A trade is "perfect" if dir+entry+exit+pnl all match
    # A "root divergence" is where the chain begins (first trade where entry differs)
    # "Cascade" trades are subsequent trades shifted due to earlier root

    in_cascade = False
    cascade_start = None
    for m in match_info:
        is_ok = m["dir_ok"] and m["et_ok"] and m["xt_ok"] and m["pnl_ok"]
        if is_ok:
            in_cascade = False
            cat_perfect.append(m["i"])
        elif not in_cascade:
            # First divergence — this is a ROOT
            cat_root_div.append(m["i"])
            in_cascade = True
            cascade_start = m["i"]
        else:
            # Continuation of cascade
            if not m["dir_ok"]:
                cat_dir_diff.append(m["i"])
            else:
                cat_time_only.append(m["i"])

    print("=" * 100)
    print("TRADE STRUCTURE ANALYSIS: Engine vs TradingView")
    print("=" * 100)
    print()
    print(f"Total trades compared: {n}")
    print()
    print(f"  ✅ PERFECT match (dir+entry+exit+pnl):  {len(cat_perfect):3d}  ({len(cat_perfect) / n * 100:.1f}%)")
    print(f"  🔴 ROOT divergences (signal timing):    {len(cat_root_div):3d}  ({len(cat_root_div) / n * 100:.1f}%)")
    print(f"  🟡 CASCADE - time shifted (same dir):   {len(cat_time_only):3d}  ({len(cat_time_only) / n * 100:.1f}%)")
    print(f"  🟠 CASCADE - direction flipped:          {len(cat_dir_diff):3d}  ({len(cat_dir_diff) / n * 100:.1f}%)")
    print()
    total_cascade = len(cat_time_only) + len(cat_dir_diff)
    print(f"  Total CASCADE (caused by roots):        {total_cascade:3d}  ({total_cascade / n * 100:.1f}%)")
    print()

    # ── Root divergences detail ──────────────────────────────────────────────
    print("ROOT DIVERGENCES (independent signal timing differences):")
    print(
        f"  {'#':>3}  {'dir_e':5} {'dir_tv':6}  {'entry_engine':>19}  {'entry_tv':>19}  {'Δ_bars':>6}  {'pnl_e':>9}  {'pnl_tv':>9}"
    )
    for r in cat_root_div:
        m = match_info[r - 1]
        # Calculate time difference in bars (30min)
        from datetime import datetime

        try:
            e_dt = datetime.strptime(m["e_et"], "%Y-%m-%d %H:%M:%S")
            tv_dt = datetime.strptime(m["tv_et"], "%Y-%m-%d %H:%M:%S")
            delta_bars = int((e_dt - tv_dt).total_seconds() / 1800)
        except:
            delta_bars = 0
        print(
            f"  {m['i']:3d}  {m['e_dir']:5} {m['tv_dir']:6}  {m['e_et']:>19}  {m['tv_et']:>19}  {delta_bars:>+6d}  {m['e_pnl']:>9.2f}  {m['tv_pnl']:>9.2f}"
        )

    # ── Cascade chains ───────────────────────────────────────────────────────
    print()
    print("CASCADE CHAINS (trades affected by each root divergence):")
    chains = []
    current_chain = None
    for m in match_info:
        is_ok = m["dir_ok"] and m["et_ok"] and m["xt_ok"] and m["pnl_ok"]
        if is_ok:
            if current_chain:
                chains.append(current_chain)
                current_chain = None
        elif m["i"] in cat_root_div:
            if current_chain:
                chains.append(current_chain)
            current_chain = {"root": m["i"], "trades": [m["i"]]}
        elif current_chain:
            current_chain["trades"].append(m["i"])

    if current_chain:
        chains.append(current_chain)

    for ch in chains:
        root_m = match_info[ch["root"] - 1]
        print(
            f"  Root #{ch['root']:3d} ({root_m['e_dir']:5} @ {root_m['e_et'][:10]}) → chain of {len(ch['trades']):3d} trades: [{ch['trades'][0]}..{ch['trades'][-1]}]"
        )

    # ── Perfect match ranges ─────────────────────────────────────────────────
    print()
    print("PERFECT MATCH RANGES:")
    if cat_perfect:
        ranges = []
        start = cat_perfect[0]
        prev = start
        for p in cat_perfect[1:]:
            if p == prev + 1:
                prev = p
            else:
                ranges.append((start, prev))
                start = p
                prev = p
        ranges.append((start, prev))
        for s, e in ranges:
            length = e - s + 1
            print(f"  Trades {s:3d}..{e:3d}  ({length:2d} trades)")

    # ── Per-field match statistics ───────────────────────────────────────────
    print()
    print("PER-FIELD MATCH STATISTICS (all 150 trades):")
    dir_match = sum(1 for m in match_info if m["dir_ok"])
    et_match = sum(1 for m in match_info if m["et_ok"])
    xt_match = sum(1 for m in match_info if m["xt_ok"])
    ep_match = sum(1 for m in match_info if m["ep_ok"])
    xp_match = sum(1 for m in match_info if m["xp_ok"])
    pnl_match = sum(1 for m in match_info if m["pnl_ok"])
    all_match = sum(1 for m in match_info if m["dir_ok"] and m["et_ok"] and m["xt_ok"] and m["pnl_ok"])

    print(f"  Direction match:     {dir_match:3d}/{n}  ({dir_match / n * 100:.1f}%)")
    print(f"  Entry time match:    {et_match:3d}/{n}  ({et_match / n * 100:.1f}%)")
    print(f"  Exit time match:     {xt_match:3d}/{n}  ({xt_match / n * 100:.1f}%)")
    print(f"  Entry price match:   {ep_match:3d}/{n}  ({ep_match / n * 100:.1f}%)")
    print(f"  Exit price match:    {xp_match:3d}/{n}  ({xp_match / n * 100:.1f}%)")
    print(f"  PnL match (<0.5$):   {pnl_match:3d}/{n}  ({pnl_match / n * 100:.1f}%)")
    print(f"  ALL PERFECT:         {all_match:3d}/{n}  ({all_match / n * 100:.1f}%)")

    # ── PnL accuracy for PERFECT trades only ─────────────────────────────────
    print()
    print("PNL ACCURACY ON PERFECT-MATCH TRADES:")
    perfect_pnl_diffs = [match_info[i - 1]["pnl_d"] for i in cat_perfect]
    if perfect_pnl_diffs:
        print(f"  Count: {len(perfect_pnl_diffs)}")
        print(f"  Total PnL diff:  {sum(perfect_pnl_diffs):+.4f} USDT")
        print(f"  Mean PnL diff:   {np.mean(perfect_pnl_diffs):+.6f} USDT")
        print(f"  Max  PnL diff:   {max(perfect_pnl_diffs):+.4f} USDT")
        print(f"  Min  PnL diff:   {min(perfect_pnl_diffs):+.4f} USDT")
        print(f"  Std  PnL diff:   {np.std(perfect_pnl_diffs):.6f} USDT")

    # ── Same-direction trades with time shift — how many bars off? ───────────
    print()
    print("TIME SHIFT ANALYSIS (same-direction trades with entry time mismatch):")
    from datetime import datetime

    shifts = []
    for m in match_info:
        if m["dir_ok"] and not m["et_ok"]:
            try:
                e_dt = datetime.strptime(m["e_et"], "%Y-%m-%d %H:%M:%S")
                tv_dt = datetime.strptime(m["tv_et"], "%Y-%m-%d %H:%M:%S")
                delta_bars = int((e_dt - tv_dt).total_seconds() / 1800)
                shifts.append((m["i"], delta_bars))
            except:
                pass
    if shifts:
        bars_list = [s[1] for s in shifts]
        print(f"  Count: {len(shifts)}")
        print(f"  Mean shift:  {np.mean(bars_list):+.1f} bars")
        print(f"  Median shift: {np.median(bars_list):+.1f} bars")
        print(f"  Min shift:   {min(bars_list):+d} bars ({min(bars_list) * 30:+d} min)")
        print(f"  Max shift:   {max(bars_list):+d} bars ({max(bars_list) * 30:+d} min)")

    # ── What if we EXCLUDE root divergences? ─────────────────────────────────
    print()
    print("=" * 100)
    print("IMPACT ANALYSIS: If root divergences were eliminated")
    print("=" * 100)
    print(f"  Current perfect matches:              {len(cat_perfect)}/{n}")
    print(f"  Root divergences to eliminate:         {len(cat_root_div)}")
    print(f"  Cascade trades that would re-align:   {total_cascade}")
    potential_perfect = len(cat_perfect) + total_cascade + len(cat_root_div)
    print(f"  Potential perfect matches:             {potential_perfect}/{n}  ({potential_perfect / n * 100:.1f}%)")
    print(f"  Remaining issues (non-cascade):        {n - potential_perfect}")

    print("\nDone.")


asyncio.run(main())
