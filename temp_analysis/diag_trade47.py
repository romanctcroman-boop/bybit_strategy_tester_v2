"""
Diagnose trade #47 intrabar TP issue.
TV: short entry=2025-04-13 22:30 exit=2025-04-13 22:30
Ours: short entry=2025-04-13 22:30 exit=2025-04-14 00:00

Steps:
1. Get kline data around that trade
2. Find the signal bar and entry bar
3. Calculate TP price
4. Check if high/low of each bar triggers TP
"""

import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

# ─────────── Load kline data ───────────
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
conn = sqlite3.connect(DB_PATH)

# Entry time in UTC: 2025-04-13 22:30 UTC+3 → 2025-04-13 19:30 UTC
entry_utc = datetime(2025, 4, 13, 19, 30, tzinfo=timezone.utc)
start_utc = entry_utc - timedelta(hours=3)
end_utc = entry_utc + timedelta(hours=4)

query = """
    SELECT timestamp, open, high, low, close 
    FROM klines 
    WHERE symbol='ETHUSDT' AND interval='30' 
    AND timestamp >= ? AND timestamp <= ?
    ORDER BY timestamp
"""
df = pd.read_sql_query(
    query,
    conn,
    params=[
        int(start_utc.timestamp() * 1000),
        int(end_utc.timestamp() * 1000),
    ],
)
conn.close()

df["dt"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
df = df.set_index("dt")
print(f"Bars around trade #47:")
print(f"{'Time (UTC)':25} {'Open':10} {'High':10} {'Low':10} {'Close':10}")
for ts, row in df.iterrows():
    print(f"{str(ts):25} {row['open']:10.4f} {row['high']:10.4f} {row['low']:10.4f} {row['close']:10.4f}")

# ─────────── Calculate TP ───────────
# Short TP = entry_price * (1 - take_profit)
# SL = entry_price * (1 + stop_loss)
# RSI strategy: TP=2.3%, SL=13.2%
take_profit = 0.023
stop_loss = 0.132

# Find the entry bar (first bar >= entry_utc)
entry_bar = df[df.index >= entry_utc].iloc[0]
entry_price = entry_bar["open"]
tp_price = entry_price * (1.0 - take_profit)
sl_price = entry_price * (1.0 + stop_loss)

print(f"\nShort entry price: {entry_price:.4f}")
print(f"TP price: {tp_price:.4f} (short TP = {take_profit * 100}% below entry)")
print(f"SL price: {sl_price:.4f} (short SL = {stop_loss * 100}% above entry)")

# ─────────── Check which bar hits TP ───────────
print(f"\nBar-by-bar TP/SL check (starting from entry bar):")
entry_bar_ts = entry_bar.name
found_exit = False
for ts, row in df[df.index >= entry_bar_ts].iterrows():
    tp_hit = row["low"] <= tp_price
    sl_hit = row["high"] >= sl_price
    marker = ""
    if tp_hit or sl_hit:
        marker = " ← TP HIT" if tp_hit else " ← SL HIT"
        if tp_hit and sl_hit:
            marker = " ← BOTH HIT"
    print(
        f"  {str(ts):25} open={row['open']:9.4f} high={row['high']:9.4f} low={row['low']:9.4f} close={row['close']:9.4f}{marker}"
    )
    if (tp_hit or sl_hit) and not found_exit:
        found_exit = True
        print(f"  ↑ FIRST EXIT BAR")

# ─────────── What does the engine do? ───────────
print(f"\nEngine logic analysis:")
print(f"Signal bar (short_entries[i]=1): The bar BEFORE entry bar")

# Find signal bar
signal_bar_ts = df[df.index < entry_bar_ts].iloc[-1].name
signal_bar = df.loc[signal_bar_ts]
print(f"Signal bar time: {signal_bar_ts}")
print(f"Entry bar time:  {entry_bar_ts}")

# The engine enters at open[i+1] where i is the signal bar index
# Entry price = open of entry bar
print(f"Entry at open of next bar = {entry_price:.4f}")

# Now check: what is entry_exec_idx and exit_idx?
# entry_idxs[trade] = i (signal bar index)
# entry_exec_idx = i + 1 (entry bar index)  → entry_time = timestamps[i+1] = entry_bar_ts
# exit_idx = j (bar where TP/SL hit)  → exit_time = timestamps[j]

# So if TP hits on entry bar (j = i+1), then exit_time = timestamps[i+1] = same as entry_time ✓
# If TP hits on NEXT bar (j = i+2), then exit_time = timestamps[i+2] = one bar later ✗
print(f"\nExpected behavior:")
print(f"  If TP hits on entry bar {entry_bar_ts}: exit_time = {entry_bar_ts} (same as entry = TV parity ✓)")
print(f"  If TP hits on next bar: exit_time = 1 bar later (what we're seeing ✗)")

# Entry bar check
eb_tp_hit = entry_bar["low"] <= tp_price
eb_sl_hit = entry_bar["high"] >= sl_price
print(f"\nTP hit on entry bar? {eb_tp_hit} (low={entry_bar['low']:.4f} vs tp={tp_price:.4f})")
print(f"SL hit on entry bar? {eb_sl_hit} (high={entry_bar['high']:.4f} vs sl={sl_price:.4f})")

print(f"\n⚠️  If TP does NOT hit on entry bar but hits on next bar → engine exits 1 bar later")
print(f"   TV may be checking TP within SAME bar as signal (before actual open price?)")
print(f"   Or TV may be treating the signal as entry at current bar's close, not next open")
