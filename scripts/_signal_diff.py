"""
Signal diff analysis: compare engine signal bars (with warmup, no 5m) vs TV CSV.
Goal: find exactly which signal bars engine has that TV doesn't and vice versa.
This helps identify why engine has 150 trades while TV has 147.
"""

import asyncio
import json
import sqlite3
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

import numpy as np
import pandas as pd

from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.core.indicators import calculate_rsi

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
TV_CSV = r"c:\Users\roman\Downloads\z4.csv"
WARMUP_BARS = 2000  # MORE warmup to improve RSI convergence


async def main():
    # ── Load strategy graph ────────────────────────────────────────────────
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

    # ── Fetch candles ──────────────────────────────────────────────────────
    svc = BacktestService()
    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    print(f"ETH 30m: {len(candles)} bars  [{candles.index[0]} .. {candles.index[-1]}]")

    # ── Fetch BTC with full warmup from 2020 ──────────────────────────────
    btc_start = pd.Timestamp("2020-01-01", tz="UTC")
    btc_main = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    warmup_ok = False
    try:
        raw = await svc.adapter.get_historical_klines(
            symbol="BTCUSDT",
            interval="30",
            start_time=int(btc_start.timestamp() * 1000),
            end_time=int(START_DATE.timestamp() * 1000),
            market_type="linear",
        )
        df_w = pd.DataFrame(raw)
        col_map = {
            "startTime": "timestamp",
            "open_time": "timestamp",
            "openPrice": "open",
            "highPrice": "high",
            "lowPrice": "low",
            "closePrice": "close",
        }
        for o, n in col_map.items():
            if o in df_w.columns and n not in df_w.columns:
                df_w = df_w.rename(columns={o: n})
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df_w.columns:
                df_w[col] = pd.to_numeric(df_w[col], errors="coerce")
        if "timestamp" in df_w.columns:
            if df_w["timestamp"].dtype in ["int64", "float64"]:
                df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms", utc=True)
            else:
                df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], utc=True)
            df_w = df_w.set_index("timestamp").sort_index()
        if btc_main.index.tz is None:
            btc_main.index = btc_main.index.tz_localize("UTC")
        if df_w.index.tz is None:
            df_w.index = df_w.index.tz_localize("UTC")
        btc_candles = pd.concat([df_w, btc_main]).sort_index()
        btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]
        warmup_ok = True
        print(f"BTC 30m: {len(btc_candles)} bars (with {WARMUP_BARS}-bar warmup)")
        print(f"  Warmup range: [{btc_candles.index[0]} .. {START_DATE})")
    except Exception as e:
        print(f"BTC warmup failed: {e}")
        btc_candles = btc_main

    if not warmup_ok:
        print("WARNING: Warmup failed - RSI values will be inaccurate!")

    # ── Generate signals (NO 5m intra-bar) ────────────────────────────────
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_candles, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)
    le = np.asarray(signals.entries.values, dtype=bool)
    se = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(le), dtype=bool)
    )
    print(f"Signals: {le.sum()} long_entries  {se.sum()} short_entries")

    # ── Engine signal bars (as timestamps in UTC) ─────────────────────────
    eth_idx = candles.index
    eng_long_bars = set(eth_idx[le])
    eng_short_bars = set(eth_idx[se])

    # ── Load TV CSV and extract signal bars ───────────────────────────────
    # TV entry time = next bar open after signal. Signal bar = entry_time - 30min
    tv = pd.read_csv(TV_CSV, sep=";")
    tv_ent = tv[tv["Тип"].str.startswith("Entry")].copy()
    tv_ent["ts_utc"] = pd.to_datetime(tv_ent["Дата и время"]) - pd.Timedelta(hours=3)
    tv_ent["side"] = tv_ent["Сигнал"].map({"RsiSE": "short", "RsiLE": "long"})
    # Signal fired on bar BEFORE the entry (entry_on_next_bar_open)
    tv_ent["signal_bar"] = tv_ent["ts_utc"] - pd.Timedelta(minutes=30)

    # Parse entry price
    price_col_raw = "Цена USDT"
    if price_col_raw in tv_ent.columns:
        tv_ent["ep"] = (
            tv_ent[price_col_raw]
            .astype(str)
            .str.replace(",", ".")
            .apply(lambda x: float(x.strip()) if x.strip() else 0.0)
        )
    else:
        tv_ent["ep"] = 0.0

    tv_longs = tv_ent[tv_ent["side"] == "long"]
    tv_shorts = tv_ent[tv_ent["side"] == "short"]
    tv_long_bars = set(tv_longs["signal_bar"])
    tv_short_bars = set(tv_shorts["signal_bar"])

    print(f"\nTV signals: {len(tv_long_bars)} long  {len(tv_short_bars)} short")
    print(f"Eng signals: {len(eng_long_bars)} long  {len(eng_short_bars)} short")

    # ── Pre-compute RSI once ───────────────────────────────────────────────
    btc_close = btc_candles["close"].copy()
    if btc_close.index.tz is None:
        btc_close.index = btc_close.index.tz_localize("UTC")
    rsi_arr = calculate_rsi(btc_close.values, period=14)
    btc_rsi = pd.Series(rsi_arr, index=btc_close.index)

    def get_rsi_at(ts):
        """Get (rsi_now, rsi_prev) at a UTC-aware timestamp."""
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        if ts not in btc_rsi.index:
            # Find nearest
            arr = btc_rsi.index
            pos = arr.searchsorted(ts)
            pos = min(pos, len(arr) - 1)
            ts = arr[pos]
        idx = btc_rsi.index.get_loc(ts)
        r_now = btc_rsi.iloc[idx]
        r_prev = btc_rsi.iloc[idx - 1] if idx > 0 else float("nan")
        return r_now, r_prev

    # Normalize TV signal bars to UTC-aware
    tv_long_bars_utc = set(t.tz_localize("UTC") if t.tzinfo is None else t for t in tv_long_bars)
    tv_short_bars_utc = set(t.tz_localize("UTC") if t.tzinfo is None else t for t in tv_short_bars)

    # ── Diff analysis ─────────────────────────────────────────────────────
    extra_long = eng_long_bars - tv_long_bars_utc  # engine fires, TV doesn't
    extra_short = eng_short_bars - tv_short_bars_utc  # engine fires, TV doesn't
    miss_long = tv_long_bars_utc - eng_long_bars  # TV fires, engine doesn't
    miss_short = tv_short_bars_utc - eng_short_bars  # TV fires, engine doesn't

    print(f"\n{'=' * 70}")
    print(f"Extra LONG bars (engine fires, TV doesn't): {len(extra_long)}")
    for t in sorted(extra_long):
        rsi_now, rsi_prev = get_rsi_at(t)
        print(f"  {t}  RSI[bar]={rsi_now:.4f}  RSI[prev]={rsi_prev:.4f}")

    print(f"\nExtra SHORT bars (engine fires, TV doesn't): {len(extra_short)}")
    for t in sorted(extra_short):
        rsi_now, rsi_prev = get_rsi_at(t)
        next_bar = t + pd.Timedelta(minutes=30)
        eth_open = candles.loc[next_bar, "open"] if next_bar in candles.index else float("nan")
        print(f"  {t}  RSI[bar]={rsi_now:.4f}  RSI[prev]={rsi_prev:.4f}  ETH_next_open={eth_open:.2f}")

    print(f"\nMissing LONG bars (TV fires, engine doesn't): {len(miss_long)}")
    for t in sorted(miss_long):
        rsi_now, rsi_prev = get_rsi_at(t)
        tv_match = tv_longs[
            tv_longs["signal_bar"].apply(lambda x: (x.tz_localize("UTC") if x.tzinfo is None else x) == t)
        ]
        ep = tv_match["ep"].values[0] if len(tv_match) > 0 else float("nan")
        print(f"  {t}  RSI[bar]={rsi_now:.4f}  RSI[prev]={rsi_prev:.4f}  TV_ep={ep:.2f}")

    print(f"\nMissing SHORT bars (TV fires, engine doesn't): {len(miss_short)}")
    for t in sorted(miss_short):
        rsi_now, rsi_prev = get_rsi_at(t)
        tv_match = tv_shorts[
            tv_shorts["signal_bar"].apply(lambda x: (x.tz_localize("UTC") if x.tzinfo is None else x) == t)
        ]
        ep = tv_match["ep"].values[0] if len(tv_match) > 0 else float("nan")
        next_bar = t + pd.Timedelta(minutes=30)
        eth_open = candles.loc[next_bar, "open"] if next_bar in candles.index else float("nan")
        print(f"  {t}  RSI[bar]={rsi_now:.4f}  RSI[prev]={rsi_prev:.4f}  TV_ep={ep:.2f}  ETH_next_open={eth_open:.2f}")

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("SUMMARY:")
    print(
        f"  Engine has {len(extra_long)} extra long + {len(extra_short)} extra short = {len(extra_long) + len(extra_short)} extra signals"
    )
    print(
        f"  Engine missing {len(miss_long)} long + {len(miss_short)} short = {len(miss_long) + len(miss_short)} signals vs TV"
    )
    print(f"  Net diff: {(len(extra_long) + len(extra_short)) - (len(miss_long) + len(miss_short))}")
    print()
    print("NOTE: These are SIGNAL bars, not trade bars.")
    print("  Pyramiding=1 means consecutive signals on same side are blocked.")
    print("  So the # of extra/missing TRADES may differ from # of extra/missing SIGNALS.")

    # ── Also show RSI at key bars ──────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("RSI values at known divergence window (2025-02-12 06:00-10:30):")
    for tstr in [
        "2025-02-12 06:00",
        "2025-02-12 06:30",
        "2025-02-12 07:00",
        "2025-02-12 07:30",
        "2025-02-12 08:00",
        "2025-02-12 08:30",
        "2025-02-12 09:00",
        "2025-02-12 09:30",
        "2025-02-12 10:00",
        "2025-02-12 10:30",
    ]:
        ts = pd.Timestamp(tstr, tz="UTC")
        if ts in btc_rsi.index:
            idx = btc_rsi.index.get_loc(ts)
            r = btc_rsi.iloc[idx]
            prev = btc_rsi.iloc[idx - 1] if idx > 0 else float("nan")
            c = btc_close.loc[ts]
            cross = ">>> CROSS <<<" if (prev >= 52 and r < 52) else ""
            print(f"  {tstr}  close={c:.2f}  RSI={r:.4f}  prev={prev:.4f}  {cross}")
        else:
            print(f"  {tstr}  NOT FOUND")


asyncio.run(main())
