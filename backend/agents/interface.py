"""
Agent interface module - re-exports from unified_agent_interface
This module provides compatibility with existing import statements
"""

from backend.agents.unified_agent_interface import (
    AgentChannel,
    AgentRequest,
    AgentResponse,
    UnifiedAgentInterface,
    get_agent_interface,
)

__all__ = [
    "AgentChannel",
    "AgentRequest",
    "AgentResponse",
    "UnifiedAgentInterface",
    "get_agent_interface",
]
