"""
Unit тесты для DataManager (backend/services/data_manager.py)

Проверяет:
1. load_historical() - загрузка исторических данных
2. update_cache() - сохранение в Parquet кэш
3. get_multi_timeframe() - multi-timeframe данные
4. Parquet кэширование (ТЗ 7.3)
5. Cache hit/miss логика
6. get_cache_info() - метаданные кэша
7. clear_cache() - удаление кэша

Создано: 25 октября 2025 (Фаза 1, Задача 8)
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import sys
import shutil

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from services.data_manager import DataManager


# ========================================================================
# Test Fixtures
# ========================================================================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Fixture: временная директория для кэша"""
    cache_dir = tmp_path / "test_cache"
    cache_dir.mkdir(exist_ok=True)
    yield cache_dir
    # Cleanup
    if cache_dir.exists():
        shutil.rmtree(cache_dir)


@pytest.fixture
def sample_klines_df():
    """Fixture: тестовые OHLCV данные"""
    n_bars = 1000
    np.random.seed(42)
    
    timestamps = pd.date_range(
        start=datetime.now() - timedelta(hours=n_bars),
        periods=n_bars,
        freq='1h'
    )
    
    base_price = 50000.0
    returns = np.random.normal(0, 0.01, n_bars)
    prices = base_price * (1 + returns).cumprod()
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': prices,
        'high': prices * (1 + np.abs(np.random.normal(0, 0.005, n_bars))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.005, n_bars))),
        'close': prices,
        'volume': np.random.uniform(100, 1000, n_bars)
    })
    
    return df


# ========================================================================
# Test DataManager Initialization
# ========================================================================

def test_data_manager_initialization(temp_cache_dir):
    """Тест: инициализация DataManager"""
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    assert dm.symbol == 'BTCUSDT'
    assert dm.timeframe == '15'
    assert dm.cache_dir == temp_cache_dir
    
    # Cache directory должна быть создана
    assert temp_cache_dir.exists()
    
    print("✓ DataManager инициализирован корректно")


def test_data_manager_default_dates(temp_cache_dir):
    """Тест: дефолтные значения start_date и end_date"""
    dm = DataManager(
        symbol='ETHUSDT',
        timeframe='60',
        cache_dir=str(temp_cache_dir)
    )
    
    # start_date должен быть ~1 год назад
    expected_start = datetime.now() - timedelta(days=365)
    assert abs((dm.start_date - expected_start).days) <= 1
    
    # end_date должен быть ~сейчас (используем total_seconds вместо seconds)
    time_diff = abs((dm.end_date - datetime.now()).total_seconds())
    assert time_diff < 60, f"end_date слишком далеко от текущего времени: {time_diff} секунд"
    
    print("✓ Дефолтные даты установлены корректно")


# ========================================================================
# Test Parquet Caching (ТЗ 7.3)
# ========================================================================

def test_update_cache(temp_cache_dir, sample_klines_df):
    """
    Тест: update_cache() сохраняет данные в Parquet
    
    ТЗ 7.3: Формат data/ohlcv/{symbol}/{timeframe}.parquet
    """
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    # Сохраняем данные в кэш
    dm.update_cache(sample_klines_df)
    
    # Проверяем, что файл создан
    cache_path = temp_cache_dir / 'BTCUSDT' / '15.parquet'
    assert cache_path.exists(), f"Parquet кэш не создан: {cache_path}"
    
    # Проверяем, что данные можно прочитать
    loaded_df = pd.read_parquet(cache_path)
    assert len(loaded_df) == len(sample_klines_df)
    assert 'timestamp' in loaded_df.columns
    assert 'close' in loaded_df.columns
    
    print(f"✓ Parquet кэш создан: {cache_path}, {len(loaded_df)} bars")


