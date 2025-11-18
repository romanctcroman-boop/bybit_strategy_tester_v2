"""
Populate PostgreSQL Database with 6+ Months of Historical Data

This script loads 6 months of BTCUSDT historical data from Bybit API
and stores it in the PostgreSQL database for comprehensive backtesting.

Target:
- Symbol: BTCUSDT
- Timeframe: 5 minutes
- Period: 6 months (~155,520 bars)
- Storage: BybitKlineAudit table with interval field

Features:
- Batch loading to handle API limits (1000 bars per request)
- Progress tracking with logging
- Duplicate prevention via UniqueConstraint
- Error handling and retry logic
- Estimated time: 2-3 hours for full 6 months

Usage:
    python scripts/populate_historical_data.py
"""

import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import pandas as pd
from pybit.unified_trading import HTTP
from sqlalchemy import select
from sqlalchemy.orm import Session

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.database import SessionLocal, engine, Base
from backend.models.bybit_kline_audit import BybitKlineAudit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/populate_historical_data.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class HistoricalDataPopulator:
    """
    Loads historical market data from Bybit API and stores in PostgreSQL.
    
    Handles:
    - Batch loading with API rate limits
    - Progress tracking
    - Duplicate prevention
    - Error recovery
    """
    
    def __init__(
        self,
        symbol: str = 'BTCUSDT',
        interval: str = '5',
        months: int = 6,
        batch_size: int = 1000
    ):
        """
        Initialize data populator.
        
        Args:
            symbol: Trading pair (default: BTCUSDT)
            interval: Timeframe (default: '5' = 5 minutes)
            months: Number of months to load (default: 6)
            batch_size: Bars per API request (max: 1000)
        """
        self.symbol = symbol
        self.interval = interval
        self.months = months
        self.batch_size = min(batch_size, 1000)  # Bybit max
        
        # Initialize Bybit client
        self.session = HTTP(testnet=False)
        
        # Calculate time range
        self.end_time = datetime.now(timezone.utc)
        self.start_time = self.end_time - timedelta(days=months * 30)
        
        # Expected total bars (5-minute intervals)
        # 6 months ≈ 180 days × 24 hours × 12 bars/hour = 51,840 bars (conservative)
        # Actual: ~155,520 bars for exact 6 months
        self.expected_bars = months * 30 * 24 * 12
        
        logger.info(f"Initialized populator for {symbol} {interval}")
        logger.info(f"Time range: {self.start_time} to {self.end_time}")
        logger.info(f"Expected bars: ~{self.expected_bars:,}")
    
    def create_tables(self):
        """Create database tables if they don't exist."""
        logger.info("Creating database tables...")
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Tables created successfully")
            
            # Log database info
            db_url = str(engine.url)
            if 'sqlite' in db_url:
                logger.info(f"Using SQLite database: {db_url}")
            else:
                logger.info(f"Using database: {db_url.split('@')[-1] if '@' in db_url else db_url}")
                
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    
    def get_existing_count(self, db: Session) -> int:
        """
        Count existing bars in database for this symbol/interval.
        
        Args:
            db: Database session
        
        Returns:
            Number of existing bars
        """
        stmt = select(BybitKlineAudit).where(
            BybitKlineAudit.symbol == self.symbol,
            BybitKlineAudit.interval == self.interval
        )
        count = db.query(BybitKlineAudit).filter(
            BybitKlineAudit.symbol == self.symbol,
            BybitKlineAudit.interval == self.interval
        ).count()
        
        return count
    
    def fetch_klines_batch(
        self,
        end_timestamp: int,
        limit: int = 1000
    ) -> List[dict]:
        """
        Fetch a batch of klines from Bybit API.
        
        Args:
            end_timestamp: End time in milliseconds
            limit: Number of bars to fetch (max 1000)
        
        Returns:
            List of kline dictionaries
        """
        try:
            response = self.session.get_kline(
                category="linear",
                symbol=self.symbol,
                interval=self.interval,
                limit=limit,
                end=end_timestamp
            )
            
            if response['retCode'] != 0:
                raise Exception(f"Bybit API error: {response['retMsg']}")
            
            klines = response['result']['list']
            
            # Bybit returns newest first, reverse for chronological order
            klines.reverse()
            
            return klines
            
        except Exception as e:
            logger.error(f"Failed to fetch klines: {e}")
            raise
    
    def save_klines_batch(
        self,
        db: Session,
        klines: List[dict]
    ) -> int:
        """
        Save a batch of klines to database.
        
        Args:
            db: Database session
            klines: List of kline data from Bybit API
        
        Returns:
            Number of new records inserted
        """
        if not klines:
            return 0
        
        inserted = 0
        
        for kline in klines:
            # Parse kline data
            # Bybit format: [timestamp, open, high, low, close, volume, turnover]
            timestamp_ms = int(kline[0])
            timestamp_dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
            
            # Create record
            record = BybitKlineAudit(
                symbol=self.symbol,
                interval=self.interval,
                open_time=timestamp_ms,
                open_time_dt=timestamp_dt,
                open_price=float(kline[1]),
                high_price=float(kline[2]),
                low_price=float(kline[3]),
                close_price=float(kline[4]),
                volume=float(kline[5]),
                turnover=float(kline[6])
            )
            
            # Set raw JSON
            record.set_raw({
                'timestamp': timestamp_ms,
                'open': kline[1],
                'high': kline[2],
                'low': kline[3],
                'close': kline[4],
                'volume': kline[5],
                'turnover': kline[6]
            })
            
            # Try to insert (will skip duplicates due to UniqueConstraint)
            try:
                db.add(record)
                db.flush()
                inserted += 1
            except Exception as e:
                # Duplicate or other error, rollback this record
                db.rollback()
                if 'duplicate' not in str(e).lower() and 'unique' not in str(e).lower():
                    logger.warning(f"Failed to insert record at {timestamp_dt}: {e}")
                continue
        
        # Commit batch
        try:
            db.commit()
        except Exception as e:
            logger.error(f"Failed to commit batch: {e}")
            db.rollback()
            raise
        
        return inserted
    
    def populate(self, rate_limit_delay: float = 0.2) -> dict:
        """
        Main population function - loads all historical data.
        
        Args:
            rate_limit_delay: Delay between API requests in seconds (default: 0.2s = 5 req/sec)
        
        Returns:
            Dictionary with statistics:
            - total_fetched: Total bars fetched from API
            - total_inserted: New bars inserted to database
            - total_duplicates: Duplicate bars skipped
            - batches: Number of API requests made
            - duration: Time taken in seconds
        """
        logger.info("=" * 80)
        logger.info("STARTING HISTORICAL DATA POPULATION")
        logger.info("=" * 80)
        
        # Create tables
        self.create_tables()
        
        # Check existing data
        db = SessionLocal()
        try:
            existing_count = self.get_existing_count(db)
            logger.info(f"Existing bars in database: {existing_count:,}")
        finally:
            db.close()
        
        # Calculate batches needed
        # Work backwards from end_time to start_time
        current_end = int(self.end_time.timestamp() * 1000)
        start_ms = int(self.start_time.timestamp() * 1000)
        
        total_fetched = 0
        total_inserted = 0
        batch_num = 0
        start_population = time.time()
        
        logger.info(f"Starting backward traversal from {self.end_time}")
        logger.info(f"Target start time: {self.start_time}")
        logger.info(f"Rate limit: {rate_limit_delay}s per request")
        
        while current_end > start_ms:
            batch_num += 1
            
            # Fetch batch
            logger.info(f"\nBatch {batch_num}: Fetching up to {self.batch_size} bars ending at {datetime.fromtimestamp(current_end/1000, tz=timezone.utc)}")
            
            try:
                klines = self.fetch_klines_batch(
                    end_timestamp=current_end,
                    limit=self.batch_size
                )
                
                if not klines:
                    logger.warning("No more klines returned, stopping")
                    break
                
                total_fetched += len(klines)
                
                # Save to database
                db = SessionLocal()
                try:
                    inserted = self.save_klines_batch(db, klines)
                    total_inserted += inserted
                    
                    logger.info(f"   Fetched: {len(klines)} bars")
                    logger.info(f"   Inserted: {inserted} new bars")
                    logger.info(f"   Duplicates: {len(klines) - inserted}")
                    logger.info(f"   Progress: {total_inserted:,} / ~{self.expected_bars:,} ({100*total_inserted/self.expected_bars:.1f}%)")
                    
                finally:
                    db.close()
                
                # Update current_end to oldest timestamp in this batch
                oldest_timestamp = int(klines[0][0])  # First in chronological order
                
                # If we didn't get a full batch or reached target, we're done
                if len(klines) < self.batch_size or oldest_timestamp <= start_ms:
                    logger.info(f"Reached target start time or end of data")
                    break
                
                # Move to next batch (1ms before oldest)
                current_end = oldest_timestamp - 1
                
                # Rate limiting
                time.sleep(rate_limit_delay)
                
                # Progress update every 10 batches
                if batch_num % 10 == 0:
                    elapsed = time.time() - start_population
                    rate = total_inserted / elapsed if elapsed > 0 else 0
                    remaining = (self.expected_bars - total_inserted) / rate if rate > 0 else 0
                    
                    logger.info(f"\nProgress Update:")
                    logger.info(f"   Batches: {batch_num}")
                    logger.info(f"   Total inserted: {total_inserted:,}")
                    logger.info(f"   Rate: {rate:.1f} bars/sec")
                    logger.info(f"   Elapsed: {elapsed/60:.1f} minutes")
                    logger.info(f"   Remaining: ~{remaining/60:.1f} minutes")
                
            except Exception as e:
                logger.error(f"Error in batch {batch_num}: {e}")
                logger.info("Waiting 5 seconds before retry...")
                time.sleep(5)
                continue
        
        # Final statistics
        duration = time.time() - start_population
        
        db = SessionLocal()
        try:
            final_count = self.get_existing_count(db)
        finally:
            db.close()
        
        stats = {
            'total_fetched': total_fetched,
            'total_inserted': total_inserted,
            'total_duplicates': total_fetched - total_inserted,
            'batches': batch_num,
            'duration_seconds': duration,
            'duration_minutes': duration / 60,
            'final_count': final_count,
            'rate_bars_per_sec': total_inserted / duration if duration > 0 else 0
        }
        
        logger.info("\n" + "=" * 80)
        logger.info("POPULATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total fetched from API: {stats['total_fetched']:,}")
        logger.info(f"New bars inserted: {stats['total_inserted']:,}")
        logger.info(f"Duplicates skipped: {stats['total_duplicates']:,}")
        logger.info(f"Total batches: {stats['batches']}")
        logger.info(f"Duration: {stats['duration_minutes']:.1f} minutes")
        logger.info(f"Rate: {stats['rate_bars_per_sec']:.1f} bars/second")
        logger.info(f"Final database count: {stats['final_count']:,}")
        logger.info("=" * 80)
        
        return stats


