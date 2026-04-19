"""
Debug script: print intra-bar RSI cross detection stats to understand over-firing.
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
PERIOD = 14
CROSS_SHORT_LEVEL = 52.0
CROSS_LONG_LEVEL = 24.0


async def main():
    svc = BacktestService()

    # Fetch BTC 30m with warmup
    WARMUP_BARS = 500
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    btc_main = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    btc_candles = btc_main
    btc_candles.index = (
        pd.DatetimeIndex(btc_candles.index).tz_localize("UTC") if btc_candles.index.tz is None else btc_candles.index
    )

    # Fetch BTC 5m
    btc_5m = await svc._fetch_historical_data(symbol="BTCUSDT", interval="5", start_date=START_DATE, end_date=END_DATE)
    btc_5m.index = pd.DatetimeIndex(btc_5m.index).tz_localize("UTC") if btc_5m.index.tz is None else btc_5m.index
    print(f"BTC  5m: {len(btc_5m)} bars  [{btc_5m.index[0]} .. {btc_5m.index[-1]}]")

    # Fetch ETH 30m
    eth_candles = await svc._fetch_historical_data(
        symbol="ETHUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    print(f"ETH 30m: {len(eth_candles)} bars")

    bar_index = eth_candles.index  # strategy bar index
    if bar_index.tz is None:
        bar_index = bar_index.tz_localize("UTC")

    # Compute BTC 30m Wilder RSI
    btc_close = btc_candles["close"].copy()
    if bar_index.tz is not None and btc_close.index.tz is None:
        btc_close.index = btc_close.index.tz_localize("UTC")

    btc_rsi_full_arr = calculate_rsi(btc_close.values, period=PERIOD)
    btc_rsi_full = pd.Series(btc_rsi_full_arr, index=btc_close.index)

    # Compute bar-close cross signals
    rsi_aligned = btc_rsi_full.reindex(bar_index, method="ffill").ffill()
    rsi_prev = rsi_aligned.shift(1)
    bar_close_short = (rsi_prev >= CROSS_SHORT_LEVEL) & (rsi_aligned < CROSS_SHORT_LEVEL)
    bar_close_long = (rsi_prev <= CROSS_LONG_LEVEL) & (rsi_aligned > CROSS_LONG_LEVEL)
    print(f"\nBar-close crosses: {bar_close_short.sum()} short, {bar_close_long.sum()} long")

    # Rebuild Wilder state from btc_30m_close
    closes_30m = btc_close.values
    ts_30m = np.array(btc_close.index, dtype="datetime64[ns]")
    n_30m = len(closes_30m)

    avg_gain_arr = np.zeros(n_30m)
    avg_loss_arr = np.zeros(n_30m)
    deltas = np.diff(closes_30m)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    ag = np.mean(gains[:PERIOD])
    al = np.mean(losses[:PERIOD])
    avg_gain_arr[PERIOD] = ag
    avg_loss_arr[PERIOD] = al
    for i in range(PERIOD, len(gains)):
        ag = (ag * (PERIOD - 1) + gains[i]) / PERIOD
        al = (al * (PERIOD - 1) + losses[i]) / PERIOD
        avg_gain_arr[i + 1] = ag
        avg_loss_arr[i + 1] = al

    ts_30m_map = {int(ts): idx for idx, ts in enumerate(ts_30m)}

    # Normalize 5m
    btc_5m_close = btc_5m["close"].copy()
    if bar_index.tz is not None and btc_5m_close.index.tz is None:
        btc_5m_close.index = btc_5m_close.index.tz_localize("UTC")
    btc_5m_arr = btc_5m_close.values
    btc_5m_idx_arr = np.array(btc_5m_close.index, dtype="datetime64[ns]")

    bar_idx_arr = np.array(bar_index, dtype="datetime64[ns]")
    n_bars = len(bar_index)
    rsi_full_aligned = btc_rsi_full.reindex(bar_index, method="ffill")

    # Run intra-bar detection and collect details
    intrabar_short_bars = []
    intrabar_long_bars = []

    # Track category of each firing
    only_ib = 0  # fires intra-bar but NOT bar-close
    also_barclose = 0  # fires intra-bar AND bar-close (duplicate)

    for k in range(1, n_bars - 1):
        bar_open_ts = bar_idx_arr[k]
        bar_close_ts = bar_idx_arr[k + 1]
        mask = (btc_5m_idx_arr >= bar_open_ts) & (btc_5m_idx_arr < bar_close_ts)
        if not np.any(mask):
            continue
        idxs = np.where(mask)[0]

        prev_bar_ts = int(bar_idx_arr[k - 1])
        state_idx = ts_30m_map.get(prev_bar_ts)
        if state_idx is None:
            continue
        ag_prev = avg_gain_arr[state_idx]
        al_prev = avg_loss_arr[state_idx]
        if ag_prev == 0.0 and al_prev == 0.0:
            continue

        close_prev_30m = closes_30m[state_idx]
        if np.isnan(close_prev_30m):
            continue

        prev_rsi_hyp = float(rsi_full_aligned.iloc[k - 1])
        if np.isnan(prev_rsi_hyp):
            continue

        fired_short = False
        fired_long = False
        tick_rsis = [prev_rsi_hyp]

        for i in idxs:
            tick_price = btc_5m_arr[i]
            delta = tick_price - close_prev_30m
            g = delta if delta > 0 else 0.0
            lo = -delta if delta < 0 else 0.0
            ag_h = (ag_prev * (PERIOD - 1) + g) / PERIOD
            al_h = (al_prev * (PERIOD - 1) + lo) / PERIOD
            cur_rsi_hyp = 100.0 if al_h < 1e-10 else 100.0 - 100.0 / (1.0 + ag_h / al_h)
            tick_rsis.append(cur_rsi_hyp)

            if not fired_short and prev_rsi_hyp >= CROSS_SHORT_LEVEL and cur_rsi_hyp < CROSS_SHORT_LEVEL:
                fired_short = True
            if not fired_long and prev_rsi_hyp <= CROSS_LONG_LEVEL and cur_rsi_hyp > CROSS_LONG_LEVEL:
                fired_long = True

            prev_rsi_hyp = cur_rsi_hyp

        if fired_short:
            intrabar_short_bars.append(bar_index[k])
            if not bar_close_short.iloc[k]:
                only_ib += 1
            else:
                also_barclose += 1

    print(f"\nIntra-bar short fires: {len(intrabar_short_bars)} total")
    print(f"  New (not bar-close): {only_ib}")
    print(f"  Dup (also bar-close): {also_barclose}")

    # Show bar-close RSI values around the "new" intra-bar fires to understand why they fire
    print(f"\nFirst 30 NEW intra-bar short bars:")
    new_ib = [b for b in intrabar_short_bars if not bar_close_short[b]]
    for ts in new_ib[:30]:
        k = bar_index.get_loc(ts)
        rsi_k_minus1 = rsi_aligned.iloc[k - 1] if k > 0 else float("nan")
        rsi_k = rsi_aligned.iloc[k]
        print(f"  {ts}  rsi[k-1]={rsi_k_minus1:.4f}  rsi[k]={rsi_k:.4f}")


asyncio.run(main())
