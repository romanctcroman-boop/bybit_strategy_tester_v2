"""
MCP Middleware
Provides Model Context Protocol integration middleware.

SECURITY: Uses constant-time comparison for auth token verification.
"""

import hmac
import logging
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


def _constant_time_compare(a: str | None, b: str | None) -> bool:
    """
    Constant-time string comparison to prevent timing attacks.

    Returns False if either value is None or they don't match.
    """
    if a is None or b is None:
        return False
    return hmac.compare_digest(a.encode(), b.encode())


class UnifiedMcpMiddleware(BaseHTTPMiddleware):
    """
    Middleware for unified MCP request handling.
    """

    def __init__(
        self,
        app,
        require_auth: bool = False,
        auth_token: str | None = None,
        allowed_origins: list[str] | None = None,
        **kwargs,
    ):
        super().__init__(app)
        self.require_auth = bool(require_auth)
        self.auth_token = auth_token
        self.allowed_origins = allowed_origins or []
        logger.info(f"UnifiedMcpMiddleware initialized (require_auth={self.require_auth})")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with MCP handling.

        Uses constant-time comparison for token verification to prevent timing attacks.
        """
        # Check auth if required
        if self.require_auth:
            token = request.headers.get("Authorization") or request.headers.get("X-MCP-Token")
            # Use constant-time comparison to prevent timing attacks
            if not token or (self.auth_token and not _constant_time_compare(token, self.auth_token)):
                return Response(
                    status_code=401,
                    content='{"message":"Unauthorized"}',
                    media_type="application/json",
                )

        response = await call_next(request)
        return response


__all__ = ["UnifiedMcpMiddleware"]
