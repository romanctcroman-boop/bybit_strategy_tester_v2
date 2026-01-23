"""
Agent Modules Package

This package contains refactored modules from unified_agent_interface.py:

- key_manager: API key management, health tracking, cooldown logic
- request_response: AgentRequest, AgentResponse, TokenUsage models
- models: AgentType, AgentChannel enums (original location)

Usage:
    from backend.agents.key_manager import APIKeyManager, get_key_manager
    from backend.agents.request_response import AgentRequest, AgentResponse, TokenUsage
    from backend.agents.models import AgentType, AgentChannel
"""

# Re-export commonly used classes for convenience
from backend.agents.key_manager import (
    APIKey,
    APIKeyHealth,
    APIKeyManager,
    get_key_manager,
)
from backend.agents.models import AgentChannel, AgentType
from backend.agents.request_response import (
    AgentRequest,
    AgentResponse,
    TokenUsage,
)

__all__ = [
    # Enums
    "AgentType",
    "AgentChannel",
    "APIKeyHealth",
    # Key management
    "APIKey",
    "APIKeyManager",
    "get_key_manager",
    # Request/Response
    "AgentRequest",
    "AgentResponse",
    "TokenUsage",
]
