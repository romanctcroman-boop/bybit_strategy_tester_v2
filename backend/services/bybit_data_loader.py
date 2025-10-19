"""
BybitDataLoader - Интеграция с Bybit API для загрузки исторических данных

Функционал:
- Загрузка OHLCV свечей через REST API
- Поддержка всех таймфреймов (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
- Автоматическая пагинация для больших периодов
- Rate limiting (10 req/sec для публичных endpoints)
- Валидация и конвертация данных
- Сохранение в базу данных через DataService
"""

import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.services.data_service import DataService

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BybitDataLoader:
    """
    Загрузчик исторических данных с Bybit
    
    API Documentation:
    https://bybit-exchange.github.io/docs/v5/market/kline
    
    Примеры использования:
        loader = BybitDataLoader()
        
        # Загрузить последние 1000 свечей
        candles = loader.fetch_klines('BTCUSDT', '15', limit=1000)
        
        # Загрузить за период
        candles = loader.fetch_klines_range(
            'BTCUSDT', '15',
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31)
        )
        
        # Загрузить и сохранить в БД
        count = loader.load_and_save('BTCUSDT', '15', days_back=30)
    """
    
    # Bybit API endpoints
    BASE_URL = "https://api.bybit.com"
    KLINE_ENDPOINT = "/v5/market/kline"
    
    # Таймфреймы (в минутах для конвертации)
    TIMEFRAME_MAP = {
        '1': 1,
        '3': 3,
        '5': 5,
        '15': 15,
        '30': 30,
        '60': 60,
        '120': 120,
        '240': 240,
        '360': 360,
        '720': 720,
        'D': 1440,
        'W': 10080,
        'M': 43200
    }
    
    # Лимиты API
    MAX_CANDLES_PER_REQUEST = 1000  # Максимум свечей за один запрос
    RATE_LIMIT_DELAY = 0.1  # 100ms между запросами (10 req/sec)
    
    def __init__(self, testnet: bool = False):
        """
        Инициализация загрузчика
        
        Args:
            testnet: Использовать testnet API (True) или mainnet (False)
        """
        self.testnet = testnet
        if testnet:
            self.BASE_URL = "https://api-testnet.bybit.com"
        
        # HTTP сессия с retry механизмом
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Счётчик запросов для rate limiting
        self.last_request_time = 0
    
    def _rate_limit(self):
        """Применить rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполнить запрос к API
        
        Args:
            params: Параметры запроса
            
        Returns:
            JSON ответ
            
        Raises:
            Exception: При ошибке API
        """
        self._rate_limit()
        
        url = f"{self.BASE_URL}{self.KLINE_ENDPOINT}"
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Проверка ответа Bybit
            if data.get('retCode') != 0:
                error_msg = data.get('retMsg', 'Unknown error')
                raise Exception(f"Bybit API error: {error_msg}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def _convert_timeframe(self, timeframe: str) -> str:
        """
        Конвертировать таймфрейм в формат Bybit
        
        Args:
            timeframe: Наш формат (1, 5, 15, 60, 240, D)
            
        Returns:
            Формат Bybit (1, 5, 15, 60, 240, D)
        """
        # Bybit использует те же обозначения
        if timeframe not in self.TIMEFRAME_MAP:
            raise ValueError(f"Invalid timeframe: {timeframe}. Valid: {list(self.TIMEFRAME_MAP.keys())}")
        return timeframe
    
    def _timestamp_to_ms(self, dt: datetime) -> int:
        """Конвертировать datetime в миллисекунды (Unix timestamp)"""
        return int(dt.timestamp() * 1000)
    
    def _ms_to_datetime(self, ms: int) -> datetime:
        """Конвертировать миллисекунды в datetime"""
        return datetime.fromtimestamp(ms / 1000)
    
    def _parse_candle(self, raw_candle: List) -> Dict[str, Any]:
        """
        Парсинг свечи из формата Bybit в наш формат
        
        Bybit формат: [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]
        
        Args:
            raw_candle: Сырые данные свечи
            
        Returns:
            Словарь с данными свечи
        """
        return {
            'timestamp': self._ms_to_datetime(int(raw_candle[0])),
            'open': float(raw_candle[1]),
            'high': float(raw_candle[2]),
            'low': float(raw_candle[3]),
            'close': float(raw_candle[4]),
            'volume': float(raw_candle[5]),
            'quote_volume': float(raw_candle[6]) if len(raw_candle) > 6 else None
        }
    
    def fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Загрузить свечи (один запрос)
        
        Args:
            symbol: Торговая пара (BTCUSDT, ETHUSDT)
            timeframe: Таймфрейм (1, 5, 15, 60, 240, D)
            start_time: Начало периода (если None, то последние свечи)
            end_time: Конец периода
            limit: Количество свечей (max 1000)
            
        Returns:
            Список свечей
        """
        if limit > self.MAX_CANDLES_PER_REQUEST:
            limit = self.MAX_CANDLES_PER_REQUEST
        
        params = {
            'category': 'linear',  # Линейные perpetual контракты
            'symbol': symbol,
            'interval': self._convert_timeframe(timeframe),
            'limit': limit
        }
        
        if start_time:
            params['start'] = self._timestamp_to_ms(start_time)
        
        if end_time:
            params['end'] = self._timestamp_to_ms(end_time)
        
        logger.info(f"Fetching {symbol} {timeframe} candles (limit={limit})")
        
        response = self._make_request(params)
        
        # Парсинг свечей
        raw_candles = response.get('result', {}).get('list', [])
        candles = [self._parse_candle(c) for c in raw_candles]
        
        # Bybit возвращает в обратном порядке (новые первые)
        candles.reverse()
        
        logger.info(f"Fetched {len(candles)} candles")
        
        return candles
    
    def fetch_klines_range(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
        verbose: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Загрузить свечи за период (с автоматической пагинацией)
        
        Если период > 1000 свечей, выполняется несколько запросов.
        
        Args:
            symbol: Торговая пара
            timeframe: Таймфрейм
            start_time: Начало периода
            end_time: Конец периода
            verbose: Выводить прогресс
            
        Returns:
            Список всех свечей за период
        """
        # Normalize timezones - ensure naive datetime for comparison
        if isinstance(start_time, datetime) and start_time.tzinfo is not None:
            start_time = start_time.replace(tzinfo=None)
        if isinstance(end_time, datetime) and end_time.tzinfo is not None:
            end_time = end_time.replace(tzinfo=None)
        
        all_candles = []
        current_start = start_time
        
        # Рассчитать количество запросов
        timeframe_minutes = self.TIMEFRAME_MAP[timeframe]
        total_minutes = (end_time - start_time).total_seconds() / 60
        estimated_candles = int(total_minutes / timeframe_minutes)
        estimated_requests = (estimated_candles // self.MAX_CANDLES_PER_REQUEST) + 1
        
        if verbose:
            logger.info(f"Estimated {estimated_candles} candles, {estimated_requests} requests")
        
        request_count = 0
        
        while current_start < end_time:
            # Загрузить порцию
            candles = self.fetch_klines(
                symbol=symbol,
                timeframe=timeframe,
                start_time=current_start,
                end_time=end_time,
                limit=self.MAX_CANDLES_PER_REQUEST
            )
            
            if not candles:
                break
            
            all_candles.extend(candles)
            request_count += 1
            
            # Сдвинуть start_time на последнюю свечу (normalize timezone)
            last_candle_time = candles[-1]['timestamp']
            if isinstance(last_candle_time, datetime) and last_candle_time.tzinfo is not None:
                last_candle_time = last_candle_time.replace(tzinfo=None)
            current_start = last_candle_time + timedelta(minutes=timeframe_minutes)
            
            if verbose and request_count % 5 == 0:
                logger.info(f"Progress: {len(all_candles)} candles loaded ({request_count} requests)")
        
        if verbose:
            logger.info(f"Total: {len(all_candles)} candles loaded ({request_count} requests)")
        
        return all_candles
    
    def load_and_save(
        self,
        symbol: str,
        timeframe: str,
        days_back: int = 30,
        data_service: Optional[DataService] = None,
        skip_existing: bool = True
    ) -> int:
        """
        Загрузить свечи и сохранить в базу данных
        
        Args:
            symbol: Торговая пара
            timeframe: Таймфрейм
            days_back: Сколько дней назад загрузить
            data_service: DataService (если None, создаётся новый)
            skip_existing: Пропустить существующие свечи
            
        Returns:
            Количество сохранённых свечей
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days_back)
        
        logger.info(f"Loading {symbol} {timeframe} from {start_time} to {end_time}")
        
        # Загрузить с Bybit
        candles = self.fetch_klines_range(
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time
        )
        
        if not candles:
            logger.warning("No candles fetched")
            return 0
        
        # Сохранить в БД
        ds = data_service or DataService()
        
        try:
            if skip_existing:
                # Проверить последнюю свечу в БД
                last_candle = ds.get_latest_candle(symbol, timeframe)
                if last_candle:
                    # Фильтровать только новые свечи
                    candles = [
                        c for c in candles 
                        if c['timestamp'] > last_candle.timestamp
                    ]
                    logger.info(f"Skipping {len(candles)} existing candles")
            
            if not candles:
                logger.info("All candles already exist")
                return 0
            
            # Подготовить данные для batch insert
            candle_data = [
                {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    **candle
                }
                for candle in candles
            ]
            
            # Сохранить batch
            saved_count = ds.create_market_data_batch(candle_data)
            
            logger.info(f"✅ Saved {saved_count} candles to database")
            
            return saved_count
            
        finally:
            if not data_service:
                ds.close()
    
    def get_available_symbols(self) -> List[str]:
        """
        Получить список доступных торговых пар (USDT perpetuals)
        
        Returns:
            Список символов (BTCUSDT, ETHUSDT, etc.)
        """
        url = f"{self.BASE_URL}/v5/market/instruments-info"
        params = {
            'category': 'linear',
            'status': 'Trading'
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('retCode') != 0:
                return []
            
            instruments = data.get('result', {}).get('list', [])
            
            # Фильтровать только USDT пары
            symbols = [
                inst['symbol'] 
                for inst in instruments 
                if inst['symbol'].endswith('USDT')
            ]
            
            return sorted(symbols)
            
        except Exception as e:
            logger.error(f"Failed to get symbols: {e}")
            return []
    
    def validate_symbol(self, symbol: str) -> bool:
        """
        Проверить, существует ли символ
        
        Args:
            symbol: Торговая пара
            
        Returns:
            True если существует
        """
        available = self.get_available_symbols()
        return symbol in available
    
    def get_timeframe_duration(self, timeframe: str) -> timedelta:
        """
        Получить длительность таймфрейма
        
        Args:
            timeframe: Таймфрейм (1, 5, 15, etc.)
            
        Returns:
            timedelta объект
        """
        minutes = self.TIMEFRAME_MAP.get(timeframe)
        if not minutes:
            raise ValueError(f"Invalid timeframe: {timeframe}")
        
        return timedelta(minutes=minutes)
    
    def estimate_candles_count(
        self,
        start_time: datetime,
        end_time: datetime,
        timeframe: str
    ) -> int:
        """
        Оценить количество свечей за период
        
        Args:
            start_time: Начало
            end_time: Конец
            timeframe: Таймфрейм
            
        Returns:
            Примерное количество свечей
        """
        timeframe_minutes = self.TIMEFRAME_MAP[timeframe]
        total_minutes = (end_time - start_time).total_seconds() / 60
        return int(total_minutes / timeframe_minutes)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def quick_load(
    symbol: str = 'BTCUSDT',
    timeframe: str = '15',
    days_back: int = 30
) -> int:
    """
    Быстрая загрузка данных (helper function)
    
    Args:
        symbol: Торговая пара
        timeframe: Таймфрейм
        days_back: Дней назад
        
    Returns:
        Количество загруженных свечей
    """
    loader = BybitDataLoader()
    return loader.load_and_save(symbol, timeframe, days_back)


def load_multiple_symbols(
    symbols: List[str],
    timeframe: str = '15',
    days_back: int = 30
) -> Dict[str, int]:
    """
    Загрузить данные для нескольких символов
    
    Args:
        symbols: Список торговых пар
        timeframe: Таймфрейм
        days_back: Дней назад
        
    Returns:
        Словарь {symbol: count}
    """
    loader = BybitDataLoader()
    results = {}
    
    for symbol in symbols:
        try:
            count = loader.load_and_save(symbol, timeframe, days_back)
            results[symbol] = count
        except Exception as e:
            logger.error(f"Failed to load {symbol}: {e}")
            results[symbol] = 0
    
    return results


# ============================================================================
# MAIN (для тестирования)
# ============================================================================

if __name__ == "__main__":
    # Пример использования
    
    loader = BybitDataLoader()
    
    # 1. Получить список доступных символов
    print("\n=== Available Symbols ===")
    symbols = loader.get_available_symbols()
    print(f"Total symbols: {len(symbols)}")
    print(f"First 10: {symbols[:10]}")
    
    # 2. Загрузить последние 100 свечей
    print("\n=== Fetching 100 candles ===")
    candles = loader.fetch_klines('BTCUSDT', '15', limit=100)
    print(f"Fetched: {len(candles)} candles")
    if candles:
        print(f"First candle: {candles[0]}")
        print(f"Last candle: {candles[-1]}")
    
    # 3. Загрузить за период
    print("\n=== Fetching range ===")
    start = datetime.utcnow() - timedelta(days=7)
    end = datetime.utcnow()
    candles = loader.fetch_klines_range('BTCUSDT', '15', start, end)
    print(f"Fetched: {len(candles)} candles for 7 days")
    
    # 4. Загрузить и сохранить в БД
    print("\n=== Load and Save ===")
    count = loader.load_and_save('BTCUSDT', '15', days_back=30)
    print(f"Saved {count} candles to database")
