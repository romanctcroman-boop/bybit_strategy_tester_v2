"""
Verify BTC close prices at root signal bars by comparing our DB data
with live Bybit API data.
"""

import asyncio
import sys

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.service import BacktestService


async def main():
    svc = BacktestService()

    # Load our BTC data from DB
    btc = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )

    # Root signal bars and their prev bars
    bars_to_check = [
        ("Root #12 signal", "2025-02-06 14:00:00"),
        ("Root #12 prev", "2025-02-06 13:30:00"),
        ("Root #85 signal", "2025-08-16 01:00:00"),
        ("Root #85 prev", "2025-08-16 00:30:00"),
        ("Root #89 signal", "2025-08-27 02:30:00"),
        ("Root #89 prev", "2025-08-27 02:00:00"),
        ("Root #91 signal", "2025-09-02 11:00:00"),
        ("Root #91 prev", "2025-09-02 10:30:00"),
    ]

    print("BTC OHLCV at root signal bars (from our DB):")
    print(f"{'Label':<20} {'Time':<22} {'Open':>12} {'High':>12} {'Low':>12} {'Close':>12} {'Volume':>15}")
    print("-" * 110)

    for label, time_str in bars_to_check:
        t = pd.Timestamp(time_str)
        if t in btc.index:
            row = btc.loc[t]
            print(
                f"{label:<20} {time_str:<22} {row['open']:>12.2f} {row['high']:>12.2f} {row['low']:>12.2f} {row['close']:>12.2f} {row['volume']:>15.4f}"
            )
        else:
            print(f"{label:<20} {time_str:<22} NOT FOUND")

    # Now fetch the same data from Bybit API for comparison
    print("\n\nFetching same bars from Bybit API for verification...")

    # Use Bybit adapter
    import aiohttp

    from backend.services.adapters.bybit import BybitAdapter

    async with aiohttp.ClientSession() as session:
        adapter = BybitAdapter(session)

        for label, time_str in bars_to_check:
            t = pd.Timestamp(time_str)
            # Bybit API: start/end in milliseconds
            start_ms = int(t.timestamp() * 1000)
            end_ms = start_ms + 30 * 60 * 1000  # 30 min later

            try:
                response = await adapter.get_kline(
                    category="linear",
                    symbol="BTCUSDT",
                    interval="30",
                    start=start_ms,
                    end=end_ms,
                    limit=2,
                )

                if response.get("retCode") == 0:
                    klines = response.get("result", {}).get("list", [])
                    for k in klines:
                        bar_ts = int(k[0]) / 1000
                        bar_time = pd.Timestamp(bar_ts, unit="s")
                        if bar_time == t:
                            api_open = float(k[1])
                            api_high = float(k[2])
                            api_low = float(k[3])
                            api_close = float(k[4])

                            db_row = btc.loc[t] if t in btc.index else None
                            if db_row is not None:
                                close_match = abs(api_close - db_row["close"]) < 0.01
                                print(
                                    f"  {label}: API_close={api_close:.2f}, DB_close={db_row['close']:.2f}, match={close_match}"
                                )
                            else:
                                print(f"  {label}: API_close={api_close:.2f}, DB=NOT FOUND")
                else:
                    print(f"  {label}: API error: {response.get('retMsg')}")
            except Exception as e:
                print(f"  {label}: Error: {e}")


asyncio.run(main())
