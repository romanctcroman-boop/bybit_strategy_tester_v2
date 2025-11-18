"""
Optimization Module

Модули оптимизации стратегий (ТЗ 3.5):
- GridOptimizer: Простой перебор параметров
- WalkForwardOptimizer: Защита от overfitting
- MonteCarloSimulator: Оценка рисков
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
    'GridOptimizer',
    'WalkForwardOptimizer',
    'WFOConfig',
    'WFOMode',
    'WFOPeriod',
    'WFOParameterRange',
    'MonteCarloSimulator',
    'MonteCarloResult',
]
