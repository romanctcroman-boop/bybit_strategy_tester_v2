"""
Strategy Factory

Фабрика для создания экземпляров торговых стратегий.
Реализует паттерн Factory для отделения создания стратегий от их использования.
"""
from typing import Any

from backend.strategies.base import BaseStrategy
from backend.strategies.bollinger_mean_reversion import BollingerMeanReversionStrategy


class StrategyFactory:
    """Фабрика для создания экземпляров торговых стратегий"""
    
    # Реестр доступных стратегий
    _strategies: dict[str, type[BaseStrategy]] = {
        'bollinger': BollingerMeanReversionStrategy,
        'bollinger_mean_reversion': BollingerMeanReversionStrategy,
    }
    
    @classmethod
    def create(cls, strategy_type: str, config: dict[str, Any]) -> BaseStrategy:
        """
        Создать экземпляр стратегии
        
        Args:
            strategy_type: Тип стратегии ('bollinger', 'bollinger_mean_reversion')
            config: Конфигурация стратегии
            
        Returns:
            Экземпляр стратегии
            
        Raises:
            ValueError: Если тип стратегии неизвестен или конфигурация невалидна
            
        Example:
            >>> factory = StrategyFactory()
            >>> strategy = factory.create('bollinger', {'bb_period': 20, 'bb_std_dev': 2.0})
            >>> signal = strategy.on_bar(bar, bar_index, data)
        """
        if strategy_type not in cls._strategies:
            available = ', '.join(cls._strategies.keys())
            raise ValueError(
                f"Unknown strategy type: '{strategy_type}'. "
                f"Available strategies: {available}"
            )
        
        strategy_class = cls._strategies[strategy_type]
        
        try:
            strategy = strategy_class(config)
        except ValueError as e:
            raise ValueError(f"Invalid configuration for '{strategy_type}': {e}")
        
        return strategy
    
    @classmethod
    def register_strategy(cls, name: str, strategy_class: type[BaseStrategy]) -> None:
        """
        Зарегистрировать кастомную стратегию
        
        Args:
            name: Идентификатор стратегии (например, 'my_custom_strategy')
            strategy_class: Класс стратегии, наследующий BaseStrategy
            
        Raises:
            ValueError: Если strategy_class не наследует BaseStrategy
            
        Example:
            >>> class MyStrategy(BaseStrategy):
            ...     pass
            >>> StrategyFactory.register_strategy('my_strategy', MyStrategy)
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError(f"{strategy_class} must extend BaseStrategy")
        
        cls._strategies[name] = strategy_class
    
    @classmethod
    def list_strategies(cls) -> list[str]:
        """
        Получить список всех доступных стратегий
        
        Returns:
            Список названий стратегий
            
        Example:
            >>> StrategyFactory.list_strategies()
            ['bollinger', 'bollinger_mean_reversion']
        """
        return list(cls._strategies.keys())
    
    @classmethod
    def get_strategy_info(cls, strategy_type: str) -> dict[str, Any]:
        """
        Получить информацию о стратегии
        
        Args:
            strategy_type: Идентификатор стратегии
            
        Returns:
            Словарь с метаданными стратегии:
            - name: Название стратегии
            - class: Имя класса
            - default_params: Параметры по умолчанию
            - docstring: Документация
            
        Raises:
            ValueError: Если стратегия неизвестна
        """
        if strategy_type not in cls._strategies:
            raise ValueError(f"Unknown strategy: {strategy_type}")
        
        strategy_class = cls._strategies[strategy_type]
        
        return {
            'name': strategy_type,
            'class': strategy_class.__name__,
            'default_params': strategy_class.get_default_params(),
            'docstring': strategy_class.__doc__
        }
