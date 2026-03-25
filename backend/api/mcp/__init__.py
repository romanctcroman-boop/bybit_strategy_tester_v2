"""
MCP Module for Bybit Strategy Tester

Provides Model Context Protocol (MCP) integration with FastMCP.
Includes circuit breaker, tools, and resources.
"""

from backend.api.mcp.circuit_breaker import (
    CB_THRESHOLD,
    CB_TIMEOUT,
    MAX_CONCURRENCY,
    CircuitBreaker,
    circuit_breakers,
    get_circuit_breaker,
    mcp_semaphore,
)


# Lazy imports for tools to avoid circular dependencies
def register_all_tools(mcp):
    """Register all MCP tools with the server."""
    from backend.api.mcp.tools.agent_tools import register_agent_tools
    from backend.api.mcp.tools.file_tools import register_file_tools

    register_agent_tools(mcp)
    register_file_tools(mcp)


__all__ = [
    "CB_THRESHOLD",
    "CB_TIMEOUT",
    "MAX_CONCURRENCY",
    "CircuitBreaker",
    "circuit_breakers",
    "get_circuit_breaker",
    "mcp_semaphore",
    "register_all_tools",
]
