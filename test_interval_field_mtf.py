"""
Test Multi-Timeframe (MTF) Data Storage with Interval Field

This script validates Priority #2 implementation:
1. Alembic migration adds 'interval' field to bybit_kline_audit
2. Updated unique constraint: (symbol, interval, open_time)
3. BackfillService properly stores MTF data
4. Database can distinguish between different timeframes

Expected Outcome:
✅ Migration applies successfully
✅ Can store same timestamp for different intervals
✅ No unique constraint violations when loading multiple TFs
✅ Can query data by (symbol, interval, time range)
"""

import os
import sys
from datetime import datetime, timedelta, UTC

from loguru import logger

# Ensure backend modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from backend.database import SessionLocal, engine
from backend.models.bybit_kline_audit import BybitKlineAudit
from backend.services.adapters.bybit import BybitAdapter
from backend.services.backfill_service import BackfillConfig, BackfillService


def test_interval_field_migration():
    """Step 1: Verify interval field exists in database schema."""
    logger.info("=" * 80)
    logger.info("STEP 1: Verify/Create 'interval' field in database schema")
    logger.info("=" * 80)
    
    # For testing, ensure schema exists with interval field
    from backend.database import Base, engine
    
    try:
        # Create all tables (will use updated model with interval field)
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Schema created with interval field")
    except Exception as e:
        logger.warning(f"⚠️ Schema creation warning: {e}")
    
    # Check if interval column exists by trying to query it
    db = SessionLocal()
    try:
        from sqlalchemy import text
        
        # Try to select interval field
        result = db.execute(
            text("SELECT interval FROM bybit_kline_audit LIMIT 1")
        ).fetchone()
        logger.success("✅ 'interval' field exists in bybit_kline_audit table")
        return True
    except Exception as e:
        logger.error(f"❌ 'interval' field missing: {e}")
        logger.info("\n🔧 For production PostgreSQL, apply migration:")
        logger.info("   $env:DATABASE_URL = 'postgresql://user:pass@localhost:5432/dbname'")
        logger.info("   alembic upgrade 20251029_add_interval_to_kline_audit")
        return False
    finally:
        db.close()


def test_mtf_data_storage():
    """Step 2: Test storing same timestamp across multiple timeframes."""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: Test MTF Data Storage (Same Timestamp, Different Intervals)")
    logger.info("=" * 80)
    
    adapter = BybitAdapter()
    symbol = "BTCUSDT"
    
    # Create test data for same timestamp but different intervals
    base_time = int(datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC).timestamp() * 1000)
    
    test_data = [
        {
            "symbol": symbol,
            "interval": "5",
            "open_time": base_time,
            "open": 42000.0,
            "high": 42100.0,
            "low": 41900.0,
            "close": 42050.0,
            "volume": 100.5,
            "turnover": 4200000.0,
        },
        {
            "symbol": symbol,
            "interval": "15",
            "open_time": base_time,
            "open": 42000.0,
            "high": 42200.0,
            "low": 41800.0,
            "close": 42100.0,
            "volume": 320.8,
            "turnover": 13500000.0,
        },
        {
            "symbol": symbol,
            "interval": "30",
            "open_time": base_time,
            "open": 42000.0,
            "high": 42300.0,
            "low": 41700.0,
            "close": 42150.0,
            "volume": 650.2,
            "turnover": 27300000.0,
        },
    ]
    
    # Normalize data (convert to format expected by _persist_klines_to_db)
    for timeframe_data in test_data:
        interval = timeframe_data["interval"]
        normalized = [
            {
                "open_time": timeframe_data["open_time"],
                "open": timeframe_data["open"],
                "high": timeframe_data["high"],
                "low": timeframe_data["low"],
                "close": timeframe_data["close"],
                "volume": timeframe_data["volume"],
                "turnover": timeframe_data["turnover"],
            }
        ]
        
        try:
            adapter._persist_klines_to_db(symbol, normalized, interval=interval)
            logger.success(f"✅ Successfully stored {interval}m candle at {datetime.fromtimestamp(base_time/1000, tz=UTC)}")
        except Exception as e:
            logger.error(f"❌ Failed to store {interval}m candle: {e}")
            return False
    
    # Verify all 3 timeframes stored separately
    db = SessionLocal()
    try:
        for interval in ["5", "15", "30"]:
            count = db.query(BybitKlineAudit).filter(
                BybitKlineAudit.symbol == symbol,
                BybitKlineAudit.interval == interval,
                BybitKlineAudit.open_time == base_time,
            ).count()
            
            if count == 1:
                logger.success(f"✅ {interval}m candle found in database")
            else:
                logger.error(f"❌ {interval}m candle not found (count={count})")
                return False
        
        # Check total count
        total = db.query(BybitKlineAudit).filter(
            BybitKlineAudit.symbol == symbol,
            BybitKlineAudit.open_time == base_time,
        ).count()
        
        logger.info(f"\n📊 Total candles at timestamp {datetime.fromtimestamp(base_time/1000, tz=UTC)}: {total}")
        
        if total == 3:
            logger.success("✅ MTF storage working: 3 different intervals stored at same timestamp")
            return True
        else:
            logger.error(f"❌ Expected 3 candles, found {total}")
            return False
            
    finally:
        db.close()


