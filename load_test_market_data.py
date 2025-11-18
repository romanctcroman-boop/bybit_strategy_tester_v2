"""
Загрузка тестовых market data для BTCUSDT
"""

from datetime import datetime, timedelta, timezone
from backend.database import SessionLocal
from backend.models import MarketData
from loguru import logger
import random


def generate_test_candles(
    symbol: str,
    interval: str,
    start: datetime,
    end: datetime,
    base_price: float = 40000.0
) -> list:
    """Генерация тестовых свечей с реалистичными данными"""
    
    # Map interval to timedelta
    interval_map = {
        "1": timedelta(minutes=1),
        "5": timedelta(minutes=5),
        "15": timedelta(minutes=15),
        "30": timedelta(minutes=30),
        "60": timedelta(hours=1),
        "240": timedelta(hours=4),
        "D": timedelta(days=1),
    }
    
    delta = interval_map.get(interval, timedelta(hours=1))
    candles = []
    current_time = start
    current_price = base_price
    
    while current_time <= end:
        # Simulate price movement
        price_change = random.uniform(-0.02, 0.02)  # ±2%
        current_price *= (1 + price_change)
        
        # Generate OHLC
        open_price = current_price
        high = open_price * random.uniform(1.0, 1.01)
        low = open_price * random.uniform(0.99, 1.0)
        close = random.uniform(low, high)
        volume = random.uniform(100, 1000)
        
        candles.append(MarketData(
            symbol=symbol,
            interval=interval,
            timestamp=current_time,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume
        ))
        
        current_time += delta
        current_price = close  # Continue from close
    
    return candles


def main():
    """Загрузка тестовых данных"""
    
    db = SessionLocal()
    
    try:
        # Параметры
        symbol = "BTCUSDT"
        interval = "60"  # 1 hour
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 2, 1, tzinfo=timezone.utc)  # 1 month
        
        logger.info(f"Generating test candles for {symbol} {interval}")
        logger.info(f"Period: {start} to {end}")
        
        # Проверить существующие данные
        existing = db.query(MarketData).filter(
            MarketData.symbol == symbol,
            MarketData.interval == interval
        ).count()
        
        if existing > 0:
            logger.warning(f"Found {existing} existing candles, deleting...")
            db.query(MarketData).filter(
                MarketData.symbol == symbol,
                MarketData.interval == interval
            ).delete()
            db.commit()
        
        # Генерация
        candles = generate_test_candles(symbol, interval, start, end)
        logger.info(f"Generated {len(candles)} candles")
        
        # Bulk insert
        db.bulk_save_objects(candles)
        db.commit()
        
        logger.success(f"✅ Loaded {len(candles)} candles to database")
        logger.info(f"   Symbol: {symbol}")
        logger.info(f"   Interval: {interval}")
        logger.info(f"   Period: {start} to {end}")
        
    except Exception as e:
        logger.error(f"❌ Failed to load data: {e}")
        db.rollback()
        raise
    
    finally:
        db.close()


if __name__ == "__main__":
    main()
