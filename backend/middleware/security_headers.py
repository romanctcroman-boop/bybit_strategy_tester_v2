"""Security headers middleware.

Adds a minimal set of HTTP response headers for safer defaults while keeping
the existing frontend working (allows inline scripts/styles for now).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security-related headers to every response."""

    def __init__(self, app, csp: str | None = None):
        super().__init__(app)
        # Allow CDN scripts and inline for development
        self.csp = csp or (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https: wss: ws: data:; "
            "frame-ancestors 'self'; "
            "object-src 'none'"
        )

    async def dispatch(self, request, call_next):  # type: ignore[override]
        response: Response = await call_next(request)

        response.headers.setdefault("Content-Security-Policy", self.csp)
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

        return response
