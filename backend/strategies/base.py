"""
Base Strategy Interface

Абстрактный базовый класс для всех торговых стратегий.
Определяет единый интерфейс для интеграции с BacktestEngine.
"""
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class BaseStrategy(ABC):
    """Абстрактный базовый класс для торговых стратегий"""
    
    def __init__(self, config: dict[str, Any]):
        """
        Инициализация стратегии
        
        Args:
            config: Словарь с параметрами стратегии
            
        Raises:
            ValueError: Если конфигурация невалидна
        """
        self.config = config
        self.validate_config(config)
    
    @abstractmethod
    def on_start(self, data: pd.DataFrame) -> None:
        """
        Вызывается один раз перед началом бэктеста
        
        Используется для:
        - Предварительного расчёта индикаторов (vectorized)
        - Инициализации внутреннего состояния стратегии
        
        Args:
            data: Полный DataFrame с OHLCV данными
        """
        pass
    
    @abstractmethod
    def on_bar(self, bar: pd.Series, bar_index: int, data: pd.DataFrame) -> dict[str, Any] | None:
        """
        Вызывается на каждом баре для генерации сигналов
        
        Args:
            bar: Текущий бар (Series с open, high, low, close, volume, timestamp)
            bar_index: Индекс текущего бара в DataFrame
            data: DataFrame с историческими данными до текущего бара (включительно)
            
        Returns:
            Словарь с сигналом или None:
            {
                'action': 'LONG' | 'SHORT' | 'CLOSE',
                'reason': str,  # Описание причины сигнала
                'stop_loss': float (optional),
                'take_profit': float (optional),
                'entry_price': float (optional)
            }
        """
        pass
    
    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> bool:
        """
        Валидация конфигурации стратегии
        
        Args:
            config: Словарь с параметрами
            
        Returns:
            True если валидна
            
        Raises:
            ValueError: С описанием проблемы, если конфигурация невалидна
        """
        pass
    
    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        """
        Получить параметры по умолчанию
        
        Returns:
            Словарь с дефолтными значениями
        """
        return {}
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(config={self.config})"
