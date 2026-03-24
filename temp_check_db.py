"""Test fetching real OHLCV from BacktestService (async)."""

import asyncio
from datetime import UTC, datetime

from backend.backtesting.service import BacktestService


async def main():
    svc = BacktestService()
    print("Trying BacktestService._fetch_historical_data for ETHUSDT 30m...")
    try:
        df = await svc._fetch_historical_data(
            symbol="ETHUSDT",
            interval="30",
            start_date=datetime(2025, 1, 1, tzinfo=UTC),
            end_date=datetime(2025, 3, 1, tzinfo=UTC),
            market_type="linear",
        )
        if df is not None and len(df) > 0:
            print(f"  OK: {len(df)} bars")
            print(f"  Columns: {list(df.columns)}")
            print(f"  Date range: {df.index[0]} → {df.index[-1]}")
        else:
            print("  No data returned (empty)")
    except Exception as e:
        import traceback

        print(f"  Error: {type(e).__name__}: {e}")
        traceback.print_exc()


asyncio.run(main())
