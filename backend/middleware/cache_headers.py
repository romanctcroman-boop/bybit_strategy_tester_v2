"""
Cache Headers Middleware
Adds Cache-Control, ETag, and Last-Modified headers where appropriate.
"""

import hashlib
import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class CacheHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds cache headers to GET responses.
    """

    def __init__(
        self,
        app,
        max_age: int = 60,
        enable_etag: bool = False,
        enable_last_modified: bool = False,
        **kwargs,
    ):
        super().__init__(app)
        self.max_age = max_age
        self.enable_etag = enable_etag
        self.enable_last_modified = enable_last_modified
        logger.info(
            f"CacheHeadersMiddleware initialized (max_age={max_age}, etag={enable_etag}, last_modified={enable_last_modified})"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only apply to safe GET requests
        response = await call_next(request)

        try:
            if request.method.upper() != "GET":
                return response

            # Add Cache-Control header
            response.headers.setdefault(
                "Cache-Control", f"public, max-age={self.max_age}"
            )

            # Optionally add ETag (simple hash of body)
            if self.enable_etag and getattr(response, "body", None):
                try:
                    # response.body may be bytes or str; ensure bytes
                    body = getattr(response, "body", None)
                    body_bytes = (
                        body
                        if isinstance(body, (bytes, bytearray))
                        else str(body).encode()
                    )
                    etag = hashlib.sha1(body_bytes).hexdigest()
                    response.headers.setdefault("ETag", etag)
                except Exception:
                    logger.debug("Failed to compute ETag")

            # Optionally add Last-Modified header
            if self.enable_last_modified:
                response.headers.setdefault(
                    "Last-Modified",
                    time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime()),
                )

        except Exception as exc:
            logger.debug("CacheHeadersMiddleware error: %s", exc)

        return response


__all__ = ["CacheHeadersMiddleware"]
