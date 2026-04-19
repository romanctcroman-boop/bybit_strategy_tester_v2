"""
Check what BTC close price change caused the large RSI drop at Root #91's engine signal bar.
Also compute: what BTC close would be needed to keep RSI >= 52?
"""

import asyncio
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.service import BacktestService
from backend.core.indicators import calculate_rsi


async def main():
    svc = BacktestService()
    btc_warmup = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2020-01-01", tz="UTC"),
        pd.Timestamp("2025-01-01", tz="UTC"),
    )
    btc_main = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    btc_close = btc["close"].values
    btc_rsi = calculate_rsi(btc_close, period=14)
    btc_idx = btc.index

    # Root #91 engine signal bar: 2025-09-02 11:00
    # Need to find this timestamp in the BTC 30m index
    target_time = pd.Timestamp("2025-09-02 11:00:00")

    # Find closest bar
    btc_tz = btc.index
    if btc_tz.tz is not None:
        target_time = target_time.tz_localize(btc_tz.tz)

    # Search for the target
    loc = btc_idx.get_indexer([target_time], method="nearest")[0]

    print(f"Target: {target_time}")
    print(f"Found BTC bar: {btc_idx[loc]} (idx={loc})")
    print(f"BTC close[loc-1]: {btc_close[loc - 1]}")
    print(f"BTC close[loc]:   {btc_close[loc]}")
    print(f"Delta: {btc_close[loc] - btc_close[loc - 1]:.2f}")
    print(f"RSI[loc-1]: {btc_rsi[loc - 1]:.6f}")
    print(f"RSI[loc]:   {btc_rsi[loc]:.6f}")

    # Now compute: what's the Wilder state at bar loc-1?
    # We need avg_gain and avg_loss at bar loc-1
    # Then we can see what close value at bar loc would give RSI = 52
    deltas = np.diff(btc_close)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:14])
    avg_loss = np.mean(losses[:14])

    for i in range(14, loc - 1):  # Go up to bar loc-1's delta
        avg_gain = (avg_gain * 13 + gains[i]) / 14
        avg_loss = (avg_loss * 13 + losses[i]) / 14

    print(f"\nWilder state at bar {loc - 1}:")
    print(f"  avg_gain = {avg_gain:.6f}")
    print(f"  avg_loss = {avg_loss:.6f}")

    # Bar loc-1's delta is in deltas[loc-1] (since deltas[i] = close[i+1] - close[i])
    # Actually deltas = diff(close), so deltas[j] = close[j+1] - close[j]
    # For bar index loc, the delta is close[loc] - close[loc-1]
    delta_at_loc = btc_close[loc] - btc_close[loc - 1]
    gain_at_loc = max(delta_at_loc, 0)
    loss_at_loc = max(-delta_at_loc, 0)

    # After applying bar loc's delta:
    new_avg_gain = (avg_gain * 13 + gain_at_loc) / 14
    new_avg_loss = (avg_loss * 13 + loss_at_loc) / 14
    rs = new_avg_gain / new_avg_loss if new_avg_loss > 0 else float("inf")
    rsi_check = 100 - 100 / (1 + rs)
    print(f"\nAfter bar {loc}:")
    print(f"  delta = {delta_at_loc:.2f}")
    print(f"  new_avg_gain = {new_avg_gain:.6f}")
    print(f"  new_avg_loss = {new_avg_loss:.6f}")
    print(f"  RSI = {rsi_check:.6f} (should match {btc_rsi[loc]:.6f})")

    # What close price would give RSI = 52?
    # RSI = 100 - 100/(1+rs) = 52
    # 100/(1+rs) = 48
    # 1+rs = 100/48 = 2.0833...
    # rs = 1.0833
    # new_avg_gain / new_avg_loss = 1.0833
    #
    # If delta < 0 (loss):
    #   new_avg_gain = avg_gain * 13/14 + 0 = avg_gain * 13/14
    #   new_avg_loss = avg_loss * 13/14 + |delta|/14
    #   (avg_gain * 13/14) / (avg_loss * 13/14 + |delta|/14) = 100/48 - 1 = 52/48
    # Wait, let me redo:
    # RSI = 52 → rs = 52/(100-52) = 52/48 = 1.0833

    target_rs = 52 / 48

    # Case 1: delta < 0 (loss, RSI drops)
    # new_avg_gain = avg_gain * 13/14
    # new_avg_loss = (avg_loss * 13 + |delta|) / 14
    # target_rs = (avg_gain * 13/14) / ((avg_loss * 13 + |delta|) / 14)
    # target_rs = (avg_gain * 13) / (avg_loss * 13 + |delta|)
    # |delta| = (avg_gain * 13 / target_rs) - avg_loss * 13
    delta_needed = (avg_gain * 13 / target_rs) - avg_loss * 13
    close_for_52 = btc_close[loc - 1] - delta_needed

    print("\nTo get RSI exactly 52:")
    print(f"  Need |delta| = {delta_needed:.2f} (loss)")
    print(f"  Close needed = {close_for_52:.2f}")
    print(f"  Actual close = {btc_close[loc]:.2f}")
    print(f"  Difference = {btc_close[loc] - close_for_52:.2f}")

    # Check all 4 roots
    print("\n" + "=" * 80)
    print("ALL 4 ROOTS - What RSI shift would make TV skip the engine's signal:")

    roots_info = [
        ("Root #12", "2025-02-06 14:00:00", 0.1175),
        ("Root #85", "2025-08-16 01:00:00", 0.4519),
        ("Root #89", "2025-08-27 02:30:00", 0.1919),
        ("Root #91", "2025-09-02 11:00:00", 1.9361),
    ]

    for name, time_str, margin in roots_info:
        t = pd.Timestamp(time_str)
        if btc_tz.tz is not None:
            t = t.tz_localize(btc_tz.tz)
        loc_r = btc_idx.get_indexer([t], method="nearest")[0]

        print(f"\n{name} ({time_str}):")
        print(f"  Our RSI = {btc_rsi[loc_r]:.6f}, margin below 52 = {margin:.4f}")
        print(f"  BTC close[prev] = {btc_close[loc_r - 1]:.2f}")
        print(f"  BTC close[bar]  = {btc_close[loc_r]:.2f}")
        print(f"  Price change = {btc_close[loc_r] - btc_close[loc_r - 1]:.2f}")

        # How much would BTC close need to change to make RSI >= 52?
        # Recompute Wilder state at bar loc_r - 1
        ag = np.mean(gains[:14])
        al = np.mean(losses[:14])
        for j in range(14, loc_r - 1):
            ag = (ag * 13 + gains[j]) / 14
            al = (al * 13 + losses[j]) / 14

        # What close gives RSI = 52?
        trs = 52 / 48
        # If delta < 0:
        dn = (ag * 13 / trs) - al * 13
        cf52 = btc_close[loc_r - 1] - dn
        print(f"  Close needed for RSI=52: {cf52:.2f}")
        print(
            f"  Price diff from actual: {cf52 - btc_close[loc_r]:.2f} ({(cf52 - btc_close[loc_r]) / btc_close[loc_r] * 100:.4f}%)"
        )


asyncio.run(main())
