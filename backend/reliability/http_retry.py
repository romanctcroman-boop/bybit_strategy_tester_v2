"""Minimal http retry shim to satisfy imports in tests.
This is a lightweight placeholder used in the developer/test environment.
Production code should use a robust retry implementation (tenacity/httpx-retry/etc.).
"""

from collections.abc import Callable
from typing import Any


async def httpx_retry(name: str, call: Callable[..., Any], *args, **kwargs) -> Any:
    """Call async function `call` and return its result without retries (placeholder).

    Args:
        name: logical name for the remote call (unused in placeholder)
        call: an async callable that performs the HTTP request
    """
    return await call()


def requests_retry(name: str, call: Callable[..., Any], *args, **kwargs) -> Any:
    """Call sync function `call` and return its result without retries (placeholder)."""
    return call()
