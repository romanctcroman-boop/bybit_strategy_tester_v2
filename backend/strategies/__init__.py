"""
Trading Strategies Module

Модуль торговых стратегий для бэктестинга.
Все стратегии реализуют интерфейс BaseStrategy.

Доступные стратегии:
- BollingerMeanReversionStrategy: Mean reversion на базе Bollinger Bands

Usage:
    from backend.strategies import StrategyFactory
    
    # Создать экземпляр стратегии
    strategy = StrategyFactory.create('bollinger', {
        'bb_period': 20,
        'bb_std_dev': 2.0,
        'entry_threshold_pct': 0.05,
        'stop_loss_pct': 0.8,
        'max_holding_bars': 48
    })
    
    # Инициализация перед бэктестом
    strategy.on_start(data)
    
    # Генерация сигналов
    for i in range(len(data)):
        bar = data.iloc[i]
        signal = strategy.on_bar(bar, i, data[:i+1])
        if signal:
            print(f"Signal: {signal}")
"""
from backend.strategies.base import BaseStrategy
from backend.strategies.bollinger_mean_reversion import BollingerMeanReversionStrategy
from backend.strategies.factory import StrategyFactory

__all__ = [
    'BaseStrategy',
    'StrategyFactory',
    'BollingerMeanReversionStrategy',
]
