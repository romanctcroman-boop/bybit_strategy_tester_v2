"""
Direct BTC bar-by-bar comparison: TV (BYBIT_BTCUSDT.P) vs our Bybit REST API.
Then rerun signals using TV BTC data to see if signal count matches TV exactly.
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
logger.add(sys.stderr, level="ERROR")

import numpy as np
import pandas as pd

from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

TV_BTC_CSV = r"c:\Users\roman\Downloads\BYBIT_BTCUSDT.P, 30 (2).csv"
TV_ETH_CSV = r"c:\Users\roman\Downloads\BYBIT_ETHUSDT.P, 30 (2).csv"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"

TV_SHORT_BARS = [
    pd.Timestamp("2026-02-01 10:00", tz="UTC"),
    pd.Timestamp("2026-02-02 00:30", tz="UTC"),
    pd.Timestamp("2026-02-03 04:00", tz="UTC"),
    pd.Timestamp("2026-02-04 04:30", tz="UTC"),
    pd.Timestamp("2026-02-06 06:00", tz="UTC"),
    pd.Timestamp("2026-02-07 12:30", tz="UTC"),
    pd.Timestamp("2026-02-08 03:00", tz="UTC"),
    pd.Timestamp("2026-02-09 23:00", tz="UTC"),
    pd.Timestamp("2026-02-11 20:00", tz="UTC"),
    pd.Timestamp("2026-02-13 04:00", tz="UTC"),
    pd.Timestamp("2026-02-23 12:00", tz="UTC"),
]


def rsi14(series):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_g = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_l = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_g / avg_l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


async def main():
    svc = BacktestService()

    # ── Load TV BTC bars ──────────────────────────────────────────────────────
    tv_btc = pd.read_csv(TV_BTC_CSV)
    tv_btc["time"] = pd.to_datetime(tv_btc["time"], utc=True)
    tv_btc = tv_btc.set_index("time").sort_index()
    tv_btc = tv_btc[~tv_btc.index.duplicated(keep="last")]
    print(f"TV BTC bars:  {len(tv_btc):6d}  [{tv_btc.index[0].date()} .. {tv_btc.index[-1].date()}]")

    # ── Fetch our API BTC bars (same window) ──────────────────────────────────
    print("Fetching Bybit BTC API 2025-01-01..2026-02-25 ...")
    api_btc_2025 = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-25", tz="UTC"),
    )
    if api_btc_2025.index.tz is None:
        api_btc_2025.index = api_btc_2025.index.tz_localize("UTC")
    api_btc_2025 = api_btc_2025.sort_index()
    api_btc_2025 = api_btc_2025[~api_btc_2025.index.duplicated(keep="last")]
    print(f"API BTC bars: {len(api_btc_2025):6d}  [{api_btc_2025.index[0].date()} .. {api_btc_2025.index[-1].date()}]")

    # ── Compare closes ────────────────────────────────────────────────────────
    common = tv_btc.index.intersection(api_btc_2025.index)
    tv_only = tv_btc.index.difference(api_btc_2025.index)
    api_only = api_btc_2025.index.difference(tv_btc.index)
    print(f"\nCommon: {len(common)},  TV-only: {len(tv_only)},  API-only: {len(api_only)}")

    tv_c = tv_btc.loc[common, "close"]
    api_c = api_btc_2025.loc[common, "close"]
    diff = (tv_c - api_c).abs()

    print(f"\nBTC Close price diff distribution:")
    for thr in [0.01, 0.1, 1.0, 5.0, 10.0, 50.0]:
        cnt = (diff > thr).sum()
        print(f"  > ${thr:6.2f}: {cnt:5d} bars  ({cnt / len(common) * 100:.3f}%)")

    big = diff[diff > 0.1].sort_values(ascending=False)
    print(f"\nBars with |close diff| > $0.10: {len(big)}")
    if len(big) > 0:
        print(f"{'Time (UTC)':22s}  {'TV close':12s}  {'API close':12s}  {'diff':8s}")
        for ts in big.index[:30]:
            print(f"{str(ts)[:22]:22s}  {tv_c[ts]:12.2f}  {api_c[ts]:12.2f}  {tv_c[ts] - api_c[ts]:+8.2f}")
        if len(big) > 30:
            print(f"  ... and {len(big) - 30} more")

    # ── RSI comparison: TV BTC RSI vs API BTC RSI ─────────────────────────────
    # Use only common bars, so RSI is computed on same timestamps
    # BUT: for proper RSI we need warmup — TV has 2025-01-01 start,
    # API has 2020 warmup. Let's compare both WITH the 2025 start only.
    tv_rsi = rsi14(tv_c)
    api_rsi = rsi14(api_c)
    rsi_diff = (tv_rsi - api_rsi).abs()

    print(f"\nBTC RSI diff (both starting 2025-01-01, no warmup before):")
    for thr in [0.001, 0.01, 0.1, 0.5, 1.0]:
        cnt = (rsi_diff > thr).sum()
        print(f"  > {thr:.3f}: {cnt:5d} bars  ({cnt / len(common) * 100:.3f}%)")

    # Show RSI at divergent signal bars (with only-2025 start)
    print(f"\nBTC RSI at TV short-signal bars (same-start, no warmup diff):")
    print(
        f"{'Time (UTC)':22s}  {'TV_RSI prev':11s}  {'TV_RSI cur':10s}  {'API_RSI prev':12s}  {'API_RSI cur':11s}  TV_cross  API_cross"
    )
    for ts in TV_SHORT_BARS:
        if ts not in tv_rsi.index:
            continue
        loc = tv_rsi.index.get_loc(ts)
        prev_ts = tv_rsi.index[loc - 1]
        tv_p = tv_rsi.iloc[loc - 1]
        tv_c2 = tv_rsi.iloc[loc]
        api_p = api_rsi.iloc[loc - 1] if loc < len(api_rsi) else float("nan")
        api_c2 = api_rsi.iloc[loc] if loc < len(api_rsi) else float("nan")
        tv_cross = tv_p >= 52 and tv_c2 < 52
        api_cross = api_p >= 52 and api_c2 < 52
        match = "OK" if tv_cross == api_cross else "MISMATCH <<"
        print(
            f"{str(ts)[:22]:22s}  {tv_p:11.4f}  {tv_c2:10.4f}  {api_p:12.4f}  {api_c2:11.4f}  {str(tv_cross):5}  {str(api_cross):5}  {match}"
        )

    # ── Now fetch API BTC with full 2020 warmup ───────────────────────────────
    print(f"\nFetching BTC API 2020 warmup...")
    btc_w = await svc._fetch_historical_data(
        "BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")
    )
    if btc_w.index.tz is None:
        btc_w.index = btc_w.index.tz_localize("UTC")
    btc_full = pd.concat([btc_w, api_btc_2025]).sort_index()
    btc_full = btc_full[~btc_full.index.duplicated(keep="last")]
    api_rsi_full = rsi14(btc_full["close"])

    # TV BTC also needs warmup — but TV file only starts 2025-01-01.
    # We can prepend API warmup bars to TV data to get the same RSI base.
    btc_warmup = btc_w.copy()
    if btc_warmup.index.tz is None:
        btc_warmup.index = btc_warmup.index.tz_localize("UTC")

    # Build TV BTC with warmup prepended
    # Use API data for warmup (2020-2024), then TV data for 2025+
    tv_btc_with_warmup = pd.concat(
        [btc_warmup[["open", "high", "low", "close"]], tv_btc[["open", "high", "low", "close"]]]
    ).sort_index()
    tv_btc_with_warmup = tv_btc_with_warmup[~tv_btc_with_warmup.index.duplicated(keep="last")]
    # Add volume if missing
    if "volume" not in tv_btc_with_warmup.columns:
        tv_btc_with_warmup["volume"] = 0.0

    tv_rsi_full = rsi14(tv_btc_with_warmup["close"])

    print(f"\nBTC RSI at TV short-signal bars (FULL warmup from 2020):")
    print(
        f"{'Time (UTC)':22s}  {'TV_RSI prev':11s}  {'TV_RSI cur':10s}  {'API_RSI prev':12s}  {'API_RSI cur':11s}  TV_cross  API_cross"
    )
    for ts in TV_SHORT_BARS:
        if ts not in tv_rsi_full.index:
            print(f"{str(ts)[:22]:22s}  NOT IN TV DATA")
            continue
        loc = tv_rsi_full.index.get_loc(ts)
        tv_p = tv_rsi_full.iloc[loc - 1]
        tv_c2 = tv_rsi_full.iloc[loc]
        api_p = (
            api_rsi_full.loc[ts - pd.Timedelta("30min")]
            if (ts - pd.Timedelta("30min")) in api_rsi_full.index
            else float("nan")
        )
        api_c2 = api_rsi_full.loc[ts] if ts in api_rsi_full.index else float("nan")
        tv_cross = tv_p >= 52 and tv_c2 < 52
        api_cross = api_p >= 52 and api_c2 < 52
        match = "OK" if tv_cross == api_cross else "MISMATCH <<"
        print(
            f"{str(ts)[:22]:22s}  {tv_p:11.4f}  {tv_c2:10.4f}  {api_p:12.4f}  {api_c2:11.4f}  {str(tv_cross):5}  {str(api_cross):5}  {match}"
        )

    # ── Run signals with TV BTC ───────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("Running signals with TV BTC (full warmup) vs API BTC...")

    # Load strategy graph
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?", (STRATEGY_ID,)
    ).fetchone()
    conn.close()
    name2, br, cr, gr = row
    blocks = json.loads(br) if isinstance(br, str) else (br or [])
    conns = json.loads(cr) if isinstance(cr, str) else (cr or [])
    gp = json.loads(gr) if isinstance(gr, str) else (gr or {})
    graph = {
        "name": name2,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if gp.get("main_strategy"):
        graph["main_strategy"] = gp["main_strategy"]

    eth_api = await svc._fetch_historical_data(
        "ETHUSDT", "30", pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2026-02-25", tz="UTC")
    )
    if eth_api.index.tz is None:
        eth_api.index = eth_api.index.tz_localize("UTC")
    eth_api = eth_api.sort_index()
    eth_api = eth_api[~eth_api.index.duplicated(keep="last")]

    # Run with TV BTC
    adapter_tv = StrategyBuilderAdapter(graph, btcusdt_ohlcv=tv_btc_with_warmup, btcusdt_5m_ohlcv=None)
    sig_tv = adapter_tv.generate_signals(eth_api)
    se_tv = (
        sig_tv.short_entries.reindex(eth_api.index, fill_value=False)
        if sig_tv.short_entries is not None
        else pd.Series(False, index=eth_api.index)
    )
    le_tv = sig_tv.entries.reindex(eth_api.index, fill_value=False)

    # Run with API BTC
    adapter_api = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_full, btcusdt_5m_ohlcv=None)
    sig_api = adapter_api.generate_signals(eth_api)
    se_api = (
        sig_api.short_entries.reindex(eth_api.index, fill_value=False)
        if sig_api.short_entries is not None
        else pd.Series(False, index=eth_api.index)
    )
    le_api = sig_api.entries.reindex(eth_api.index, fill_value=False)

    short_tv = set(eth_api.index[se_tv])
    long_tv = set(eth_api.index[le_tv])
    short_api = set(eth_api.index[se_api])
    long_api = set(eth_api.index[le_api])

    print(f"[TV  BTC] Long: {len(long_tv)},  Short: {len(short_tv)}")
    print(f"[API BTC] Long: {len(long_api)},  Short: {len(short_api)}")

    # Filter to TV window (2026-01-30 to 2026-02-24)
    win_start = pd.Timestamp("2026-01-30", tz="UTC")
    win_end = pd.Timestamp("2026-02-25", tz="UTC")

    short_tv_win = sorted(t for t in short_tv if win_start <= t < win_end)
    short_api_win = sorted(t for t in short_api if win_start <= t < win_end)
    long_tv_win = sorted(t for t in long_tv if win_start <= t < win_end)
    long_api_win = sorted(t for t in long_api if win_start <= t < win_end)

    print(f"\nIn window 2026-01-30..2026-02-24:")
    print(f"  TV  BTC short: {len(short_tv_win)}")
    print(f"  API BTC short: {len(short_api_win)}")
    print(f"  TV  BTC long:  {len(long_tv_win)}")
    print(f"  API BTC long:  {len(long_api_win)}")

    tv_short_set = set(TV_SHORT_BARS)
    print(f"\nExpected TV short signals: {len(TV_SHORT_BARS)}")
    match_tv_btc = len(set(short_tv_win) & tv_short_set)
    match_api_btc = len(set(short_api_win) & tv_short_set)
    print(f"  With TV  BTC: {match_tv_btc}/11 exact matches")
    print(f"  With API BTC: {match_api_btc}/11 exact matches")

    extra_tv = sorted(set(short_tv_win) - tv_short_set)
    extra_api = sorted(set(short_api_win) - tv_short_set)
    miss_tv = sorted(tv_short_set - set(short_tv_win))
    miss_api = sorted(tv_short_set - set(short_api_win))

    print(f"\n  TV  BTC: {len(extra_tv)} extra, {len(miss_tv)} missing")
    print(f"  API BTC: {len(extra_api)} extra, {len(miss_api)} missing")

    if miss_tv:
        print(f"  Missing with TV  BTC: {[str(t)[:16] for t in miss_tv]}")
    if miss_api:
        print(f"  Missing with API BTC: {[str(t)[:16] for t in miss_api]}")
    if extra_tv[:5]:
        print(f"  Extra with TV  BTC (first 5): {[str(t)[:16] for t in extra_tv[:5]]}")


asyncio.run(main())
