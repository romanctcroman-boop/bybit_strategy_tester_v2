"""
Optimization Module

Модули оптимизации стратегий (ТЗ 3.5):
- GridOptimizer: Простой перебор параметров
- WalkForwardOptimizer: Защита от overfitting
- MonteCarloSimulator: Оценка рисков
"""

from .grid_optimizer import GridOptimizer

__all__ = ['GridOptimizer']
