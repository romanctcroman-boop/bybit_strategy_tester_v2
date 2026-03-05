"""
Quick check: RSI sensitivity around root divergences.
For root #9, our RSI = 52.06 at bar 2025-01-28 14:00.
TV fires crossunder(rsi, 52) here, meaning TV's RSI <= 52.
Possible cause: tiny RSI precision difference due to Wilder smoothing accumulation.

Let's check what RSI value would be needed, and how sensitive it is
to small price changes.
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
    """Wilder RSI with full state tracking."""
    n = len(close_prices)
    rsi = np.full(n, np.nan)
    avg_gain = np.zeros(n)
    avg_loss = np.zeros(n)

    deltas = np.diff(close_prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    if len(gains) < period:
        return rsi, avg_gain, avg_loss

    ag = np.mean(gains[:period])
    al = np.mean(losses[:period])
    avg_gain[period] = ag
    avg_loss[period] = al
    rsi[period] = 100.0 if al < 1e-10 else 100.0 - 100.0 / (1.0 + ag / al)

    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
        avg_gain[i + 1] = ag
        avg_loss[i + 1] = al
        rsi[i + 1] = 100.0 if al < 1e-10 else 100.0 - 100.0 / (1.0 + ag / al)

    return rsi, avg_gain, avg_loss


async def main():
    svc = BacktestService()

    # Load BTC 30m with warmup
    btc_start = pd.Timestamp("2020-01-01", tz="UTC")
    start_date = pd.Timestamp("2025-01-01", tz="UTC")
    end_date = pd.Timestamp("2026-02-24", tz="UTC")

    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", btc_start, start_date)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", start_date, end_date)
    btc_candles = pd.concat([btc_warmup, btc_main]).sort_index()
    btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]

    close = btc_candles["close"].values
    idx = btc_candles.index
    if idx.tz is not None:
        idx_naive = idx.tz_localize(None)
    else:
        idx_naive = idx

    rsi, ag, al = calculate_rsi_wilder(close, 14)
    rsi_s = pd.Series(rsi, index=idx_naive)

    # Root #9: TV signal bar = 2025-01-28 14:00 UTC
    target_bar = pd.Timestamp("2025-01-28 14:00:00")
    bar_loc = idx_naive.get_loc(target_bar)

    print("=== ROOT #9 ANALYSIS ===")
    print(f"Bar: {target_bar}")
    print(f"BTC close at bar: {close[bar_loc]:.2f}")
    print(f"BTC close at bar-1: {close[bar_loc - 1]:.2f}")
    print(f"RSI at bar: {rsi[bar_loc]:.6f}")
    print(f"RSI at bar-1: {rsi[bar_loc - 1]:.6f}")
    print(
        f"Cross down 52? prev={rsi[bar_loc - 1]:.6f} >= 52 AND cur={rsi[bar_loc]:.6f} < 52: {rsi[bar_loc - 1] >= 52 and rsi[bar_loc] < 52}"
    )
    print(f"Gap to 52: {rsi[bar_loc] - 52:.6f}")
    print()

    # What close price at this bar would make RSI exactly 52?
    # RSI = 100 - 100/(1 + ag/al)
    # 52 = 100 - 100/(1 + ag/al) → 48 = 100/(1 + ag/al) → 1 + ag/al = 100/48
    # ag/al = 100/48 - 1 = 52/48
    # ag = (ag_prev * 13 + gain) / 14
    # al = (al_prev * 13 + loss) / 14
    # If close goes UP: gain = close - close_prev, loss = 0
    # If close goes DOWN: gain = 0, loss = close_prev - close

    ag_prev = ag[bar_loc - 1]
    al_prev = al[bar_loc - 1]
    close_prev = close[bar_loc - 1]

    # For RSI = 52:
    # ag_needed / al_needed = 52/48
    # Case 1: price goes down (gain=0, loss=L)
    # ag_needed = ag_prev * 13 / 14
    # al_needed = (al_prev * 13 + L) / 14
    # ag_needed / al_needed = (ag_prev * 13) / (al_prev * 13 + L) = 52/48
    # 48 * ag_prev * 13 = 52 * (al_prev * 13 + L)
    # L = (48 * ag_prev * 13 - 52 * al_prev * 13) / 52
    # L = 13 * (48 * ag_prev - 52 * al_prev) / 52
    ag_needed_ratio = 52.0 / 48.0  # ag/al for RSI=52

    L_for_52 = 13.0 * (48.0 * ag_prev - 52.0 * al_prev) / 52.0
    price_for_52_down = close_prev - L_for_52

    # Case 2: price goes up (gain=G, loss=0)
    # ag_needed = (ag_prev * 13 + G) / 14
    # al_needed = al_prev * 13 / 14
    # (ag_prev * 13 + G) / (al_prev * 13) = 52/48
    # G = 52/48 * al_prev * 13 - ag_prev * 13
    G_for_52 = 52.0 / 48.0 * al_prev * 13.0 - ag_prev * 13.0
    price_for_52_up = close_prev + G_for_52

    print(f"Wilder state at bar-1: ag={ag_prev:.6f}, al={al_prev:.6f}")
    print(f"Close at bar-1: {close_prev:.2f}")
    print(f"Actual close at bar: {close[bar_loc]:.2f}")
    print(f"Close needed for RSI=52.000 (if down): {price_for_52_down:.2f}")
    print(f"Close needed for RSI=52.000 (if up): {price_for_52_up:.2f}")
    print(f"Actual close - price_for_52: {close[bar_loc] - price_for_52_down:.2f} (sensitivity)")
    print()

    # How much would a BTC close difference of ±1 USDT change RSI?
    test_prices = [
        close[bar_loc] - 2,
        close[bar_loc] - 1,
        close[bar_loc] - 0.5,
        close[bar_loc],
        close[bar_loc] + 0.5,
        close[bar_loc] + 1,
    ]
    print("RSI sensitivity to BTC close price:")
    for p in test_prices:
        delta = p - close_prev
        g = max(delta, 0)
        lo = max(-delta, 0)
        ag_h = (ag_prev * 13 + g) / 14
        al_h = (al_prev * 13 + lo) / 14
        rsi_h = 100.0 if al_h < 1e-10 else 100.0 - 100.0 / (1.0 + ag_h / al_h)
        print(f"  Close={p:.2f} (delta={p - close[bar_loc]:+.2f})  RSI={rsi_h:.4f}  cross<52={rsi_h < 52}")

    # Check Wilder state accumulation depth
    print("\n=== WILDER STATE CONVERGENCE ===")
    print(f"Warmup bars: {bar_loc} (from index 0)")
    print(f"Bars since RSI period init: {bar_loc - 14}")

    # Now check ALL 6 roots' RSI values and distances from cross level
    print("\n=== ALL ROOT DIVERGENCES: RSI vs CROSS LEVEL ===")

    eth_candles = await svc._fetch_historical_data("ETHUSDT", "30", start_date, end_date)
    if eth_candles is None:
        print("ERROR: Could not load ETH candles")
        return

    # Align RSI to ETH index
    eth_idx = eth_candles.index
    if eth_idx.tz is not None:
        eth_idx_naive = eth_idx.tz_localize(None)
    else:
        eth_idx_naive = eth_idx
    rsi_aligned = rsi_s.reindex(eth_idx_naive, method="ffill")

    # Root bars from trade structure analysis
    # Engine entry → signal bar is entry - 30m (due to entry_on_next_bar_open)
    roots_info = [
        (9, "2025-01-28 18:00", "2025-01-28 14:30"),  # engine entry → TV entry
        (12, "2025-02-06 14:30", "2025-02-07 05:30"),
        (85, "2025-08-16 01:30", "2025-08-16 14:00"),
        (89, "2025-08-27 03:00", "2025-08-27 12:30"),
        (91, "2025-09-02 11:30", "2025-09-02 18:30"),
        (144, "2026-02-07 16:30", "2026-02-08 03:30"),
    ]

    for trade_num, eng_entry, tv_entry in roots_info:
        eng_signal = pd.Timestamp(eng_entry) - pd.Timedelta(minutes=30)
        tv_signal = pd.Timestamp(tv_entry) - pd.Timedelta(minutes=30)

        eng_rsi = rsi_aligned.get(eng_signal, np.nan)
        eng_rsi_prev = rsi_aligned.get(eng_signal - pd.Timedelta(minutes=30), np.nan)
        tv_rsi = rsi_aligned.get(tv_signal, np.nan)
        tv_rsi_prev = rsi_aligned.get(tv_signal - pd.Timedelta(minutes=30), np.nan)

        eng_cross = eng_rsi_prev >= 52 and eng_rsi < 52
        tv_bar_cross = tv_rsi_prev >= 52 and tv_rsi < 52

        print(f"\n  Trade #{trade_num}: Engine signal={eng_signal}, TV signal={tv_signal}")
        print(f"    Engine signal bar RSI: {eng_rsi:.4f} (prev: {eng_rsi_prev:.4f})  cross<52: {eng_cross}")
        print(f"    TV signal bar RSI:     {tv_rsi:.4f} (prev: {tv_rsi_prev:.4f})  bar-close cross<52: {tv_bar_cross}")
        print(f"    TV RSI gap to 52:      {tv_rsi - 52:+.4f}")

        # Check if engine fires BEFORE TV or AFTER
        if eng_signal < tv_signal:
            print(f"    → Engine fires {(tv_signal - eng_signal).total_seconds() / 1800:.0f} bars EARLIER")
        else:
            print(f"    → Engine fires {(eng_signal - tv_signal).total_seconds() / 1800:.0f} bars LATER")


asyncio.run(main())
