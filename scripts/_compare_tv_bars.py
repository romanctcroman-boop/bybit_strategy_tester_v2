"""
Direct bar-by-bar comparison: TV ETH bars vs our Bybit API data.
Also compares TV signals (Пересечение Long/Short) vs our engine signals.

TV file: BYBIT_ETHUSDT.P, 30.csv  — exported from TradingView chart
Range: 2026-01-30 to 2026-02-24 (1215 bars)
"""

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="ERROR")

import numpy as np
import pandas as pd

from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

TV_CSV = r"c:\Users\roman\Downloads\BYBIT_ETHUSDT.P, 30.csv"

# ── Load TV bars ──────────────────────────────────────────────────────────────
tv = pd.read_csv(TV_CSV)
tv["time"] = pd.to_datetime(tv["time"], utc=True)
tv = tv.set_index("time").sort_index()
print(f"TV bars: {len(tv)}  [{tv.index[0]} .. {tv.index[-1]}]")

# TV signals on bar (signal is on the BAR that closed — next bar is entry)
tv_long_bars = tv[tv["Пересечение Long"] == 1].index
tv_short_bars = tv[tv["Пересечение Short"] == 1].index
print(f"TV long signals:  {len(tv_long_bars)}")
print(f"TV short signals: {len(tv_short_bars)}")


