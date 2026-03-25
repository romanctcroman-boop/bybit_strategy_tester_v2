"""Security headers middleware.

Adds a minimal set of HTTP response headers for safer defaults while keeping
the existing frontend working (allows inline scripts/styles for now).

Security headers included:
- Content-Security-Policy (CSP) with nonce support
- Referrer-Policy
- X-Content-Type-Options
- X-Frame-Options
- Cross-Origin-Resource-Policy
- Strict-Transport-Security (HSTS)
"""

import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security-related headers to every response."""

    def __init__(
        self,
        app,
        csp: str | None = None,
        enable_hsts: bool | None = None,
        hsts_max_age: int = 31536000,  # 1 year
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = False,
        use_csp_nonce: bool | None = None,
    ):
        super().__init__(app)

        # Environment-based configuration
        environment = os.environ.get("ENVIRONMENT", "development").lower()
        is_production = environment in ("staging", "production", "prod")

        # Determine if CSP nonce should be used
        # Default: enabled in production, disabled in development
        if use_csp_nonce is None:
            self.use_csp_nonce = is_production or os.environ.get("USE_CSP_NONCE", "false").lower() == "true"
        else:
            self.use_csp_nonce = use_csp_nonce

        # Store custom CSP or use template
        self._custom_csp = csp

        # HSTS configuration
        # Enable HSTS by default in production/staging environments
        if enable_hsts is None:
            self.enable_hsts = is_production
        else:
            self.enable_hsts = enable_hsts

        # Build HSTS header value
        hsts_parts = [f"max-age={hsts_max_age}"]
        if hsts_include_subdomains:
            hsts_parts.append("includeSubDomains")
        if hsts_preload:
            hsts_parts.append("preload")
        self.hsts_value = "; ".join(hsts_parts)

    def _generate_csp(self, nonce: str | None = None) -> str:
        """
        Generate CSP header value.

        Args:
            nonce: Optional nonce for script-src and style-src

        Returns:
            CSP header value string
        """
        if self._custom_csp:
            return self._custom_csp

        if nonce and self.use_csp_nonce:
            # Secure CSP with nonce - no unsafe-inline
            return (
                "default-src 'self'; "
                f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net https://unpkg.com; "
                f"style-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
                "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https: wss: ws: data:; "
                "frame-ancestors 'none'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )

        # Fallback CSP with unsafe-inline for development
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https: wss: ws: data:; "
            "frame-ancestors 'none'; "
            "object-src 'none'"
        )

    async def dispatch(self, request, call_next):  # type: ignore[override]
        # Generate nonce for this request
        nonce = secrets.token_urlsafe(16) if self.use_csp_nonce else None

        # Store nonce in request state for templates/frontend
        if nonce:
            request.state.csp_nonce = nonce

        response: Response = await call_next(request)

        # Generate CSP with nonce
        csp = self._generate_csp(nonce)

        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

        # Add HSTS header (only effective over HTTPS)
        if self.enable_hsts:
            response.headers.setdefault("Strict-Transport-Security", self.hsts_value)

        # Expose nonce header for frontend JavaScript
        if nonce:
            response.headers["X-CSP-Nonce"] = nonce

        return response
