"""
MCP Error Handling
Custom errors for Model Context Protocol operations.
"""


class MCPError(Exception):
    """Base class for MCP errors"""

    pass


class MCPConnectionError(MCPError):
    """MCP connection error"""

    pass


class MCPTimeoutError(MCPError):
    """MCP timeout error"""

    pass


class MCPValidationError(MCPError):
    """MCP validation error"""

    pass


class AgentUnavailableError(MCPError):
    """Agent unavailable error"""

    pass


def exception_to_mcp_error(exc: Exception) -> MCPError:
    """
    Convert generic exception to MCP error.

    Args:
        exc: Original exception

    Returns:
        Corresponding MCP error
    """
    if isinstance(exc, MCPError):
        return exc

    error_message = str(exc)

    if "timeout" in error_message.lower():
        return MCPTimeoutError(error_message)
    elif "connection" in error_message.lower():
        return MCPConnectionError(error_message)
    elif "validation" in error_message.lower():
        return MCPValidationError(error_message)
    elif "unavailable" in error_message.lower():
        return AgentUnavailableError(error_message)
    else:
        return MCPError(error_message)


__all__ = [
    "MCPError",
    "MCPConnectionError",
    "MCPTimeoutError",
    "MCPValidationError",
    "AgentUnavailableError",
    "exception_to_mcp_error",
]
