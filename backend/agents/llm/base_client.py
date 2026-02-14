"""
Base LLM Client

Abstract base class and shared infrastructure for all LLM clients:
- Session management (aiohttp persistent sessions)
- Rate limiting (token bucket)
- Retry with exponential backoff
- Circuit breaker integration
- Usage statistics tracking
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypeVar

import aiohttp
from loguru import logger

# Token-aware rate limiter (preferred over basic RateLimiter)
from backend.agents.llm.rate_limiter import TokenAwareRateLimiter, TokenBudget

# Circuit Breaker integration (optional - graceful fallback)
try:
    from backend.agents.circuit_breaker_manager import (
        CircuitBreakerError,
        get_circuit_manager,
    )

    _CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    logger.debug("Circuit breaker not available, running without protection")
    _CIRCUIT_BREAKER_AVAILABLE = False
    CircuitBreakerError = Exception  # type: ignore[assignment, misc]
    get_circuit_manager = None  # type: ignore[assignment]

T = TypeVar("T")


class LLMProvider(Enum):
    """Supported LLM providers."""

    DEEPSEEK = "deepseek"
    PERPLEXITY = "perplexity"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    QWEN = "qwen"
    CUSTOM = "custom"


@dataclass
class LLMMessage:
    """Chat message for LLM APIs."""

    role: str  # "system", "user", "assistant"
    content: str
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to API-compatible dict format."""
        data: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            data["name"] = self.name
        return data


@dataclass
class LLMResponse:
    """Standardized LLM API response across all providers."""

    content: str
    model: str
    provider: LLMProvider
    finish_reason: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    raw_response: dict[str, Any] | None = None
    reasoning_content: str | None = None  # CoT reasoning (Qwen3, DeepSeek-R1)

    @property
    def estimated_cost(self) -> float:
        """Estimate cost in USD based on provider pricing (per 1M tokens).

        .. deprecated:: 2026-02-12
            Use :meth:`backend.agents.cost_tracker.CostTracker.record`
            for authoritative cost estimation with the full COST_TABLE.
            This property uses a simplified cost table and may diverge.
        """
        costs = {
            LLMProvider.DEEPSEEK: {"input": 0.14, "output": 0.28},
            LLMProvider.PERPLEXITY: {"input": 0.20, "output": 0.60},
            LLMProvider.OPENAI: {"input": 2.50, "output": 10.0},
            LLMProvider.ANTHROPIC: {"input": 3.0, "output": 15.0},
            LLMProvider.QWEN: {"input": 0.40, "output": 1.20},
            LLMProvider.OLLAMA: {"input": 0.0, "output": 0.0},
        }
        rates = costs.get(self.provider, {"input": 0.0, "output": 0.0})
        input_cost = (self.prompt_tokens / 1_000_000) * rates["input"]
        output_cost = (self.completion_tokens / 1_000_000) * rates["output"]
        return input_cost + output_cost


@dataclass
class LLMConfig:
    """LLM connection configuration."""

    provider: LLMProvider
    api_key: str | None = None
    base_url: str | None = None
    model: str = "default"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_seconds: int = 60
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    rate_limit_rpm: int = 60