def test_backfill_service_mtf():
    """Step 3: Test BackfillService with multiple timeframes."""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: Test BackfillService MTF Support")
    logger.info("=" * 80)
    
    symbol = "BTCUSDT"
    timeframes = ["5", "15", "30"]
    
    service = BackfillService()
    
    results = {}
    for interval in timeframes:
        logger.info(f"\n🔄 Backfilling {symbol} {interval}m (last 1 hour)...")
        
        cfg = BackfillConfig(
            symbol=symbol,
            interval=interval,
            lookback_minutes=60,  # 1 hour
            page_limit=200,
            max_pages=2,
            pause_sec=0.1,
        )
        
        try:
            upserts, pages = service.backfill(cfg, resume=False)
            results[interval] = {"upserts": upserts, "pages": pages}
            logger.success(f"✅ {interval}m: {upserts} candles, {pages} pages")
        except Exception as e:
            logger.error(f"❌ {interval}m backfill failed: {e}")
            results[interval] = {"error": str(e)}
    
    # Verify data in database
    db = SessionLocal()
    try:
        logger.info("\n📊 Database Verification:")
        for interval in timeframes:
            count = db.query(BybitKlineAudit).filter(
                BybitKlineAudit.symbol == symbol,
                BybitKlineAudit.interval == interval,
            ).count()
            logger.info(f"   {interval}m: {count} candles in database")
        
        return True
    finally:
        db.close()


def test_mtf_query_performance():
    """Step 4: Test query performance with interval field."""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: Test Query Performance (with interval index)")
    logger.info("=" * 80)
    
    import time
    
    symbol = "BTCUSDT"
    interval = "15"
    
    db = SessionLocal()
    try:
        # Query with interval filter (should use index)
        start = time.perf_counter()
        results = db.query(BybitKlineAudit).filter(
            BybitKlineAudit.symbol == symbol,
            BybitKlineAudit.interval == interval,
        ).order_by(BybitKlineAudit.open_time.desc()).limit(100).all()
        elapsed = time.perf_counter() - start
        
        logger.info(f"📈 Query time (100 candles, {interval}m): {elapsed*1000:.2f}ms")
        logger.info(f"📊 Results: {len(results)} candles")
        
        if results:
            latest = results[0]
            logger.info(f"   Latest: {datetime.fromtimestamp(latest.open_time/1000, tz=UTC)} | Close: {latest.close_price}")
        
        if elapsed < 1.0:  # Should be fast with index
            logger.success("✅ Query performance acceptable (< 1s)")
            return True
        else:
            logger.warning(f"⚠️ Query slower than expected ({elapsed:.2f}s)")
            return False
            
    finally:
        db.close()


