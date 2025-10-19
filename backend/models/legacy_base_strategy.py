# -*- coding: utf-8 -*-
"""Базовый класс стратегии (интерфейс)"""
from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    """Абстрактный базовый класс для всех стратегий"""

    def __init__(self, params=None):
        """
        params: dict с параметрами стратегии
        """
        self.params = params or {}
        self.name = self.__class__.__name__

    @abstractmethod
    def generate_signals(self, df):
        """
        Генерация торговых сигналов

        Args:
            df: DataFrame с OHLCV данными

        Returns:
            DataFrame с сигналами (signal, position)
        """
        pass

    def get_param(self, key, default=None):
        """Безопасное получение параметра"""
        return self.params.get(key, default)

    def set_param(self, key, value):
        """Установка параметра"""
        self.params[key] = value

    def get_param_ranges(self):
        """
        Возвращает диапазоны параметров для оптимизации

        Returns:
            dict: {'param_name': (min, max, type)}
        """
        return {}
