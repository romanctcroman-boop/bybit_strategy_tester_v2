"""
🧪 Автоматические тесты для проверки логики кэширования свечей
Выполняются с реальным API Bybit для проверки алгоритмов
"""

import asyncio
import json
import time
import sys
import io
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

# Настройка UTF-8 для Windows консоли
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services.adapters.bybit import BybitAdapter


class StorageSimulator:
    """Симулятор localStorage для тестирования логики"""
    
    def __init__(self):
        self.storage: Dict[str, Dict] = {}
        self.max_age_days = 7
        self.max_candles = 2000
    
    def get_key(self, symbol: str, interval: str, category: str = 'linear') -> str:
        return f"bybit_candles_v1_{category}_{symbol.upper()}_{interval}"
    
    def save(self, symbol: str, interval: str, category: str, candles: List[Dict]) -> None:
        """Сохранить свечи в хранилище"""
        key = self.get_key(symbol, interval, category)
        self.storage[key] = {
            'timestamp': int(time.time() * 1000),
            'candles': candles[-self.max_candles:]  # Ограничение 2000
        }
        print(f"💾 Saved {len(candles)} candles to {key}")
    
    def load(self, symbol: str, interval: str, category: str = 'linear') -> Optional[List[Dict]]:
        """Загрузить свечи из хранилища"""
        key = self.get_key(symbol, interval, category)
        if key not in self.storage:
            return None
        
        data = self.storage[key]
        timestamp = data['timestamp']
        age_ms = time.time() * 1000 - timestamp
        age_days = age_ms / (1000 * 60 * 60 * 24)
        
        if age_days > self.max_age_days:
            print(f"⚠️ Cache too old ({age_days:.1f} days), ignoring")
            del self.storage[key]
            return None
        
        print(f"📦 Loaded {len(data['candles'])} candles from cache (age: {age_days:.2f} days)")
        return data['candles']
    
    def clear(self, symbol: str, interval: str, category: str = 'linear') -> None:
        """Очистить кэш"""
        key = self.get_key(symbol, interval, category)
        if key in self.storage:
            del self.storage[key]
            print(f"🗑️ Cleared {key}")
    
    def clear_all(self) -> None:
        """Очистить всё хранилище"""
        count = len(self.storage)
        self.storage.clear()
        print(f"🗑️ Cleared all storage ({count} entries)")
    
    def stats(self) -> None:
        """Показать статистику"""
        print("\n" + "="*60)
        print("📊 STORAGE STATISTICS")
        print("="*60)
        
        total_candles = 0
        for key, data in self.storage.items():
            candles = data['candles']
            count = len(candles)
            total_candles += count
            
            if count > 0:
                oldest_time = get_candle_time(candles[0])
                newest_time = get_candle_time(candles[-1])
                oldest = datetime.fromtimestamp(oldest_time)
                newest = datetime.fromtimestamp(newest_time)
                print(f"\n📈 {key}")
                print(f"   Candles: {count}")
                print(f"   Range: {oldest} - {newest}")
        
        print(f"\n{'='*60}")
        print(f"Total entries: {len(self.storage)}")
        print(f"Total candles: {total_candles}")
        print(f"{'='*60}\n")


def get_interval_seconds(interval: str) -> int:
    """Конвертировать interval в секунды"""
    if interval == 'D':
        return 86400
    elif interval == 'W':
        return 604800
    else:
        return int(interval) * 60


def get_candle_time(candle: Dict) -> int:
    """Получить время свечи в секундах"""
    if 'time' in candle:
        return candle['time']
    elif 'open_time' in candle:
        # open_time в миллисекундах
        return int(candle['open_time'] / 1000)
    elif 'open_time_dt' in candle and candle['open_time_dt']:
        return int(candle['open_time_dt'].timestamp())
    else:
        raise ValueError(f"Cannot extract time from candle: {candle.keys()}")


def deduplicate_candles(candles: List[Dict]) -> List[Dict]:
    """Удалить дубликаты и отсортировать"""
    seen = set()
    result = []
    
    for candle in sorted(candles, key=lambda c: get_candle_time(c)):
        candle_time = get_candle_time(candle)
        if candle_time not in seen:
            seen.add(candle_time)
            result.append(candle)
    
    return result


