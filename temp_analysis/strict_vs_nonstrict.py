"""
Deep signal trace: run _handle_macd directly (same as engine does)
and show every signal bar with MACD values. Compare with TV Pine Script.

TV Pine Script (with our params):
  longSignal  = crossDownZero AND crossDownSignal  (macd crosses UNDER both zero and signal)
  shortSignal = crossUpZero   AND crossUpSignal    (macd crosses OVER  both zero and signal)
  confirmedBar = barstate.isconfirmed  (only on bar close — same as our EoB logic)

TV crossover definition (ta.crossover(a,b)):
  crossover(a,b)  = a[1] < b[1] and a > b   (strict less/greater on prev)
  crossunder(a,b) = a[1] > b[1] and a < b   (strict greater/less  on prev)

Our crossover in _handle_macd:
  cross_long  = (macd_prev <= signal_prev) & (macd_line > signal_line)   <- uses <=, not strict <
  cross_short = (macd_prev >= signal_prev) & (macd_line < signal_line)   <- uses >=, not strict >

Potential bug: TV uses STRICT prev comparison (a[1] < b[1])
               we use NON-STRICT (macd_prev <= signal_prev)
               This can fire an extra bar when they were exactly equal on prev bar.
"""

import os
import sys

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
os.chdir(r"d:\bybit_strategy_tester_v2")

import sqlite3

import pandas as pd

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
SYMBOL = "ETHUSDT"
INTERVAL = "30"
START = "2025-04-01"
END = "2025-04-30"

warmup_start_ms = int(pd.Timestamp("2025-02-14", tz="UTC").timestamp() * 1000)
end_ms = int(pd.Timestamp(END, tz="UTC").timestamp() * 1000) + 86400000

con = sqlite3.connect(DB_PATH)
df = pd.read_sql(
    "SELECT open_time, open_price AS open, high_price AS high, low_price AS low, "
    "close_price AS close, volume FROM bybit_kline_audit "
    "WHERE symbol=? AND interval=? AND open_time >= ? AND open_time <= ? ORDER BY open_time",
    con,
    params=(SYMBOL, INTERVAL, warmup_start_ms, end_ms),
)
con.close()
df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df = df.set_index("timestamp").sort_index()
df = df.astype({"open": float, "high": float, "low": float, "close": float})
close = df["close"]
print(f"Loaded {len(df)} bars  {df.index[0]} → {df.index[-1]}\n")

FAST, SLOW, SIG = 14, 15, 9

fast_ema = close.ewm(span=FAST, adjust=False).mean()
slow_ema = close.ewm(span=SLOW, adjust=False).mean()
macd_line = fast_ema - slow_ema
signal_line = macd_line.ewm(span=SIG, adjust=False).mean()
macd_prev = macd_line.shift(1)
sig_prev = signal_line.shift(1)

# ── OUR current logic (non-strict <=, >=) ────────────────────────────────────
our_cross_dn = (macd_prev >= sig_prev) & (macd_line < signal_line)  # crossunder
our_cross_up = (macd_prev <= sig_prev) & (macd_line > signal_line)  # crossover
our_zero_dn = (macd_prev >= 0) & (macd_line < 0)
our_zero_up = (macd_prev <= 0) & (macd_line > 0)

# After opposite swap: long=crossDN, short=crossUP
our_long_raw = our_cross_dn & our_zero_dn
our_short_raw = our_cross_up & our_zero_up

# ── TV strict logic (strict <, >) ────────────────────────────────────────────
tv_cross_dn = (macd_prev > sig_prev) & (macd_line < signal_line)  # strict crossunder
tv_cross_up = (macd_prev < sig_prev) & (macd_line > signal_line)  # strict crossover
tv_zero_dn = (macd_prev > 0) & (macd_line < 0)
tv_zero_up = (macd_prev < 0) & (macd_line > 0)

tv_long_raw = tv_cross_dn & tv_zero_dn
tv_short_raw = tv_cross_up & tv_zero_up

# ── Trim to analysis period ───────────────────────────────────────────────────
cutoff = pd.Timestamp(START, tz="UTC")
mask = df.index >= cutoff

print("=" * 70)
print("Signals in April 2025 (memory OFF, no opposite swap applied to naming)")
print("=" * 70)
print(f"\n  OUR  (non-strict <= >=):  long={our_long_raw[mask].sum()}  short={our_short_raw[mask].sum()}")
print(f"  TV   (strict   <  >  ):  long={tv_long_raw[mask].sum()}   short={tv_short_raw[mask].sum()}")

