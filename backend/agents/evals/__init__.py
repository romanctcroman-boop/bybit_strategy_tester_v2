"""
Agent Evaluation & Benchmarking Suite

Provides standardized evaluation tools for measuring AI agent quality:
- BenchmarkSuite: Runs benchmark tests across response quality, latency, accuracy
- StrategyEval: Trading-strategy-specific evaluations (signal quality, PnL reasoning)
- ScoreCard: Aggregated evaluation report with grading

Usage:
    from backend.agents.evals import BenchmarkSuite, StrategyEval

    suite = BenchmarkSuite()
    result = await suite.run_all()
    print(result.overall_score)
"""

from backend.agents.evals.benchmark_suite import (
    BenchmarkCase,
    BenchmarkResult,
    BenchmarkSuite,
    EvalMetric,
    ScoreCard,
)
from backend.agents.evals.strategy_eval import (
    SignalQualityResult,
    StrategyEval,
    StrategyEvalResult,
)

__all__ = [
    "BenchmarkCase",
    "BenchmarkResult",
    "BenchmarkSuite",
    "EvalMetric",
    "ScoreCard",
    "SignalQualityResult",
    "StrategyEval",
    "StrategyEvalResult",
]
