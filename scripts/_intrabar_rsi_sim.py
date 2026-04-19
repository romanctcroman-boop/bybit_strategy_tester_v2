"""
Simulate TradingView's calc_on_every_tick=True for RSI(14) on 30m bars.
For each 30m signal bar, replace the last bar's close with each 5m bar close
and recompute RSI to see if it crosses the level intra-bar.

This directly replicates TV's tick-level RSI recalculation.
"""

import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from backend.core.indicators import calculate_rsi as wilder_rsi

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
ETH_CACHE = r"d:\bybit_strategy_tester_v2\data\eth_30m_cache.csv"


def load_btc():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT open_time, open_price, high_price, low_price, close_price FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='30' ORDER BY open_time"
    ).fetchall()
    conn.close()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df.set_index("ts")


def load_eth():
    df = pd.read_csv(ETH_CACHE, index_col=0, parse_dates=True)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def load_btc_5m():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT open_time, close_price FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='5' ORDER BY open_time"
    ).fetchall()
    conn.close()
    df = pd.DataFrame(rows, columns=["ts", "close"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df.set_index("ts")


print("Loading data...")
btc = load_btc()
eth = load_eth()
btc5m = load_btc_5m()
print(f"BTC 30m: {len(btc)} bars | BTC 5m: {len(btc5m)} bars | ETH 30m: {len(eth)} bars")

PERIOD = 14
# Compute full-series RSI on 30m (used for context)
rsi30 = pd.Series(wilder_rsi(btc["close"].values, PERIOD), index=btc.index)


def sim_intrabar_rsi(sig_bar: pd.Timestamp, level: float, direction: str, n_context: int = 30):
    """
    For the 30m bar at sig_bar, compute what RSI would have been at each 5m tick
    within that bar (using the 5m close as a proxy for the partial bar close).

    Returns: list of (5m_timestamp, partial_close, partial_rsi)
    """
    # Get the N bars BEFORE sig_bar (the history, using bar closes up to T-1)
    bar_idx = btc.index.searchsorted(sig_bar)
    if bar_idx < PERIOD + 1:
        return []

    # We use all 30m bars up to (not including) sig_bar for the RSI history
    history_closes = btc["close"].values[:bar_idx]  # all bars up to T-1

    # The 5m bars within the 30m bar: [sig_bar, sig_bar+5m, ..., sig_bar+25m]
    results = []
    for offset in range(6):
        t5 = sig_bar + pd.Timedelta(minutes=5 * offset)
        if t5 not in btc5m.index:
            continue
        partial_close = float(btc5m.loc[t5, "close"])

        # Build the close series: history + partial bar
        extended = np.append(history_closes, partial_close)
        rsi_arr = wilder_rsi(extended, PERIOD)
        partial_rsi = float(rsi_arr[-1])
        results.append((t5, partial_close, partial_rsi))

    return results


# ── Anomaly cases ─────────────────────────────────────────────────────────────
anomalies = [
    ("2025-02-12 10:00", "2025-02-12 09:30", "short", 52.0),
    ("2025-02-19 16:00", "2025-02-19 15:30", "short", 52.0),
    ("2025-03-28 18:00", "2025-03-28 17:30", "long", 24.0),
    ("2025-04-19 21:00", "2025-04-19 20:30", "short", 52.0),
    ("2025-06-14 01:30", "2025-06-14 01:00", "short", 52.0),
    ("2025-07-25 05:00", "2025-07-25 04:30", "long", 24.0),
]

print()
print("=" * 80)
print("INTRA-BAR RSI SIMULATION (TV calc_on_every_tick proxy)")
print("Using BTC 5m closes as partial-bar price proxy for RSI(14,30m)")
print("=" * 80)

for tv_entry_str, sig_bar_str, direction, level in anomalies:
    sig_bar = pd.Timestamp(sig_bar_str)
    prev_bar = sig_bar - pd.Timedelta(minutes=30)

    r_prev = float(rsi30.get(prev_bar, float("nan")))
    r_t = float(rsi30.get(sig_bar, float("nan")))

    print()
    print(f"TV entry: {tv_entry_str} UTC  (signal bar: {sig_bar_str})  dir={direction}  level={level}")
    print(f"  30m RSI: T-1={r_prev:.4f}  T(bar-close)={r_t:.4f}")

    if direction == "short":
        standard_cross = r_prev >= level and r_t < level
        print(f"  Bar-close crossunder? {standard_cross}  (need T-1>={level} AND T<{level})")
    else:
        standard_cross = r_prev <= level and r_t > level
        print(f"  Bar-close crossover? {standard_cross}  (need T-1<={level} AND T>{level})")

    print("  Intra-bar 30m RSI (using each 5m bar as partial close):")
    ticks = sim_intrabar_rsi(sig_bar, level, direction)

    crossed = False
    first_cross_time = None
    for t5, price, rsi_partial in ticks:
        if direction == "short":
            below = rsi_partial < level
        else:
            below = rsi_partial > level  # for long, "crossing" = going above level

        marker = ""
        if direction == "short" and rsi_partial < level:
            marker = " <<< CROSSED BELOW LEVEL"
            if not crossed:
                crossed = True
                first_cross_time = t5
        elif direction == "long" and rsi_partial > level:
            marker = " <<< CROSSED ABOVE LEVEL"
            if not crossed:
                crossed = True
                first_cross_time = t5

        print(f"    {t5}  BTC5m={price:.2f}  RSI_partial={rsi_partial:.4f}{marker}")

    if crossed:
        print(f"  ✅ INTRA-BAR CROSS CONFIRMED at {first_cross_time} → TV would fire!")
    else:
        print("  ❌ No intra-bar cross found with 5m proxy")

    # For LONG anomalies, also check T-1 bar intra-bar (signal might have fired at T-1 tick-level)
    if direction == "long":
        print(f"  [Checking T-1 bar ({prev_bar}) intra-bar — did cross happen there?]")
        ticks_prev = sim_intrabar_rsi(prev_bar, level, direction)
        prev_prev_bar = prev_bar - pd.Timedelta(minutes=30)
        r_pp = float(rsi30.get(prev_prev_bar, float("nan")))
        print(f"    T-2 bar-close RSI: {r_pp:.4f}")
        for t5, price, rsi_partial in ticks_prev:
            marker = " <<< CROSSED ABOVE" if rsi_partial > level else ""
            print(f"    {t5}  BTC5m={price:.2f}  RSI_partial={rsi_partial:.4f}{marker}")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()
print("If INTRA-BAR CROSS CONFIRMED for ALL anomalies → TV uses calc_on_every_tick=True")
print("with 30m RSI recomputed using partial bar close at every tick.")
print()
print("Fix in indicator_handlers.py:")
print("  Instead of: cross_short = (rsi_prev >= level) & (rsi < level)")
print("  Add:        cross_short |= intrabar_cross_short  (using bar LOW price as proxy)")
print("  OR:         Implement calc-on-every-tick using resampled high-frequency data")
