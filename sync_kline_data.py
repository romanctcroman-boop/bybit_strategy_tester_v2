""""""

Sync kline data - ensure all symbols have the same timeframes.Sync kline data - ensure all symbols have the same timeframes.

Target intervals: 15m, 30m, 1h (60), 4h (240), DTarget intervals: 15m, 30m, 1h (60), 4h (240), D

""""""



import osimport asyncio

import sysimport os

import timeimport sys



sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))



from backend.services.adapters.bybit import BybitAdapterfrom datetime import datetime, timedelta

from backend.services.kline_db_service import KlineDBService

from backend.services.adapters.bybit import BybitAdapter

from backend.services.kline_db_service import KlineDBService

# Target symbols and intervals

TARGET_SYMBOLS = [# Target symbols and intervals

    "BTCUSDT", "ETHUSDT", "ADAUSDT", "AVAXUSDT", "BNBUSDT",TARGET_SYMBOLS = [

    "DOGEUSDT", "DOTUSDT", "LINKUSDT", "SOLUSDT", "XRPUSDT"    "BTCUSDT",

]    "ETHUSDT",

    "ADAUSDT",

TARGET_INTERVALS = ["15", "30", "60", "240", "D"]  # 15m, 30m, 1h, 4h, Daily    "AVAXUSDT",

    "BNBUSDT",

    "DOGEUSDT",

def fetch_and_store(adapter: BybitAdapter, db_service: KlineDBService,    "DOTUSDT",

                    symbol: str, interval: str, limit: int):    "LINKUSDT",

    """Fetch klines from Bybit and store in DB."""    "SOLUSDT",

    try:    "XRPUSDT",

        print(f"  {symbol} {interval}...", end=" ", flush=True)]



        klines = adapter.get_klines(# Skip MATICUSDT - it's been replaced by POLUSDT on Bybit

            symbol=symbol,

            interval=interval,TARGET_INTERVALS = ["15", "30", "60", "240", "D"]  # 15m, 30m, 1h, 4h, Daily

            limit=min(limit, 1000)

        )# How many candles to fetch per interval

CANDLE_LIMITS = {

        if not klines:    "15": 40000,  # ~416 days of 15m data

            print("❌ No data")    "30": 20000,  # ~416 days of 30m data

            return 0    "60": 10000,  # ~416 days of 1h data

    "240": 2500,  # ~416 days of 4h data

        db_service.queue_klines(symbol, interval, klines)    "D": 500,  # ~500 days of daily data

        print(f"✅ {len(klines)}")}

        return len(klines)



    except Exception as e:async def fetch_and_store(adapter: BybitAdapter, db_service: KlineDBService, symbol: str, interval: str, limit: int):

        print(f"❌ {e}")    """Fetch klines from Bybit and store in DB."""

        return 0    try:

        print(f"  Fetching {symbol} {interval}m ({limit} candles)...", end=" ", flush=True)



def main():        # Calculate start time (go back enough days)

    print("=" * 60)        klines = await adapter.get_klines(

    print("🔄 Syncing Kline Data - All Symbols to Same Timeframes")            symbol=symbol,

    print("=" * 60)            interval=interval,

    print(f"Symbols: {', '.join(TARGET_SYMBOLS)}")            limit=min(limit, 1000),  # Bybit max is 1000 per request

    print(f"Intervals: {', '.join(TARGET_INTERVALS)}")        )

    print()

        if not klines:

    adapter = BybitAdapter()            print("❌ No data")

    db_service = KlineDBService()            return 0

    db_service.start()

        # Store in DB

    try:        db_service.queue_klines(symbol, interval, klines)

        total_fetched = 0        print(f"✅ {len(klines)} candles")

        return len(klines)

        for symbol in TARGET_SYMBOLS:

            print(f"\n📊 {symbol}")    except Exception as e:

        print(f"❌ Error: {e}")

            for interval in TARGET_INTERVALS:        return 0

                count = fetch_and_store(adapter, db_service, symbol, interval, 1000)

                total_fetched += count

                time.sleep(0.25)async def fetch_historical(

    adapter: BybitAdapter, db_service: KlineDBService, symbol: str, interval: str, total_candles: int

        print("\n⏳ Waiting for DB writes...")):

        time.sleep(3)    """Fetch historical data in batches."""

    print(f"  Fetching {symbol} {interval} ({total_candles} candles historical)...")

        print(f"\n✅ Done! Total: {total_fetched} candles")

    all_klines = []

    finally:    end_time = None

        db_service.stop()    batch_size = 1000

    fetched = 0



if __name__ == "__main__":    while fetched < total_candles:

    main()        try:

            klines = await adapter.get_klines(symbol=symbol, interval=interval, limit=batch_size, end=end_time)

            if not klines:
                break

            all_klines.extend(klines)
            fetched += len(klines)

            # Get oldest timestamp for next batch
            oldest = min(k.get("openTime", k.get("open_time", 0)) for k in klines)
            end_time = oldest - 1

            print(f"    Batch: {len(klines)}, Total: {fetched}/{total_candles}", flush=True)

            if len(klines) < batch_size:
                break

            await asyncio.sleep(0.1)  # Rate limiting

        except Exception as e:
            print(f"    Error: {e}")
            break

    if all_klines:
        db_service.queue_klines(symbol, interval, all_klines)
        print(f"  ✅ Stored {len(all_klines)} candles for {symbol} {interval}")

    return len(all_klines)


async def main():
    print("=" * 60)
    print("🔄 Syncing Kline Data - All Symbols to Same Timeframes")
    print("=" * 60)
    print(f"Symbols: {', '.join(TARGET_SYMBOLS)}")
    print(f"Intervals: {', '.join(TARGET_INTERVALS)}")
    print()

    # Initialize services
    adapter = BybitAdapter()
    db_service = KlineDBService()
    db_service.start()

    try:
        total_fetched = 0

        for symbol in TARGET_SYMBOLS:
            print(f"\n📊 {symbol}")
            print("-" * 40)

            for interval in TARGET_INTERVALS:
                limit = CANDLE_LIMITS.get(interval, 1000)
                count = await fetch_and_store(adapter, db_service, symbol, interval, limit)
                total_fetched += count
                await asyncio.sleep(0.2)  # Rate limiting between requests

        # Wait for all writes to complete
        print("\n⏳ Waiting for DB writes to complete...")
        await asyncio.sleep(3)

        print(f"\n✅ Done! Total candles fetched: {total_fetched}")

    finally:
        db_service.stop()


if __name__ == "__main__":
    asyncio.run(main())
