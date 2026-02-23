"""Check OHLCV bars around TV entry times to understand TV entry price logic."""

import asyncio
import sys

sys.path.insert(0, ".")


async def main():
    import pandas as pd

    from backend.services.adapters.bybit import BybitAdapter

    adapter = BybitAdapter()
    start = int(pd.Timestamp("2025-11-01 09:00", tz="UTC").timestamp() * 1000)
    end = int(pd.Timestamp("2025-11-01 10:30", tz="UTC").timestamp() * 1000)
    result = await adapter.get_historical_klines("BTCUSDT", "15", start, end)

    print("Bars around first TV entry (Entry short 2025-11-01 09:45, price=109917.9):")
    print(f"{'Time':22} | {'Open':>10} | {'High':>10} | {'Low':>10} | {'Close':>10}")
    print("-" * 75)
    for bar in result:
        raw = bar.get("raw", [])
        if len(raw) >= 5:
            dt = bar["open_time_dt"]
            o = float(raw[1])
            h = float(raw[2])
            lo = float(raw[3])
            c = float(raw[4])
            marker = " <-- TV entry bar?" if abs(o - 109917.9) < 50 or abs(c - 109917.9) < 50 else ""
            print(f"{dt!s:22} | {o:>10.1f} | {h:>10.1f} | {lo:>10.1f} | {c:>10.1f}{marker}")

    # Also check second entry: 2025-11-03 08:15 RsiLE price=107903.8
    print("\nBars around second TV entry (Entry long 2025-11-03 08:15, price=107903.8):")
    start2 = int(pd.Timestamp("2025-11-03 07:45", tz="UTC").timestamp() * 1000)
    end2 = int(pd.Timestamp("2025-11-03 09:00", tz="UTC").timestamp() * 1000)
    result2 = await adapter.get_historical_klines("BTCUSDT", "15", start2, end2)
    print(f"{'Time':22} | {'Open':>10} | {'High':>10} | {'Low':>10} | {'Close':>10}")
    print("-" * 75)
    for bar in result2:
        raw = bar.get("raw", [])
        if len(raw) >= 5:
            dt = bar["open_time_dt"]
            o = float(raw[1])
            h = float(raw[2])
            lo = float(raw[3])
            c = float(raw[4])
            marker = " <-- TV entry?" if abs(o - 107903.8) < 100 or abs(c - 107903.8) < 100 else ""
            print(f"{dt!s:22} | {o:>10.1f} | {h:>10.1f} | {lo:>10.1f} | {c:>10.1f}{marker}")


asyncio.run(main())
