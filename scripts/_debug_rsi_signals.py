"""
Investigate RSI values around Nov 3 to understand why TV generates a long signal at 05:00 UTC
but our engine does not.
"""

import sqlite3
import sys
from datetime import UTC, datetime

import pandas as pd
import pandas_ta as ta


# Use manual RSI calculation to avoid talib dependency issues
def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"

# RSI Strategy_RSI_L\S_3 parameters
RSI_PERIOD = 14
CROSS_LONG_LEVEL = 29  # RSI crosses UP from below 29 = long signal
CROSS_SHORT_LEVEL = 55  # RSI crosses DOWN from above 55 = short signal


def load_ohlcv():
    conn = sqlite3.connect(DB_PATH)
    start_ms = int(datetime(2025, 11, 1, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime(2026, 2, 23, tzinfo=UTC).timestamp() * 1000)
    df = pd.read_sql_query(
        "SELECT open_time, open_price as open, high_price as high, "
        "low_price as low, close_price as close, volume "
        "FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
        "AND open_time >= ? AND open_time <= ? "
        "ORDER BY open_time ASC",
        conn,
        params=(start_ms, end_ms),
    )
    conn.close()
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("timestamp").drop(columns=["open_time"])


def main():
    ohlcv = load_ohlcv()

    # Compute RSI manually
    rsi = compute_rsi(ohlcv["close"], period=RSI_PERIOD)

    # Our signal generation (from indicator_handlers.py):
    # cross_long = (rsi_prev <= cross_long_level) & (rsi > cross_long_level)
    # cross_short = (rsi_prev >= cross_short_level) & (rsi < cross_short_level)
    rsi_prev = rsi.shift(1)
    cross_long = (rsi_prev <= CROSS_LONG_LEVEL) & (rsi > CROSS_LONG_LEVEL)
    cross_short = (rsi_prev >= CROSS_SHORT_LEVEL) & (rsi < CROSS_SHORT_LEVEL)

    # Show RSI values around Nov 3 03:00 - 08:00 UTC
    print("=== RSI VALUES AND SIGNALS: Nov 3 00:00 - 08:00 UTC ===")
    target_start = pd.Timestamp("2025-11-03 00:00:00", tz="UTC")
    target_end = pd.Timestamp("2025-11-03 08:00:00", tz="UTC")

    print(f"{'Bar':<5} {'Time':<30} {'Close':<12} {'RSI_prev':<12} {'RSI':<10} {'Long?':<6} {'Short?'}")
    for i, ts in enumerate(ohlcv.index):
        if target_start <= ts <= target_end:
            r = rsi.iloc[i] if not pd.isna(rsi.iloc[i]) else -1
            r_prev = rsi_prev.iloc[i] if not pd.isna(rsi_prev.iloc[i]) else -1
            cl = cross_long.iloc[i] if not pd.isna(cross_long.iloc[i]) else False
            cs = cross_short.iloc[i] if not pd.isna(cross_short.iloc[i]) else False
            marker = " ← LONG!" if cl else (" ← SHORT!" if cs else "")
            print(
                f"{i:<5} {ts!s:<30} {ohlcv['close'].iloc[i]:<12.2f} {r_prev:<12.4f} {r:<10.4f} {bool(cl)!s:<6} {bool(cs)!s}{marker}"
            )

    # TV signal bar index 212 = 05:00 UTC Nov 3
    tv_bar_idx = 212
    print("\n=== DETAILED ANALYSIS OF BAR 212 (05:00 UTC Nov 3) ===")
    ts212 = ohlcv.index[tv_bar_idx]
    print(f"Index: {tv_bar_idx}, Time: {ts212}")
    print(f"Close: {ohlcv['close'].iloc[tv_bar_idx]:.4f}")
    rsi_val = rsi.iloc[tv_bar_idx]
    rsi_prev_val = rsi_prev.iloc[tv_bar_idx]
    print(f"RSI(14): {rsi_val:.6f}")
    print(f"RSI_prev: {rsi_prev_val:.6f}")
    print(f"CROSS_LONG_LEVEL: {CROSS_LONG_LEVEL}")
    print(f"Would be long signal if: rsi_prev <= {CROSS_LONG_LEVEL} AND rsi > {CROSS_LONG_LEVEL}")
    print(f"rsi_prev={rsi_prev_val:.4f} <= {CROSS_LONG_LEVEL}? {rsi_prev_val <= CROSS_LONG_LEVEL}")
    print(f"rsi={rsi_val:.4f} > {CROSS_LONG_LEVEL}? {rsi_val > CROSS_LONG_LEVEL}")
    print(f"Signal: {cross_long.iloc[tv_bar_idx]}")

    # Check if TV uses crossover (rsi crossed UP through the level, meaning prev STRICTLY below and current above)
    # Or cross (meaning prev < level and current >= level) - different definitions
    # TV crossover: ta.crossover(source, level) = prev < level AND current >= level (strictly crosses)
    # Our code: (rsi_prev <= cross_long_level) & (rsi > cross_long_level)
    # TV might use: (rsi_prev < cross_long_level) & (rsi >= cross_long_level)  ← NOTE >= vs >

    print("\n=== ALTERNATIVE SIGNAL DEFINITIONS ===")
    # Definition 1 (ours): prev <= level AND current > level
    cross_long_v1 = (rsi_prev <= CROSS_LONG_LEVEL) & (rsi > CROSS_LONG_LEVEL)
    # Definition 2: prev < level AND current > level (strict on both)
    cross_long_v2 = (rsi_prev < CROSS_LONG_LEVEL) & (rsi > CROSS_LONG_LEVEL)
    # Definition 3: prev < level AND current >= level (TV-style crossover)
    cross_long_v3 = (rsi_prev < CROSS_LONG_LEVEL) & (rsi >= CROSS_LONG_LEVEL)
    # Definition 4: rsi crosses 29 (any direction crossing)
    # Definition 5: rsi crosses from below (crosses up through 29 from previous <= 29)
    # Definition 6: rsi at bar i >= level AND rsi at bar i-1 < level (TV ta.crossover)

    for label, sig in [
        ("v1 (prev<=L AND cur>L)", cross_long_v1),
        ("v2 (prev<L AND cur>L)", cross_long_v2),
        ("v3 (prev<L AND cur>=L)", cross_long_v3),
    ]:
        at_212 = sig.iloc[tv_bar_idx]
        count = sig.sum()
        print(f"  {label}: at bar 212 = {at_212}, total signals = {count}")

    # Show all RSI values around bar 212 more carefully
    print("\n=== RSI AROUND BAR 205-220 (Nov 3 03:15 - 07:15 UTC) ===")
    print(f"{'Bar':<5} {'Time':<30} {'RSI_prev':<12} {'RSI':<10} {'v1':<6} {'v2':<6} {'v3'}")
    for i in range(200, 225):
        ts = ohlcv.index[i]
        r = rsi.iloc[i] if not pd.isna(rsi.iloc[i]) else -1
        r_prev = rsi_prev.iloc[i] if not pd.isna(rsi_prev.iloc[i]) else -1
        s1 = cross_long_v1.iloc[i] if not pd.isna(cross_long_v1.iloc[i]) else False
        s2 = cross_long_v2.iloc[i] if not pd.isna(cross_long_v2.iloc[i]) else False
        s3 = cross_long_v3.iloc[i] if not pd.isna(cross_long_v3.iloc[i]) else False
        print(f"{i:<5} {ts!s:<30} {r_prev:<12.4f} {r:<10.4f} {bool(s1)!s:<6} {bool(s2)!s:<6} {bool(s3)!s}")


if __name__ == "__main__":
    main()
