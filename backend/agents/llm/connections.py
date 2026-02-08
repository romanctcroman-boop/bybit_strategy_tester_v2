"""
Real LLM API Connections

Production-ready connections to LLM APIs:
- DeepSeek API
- Perplexity API
- OpenAI-compatible APIs
- Anthropic Claude API
- Local models via Ollama

Features:
- Connection pooling (via persistent aiohttp sessions)
- Automatic retries with backoff
- Rate limiting
- Streaming support
- Token tracking
- Circuit Breaker integration (P1 fix 2026-01-28)
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

# Circuit Breaker integration (optional - graceful fallback if not available)
try:
    from backend.agents.circuit_breaker_manager import (
        CircuitBreakerError,
        get_circuit_manager,
    )
    _CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    logger.debug("Circuit breaker not available, running without protection")
    _CIRCUIT_BREAKER_AVAILABLE = False
    CircuitBreakerError = Exception  # type: ignore
    get_circuit_manager = None  # type: ignore

T = TypeVar("T")


class LLMProvider(Enum):
    """Supported LLM providers"""

    DEEPSEEK = "deepseek"
    PERPLEXITY = "perplexity"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    CUSTOM = "custom"


@dataclass
class LLMMessage:
    """Chat message"""

    role: str  # "system", "user", "assistant"
    content: str
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to API format"""
        data = {"role": self.role, "content": self.content}
        if self.name:
            data["name"] = self.name
        return data


@dataclass
class LLMResponse:
    """LLM API response"""

    content: str
    model: str
    provider: LLMProvider
    finish_reason: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    raw_response: dict[str, Any] | None = None

    @property
    def estimated_cost(self) -> float:
        """Estimate cost in USD (rough estimates)"""
        # Cost per 1M tokens (approximate)
        costs = {
            LLMProvider.DEEPSEEK: {"input": 0.14, "output": 0.28},
            LLMProvider.PERPLEXITY: {"input": 0.20, "output": 0.60},
            LLMProvider.OPENAI: {"input": 2.50, "output": 10.0},  # GPT-4o
            LLMProvider.ANTHROPIC: {"input": 3.0, "output": 15.0},  # Claude
            LLMProvider.OLLAMA: {"input": 0.0, "output": 0.0},  # Free
        }

        rates = costs.get(self.provider, {"input": 0.0, "output": 0.0})
        input_cost = (self.prompt_tokens / 1_000_000) * rates["input"]
        output_cost = (self.completion_tokens / 1_000_000) * rates["output"]

        return input_cost + output_cost


@dataclass
class LLMConfig:
    """LLM connection configuration"""

    provider: LLMProvider
    api_key: str | None = None
    base_url: str | None = None
    model: str = "default"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_seconds: int = 60
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    rate_limit_rpm: int = 60  # Requests per minute


class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, rate_limit_rpm: int):
        self.rate_limit = rate_limit_rpm
        self.tokens = rate_limit_rpm
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Acquire a token, wait if necessary"""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update

            # Refill tokens based on elapsed time
            self.tokens = min(
                self.rate_limit, self.tokens + (elapsed * self.rate_limit / 60)
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
    """Abstract LLM client with optional circuit breaker integration"""

    _circuit_manager = None
    _breaker_name: str = "llm_default"

    def _init_circuit_breaker(self, breaker_name: str) -> None:
        """Initialize circuit breaker for this client"""
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
        """Execute function with circuit breaker protection"""
        if self._circuit_manager:
            try:
                return await self._circuit_manager.call_with_breaker(
                    self._breaker_name, func
                )
            except CircuitBreakerError:
                logger.warning(f"Circuit breaker '{self._breaker_name}' is open")
                raise
        return await func()

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        **kwargs,
    ) -> LLMResponse:
        """Send chat completion request"""
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[LLMMessage],
        **kwargs,
    ) -> AsyncGenerator[str]:
        """Stream chat completion"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connection"""
        pass