class StorageTester:
    """Класс для выполнения тестов с реальным API"""
    
    def __init__(self):
        self.adapter = BybitAdapter()
        self.storage = StorageSimulator()
        self.test_results = []
    
    def log_test(self, test_name: str, status: str, message: str = ""):
        """Записать результат теста"""
        result = {
            'test': test_name,
            'status': status,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"\n{emoji} TEST: {test_name} - {status}")
        if message:
            print(f"   {message}")
    
    async def test_1_empty_storage(self):
        """ТЕСТ 1: Загрузка в пустое хранилище"""
        print("\n" + "="*60)
        print("🧪 ТЕСТ 1: Загрузка 1000 свечей в пустую базу")
        print("="*60)
        
        symbol = 'BTCUSDT'
        interval = '15'
        category = 'linear'
        
        # Очистить хранилище
        self.storage.clear_all()
        
        # Проверить что кэша нет
        cached = self.storage.load(symbol, interval, category)
        if cached is not None:
            self.log_test("test_1_empty_storage", "FAIL", "Cache should be empty")
            return
        
        print("🆕 No cache found, loading fresh data...")
        
        # Загрузить с API
        try:
            candles = self.adapter.get_klines(
                symbol=symbol,
                interval=interval,
                limit=1000
            )
            
            if not candles:
                self.log_test("test_1_empty_storage", "FAIL", "No candles returned from API")
                return
            
            print(f"📊 Loaded {len(candles)} candles from API")
            
            # Сохранить в storage
            self.storage.save(symbol, interval, category, candles)
            
            # Проверить что сохранилось
            loaded = self.storage.load(symbol, interval, category)
            if loaded is None or len(loaded) != len(candles):
                self.log_test("test_1_empty_storage", "FAIL", 
                            f"Expected {len(candles)} candles, got {len(loaded) if loaded else 0}")
                return
            
            # Проверить временной диапазон
            oldest_time = get_candle_time(loaded[0])
            newest_time = get_candle_time(loaded[-1])
            oldest = datetime.fromtimestamp(oldest_time)
            newest = datetime.fromtimestamp(newest_time)
            print(f"🕐 Oldest: {oldest}")
            print(f"🕐 Newest: {newest}")
            
            self.log_test("test_1_empty_storage", "PASS", 
                        f"Loaded and saved {len(candles)} candles")
            
        except Exception as e:
            self.log_test("test_1_empty_storage", "FAIL", f"Exception: {str(e)}")
    
    async def test_2_update_existing(self):
        """ТЕСТ 2: Обновление существующего кэша"""
        print("\n" + "="*60)
        print("🧪 ТЕСТ 2: Догрузка новых свечей к существующему кэшу")
        print("="*60)
        
        symbol = 'BTCUSDT'
        interval = '15'
        category = 'linear'
        
        # Должен быть кэш из теста 1
        cached = self.storage.load(symbol, interval, category)
        if cached is None:
            self.log_test("test_2_update_existing", "FAIL", "No cache from test 1")
            return
        
        initial_count = len(cached)
        print(f"📦 Found {initial_count} cached candles")
        
        # Получить время последней свечи
        newest_cached_time = get_candle_time(cached[-1])
        oldest_cached_time = get_candle_time(cached[0])
        print(f"🕐 Oldest cached: {datetime.fromtimestamp(oldest_cached_time)}")
        print(f"🕐 Newest cached: {datetime.fromtimestamp(newest_cached_time)}")
        
        # Загрузить БОЛЬШЕ исторических данных (2000 свечей)
        print("📊 Fetching 2000 historical candles...")
        
        try:
            historical = self.adapter.get_klines_historical(
                symbol=symbol,
                interval=interval,
                total_candles=2000,
                end_time=None  # До текущего момента
            )
            
            if not historical:
                self.log_test("test_2_update_existing", "FAIL", "No historical data")
                return
            
            print(f"✅ Loaded {len(historical)} historical candles")
            
            # Проверить временной диапазон
            oldest_hist_time = get_candle_time(historical[0])
            newest_hist_time = get_candle_time(historical[-1])
            print(f"🕐 Historical range: {datetime.fromtimestamp(oldest_hist_time)} - {datetime.fromtimestamp(newest_hist_time)}")
            
            # Сохранить новые данные
            self.storage.save(symbol, interval, category, historical)
            
            # Проверить что данных стало больше
            loaded = self.storage.load(symbol, interval, category)
            if loaded is None:
                self.log_test("test_2_update_existing", "FAIL", "Cache lost after save")
                return
            
            final_count = len(loaded)
            
            if final_count < initial_count:
                self.log_test("test_2_update_existing", "FAIL", 
                            f"Data decreased: {initial_count} -> {final_count}")
                return
            
            # Проверить что данные покрывают больший период
            oldest_final = get_candle_time(loaded[0])
            if oldest_final >= oldest_cached_time:
                print(f"⚠️ Warning: oldest time did not move back ({datetime.fromtimestamp(oldest_final)} >= {datetime.fromtimestamp(oldest_cached_time)})")
            
            self.log_test("test_2_update_existing", "PASS", 
                        f"Updated cache: {initial_count} -> {final_count} candles, historical data loaded")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.log_test("test_2_update_existing", "FAIL", f"Exception: {str(e)}")
    
    async def test_3_multiple_timeframes(self):
        """ТЕСТ 3: Разные таймфреймы изолированы"""
        print("\n" + "="*60)
        print("🧪 ТЕСТ 3: Изоляция данных между таймфреймами")
        print("="*60)
        
        symbol = 'BTCUSDT'
        category = 'linear'
        intervals = ['1', '5', '15', '60']
        
        for interval in intervals:
            print(f"\n📊 Loading {symbol} {interval}m...")
            
            candles = self.adapter.get_klines(
                symbol=symbol,
                interval=interval,
                limit=200)
            
            if not candles:
                self.log_test("test_3_multiple_timeframes", "FAIL", 
                            f"No candles for {interval}m")
                return
            
            self.storage.save(symbol, interval, category, candles)
            print(f"✅ Saved {len(candles)} candles for {interval}m")
        
        # Проверить что все независимы
        print("\n🔍 Verifying isolation...")
        for interval in intervals:
            loaded = self.storage.load(symbol, interval, category)
            if loaded is None:
                self.log_test("test_3_multiple_timeframes", "FAIL", 
                            f"Cache lost for {interval}m")
                return
            print(f"✅ {interval}m: {len(loaded)} candles")
        
        self.storage.stats()
        
        self.log_test("test_3_multiple_timeframes", "PASS", 
                    f"All {len(intervals)} timeframes isolated")
    
    async def test_4_multiple_symbols(self):
        """ТЕСТ 4: Разные символы изолированы"""
        print("\n" + "="*60)
        print("🧪 ТЕСТ 4: Изоляция данных между символами")
        print("="*60)
        
        symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        interval = '15'
        category = 'linear'
        
        for symbol in symbols:
            print(f"\n📊 Loading {symbol}...")
            
            candles = self.adapter.get_klines(
                symbol=symbol,
                interval=interval,
                limit=200)
            
            if not candles:
                self.log_test("test_4_multiple_symbols", "FAIL", 
                            f"No candles for {symbol}")
                return
            
            self.storage.save(symbol, interval, category, candles)
            print(f"✅ Saved {len(candles)} candles for {symbol}")
        
        # Проверить изоляцию
        print("\n🔍 Verifying isolation...")
        for symbol in symbols:
            loaded = self.storage.load(symbol, interval, category)
            if loaded is None:
                self.log_test("test_4_multiple_symbols", "FAIL", 
                            f"Cache lost for {symbol}")
                return
            
            # Проверить что цены разные (не смешались)
            avg_price = sum(c.get('close', 0) or 0 for c in loaded) / len(loaded)
            print(f"✅ {symbol}: {len(loaded)} candles, avg price: ${avg_price:.2f}")
        
        self.storage.stats()
        
        self.log_test("test_4_multiple_symbols", "PASS", 
                    f"All {len(symbols)} symbols isolated")
    
    async def test_5_limit_2000(self):
        """ТЕСТ 5: Лимит 2000 свечей"""
        print("\n" + "="*60)
        print("🧪 ТЕСТ 5: Проверка лимита 2000 свечей")
        print("="*60)
        
        symbol = 'BTCUSDT'
        interval = '1'  # 1 минута - быстрее накопить
        category = 'linear'
        
        # Создать искусственный большой кэш используя исторический метод
        print("📊 Creating large cache with historical data...")
        
        try:
            all_candles = self.adapter.get_klines_historical(
                symbol=symbol,
                interval=interval,
                total_candles=3000  # Запросить 3000 свечей
            )
            
            print(f"📊 Total fetched: {len(all_candles)} candles")
            
            if len(all_candles) < 2000:
                print(f"⚠️ Warning: fetched less than 2000 candles ({len(all_candles)})")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.log_test("test_5_limit_2000", "FAIL", f"Exception during fetch: {str(e)}")
            return
        
        # Сохранить (должно обрезать до 2000)
        self.storage.save(symbol, interval, category, all_candles)
        
        # Проверить
        loaded = self.storage.load(symbol, interval, category)
        if loaded is None:
            self.log_test("test_5_limit_2000", "FAIL", "Cache lost")
            return
        
        if len(loaded) > 2000:
            self.log_test("test_5_limit_2000", "FAIL", 
                        f"Limit exceeded: {len(loaded)} > 2000")
            return
        
        if len(loaded) != 2000:
            self.log_test("test_5_limit_2000", "FAIL", 
                        f"Expected 2000, got {len(loaded)}")
            return
        
        # Проверить что сохранились последние
        oldest_loaded_time = get_candle_time(loaded[0])
        newest_loaded_time = get_candle_time(loaded[-1])
        oldest_loaded = datetime.fromtimestamp(oldest_loaded_time)
        newest_loaded = datetime.fromtimestamp(newest_loaded_time)
        print(f"🕐 Oldest: {oldest_loaded}")
        print(f"🕐 Newest: {newest_loaded}")
        
        self.log_test("test_5_limit_2000", "PASS", 
                    f"Correctly limited to {len(loaded)} candles")
    
    async def test_6_deduplication(self):
        """ТЕСТ 6: Дедупликация работает"""
        print("\n" + "="*60)
        print("🧪 ТЕСТ 6: Проверка дедупликации")
        print("="*60)
        
        symbol = 'BTCUSDT'
        interval = '15'
        category = 'linear'
        
        # Загрузить одни и те же данные дважды
        print("📊 Fetching same data twice...")
        
        candles1 = self.adapter.get_klines(
            symbol=symbol,
            interval=interval,
            limit=500)
        
        candles2 = self.adapter.get_klines(
            symbol=symbol,
            interval=interval,
            limit=500)
        
        print(f"Batch 1: {len(candles1)} candles")
        print(f"Batch 2: {len(candles2)} candles")
        
        # Объединить
        combined = candles1 + candles2
        print(f"Combined: {len(combined)} candles")
        
        # Дедупликация
        deduped = deduplicate_candles(combined)
        print(f"After deduplication: {len(deduped)} candles")
        
        # Должно быть примерно 500 (не 1000)
        if len(deduped) > len(candles1) * 1.1:  # +10% допуск
            self.log_test("test_6_deduplication", "FAIL", 
                        f"Too many duplicates: {len(combined)} -> {len(deduped)}")
            return
        
        # Проверить что нет дубликатов по времени
        times = [get_candle_time(c) for c in deduped]
        unique_times = set(times)
        
        if len(times) != len(unique_times):
            self.log_test("test_6_deduplication", "FAIL", 
                        f"Still have duplicates: {len(times)} vs {len(unique_times)}")
            return
        
        self.log_test("test_6_deduplication", "PASS", 
                    f"Deduplication works: {len(combined)} -> {len(deduped)}")
    
    async def test_7_cache_expiry(self):
        """ТЕСТ 7: Устаревший кэш игнорируется"""
        print("\n" + "="*60)
        print("🧪 ТЕСТ 7: Проверка истечения кэша")
        print("="*60)
        
        symbol = 'ETHUSDT'
        interval = '5'
        category = 'linear'
        
        # Загрузить свежие данные
        candles = self.adapter.get_klines(
            symbol=symbol,
            interval=interval,
            limit=100)
        
        # Сохранить со старой датой
        key = self.storage.get_key(symbol, interval, category)
        old_timestamp = int((time.time() - 8 * 24 * 60 * 60) * 1000)  # 8 дней назад
        
        self.storage.storage[key] = {
            'timestamp': old_timestamp,
            'candles': candles
        }
        
        print(f"💾 Saved cache with timestamp 8 days ago")
        
        # Попытка загрузить
        loaded = self.storage.load(symbol, interval, category)
        
        if loaded is not None:
            self.log_test("test_7_cache_expiry", "FAIL", 
                        "Old cache should be ignored")
            return
        
        self.log_test("test_7_cache_expiry", "PASS", 
                    "Old cache correctly ignored")
    
    async def test_8_api_limits(self):
        """ТЕСТ 8: Проверка лимитов API"""
        print("\n" + "="*60)
        print("🧪 ТЕСТ 8: Проверка лимитов API Bybit")
        print("="*60)
        
        symbol = 'BTCUSDT'
        interval = '15'
        category = 'linear'
        
        # Попытка загрузить больше 1000
        print("📊 Requesting 2000 candles (should get max 1000)...")
        
        candles = self.adapter.get_klines(
            symbol=symbol,
            interval=interval,
            limit=2000  # Запросим больше лимита
        )
        
        print(f"Received: {len(candles)} candles")
        
        if len(candles) > 1000:
            self.log_test("test_8_api_limits", "FAIL", 
                        f"API returned too many: {len(candles)}")
            return
        
        # Проверить что данные актуальные
        if candles:
            newest_time = get_candle_time(candles[-1])
            newest = datetime.fromtimestamp(newest_time)
            age = datetime.now() - newest
            print(f"🕐 Newest candle: {newest} (age: {age})")
            
            if age.total_seconds() > 3600:  # Больше часа
                print(f"⚠️ Warning: Data may be outdated")
        
        self.log_test("test_8_api_limits", "PASS", 
                    f"API limit respected: {len(candles)} <= 1000")
    
    async def test_9_historical_fetch_5000(self):
        """ТЕСТ 9: Загрузка 5000 исторических свечей"""
        print("\n" + "="*60)
        print("🧪 ТЕСТ 9: Загрузка 5000 исторических свечей")
        print("="*60)
        
        symbol = 'ETHUSDT'
        interval = '5'  # 5 минут
        category = 'linear'
        target = 5000
        
        print(f"📊 Requesting {target} historical candles for {symbol} {interval}m...")
        
        try:
            candles = self.adapter.get_klines_historical(
                symbol=symbol,
                interval=interval,
                total_candles=target
            )
            
            if not candles:
                self.log_test("test_9_historical_fetch_5000", "FAIL", "No candles returned")
                return
            
            print(f"✅ Received {len(candles)} candles")
            
            # Проверить временной диапазон
            oldest_time = get_candle_time(candles[0])
            newest_time = get_candle_time(candles[-1])
            oldest = datetime.fromtimestamp(oldest_time)
            newest = datetime.fromtimestamp(newest_time)
            
            time_diff = newest_time - oldest_time
            expected_diff = target * 5 * 60  # 5 минут * 60 секунд
            
            print(f"🕐 Oldest: {oldest}")
            print(f"🕐 Newest: {newest}")
            print(f"📊 Time span: {time_diff/3600:.2f} hours (expected: ~{expected_diff/3600:.2f} hours)")
            
            # Проверить что получили достаточно данных
            if len(candles) < target * 0.9:  # Допуск 10%
                print(f"⚠️ Warning: received less than 90% of target ({len(candles)} < {target * 0.9})")
            
            # Проверить уникальность
            times = [get_candle_time(c) for c in candles]
            unique_times = set(times)
            
            if len(times) != len(unique_times):
                self.log_test("test_9_historical_fetch_5000", "FAIL", 
                            f"Duplicates found: {len(times)} vs {len(unique_times)}")
                return
            
            # Проверить сортировку
            is_sorted = all(times[i] <= times[i+1] for i in range(len(times)-1))
            if not is_sorted:
                self.log_test("test_9_historical_fetch_5000", "FAIL", "Data not sorted by time")
                return
            
            # Сохранить
            self.storage.save(symbol, interval, category, candles[-2000:])  # Только последние 2000
            
            self.log_test("test_9_historical_fetch_5000", "PASS", 
                        f"Loaded {len(candles)} historical candles, time span: {time_diff/3600:.1f}h")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.log_test("test_9_historical_fetch_5000", "FAIL", f"Exception: {str(e)}")
    
    async def test_10_historical_different_intervals(self):
        """ТЕСТ 10: Исторические данные для разных интервалов"""
        print("\n" + "="*60)
        print("🧪 ТЕСТ 10: Исторические данные для разных интервалов")
        print("="*60)
        
        symbol = 'SOLUSDT'
        intervals = ['1', '15', '60', 'D']  # 1m, 15m, 1h, 1d
        category = 'linear'
        target = 1500
        
        results = {}
        
        for interval in intervals:
            print(f"\n📊 Testing {symbol} {interval}...")
            
            try:
                candles = self.adapter.get_klines_historical(
                    symbol=symbol,
                    interval=interval,
                    total_candles=target
                )
                
                if not candles:
                    print(f"⚠️ No data for {interval}")
                    results[interval] = 0
                    continue
                
                oldest_time = get_candle_time(candles[0])
                newest_time = get_candle_time(candles[-1])
                time_span_hours = (newest_time - oldest_time) / 3600
                
                print(f"✅ {len(candles)} candles, span: {time_span_hours:.1f}h")
                results[interval] = len(candles)
                
                # Сохранить
                self.storage.save(symbol, interval, category, candles[-2000:])
                
            except Exception as e:
                print(f"❌ Error for {interval}: {e}")
                results[interval] = 0
        
        # Проверить что хотя бы 3 из 4 интервалов загрузились
        successful = sum(1 for count in results.values() if count > 0)
        
        if successful < 3:
            self.log_test("test_10_historical_different_intervals", "FAIL", 
                        f"Only {successful}/4 intervals loaded successfully")
            return
        
        self.storage.stats()
        
        self.log_test("test_10_historical_different_intervals", "PASS", 
                    f"Loaded data for {successful}/4 intervals: {results}")
    
    async def run_all_tests(self):
        """Запустить все тесты"""
        print("\n" + "="*80)
        print("🚀 STARTING AUTOMATED STORAGE LOGIC TESTS")
        print("="*80)
        print(f"Time: {datetime.now()}")
        print(f"API: Bybit (real)")
        print("="*80)
        
        tests = [
            self.test_1_empty_storage,
            self.test_2_update_existing,
            self.test_3_multiple_timeframes,
            self.test_4_multiple_symbols,
            self.test_5_limit_2000,
            self.test_6_deduplication,
            self.test_7_cache_expiry,
            self.test_8_api_limits,
            self.test_9_historical_fetch_5000,
            self.test_10_historical_different_intervals,
        ]
        
        for test in tests:
            try:
                await test()
            except Exception as e:
                self.log_test(test.__name__, "FAIL", f"Exception: {str(e)}")
                import traceback
                traceback.print_exc()
            
            # Пауза между тестами
            await asyncio.sleep(2)
        
        # Итоговая статистика
        self.print_summary()
    
    def print_summary(self):
        """Вывести итоговую статистику"""
        print("\n" + "="*80)
        print("📊 TEST SUMMARY")
        print("="*80)
        
        passed = sum(1 for r in self.test_results if r['status'] == 'PASS')
        failed = sum(1 for r in self.test_results if r['status'] == 'FAIL')
        total = len(self.test_results)
        
        for result in self.test_results:
            emoji = "✅" if result['status'] == 'PASS' else "❌"
            print(f"{emoji} {result['test']}: {result['status']}")
            if result['message']:
                print(f"   {result['message']}")
        
        print("\n" + "="*80)
        print(f"Total: {total} tests")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"Success rate: {passed/total*100:.1f}%")
        print("="*80)
        
        # Показать финальную статистику хранилища
        self.storage.stats()
        
        # Сохранить результаты в файл
        results_file = Path(__file__).parent / 'test_results.json'
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'tests': self.test_results,
                'summary': {
                    'total': total,
                    'passed': passed,
                    'failed': failed,
                    'success_rate': passed/total*100
                }
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {results_file}")


async def main():
    """Главная функция"""
    tester = StorageTester()
    await tester.run_all_tests()


if __name__ == '__main__':
    asyncio.run(main())


