"""
MCP Middleware
Provides Model Context Protocol integration middleware.
"""

import logging
from typing import Callable, List, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class UnifiedMcpMiddleware(BaseHTTPMiddleware):
    """
    Middleware for unified MCP request handling.
    """

    def __init__(
        self,
        app,
        require_auth: bool = False,
        auth_token: Optional[str] = None,
        allowed_origins: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(app)
        self.require_auth = bool(require_auth)
        self.auth_token = auth_token
        self.allowed_origins = allowed_origins or []
        logger.info(
            f"UnifiedMcpMiddleware initialized (require_auth={self.require_auth})"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with MCP handling. This is a stub for compatibility.
        """
        # Example: if require_auth is True, check header
        if self.require_auth:
            token = request.headers.get("Authorization") or request.headers.get(
                "X-MCP-Token"
            )
            if not token or (self.auth_token and token != self.auth_token):
                return Response(
                    status_code=401,
                    content='{"message":"Unauthorized"}',
                    media_type="application/json",
                )

        response = await call_next(request)
        return response


__all__ = ["UnifiedMcpMiddleware"]
