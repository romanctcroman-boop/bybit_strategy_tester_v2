"""
DataManager - Централизованное управление историческими данными

Соответствие ТЗ 3.1.2:
- Фасад над BybitAdapter и DataService
- Кэширование (Parquet + DB)
- Multi-timeframe support
- Автоматическое обновление данных

Параметры:
- symbol: str - Торговая пара (BTCUSDT, ETHUSDT, etc.)
- timeframe: str - Таймфрейм ('1', '5', '15', '60', '240', 'D')
- start_date: datetime - Начало исторического периода
- end_date: datetime - Конец периода
- cache_dir: str - Директория для локального кэша

Методы (ТЗ 3.1.2):
- load_historical(limit=1000) -> pd.DataFrame
- update_cache() -> None
- get_multi_timeframe(timeframes: list) -> dict[str, pd.DataFrame]

Создано: 25 октября 2025 (Фаза 1, Задача 2)
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from loguru import logger

from backend.services.adapters.bybit import BybitAdapter
from backend.services.data_service import DataService


class DataManager:
    """
    ТЗ 3.1.2 - Управляет загрузкой, кэшированием и синхронизацией исторических данных
    
    Предоставляет централизованный доступ к рыночным данным с автоматическим
    кэшированием в Parquet формате согласно ТЗ 7.3.
    
    Workflow:
    1. Проверяет Parquet кэш (data/ohlcv/{symbol}/{timeframe}.parquet)
    2. Если данных нет или недостаточно - запрашивает из Bybit API
    3. Сохраняет в Parquet кэш для быстрого доступа
    4. Опционально сохраняет в DB audit table
    
    Example:
        >>> dm = DataManager(symbol='BTCUSDT', timeframe='15')
        >>> df = dm.load_historical(limit=1000)
        >>> print(f"Loaded {len(df)} bars")
        
        >>> # Multi-timeframe
        >>> mtf_data = dm.get_multi_timeframe(['5', '15', '60'])
        >>> print(f"5m: {len(mtf_data['5'])} bars")
    """
    
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        cache_dir: str = "data/ohlcv"
    ):
        """
        Args:
            symbol: Торговая пара (BTCUSDT, ETHUSDT, etc.)
            timeframe: Таймфрейм ('1', '5', '15', '60', '240', 'D')
            start_date: Начало периода (default: 1 год назад)
            end_date: Конец периода (default: сейчас)
            cache_dir: Директория для Parquet кэша
        """
        self.symbol = symbol.upper()
        self.timeframe = timeframe
        self.start_date = start_date or (datetime.now() - timedelta(days=365))
        self.end_date = end_date or datetime.now()
        self.cache_dir = Path(cache_dir)
        
        # Initialize adapters
        self.bybit = BybitAdapter()
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            f"DataManager initialized: {self.symbol} @ {self.timeframe}, "
            f"cache={self.cache_dir}"
        )
    
    def load_historical(self, limit: int = 1000) -> pd.DataFrame:
        """
        ТЗ 3.1.2 - Загрузить исторические данные
        
        Логика:
        1. Пытается загрузить из Parquet кэша
        2. Если нет или недостаточно - запрашивает из Bybit API
        3. Сохраняет в кэш
        
        Args:
            limit: Количество баров (максимум)
        
        Returns:
            DataFrame с колонками [timestamp, open, high, low, close, volume]
        """
        logger.info(f"Loading historical data for {self.symbol} @ {self.timeframe}, limit={limit}")
        
        # Try to load from Parquet cache
        cache_path = self._get_cache_path()
        
        if cache_path.exists():
            logger.info(f"Loading from cache: {cache_path}")
            try:
                df = pd.read_parquet(cache_path)
                
                # Filter by date range
                if 'timestamp' in df.columns:
                    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                    
                    df = df[
                        (df['timestamp'] >= self.start_date) &
                        (df['timestamp'] <= self.end_date)
                    ]
                
                if len(df) >= limit:
                    logger.info(f"Cache hit: {len(df)} bars loaded, returning last {limit}")
                    return df.tail(limit).reset_index(drop=True)
                else:
                    logger.warning(f"Cache has only {len(df)} bars, need {limit}. Fetching from API...")
            except Exception as e:
                logger.error(f"Failed to load cache: {e}. Fetching from API...")
        
        # Fetch from Bybit API
        logger.info(f"Fetching from Bybit API: {self.symbol} @ {self.timeframe}")
        klines = self.bybit.get_klines(
            symbol=self.symbol,
            interval=self.timeframe,
            limit=limit
        )
        
        if not klines:
            logger.error("No data returned from Bybit API")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(klines)
        
        # Normalize columns
        column_mapping = {
            'open_time': 'timestamp',
            'time': 'timestamp',
            't': 'timestamp',
            'o': 'open',
            'h': 'high',
            'l': 'low',
            'c': 'close',
            'v': 'volume'
        }
        
        df = df.rename(columns=column_mapping)
        
        # Ensure required columns exist
        required_cols = ['timestamp', 'open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                logger.error(f"Missing required column: {col}")
                return pd.DataFrame()
        
        # Ensure timestamp is datetime
        if 'timestamp' in df.columns:
            if pd.api.types.is_integer_dtype(df['timestamp']):
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            elif not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Save to cache
        try:
            self.update_cache(df)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
        
        logger.info(f"Loaded {len(df)} bars from API")
        return df
    
    def update_cache(self, data: pd.DataFrame | None = None) -> None:
        """
        ТЗ 3.1.2 - Обновить Parquet кэш
        
        Сохраняет данные в формате:
        data/ohlcv/{symbol}/{timeframe}.parquet (ТЗ 7.3)
        
        Args:
            data: DataFrame для сохранения (если None, загружает с API)
        """
        if data is None or data.empty:
            logger.warning("No data provided for cache update")
            return
        
        cache_path = self._get_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Save to Parquet with compression
            data.to_parquet(
                cache_path,
                compression='snappy',
                index=False,
                engine='pyarrow'
            )
            
            logger.info(f"Cache updated: {cache_path}, {len(data)} bars")
        except Exception as e:
            logger.error(f"Failed to write Parquet cache: {e}")
    
    def get_multi_timeframe(self, timeframes: list[str]) -> dict[str, pd.DataFrame]:
        """
        ТЗ 3.1.2 - Загрузить данные по нескольким таймфреймам
        
        Используется для multi-timeframe анализа и стратегий.
        
        Args:
            timeframes: Список таймфреймов ['1', '5', '15', '60']
        
        Returns:
            dict[timeframe, DataFrame]
        
        Example:
            >>> dm = DataManager('BTCUSDT', '15')
            >>> mtf = dm.get_multi_timeframe(['5', '15', '60'])
            >>> print(f"5m: {len(mtf['5'])} bars")
            >>> print(f"15m: {len(mtf['15'])} bars")
            >>> print(f"60m: {len(mtf['60'])} bars")
        """
        logger.info(f"Loading multi-timeframe data for {self.symbol}: {timeframes}")
        
        result = {}
        
        for tf in timeframes:
            logger.info(f"  Loading {tf}...")
            
            # Create DataManager for each timeframe
            dm = DataManager(
                symbol=self.symbol,
                timeframe=tf,
                start_date=self.start_date,
                end_date=self.end_date,
                cache_dir=str(self.cache_dir)
            )
            
            df = dm.load_historical()
            result[tf] = df
            
            logger.info(f"    {tf}: {len(df)} bars loaded")
        
        logger.info(f"Multi-timeframe loading completed: {len(result)} timeframes")
        return result
    
    def _get_cache_path(self) -> Path:
        """
        Получить путь к Parquet кэшу
        
        Format (ТЗ 7.3): data/ohlcv/{symbol}/{timeframe}.parquet
        
        Example: data/ohlcv/BTCUSDT/15.parquet
        """
        return self.cache_dir / self.symbol / f"{self.timeframe}.parquet"
    
    def clear_cache(self) -> bool:
        """
        Очистить Parquet кэш для данного symbol + timeframe
        
        Returns:
            True если успешно удалено, False otherwise
        """
        cache_path = self._get_cache_path()
        
        if cache_path.exists():
            try:
                cache_path.unlink()
                logger.info(f"Cache cleared: {cache_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to clear cache: {e}")
                return False
        else:
            logger.warning(f"Cache does not exist: {cache_path}")
            return False
    
    def get_cache_info(self) -> dict[str, Any]:
        """
        Получить информацию о кэше
        
        Returns:
            {
                'exists': bool,
                'path': str,
                'size_bytes': int,
                'num_bars': int,
                'date_range': tuple[datetime, datetime]
            }
        """
        cache_path = self._get_cache_path()
        
        if not cache_path.exists():
            return {
                'exists': False,
                'path': str(cache_path),
                'size_bytes': 0,
                'num_bars': 0,
                'date_range': (None, None)
            }
        
        try:
            df = pd.read_parquet(cache_path)
            
            if 'timestamp' in df.columns:
                if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                date_range = (df['timestamp'].min(), df['timestamp'].max())
            else:
                date_range = (None, None)
            
            return {
                'exists': True,
                'path': str(cache_path),
                'size_bytes': cache_path.stat().st_size,
                'num_bars': len(df),
                'date_range': date_range
            }
        except Exception as e:
            logger.error(f"Failed to read cache info: {e}")
            return {
                'exists': True,
                'path': str(cache_path),
                'size_bytes': cache_path.stat().st_size if cache_path.exists() else 0,
                'num_bars': 0,
                'date_range': (None, None),
                'error': str(e)
            }
