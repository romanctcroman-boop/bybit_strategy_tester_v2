"""
Check EMA seed differences between TV and pandas ewm.
TV ta.ema() = RMA-style seed vs pandas ewm(adjust=False).

TV ta.ema(source, length):
  Uses SMA of first `length` bars as seed, then EMA from there.
  i.e.: seed = sma(source, length) on first bar, then ema.

pandas ewm(span=n, adjust=False):
  Uses first value as seed (seed = source[0]), then EMA.

This can produce different MACD values in the warmup region,
which shifts WHERE crossovers land.

Let's compare both approaches on ETHUSDT 30m.
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
    "SELECT open_time, close_price AS close FROM bybit_kline_audit "
    "WHERE symbol=? AND interval=? AND open_time >= ? AND open_time <= ? ORDER BY open_time",
    con,
    params=(SYMBOL, INTERVAL, warmup_start_ms, end_ms),
)
con.close()
df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df = df.set_index("timestamp").sort_index()
close = df["close"].astype(float)

FAST, SLOW, SIG = 14, 15, 9


# ── pandas ewm (our current) ──────────────────────────────────────────────────
def ema_pandas(s, n):
    return s.ewm(span=n, adjust=False).mean()


macd_p = ema_pandas(close, FAST) - ema_pandas(close, SLOW)
sig_p = ema_pandas(macd_p, SIG)


# ── TV-style EMA: SMA seed for first `length` bars ───────────────────────────
def ema_tv(s, n):
    """Replicates ta.ema() in Pine Script: SMA of first n values as seed."""
    alpha = 2.0 / (n + 1)
    result = [float("nan")] * len(s)
    vals = s.values
    # First valid seed = SMA of first n values
    if len(vals) < n:
        return pd.Series(result, index=s.index)
    seed = float(sum(vals[:n])) / n
    result[n - 1] = seed
    for i in range(n, len(vals)):
        result[i] = alpha * vals[i] + (1 - alpha) * result[i - 1]
    return pd.Series(result, index=s.index)


fast_tv = ema_tv(close, FAST)
slow_tv = ema_tv(close, SLOW)
macd_tv = fast_tv - slow_tv
sig_tv = ema_tv(macd_tv.dropna(), SIG).reindex(macd_tv.index)

# ── Signals: pandas ──────────────────────────────────────────────────────────
mp_p = macd_p.shift(1)
sp_p = sig_p.shift(1)
long_p = (mp_p >= sp_p) & (macd_p < sig_p) & (mp_p >= 0) & (macd_p < 0)
short_p = (mp_p <= sp_p) & (macd_p > sig_p) & (mp_p <= 0) & (macd_p > 0)

# ── Signals: TV-style EMA ────────────────────────────────────────────────────
mp_tv = macd_tv.shift(1)
sp_tv = sig_tv.shift(1)
long_tv = (mp_tv >= sp_tv) & (macd_tv < sig_tv) & (mp_tv >= 0) & (macd_tv < 0)
short_tv = (mp_tv <= sp_tv) & (macd_tv > sig_tv) & (mp_tv <= 0) & (macd_tv > 0)

# ── Compare ───────────────────────────────────────────────────────────────────
cutoff = pd.Timestamp(START, tz="UTC")
mask = df.index >= cutoff

print("=" * 70)
print("EMA seed comparison: pandas ewm vs TV ta.ema (SMA seed)")
print("=" * 70)
print(f"\n  Pandas signals: long={long_p[mask].sum()}  short={short_p[mask].sum()}")
print(f"  TV EMA signals: long={long_tv[mask].sum()}  short={short_tv[mask].sum()}")

diff_long = long_p[mask] != long_tv[mask]
diff_short = short_p[mask] != short_tv[mask]
print(f"\n  Long  diff bars: {diff_long.sum()}")
print(f"  Short diff bars: {diff_short.sum()}")

# Show MACD values at signal bars to compare
print("\n  Pandas LONG  signals:")
for t in df.index[mask][long_p[mask].values]:
    print(f"    {t.strftime('%Y-%m-%d %H:%M')}  macd={macd_p.loc[t]:.5f}  sig={sig_p.loc[t]:.5f}")

print("\n  TV EMA LONG  signals:")
for t in df.index[mask][long_tv[mask].values]:
    print(f"    {t.strftime('%Y-%m-%d %H:%M')}  macd={macd_tv.loc[t]:.5f}  sig={sig_tv.loc[t]:.5f}")

print("\n  Pandas SHORT signals:")
for t in df.index[mask][short_p[mask].values]:
    print(f"    {t.strftime('%Y-%m-%d %H:%M')}  macd={macd_p.loc[t]:.5f}  sig={sig_p.loc[t]:.5f}")

print("\n  TV EMA SHORT signals:")
for t in df.index[mask][short_tv[mask].values]:
    print(f"    {t.strftime('%Y-%m-%d %H:%M')}  macd={macd_tv.loc[t]:.5f}  sig={sig_tv.loc[t]:.5f}")

# ── MACD value comparison at first few signal bars ───────────────────────────
print("\n  Sample MACD values at April 2025 signal bars:")
print("  (pandas vs TV EMA — should match if EMA seed is same)")
all_sigs = set(
    list(df.index[mask][long_p[mask].values])
    + list(df.index[mask][short_p[mask].values])
    + list(df.index[mask][long_tv[mask].values])
    + list(df.index[mask][short_tv[mask].values])
)
for t in sorted(all_sigs)[:15]:
    print(
        f"    {t.strftime('%Y-%m-%d %H:%M')}  "
        f"pandas_macd={macd_p.loc[t]:.6f}  tv_macd={macd_tv.loc[t]:.6f}  "
        f"diff={abs(macd_p.loc[t] - macd_tv.loc[t]):.8f}"
    )
