"""
MCP Error Handling
Custom errors for Model Context Protocol operations.
"""


class MCPError(Exception):
    """Base class for MCP errors"""

    @property
    def error_type(self) -> str:
        """Return the error class name as the error type."""
        return type(self).__name__

    def to_dict(self) -> dict:
        """Serialize the error to a dict for MCP responses."""
        return {
            "success": False,
            "error": str(self),
            "error_type": self.error_type,
        }


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
    "AgentUnavailableError",
    "MCPConnectionError",
    "MCPError",
    "MCPTimeoutError",
    "MCPValidationError",
    "exception_to_mcp_error",
]
