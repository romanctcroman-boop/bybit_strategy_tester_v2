"""
Base configuration for agent system.

Uses Pydantic BaseSettings for validated, typed configuration from env vars.
All raw ``os.getenv()`` calls are replaced with a single validated model.

Usage:
    from backend.agents.base_config import FORCE_DIRECT_AGENT_API, MCP_DISABLED
    # Module-level constants remain backward-compatible.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Final

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    """Validated agent configuration from environment variables."""

    # Agent routing
    force_direct_agent_api: bool = Field(
        default=True,
        description="Force direct agent API (bypass MCP bridge).",
    )
    mcp_disabled: bool = Field(
        default=True,
        description="Disable MCP bridge entirely.",
    )

    # API availability (derived from key presence)
    deepseek_api_key: str = Field(default="", description="DeepSeek API key.")
    perplexity_api_key: str = Field(default="", description="Perplexity API key.")

    # Memory
    agent_memory_backend: str = Field(
        default="file",
        description="Memory backend type: file | sqlite.",
    )
    agent_memory_dir: str = Field(
        default="agent_memory",
        description="Directory for file-based agent memory.",
    )

    # Timeouts & budgets
    agent_timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Agent request timeout in seconds.",
    )
    tool_call_budget: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Max tool calls per single agent request.",
    )

    # Logging
    agent_log_level: str = Field(
        default="INFO",
        description="Agent subsystem log level.",
    )

    # Debug
    debug_agents: bool = Field(
        default=False,
        description="Enable detailed debug logging for agents.",
    )
    debug_agent_communication: bool = Field(
        default=False,
        description="Enable agent communication tracing.",
    )

    @field_validator("agent_log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"agent_log_level must be one of {allowed}, got '{v}'")
        return upper

    @field_validator("agent_memory_backend")
    @classmethod
    def _validate_backend(cls, v: str) -> str:
        allowed = {"file", "sqlite"}
        if v not in allowed:
            raise ValueError(f"agent_memory_backend must be one of {allowed}, got '{v}'")
        return v

    model_config = {
        "env_prefix": "",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def _get_settings() -> AgentSettings:
    """Cached singleton — parsed once, reused everywhere."""
    return AgentSettings()


# ═══════════════════════════════════════════════════════════════════════════
# BACKWARD-COMPATIBLE MODULE-LEVEL CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
_settings = _get_settings()

FORCE_DIRECT_AGENT_API: Final[bool] = _settings.force_direct_agent_api
MCP_DISABLED: Final[bool] = _settings.mcp_disabled
DEEPSEEK_AVAILABLE: Final[bool] = bool(_settings.deepseek_api_key.strip())
PERPLEXITY_AVAILABLE: Final[bool] = bool(_settings.perplexity_api_key.strip())
AGENT_MEMORY_BACKEND: Final[str] = _settings.agent_memory_backend
AGENT_MEMORY_DIR: Final[str] = _settings.agent_memory_dir
AGENT_TIMEOUT_SECONDS: Final[int] = _settings.agent_timeout_seconds
TOOL_CALL_BUDGET: Final[int] = _settings.tool_call_budget
AGENT_LOG_LEVEL: Final[str] = _settings.agent_log_level
DEBUG_AGENTS: Final[bool] = _settings.debug_agents
DEBUG_AGENT_COMMUNICATION: Final[bool] = _settings.debug_agent_communication


__all__ = [
    "AGENT_LOG_LEVEL",
    "AGENT_MEMORY_BACKEND",
    "AGENT_MEMORY_DIR",
    "AGENT_TIMEOUT_SECONDS",
    "AgentSettings",
    "DEBUG_AGENTS",
    "DEBUG_AGENT_COMMUNICATION",
    "DEEPSEEK_AVAILABLE",
    "FORCE_DIRECT_AGENT_API",
    "MCP_DISABLED",
    "PERPLEXITY_AVAILABLE",
    "TOOL_CALL_BUDGET",
]
