"""
Detailed RSI profile for the TV replacements that have anomalous RSI[T-1] < 52.
When TV replacement has RSI[T-1] < 52, it's NOT a standard crossunder.
This means TV must be firing on something else — look at the full RSI history
for 10 bars before and 5 after each TV replacement entry.
"""

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import numpy as np
import pandas as pd
from loguru import logger

logger.remove()

from backend.backtesting.service import BacktestService
from backend.core.indicators import calculate_rsi

START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")

# TV entries (from z4.csv) - what TV actually fires on
# These are the "missing TV" trades that the engine doesn't produce
TV_MISSING = [
    # (tv_entry_utc, paired_engine_extra_or_None)
    ("2025-02-12 10:00", "2025-02-12 07:30"),
    ("2025-02-14 16:30", None),  # no engine match
    ("2025-02-15 16:30", "2025-02-15 00:00"),
    ("2025-02-19 16:00", "2025-02-18 04:30"),
    ("2025-03-28 18:00", None),  # long trade, different direction
    ("2025-04-02 02:30", "2025-03-31 12:00"),
    ("2025-04-19 21:00", None),
    ("2025-05-11 16:00", None),
    ("2025-06-22 12:30", "2025-06-22 07:00"),
    ("2025-06-25 22:30", "2025-06-24 19:00"),
    ("2025-07-10 12:00", None),
    ("2025-07-25 05:00", None),  # long
    ("2025-07-25 12:00", "2025-07-24 09:30"),
    ("2025-07-26 23:30", None),
    ("2025-08-01 15:00", None),
    ("2025-08-16 14:00", "2025-08-16 01:00"),
    ("2025-08-27 12:30", "2025-08-27 02:30"),
    ("2025-11-25 05:30", "2025-11-25 00:00"),
]


async def main():
    svc = BacktestService()
    candles_eth = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    eth_idx = candles_eth.index

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

    RSI_PERIOD = 14
    CROSS_LEVEL = 52.0
    rsi_vals = calculate_rsi(btc_full["close"].values.astype(float), RSI_PERIOD)
    btc_full["rsi"] = rsi_vals

    if eth_idx.tz is None and btc_full.index.tz is not None:
        align_idx = eth_idx.tz_localize("UTC")
    else:
        align_idx = eth_idx
    rsi_a = btc_full["rsi"].reindex(align_idx)

    def get_pos(ts_str):
        ts = pd.Timestamp(ts_str)
        if ts not in eth_idx:
            ts = pd.Timestamp(ts_str, tz="UTC")
        return eth_idx.get_loc(ts) if ts in eth_idx else None

    # For each TV entry: print RSI for 12 bars before, entry bar, 3 bars after
    for tv_ts_str, eng_ts_str in TV_MISSING:
        pos = get_pos(tv_ts_str)
        if pos is None:
            print(f"\n{tv_ts_str}: NOT IN INDEX")
            continue

        eng_pos = get_pos(eng_ts_str) if eng_ts_str else None

        print(f"\n{'=' * 65}")
        print(f"TV fires at: {tv_ts_str}  |  Engine extra: {eng_ts_str or 'NONE'}")
        print(f"{'Bar':5}  {'Time':16}  {'RSI':>7}  Notes")
        print("-" * 50)

        lo = max(0, pos - 12)
        for i in range(lo, min(len(eth_idx), pos + 4)):
            t = eth_idx[i]
            r = rsi_a.iloc[i]
            r1 = rsi_a.iloc[i - 1] if i >= 1 else np.nan

            notes = []
            if not np.isnan(r) and not np.isnan(r1):
                if r1 >= CROSS_LEVEL and r < CROSS_LEVEL:
                    notes.append("CROSSUNDER")
                if r >= CROSS_LEVEL and r1 < CROSS_LEVEL:
                    notes.append("CROSSOVER")
            if i == pos:
                notes.append("<-- TV ENTRY")
            if eng_ts_str and i == eng_pos:
                notes.append("<-- ENGINE ENTRY")

            marker = ">>>" if i == pos else "   "
            print(f"{marker}  {str(t)[:16]}  {r:>7.3f}  {' | '.join(notes)}")

    # Summary: count how many TV missing entries are standard crossunders vs not
    print(f"\n{'=' * 65}")
    print("SUMMARY: Is the TV entry bar a standard crossunder?")
    crossunder_count = 0
    not_crossunder = 0
    for tv_ts_str, _ in TV_MISSING:
        pos = get_pos(tv_ts_str)
        if pos is None or pos < 1:
            continue
        r = rsi_a.iloc[pos]
        r1 = rsi_a.iloc[pos - 1]
        if r1 >= CROSS_LEVEL and r < CROSS_LEVEL:
            crossunder_count += 1
            print(f"  {tv_ts_str[:13]}  RSI[T-1]={r1:.3f} RSI[T]={r:.3f}  CROSSUNDER")
        else:
            not_crossunder += 1
            print(f"  {tv_ts_str[:13]}  RSI[T-1]={r1:.3f} RSI[T]={r:.3f}  NOT crossunder (r1-52={r1 - 52:.3f})")

    print(f"\nTV entries that ARE crossunders:     {crossunder_count}")
    print(f"TV entries that are NOT crossunders: {not_crossunder}")


asyncio.run(main())