class RateLimiter:
    """
    DEPRECATED: Use TokenAwareRateLimiter from rate_limiter.py instead.

    Basic token bucket rate limiter for API calls.
    Kept for backward compatibility only.
    """

    def __init__(self, rate_limit_rpm: int):
        import warnings

        warnings.warn(
            "RateLimiter is deprecated. Use TokenAwareRateLimiter from backend.agents.llm.rate_limiter instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.rate_limit = rate_limit_rpm
        self.tokens = float(rate_limit_rpm)
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Acquire a token, wait if necessary."""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update

            # Refill tokens based on elapsed time
            self.tokens = min(
                self.rate_limit,
                self.tokens + (elapsed * self.rate_limit / 60),
            )
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True

            # Wait for refill
            wait_time = (1 - self.tokens) * 60 / self.rate_limit
            await asyncio.sleep(wait_time)
            self.tokens = 0
            return True


class LLMClient(ABC):
    """Abstract LLM client with optional circuit breaker integration."""

    _circuit_manager = None
    _breaker_name: str = "llm_default"

    def _init_circuit_breaker(self, breaker_name: str) -> None:
        """Initialize circuit breaker for this client."""
        self._breaker_name = breaker_name
        if _CIRCUIT_BREAKER_AVAILABLE and get_circuit_manager is not None:
            try:
                self._circuit_manager = get_circuit_manager()
                if breaker_name not in self._circuit_manager.get_all_breakers():
                    self._circuit_manager.register_breaker(
                        name=breaker_name,
                        fail_max=5,
                        timeout_duration=60,
                        expected_exception=Exception,
                    )
                logger.debug(f"Circuit breaker '{breaker_name}' initialized")
            except Exception as e:
                logger.warning(f"Could not initialize circuit breaker: {e}")
                self._circuit_manager = None

    async def _call_with_breaker(self, func: Callable[[], T]) -> T:
        """Execute function with circuit breaker protection."""
        if self._circuit_manager:
            try:
                return await self._circuit_manager.call_with_breaker(self._breaker_name, func)
            except CircuitBreakerError:
                logger.warning(f"Circuit breaker '{self._breaker_name}' is open")
                raise
        return await func()

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        """Send chat completion request."""

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> AsyncGenerator[str]:
        """Stream chat completion."""
        yield ""  # pragma: no cover

    @abstractmethod
    async def close(self) -> None:
        """Close connection and release resources."""


class OpenAICompatibleClient(LLMClient):
    """
    Base class for OpenAI-compatible API clients.

    Extracts shared logic: session management, retry loop, SSE streaming,
    stats tracking, and circuit breaker initialization.

    Subclasses only need to set class-level defaults and override
    _build_payload() or _parse_response() if needed.
    """

    DEFAULT_BASE_URL: str = ""
    DEFAULT_MODEL: str = ""
    PROVIDER: LLMProvider = LLMProvider.CUSTOM
    BREAKER_NAME: str = "llm_default"
    EMOJI: str = "🔹"

    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.base_url or self.DEFAULT_BASE_URL
        self.model = config.model if config.model != "default" else self.DEFAULT_MODEL
        self.session: aiohttp.ClientSession | None = None

        # Use TokenAwareRateLimiter instead of basic RateLimiter
        self.rate_limiter = TokenAwareRateLimiter(
            provider=self.PROVIDER.value,
            budget=TokenBudget(max_tokens_per_minute=config.rate_limit_rpm * 1000),
        )

        # Stats
        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost = 0.0

        # Circuit breaker
        self._init_circuit_breaker(self.BREAKER_NAME)

        logger.info(f"{self.EMOJI} {type(self).__name__} initialized: {self.model}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create persistent aiohttp session."""
        if self.session is None or self.session.closed:
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            }
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self.session

    def _build_payload(self, messages: list[LLMMessage], **kwargs: Any) -> dict[str, Any]:
        """Build request payload. Override in subclasses for custom fields."""
        return {
            "model": kwargs.get("model", self.model),
            "messages": [m.to_dict() for m in messages],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }

    def _parse_response(self, data: dict[str, Any], latency: float) -> LLMResponse:
        """Parse API response. Override in subclasses for custom parsing."""
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", self.model),
            provider=self.PROVIDER,
            finish_reason=data["choices"][0].get("finish_reason"),
            prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
            completion_tokens=data.get("usage", {}).get("completion_tokens", 0),
            total_tokens=data.get("usage", {}).get("total_tokens", 0),
            latency_ms=latency,
            raw_response=data,
        )

    async def chat(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        """Send chat completion with retry, rate limiting, and usage tracking."""
        estimated_tokens = kwargs.pop("estimated_tokens", 1000)
        await self.rate_limiter.acquire(estimated_tokens=estimated_tokens)

        session = await self._get_session()
        start_time = time.time()
        payload = self._build_payload(messages, **kwargs)

        for attempt in range(self.config.max_retries):
            try:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                ) as resp:
                    if resp.status == 429:
                        retry_after = float(resp.headers.get("Retry-After", 5))
                        logger.warning(f"{self.EMOJI} Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue

                    resp.raise_for_status()
                    data = await resp.json()

                    latency = (time.time() - start_time) * 1000
                    response = self._parse_response(data, latency)

                    # Update stats
                    self.total_requests += 1
                    self.total_tokens += response.total_tokens
                    self.total_cost += response.estimated_cost

                    # Record usage in rate limiter for accurate tracking
                    self.rate_limiter.record_usage(
                        tokens=response.total_tokens,
                        cost_usd=response.estimated_cost,
                    )

                    return response

            except aiohttp.ClientError as e:
                logger.warning(f"{self.EMOJI} Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay_seconds * (2**attempt))
                else:
                    raise

        raise RuntimeError(f"{type(self).__name__}: max retries exceeded")

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> AsyncGenerator[str]:
        """Stream chat completion via SSE."""
        estimated_tokens = kwargs.pop("estimated_tokens", 1000)
        await self.rate_limiter.acquire(estimated_tokens=estimated_tokens)

        session = await self._get_session()
        payload = self._build_payload(messages, **kwargs)
        payload["stream"] = True

        async with session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
        ) as resp:
            resp.raise_for_status()

            async for line in resp.content:
                decoded = line.decode().strip()
                if decoded.startswith("data: "):
                    data_str = decoded[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                    except json.JSONDecodeError:
                        continue

    async def close(self) -> None:
        """Close session."""
        if self.session and not self.session.closed:
            await self.session.close()
        logger.info(f"{self.EMOJI} {type(self).__name__} closed")


class LLMClientFactory:
    """Factory for creating LLM clients from config or environment."""

    # Lazy import map to avoid circular imports at module level
    _CLIENT_CLASSES: dict[LLMProvider, str] = {
        LLMProvider.DEEPSEEK: "DeepSeekClient",
        LLMProvider.PERPLEXITY: "PerplexityClient",
        LLMProvider.QWEN: "QwenClient",
        LLMProvider.OLLAMA: "OllamaClient",
    }

    _ENV_KEYS: dict[LLMProvider, str] = {
        LLMProvider.DEEPSEEK: "DEEPSEEK_API_KEY",
        LLMProvider.PERPLEXITY: "PERPLEXITY_API_KEY",
        LLMProvider.OPENAI: "OPENAI_API_KEY",
        LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
        LLMProvider.QWEN: "QWEN_API_KEY",
    }

    @staticmethod
    def create(config: LLMConfig) -> LLMClient:
        """Create client based on provider config."""
        # Import here to break circular dependency
        from backend.agents.llm.clients.deepseek import DeepSeekClient
        from backend.agents.llm.clients.ollama import OllamaClient
        from backend.agents.llm.clients.perplexity import PerplexityClient
        from backend.agents.llm.clients.qwen import QwenClient

        provider_map: dict[LLMProvider, type[LLMClient]] = {
            LLMProvider.DEEPSEEK: DeepSeekClient,
            LLMProvider.PERPLEXITY: PerplexityClient,
            LLMProvider.QWEN: QwenClient,
            LLMProvider.OLLAMA: OllamaClient,
        }

        client_class = provider_map.get(config.provider)
        if client_class is None:
            raise ValueError(f"Unsupported provider: {config.provider}")
        return client_class(config)

    @staticmethod
    def create_from_env(provider: LLMProvider) -> LLMClient:
        """Create client from environment variables."""
        api_key = os.environ.get(LLMClientFactory._ENV_KEYS.get(provider, ""), "")
        config = LLMConfig(provider=provider, api_key=api_key)
        return LLMClientFactory.create(config)


class LLMClientPool:
    """
    Pool of LLM clients for high availability.

    Features:
    - Round-robin load balancing
    - Automatic failover on errors
    - Health checking with timeout-based recovery
    - Usage tracking
    """

    def __init__(self) -> None:
        self.clients: list[LLMClient] = []
        self._current_index = 0
        self._lock = asyncio.Lock()
        self._failed_clients: dict[int, datetime] = {}
        self._fail_timeout_seconds = 60

        logger.info("LLMClientPool initialized")

    def add_client(self, client: LLMClient) -> None:
        """Add client to pool."""
        self.clients.append(client)
        logger.debug(f"Added client to pool: {type(client).__name__}")

    async def _get_healthy_client(self) -> LLMClient | None:
        """Get next healthy client via round-robin."""
        async with self._lock:
            now = datetime.now(UTC)

            for _ in range(len(self.clients)):
                idx = self._current_index
                self._current_index = (self._current_index + 1) % len(self.clients)

                if idx in self._failed_clients:
                    fail_time = self._failed_clients[idx]
                    if (now - fail_time).total_seconds() < self._fail_timeout_seconds:
                        continue
                    else:
                        del self._failed_clients[idx]

                return self.clients[idx]

            # All clients failed — try first anyway
            return self.clients[0] if self.clients else None

    def _mark_failed(self, client: LLMClient) -> None:
        """Mark client as temporarily failed."""
        try:
            idx = self.clients.index(client)
            self._failed_clients[idx] = datetime.now(UTC)
        except ValueError:
            pass

    async def chat(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        """Send chat to next available client with automatic failover."""
        if not self.clients:
            raise RuntimeError("No clients in pool")

        last_error: Exception | None = None

        for _ in range(len(self.clients)):
            client = await self._get_healthy_client()
            if not client:
                break

            try:
                return await client.chat(messages, **kwargs)
            except Exception as e:
                logger.warning(f"Client failed: {e}")
                self._mark_failed(client)
                last_error = e

        raise RuntimeError(f"All clients failed: {last_error}")

    async def close_all(self) -> None:
        """Close all clients in pool."""
        for client in self.clients:
            await client.close()
        self.clients.clear()


__all__ = [
    "LLMClient",
    "LLMClientFactory",
    "LLMClientPool",
    "LLMConfig",
    "LLMMessage",
    "LLMProvider",
    "LLMResponse",
    "OpenAICompatibleClient",
    "RateLimiter",
]
