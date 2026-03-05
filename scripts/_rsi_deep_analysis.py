"""
Deep-dive analysis of the 22 extra engine entries vs TV replacements.
For each extra engine entry, print:
  - The RSI crossunder details at signal bar T
  - RSI at T-1, T, T+1, T+2
  - Whether there's a subsequent crossunder within 12h (TV fires there instead)
  - The RSI "depth" below the cross level

Goal: find the pattern that distinguishes signals TV fires vs skips.
"""

import asyncio
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

from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.core.indicators import calculate_rsi

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")

# fmt: (engine_entry_utc, tv_entry_utc_or_None)
# extra engine entries and their TV replacement (from _divergence_analysis output)
DIVERGENCES = [
    ("2025-02-12 07:30", "2025-02-12 10:00"),
    ("2025-02-15 00:00", "2025-02-15 16:30"),
    ("2025-02-17 13:00", None),
    ("2025-02-18 04:30", "2025-02-19 16:00"),
    ("2025-02-19 18:00", None),
    ("2025-03-30 05:30", None),
    ("2025-03-31 12:00", "2025-04-02 02:30"),
    ("2025-04-20 02:00", None),
    ("2025-05-11 20:30", None),
    ("2025-05-13 07:30", None),
    ("2025-05-19 01:30", None),
    ("2025-06-22 07:00", "2025-06-22 12:30"),
    ("2025-06-24 19:00", "2025-06-25 22:30"),
    ("2025-07-03 04:30", None),
    ("2025-07-04 23:00", None),
    ("2025-07-11 18:00", None),
    ("2025-07-13 09:30", None),
    ("2025-07-24 09:30", "2025-07-25 12:00"),
    ("2025-08-16 01:00", "2025-08-16 14:00"),
    ("2025-08-27 02:30", "2025-08-27 12:30"),
    ("2025-09-02 11:00", None),
    ("2025-11-25 00:00", "2025-11-25 05:30"),
]


def load_graph():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
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
    return graph


