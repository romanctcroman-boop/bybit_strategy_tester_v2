"""
AI Strategy Optimization Module.

Provides parameter optimization for LLM-generated strategies:
- StrategyOptimizer: genetic, grid, and bayesian optimization
"""

from backend.agents.optimization.strategy_optimizer import StrategyOptimizer

__all__ = [
    "StrategyOptimizer",
]
