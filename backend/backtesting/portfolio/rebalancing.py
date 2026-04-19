"""
📊 Rebalancing Strategies

Стратегии ребалансировки портфеля.
"""

from abc import ABC, abstractmethod

import pandas as pd


class RebalancingStrategy(ABC):
    """Базовый класс для стратегий ребалансировки"""

    @abstractmethod
    def should_rebalance(
        self, current_weights: dict[str, float], target_weights: dict[str, float], current_date: pd.Timestamp
    ) -> bool:
        """Проверка необходимости ребалансировки"""
        pass

    @abstractmethod
    def get_target_weights(self, prices: dict[str, float], current_date: pd.Timestamp) -> dict[str, float]:
        """Получить целевые веса"""
        pass


class PeriodicRebalancing(RebalancingStrategy):
    """
    Периодическая ребалансировка.

    Args:
        frequency: 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'
        target_weights: Целевые веса портфеля
    """

    def __init__(self, frequency: str = "monthly", target_weights: dict[str, float] | None = None):
        self.frequency = frequency
        self.target_weights = target_weights or {}
        self.last_rebalance: pd.Timestamp | None = None

    def should_rebalance(
        self, current_weights: dict[str, float], target_weights: dict[str, float], current_date: pd.Timestamp
    ) -> bool:
        if self.last_rebalance is None:
            return True

        # Проверка периода
        days_diff = (current_date - self.last_rebalance).days

        if self.frequency == "daily":
            return days_diff >= 1
        elif self.frequency == "weekly":
            return days_diff >= 7
        elif self.frequency == "monthly":
            return days_diff >= 30
        elif self.frequency == "quarterly":
            return days_diff >= 90
        elif self.frequency == "yearly":
            return days_diff >= 365

        return False

    def get_target_weights(self, prices: dict[str, float], current_date: pd.Timestamp) -> dict[str, float]:
        """Возвращает целевые веса"""
        if self.target_weights:
            return self.target_weights.copy()

        # Равные веса по умолчанию
        n_assets = len(prices)
        if n_assets == 0:
            return {}
        return dict.fromkeys(prices, 1.0 / n_assets)

    def on_rebalance(self, date: pd.Timestamp):
        """Вызывается после ребалансировки"""
        self.last_rebalance = date


class ThresholdRebalancing(RebalancingStrategy):
    """
    Ребалансировка по отклонению весов.

    Args:
        threshold: Порог отклонения (0.05 = 5%)
    """

    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold

    def should_rebalance(
        self, current_weights: dict[str, float], target_weights: dict[str, float], current_date: pd.Timestamp
    ) -> bool:
        for symbol in target_weights:
            current = current_weights.get(symbol, 0)
            target = target_weights[symbol]

            if abs(current - target) > self.threshold:
                return True

        return False

    def get_target_weights(self, prices: dict[str, float], current_date: pd.Timestamp) -> dict[str, float]:
        return {}
