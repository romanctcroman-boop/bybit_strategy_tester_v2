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

from backend.agents.consensus.deliberation import (
    MultiAgentDeliberation,
    AgentVote,
    VotingStrategy,
    DeliberationResult,
)
from backend.agents.consensus.domain_agents import (
    DomainAgent,
    TradingStrategyAgent,
    RiskManagementAgent,
    CodeAuditAgent,
    MarketResearchAgent,
    DomainAgentRegistry,
)

__all__ = [
    "MultiAgentDeliberation",
    "AgentVote",
    "VotingStrategy",
    "DeliberationResult",
    "DomainAgent",
    "TradingStrategyAgent",
    "RiskManagementAgent",
    "CodeAuditAgent",
    "MarketResearchAgent",
    "DomainAgentRegistry",
]