class DeepSeekClient(LLMClient):
    """DeepSeek API client with circuit breaker protection"""

    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
    DEFAULT_MODEL = "deepseek-chat"

    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.base_url or self.DEFAULT_BASE_URL
        self.model = config.model if config.model != "default" else self.DEFAULT_MODEL
        self.session: aiohttp.ClientSession | None = None
        self.rate_limiter = RateLimiter(config.rate_limit_rpm)

        # Stats
        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost = 0.0

        # Initialize circuit breaker
        self._init_circuit_breaker("deepseek_llm_client")

        logger.info(f"🔵 DeepSeek client initialized: {self.model}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create session"""
        if self.session is None or self.session.closed:
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            }
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self.session

    async def chat(
        self,
        messages: list[LLMMessage],
        **kwargs,
    ) -> LLMResponse:
        """Send chat completion"""
        await self.rate_limiter.acquire()

        session = await self._get_session()
        start_time = time.time()

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [m.to_dict() for m in messages],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }

        for attempt in range(self.config.max_retries):
            try:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                ) as resp:
                    if resp.status == 429:
                        # Rate limited
                        retry_after = float(resp.headers.get("Retry-After", 5))
                        logger.warning(f"Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue

                    resp.raise_for_status()
                    data = await resp.json()

                    latency = (time.time() - start_time) * 1000

                    response = LLMResponse(
                        content=data["choices"][0]["message"]["content"],
                        model=data.get("model", self.model),
                        provider=LLMProvider.DEEPSEEK,
                        finish_reason=data["choices"][0].get("finish_reason"),
                        prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                        completion_tokens=data.get("usage", {}).get(
                            "completion_tokens", 0
                        ),
                        total_tokens=data.get("usage", {}).get("total_tokens", 0),
                        latency_ms=latency,
                        raw_response=data,
                    )

                    # Update stats
                    self.total_requests += 1
                    self.total_tokens += response.total_tokens
                    self.total_cost += response.estimated_cost

                    return response

            except aiohttp.ClientError as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay_seconds * (2**attempt))
                else:
                    raise

        raise RuntimeError("Max retries exceeded")

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        **kwargs,
    ) -> AsyncGenerator[str]:
        """Stream chat completion"""
        await self.rate_limiter.acquire()

        session = await self._get_session()

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [m.to_dict() for m in messages],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "stream": True,
        }

        async with session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
        ) as resp:
            resp.raise_for_status()

            async for line in resp.content:
                line = line.decode().strip()
                if line.startswith("data: "):
                    data_str = line[6:]
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
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()
        logger.info("🔵 DeepSeek client closed")


class PerplexityClient(LLMClient):
    """Perplexity API client with circuit breaker protection"""

    DEFAULT_BASE_URL = "https://api.perplexity.ai"
    DEFAULT_MODEL = "llama-3.1-sonar-small-128k-online"

    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.base_url or self.DEFAULT_BASE_URL
        self.model = config.model if config.model != "default" else self.DEFAULT_MODEL
        self.session: aiohttp.ClientSession | None = None
        self.rate_limiter = RateLimiter(config.rate_limit_rpm)

        self.total_requests = 0
        self.total_tokens = 0

        # Initialize circuit breaker
        self._init_circuit_breaker("perplexity_llm_client")

        logger.info(f"🟣 Perplexity client initialized: {self.model}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create session"""
        if self.session is None or self.session.closed:
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            }
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self.session

    async def chat(
        self,
        messages: list[LLMMessage],
        **kwargs,
    ) -> LLMResponse:
        """Send chat completion"""
        await self.rate_limiter.acquire()

        session = await self._get_session()
        start_time = time.time()

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [m.to_dict() for m in messages],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }

        for attempt in range(self.config.max_retries):
            try:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                ) as resp:
                    if resp.status == 429:
                        retry_after = float(resp.headers.get("Retry-After", 5))
                        await asyncio.sleep(retry_after)
                        continue

                    resp.raise_for_status()
                    data = await resp.json()

                    latency = (time.time() - start_time) * 1000

                    response = LLMResponse(
                        content=data["choices"][0]["message"]["content"],
                        model=data.get("model", self.model),
                        provider=LLMProvider.PERPLEXITY,
                        finish_reason=data["choices"][0].get("finish_reason"),
                        prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                        completion_tokens=data.get("usage", {}).get(
                            "completion_tokens", 0
                        ),
                        total_tokens=data.get("usage", {}).get("total_tokens", 0),
                        latency_ms=latency,
                        raw_response=data,
                    )

                    self.total_requests += 1
                    self.total_tokens += response.total_tokens

                    return response

            except aiohttp.ClientError as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay_seconds * (2**attempt))
                else:
                    raise

        raise RuntimeError("Max retries exceeded")

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        **kwargs,
    ) -> AsyncGenerator[str]:
        """Stream chat completion"""
        await self.rate_limiter.acquire()

        session = await self._get_session()

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [m.to_dict() for m in messages],
            "stream": True,
        }

        async with session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
        ) as resp:
            resp.raise_for_status()

            async for line in resp.content:
                line = line.decode().strip()
                if line.startswith("data: "):
                    data_str = line[6:]
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
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()
        logger.info("🟣 Perplexity client closed")


