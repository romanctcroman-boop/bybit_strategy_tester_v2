"""
Base configuration for agent system
Contains feature flags and routing controls
"""

import os
from typing import Final

# ═══════════════════════════════════════════════════════════════════════════
# AGENT ROUTING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

# Force direct agent API (bypass MCP bridge)
# Set to True to use direct API calls instead of MCP bridge
# Default: True (use direct API)
FORCE_DIRECT_AGENT_API: Final[bool] = bool(
    int(os.getenv("FORCE_DIRECT_AGENT_API", "1"))
)

# Disable MCP bridge entirely
# Set to True to mark MCP as decommissioned; all tools run in direct mode
# Default: True (MCP disabled)
MCP_DISABLED: Final[bool] = bool(int(os.getenv("MCP_DISABLED", "1")))

# Deep Seek API availability flag
# Set to True if DeepSeek API integration is available
# Default: False (not available)
DEEPSEEK_AVAILABLE: Final[bool] = bool(os.getenv("DEEPSEEK_API_KEY", "").strip())

# Perplexity API availability flag
# Set to True if Perplexity API integration is available
# Default: False (not available)
PERPLEXITY_AVAILABLE: Final[bool] = bool(os.getenv("PERPLEXITY_API_KEY", "").strip())

# Agent memory configuration
# Use file-based memory (JSON) for agent conversations
AGENT_MEMORY_BACKEND: Final[str] = os.getenv("AGENT_MEMORY_BACKEND", "file")

# Agent memory directory
AGENT_MEMORY_DIR: Final[str] = os.getenv("AGENT_MEMORY_DIR", "agent_memory")

# Agent timeout (seconds)
AGENT_TIMEOUT_SECONDS: Final[int] = int(os.getenv("AGENT_TIMEOUT_SECONDS", "300"))

# Tool call budget limit (max tool calls per request)
TOOL_CALL_BUDGET: Final[int] = int(os.getenv("TOOL_CALL_BUDGET", "10"))

# ═══════════════════════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

AGENT_LOG_LEVEL: Final[str] = os.getenv("AGENT_LOG_LEVEL", "INFO")

# ═══════════════════════════════════════════════════════════════════════════
# DEBUG FLAGS
# ═══════════════════════════════════════════════════════════════════════════

# Enable detailed debug logging for agents
DEBUG_AGENTS: Final[bool] = bool(int(os.getenv("DEBUG_AGENTS", "0")))

# Enable agent communication tracing
DEBUG_AGENT_COMMUNICATION: Final[bool] = bool(
    int(os.getenv("DEBUG_AGENT_COMMUNICATION", "0"))
)

# ═══════════════════════════════════════════════════════════════════════════
# EXPORTED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    "FORCE_DIRECT_AGENT_API",
    "MCP_DISABLED",
    "DEEPSEEK_AVAILABLE",
    "PERPLEXITY_AVAILABLE",
    "AGENT_MEMORY_BACKEND",
    "AGENT_MEMORY_DIR",
    "AGENT_TIMEOUT_SECONDS",
    "AGENT_LOG_LEVEL",
    "DEBUG_AGENTS",
    "DEBUG_AGENT_COMMUNICATION",
]