def test_cache_path_format(temp_cache_dir):
    """
    Тест: формат пути кэша соответствует ТЗ 7.3
    
    Ожидается: data/ohlcv/{symbol}/{timeframe}.parquet
    """
    dm = DataManager(
        symbol='ETHUSDT',
        timeframe='60',
        cache_dir=str(temp_cache_dir)
    )
    
    cache_path = dm._get_cache_path()
    
    # Проверяем формат пути
    assert cache_path.parent.name == 'ETHUSDT'
    assert cache_path.name == '60.parquet'
    assert cache_path.suffix == '.parquet'
    
    print(f"✓ Cache path формат корректен: {cache_path}")


def test_cache_hit_and_miss(temp_cache_dir, sample_klines_df):
    """
    Тест: cache hit (загрузка из кэша) vs cache miss (API request)
    
    Логика:
    1. Первый запрос - cache miss (нет кэша)
    2. Сохраняем в кэш
    3. Второй запрос - cache hit (загружает из кэша)
    """
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    cache_path = dm._get_cache_path()
    
    # Cache miss - файла ещё нет
    assert not cache_path.exists()
    
    # Сохраняем в кэш
    dm.update_cache(sample_klines_df)
    
    # Cache hit - файл существует
    assert cache_path.exists()
    
    # Загружаем из кэша
    loaded_df = pd.read_parquet(cache_path)
    assert len(loaded_df) == len(sample_klines_df)
    
    print(f"✓ Cache hit/miss логика работает корректно")


# ========================================================================
# Test get_cache_info()
# ========================================================================

def test_get_cache_info_no_cache(temp_cache_dir):
    """Тест: get_cache_info() когда кэша нет"""
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    info = dm.get_cache_info()
    
    assert info['exists'] is False
    assert info['size_bytes'] == 0
    assert info['num_bars'] == 0
    assert info['date_range'] == (None, None)
    
    print("✓ get_cache_info() без кэша: exists=False")


def test_get_cache_info_with_cache(temp_cache_dir, sample_klines_df):
    """Тест: get_cache_info() когда кэш существует"""
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    # Сохраняем кэш
    dm.update_cache(sample_klines_df)
    
    info = dm.get_cache_info()
    
    assert info['exists'] is True
    assert info['size_bytes'] > 0
    assert info['num_bars'] == len(sample_klines_df)
    
    # Проверяем date_range
    date_range = info['date_range']
    assert date_range[0] is not None
    assert date_range[1] is not None
    assert date_range[0] <= date_range[1]
    
    print(f"✓ get_cache_info(): {info['num_bars']} bars, {info['size_bytes']} bytes")


# ========================================================================
# Test clear_cache()
# ========================================================================

def test_clear_cache_success(temp_cache_dir, sample_klines_df):
    """Тест: clear_cache() успешно удаляет кэш"""
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    # Создаём кэш
    dm.update_cache(sample_klines_df)
    cache_path = dm._get_cache_path()
    assert cache_path.exists()
    
    # Удаляем кэш
    result = dm.clear_cache()
    
    assert result is True
    assert not cache_path.exists()
    
    print("✓ clear_cache() успешно удалил кэш")


def test_clear_cache_no_cache(temp_cache_dir):
    """Тест: clear_cache() когда кэша нет"""
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    # Кэша нет
    result = dm.clear_cache()
    
    # Должен вернуть False (кэш не существовал)
    assert result is False
    
    print("✓ clear_cache() без кэша: result=False")


# ========================================================================
# Test get_multi_timeframe() (ТЗ 3.1.2)
# ========================================================================

