"""
Backend Middleware Package

Middleware components:
- cache_headers: HTTP cache headers (ETag, 304, Cache-Control)
- rate_limiter: Rate limiting (Phase 1 Security)
"""

from backend.middleware.cache_headers import CacheHeadersMiddleware

__all__ = ["CacheHeadersMiddleware"]
