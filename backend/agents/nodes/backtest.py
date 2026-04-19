"""Execution & evaluation nodes.

* :class:`BacktestNode`           — runs FallbackEngineV4 on a generated graph.
* :class:`BacktestAnalysisNode`   — 166-metric TradingView parity analysis +
                                    :class:`RiskVetoGuard` gate.
* :class:`MLValidationNode`       — stability/overfitting ML checks.
"""

from backend.agents.trading_strategy_graph import (
    BacktestAnalysisNode,
    BacktestNode,
    MLValidationNode,
)

__all__ = [
    "BacktestAnalysisNode",
    "BacktestNode",
    "MLValidationNode",
]
