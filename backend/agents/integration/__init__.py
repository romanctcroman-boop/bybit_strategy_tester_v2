"""
AI Integration Module

Connects AI Agent System with trading infrastructure:
- AIBacktestAnalyzer: AI-powered backtest result analysis
- AIOptimizationAnalyzer: AI-powered optimization interpretation
- BacktestBridge: Converts LLM strategies to engine-compatible format
"""

from backend.agents.integration.ai_backtest_integration import (
    AIBacktestAnalyzer,
    AIBacktestResult,
    AIOptimizationAnalyzer,
    AIOptimizationResult,
    get_backtest_analyzer,
    get_optimization_analyzer,
)
from backend.agents.integration.backtest_bridge import BacktestBridge

__all__ = [
    "AIBacktestAnalyzer",
    "AIBacktestResult",
    "AIOptimizationAnalyzer",
    "AIOptimizationResult",
    "BacktestBridge",
    "get_backtest_analyzer",
    "get_optimization_analyzer",
]
