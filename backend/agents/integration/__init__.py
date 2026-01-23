"""
AI Integration Module

Connects AI Agent System with trading infrastructure:
- AIBacktestAnalyzer: AI-powered backtest result analysis
- AIOptimizationAnalyzer: AI-powered optimization interpretation
"""

from backend.agents.integration.ai_backtest_integration import (
    AIBacktestResult,
    AIOptimizationResult,
    AIBacktestAnalyzer,
    AIOptimizationAnalyzer,
    get_backtest_analyzer,
    get_optimization_analyzer,
)

__all__ = [
    "AIBacktestResult",
    "AIOptimizationResult",
    "AIBacktestAnalyzer",
    "AIOptimizationAnalyzer",
    "get_backtest_analyzer",
    "get_optimization_analyzer",
]
