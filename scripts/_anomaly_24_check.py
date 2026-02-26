"""
Verify anomalies #2 and #4 using BTC 5m intra-bar RSI simulation.
These have rsi_prev < 52 — meaning TV may have fired on an intra-bar
crossunder WITHIN bar T-1 (the 15:00 and 20:00 bars respectively).
"""

import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from backend.core.indicators import calculate_rsi as wilder_rsi

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"


def load_btc_30m():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT open_time, open_price, high_price, low_price, close_price FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='30' ORDER BY open_time"
    ).fetchall()
    conn.close()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df.set_index("ts")


def load_btc_5m():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT open_time, open_price, high_price, low_price, close_price FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='5' ORDER BY open_time"
    ).fetchall()
    conn.close()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df.set_index("ts")


def wilder_rsi_states(closes, period=14):
    """Build Wilder RSI state arrays (ag, al) for all bars."""
    n = len(closes)
    ag_arr = np.zeros(n)
    al_arr = np.zeros(n)

    # Warmup
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    ag = np.mean(gains[:period])
    al = np.mean(losses[:period])
    ag_arr[period] = ag
    al_arr[period] = al

    for t in range(period + 1, n):
        d = closes[t] - closes[t - 1]
        ag = (ag * (period - 1) + max(d, 0)) / period
        al = (al * (period - 1) + max(-d, 0)) / period
        ag_arr[t] = ag
        al_arr[t] = al

    return ag_arr, al_arr


def rsi_one_step(ag_prev, al_prev, close_prev, close_new, period=14):
    """Compute RSI using Wilder's incremental formula for one more bar."""
    d = close_new - close_prev
    ag = (ag_prev * (period - 1) + max(d, 0)) / period
    al = (al_prev * (period - 1) + max(-d, 0)) / period
    if al == 0:
        return 100.0
    return 100 - 100 / (1 + ag / al)


def _rsi_below_52(rsi_val: float) -> bool:
    """Check if RSI is below 52 (used for intra-bar cross detection)."""
    return rsi_val < 52


def prev_rsi_prev_close_check(rsi_val: float) -> bool:
    return _rsi_below_52(rsi_val)


btc_30m = load_btc_30m()
btc_5m = load_btc_5m()

P = 14
closes_30m = btc_30m["close"].values
idx_30m = btc_30m.index
ag_arr, al_arr = wilder_rsi_states(closes_30m, P)

print("Verifying anomaly #2: TV entry 2025-02-19 16:00 UTC, signal bar 2025-02-19 15:30")
print("  BUT rsi_prev (at 15:00) = 51.807 < 52 — so the crossunder must be intra-bar at 15:00")
print()

# The signal bar is 15:30, meaning TV fires at 15:30.
# But prev RSI (= RSI at 15:00 bar close) is 51.807 < 52.
# So TV must have seen RSI cross 52 INTRA-BAR during the 15:30 bar.
# We need to check if the bar's HIGH (intra-bar) pushed RSI above 52.

