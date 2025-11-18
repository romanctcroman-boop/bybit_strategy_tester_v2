"""
HTTP Cache Headers Middleware

Implements HTTP caching best practices:
- ETag generation (MD5 hash of response content)
- Last-Modified tracking
- 304 Not Modified responses
- Cache-Control headers
- Conditional requests (If-None-Match, If-Modified-Since)

Features:
- Automatic ETag generation for GET requests
- Bandwidth optimization with 304 responses
- Configurable cache control policies
- Integration with backend cache system
"""

import hashlib
import json
from datetime import datetime
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class CacheHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware for adding HTTP cache headers to responses.
    
    Implements:
    - ETag: MD5 hash of response content
    - Last-Modified: Current timestamp for dynamic content
    - Cache-Control: max-age, must-revalidate, etc.
    - 304 Not Modified: When ETag matches If-None-Match
    
    Usage:
        app.add_middleware(CacheHeadersMiddleware, max_age=60)
    """
    
    def __init__(
        self,
        app: ASGIApp,
        max_age: int = 60,
        enable_etag: bool = True,
        enable_last_modified: bool = True,
    ):
        """
        Initialize cache headers middleware.
        
        Args:
            app: ASGI application
            max_age: Cache-Control max-age in seconds (default: 60)
            enable_etag: Enable ETag generation (default: True)
            enable_last_modified: Enable Last-Modified header (default: True)
        """
        super().__init__(app)
        self.max_age = max_age
        self.enable_etag = enable_etag
        self.enable_last_modified = enable_last_modified
        
        # Paths that should have cache headers
        self.cacheable_paths = [
            "/api/v1/backtests",
            "/api/v1/strategies",
            "/api/v1/marketdata",
        ]
        
        # Paths that should NOT be cached
        self.no_cache_paths = [
            "/api/v1/auth",
            "/api/v1/security",
            "/api/v1/admin",
            "/api/v1/cache/clear",
            "/ws/",
        ]
    
    def _is_cacheable_path(self, path: str) -> bool:
        """Check if path should have cache headers."""
        # Skip non-cacheable paths
        for no_cache in self.no_cache_paths:
            if path.startswith(no_cache):
                return False
        
        # Check if path is in cacheable list
        for cacheable in self.cacheable_paths:
            if path.startswith(cacheable):
                return True
        
        return False
    
    def _generate_etag(self, content: bytes) -> str:
        """
        Generate ETag from response content.
        
        Uses MD5 hash for fast ETag generation.
        Format: W/"<md5_hash>" (weak ETag)
        
        Args:
            content: Response body bytes
            
        Returns:
            ETag string in format: W/"abc123..."
        """
        md5_hash = hashlib.md5(content).hexdigest()
        return f'W/"{md5_hash}"'
    
    def _should_return_304(
        self,
        request: Request,
        etag: str,
        last_modified: Optional[datetime] = None
    ) -> bool:
        """
        Check if 304 Not Modified should be returned.
        
        Checks:
        1. If-None-Match header matches ETag
        2. If-Modified-Since header is newer than Last-Modified
        
        Args:
            request: FastAPI request
            etag: Generated ETag for response
            last_modified: Last-Modified timestamp (optional)
            
        Returns:
            True if 304 should be returned, False otherwise
        """
        # Check If-None-Match (ETag matching)
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match and if_none_match == etag:
            return True
        
        # Check If-Modified-Since (timestamp matching)
        if last_modified:
            if_modified_since = request.headers.get("If-Modified-Since")
            if if_modified_since:
                try:
                    # Parse If-Modified-Since header
                    ims_dt = datetime.strptime(
                        if_modified_since,
                        "%a, %d %b %Y %H:%M:%S GMT"
                    )
                    # Return 304 if content not modified
                    if last_modified <= ims_dt:
                        return True
                except (ValueError, TypeError):
                    pass
        
        return False
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Process request and add cache headers to response.
        
        Flow:
        1. Check if path is cacheable
        2. Check for conditional request headers
        3. Generate response
        4. Add cache headers (ETag, Last-Modified, Cache-Control)
        5. Return 304 if content not modified
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response with cache headers or 304 Not Modified
        """
        # Only process GET requests for caching
        if request.method != "GET":
            return await call_next(request)
        
        # Check if path should have cache headers
        if not self._is_cacheable_path(request.url.path):
            return await call_next(request)
        
        # Get response from handler
        response = await call_next(request)
        
        # Only add cache headers to successful responses
        if response.status_code != 200:
            return response
        
        # Read response body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        
        # Generate ETag
        etag = None
        if self.enable_etag:
            etag = self._generate_etag(body)
            response.headers["ETag"] = etag
        
        # Add Last-Modified header
        last_modified = None
        if self.enable_last_modified:
            from datetime import timezone
            last_modified = datetime.now(timezone.utc)
            last_modified_str = last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")
            response.headers["Last-Modified"] = last_modified_str
        
        # Check if 304 should be returned
        if self._should_return_304(request, etag, last_modified):
            # Return 304 Not Modified (no body)
            return Response(
                status_code=304,
                headers={
                    "ETag": etag,
                    "Last-Modified": response.headers.get("Last-Modified", ""),
                    "Cache-Control": response.headers.get("Cache-Control", ""),
                }
            )
        
        # Add Cache-Control header
        cache_control_parts = [
            f"max-age={self.max_age}",
            "must-revalidate",  # Always validate with origin
            "public",  # Can be cached by any cache
        ]
        response.headers["Cache-Control"] = ", ".join(cache_control_parts)
        
        # Add Vary header (important for correct caching)
        response.headers["Vary"] = "Accept-Encoding"
        
        # Recreate response with body
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )


def configure_cache_headers(max_age: int = 60) -> CacheHeadersMiddleware:
    """
    Factory function to create cache headers middleware with custom settings.
    
    Args:
        max_age: Cache-Control max-age in seconds
        
    Returns:
        Configured CacheHeadersMiddleware instance
        
    Example:
        app.add_middleware(
            CacheHeadersMiddleware,
            max_age=120,  # 2 minutes
            enable_etag=True,
            enable_last_modified=True
        )
    """
    return CacheHeadersMiddleware