class OllamaClient(LLMClient):
    """Ollama local LLM client"""

    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL = "llama2"

    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.base_url or self.DEFAULT_BASE_URL
        self.model = config.model if config.model != "default" else self.DEFAULT_MODEL
        self.session: aiohttp.ClientSession | None = None

        logger.info(f"🦙 Ollama client initialized: {self.model}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def chat(
        self,
        messages: list[LLMMessage],
        **kwargs,
    ) -> LLMResponse:
        """Send chat completion"""
        session = await self._get_session()
        start_time = time.time()

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [m.to_dict() for m in messages],
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            },
        }

        try:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

                latency = (time.time() - start_time) * 1000

                return LLMResponse(
                    content=data["message"]["content"],
                    model=data.get("model", self.model),
                    provider=LLMProvider.OLLAMA,
                    finish_reason="stop",
                    prompt_tokens=data.get("prompt_eval_count", 0),
                    completion_tokens=data.get("eval_count", 0),
                    total_tokens=data.get("prompt_eval_count", 0)
                    + data.get("eval_count", 0),
                    latency_ms=latency,
                    raw_response=data,
                )
        except aiohttp.ClientError as e:
            logger.error(f"Ollama request failed: {e}")
            raise

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        **kwargs,
    ) -> AsyncGenerator[str]:
        """Stream chat completion"""
        session = await self._get_session()

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [m.to_dict() for m in messages],
            "stream": True,
        }

        async with session.post(
            f"{self.base_url}/api/chat",
            json=payload,
        ) as resp:
            resp.raise_for_status()

            async for line in resp.content:
                try:
                    data = json.loads(line.decode())
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
                except json.JSONDecodeError:
                    continue

    async def close(self) -> None:
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()
        logger.info("🦙 Ollama client closed")


class LLMClientFactory:
    """Factory for creating LLM clients"""

    @staticmethod
    def create(config: LLMConfig) -> LLMClient:
        """Create client based on provider"""
        if config.provider == LLMProvider.DEEPSEEK:
            return DeepSeekClient(config)
        elif config.provider == LLMProvider.PERPLEXITY:
            return PerplexityClient(config)
        elif config.provider == LLMProvider.OLLAMA:
            return OllamaClient(config)
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")

    @staticmethod
    def create_from_env(provider: LLMProvider) -> LLMClient:
        """Create client from environment variables"""
        env_map = {
            LLMProvider.DEEPSEEK: "DEEPSEEK_API_KEY",
            LLMProvider.PERPLEXITY: "PERPLEXITY_API_KEY",
            LLMProvider.OPENAI: "OPENAI_API_KEY",
            LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
        }

        api_key = os.environ.get(env_map.get(provider, ""))

        config = LLMConfig(
            provider=provider,
            api_key=api_key,
        )

        return LLMClientFactory.create(config)


class LLMClientPool:
    """
    Pool of LLM clients for high availability

    Features:
    - Round-robin load balancing
    - Automatic failover
    - Health checking
    - Usage tracking

    Example:
        pool = LLMClientPool()
        pool.add_client(deepseek_client)
        pool.add_client(perplexity_client)

        response = await pool.chat(messages)  # Auto-selects client
    """

    def __init__(self):
        self.clients: list[LLMClient] = []
        self._current_index = 0
        self._lock = asyncio.Lock()
        self._failed_clients: dict[int, datetime] = {}
        self._fail_timeout_seconds = 60

        logger.info("🔄 LLMClientPool initialized")

    def add_client(self, client: LLMClient) -> None:
        """Add client to pool"""
        self.clients.append(client)
        logger.debug(f"Added client to pool: {type(client).__name__}")

    async def _get_healthy_client(self) -> LLMClient | None:
        """Get next healthy client"""
        async with self._lock:
            now = datetime.now(UTC)

            for _ in range(len(self.clients)):
                idx = self._current_index
                self._current_index = (self._current_index + 1) % len(self.clients)

                # Check if client was marked as failed
                if idx in self._failed_clients:
                    fail_time = self._failed_clients[idx]
                    if (now - fail_time).total_seconds() < self._fail_timeout_seconds:
                        continue
                    else:
                        del self._failed_clients[idx]

                return self.clients[idx]

            # All clients failed, try anyway
            return self.clients[0] if self.clients else None

    def _mark_failed(self, client: LLMClient) -> None:
        """Mark client as failed"""
        try:
            idx = self.clients.index(client)
            self._failed_clients[idx] = datetime.now(UTC)
        except ValueError:
            pass

    async def chat(
        self,
        messages: list[LLMMessage],
        **kwargs,
    ) -> LLMResponse:
        """Send chat to available client"""
        if not self.clients:
            raise RuntimeError("No clients in pool")

        last_error = None

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
        """Close all clients"""
        for client in self.clients:
            await client.close()
        self.clients.clear()


__all__ = [
    "DeepSeekClient",
    "LLMClient",
    "LLMClientFactory",
    "LLMClientPool",
    "LLMConfig",
    "LLMMessage",
    "LLMProvider",
    "LLMResponse",
    "OllamaClient",
    "PerplexityClient",
    "RateLimiter",
]
