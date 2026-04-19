"""Deep dive into why StrategyBuilderAdapter gives 489 signals vs AdvancedMACDStrategy ~42"""

import sys
from typing import TextIO

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

# Reconfigure stdout for UTF-8 output (ignore mypy type issue)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

import sqlite3

import pandas as pd
import vectorbt as vbt

# Load OHLCV (same range)
conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
START_MS = int(pd.Timestamp("2025-01-04 15:30", tz="UTC").timestamp() * 1000)
END_MS = int(pd.Timestamp("2026-03-01 13:30", tz="UTC").timestamp() * 1000)
df = pd.read_sql(
    f"SELECT open_time, open_price AS open, high_price AS high, low_price AS low, close_price AS close, volume"
    f" FROM bybit_kline_audit WHERE symbol='ETHUSDT' AND interval='30'"
    f" AND open_time >= {START_MS} AND open_time <= {END_MS}"
    f" ORDER BY open_time",
    conn,
)
conn.close()
df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df.set_index("open_time", inplace=True)
for col in ["open", "high", "low", "close", "volume"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")
ohlcv = df
close = ohlcv["close"]
print(f"Bars: {len(ohlcv)}, {ohlcv.index[0]} to {ohlcv.index[-1]}")

# --- Adapter approach (vbt.MACD.run) ---
macd_result = vbt.MACD.run(close, fast_window=14, slow_window=15, signal_window=9)
macd_vbt = macd_result.macd
sig_vbt = macd_result.signal

# --- AdvancedMACDStrategy approach (ewm adjust=False) ---
fast_ema = close.ewm(span=14, adjust=False).mean()
slow_ema = close.ewm(span=15, adjust=False).mean()
macd_ewm = fast_ema - slow_ema
sig_ewm = macd_ewm.ewm(span=9, adjust=False).mean()

# Compare MACD values
diff = (macd_vbt - macd_ewm).abs()
print(f"\nMACD EMA diff: max={diff.max():.8f}, mean={diff.mean():.8f}")
print(f"vbt NaN count: {macd_vbt.isna().sum()}, ewm NaN count: {macd_ewm.isna().sum()}")
print(f"First non-NaN vbt: index {macd_vbt.first_valid_index()}")
print(f"First non-NaN ewm: index {macd_ewm.first_valid_index()}")


# --- Compute crossovers for BOTH ---
def count_signals(macd_line, signal_line, label):
    macd_safe = macd_line.fillna(0.0)
    sig_safe = signal_line.fillna(0.0)
    data_valid = (~macd_line.isna()) & (~signal_line.isna())
    mp = macd_safe.shift(1)
    sp = sig_safe.shift(1)

    # With opposite flags: long = crossUNDER
    cross_down_signal = (mp >= sp) & (macd_safe < sig_safe)  # MACD crosses under signal
    cross_down_zero = (mp >= 0) & (macd_safe < 0)  # MACD crosses under zero

    print(f"\n[{label}]")
    print(f"  cross_down_signal (long raw): {cross_down_signal.sum()}")
    print(f"  cross_down_zero (long raw):   {cross_down_zero.sum()}")
    intersection = data_valid & cross_down_signal & cross_down_zero
    print(f"  AND intersection (long entries): {intersection.sum()}")

    # Also count short signals
    cross_up_signal = (mp <= sp) & (macd_safe > sig_safe)
    cross_up_zero = (mp <= 0) & (macd_safe > 0)
    short_intersection = data_valid & cross_up_signal & cross_up_zero
    print(f"  AND intersection (short entries): {short_intersection.sum()}")

    return intersection.sum(), short_intersection.sum()


l_vbt, s_vbt = count_signals(macd_vbt, sig_vbt, "vbt.MACD.run")
l_ewm, s_ewm = count_signals(macd_ewm, sig_ewm, "ewm(adjust=False)")

print(f"\nSummary:")
print(f"  vbt.MACD.run -> long={l_vbt}, short={s_vbt}")
print(f"  ewm(adj=F)   -> long={l_ewm}, short={s_ewm}")
print(f"  TV reference: 42 trades (20 long + 22 short)")
