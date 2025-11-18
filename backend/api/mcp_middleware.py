"""
Unified MCP Middleware with Auth + CORS + Preflight Handling
Per Agent Recommendations (DeepSeek + Perplexity 2025-11-16)

Replaces separate McpHardeningMiddleware to eliminate CORS conflicts
"""

import logging
import os

from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class UnifiedMcpMiddleware(BaseHTTPMiddleware):
    """
    Path-aware middleware for /mcp routes combining:
    - Bearer token authentication (feature-flagged)
    - Strict CORS policy override
    - Preflight OPTIONS handling
    """
    
    def __init__(self, app, require_auth: bool = False, auth_token: str = "", allowed_origins: list[str] = None):
        super().__init__(app)
        self.require_auth = require_auth
        self.auth_token = auth_token
        self.allowed_origins = allowed_origins or ["http://localhost:5173", "http://127.0.0.1:5173"]
        self.logger = logging.getLogger("uvicorn.error")
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Only apply to /mcp routes
        if not path.startswith("/mcp"):
            return await call_next(request)
        
        # Handle preflight OPTIONS request
        if request.method == "OPTIONS":
            return self._build_cors_response(request)
        
        # Bearer auth check (if enabled)
        if self.require_auth:
            if not self._validate_auth(request):
                self.logger.warning(f"MCP auth failure for path={path} origin={request.headers.get('origin')}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "unauthorized",
                        "message": "Missing or invalid Authorization header",
                        "error_type": "AuthError",
                        "jsonrpc_error_code": -32001
                    }
                )
        
        # Process request
        response = await call_next(request)
        
        # Apply strict CORS headers
        return self._apply_cors_headers(request, response)
    
    def _validate_auth(self, request: Request) -> bool:
        """Validate Bearer token"""
        if not self.auth_token:
            return False
        
        expected = f"Bearer {self.auth_token}"
        received = request.headers.get("Authorization", "")
        return received == expected
    
    def _build_cors_response(self, request: Request) -> Response:
        """Build preflight CORS response"""
        origin = request.headers.get("origin")
        allow_origin = self._get_allowed_origin(origin)
        
        if allow_origin is None:
            # Return 403 for disallowed origins (per Perplexity recommendation)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "forbidden",
                    "message": f"Origin '{origin}' not allowed",
                    "error_type": "CORSError",
                    "jsonrpc_error_code": -32003
                }
            )
        
        headers = {
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, mcp-session-id",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "86400"
        }
        
        return Response(content=b"", status_code=status.HTTP_200_OK, headers=headers)
    
    def _apply_cors_headers(self, request: Request, response: Response) -> Response:
        """Apply CORS headers to response"""
        origin = request.headers.get("origin")
        allow_origin = self._get_allowed_origin(origin)
        
        if allow_origin is None:
            # Return 403 for disallowed origins (per Perplexity recommendation)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "forbidden",
                    "message": f"Origin '{origin}' not allowed",
                    "error_type": "CORSError",
                    "jsonrpc_error_code": -32003
                }
            )
        
        response.headers["Access-Control-Allow-Origin"] = allow_origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, mcp-session-id"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
    
    def _get_allowed_origin(self, origin: str) -> str:
        """
        Get allowed origin or None for disallowed
        Per Perplexity: Return 403 instead of fallback
        """
        if not origin:
            # No origin header - allow (direct API calls, curl, etc.)
            return self.allowed_origins[0]
        
        if origin in self.allowed_origins:
            return origin
        
        # Disallowed origin - return None to trigger 403
        return None


def create_unified_mcp_middleware(app) -> UnifiedMcpMiddleware:
    """Factory function to create UnifiedMcpMiddleware from environment"""
    require_auth = int(os.getenv("MCP_REQUIRE_AUTH", "0")) == 1
    auth_token = os.getenv("MCP_AUTH_TOKEN", "")
    allowed_origins_str = os.getenv(
        "MCP_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    allowed_origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]
    
    return UnifiedMcpMiddleware(
        app=app,
        require_auth=require_auth,
        auth_token=auth_token,
        allowed_origins=allowed_origins
    )
