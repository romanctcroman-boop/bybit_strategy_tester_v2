"""
Cross-reference the 22 extra engine trades with TV missing trades.
For each extra engine trade, find the CORRESPONDING TV trade (nearby missing TV trade).
This reveals the EXACT divergence pattern.
"""

import asyncio
import csv
import json
import sqlite3
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import numpy as np
import pandas as pd
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.core.indicators import calculate_rsi

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
TV_Z4_PATH = r"c:\Users\roman\Downloads\z4.csv"
WARMUP_BARS = 500
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
        **({"main_strategy": ms} if ms else {}),
    }


def load_tv_trades():
    trades = []
    with open(TV_Z4_PATH, encoding="cp1251") as f:
        reader = csv.DictReader(f, delimiter=";")
        all_rows = list(reader)
    keys = list(all_rows[0].keys())
    for i in range(0, len(all_rows) - 1, 2):
        exit_row = all_rows[i]
        entry_row = all_rows[i + 1]
        try:
            ep = float(entry_row[keys[4]].replace(",", ".").strip())
            xp = float(exit_row[keys[4]].replace(",", ".").strip())
            side_raw = entry_row[keys[1]].strip().lower()
            side = "long" if "long" in side_raw or "покупка" in side_raw else "short"
            entry_ts = pd.to_datetime(entry_row[keys[2]].strip()) - pd.Timedelta(hours=3)
            exit_ts = pd.to_datetime(exit_row[keys[2]].strip()) - pd.Timedelta(hours=3)
            trades.append({"ep": ep, "xp": xp, "side": side, "entry_ts": entry_ts, "exit_ts": exit_ts})
        except (ValueError, KeyError, IndexError):
            pass
    return trades


