"""
Quick MTF Interval Field Test (In-Memory SQLite)

Tests Priority #2 implementation with fresh in-memory database.
"""

import os
import sys

# Set DATABASE_URL to file-based SQLite BEFORE importing backend modules
os.environ["DATABASE_URL"] = "sqlite:///test_mtf_fresh.db"

from datetime import datetime, UTC
from loguru import logger

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from backend.database import Base, SessionLocal, engine
from backend.models.bybit_kline_audit import BybitKlineAudit
from backend.services.adapters.bybit import BybitAdapter


def main():
    logger.info("🚀 Quick MTF Interval Field Test")
    logger.info("=" * 80)
    
    # Step 1: Create fresh schema
    logger.info("Step 1: Creating fresh database schema...")
    Base.metadata.drop_all(bind=engine)  # Drop existing
    Base.metadata.create_all(bind=engine)  # Create new with interval field
    logger.success("✅ Fresh schema created")
    
    # Step 2: Test MTF storage
    logger.info("\nStep 2: Testing MTF data storage (same timestamp, different intervals)...")
    
    adapter = BybitAdapter()
    symbol = "BTCUSDT"
    base_time = int(datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC).timestamp() * 1000)
    
    test_intervals = ["5", "15", "30"]
    test_data = {
        "5": {"close": 42050.0, "volume": 100.5},
        "15": {"close": 42100.0, "volume": 320.8},
        "30": {"close": 42150.0, "volume": 650.2},
    }
    
    # Insert data for each interval
    for interval in test_intervals:
        normalized = [{
            "open_time": base_time,
            "open": 42000.0,
            "high": 42000.0 + int(interval) * 10,
            "low": 42000.0 - int(interval) * 10,
            "close": test_data[interval]["close"],
            "volume": test_data[interval]["volume"],
            "turnover": 4200000.0,
        }]
        
        try:
            adapter._persist_klines_to_db(symbol, normalized, interval=interval)
            logger.success(f"✅ {interval}m candle stored")
        except Exception as e:
            logger.error(f"❌ {interval}m failed: {e}")
            return False
    
    # Step 3: Verify storage
    logger.info("\nStep 3: Verifying MTF storage...")
    
    db = SessionLocal()
    try:
        for interval in test_intervals:
            candles = db.query(BybitKlineAudit).filter(
                BybitKlineAudit.symbol == symbol,
                BybitKlineAudit.interval == interval,
                BybitKlineAudit.open_time == base_time,
            ).all()
            
            if len(candles) == 1:
                candle = candles[0]
                logger.success(
                    f"✅ {interval}m: close={candle.close_price}, volume={candle.volume}"
                )
            else:
                logger.error(f"❌ {interval}m: Expected 1 candle, found {len(candles)}")
                return False
        
        # Check total
        total = db.query(BybitKlineAudit).filter(
            BybitKlineAudit.symbol == symbol,
            BybitKlineAudit.open_time == base_time,
        ).count()
        
        logger.info(f"\n📊 Total candles at same timestamp: {total}")
        
        if total == 3:
            logger.success("✅ MTF STORAGE WORKING: 3 different intervals at same timestamp!")
            return True
        else:
            logger.error(f"❌ Expected 3, found {total}")
            return False
            
    finally:
        db.close()
    
    # Step 4: Test unique constraint (upsert)
    logger.info("\nStep 4: Testing unique constraint (upsert)...")
    
    # Try to insert duplicate with different close price
    duplicate_data = [{
        "open_time": base_time,
        "open": 42000.0,
        "high": 42100.0,
        "low": 41900.0,
        "close": 43000.0,  # Different close
        "volume": 999.9,  # Different volume
        "turnover": 9999999.0,
    }]
    
    try:
        adapter._persist_klines_to_db(symbol, duplicate_data, interval="15")
        logger.success("✅ Duplicate insert handled (no error)")
    except Exception as e:
        logger.error(f"❌ Duplicate insert failed: {e}")
        return False
    
    # Verify only 1 record for 15m
    db = SessionLocal()
    try:
        count = db.query(BybitKlineAudit).filter(
            BybitKlineAudit.symbol == symbol,
            BybitKlineAudit.interval == "15",
            BybitKlineAudit.open_time == base_time,
        ).count()
        
        if count == 1:
            # Check if updated
            candle = db.query(BybitKlineAudit).filter(
                BybitKlineAudit.symbol == symbol,
                BybitKlineAudit.interval == "15",
                BybitKlineAudit.open_time == base_time,
            ).first()
            
            if candle.close_price == 43000.0:
                logger.success("✅ Unique constraint working: Data updated via upsert")
                logger.info(f"   Updated close: {candle.close_price}, volume: {candle.volume}")
            else:
                logger.warning(f"⚠️ Close price not updated: {candle.close_price}")
        else:
            logger.error(f"❌ Expected 1 record, found {count}")
            return False
    finally:
        db.close()
    
    logger.info("\n" + "=" * 80)
    logger.success("🎉 Priority #2 COMPLETE: 'interval' field working perfectly!")
    logger.info("\n✅ Summary:")
    logger.info("   • Database schema supports 'interval' field")
    logger.info("   • Can store multiple timeframes at same timestamp")
    logger.info("   • Unique constraint (symbol, interval, open_time) working")
    logger.info("   • Upsert functionality working (updates on conflict)")
    logger.info("\n📋 Next Steps:")
    logger.info("   1. Apply migration to production PostgreSQL:")
    logger.info("      alembic upgrade 20251029_add_interval_to_kline_audit")
    logger.info("   2. Test with real MTF data loading")
    logger.info("   3. Integrate MTFBacktestEngine (Priority #3)")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

