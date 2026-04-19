"""
Advanced Consensus Mechanisms for Multi-Agent Systems

This package provides consensus decision-making through agent collaboration.
Note: the debate/deliberation system has been removed.
"""

from backend.agents.consensus.consensus_engine import (
    AgentPerformance,
    ConsensusEngine,
    ConsensusMethod,
    ConsensusResult,
)
from backend.agents.consensus.risk_veto_guard import (
    RiskVetoGuard,
    VetoConfig,
    VetoDecision,
    VetoReason,
    get_risk_veto_guard,
)

__all__ = [
    "AgentPerformance",
    "ConsensusEngine",
    "ConsensusMethod",
    "ConsensusResult",
    "RiskVetoGuard",
    "VetoConfig",
    "VetoDecision",
    "VetoReason",
    "get_risk_veto_guard",
]