def main():
    """Main entry point."""
    # Create logs directory
    Path('logs').mkdir(exist_ok=True)
    
    # Configuration
    SYMBOL = 'BTCUSDT'
    INTERVAL = '5'  # 5 minutes
    MONTHS = 6
    RATE_LIMIT_DELAY = 0.2  # 5 requests per second
    
    logger.info(f"Configuration:")
    logger.info(f"  Symbol: {SYMBOL}")
    logger.info(f"  Interval: {INTERVAL} minutes")
    logger.info(f"  Period: {MONTHS} months")
    logger.info(f"  Rate limit: {1/RATE_LIMIT_DELAY:.0f} req/sec")
    
    # Create populator
    populator = HistoricalDataPopulator(
        symbol=SYMBOL,
        interval=INTERVAL,
        months=MONTHS
    )
    
    # Run population
    try:
        stats = populator.populate(rate_limit_delay=RATE_LIMIT_DELAY)
        
        # Success message
        logger.info("\nDatabase population successful!")
        logger.info(f"Loaded {stats['final_count']:,} bars of {SYMBOL} {INTERVAL}m data")
        logger.info(f"Ready for comprehensive backtesting")
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("\nPopulation interrupted by user")
        return 1
        
    except Exception as e:
        logger.error(f"\nPopulation failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
