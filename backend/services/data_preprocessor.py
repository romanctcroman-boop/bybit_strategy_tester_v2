"""
DataPreprocessor - Валидация, очистка и нормализация данных

Функционал:
- Валидация OHLCV данных
- Обнаружение и исправление аномалий
- Заполнение пропущенных свечей
- Outlier detection (выбросы)
- Нормализация данных
- Проверка целостности данных
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataPreprocessor:
    """
    Препроцессор для маркет данных
    
    Примеры использования:
        preprocessor = DataPreprocessor()
        
        # Валидация данных
        is_valid, errors = preprocessor.validate_ohlcv(candles)
        
        # Очистка данных
        cleaned = preprocessor.clean_data(candles)
        
        # Заполнение пропусков
        filled = preprocessor.fill_missing_candles(candles, '15')
        
        # Обнаружение выбросов
        outliers = preprocessor.detect_outliers(candles)
        
        # Полная обработка
        processed = preprocessor.preprocess(candles, timeframe='15')
    """
    
    # Validation thresholds
    MAX_PRICE_CHANGE_PCT = 50.0  # 50% за одну свечу
    MAX_VOLUME_SPIKE = 100.0  # 100x от средней
    MIN_PRICE = 0.0001  # Минимальная цена
    MAX_PRICE = 1000000000.0  # Максимальная цена
    
    def __init__(self):
        """Инициализация препроцессора"""
        self.stats = {
            'total_processed': 0,
            'invalid_candles': 0,
            'missing_filled': 0,
            'outliers_detected': 0,
            'anomalies_fixed': 0
        }
    
    # ========================================================================
    # VALIDATION
    # ========================================================================
    
    def validate_ohlcv(self, candles: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Валидация OHLCV данных
        
        Args:
            candles: Список свечей
            
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        if not candles:
            errors.append("Empty candles list")
            return False, errors
        
        for i, candle in enumerate(candles):
            # Check required fields
            required_fields = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            missing = [f for f in required_fields if f not in candle]
            if missing:
                errors.append(f"Candle {i}: Missing fields {missing}")
                continue
            
            # Extract OHLCV
            try:
                o = float(candle['open'])
                h = float(candle['high'])
                l = float(candle['low'])
                c = float(candle['close'])
                v = float(candle['volume'])
            except (ValueError, TypeError) as e:
                errors.append(f"Candle {i}: Invalid numeric values - {e}")
                continue
            
            # Check OHLC relationship
            if not (l <= o <= h and l <= c <= h):
                errors.append(f"Candle {i}: Invalid OHLC relationship (High: {h}, Low: {l}, Open: {o}, Close: {c})")
            
            # Check price range
            if h <= 0 or l <= 0 or o <= 0 or c <= 0:
                errors.append(f"Candle {i}: Negative or zero prices")
            
            if h < self.MIN_PRICE or h > self.MAX_PRICE:
                errors.append(f"Candle {i}: Price out of range ({h})")
            
            # Check volume
            if v < 0:
                errors.append(f"Candle {i}: Negative volume")
            
            # Check timestamp
            if isinstance(candle['timestamp'], datetime):
                ts = candle['timestamp']
            else:
                try:
                    ts = datetime.fromisoformat(str(candle['timestamp']))
                except:
                    errors.append(f"Candle {i}: Invalid timestamp format")
                    continue
            
            # Check chronological order
            if i > 0:
                prev_ts = candles[i-1]['timestamp']
                if isinstance(prev_ts, str):
                    prev_ts = datetime.fromisoformat(prev_ts)
                
                if ts <= prev_ts:
                    errors.append(f"Candle {i}: Timestamps not in chronological order")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def detect_price_anomalies(
        self,
        candles: List[Dict],
        threshold_pct: float = MAX_PRICE_CHANGE_PCT
    ) -> List[Dict]:
        """
        Обнаружить аномальные изменения цен
        
        Args:
            candles: Список свечей
            threshold_pct: Порог изменения (%)
            
        Returns:
            Список аномальных свечей с описанием
        """
        anomalies = []
        
        for i in range(1, len(candles)):
            prev = candles[i-1]
            curr = candles[i]
            
            prev_close = float(prev['close'])
            curr_open = float(curr['open'])
            curr_close = float(curr['close'])
            
            # Gap между свечами
            gap_pct = abs((curr_open - prev_close) / prev_close * 100)
            if gap_pct > threshold_pct:
                anomalies.append({
                    'index': i,
                    'type': 'gap',
                    'change_pct': gap_pct,
                    'description': f"Gap of {gap_pct:.2f}% between candles"
                })
            
            # Изменение внутри свечи
            intrabar_pct = abs((curr_close - curr_open) / curr_open * 100)
            if intrabar_pct > threshold_pct:
                anomalies.append({
                    'index': i,
                    'type': 'intrabar_spike',
                    'change_pct': intrabar_pct,
                    'description': f"Intrabar change of {intrabar_pct:.2f}%"
                })
        
        return anomalies
    
    def detect_volume_anomalies(
        self,
        candles: List[Dict],
        threshold_multiplier: float = MAX_VOLUME_SPIKE
    ) -> List[Dict]:
        """
        Обнаружить аномальные объёмы
        
        Args:
            candles: Список свечей
            threshold_multiplier: Порог (кратно средней)
            
        Returns:
            Список аномальных свечей
        """
        volumes = [float(c['volume']) for c in candles]
        avg_volume = np.mean(volumes)
        
        if avg_volume == 0:
            return []
        
        anomalies = []
        
        for i, candle in enumerate(candles):
            volume = float(candle['volume'])
            multiplier = volume / avg_volume
            
            if multiplier > threshold_multiplier:
                anomalies.append({
                    'index': i,
                    'type': 'volume_spike',
                    'multiplier': multiplier,
                    'description': f"Volume {multiplier:.1f}x above average"
                })
        
        return anomalies
    
    def detect_outliers(
        self,
        candles: List[Dict],
        method: str = 'iqr'
    ) -> List[int]:
        """
        Обнаружить выбросы (outliers)
        
        Args:
            candles: Список свечей
            method: Метод ('iqr' или 'zscore')
            
        Returns:
            Список индексов выбросов
        """
        closes = np.array([float(c['close']) for c in candles])
        
        if method == 'iqr':
            # IQR method
            q1 = np.percentile(closes, 25)
            q3 = np.percentile(closes, 75)
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            outliers = [
                i for i, price in enumerate(closes)
                if price < lower_bound or price > upper_bound
            ]
        
        elif method == 'zscore':
            # Z-score method
            mean = np.mean(closes)
            std = np.std(closes)
            
            if std == 0:
                return []
            
            z_scores = np.abs((closes - mean) / std)
            outliers = [i for i, z in enumerate(z_scores) if z > 3]
        
        else:
            raise ValueError(f"Unknown method: {method}")
        
        return outliers
    
    # ========================================================================
    # CLEANING
    # ========================================================================
    
    def remove_duplicates(self, candles: List[Dict]) -> List[Dict]:
        """
        Удалить дублирующиеся свечи (по timestamp)
        
        Args:
            candles: Список свечей
            
        Returns:
            Очищенный список
        """
        seen_timestamps = set()
        unique_candles = []
        duplicates_count = 0
        
        for candle in candles:
            ts = candle['timestamp']
            if isinstance(ts, datetime):
                ts = ts.isoformat()
            
            if ts not in seen_timestamps:
                seen_timestamps.add(ts)
                unique_candles.append(candle)
            else:
                duplicates_count += 1
        
        if duplicates_count > 0:
            logger.info(f"Removed {duplicates_count} duplicate candles")
        
        return unique_candles
    
    def fix_ohlc_relationships(self, candles: List[Dict]) -> List[Dict]:
        """
        Исправить нарушенные OHLC соотношения
        
        Args:
            candles: Список свечей
            
        Returns:
            Исправленный список
        """
        fixed = []
        fixed_count = 0
        
        for candle in candles:
            c = candle.copy()
            
            o = float(c['open'])
            h = float(c['high'])
            l = float(c['low'])
            cl = float(c['close'])
            
            # Fix high (должно быть максимумом)
            actual_high = max(o, h, l, cl)
            if h != actual_high:
                c['high'] = actual_high
                fixed_count += 1
            
            # Fix low (должно быть минимумом)
            actual_low = min(o, h, l, cl)
            if l != actual_low:
                c['low'] = actual_low
                fixed_count += 1
            
            fixed.append(c)
        
        if fixed_count > 0:
            logger.info(f"Fixed {fixed_count} OHLC relationships")
            self.stats['anomalies_fixed'] += fixed_count
        
        return fixed
    
    def smooth_outliers(
        self,
        candles: List[Dict],
        outlier_indices: List[int],
        method: str = 'interpolate'
    ) -> List[Dict]:
        """
        Сгладить выбросы
        
        Args:
            candles: Список свечей
            outlier_indices: Индексы выбросов
            method: Метод ('interpolate', 'remove', 'cap')
            
        Returns:
            Сглаженный список
        """
        if not outlier_indices:
            return candles
        
        smoothed = candles.copy()
        
        if method == 'interpolate':
            # Interpolate between neighbors
            for idx in outlier_indices:
                if 0 < idx < len(candles) - 1:
                    prev = candles[idx - 1]
                    next = candles[idx + 1]
                    
                    smoothed[idx]['close'] = (
                        float(prev['close']) + float(next['close'])
                    ) / 2
        
        elif method == 'remove':
            # Remove outliers
            smoothed = [
                c for i, c in enumerate(candles)
                if i not in outlier_indices
            ]
        
        elif method == 'cap':
            # Cap to reasonable range
            closes = [float(c['close']) for c in candles]
            q1 = np.percentile(closes, 25)
            q3 = np.percentile(closes, 75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            
            for idx in outlier_indices:
                price = float(smoothed[idx]['close'])
                if price < lower:
                    smoothed[idx]['close'] = lower
                elif price > upper:
                    smoothed[idx]['close'] = upper
        
        logger.info(f"Smoothed {len(outlier_indices)} outliers using '{method}' method")
        return smoothed
    
    # ========================================================================
    # GAP FILLING
    # ========================================================================
    
    def fill_missing_candles(
        self,
        candles: List[Dict],
        timeframe: str,
        method: str = 'forward_fill'
    ) -> List[Dict]:
        """
        Заполнить пропущенные свечи
        
        Args:
            candles: Список свечей
            timeframe: Таймфрейм (1, 5, 15, 60, etc.)
            method: Метод заполнения ('forward_fill', 'interpolate', 'zero')
            
        Returns:
            Заполненный список
        """
        if not candles or len(candles) < 2:
            return candles
        
        # Определить интервал
        timeframe_map = {
            '1': 1, '3': 3, '5': 5, '15': 15, '30': 30,
            '60': 60, '120': 120, '240': 240, 'D': 1440
        }
        
        interval_minutes = timeframe_map.get(timeframe, 15)
        interval = timedelta(minutes=interval_minutes)
        
        # Сортировать по времени
        sorted_candles = sorted(candles, key=lambda x: x['timestamp'])
        
        filled = []
        missing_count = 0
        
        for i in range(len(sorted_candles) - 1):
            current = sorted_candles[i]
            next_candle = sorted_candles[i + 1]
            
            filled.append(current)
            
            current_time = current['timestamp']
            next_time = next_candle['timestamp']
            
            # Проверить пропуск
            expected_next = current_time + interval
            
            while expected_next < next_time:
                # Создать заполняющую свечу
                if method == 'forward_fill':
                    # Копировать close предыдущей
                    fill_candle = {
                        'timestamp': expected_next,
                        'open': current['close'],
                        'high': current['close'],
                        'low': current['close'],
                        'close': current['close'],
                        'volume': 0
                    }
                
                elif method == 'interpolate':
                    # Интерполяция между current и next
                    total_gap = (next_time - current_time).total_seconds()
                    current_gap = (expected_next - current_time).total_seconds()
                    ratio = current_gap / total_gap
                    
                    interpolated_price = (
                        float(current['close']) + 
                        (float(next_candle['close']) - float(current['close'])) * ratio
                    )
                    
                    fill_candle = {
                        'timestamp': expected_next,
                        'open': interpolated_price,
                        'high': interpolated_price,
                        'low': interpolated_price,
                        'close': interpolated_price,
                        'volume': 0
                    }
                
                elif method == 'zero':
                    # Нулевая свеча
                    fill_candle = {
                        'timestamp': expected_next,
                        'open': current['close'],
                        'high': current['close'],
                        'low': current['close'],
                        'close': current['close'],
                        'volume': 0
                    }
                
                filled.append(fill_candle)
                missing_count += 1
                expected_next += interval
        
        # Добавить последнюю свечу
        filled.append(sorted_candles[-1])
        
        if missing_count > 0:
            logger.info(f"Filled {missing_count} missing candles using '{method}' method")
            self.stats['missing_filled'] += missing_count
        
        return filled
    
    # ========================================================================
    # NORMALIZATION
    # ========================================================================
    
    def normalize_prices(
        self,
        candles: List[Dict],
        method: str = 'minmax'
    ) -> Tuple[List[Dict], Dict[str, float]]:
        """
        Нормализовать цены
        
        Args:
            candles: Список свечей
            method: Метод ('minmax' или 'zscore')
            
        Returns:
            (normalized_candles, normalization_params)
        """
        closes = np.array([float(c['close']) for c in candles])
        
        if method == 'minmax':
            min_price = closes.min()
            max_price = closes.max()
            
            if max_price == min_price:
                return candles, {'method': method}
            
            scale = max_price - min_price
            
            normalized = []
            for candle in candles:
                c = candle.copy()
                c['open'] = (float(c['open']) - min_price) / scale
                c['high'] = (float(c['high']) - min_price) / scale
                c['low'] = (float(c['low']) - min_price) / scale
                c['close'] = (float(c['close']) - min_price) / scale
                normalized.append(c)
            
            params = {
                'method': method,
                'min': min_price,
                'max': max_price,
                'scale': scale
            }
        
        elif method == 'zscore':
            mean = closes.mean()
            std = closes.std()
            
            if std == 0:
                return candles, {'method': method}
            
            normalized = []
            for candle in candles:
                c = candle.copy()
                c['open'] = (float(c['open']) - mean) / std
                c['high'] = (float(c['high']) - mean) / std
                c['low'] = (float(c['low']) - mean) / std
                c['close'] = (float(c['close']) - mean) / std
                normalized.append(c)
            
            params = {
                'method': method,
                'mean': mean,
                'std': std
            }
        
        else:
            raise ValueError(f"Unknown method: {method}")
        
        return normalized, params
    
    # ========================================================================
    # HIGH-LEVEL
    # ========================================================================
    
    def clean_data(
        self,
        candles: List[Dict],
        fix_ohlc: bool = True,
        remove_dups: bool = True
    ) -> List[Dict]:
        """
        Очистить данные
        
        Args:
            candles: Список свечей
            fix_ohlc: Исправить OHLC соотношения
            remove_dups: Удалить дубликаты
            
        Returns:
            Очищенный список
        """
        cleaned = candles.copy()
        
        if remove_dups:
            cleaned = self.remove_duplicates(cleaned)
        
        if fix_ohlc:
            cleaned = self.fix_ohlc_relationships(cleaned)
        
        return cleaned
    
    def preprocess(
        self,
        candles: List[Dict],
        timeframe: str = '15',
        fill_missing: bool = True,
        detect_outliers: bool = True,
        smooth_outliers: bool = False,
        validate: bool = True
    ) -> Tuple[List[Dict], Dict[str, Any]]:
        """
        Полная предобработка данных
        
        Args:
            candles: Список свечей
            timeframe: Таймфрейм
            fill_missing: Заполнить пропуски
            detect_outliers: Обнаружить выбросы
            smooth_outliers: Сгладить выбросы
            validate: Валидировать данные
            
        Returns:
            (processed_candles, report)
        """
        report = {
            'input_count': len(candles),
            'output_count': 0,
            'validation_errors': [],
            'outliers': [],
            'anomalies': []
        }
        
        # Validate
        if validate:
            is_valid, errors = self.validate_ohlcv(candles)
            report['validation_errors'] = errors
            if not is_valid:
                logger.warning(f"Validation found {len(errors)} errors")
        
        # Clean
        processed = self.clean_data(candles)
        
        # Fill missing
        if fill_missing:
            processed = self.fill_missing_candles(processed, timeframe)
        
        # Detect outliers
        if detect_outliers:
            outlier_indices = self.detect_outliers(processed)
            report['outliers'] = outlier_indices
            
            if outlier_indices:
                logger.info(f"Detected {len(outlier_indices)} outliers")
                
                if smooth_outliers:
                    processed = self.smooth_outliers(processed, outlier_indices)
        
        # Detect anomalies
        price_anomalies = self.detect_price_anomalies(processed)
        volume_anomalies = self.detect_volume_anomalies(processed)
        report['anomalies'] = price_anomalies + volume_anomalies
        
        if report['anomalies']:
            logger.warning(f"Detected {len(report['anomalies'])} anomalies")
        
        report['output_count'] = len(processed)
        self.stats['total_processed'] += len(processed)
        
        return processed, report
    
    def get_stats(self) -> Dict[str, int]:
        """Получить статистику обработки"""
        return self.stats.copy()


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Создать препроцессор
    preprocessor = DataPreprocessor()
    
    # Тестовые данные с проблемами
    test_candles = [
        {'timestamp': datetime(2024, 1, 1, 10, 0), 'open': 50000, 'high': 50500, 'low': 49500, 'close': 50200, 'volume': 100},
        {'timestamp': datetime(2024, 1, 1, 10, 15), 'open': 50200, 'high': 50300, 'low': 50100, 'close': 50250, 'volume': 105},
        # Пропуск (10:30 отсутствует)
        {'timestamp': datetime(2024, 1, 1, 10, 45), 'open': 50250, 'high': 50350, 'low': 50150, 'close': 50300, 'volume': 110},
        # Аномалия: резкий скачок
        {'timestamp': datetime(2024, 1, 1, 11, 0), 'open': 50300, 'high': 75000, 'low': 50200, 'close': 74500, 'volume': 10000},
        {'timestamp': datetime(2024, 1, 1, 11, 15), 'open': 74500, 'high': 50600, 'low': 50400, 'close': 50500, 'volume': 120},  # Неправильный high
    ]
    
    print("="*70)
    print("  DATA PREPROCESSING TEST")
    print("="*70)
    
    # 1. Validation
    print("\n1. Validation:")
    is_valid, errors = preprocessor.validate_ohlcv(test_candles)
    print(f"   Valid: {is_valid}")
    if errors:
        for error in errors[:3]:
            print(f"   • {error}")
    
    # 2. Detect anomalies
    print("\n2. Price Anomalies:")
    anomalies = preprocessor.detect_price_anomalies(test_candles, threshold_pct=20)
    for a in anomalies:
        print(f"   • {a['description']}")
    
    # 3. Detect outliers
    print("\n3. Outliers:")
    outliers = preprocessor.detect_outliers(test_candles)
    print(f"   Found {len(outliers)} outliers: {outliers}")
    
    # 4. Full preprocessing
    print("\n4. Full Preprocessing:")
    processed, report = preprocessor.preprocess(
        test_candles,
        timeframe='15',
        fill_missing=True,
        detect_outliers=True,
        smooth_outliers=True
    )
    
    print(f"   Input: {report['input_count']} candles")
    print(f"   Output: {report['output_count']} candles")
    print(f"   Validation errors: {len(report['validation_errors'])}")
    print(f"   Outliers: {len(report['outliers'])}")
    print(f"   Anomalies: {len(report['anomalies'])}")
    
    # 5. Stats
    print("\n5. Statistics:")
    stats = preprocessor.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n" + "="*70)
    print("✅ Preprocessing completed")
    print("="*70)
