"""Check RSI values around specific TV entry times where we have no signal."""
import asyncio
import sys

import pandas as pd

sys.path.insert(0, "D:/bybit_strategy_tester_v2")

RSI_PERIOD = 14
CROSS_SHORT = 55
CROSS_LONG = 29

CHECK_TIMES = [
    ("short", "2025-11-05 20:00", "2025-11-05 21:15"),
    ("long",  "2025-11-06 16:15", "2025-11-06 17:45"),
    ("short", "2025-11-07 23:30", "2025-11-08 01:15"),
    ("short", "2025-11-09 21:45", "2025-11-09 23:15"),
    ("long",  "2025-11-12 18:45", "2025-11-12 20:30"),
    ("long",  "2025-11-13 20:30", "2025-11-13 22:00"),
]


async def main():
    import vectorbt as vbt

    from backend.backtesting.service import BacktestService

    svc = BacktestService()
    ohlcv = await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="15",
        start_date=pd.Timestamp("2025-11-01", tz="UTC"),
        end_date=pd.Timestamp("2026-02-23", tz="UTC"),
    )

    close = ohlcv["close"]
    rsi_series = vbt.RSI.run(close, window=RSI_PERIOD).rsi
    rsi_prev = rsi_series.shift(1)

    short_sig = (rsi_prev >= CROSS_SHORT) & (rsi_series < CROSS_SHORT)
    long_sig = (rsi_prev <= CROSS_LONG) & (rsi_series > CROSS_LONG)

    idx_utc = ohlcv.index.tz_convert("UTC").tz_localize(None) if ohlcv.index.tz is not None else ohlcv.index

    print("RSI values around TV missing signal bars:")
    print()

    for direction, start_str, end_str in CHECK_TIMES:
        start_ts = pd.Timestamp(start_str)
        end_ts = pd.Timestamp(end_str)
        mask = (idx_utc >= start_ts) & (idx_utc <= end_ts)

        print(f"=== {direction} window {start_str} to {end_str} UTC ===")
        print(f"  {'UTC Time':26} {'Close':>10} {'RSI':>8} {'Prev':>8} {'Signal':>8}")

        if not mask.any():
            print("  (no bars)")
        else:
            for loc_idx in ohlcv.index[mask]:
                c = ohlcv.loc[loc_idx, "close"]
                r = rsi_series.loc[loc_idx]
                p = rsi_prev.loc[loc_idx]
                sig = short_sig.loc[loc_idx] if direction == "short" else long_sig.loc[loc_idx]
                time_str = str(loc_idx)[:26]
                marker = " <-- SIGNAL" if sig else ""
                lvl = CROSS_SHORT if direction == "short" else CROSS_LONG
                near = " (CLOSE)" if abs(r - lvl) < 1.5 else ""
                print(f"  {time_str:26} {c:10.2f} {r:8.2f} {p:8.2f} {sig!s:>8}{marker}{near}")

        lvl = CROSS_SHORT if direction == "short" else CROSS_LONG
        word = "below" if direction == "short" else "above"
        print(f"  (threshold RSI {word} {lvl})")
        print()

    print("=" * 60)
    print("ALL RSI signals Nov 1-15 UTC:")
    nov1 = pd.Timestamp("2025-11-01")
    nov15 = pd.Timestamp("2025-11-15")
    full_mask = (idx_utc >= nov1) & (idx_utc < nov15)

    long_times_mask = long_sig[full_mask]
    short_times_mask = short_sig[full_mask]
    long_ts = idx_utc[full_mask][long_times_mask]
    short_ts = idx_utc[full_mask][short_times_mask]

    print(f"Long signals ({len(long_ts)}):")
    for t in long_ts:
        print(f"  UTC {t}  =>  MSK {t + pd.Timedelta(hours=3)}")

    print(f"\nShort signals ({len(short_ts)}):")
    for t in short_ts:
        print(f"  UTC {t}  =>  MSK {t + pd.Timedelta(hours=3)}")


asyncio.run(main())
