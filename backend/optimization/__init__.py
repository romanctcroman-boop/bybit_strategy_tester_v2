"""
Optimization Module

Единый модуль для всех алгоритмов оптимизации стратегий (ТЗ 3.5).
Консолидированная реализация - исправление аномалии #1.

Доступные оптимизаторы:
- GridOptimizer: Простой перебор параметров (Grid Search)
- WalkForwardOptimizer: Защита от overfitting с IS/OOS окнами
- MonteCarloSimulator: Оценка рисков через bootstrap resampling

Исправлено: Удалены дубликаты (*_optimizer.py, *_simulator.py)
Дата: 2025-10-27
"""

from .grid_optimizer import GridOptimizer
from .walk_forward import (
    WalkForwardOptimizer,
    WFOConfig,
    WFOMode,
    WFOPeriod,
    ParameterRange as WFOParameterRange,
)
from .monte_carlo import MonteCarloSimulator, MonteCarloResult

__all__ = [
    # Grid Search
    'GridOptimizer',
    
    # Walk-Forward Optimization
    'WalkForwardOptimizer',
    'WFOConfig',
    'WFOMode',
    'WFOPeriod',
    'WFOParameterRange',
    
    # Monte Carlo Simulation
    'MonteCarloSimulator',
    'MonteCarloResult',
]
