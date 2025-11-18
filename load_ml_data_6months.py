"""
Загрузка 6 месяцев исторических данных для ML-оптимизации
Поддержка таймфреймов: 5, 15, 30 минут
С догрузкой данных (не очищает базу)
"""

import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional

import pandas as pd
from pybit.unified_trading import HTTP
from sqlalchemy import select
from sqlalchemy.orm import Session

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.database import SessionLocal, Base
from backend.models.bybit_kline_audit import BybitKlineAudit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/load_ml_data.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class MLDataLoader:
    """
    Загрузка данных для ML-оптимизации с догрузкой
    
    Features:
    - Множественные таймфреймы (5, 15, 30 минут)
    - Догрузка недостающих данных
    - Не очищает существующие данные
    - Прогресс-бар и статистика
    """
    
    def __init__(
        self,
        symbol: str = 'BTCUSDT',
        months: int = 6,
        batch_size: int = 1000
    ):
        """
        Args:
            symbol: Торговая пара (BTCUSDT)
            months: Период загрузки (6 месяцев)
            batch_size: Баров за запрос (макс 1000)
        """
        self.symbol = symbol
        self.months = months
        self.batch_size = min(batch_size, 1000)
        
        # Bybit client
        self.session = HTTP(testnet=False)
        
        # Временной диапазон
        self.end_time = datetime.now(timezone.utc)
        self.start_time = self.end_time - timedelta(days=months * 30)
        
        logger.info(f"📊 ML Data Loader initialized")
        logger.info(f"   Symbol: {symbol}")
        logger.info(f"   Period: {self.start_time.date()} → {self.end_time.date()}")
        logger.info(f"   Duration: {months} months (~{months * 30} days)")
    
    def get_existing_data_range(
        self, 
        interval: str,
        db: Session
    ) -> Optional[tuple]:
        """
        Получить диапазон существующих данных
        
        Returns:
            (min_timestamp, max_timestamp) или None
        """
        try:
            stmt = select(
                BybitKlineAudit.open_time_dt
            ).where(
                BybitKlineAudit.symbol == self.symbol,
                BybitKlineAudit.interval == interval
            ).order_by(
                BybitKlineAudit.open_time_dt
            )
            
            result = db.execute(stmt).all()
            
            if not result:
                return None
            
            timestamps = [row[0] for row in result if row[0]]
            if not timestamps:
                return None
            
            min_ts = min(timestamps)
            max_ts = max(timestamps)
            
            return (min_ts, max_ts)
            
        except Exception as e:
            logger.error(f"Error getting existing range: {e}")
            return None
    
    def load_interval_data(
        self,
        interval: str,
        rate_limit_delay: float = 0.2
    ) -> Dict:
        """
        Загрузить данные для одного таймфрейма с догрузкой
        
        Args:
            interval: '5', '15', '30' (минуты)
            rate_limit_delay: Задержка между запросами (сек)
        
        Returns:
            Статистика загрузки
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"📈 Loading {interval}-minute data for {self.symbol}")
        logger.info(f"{'='*80}")
        
        db = SessionLocal()
        
        try:
            # Проверить существующие данные
            existing_range = self.get_existing_data_range(interval, db)
            
            if existing_range:
                min_ts, max_ts = existing_range
                
                # Ensure timezone awareness for comparison
                if min_ts.tzinfo is None:
                    min_ts = min_ts.replace(tzinfo=timezone.utc)
                if max_ts.tzinfo is None:
                    max_ts = max_ts.replace(tzinfo=timezone.utc)
                
                logger.info(f"✓ Existing data found:")
                logger.info(f"  Range: {min_ts} → {max_ts}")
                logger.info(f"  Duration: {(max_ts - min_ts).days} days")
                
                # Определить что нужно догрузить
                gaps_to_load = []
                
                # Догрузить в начало (если нужно)
                if min_ts > self.start_time:
                    gaps_to_load.append(('backward', self.start_time, min_ts))
                    logger.info(f"  Need to load backward: {self.start_time.date()} → {min_ts.date()}")
                
                # Догрузить в конец (если нужно)
                if max_ts < self.end_time:
                    gaps_to_load.append(('forward', max_ts, self.end_time))
                    logger.info(f"  Need to load forward: {max_ts.date()} → {self.end_time.date()}")
                
                if not gaps_to_load:
                    logger.info(f"✅ Data is up to date! No loading needed.")
                    
                    # Подсчитать количество записей
                    count_stmt = select(BybitKlineAudit).where(
                        BybitKlineAudit.symbol == self.symbol,
                        BybitKlineAudit.interval == interval
                    )
                    total_count = len(db.execute(count_stmt).all())
                    
                    return {
                        'interval': interval,
                        'loaded': 0,
                        'existing': total_count,
                        'total': total_count,
                        'skipped': 0
                    }
            else:
                logger.info(f"ℹ️  No existing data found, loading full range")
                gaps_to_load = [('full', self.start_time, self.end_time)]
            
            # Загрузить недостающие данные
            total_loaded = 0
            total_skipped = 0
            
            for gap_type, start, end in gaps_to_load:
                logger.info(f"\n🔄 Loading {gap_type} gap: {start.date()} → {end.date()}")
                
                current_time = end
                batch_count = 0
                
                while current_time > start:
                    batch_count += 1
                    
                    # Запросить данные
                    try:
                        response = self.session.get_kline(
                            category='spot',
                            symbol=self.symbol,
                            interval=interval,
                            end=int(current_time.timestamp() * 1000),
                            limit=self.batch_size
                        )
                        
                        if response['retCode'] != 0:
                            logger.error(f"API error: {response['retMsg']}")
                            break
                        
                        klines = response['result']['list']
                        
                        if not klines:
                            logger.info(f"No more data available before {current_time.date()}")
                            break
                        
                        # Преобразовать и сохранить
                        records_added = 0
                        records_skipped = 0
                        
                        for kline in klines:
                            open_time_ms = int(kline[0])
                            open_time_dt = datetime.fromtimestamp(
                                open_time_ms / 1000, 
                                tz=timezone.utc
                            )
                            
                            # Проверить дубликаты
                            exists = db.query(BybitKlineAudit).filter_by(
                                symbol=self.symbol,
                                interval=interval,
                                open_time=open_time_ms
                            ).first()
                            
                            if exists:
                                records_skipped += 1
                                continue
                            
                            # Создать запись
                            record = BybitKlineAudit(
                                symbol=self.symbol,
                                interval=interval,
                                open_time=open_time_ms,
                                open_time_dt=open_time_dt,
                                open_price=float(kline[1]),
                                high_price=float(kline[2]),
                                low_price=float(kline[3]),
                                close_price=float(kline[4]),
                                volume=float(kline[5]),
                                turnover=float(kline[6])
                            )
                            record.set_raw(kline)
                            
                            db.add(record)
                            records_added += 1
                        
                        db.commit()
                        
                        total_loaded += records_added
                        total_skipped += records_skipped
                        
                        # Обновить время
                        oldest_kline_ms = int(klines[-1][0])
                        current_time = datetime.fromtimestamp(
                            oldest_kline_ms / 1000,
                            tz=timezone.utc
                        )
                        
                        # Логирование прогресса
                        if batch_count % 10 == 0:
                            progress = (end - current_time) / (end - start) * 100
                            logger.info(
                                f"  Batch {batch_count}: {progress:.1f}% | "
                                f"Added: {records_added} | Skipped: {records_skipped} | "
                                f"Current: {current_time.date()}"
                            )
                        
                        # Rate limiting
                        time.sleep(rate_limit_delay)
                        
                    except Exception as e:
                        logger.error(f"Error loading batch {batch_count}: {e}")
                        db.rollback()
                        break
            
            # Финальная статистика
            count_stmt = select(BybitKlineAudit).where(
                BybitKlineAudit.symbol == self.symbol,
                BybitKlineAudit.interval == interval
            )
            final_count = len(db.execute(count_stmt).all())
            
            logger.info(f"\n✅ Loading complete for {interval}-minute data!")
            logger.info(f"   Loaded: {total_loaded:,} new records")
            logger.info(f"   Skipped: {total_skipped:,} duplicates")
            logger.info(f"   Total in DB: {final_count:,} records")
            
            return {
                'interval': interval,
                'loaded': total_loaded,
                'existing': final_count - total_loaded,
                'total': final_count,
                'skipped': total_skipped
            }
            
        finally:
            db.close()
    
    def load_all_timeframes(
        self,
        intervals: List[str] = ['5', '15', '30'],
        rate_limit_delay: float = 0.2
    ) -> Dict:
        """
        Загрузить все таймфреймы
        
        Args:
            intervals: Список таймфреймов ['5', '15', '30']
            rate_limit_delay: Задержка между запросами
        
        Returns:
            Сводная статистика
        """
        start_time = time.time()
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 Starting ML data loading for {self.symbol}")
        logger.info(f"{'='*80}")
        logger.info(f"Timeframes: {', '.join(intervals)} minutes")
        logger.info(f"Period: {self.months} months")
        logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        results = {}
        
        for interval in intervals:
            try:
                stats = self.load_interval_data(interval, rate_limit_delay)
                results[f'{interval}min'] = stats
            except Exception as e:
                logger.error(f"❌ Failed to load {interval}-minute data: {e}")
                results[f'{interval}min'] = {'error': str(e)}
        
        elapsed = time.time() - start_time
        
        # Итоговая статистика
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 FINAL STATISTICS")
        logger.info(f"{'='*80}")
        
        total_loaded = 0
        total_existing = 0
        total_records = 0
        
        for tf, stats in results.items():
            if 'error' not in stats:
                total_loaded += stats['loaded']
                total_existing += stats['existing']
                total_records += stats['total']
                
                logger.info(f"\n{tf}:")
                logger.info(f"  New records:      {stats['loaded']:,}")
                logger.info(f"  Existing records: {stats['existing']:,}")
                logger.info(f"  Total records:    {stats['total']:,}")
        
        logger.info(f"\nOverall:")
        logger.info(f"  Total loaded:     {total_loaded:,} new records")
        logger.info(f"  Total existing:   {total_existing:,} records")
        logger.info(f"  Total in DB:      {total_records:,} records")
        logger.info(f"  Elapsed time:     {elapsed/60:.1f} minutes")
        logger.info(f"  Finished:         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ ML DATA LOADING COMPLETE!")
        logger.info(f"{'='*80}\n")
        
        return {
            'results': results,
            'total_loaded': total_loaded,
            'total_existing': total_existing,
            'total_records': total_records,
            'elapsed_minutes': elapsed / 60
        }


def main():
    """Main entry point"""
    # Create logs directory
    Path('logs').mkdir(exist_ok=True)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"ML DATA LOADER - 6 MONTHS HISTORICAL DATA")
    logger.info(f"{'='*80}")
    logger.info(f"Purpose: Load data for ML-optimization")
    logger.info(f"Timeframes: 5, 15, 30 minutes")
    logger.info(f"Period: 6 months from {datetime.now().date()}")
    logger.info(f"Mode: INCREMENTAL (dogruzka - не очищает базу)")
    logger.info(f"{'='*80}\n")
    
    # Configuration
    SYMBOL = 'BTCUSDT'
    MONTHS = 6
    INTERVALS = ['5', '15', '30']
    RATE_LIMIT = 0.2  # 5 req/sec
    
    # Create loader
    loader = MLDataLoader(
        symbol=SYMBOL,
        months=MONTHS
    )
    
    try:
        # Load all timeframes
        stats = loader.load_all_timeframes(
            intervals=INTERVALS,
            rate_limit_delay=RATE_LIMIT
        )
        
        # Success
        logger.info("\n🎉 SUCCESS! Data ready for ML-optimization")
        logger.info(f"Total records in database: {stats['total_records']:,}")
        logger.info(f"Time taken: {stats['elapsed_minutes']:.1f} minutes")
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Loading interrupted by user")
        return 1
        
    except Exception as e:
        logger.error(f"\n❌ Loading failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
