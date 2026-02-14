"""
Agent Modules Package

This package contains refactored modules:

- key_models: APIKey, APIKeyHealth (single source of truth)
- key_manager: APIKeyManager with health tracking, cooldown logic
- request_models: AgentRequest, AgentResponse, TokenUsage
- models: AgentType, AgentChannel enums

Usage:
    from backend.agents.key_models import APIKey, APIKeyHealth
    from backend.agents.key_manager import APIKeyManager, get_key_manager
    from backend.agents.request_models import AgentRequest, AgentResponse, TokenUsage
    from backend.agents.models import AgentType, AgentChannel
"""

# Re-export commonly used classes for convenience
from backend.agents.key_manager import (
    APIKeyManager,
    get_key_manager,
)
from backend.agents.key_models import APIKey, APIKeyHealth
from backend.agents.models import AgentChannel, AgentType
from backend.agents.request_models import (
    AgentRequest,
    AgentResponse,
    TokenUsage,
)

__all__ = [
    "APIKey",
    "APIKeyHealth",
    "APIKeyManager",
    "AgentChannel",
    "AgentRequest",
    "AgentResponse",
    "AgentType",
    "TokenUsage",
    "get_key_manager",
]