async def main():
    graph = load_graph()
    svc = BacktestService()

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    if candles.index.tz is not None:
        candles.index = candles.index.tz_localize(None)

    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    if btc_main.index.tz is None:
        btc_main.index = btc_main.index.tz_localize("UTC")

    warmup_start_ts = int(btc_start.timestamp() * 1000)
    warmup_end_ts = int(START_DATE.timestamp() * 1000)
    raw_warmup = await svc.adapter.get_historical_klines(
        "BTCUSDT", "30", warmup_start_ts, warmup_end_ts, market_type="linear"
    )
    df_w = pd.DataFrame(raw_warmup)
    for old, new in {
        "startTime": "timestamp",
        "open_time": "timestamp",
        "openPrice": "open",
        "highPrice": "high",
        "lowPrice": "low",
        "closePrice": "close",
    }.items():
        if old in df_w.columns and new not in df_w.columns:
            df_w = df_w.rename(columns={old: new})
    for col in ["open", "high", "low", "close"]:
        if col in df_w.columns:
            df_w[col] = pd.to_numeric(df_w[col], errors="coerce")
    if df_w["timestamp"].dtype in ["int64", "float64"]:
        df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms", utc=True)
    else:
        df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], utc=True)
    df_w = df_w.set_index("timestamp").sort_index()

    btc_candles = pd.concat([df_w, btc_main]).sort_index()
    btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]

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
    eng_trades = result.trades

    # Build BTC RSI series aligned to ETH candles
    btc_close = btc_candles["close"].copy()
    if btc_close.index.tz is not None:
        btc_close.index = btc_close.index.tz_localize(None)
    rsi_arr = calculate_rsi(btc_close.values, period=14)
    rsi_full = pd.Series(rsi_arr, index=btc_close.index)
    rsi_aligned = rsi_full.reindex(candles.index, method="ffill").fillna(method="bfill")
    candles_idx = list(candles.index)

    # Load TV trades
    tv_trades = load_tv_trades()
    print(f"Engine: {len(eng_trades)} trades, TV: {len(tv_trades)} trades")

    # Match engine to TV
    TOLERANCE = pd.Timedelta(minutes=30)
    tv_unmatched = list(range(len(tv_trades)))
    eng_unmatched = []
    eng_matched_pairs = []

    for et in eng_trades:
        et_ts = pd.Timestamp(et.entry_time)
        if et_ts.tz is not None:
            et_ts = et_ts.tz_localize(None)
        best_idx = None
        best_diff = TOLERANCE + pd.Timedelta(minutes=1)
        for i in tv_unmatched:
            tv = tv_trades[i]
            if tv["side"] != et.direction:
                continue
            diff = abs(et_ts - tv["entry_ts"])
            if diff <= TOLERANCE and diff < best_diff:
                best_diff = diff
                best_idx = i
        if best_idx is not None:
            tv_unmatched.remove(best_idx)
            eng_matched_pairs.append((et, tv_trades[best_idx]))
        else:
            eng_unmatched.append(et)

    tv_unmatched_trades = [tv_trades[i] for i in tv_unmatched]

    print(f"Extra engine: {len(eng_unmatched)}, Missing TV: {len(tv_unmatched_trades)}")
    print()

    # For each extra engine trade, find the "replacement" TV trade
    # (the TV trade that fired instead of the engine's extra trade)
    print("=" * 120)
    print("DETAILED ANALYSIS: Extra engine trades vs their TV 'replacement'")
    print("For each extra engine trade, we show:")
    print("  - Engine signal bar T, RSI[T], RSI[T+1], RSI[T+2]")
    print("  - The closest MISSING TV trade (which fired LATER instead)")
    print("  - RSI[TV_T], RSI[TV_T+1]")
    print("=" * 120)

    def get_rsi_context(ts, n_bars=4):
        """Get RSI values for bars T-1..T+n around a timestamp."""
        ts_naive = pd.Timestamp(ts)
        if ts_naive.tz is not None:
            ts_naive = ts_naive.tz_localize(None)
        try:
            pos = candles_idx.index(ts_naive)
        except ValueError:
            diffs = [abs((t - ts_naive).total_seconds()) for t in candles_idx]
            pos = int(np.argmin(diffs))
        result_vals = {}
        for offset in range(-1, n_bars + 1):
            idx_i = pos + offset
            if 0 <= idx_i < len(candles_idx):
                t = candles_idx[idx_i]
                result_vals[offset] = (t, rsi_aligned.get(t, float("nan")))
        return result_vals, pos

    for i, eng_extra in enumerate(eng_unmatched):
        eng_ts = pd.Timestamp(eng_extra.entry_time)
        if eng_ts.tz is not None:
            eng_ts = eng_ts.tz_localize(None)

        # Find nearest TV missing trade
        tv_candidates = [
            tv
            for tv in tv_unmatched_trades
            if tv["side"] == eng_extra.direction
            and pd.Timestamp(tv["entry_ts"]) > eng_ts
            and pd.Timestamp(tv["entry_ts"]) < eng_ts + pd.Timedelta(hours=48)
        ]
        tv_match = tv_candidates[0] if tv_candidates else None

        eng_rsi, eng_pos = get_rsi_context(eng_ts)
        rsi_T = eng_rsi.get(0, (None, float("nan")))[1]
        rsi_T1 = eng_rsi.get(1, (None, float("nan")))[1]
        rsi_T2 = eng_rsi.get(2, (None, float("nan")))[1]
        rsi_Tneg1 = eng_rsi.get(-1, (None, float("nan")))[1]

        print(
            f"\n--- Extra #{i + 1}: {eng_extra.direction:5s} eng={eng_ts} ep={eng_extra.entry_price:.2f} exit={str(pd.Timestamp(eng_extra.exit_time))[:16]} ({eng_extra.exit_reason})"
        )
        print(f"    RSI[T-1]={rsi_Tneg1:.4f}  RSI[T]={rsi_T:.4f}  RSI[T+1]={rsi_T1:.4f}  RSI[T+2]={rsi_T2:.4f}")

        if tv_match:
            tv_ts = pd.Timestamp(tv_match["entry_ts"])
            # TV signal bar = tv_ts - 30 min (since TV entry = signal_bar + 30min)
            tv_signal_ts = tv_ts - pd.Timedelta(minutes=30)
            tv_rsi, tv_pos = get_rsi_context(tv_signal_ts)
            tv_rsi_T = tv_rsi.get(0, (None, float("nan")))[1]
            tv_rsi_T1 = tv_rsi.get(1, (None, float("nan")))[1]
            tv_rsi_T2 = tv_rsi.get(2, (None, float("nan")))[1]
            tv_rsi_Tneg1 = tv_rsi.get(-1, (None, float("nan")))[1]

            print(
                f"    TV replacement: {tv_match['side']:5s} tv_entry={tv_ts} ep={tv_match['ep']:.2f} (signal bar={tv_signal_ts})"
            )
            print(
                f"    TV RSI[T-1]={tv_rsi_Tneg1:.4f}  RSI[T]={tv_rsi_T:.4f}  RSI[T+1]={tv_rsi_T1:.4f}  RSI[T+2]={tv_rsi_T2:.4f}"
            )

            gap_bars = tv_pos - eng_pos
            print(f"    Gap: {gap_bars} bars ({(tv_signal_ts - eng_ts).total_seconds() / 1800:.1f} x 30min)")

            # Show all RSI values between eng and TV signal
            print("    RSI between eng_T and tv_T:")
            for offset in range(1, min(gap_bars, 20)):
                idx_i = eng_pos + offset
                if 0 <= idx_i < len(candles_idx):
                    t = candles_idx[idx_i]
                    r = rsi_aligned.get(t, float("nan"))
                    flag = ""
                    if offset > 0:
                        r_prev = rsi_aligned.get(candles_idx[idx_i - 1], float("nan"))
                        if r_prev >= CROSS_SHORT_LEVEL and r < CROSS_SHORT_LEVEL:
                            flag = " <CROSSUNDER"
                    print(f"      +{offset:2d} {t}  RSI={r:.4f}{flag}")
        else:
            print("    TV replacement: (none found in +48h window)")


asyncio.run(main())
