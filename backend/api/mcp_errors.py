"""
MCP Error Taxonomy with JSON-RPC Code Mapping
Per Agent Recommendations (DeepSeek + Perplexity 2025-11-16)
"""

from typing import Any

from fastapi.responses import JSONResponse


class McpError(Exception):
    """Base class for MCP errors with JSON-RPC and HTTP code mapping"""
    
    def __init__(
        self,
        message: str,
        error_type: str = None,
        json_rpc_code: int = -32603,
        http_code: int = 500,
        details: dict[str, Any] | None = None
    ):
        self.message = message
        self.error_type = error_type or self.__class__.__name__
        self.json_rpc_code = json_rpc_code
        self.http_code = http_code
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize error to dictionary"""
        return {
            "success": False,
            "error": self.message,
            "error_type": self.error_type,
            "jsonrpc_error_code": self.json_rpc_code,
            **self.details
        }


class ValidationError(McpError):
    """Invalid parameters or request validation failure"""
    
    def __init__(self, message: str = "Invalid parameters", details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_type="ValidationError",
            json_rpc_code=-32602,  # JSON-RPC 2.0 standard: Invalid params
            http_code=422,
            details=details
        )


class AuthError(McpError):
    """Authentication or authorization failure"""
    
    def __init__(self, message: str = "Authentication required", details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_type="AuthError",
            json_rpc_code=-32001,  # Custom application error
            http_code=401,
            details=details
        )


class NetworkError(McpError):
    """Network communication or external service failure"""
    
    def __init__(self, message: str = "Network communication failed", details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_type="NetworkError",
            json_rpc_code=-32603,  # JSON-RPC 2.0 standard: Internal error
            http_code=500,
            details=details
        )


class AgentUnavailableError(McpError):
    """AI Agent service unavailable"""
    
    def __init__(self, message: str = "Agent service unavailable", details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_type="AgentUnavailableError",
            json_rpc_code=-32002,  # Custom application error
            http_code=503,
            details=details
        )


class ToolNotFoundError(McpError):
    """MCP tool not found"""
    
    def __init__(self, message: str = "Tool not found", details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_type="ToolNotFoundError",
            json_rpc_code=-32601,  # JSON-RPC 2.0 standard: Method not found
            http_code=404,
            details=details
        )


def error_to_response(error: McpError) -> JSONResponse:
    """Convert McpError to FastAPI JSONResponse"""
    return JSONResponse(
        status_code=error.http_code,
        content=error.to_dict()
    )


def exception_to_mcp_error(exc: Exception) -> McpError:
    """Convert generic exception to McpError"""
    # Map common exception types
    if isinstance(exc, McpError):
        return exc
    elif "validation" in exc.__class__.__name__.lower() or "pydantic" in exc.__class__.__module__.lower():
        return ValidationError(str(exc))
    elif "auth" in exc.__class__.__name__.lower() or "permission" in exc.__class__.__name__.lower():
        return AuthError(str(exc))
    elif "network" in exc.__class__.__name__.lower() or "connection" in exc.__class__.__name__.lower():
        return NetworkError(str(exc))
    else:
        # Generic internal error
        return McpError(
            message=str(exc),
            error_type=exc.__class__.__name__,
            json_rpc_code=-32603,
            http_code=500
        )