async def main():
    svc = BacktestService()

    candles_eth = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    print(f"ETH: {len(candles_eth)} candles (tz={candles_eth.index.tz})")

    # BTC with warmup
    WARMUP = 500
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc_warmup = None
    try:
        raw = await svc.adapter.get_historical_klines(
            symbol="BTCUSDT",
            interval="30",
            start_time=int(btc_start.timestamp() * 1000),
            end_time=int(START_DATE.timestamp() * 1000),
            market_type="linear",
        )
        if raw:
            dfw = pd.DataFrame(raw)
            col_map = {
                "startTime": "timestamp",
                "open_time": "timestamp",
                "openPrice": "open",
                "highPrice": "high",
                "lowPrice": "low",
                "closePrice": "close",
            }
            for old, new in col_map.items():
                if old in dfw.columns and new not in dfw.columns:
                    dfw = dfw.rename(columns={old: new})
            for col in ["open", "high", "low", "close", "volume"]:
                if col in dfw.columns:
                    dfw[col] = pd.to_numeric(dfw[col], errors="coerce")
            if "timestamp" in dfw.columns:
                dfw["timestamp"] = (
                    pd.to_datetime(dfw["timestamp"], unit="ms", utc=True)
                    if dfw["timestamp"].dtype in ["int64", "float64"]
                    else pd.to_datetime(dfw["timestamp"], utc=True)
                )
                dfw = dfw.set_index("timestamp").sort_index()
            btc_warmup = dfw
    except Exception as e:
        print(f"Warmup failed: {e}")

    if btc_warmup is not None and len(btc_warmup) > 0:
        if btc_main.index.tz is None:
            btc_main.index = btc_main.index.tz_localize("UTC")
        if btc_warmup.index.tz is None:
            btc_warmup.index = btc_warmup.index.tz_localize("UTC")
        btc_full = pd.concat([btc_warmup, btc_main]).sort_index()
        btc_full = btc_full[~btc_full.index.duplicated(keep="last")]
    else:
        btc_full = btc_main

    # Compute RSI on full BTC series (same as indicator_handlers.py)
    RSI_PERIOD = 14
    CROSS_LEVEL = 52.0
    rsi_vals = calculate_rsi(btc_full["close"].values.astype(float), RSI_PERIOD)
    btc_full["rsi"] = rsi_vals

    # Align to ETH candle index
    eth_idx = candles_eth.index
    # Handle tz mismatch
    if eth_idx.tz is None and btc_full.index.tz is not None:
        eth_idx_utc = eth_idx.tz_localize("UTC")
    else:
        eth_idx_utc = eth_idx

    rsi_aligned = btc_full["rsi"].reindex(eth_idx_utc if eth_idx.tz is None else eth_idx)

    # Short signal: rsi[T-1] >= 52 AND rsi[T] < 52
    rsi_prev = rsi_aligned.shift(1)
    short_cross = (rsi_prev >= CROSS_LEVEL) & (rsi_aligned < CROSS_LEVEL)

    print(f"\nTotal RSI crossunders below {CROSS_LEVEL}: {short_cross.sum()}")
    print(f"Candle index sample: {candles_eth.index[:2].tolist()}")

    def get_rsi_window(ts_str, n_before=3, n_after=5):
        """Get RSI values for N bars around timestamp."""
        # Try tz-naive
        ts = pd.Timestamp(ts_str)
        if ts not in eth_idx:
            ts_utc = pd.Timestamp(ts_str, tz="UTC")
            if ts_utc in eth_idx:
                ts = ts_utc
            else:
                return None, None
        pos = eth_idx.get_loc(ts)
        lo, hi = max(0, pos - n_before), min(len(eth_idx), pos + n_after + 1)
        window_idx = eth_idx[lo:hi]
        window_rsi = rsi_aligned.iloc[lo:hi]
        return window_idx, window_rsi, pos

    # Header
    print(f"\n{'=' * 80}")
    print(
        f"{'#':>3}  {'Engine Entry':16}  {'TV Entry':16}  {'RSI[T-1]':>9}  {'RSI[T]':>7}  "
        f"{'RSI[T+1]':>9}  {'RSI[T+2]':>9}  {'TV_RSI[T]':>9}  {'TV_RSI[T+1]':>11}  Notes"
    )
    print(f"{'=' * 80}")

    for i, (eng_ts_str, tv_ts_str) in enumerate(DIVERGENCES, 1):
        result = get_rsi_window(eng_ts_str, 2, 6)
        if result[0] is None:
            print(f"{i:>3}  {eng_ts_str:16}  MISSING FROM CANDLES")
            continue
        win_idx, win_rsi, pos = result

        rsi_tm1 = rsi_aligned.iloc[pos - 1] if pos >= 1 else np.nan
        rsi_t = rsi_aligned.iloc[pos]
        rsi_tp1 = rsi_aligned.iloc[pos + 1] if pos + 1 < len(rsi_aligned) else np.nan
        rsi_tp2 = rsi_aligned.iloc[pos + 2] if pos + 2 < len(rsi_aligned) else np.nan

        # TV entry RSI
        tv_rsi_t = tv_rsi_tp1 = np.nan
        if tv_ts_str:
            tv_result = get_rsi_window(tv_ts_str, 1, 3)
            if tv_result[0] is not None:
                tv_pos = tv_result[2]
                tv_rsi_t = rsi_aligned.iloc[tv_pos]
                tv_rsi_tp1 = rsi_aligned.iloc[tv_pos + 1] if tv_pos + 1 < len(rsi_aligned) else np.nan

        # Check if RSI bounces above CROSS_LEVEL before TV entry
        bounces_back = rsi_tp1 >= CROSS_LEVEL if not np.isnan(rsi_tp1) else False
        tv_label = tv_ts_str[:13] if tv_ts_str else "NONE"

        note = "BOUNCE" if bounces_back else "stays<52"

        print(
            f"{i:>3}  {eng_ts_str[:13]:16}  {tv_label:16}  "
            f"{rsi_tm1:>9.3f}  {rsi_t:>7.3f}  "
            f"{rsi_tp1:>9.3f}  {rsi_tp2:>9.3f}  "
            f"{tv_rsi_t:>9.3f}  {tv_rsi_tp1:>11.3f}  {note}"
        )

    print(f"\n{'=' * 80}")
    print("LEGEND: RSI[T] = RSI at signal bar; RSI[T+1] = next bar after entry")
    print("BOUNCE = RSI[T+1] >= 52 (bounces back above cross level)")
    print()

    # Separate: show stats for all engine signals that TV fires (matched)
    # We need to compare BOUNCE rate in extra vs matched
    graph = load_graph()
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_full)
    signals = adapter.generate_signals(candles_eth)
    se_arr = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(candles_eth), dtype=bool)
    )

    # For all short entry signals, compute stats
    se_times = candles_eth.index[se_arr]
    bounce_count = 0
    no_bounce_count = 0
    for ts in se_times:
        pos = eth_idx.get_loc(ts)
        r_tp1 = rsi_aligned.iloc[pos + 1] if pos + 1 < len(rsi_aligned) else np.nan
        if np.isnan(r_tp1):
            continue
        if r_tp1 >= CROSS_LEVEL:
            bounce_count += 1
        else:
            no_bounce_count += 1

    print("ALL 600 short entry signals:")
    print(f"  RSI[T+1] >= {CROSS_LEVEL} (bounce): {bounce_count} ({bounce_count / 600 * 100:.1f}%)")
    print(f"  RSI[T+1] <  {CROSS_LEVEL} (stays):  {no_bounce_count} ({no_bounce_count / 600 * 100:.1f}%)")

    extra_bounce = sum(
        1
        for eng_ts_str, _ in DIVERGENCES
        if (r := get_rsi_window(eng_ts_str, 1, 2))
        and r[0] is not None
        and not np.isnan(rsi_aligned.iloc[r[2] + 1])
        and rsi_aligned.iloc[r[2] + 1] >= CROSS_LEVEL
    )
    print(f"\nExtra engine signals with bounce: {extra_bounce}/22")
    print(f"Extra engine signals without bounce: {22 - extra_bounce}/22")


asyncio.run(main())