# Check for bars where they differ
long_diff = our_long_raw[mask] != tv_long_raw[mask]
short_diff = our_short_raw[mask] != tv_short_raw[mask]
print(f"\n  Bars where LONG  signals differ: {long_diff.sum()}")
print(f"  Bars where SHORT signals differ: {short_diff.sum()}")

# Show diff bars
if long_diff.sum() > 0:
    print("\n  LONG diff bars:")
    for t in df.index[mask][long_diff.values]:
        m = macd_line.loc[t]
        mp = macd_prev.loc[t]
        s = signal_line.loc[t]
        sp = sig_prev.loc[t]
        z = 0
        zp = 0
        print(f"    {t.strftime('%Y-%m-%d %H:%M')}  macd_prev={mp:.6f} macd={m:.6f}  sig_prev={sp:.6f} sig={s:.6f}")
        print(f"      our_long={our_long_raw.loc[t]}  tv_long={tv_long_raw.loc[t]}")

if short_diff.sum() > 0:
    print("\n  SHORT diff bars:")
    for t in df.index[mask][short_diff.values]:
        m = macd_line.loc[t]
        mp = macd_prev.loc[t]
        s = signal_line.loc[t]
        sp = sig_prev.loc[t]
        print(f"    {t.strftime('%Y-%m-%d %H:%M')}  macd_prev={mp:.6f} macd={m:.6f}  sig_prev={sp:.6f} sig={s:.6f}")
        print(f"      our_short={our_short_raw.loc[t]}  tv_short={tv_short_raw.loc[t]}")

# ── Full signal list with MACD values ────────────────────────────────────────
print("\n" + "=" * 70)
print("OUR LONG signal bars (non-strict):")
for t in df.index[mask][our_long_raw[mask].values]:
    m = macd_line.loc[t]
    mp = macd_prev.loc[t]
    s = signal_line.loc[t]
    sp = sig_prev.loc[t]
    print(f"  {t.strftime('%Y-%m-%d %H:%M')}  macd: {mp:+.5f} → {m:+.5f}  sig: {sp:+.5f} → {s:+.5f}")

print("\nTV LONG signal bars (strict):")
for t in df.index[mask][tv_long_raw[mask].values]:
    m = macd_line.loc[t]
    mp = macd_prev.loc[t]
    s = signal_line.loc[t]
    sp = sig_prev.loc[t]
    print(f"  {t.strftime('%Y-%m-%d %H:%M')}  macd: {mp:+.5f} → {m:+.5f}  sig: {sp:+.5f} → {s:+.5f}")

print("\nOUR SHORT signal bars (non-strict):")
for t in df.index[mask][our_short_raw[mask].values]:
    m = macd_line.loc[t]
    mp = macd_prev.loc[t]
    s = signal_line.loc[t]
    sp = sig_prev.loc[t]
    print(f"  {t.strftime('%Y-%m-%d %H:%M')}  macd: {mp:+.5f} → {m:+.5f}  sig: {sp:+.5f} → {s:+.5f}")

print("\nTV SHORT signal bars (strict):")
for t in df.index[mask][tv_short_raw[mask].values]:
    m = macd_line.loc[t]
    mp = macd_prev.loc[t]
    s = signal_line.loc[t]
    sp = sig_prev.loc[t]
    print(f"  {t.strftime('%Y-%m-%d %H:%M')}  macd: {mp:+.5f} → {m:+.5f}  sig: {sp:+.5f} → {s:+.5f}")

# ── Also check zero_cross separately ─────────────────────────────────────────
print("\n" + "=" * 70)
print("Individual component check (April 2025):")
print(f"  our_cross_dn (signal line crossunder): {our_cross_dn[mask].sum()}")
print(f"  tv_cross_dn  (signal line crossunder): {tv_cross_dn[mask].sum()}")
print(f"  our_zero_dn  (zero crossunder):        {our_zero_dn[mask].sum()}")
print(f"  tv_zero_dn   (zero crossunder):        {tv_zero_dn[mask].sum()}")
print(f"  our_cross_up (signal line crossover):  {our_cross_up[mask].sum()}")
print(f"  tv_cross_up  (signal line crossover):  {tv_cross_up[mask].sum()}")
print(f"  our_zero_up  (zero crossover):         {our_zero_up[mask].sum()}")
print(f"  tv_zero_up   (zero crossover):         {tv_zero_up[mask].sum()}")
