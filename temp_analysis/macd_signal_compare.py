"""
MACD Signal Diagnostic — compare our signals vs TV Pine Script logic.
Shows raw crossovers, after-opposite-swap, with/without memory.
"""

import os
import sys

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
os.chdir(r"d:\bybit_strategy_tester_v2")

import sqlite3

import pandas as pd

# ── fetch OHLCV from SQLite directly ─────────────────────────────────────────
SYMBOL = "ETHUSDT"
INTERVAL = "30"
START = "2025-04-01"
END = "2025-04-30"

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"

warmup_start_ms = int(pd.Timestamp("2025-02-14", tz="UTC").timestamp() * 1000)
end_ms = int(pd.Timestamp(END, tz="UTC").timestamp() * 1000) + 86400000

con = sqlite3.connect(DB_PATH)
df_full = pd.read_sql(
    "SELECT open_time, open_price AS open, high_price AS high, low_price AS low, "
    "close_price AS close, volume FROM bybit_kline_audit "
    "WHERE symbol=? AND interval=? AND open_time >= ? AND open_time <= ? "
    "ORDER BY open_time",
    con,
    params=(SYMBOL, INTERVAL, warmup_start_ms, end_ms),
)
con.close()

df_full["timestamp"] = pd.to_datetime(df_full["open_time"], unit="ms", utc=True)
df_full = df_full.set_index("timestamp").sort_index()
df_full = df_full.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
print(f"Loaded {len(df_full)} bars from {df_full.index[0]} to {df_full.index[-1]}")

close = df_full["close"]

# ── MACD parameters (from Strategy_MACD_07) ──────────────────────────────────
FAST = 14
SLOW = 15
SIG = 9
OPPOSITE_CROSS = True  # opposite_macd_cross_signal=true
OPPOSITE_ZERO = True  # opposite_macd_cross_zero=true
USE_CROSS = True  # use_macd_cross_signal=true
USE_ZERO = True  # use_macd_cross_zero=true
DISABLE_MEMORY = True  # disable_signal_memory=true  ← our DB setting
MEMORY_BARS = 5

# ── Compute MACD ─────────────────────────────────────────────────────────────
fast_ema = close.ewm(span=FAST, adjust=False).mean()
slow_ema = close.ewm(span=SLOW, adjust=False).mean()
macd_line = fast_ema - slow_ema
signal_line = macd_line.ewm(span=SIG, adjust=False).mean()

# ── Raw crossovers ────────────────────────────────────────────────────────────
macd_prev = macd_line.shift(1)
sig_prev = signal_line.shift(1)

# SIGNAL cross (MACD vs signal line)
cross_up_signal = (macd_prev <= sig_prev) & (macd_line > signal_line)  # crossover  (up)
cross_dn_signal = (macd_prev >= sig_prev) & (macd_line < signal_line)  # crossunder (down)

# ZERO cross
zero_cross_up = (macd_prev <= 0) & (macd_line > 0)  # crossover  zero
zero_cross_dn = (macd_prev >= 0) & (macd_line < 0)  # crossunder zero

# ── TV Pine Script logic (with our params: opposite both = true) ─────────────
# TV:
#   longCrossZeroCondition   = oppositeCrossZero   ? crossDownZero   : crossUpZero
#   longCrossSignalCondition = oppositeCrossSignal ? crossDownSignal : crossUpSignal
#   shortCrossZeroCondition  = oppositeCrossZero   ? crossUpZero     : crossDownZero
#   shortCrossSignalCondition= oppositeCrossSignal ? crossUpSignal   : crossDownSignal
#   longSignal  = confirmedBar and useCrossZero(crossDownZero) and useCrossSignal(crossDownSignal)
#   shortSignal = confirmedBar and useCrossZero(crossUpZero)   and useCrossSignal(crossUpSignal)
tv_long_raw = cross_dn_signal & zero_cross_dn  # TV: MACD crossunder both signal AND zero
tv_short_raw = cross_up_signal & zero_cross_up  # TV: MACD crossover  both signal AND zero

# ── OUR logic: after opposite swap + AND + NO memory (disable_signal_memory=true) ──
# After swap: fresh_cross_long = cross_dn_signal, fresh_zero_cross_long = zero_cross_dn
our_long_raw = cross_dn_signal & zero_cross_dn  # same as TV ✓
our_short_raw = cross_up_signal & zero_cross_up  # same as TV ✓


