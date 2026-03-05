"""
Diagnose trade #47 (Short) and #105 (Long) intrabar TP timing issue.

TV:
  Trade #47: short entry=2025-04-13 22:30 exit=2025-04-13 22:30 (same bar!)
  Trade #105: long entry=2025-10-17 14:00 exit=2025-10-17 14:00 (same bar!)
Our engine:
  Trade #47: short entry=2025-04-13 22:30 exit=2025-04-14 00:00 (1 bar late)
  Trade #105: long entry=2025-10-17 14:00 exit=2025-10-17 15:00 (1 bar late)
"""

import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

# Load ETH 30m klines
df = pd.read_csv(r"d:\bybit_strategy_tester_v2\data\eth_30m_cache.csv")
df["time"] = pd.to_datetime(df["timestamp"])
df = df.set_index("time")

TP = 0.023  # 2.3%
SL = 0.132  # 13.2%


def analyze_trade(label, direction, entry_utc3_str, exit_utc3_str):
    """Analyze a trade by looking at the bars around it."""
    # Convert UTC+3 → UTC (subtract 3 hours)
    entry_dt_utc3 = pd.to_datetime(entry_utc3_str)
    exit_dt_utc3 = pd.to_datetime(exit_utc3_str)
    entry_utc = entry_dt_utc3 - timedelta(hours=3)
    exit_utc = exit_dt_utc3 - timedelta(hours=3)

    print(f"\n{'=' * 70}")
    print(f"Trade {label}: {direction}")
    print(f"  TV entry: {entry_utc3_str} (UTC+3) = {entry_utc} (UTC)")
    print(f"  TV exit:  {exit_utc3_str} (UTC+3) = {exit_utc} (UTC)")

    # Find bars around entry
    window_start = entry_utc - timedelta(hours=2)
    window_end = entry_utc + timedelta(hours=3)
    window = df[(df.index >= str(window_start)) & (df.index <= str(window_end))].copy()

    # Entry price is the OPEN of the entry bar
    entry_bar = df[df.index == str(entry_utc)]
    if entry_bar.empty:
        print(f"  ERROR: entry bar not found at {entry_utc}")
        return

    entry_price = entry_bar["open"].values[0]

    if direction == "short":
        tp_price = entry_price * (1.0 - TP)
        sl_price = entry_price * (1.0 + SL)
    else:
        tp_price = entry_price * (1.0 + TP)
        sl_price = entry_price * (1.0 - SL)

    print(f"  Entry price (open of entry bar): {entry_price:.4f}")
    print(f"  TP price: {tp_price:.4f}  SL price: {sl_price:.4f}")

    # Find signal bar = bar BEFORE entry bar
    bars_before = df[df.index < str(entry_utc)]
    if bars_before.empty:
        print("  ERROR: no bars before entry")
        return
    signal_bar_ts = bars_before.index[-1]
    signal_bar = df.loc[signal_bar_ts]
    print(f"  Signal bar: {signal_bar_ts} (one bar before entry)")
    print(
        f"  Signal bar: open={signal_bar['open']:.4f} high={signal_bar['high']:.4f} low={signal_bar['low']:.4f} close={signal_bar['close']:.4f}"
    )

    # Check if TP/SL hits on signal bar
    if direction == "short":
        sb_tp = signal_bar["low"] <= tp_price
        sb_sl = signal_bar["high"] >= sl_price
    else:
        sb_tp = signal_bar["high"] >= tp_price
        sb_sl = signal_bar["low"] <= sl_price
    print(f"  Signal bar TP hit? {sb_tp}  SL hit? {sb_sl}")

    # Show bars starting from entry
    print(f"\n  Bar-by-bar check from entry bar:")
    print(f"  {'Time (UTC)':22} {'Open':9} {'High':9} {'Low':9} {'Close':9} {'TP?':5} {'SL?':5}")

    first_exit_found = False
    for ts, row in df[df.index >= str(entry_utc)].head(6).iterrows():
        if direction == "short":
            tp_h = row["low"] <= tp_price
            sl_h = row["high"] >= sl_price
        else:
            tp_h = row["high"] >= tp_price
            sl_h = row["low"] <= sl_price
        marker = ""
        if (tp_h or sl_h) and not first_exit_found:
            marker = " ← FIRST EXIT"
            first_exit_found = True
        print(
            f"  {str(ts):22} {row['open']:9.4f} {row['high']:9.4f} {row['low']:9.4f} {row['close']:9.4f} {str(tp_h):5} {str(sl_h):5}{marker}"
        )

    # Key question: does the entry bar itself trigger TP?
    entry_bar_tp = None
    entry_bar_sl = None
    for ts, row in df[df.index == str(entry_utc)].iterrows():
        if direction == "short":
            entry_bar_tp = row["low"] <= tp_price
            entry_bar_sl = row["high"] >= sl_price
        else:
            entry_bar_tp = row["high"] >= tp_price
            entry_bar_sl = row["low"] <= sl_price

    print(f"\n  CONCLUSION:")
    print(f"  Entry bar TP hit? {entry_bar_tp}  SL hit? {entry_bar_sl}")
    if entry_bar_tp:
        print(f"  → TP SHOULD exit on SAME bar (TV parity: entry==exit timestamp)")
        print(f"  → Our engine: TP is checked at START of bar before entry, so entry bar exit IS correct")
        print(f"  → But we're seeing 1 bar late — bug must be in the entry logic!")
    else:
        print(f"  → TP does NOT hit on entry bar → exit on NEXT bar is correct")
        print(f"  → Check next bar...")

    # Check next bar
    next_bars = df[df.index > str(entry_utc)]
    if not next_bars.empty:
        next_ts = next_bars.index[0]
        next_bar = next_bars.iloc[0]
        if direction == "short":
            nb_tp = next_bar["low"] <= tp_price
            nb_sl = next_bar["high"] >= sl_price
        else:
            nb_tp = next_bar["high"] >= tp_price
            nb_sl = next_bar["low"] <= sl_price
        print(f"  Next bar ({next_ts}): TP hit? {nb_tp}  SL hit? {nb_sl}")


# Trade #47: Short, TV entry=2025-04-13 22:30 UTC+3, exit=same bar
analyze_trade("#47", "short", "2025-04-13 22:30", "2025-04-13 22:30")

# Trade #105: Long, TV entry=2025-10-17 14:00 UTC+3, exit=same bar
analyze_trade("#105", "long", "2025-10-17 14:00", "2025-10-17 14:00")
