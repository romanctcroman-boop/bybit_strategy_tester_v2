"""Quick RSI crossunder analysis at 2026-02-01 10:00"""

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()

import numpy as np
import pandas as pd

from backend.backtesting.service import BacktestService
from backend.core.indicators.momentum import calculate_rsi


async def main():
    svc = BacktestService()
    btc_w = await svc._fetch_historical_data(
        "BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")
    )
    btc_m = await svc._fetch_historical_data(
        "BTCUSDT", "30", pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2026-02-25", tz="UTC")
    )
    btc = pd.concat([btc_w, btc_m]).sort_index()
    if btc.index.tz is None:
        btc.index = btc.index.tz_localize("UTC")
    btc = btc[~btc.index.duplicated(keep="last")]

    rsi_arr = calculate_rsi(btc["close"].values, 14)
    rsi = pd.Series(rsi_arr, index=btc.index)

    t = pd.Timestamp("2026-02-01 10:00", tz="UTC")
    loc = rsi.index.get_loc(t)

    print("--- 10 bars around 2026-02-01 10:00 ---")
    print(f"{'Time':22s}  {'BTC close':10s}  {'RSI':8s}  {'crossunder52':12s}")
    for i in range(loc - 5, loc + 5):
        ts = rsi.index[i]
        r = rsi.iloc[i]
        rp = rsi.iloc[i - 1] if i > 0 else float("nan")
        c = btc["close"].iloc[i]
        cross = bool(rp >= 52 and r < 52)
        marker = "  <<< TV signal bar" if i == loc else ""
        print(f"{str(ts)[:22]:22s}  {c:10.2f}  {r:8.4f}  {str(cross):12s}{marker}")

    rsi_prev = rsi.shift(1)
    crossunder_52 = (rsi_prev >= 52) & (rsi < 52)
    short_range = (rsi >= 50) & (rsi <= 70)
    signal_std = crossunder_52 & short_range

    print(f"\nTotal crossunder(52):              {crossunder_52.sum()}")
    print(f"Total crossunder(52) & [50..70]:   {signal_std.sum()}")

    rp_t = rsi.iloc[loc - 1]
    rc_t = rsi.iloc[loc]

    print(f"\nAt 2026-02-01 10:00:")
    print(f"  prev RSI = {rp_t:.6f}  (>= 52? {rp_t >= 52})")
    print(f"  curr RSI = {rc_t:.6f}  (< 52? {rc_t < 52})")
    print(f"  Standard crossunder(52): {bool(rp_t >= 52 and rc_t < 52)}")
    print(f"  Diff to 52: prev is {52 - rp_t:.6f} BELOW 52")

    # How many consecutive bars before this one were also < 52?
    consec = 0
    for i in range(loc - 1, max(0, loc - 20), -1):
        if rsi.iloc[i] < 52:
            consec += 1
        else:
            break
    print(f"  Consecutive bars below 52 before this bar: {consec}")

    # Show wider context: last time RSI was >= 52 before this bar
    above_52_before = rsi.iloc[:loc][rsi.iloc[:loc] >= 52]
    if len(above_52_before):
        last_above = above_52_before.index[-1]
        bars_since = loc - rsi.index.get_loc(last_above)
        print(f"  Last bar with RSI >= 52 before this: {str(last_above)[:16]} ({bars_since} bars ago)")
        print(f"  RSI at last-above-52 bar: {above_52_before.iloc[-1]:.4f}")

    # Key question: maybe TV uses a looser crossunder —
    # "ta.crossunder(rsi, 52)" in Pine Script means:
    #   rsi[1] >= 52 and rsi < 52  (standard, what we implement)
    # OR does TV actually evaluate on every tick (not bar close)?
    # If BTC had a tick where RSI was >= 52 during the bar at 09:30 but
    # the bar CLOSED at 51.97, then bar-close RSI = 51.97 < 52
    # but the bar at 09:30 also closed at 51.97 — so no intra-bar issue here.

    print("\n--- Summary ---")
    print(f"The TV signal at 2026-02-01 10:00 has prev_rsi={rp_t:.4f}")
    print(f"This is {52 - rp_t:.4f} points BELOW 52 threshold.")
    print(f"Standard crossunder(52) = False.")
    print(f"TV somehow fires here despite prev_rsi < 52.")
    print(f"Possible explanations:")
    print(f"  1. TV uses a different RSI value for the prev bar (data diff)")
    print(f"     But we proved data is identical => RSI is identical")
    print(f"  2. TV script uses a looser condition:")
    print(f"     e.g. 'rsi < 52' (no crossunder, just level check)")
    print(f"  3. TV applies 'short_range [50..70]' as the only condition")
    print(f"     (RSI just needs to be in [50..70], no crossunder required)")
    print(f"  4. Repainting: TV show signal 1 bar earlier/later in list")


asyncio.run(main())
