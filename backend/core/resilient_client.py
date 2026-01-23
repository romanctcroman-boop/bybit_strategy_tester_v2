"""
Resilient HTTP Client

Production-ready HTTP client with:
- Circuit breaker protection
- Retry logic with exponential backoff
- Rate limiting awareness
- Timeout handling
- Connection pooling

Usage:
    from backend.core.resilient_client import ResilientClient

    client = ResilientClient("bybit_api")
    response = await client.get("https://api.bybit.com/v5/market/kline", params={...})
"""

from typing import Any

import httpx

from backend.core.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerError,
    RateLimitError,
    RetryableError,
    TransientError,
    get_circuit_registry,
    with_retry,
)
from backend.core.circuit_breaker import (
    TimeoutError as CBTimeoutError,
)


class ResilientClient:
    """
    HTTP client with built-in resilience patterns.

    Features:
    - Circuit breaker for failing fast
    - Retry with exponential backoff
    - Automatic timeout handling
    - Rate limit detection
    """

    def __init__(
        self,
        circuit_name: str,
        base_url: str = "",
        timeout: float = 30.0,
        max_retries: int = 3,
        circuit_config: CircuitBreakerConfig | None = None,
        headers: dict[str, str] | None = None,
    ):
        """
        Initialize resilient client.

        Args:
            circuit_name: Name for the circuit breaker
            base_url: Base URL for all requests
            timeout: Default timeout in seconds
            max_retries: Maximum retry attempts
            circuit_config: Optional circuit breaker config
            headers: Default headers for all requests
        """
        self.circuit_name = circuit_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        # Get or create circuit breaker
        self._circuit = get_circuit_registry().get_or_create(
            circuit_name,
            circuit_config
            or CircuitBreakerConfig(
                failure_threshold=5,
                timeout=30.0,
                success_threshold=3,
            ),
        )

        # Create HTTP client with connection pooling
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            headers=headers or {},
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            http2=True,  # Enable HTTP/2 for better performance
        )

    async def __aenter__(self) -> "ResilientClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def _classify_error(self, error: Exception) -> Exception:
        """Classify error for proper handling."""
        if isinstance(error, httpx.TimeoutException):
            return CBTimeoutError(str(error))
        elif isinstance(error, httpx.ConnectError):
            return TransientError(f"Connection failed: {error}")
        elif isinstance(error, httpx.HTTPStatusError):
            status = error.response.status_code
            if status == 429:
                # Try to get retry-after header
                retry_after = float(error.response.headers.get("Retry-After", 60))
                return RateLimitError(retry_after)
            elif 500 <= status < 600:
                return TransientError(f"Server error: {status}")
        return error

    @with_retry(
        max_attempts=3, retry_on=(RetryableError, CBTimeoutError, TransientError)
    )
    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make HTTP request with retry logic."""
        try:
            response = await self._client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            raise self._classify_error(e) from e

    async def request(
        self,
        method: str,
        url: str,
        fallback: Any = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make HTTP request with circuit breaker protection.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL path (appended to base_url)
            fallback: Optional fallback value if circuit is open
            **kwargs: Additional arguments for httpx

        Returns:
            httpx.Response

        Raises:
            CircuitBreakerError: If circuit is open and no fallback
        """

        async def fallback_func() -> Any:
            if fallback is not None:
                return fallback
            raise CircuitBreakerError(self.circuit_name)

        return await self._circuit.execute(
            self._make_request,
            method,
            url,
            fallback=fallback_func if fallback is not None else None,
            **kwargs,
        )

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make GET request."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make POST request."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make PUT request."""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make DELETE request."""
        return await self.request("DELETE", url, **kwargs)

    async def get_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
        """Make GET request and return JSON."""
        response = await self.get(url, **kwargs)
        return response.json()

    async def post_json(
        self, url: str, json_data: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        """Make POST request with JSON body and return JSON."""
        response = await self.post(url, json=json_data, **kwargs)
        return response.json()

    def get_circuit_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        return self._circuit.get_status()


# =============================================================================
# PRE-CONFIGURED CLIENTS
# =============================================================================

_clients: dict[str, ResilientClient] = {}


async def get_bybit_client() -> ResilientClient:
    """Get pre-configured Bybit API client."""
    if "bybit" not in _clients:
        _clients["bybit"] = ResilientClient(
            circuit_name="bybit_api",
            base_url="https://api.bybit.com",
            timeout=10.0,
            max_retries=3,
            circuit_config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout=30.0,
                success_threshold=3,
            ),
        )
    return _clients["bybit"]


async def get_deepseek_client() -> ResilientClient:
    """Get pre-configured DeepSeek API client."""
    import os

    if "deepseek" not in _clients:
        _clients["deepseek"] = ResilientClient(
            circuit_name="deepseek_api",
            base_url="https://api.deepseek.com",
            timeout=120.0,  # Longer timeout for LLM
            max_retries=3,
            circuit_config=CircuitBreakerConfig(
                failure_threshold=3,  # Trip faster for expensive API
                timeout=60.0,
                success_threshold=2,
            ),
            headers={
                "Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY', '')}",
                "Content-Type": "application/json",
            },
        )
    return _clients["deepseek"]


async def get_perplexity_client() -> ResilientClient:
    """Get pre-configured Perplexity API client."""
    import os

    if "perplexity" not in _clients:
        _clients["perplexity"] = ResilientClient(
            circuit_name="perplexity_api",
            base_url="https://api.perplexity.ai",
            timeout=60.0,
            max_retries=3,
            circuit_config=CircuitBreakerConfig(
                failure_threshold=3,
                timeout=60.0,
                success_threshold=2,
            ),
            headers={
                "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY', '')}",
                "Content-Type": "application/json",
            },
        )
    return _clients["perplexity"]


async def close_all_clients() -> None:
    """Close all cached clients."""
    for client in _clients.values():
        await client.close()
    _clients.clear()


__all__ = [
    "ResilientClient",
    "get_bybit_client",
    "get_deepseek_client",
    "get_perplexity_client",
    "close_all_clients",
]