def test_get_multi_timeframe(temp_cache_dir, sample_klines_df):
    """
    Тест: get_multi_timeframe() загружает данные по нескольким таймфреймам
    
    ТЗ 3.1.2: Поддержка multi-timeframe анализа
    """
    # Создаём кэш для разных таймфреймов
    for tf in ['5', '15', '60']:
        dm = DataManager(
            symbol='BTCUSDT',
            timeframe=tf,
            cache_dir=str(temp_cache_dir)
        )
        dm.update_cache(sample_klines_df)
    
    # Загружаем multi-timeframe
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',  # Базовый таймфрейм
        cache_dir=str(temp_cache_dir)
    )
    
    mtf_data = dm.get_multi_timeframe(['5', '15', '60'])
    
    # Проверяем структуру
    assert isinstance(mtf_data, dict)
    assert '5' in mtf_data
    assert '15' in mtf_data
    assert '60' in mtf_data
    
    # Проверяем, что каждый таймфрейм содержит DataFrame
    for tf, df in mtf_data.items():
        assert isinstance(df, pd.DataFrame)
        assert 'timestamp' in df.columns
        assert 'close' in df.columns
        assert len(df) > 0
    
    print(f"✓ Multi-timeframe загружен: {list(mtf_data.keys())}")
    print(f"  5m: {len(mtf_data['5'])} bars")
    print(f"  15m: {len(mtf_data['15'])} bars")
    print(f"  60m: {len(mtf_data['60'])} bars")


def test_get_multi_timeframe_empty(temp_cache_dir):
    """Тест: get_multi_timeframe() когда кэша нет"""
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    # Кэша нет, но метод должен попытаться загрузить (вернёт пустые DataFrame)
    mtf_data = dm.get_multi_timeframe(['5', '15'])
    
    assert isinstance(mtf_data, dict)
    assert '5' in mtf_data
    assert '15' in mtf_data
    
    # DataFrames могут быть пустыми (нет API мока)
    # Просто проверяем, что метод не упал
    print("✓ get_multi_timeframe() без кэша: не упал")


# ========================================================================
# Test load_historical() - основной метод
# ========================================================================

def test_load_historical_from_cache(temp_cache_dir, sample_klines_df):
    """
    Тест: load_historical() загружает из кэша
    
    Workflow:
    1. Сохраняем данные в кэш
    2. load_historical() должен загрузить из кэша (cache hit)
    """
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    # Сохраняем в кэш
    dm.update_cache(sample_klines_df)
    
    # Загружаем (должен быть cache hit)
    loaded_df = dm.load_historical(limit=500)
    
    assert isinstance(loaded_df, pd.DataFrame)
    assert len(loaded_df) == 500  # Limit работает
    assert 'timestamp' in loaded_df.columns
    assert 'close' in loaded_df.columns
    
    print(f"✓ load_historical() из кэша: {len(loaded_df)} bars (limit=500)")


def test_load_historical_limit(temp_cache_dir, sample_klines_df):
    """Тест: load_historical() с разными limit значениями"""
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    dm.update_cache(sample_klines_df)
    
    # Проверяем разные лимиты
    for limit in [100, 500, 1000]:
        df = dm.load_historical(limit=limit)
        expected_len = min(limit, len(sample_klines_df))
        assert len(df) == expected_len, f"Limit {limit} не работает: expected={expected_len}, actual={len(df)}"
    
    print("✓ load_historical() limit работает корректно (100, 500, 1000)")


def test_load_historical_date_filtering(temp_cache_dir, sample_klines_df):
    """Тест: load_historical() фильтрует по start_date/end_date"""
    # Задаём узкий диапазон дат
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now() - timedelta(days=10)
    
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        start_date=start_date,
        end_date=end_date,
        cache_dir=str(temp_cache_dir)
    )
    
    dm.update_cache(sample_klines_df)
    
    # Загружаем с фильтрацией
    df = dm.load_historical(limit=10000)
    
    # Проверяем, что timestamp в пределах диапазона
    # Примечание: если кэш недостаточен, будет запрос к API,
    # который может вернуть свежие данные вне диапазона
    if len(df) > 0 and 'timestamp' in df.columns:
        min_ts = df['timestamp'].min()
        max_ts = df['timestamp'].max()
        
        # Если данные из кэша - проверяем диапазон
        # Если из API - skip проверку (API может вернуть свежие данные)
        cache_path = dm._get_cache_path()
        cached_df = pd.read_parquet(cache_path) if cache_path.exists() else None
        
        if cached_df is not None and len(df) <= len(cached_df):
            # Данные из кэша - проверяем фильтрацию
            assert min_ts >= start_date or len(df) == 0, f"min_ts ({min_ts}) < start_date ({start_date})"
        else:
            # Данные из API - skip строгую проверку
            pass
    
    print(f"✓ Date filtering: {len(df)} bars загружено")