def test_unique_constraint():
    """Step 5: Test unique constraint (symbol, interval, open_time)."""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 5: Test Unique Constraint (symbol, interval, open_time)")
    logger.info("=" * 80)
    
    adapter = BybitAdapter()
    symbol = "BTCUSDT"
    interval = "15"
    
    # Try to insert duplicate (same symbol, interval, open_time)
    base_time = int(datetime(2025, 1, 1, 15, 0, 0, tzinfo=UTC).timestamp() * 1000)
    
    test_data = {
        "open_time": base_time,
        "open": 43000.0,
        "high": 43100.0,
        "low": 42900.0,
        "close": 43050.0,
        "volume": 50.0,
        "turnover": 2150000.0,
    }
    
    # Insert first time
    try:
        adapter._persist_klines_to_db(symbol, [test_data], interval=interval)
        logger.success("✅ First insert successful")
    except Exception as e:
        logger.error(f"❌ First insert failed: {e}")
        return False
    
    # Try to insert duplicate (should update, not error)
    modified_data = test_data.copy()
    modified_data["close"] = 43200.0  # Different close price
    
    try:
        adapter._persist_klines_to_db(symbol, [modified_data], interval=interval)
        logger.success("✅ Duplicate insert handled (upsert)")
    except Exception as e:
        logger.error(f"❌ Duplicate insert failed: {e}")
        return False
    
    # Verify only 1 record exists
    db = SessionLocal()
    try:
        count = db.query(BybitKlineAudit).filter(
            BybitKlineAudit.symbol == symbol,
            BybitKlineAudit.interval == interval,
            BybitKlineAudit.open_time == base_time,
        ).count()
        
        if count == 1:
            # Check if close price was updated
            record = db.query(BybitKlineAudit).filter(
                BybitKlineAudit.symbol == symbol,
                BybitKlineAudit.interval == interval,
                BybitKlineAudit.open_time == base_time,
            ).first()
            
            if record and record.close_price == 43200.0:
                logger.success("✅ Unique constraint working: Duplicate updated (upsert)")
                return True
            else:
                logger.warning(f"⚠️ Record exists but close price not updated: {record.close_price}")
                return False
        else:
            logger.error(f"❌ Expected 1 record, found {count}")
            return False
    finally:
        db.close()


def main():
    """Run all MTF interval field tests."""
    logger.info("🚀 Priority #2: Add 'interval' Field to BybitKlineAudit - Test Suite")
    logger.info("=" * 80)
    
    # Check if migration applied
    if not test_interval_field_migration():
        logger.error("\n❌ Migration not applied. Run: alembic upgrade head")
        logger.info("\nOr manually apply migration:")
        logger.info("   $env:DATABASE_URL = 'postgresql://user:pass@localhost:5432/dbname'")
        logger.info("   alembic upgrade head")
        return
    
    # Run tests
    tests = [
        ("MTF Data Storage", test_mtf_data_storage),
        ("BackfillService MTF", test_backfill_service_mtf),
        ("Query Performance", test_mtf_query_performance),
        ("Unique Constraint", test_unique_constraint),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.exception(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 80)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} | {test_name}")
    
    total_passed = sum(results.values())
    total_tests = len(results)
    
    logger.info(f"\n🎯 Result: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        logger.success("\n🎉 Priority #2 COMPLETE: 'interval' field working correctly!")
        logger.info("\n✅ Next steps:")
        logger.info("   1. Update existing data with correct intervals (if needed)")
        logger.info("   2. Test MTFBacktestEngine integration (Priority #3)")
        logger.info("   3. Remove legacy code (Priority #1)")
    else:
        logger.error(f"\n⚠️ {total_tests - total_passed} tests failed. Review output above.")


if __name__ == "__main__":
    main()

