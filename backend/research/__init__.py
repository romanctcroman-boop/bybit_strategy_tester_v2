"""
🔬 Research Module

Advanced research features:
- Multi-agent simulation
- Real-time parameter adaptation
- Explainable AI
- Blockchain verification
- Federated learning

@version: 1.0.0
@date: 2026-02-26
"""

from .blockchain_verification import BacktestProof, BacktestVerifier
from .explainable_ai import LIMEExplainer, SHAPExplainer, SignalExplanation
from .federated_learning import FederatedLearning, LocalModel
from .multi_agent_simulation import Agent, AgentType, MarketSimulator
from .parameter_adaptation import MarketRegime, ParameterAdapter

__all__ = [
    "Agent",
    "AgentType",
    "BacktestProof",
    # Blockchain verification
    "BacktestVerifier",
    # Federated learning
    "FederatedLearning",
    "LIMEExplainer",
    "LocalModel",
    "MarketRegime",
    # Multi-agent simulation
    "MarketSimulator",
    # Parameter adaptation
    "ParameterAdapter",
    # Explainable AI
    "SHAPExplainer",
    "SignalExplanation",
]
