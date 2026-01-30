"""
🔒 CSRF Protection Middleware - Bybit Strategy Tester v2

Cross-Site Request Forgery protection using double-submit cookie pattern.

Fixes P0-2: CSRF Protection

@version 1.0.0
@date 2026-01-28
"""

import secrets
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.core.logging_config import get_logger

logger = get_logger(__name__)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware using double-submit cookie pattern.

    The middleware:
    1. Sets a CSRF token in a cookie on first request
    2. For state-changing requests (POST, PUT, DELETE, PATCH),
       validates that the X-CSRF-Token header matches the cookie

    Usage:
        app.add_middleware(CSRFMiddleware)

    Frontend must:
    1. Read the csrf_token cookie
    2. Include it in X-CSRF-Token header for all POST/PUT/DELETE requests
    """

    SAFE_METHODS: set[str] = {"GET", "HEAD", "OPTIONS", "TRACE"}
    COOKIE_NAME: str = "csrf_token"
    HEADER_NAME: str = "X-CSRF-Token"
    TOKEN_LENGTH: int = 32

    def __init__(
        self,
        app: ASGIApp,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        cookie_secure: bool = True,
        cookie_httponly: bool = False,  # False so JS can read it
        cookie_samesite: str = "strict",
        exempt_paths: set[str] | None = None,
        exempt_prefixes: set[str] | None = None,
    ):
        """
        Initialize CSRF middleware.

        Args:
            app: ASGI application
            cookie_name: Name of the CSRF cookie
            header_name: Name of the CSRF header
            cookie_secure: Set Secure flag on cookie (True for HTTPS)
            cookie_httponly: Set HttpOnly flag (False to allow JS access)
            cookie_samesite: SameSite policy ('strict', 'lax', 'none')
            exempt_paths: Exact paths to exempt from CSRF
            exempt_prefixes: Path prefixes to exempt from CSRF
        """
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.cookie_secure = cookie_secure
        self.cookie_httponly = cookie_httponly
        self.cookie_samesite = cookie_samesite

        # Default exempt paths (webhooks, public APIs)
        self.exempt_paths = exempt_paths or {
            "/api/v1/webhooks/tradingview",
            "/api/v1/webhooks/bybit",
            "/api/v1/health",
            "/health",
            "/metrics",
        }

        # Default exempt prefixes (API docs, static)
        self.exempt_prefixes = exempt_prefixes or {
            "/docs",
            "/redoc",
            "/openapi.json",
            "/static/",
            "/assets/",
        }

    def _generate_token(self) -> str:
        """Generate a cryptographically secure CSRF token."""
        return secrets.token_hex(self.TOKEN_LENGTH)

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from CSRF protection."""
        # Exact path match
        if path in self.exempt_paths:
            return True

        # Prefix match
        return any(path.startswith(prefix) for prefix in self.exempt_prefixes)

    def _get_cookie_token(self, request: Request) -> str | None:
        """Get CSRF token from cookie."""
        return request.cookies.get(self.cookie_name)

    def _get_header_token(self, request: Request) -> str | None:
        """Get CSRF token from header."""
        return request.headers.get(self.header_name)

    def _validate_token(self, cookie_token: str | None, header_token: str | None) -> bool:
        """
        Validate that header token matches cookie token.
        Uses constant-time comparison to prevent timing attacks.
        """
        if not cookie_token or not header_token:
            return False

        return secrets.compare_digest(cookie_token, header_token)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with CSRF protection."""

        # Get existing token from cookie
        cookie_token = self._get_cookie_token(request)

        # Generate new token if none exists
        new_token = None
        if not cookie_token:
            new_token = self._generate_token()
            cookie_token = new_token

        # Check if this is a state-changing request that requires CSRF validation
        if request.method not in self.SAFE_METHODS and not self._is_exempt(request.url.path):
            # Validate CSRF token
            header_token = self._get_header_token(request)

            if not self._validate_token(cookie_token, header_token):
                logger.warning(
                    "CSRF validation failed",
                    path=request.url.path,
                    method=request.method,
                    client_ip=request.client.host if request.client else "unknown",
                )
                return Response(
                    content='{"detail": "CSRF token missing or invalid"}',
                    status_code=403,
                    media_type="application/json",
                )

        # Process request
        response = await call_next(request)

        # Set CSRF cookie if new token was generated
        if new_token:
            response.set_cookie(
                key=self.cookie_name,
                value=new_token,
                httponly=self.cookie_httponly,
                secure=self.cookie_secure,
                samesite=self.cookie_samesite,
                path="/",
                max_age=86400,  # 24 hours
            )

        return response


class CSRFExempt:
    """
    Decorator to mark a route as CSRF exempt.

    Usage:
        @router.post("/webhook")
        @csrf_exempt
        async def webhook_handler():
            ...

    Note: This sets an attribute that can be checked by middleware,
    but the current implementation uses path-based exemption.
    """

    def __init__(self, func: Callable):
        self.func = func
        func._csrf_exempt = True

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


# Convenient alias
csrf_exempt = CSRFExempt


def get_csrf_token(request: Request) -> str | None:
    """
    Get CSRF token from request.
    Useful for including in rendered templates.

    Args:
        request: FastAPI request

    Returns:
        CSRF token string or None
    """
    return request.cookies.get(CSRFMiddleware.COOKIE_NAME)
