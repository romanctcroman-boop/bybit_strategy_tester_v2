"""
Advanced Consensus Mechanisms for Multi-Agent Systems

This package provides sophisticated decision-making through agent collaboration:
- Multi-Agent Deliberation: Structured debate and refinement
- Specialized Domain Agents: Expert agents for specific tasks
- Voting Strategies: Multiple consensus algorithms
- Evidence Chain Building: Traceable reasoning

Based on research:
- "Multi-Agent Debate" (Du et al., 2023)
- "Society of Mind" (Minsky, 1986)
- "Swarm Intelligence" patterns
"""

from backend.agents.consensus.consensus_engine import (
    AgentPerformance,
    ConsensusEngine,
    ConsensusMethod,
    ConsensusResult,
)
from backend.agents.consensus.deliberation import (
    AgentVote,
    DeliberationResult,
    MultiAgentDeliberation,
    VotingStrategy,
)
from backend.agents.consensus.domain_agents import (
    CodeAuditAgent,
    DomainAgent,
    DomainAgentRegistry,
    MarketResearchAgent,
    RiskManagementAgent,
    TradingStrategyAgent,
)
from backend.agents.consensus.perplexity_integration import (
    AgentSignal,
    CrossValidationResult,
    PerplexityIntegration,
    PerplexityRelevance,
    get_perplexity_integration,
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
    "AgentSignal",
    "AgentVote",
    "CodeAuditAgent",
    "ConsensusEngine",
    "ConsensusMethod",
    "ConsensusResult",
    "CrossValidationResult",
    "DeliberationResult",
    "DomainAgent",
    "DomainAgentRegistry",
    "MarketResearchAgent",
    "MultiAgentDeliberation",
    "PerplexityIntegration",
    "PerplexityRelevance",
    "RiskManagementAgent",
    "RiskVetoGuard",
    "TradingStrategyAgent",
    "VetoConfig",
    "VetoDecision",
    "VetoReason",
    "VotingStrategy",
    "get_perplexity_integration",
    "get_risk_veto_guard",
]