# With memory applied (as TV default: disableSignalMemory UNCHECKED = memory ON)
def apply_memory(series, bars):
    result = series.copy()
    for shift in range(1, bars):
        result = result | series.shift(shift).fillna(False)
    return result.fillna(False)


tv_long_mem = apply_memory(tv_long_raw, MEMORY_BARS)  # TV: memory=5
tv_short_mem = apply_memory(tv_short_raw, MEMORY_BARS)

# ── Trim to analysis period ───────────────────────────────────────────────────
cutoff = pd.Timestamp(START, tz="UTC")
mask = df_full.index >= cutoff
idx = df_full.index[mask]

our_long_trimmed = our_long_raw[mask]
our_short_trimmed = our_short_raw[mask]
tv_long_trimmed = tv_long_mem[mask]  # TV with memory
tv_short_trimmed = tv_short_mem[mask]

# ── Summary counts ────────────────────────────────────────────────────────────
print("=" * 70)
print(f"MACD Signal Comparison: {SYMBOL} {INTERVAL}m  {START} → {END}")
print(f"Params: fast={FAST}, slow={SLOW}, signal={SIG}")
print(f"Opposite cross_signal={OPPOSITE_CROSS}, opposite_zero={OPPOSITE_ZERO}")
print(f"OUR disable_memory={DISABLE_MEMORY} | TV memory=ON (5 bars)")
print("=" * 70)
print(f"  Raw crossovers (BOTH conditions AND, no memory):")
print(f"    Long  (crossDN_signal AND crossDN_zero): {tv_long_raw[mask].sum()}")
print(f"    Short (crossUP_signal AND crossUP_zero): {tv_short_raw[mask].sum()}")
print(f"  Our signals (no memory):  long={our_long_trimmed.sum()}  short={our_short_trimmed.sum()}")
print(f"  TV signals (5-bar memory): long={tv_long_trimmed.sum()}  short={tv_short_trimmed.sum()}")
print()

# ── Show signal bars ─────────────────────────────────────────────────────────
our_long_bars = idx[our_long_trimmed.values]
tv_long_bars = idx[tv_long_trimmed.values]
our_short_bars = idx[our_short_trimmed.values]
tv_short_bars = idx[tv_short_trimmed.values]

print("── OUR LONG signal bars (no memory) ──")
for t in our_long_bars[:30]:
    bar = df_full.loc[t]
    ml = macd_line.loc[t]
    sl = signal_line.loc[t]
    print(f"  {t.strftime('%Y-%m-%d %H:%M')}  close={bar['close']:.2f}  macd={ml:.4f}  sig={sl:.4f}")

print()
print("── OUR SHORT signal bars (no memory) ──")
for t in our_short_bars[:30]:
    bar = df_full.loc[t]
    ml = macd_line.loc[t]
    sl = signal_line.loc[t]
    print(f"  {t.strftime('%Y-%m-%d %H:%M')}  close={bar['close']:.2f}  macd={ml:.4f}  sig={sl:.4f}")

print()
print("── TV LONG signal bars (5-bar memory) ──")
for t in tv_long_bars[:30]:
    bar = df_full.loc[t]
    is_fresh = tv_long_raw[mask][idx == t].values[0] if t in idx else False
    marker = (
        "← FRESH"
        if tv_long_raw.loc[t]
        else f"  (mem+{list(idx).index(t) - list(idx[tv_long_raw[mask]]).index(next((x for x in idx[tv_long_raw[mask]] if x <= t), t))})"
    )
    print(f"  {t.strftime('%Y-%m-%d %H:%M')}  close={bar['close']:.2f}  fresh={tv_long_raw.loc[t]}")

print()
print("── TV SHORT signal bars (5-bar memory) ──")
for t in tv_short_bars[:30]:
    bar = df_full.loc[t]
    print(f"  {t.strftime('%Y-%m-%d %H:%M')}  close={bar['close']:.2f}  fresh={tv_short_raw.loc[t]}")

# ── Are our raw signals identical to TV raw signals? ─────────────────────────
print()
long_match = (our_long_trimmed == tv_long_raw[mask]).all()
short_match = (our_short_trimmed == tv_short_raw[mask]).all()
print(f"Raw signal match (our no-mem == TV raw): long={long_match}  short={short_match}")