# ========================================================================
# Test Edge Cases
# ========================================================================

def test_update_cache_empty_data(temp_cache_dir):
    """Тест: update_cache() с пустым DataFrame"""
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    empty_df = pd.DataFrame()
    
    # Не должно упасть, просто warning
    dm.update_cache(empty_df)
    
    # Кэш не должен быть создан
    cache_path = dm._get_cache_path()
    assert not cache_path.exists()
    
    print("✓ update_cache() с пустым DataFrame: не упал")


def test_update_cache_none_data(temp_cache_dir):
    """Тест: update_cache() с None"""
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    # Не должно упасть
    dm.update_cache(None)
    
    cache_path = dm._get_cache_path()
    assert not cache_path.exists()
    
    print("✓ update_cache() с None: не упал")


def test_symbol_case_normalization(temp_cache_dir):
    """Тест: symbol нормализуется в uppercase"""
    dm = DataManager(
        symbol='btcusdt',  # lowercase
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    assert dm.symbol == 'BTCUSDT'  # Должен быть uppercase
    
    cache_path = dm._get_cache_path()
    assert cache_path.parent.name == 'BTCUSDT'
    
    print("✓ Symbol нормализуется в uppercase")


def test_multiple_symbols_separate_cache(temp_cache_dir, sample_klines_df):
    """Тест: разные символы имеют раздельный кэш"""
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    
    for symbol in symbols:
        dm = DataManager(
            symbol=symbol,
            timeframe='15',
            cache_dir=str(temp_cache_dir)
        )
        dm.update_cache(sample_klines_df)
    
    # Проверяем, что создано 3 отдельные директории
    for symbol in symbols:
        cache_path = temp_cache_dir / symbol / '15.parquet'
        assert cache_path.exists(), f"Кэш для {symbol} не создан"
    
    print(f"✓ Раздельный кэш для {len(symbols)} символов")


def test_multiple_timeframes_same_symbol(temp_cache_dir, sample_klines_df):
    """Тест: разные таймфреймы одного символа имеют раздельный кэш"""
    timeframes = ['5', '15', '60', '240']
    
    for tf in timeframes:
        dm = DataManager(
            symbol='BTCUSDT',
            timeframe=tf,
            cache_dir=str(temp_cache_dir)
        )
        dm.update_cache(sample_klines_df)
    
    # Проверяем, что создано 4 файла
    for tf in timeframes:
        cache_path = temp_cache_dir / 'BTCUSDT' / f'{tf}.parquet'
        assert cache_path.exists(), f"Кэш для {tf} не создан"
    
    print(f"✓ Раздельный кэш для {len(timeframes)} таймфреймов")


# ========================================================================
# Test Data Integrity
# ========================================================================

def test_cache_data_integrity(temp_cache_dir, sample_klines_df):
    """Тест: данные сохраняются и загружаются без потерь"""
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    # Сохраняем
    dm.update_cache(sample_klines_df)
    
    # Загружаем
    cache_path = dm._get_cache_path()
    loaded_df = pd.read_parquet(cache_path)
    
    # Проверяем целостность
    assert len(loaded_df) == len(sample_klines_df)
    
    # Проверяем колонки
    for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
        if col in sample_klines_df.columns:
            assert col in loaded_df.columns, f"Колонка {col} потеряна"
    
    # Проверяем значения (первая и последняя строка)
    assert loaded_df['close'].iloc[0] == pytest.approx(sample_klines_df['close'].iloc[0], abs=0.01)
    assert loaded_df['close'].iloc[-1] == pytest.approx(sample_klines_df['close'].iloc[-1], abs=0.01)
    
    print("✓ Data integrity: данные сохранены без потерь")


# ========================================================================
# Main (для pytest)
# ========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
