"""
Debug script for RSI_5 signal discrepancy analysis.
Investigates why TV signals fire but ours don't.
"""

import sqlite3
import sys
from datetime import UTC, datetime

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()

from backend.backtesting.indicator_handlers import calculate_rsi

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"

conn = sqlite3.connect(DB_PATH)
start_ms = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
end_ms = int(datetime(2025, 2, 5, tzinfo=UTC).timestamp() * 1000)

df = pd.read_sql_query(
    "SELECT open_time, open_price as open, high_price as high, low_price as low, close_price as close "
    "FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='30' AND market_type='linear' "
    "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
    conn,
    params=(start_ms, end_ms),
)
conn.close()
df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df = df.set_index("ts").drop(columns=["open_time"])

rsi_arr = calculate_rsi(df["close"].values, period=14)
rsi = pd.Series(rsi_arr, index=df.index)

# TV signal bars (UTC) for trades 6-15
tv_signals = [
    (6, "short", "2025-01-20 02:00"),
    (7, "long", "2025-01-21 18:00"),
    (8, "short", "2025-01-22 16:00"),
    (9, "short", "2025-01-23 14:00"),
    (10, "short", "2025-01-27 18:30"),
    (11, "short", "2025-01-28 18:00"),
    (12, "short", "2025-01-29 22:00"),
    (13, "short", "2025-01-30 17:00"),
    (14, "short", "2025-01-31 09:00"),
    (15, "long", "2025-02-03 02:00"),
]

print("=" * 90)
print(
    f"{'#':<4} {'side':<7} {'signal_bar':<22} {'RSI_prev':>10} {'RSI_cur':>10} {'close':>10} {'range_ok':<10} {'cross_ok'}"
)
print("-" * 90)
for num, side, sig_str in tv_signals:
    sig_ts = pd.Timestamp(sig_str, tz="UTC")
    prev_ts = sig_ts - pd.Timedelta(minutes=30)
    rsi_cur = rsi.get(sig_ts, float("nan"))
    rsi_prev = rsi.get(prev_ts, float("nan"))
    close_cur = df["close"].get(sig_ts, float("nan"))
    if side == "short":
        range_ok = 50 <= rsi_cur <= 65
        cross_ok = rsi_prev >= 63 and rsi_cur < 63
    else:
        range_ok = 10 <= rsi_cur <= 40
        cross_ok = rsi_prev <= 18 and rsi_cur > 18
    print(
        f"{num:<4} {side:<7} {sig_str:<22} {rsi_prev:>10.2f} {rsi_cur:>10.2f} {close_cur:>10.1f} {range_ok!s:<10} {cross_ok}"
    )

print()
print("All TV#6-15 signals: RSI in range but NOT crossing the cross_level")
print("Hypothesis: TV does not require cross_level when RSI is in range")
print("Or: TV's cross_level check has a different look-back (any bar in last N bars)")
print()

# Test hypothesis: TV uses OR logic (range signal OR cross signal)
short_range_only = (rsi >= 50) & (rsi <= 65)
long_range_only = (rsi >= 10) & (rsi <= 40)
rsi_prev = rsi.shift(1)
cross_long = (rsi_prev <= 18) & (rsi > 18)
cross_short = (rsi_prev >= 63) & (rsi < 63)

# OR logic
long_or = long_range_only | cross_long
short_or = short_range_only | cross_short

# AND logic (current implementation)
long_and = long_range_only & cross_long
short_and = short_range_only & cross_short

print("Signal counts (Jan-Feb data):")
print(f"  Long range-only:  {long_range_only.sum()}")
print(f"  Short range-only: {short_range_only.sum()}")
print(f"  Long OR:          {long_or.sum()}")
print(f"  Short OR:         {short_or.sum()}")
print(f"  Long AND:         {long_and.sum()}")
print(f"  Short AND:        {short_and.sum()}")

print()
print("=== Check TV signals with OR logic ===")
for num, side, sig_str in tv_signals:
    sig_ts = pd.Timestamp(sig_str, tz="UTC")
    if side == "short":
        sig_or = bool(short_or.get(sig_ts, False))
        sig_range = bool(short_range_only.get(sig_ts, False))
        sig_cross = bool(cross_short.get(sig_ts, False))
    else:
        sig_or = bool(long_or.get(sig_ts, False))
        sig_range = bool(long_range_only.get(sig_ts, False))
        sig_cross = bool(cross_long.get(sig_ts, False))
    print(f"  TV#{num:<3} {side:<6}: OR={sig_or}  range={sig_range}  cross={sig_cross}")

# Also show our data at the TV entry price to confirm it's available
print()
print("=== Our OHLCV at TV entry bars (entry bar = signal_bar + 30min) ===")
for num, side, sig_str in tv_signals[:5]:
    sig_ts = pd.Timestamp(sig_str, tz="UTC")
    entry_ts = sig_ts + pd.Timedelta(minutes=30)
    if entry_ts in df.index:
        row = df.loc[entry_ts]
        print(f"  TV#{num} entry bar {entry_ts}: open={row['open']:.1f} close={row['close']:.1f}")
    else:
        print(f"  TV#{num} entry bar {entry_ts}: NOT IN DATA")