async def main():
    svc = BacktestService()

    # ── Fetch our Bybit ETH bars ──────────────────────────────────────────────
    start = pd.Timestamp("2026-01-30", tz="UTC")
    end = pd.Timestamp("2026-02-25", tz="UTC")
    eth = await svc._fetch_historical_data("ETHUSDT", "30", start, end)
    if eth.index.tz is None:
        eth.index = eth.index.tz_localize("UTC")
    print(f"\nBybit ETH bars: {len(eth)}  [{eth.index[0]} .. {eth.index[-1]}]")

    # ── Bar-by-bar close price comparison ────────────────────────────────────
    common_idx = tv.index.intersection(eth.index)
    print(f"\nCommon timestamps: {len(common_idx)}")

    diffs = []
    for ts in common_idx:
        tv_close = tv.loc[ts, "close"]
        our_close = eth.loc[ts, "close"]
        diff = tv_close - our_close
        if abs(diff) > 0.005:  # more than 0.5 cent difference
            diffs.append((ts, tv_close, our_close, diff))

    print(f"Bars with close diff > $0.005: {len(diffs)}")
    if diffs:
        print(f"\n{'Time (UTC)':25s}  {'TV close':10s}  {'Our close':10s}  {'diff':8s}")
        for ts, tvc, ourc, d in diffs[:30]:
            print(f"{str(ts)[:25]:25s}  {tvc:10.2f}  {ourc:10.2f}  {d:+8.4f}")
        if len(diffs) > 30:
            print(f"  ... and {len(diffs) - 30} more")

    # ── Missing bars ──────────────────────────────────────────────────────────
    tv_only = tv.index.difference(eth.index)
    our_only = eth.index.difference(tv.index)
    print(f"\nBars in TV but NOT in our data:  {len(tv_only)}")
    print(f"Bars in our data but NOT in TV:  {len(our_only)}")
    if len(tv_only) > 0:
        print("  TV-only timestamps:", list(tv_only[:10]))
    if len(our_only) > 0:
        print("  Our-only timestamps:", list(our_only[:10]))

    # ── Now fetch BTC (Bybit, 2020 warmup) and compute our RSI signals ───────
    btc_start = pd.Timestamp("2020-01-01", tz="UTC")
    eth_full_start = pd.Timestamp("2025-01-01", tz="UTC")

    print("\nFetching Bybit BTC 30m (2020 warmup) for RSI...")
    btc_w = await svc._fetch_historical_data("BTCUSDT", "30", btc_start, eth_full_start)
    btc_m = await svc._fetch_historical_data("BTCUSDT", "30", eth_full_start, end)
    btc = pd.concat([btc_w, btc_m]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]
    if btc.index.tz is None:
        btc.index = btc.index.tz_localize("UTC")

    # Load strategy graph
    import json
    import sqlite3

    DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
    STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?", (STRATEGY_ID,)
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br) if isinstance(br, str) else (br or [])
    conns = json.loads(cr) if isinstance(cr, str) else (cr or [])
    gp = json.loads(gr) if isinstance(gr, str) else (gr or {})
    graph = {
        "name": name,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if gp.get("main_strategy"):
        graph["main_strategy"] = gp["main_strategy"]

    # Generate signals on full ETH (2025-2026)
    eth_full = await svc._fetch_historical_data("ETHUSDT", "30", eth_full_start, end)
    if eth_full.index.tz is None:
        eth_full.index = eth_full.index.tz_localize("UTC")

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(eth_full)

    le = signals.entries.reindex(eth_full.index, fill_value=False)
    se = (
        signals.short_entries.reindex(eth_full.index, fill_value=False)
        if signals.short_entries is not None
        else pd.Series(False, index=eth_full.index)
    )

    # Get signal bars in TV window
    our_long_bars = le[le & (le.index >= tv.index[0])].index
    our_short_bars = se[se & (se.index >= tv.index[0])].index

    print(f"\n=== Signal comparison in TV window ({tv.index[0].date()} to {tv.index[-1].date()}) ===")
    print(f"TV   long signals: {len(tv_long_bars)}  at: {[str(t)[:16] for t in tv_long_bars]}")
    print(f"Our  long signals: {len(our_long_bars)} at: {[str(t)[:16] for t in our_long_bars]}")
    print(f"TV  short signals: {len(tv_short_bars)} at: {[str(t)[:16] for t in tv_short_bars]}")
    print(f"Our short signals: {len(our_short_bars)} at: {[str(t)[:16] for t in our_short_bars]}")

    # Exact matches
    long_match = set(tv_long_bars) & set(our_long_bars)
    short_match = set(tv_short_bars) & set(our_short_bars)
    print(
        f"\nExact time matches: long={len(long_match)}/{len(tv_long_bars)},  short={len(short_match)}/{len(tv_short_bars)}"
    )

    # Mismatches
    tv_long_only = sorted(set(tv_long_bars) - set(our_long_bars))
    our_long_only = sorted(set(our_long_bars) - set(tv_long_bars))
    tv_short_only = sorted(set(tv_short_bars) - set(our_short_bars))
    our_short_only = sorted(set(our_short_bars) - set(tv_short_bars))

    if tv_long_only:
        print(f"\nLong in TV but NOT in engine:")
        for t in tv_long_only:
            print(f"  {str(t)[:16]}  close={tv.loc[t, 'close'] if t in tv.index else 'N/A'}")
    if our_long_only:
        print(f"\nLong in engine but NOT in TV:")
        for t in our_long_only:
            print(f"  {str(t)[:16]}  close={eth_full.loc[t, 'close'] if t in eth_full.index else 'N/A'}")
    if tv_short_only:
        print(f"\nShort in TV but NOT in engine:")
        for t in tv_short_only:
            print(f"  {str(t)[:16]}  close={tv.loc[t, 'close'] if t in tv.index else 'N/A'}")
    if our_short_only:
        print(f"\nShort in engine but NOT in TV:")
        for t in our_short_only:
            print(f"  {str(t)[:16]}  close={eth_full.loc[t, 'close'] if t in eth_full.index else 'N/A'}")

    # ── For each mismatch, print BTC RSI at that bar ──────────────────────────
    if tv_short_only or our_short_only:
        print(f"\n=== BTC RSI at divergent short-signal bars ===")

        def rsi_series(series, period=14):
            delta = series.diff()
            gain = delta.clip(lower=0)
            loss = (-delta).clip(lower=0)
            avg_g = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
            avg_l = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
            rs = avg_g / avg_l.replace(0, np.nan)
            return 100 - (100 / (1 + rs))

        btc_rsi = rsi_series(btc["close"])
        btc_rsi.index = btc.index

        all_divergent = sorted(set(tv_short_only) | set(our_short_only))
        print(f"{'Time (UTC)':20s}  {'BTC RSI':8s}  {'prev RSI':8s}  who_has_it")
        for t in all_divergent:
            if t not in btc_rsi.index:
                continue
            cur = btc_rsi.loc[t]
            prev_t = btc_rsi.index[btc_rsi.index.get_loc(t) - 1]
            prev = btc_rsi.loc[prev_t]
            who = "TV" if t in tv_short_only else "Engine"
            print(
                f"{str(t)[:20]:20s}  {cur:8.4f}  {prev:8.4f}  {who}  (cross52: prev={prev:.4f}>=52, cur={cur:.4f}<52 ? {prev >= 52 and cur < 52})"
            )


asyncio.run(main())
