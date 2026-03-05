"""
Diagnose why entry/exit bar timestamps differ between our backtest and TradingView.

TV screenshots show:
  Trade 1: MACD_LE signal fires at ~02:00 UTC+3 on Mar 4 (= ~23:00 UTC Mar 3)
  Our:      Buy 1967.37 at ~20:00 UTC+3 on Mar 3 (= ~17:00 UTC Mar 3)

Key question: does TV fire signal on BAR CLOSE or are both correct but showing different things?
"""

import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import sqlite3

import pandas as pd

# Load ETHUSDT 30m candles
conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
df = pd.read_sql(
    """
    SELECT timestamp, open, high, low, close, volume
    FROM klines
    WHERE symbol='ETHUSDT' AND interval='30'
    ORDER BY timestamp ASC
""",
    conn,
)
conn.close()

df["ts"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
df = df.set_index("ts").sort_index()

# Focus on the dates visible in screenshots: around 2026-03-03 and 2026-03-13
for target_date in ["2026-03-03", "2026-03-04", "2026-03-13"]:
    print(f"\n{'=' * 60}")
    print(f"Date range: {target_date}")
    window = df.loc[f"{target_date}"]
    if len(window) == 0:
        print("No data")
        continue

    # Compute MACD(14,15,9) exactly as our code does (ewm adjust=False)
    close = df["close"]
    fast_ema = close.ewm(span=14, adjust=False).mean()
    slow_ema = close.ewm(span=15, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=9, adjust=False).mean()

    macd_prev = macd_line.shift(1)
    signal_prev = signal_line.shift(1)

    # Both conditions: use_macd_cross_signal AND use_macd_cross_zero (with opposite flags)
    # opposite_macd_cross_signal=True => swap cross directions
    # So: raw cross_long (MACD > signal) becomes SHORT, raw cross_short becomes LONG
    raw_cross_long = (macd_prev <= signal_prev) & (macd_line > signal_line)
    raw_cross_short = (macd_prev >= signal_prev) & (macd_line < signal_line)
    # opposite => swap
    cross_long = raw_cross_short  # actual long signal after opposite flip
    cross_short = raw_cross_long  # actual short signal after opposite flip

    # opposite_macd_cross_zero=True => swap zero cross directions
    zero_prev = macd_line.shift(1)
    raw_zero_long = (zero_prev <= 0) & (macd_line > 0)
    raw_zero_short = (zero_prev >= 0) & (macd_line < 0)
    # opposite => swap
    zero_long = raw_zero_short
    zero_short = raw_zero_long

    # Both modes active => AND on fresh signals
    both_long = cross_long & zero_long
    both_short = cross_short & zero_short

    # Filter to target date
    target_both_long = both_long.loc[target_date]
    target_both_short = both_short.loc[target_date]
    target_macd = macd_line.loc[target_date]
    target_signal = signal_line.loc[target_date]
    target_cross_l = cross_long.loc[target_date]
    target_cross_s = cross_short.loc[target_date]
    target_zero_l = zero_long.loc[target_date]
    target_zero_s = zero_short.loc[target_date]

    # Show signal bars
    sigs = target_both_long | target_both_short | target_cross_l | target_cross_s | target_zero_l | target_zero_s

    if not sigs.any():
        print(f"No signals on {target_date}")
    else:
        print(f"\nSignal bars on {target_date}:")
        for ts, row in df.loc[target_date].iterrows():
            has_sig = (
                both_long.get(ts, False)
                or both_short.get(ts, False)
                or cross_long.get(ts, False)
                or cross_short.get(ts, False)
                or zero_long.get(ts, False)
                or zero_short.get(ts, False)
            )
            if has_sig:
                print(f"  {ts} (UTC) | close={row['close']:.2f} | open={row['open']:.2f}")
                print(f"    cross_long={cross_long.get(ts, False)}, cross_short={cross_short.get(ts, False)}")
                print(f"    zero_long={zero_long.get(ts, False)},  zero_short={zero_short.get(ts, False)}")
                print(f"    BOTH_long={both_long.get(ts, False)},  BOTH_short={both_short.get(ts, False)}")
                # NEXT BAR (where we enter)
                idx = df.index.get_loc(ts)
                if idx + 1 < len(df):
                    next_ts = df.index[idx + 1]
                    next_open = df["open"].iloc[idx + 1]
                    print(f"    => Our entry bar: {next_ts} (UTC), open={next_open:.2f}")
                    print(f"    => UTC+3: {(next_ts).tz_convert('Europe/Moscow')}")

print("\n\nDone.")