# Find position of 15:00 and 15:30 bars
for bar_ts_str, prev_bar_str, label in [
    ("2025-02-19 15:30", "2025-02-19 15:00", "anomaly #2"),
    ("2025-04-19 20:30", "2025-04-19 20:00", "anomaly #4"),
]:
    bar_ts = pd.Timestamp(bar_ts_str)
    prev_ts = pd.Timestamp(prev_bar_str)

    if bar_ts not in idx_30m:
        print(f"{bar_ts_str}: NOT IN INDEX")
        continue

    pos = idx_30m.get_loc(bar_ts)
    prev_pos = idx_30m.get_loc(prev_ts)

    rsi_prev_close = 100 - 100 / (1 + ag_arr[prev_pos] / al_arr[prev_pos]) if al_arr[prev_pos] > 0 else 100
    rsi_bar_close = 100 - 100 / (1 + ag_arr[pos] / al_arr[pos]) if al_arr[pos] > 0 else 100

    print(f"\n{'=' * 60}")
    print(f"{label}: signal bar = {bar_ts_str}")
    print(f"  RSI at prev bar close ({prev_bar_str}): {rsi_prev_close:.4f}")
    print(f"  RSI at bar close ({bar_ts_str}): {rsi_bar_close:.4f}")
    print()

    # Simulate RSI with HIGH of the signal bar (would this push it above 52?)
    ag_before = ag_arr[pos - 1]  # state before bar T
    al_before = al_arr[pos - 1]
    close_before = closes_30m[pos - 1]

    high_t = float(btc_30m["high"].iloc[pos])
    low_t = float(btc_30m["low"].iloc[pos])
    close_t = float(btc_30m["close"].iloc[pos])

    rsi_if_high = rsi_one_step(ag_before, al_before, close_before, high_t, P)
    rsi_if_low = rsi_one_step(ag_before, al_before, close_before, low_t, P)

    print(
        f"  Bar {bar_ts_str}: open={btc_30m['open'].iloc[pos]:.2f} high={high_t:.2f} low={low_t:.2f} close={close_t:.2f}"
    )
    print(f"  RSI if bar closed at HIGH: {rsi_if_high:.4f}")
    print(f"  RSI if bar closed at LOW:  {rsi_if_low:.4f}")
    print(f"  RSI if bar closed at CLOSE: {rsi_bar_close:.4f}")
    print()

    # Now check with the 5m bars within this 30m bar
    bar_5m = btc_5m[(btc_5m.index >= bar_ts) & (btc_5m.index < bar_ts + pd.Timedelta("30min"))]
    print(f"  5m bars within signal bar {bar_ts_str}:")
    prev_close = close_before
    prev_ag = ag_before
    prev_al = al_before
    for i, (ts5, row5) in enumerate(bar_5m.iterrows()):
        c5 = float(row5["close"])
        rsi5 = rsi_one_step(prev_ag, prev_al, prev_close, c5, P)
        crossed = " <<< INTRA-BAR CROSS" if _rsi_below_52(rsi5) else ""
        print(f"    [{i + 1}] {ts5} close={c5:.2f} RSI_partial={rsi5:.4f}{crossed}")


# Redo with proper check
for bar_ts_str, prev_bar_str, label in [
    ("2025-02-19 15:30", "2025-02-19 15:00", "anomaly #2"),
    ("2025-04-19 20:30", "2025-04-19 20:00", "anomaly #4"),
]:
    bar_ts = pd.Timestamp(bar_ts_str)

    if bar_ts not in idx_30m:
        continue

    pos = idx_30m.get_loc(bar_ts)

    ag_before = ag_arr[pos - 1]
    al_before = al_arr[pos - 1]
    close_before = closes_30m[pos - 1]

    rsi_prev = 100 - 100 / (1 + ag_arr[pos - 1] / al_arr[pos - 1]) if al_arr[pos - 1] > 0 else 100

    print(f"\n{'=' * 60}")
    print(f"{label}: rsi_prev (RSI at T-1 close) = {rsi_prev:.4f}")
    print("  Q: Did RSI cross ABOVE 52 intra-bar at T, then end up below 52?")
    print("  => This would mean: rsi_prev < 52, RSI peaks > 52 intra-bar, close < 52")
    print()

    bar_5m = btc_5m[(btc_5m.index >= bar_ts) & (btc_5m.index < bar_ts + pd.Timedelta("30min"))]

    prev_close = close_before
    prev_ag = ag_before
    prev_al = al_before
    prev_rsi = rsi_prev

    seen_crossover = False
    seen_crossunder = False

    for i, (ts5, row5) in enumerate(bar_5m.iterrows()):
        c5 = float(row5["close"])
        rsi5 = rsi_one_step(prev_ag, prev_al, prev_close, c5, P)
        crossed_above = prev_rsi < 52 and rsi5 >= 52
        crossed_below = prev_rsi >= 52 and rsi5 < 52
        note = ""
        if crossed_above:
            note = " <<< CROSSES ABOVE 52"
            seen_crossover = True
        if crossed_below:
            note = " <<< CROSSES BELOW 52"
            seen_crossunder = True
        print(f"  [{i + 1}] {ts5} c={c5:.2f} RSI={rsi5:.4f} (prev={prev_rsi:.4f}){note}")
        prev_rsi = rsi5
        prev_close = close_before  # Keep using T-1 close as base!

    print()
    if seen_crossover and seen_crossunder:
        print("  \u2705 CONFIRMED: RSI crossed above 52 then back below within the bar!")
    elif seen_crossover:
        print("  RSI crossed above 52 but didn't come back below")
    elif seen_crossunder:
        print("  RSI crossed below 52 (standard crossunder)")
    else:
        print("  \u274c No crossing detected \u2014 TV behavior unexplained by 5m data")
