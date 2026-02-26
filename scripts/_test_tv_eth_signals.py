"""
Run Strategy_RSI_L/S_10 backtest using TV ETH bars (close prices)
to check if signal count changes vs using Bybit API ETH bars.

If signals are SAME -> ETH data doesn't matter, problem is purely BTC RSI.
If signals DIFFER -> ETH close prices also affect something.
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

TV_ETH_CSV = r"c:\Users\roman\Downloads\BYBIT_ETHUSDT.P, 30 (2).csv"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"


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

    # Load strategy graph
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

    end = pd.Timestamp("2026-02-25", tz="UTC")

    # Fetch BTC 30m (our Bybit API)
    print("Fetching BTC 30m (Bybit API, 2020 warmup)...")
    btc_w = await svc._fetch_historical_data(
        "BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")
    )
    btc_m = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2025-01-01", tz="UTC"), end)
    btc = pd.concat([btc_w, btc_m]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]
    if btc.index.tz is None:
        btc.index = btc.index.tz_localize("UTC")
    print(f"BTC bars: {len(btc)}")

    # ── Run 1: Bybit API ETH ───────────────────────────────────────────────────
    print("\nFetching ETH 30m (Bybit API)...")
    eth_api = await svc._fetch_historical_data("ETHUSDT", "30", pd.Timestamp("2025-01-01", tz="UTC"), end)
    if eth_api.index.tz is None:
        eth_api.index = eth_api.index.tz_localize("UTC")
    eth_api = eth_api.sort_index()
    eth_api = eth_api[~eth_api.index.duplicated(keep="last")]

    adapter1 = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    sig1 = adapter1.generate_signals(eth_api)
    se1 = (
        sig1.short_entries.reindex(eth_api.index, fill_value=False)
        if sig1.short_entries is not None
        else pd.Series(False, index=eth_api.index)
    )
    le1 = sig1.entries.reindex(eth_api.index, fill_value=False)

    short_times_api = sorted(eth_api.index[se1])
    long_times_api = sorted(eth_api.index[le1])
    print(f"[API ETH] Long signals: {len(long_times_api)},  Short signals: {len(short_times_api)}")

    # ── Run 2: TV ETH bars ────────────────────────────────────────────────────
    print("\nLoading TV ETH bars...")
    tv_eth = pd.read_csv(TV_ETH_CSV)
    tv_eth["time"] = pd.to_datetime(tv_eth["time"], utc=True)
    tv_eth = tv_eth.set_index("time").sort_index()
    tv_eth = tv_eth[~tv_eth.index.duplicated(keep="last")]
    tv_eth.index.name = "time"
    # Make sure columns match (open, high, low, close, volume)
    if "volume" not in tv_eth.columns:
        tv_eth["volume"] = 0.0
    print(f"TV ETH bars: {len(tv_eth)}")

    adapter2 = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    sig2 = adapter2.generate_signals(tv_eth)
    se2 = (
        sig2.short_entries.reindex(tv_eth.index, fill_value=False)
        if sig2.short_entries is not None
        else pd.Series(False, index=tv_eth.index)
    )
    le2 = sig2.entries.reindex(tv_eth.index, fill_value=False)

    short_times_tv = sorted(tv_eth.index[se2])
    long_times_tv = sorted(tv_eth.index[le2])
    print(f"[TV  ETH] Long signals: {len(long_times_tv)},  Short signals: {len(short_times_tv)}")

    # ── Compare ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SIGNAL COMPARISON (API ETH vs TV ETH, same BTC):")
    api_shorts = set(short_times_api)
    tv_shorts = set(short_times_tv)
    api_longs = set(long_times_api)
    tv_longs = set(long_times_tv)

    same_s = api_shorts == tv_shorts
    same_l = api_longs == tv_longs
    print(f"  Short signals identical: {same_s}")
    print(f"  Long  signals identical: {same_l}")

    if not same_s:
        only_api = sorted(api_shorts - tv_shorts)
        only_tv = sorted(tv_shorts - api_shorts)
        print(f"  Shorts only in API ETH ({len(only_api)}): {[str(t)[:16] for t in only_api[:5]]}")
        print(f"  Shorts only in TV  ETH ({len(only_tv)}):  {[str(t)[:16] for t in only_tv[:5]]}")

    if same_s and same_l:
        print("\nConclusion: ETH source is IRRELEVANT for signals.")
        print("=> Problem is 100% in BTC RSI data.")
    else:
        print("\nConclusion: ETH source DOES affect signals (minor).")


asyncio.run(main())
