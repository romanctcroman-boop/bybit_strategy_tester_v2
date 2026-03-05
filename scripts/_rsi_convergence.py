"""
Test RSI convergence: how does starting warmup at different dates affect
the RSI value at the root divergence bars?

If the RSI is sensitive to warmup start, we have a convergence problem.
If not, the divergence must come from data differences.
"""

import asyncio
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


def calculate_rsi_wilder(close_prices, period=14):
    n = len(close_prices)
    rsi = np.full(n, np.nan)
    deltas = np.diff(close_prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    if len(gains) < period:
        return rsi
    ag = np.mean(gains[:period])
    al = np.mean(losses[:period])
    rsi[period] = 100.0 if al < 1e-10 else 100.0 - 100.0 / (1.0 + ag / al)
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
        rsi[i + 1] = 100.0 if al < 1e-10 else 100.0 - 100.0 / (1.0 + ag / al)
    return rsi


async def main():
    svc = BacktestService()
    start_date = pd.Timestamp("2025-01-01", tz="UTC")
    end_date = pd.Timestamp("2026-02-24", tz="UTC")

    # Load BTC 30m with different warmup starts
    warmup_starts = [
        "2019-01-01",
        "2020-01-01",
        "2021-01-01",
        "2022-01-01",
        "2023-01-01",
        "2024-01-01",
        "2024-06-01",
        "2024-10-01",
    ]

    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", start_date, end_date)

    target_bars = [
        pd.Timestamp("2025-01-28 14:00:00"),  # Root #9 TV signal bar
        pd.Timestamp("2025-02-06 14:00:00"),  # Root #12 engine signal bar
    ]

    print("RSI at target bars with different warmup starts:")
    print(f"{'Warmup start':>15s}  {'warmup bars':>11s}  ", end="")
    for tb in target_bars:
        print(f"{'RSI@' + str(tb)[:16]:>25s}  ", end="")
    print()
    print("-" * 90)

    for ws in warmup_starts:
        ws_ts = pd.Timestamp(ws, tz="UTC")
        btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", ws_ts, start_date)
        btc_all = pd.concat([btc_warmup, btc_main]).sort_index()
        btc_all = btc_all[~btc_all.index.duplicated(keep="last")]

        close = btc_all["close"].values
        idx = btc_all.index
        if idx.tz is not None:
            idx = idx.tz_localize(None)

        rsi = calculate_rsi_wilder(close, 14)
        rsi_s = pd.Series(rsi, index=idx)

        n_warmup = len(btc_warmup) if btc_warmup is not None else 0
        print(f"{ws:>15s}  {n_warmup:>11d}  ", end="")

        for tb in target_bars:
            val = rsi_s.get(tb, np.nan)
            gap = val - 52 if not np.isnan(val) else np.nan
            print(f"  {val:10.6f} (gap={gap:+.4f})", end="")
        print()

    # Also test: what if BTC started from the very beginning on Bybit?
    # Bybit BTCUSDT linear started around 2020-03-30
    print("\n\nNOTE: Bybit BTCUSDT linear perpetual started ~2020-03-30.")
    print("TV likely starts from the first available bar.")
    print("Convergence difference between warmup starts tells us if this matters.")


asyncio.run(main())
