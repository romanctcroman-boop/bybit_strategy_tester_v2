"""
Tests for LLM base_client.py and provider clients.

Tests cover:
- LLMProvider enum
- LLMMessage serialization
- LLMResponse cost estimation
- LLMConfig defaults
- RateLimiter token bucket
- OpenAICompatibleClient shared behavior
- LLMClientFactory creation
- LLMClientPool failover
- Claude/Perplexity/Ollama client initialization
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.llm.base_client import (
    LLMClient,
    LLMClientFactory,
    LLMClientPool,
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    RateLimiter,
)
from backend.agents.llm.clients.claude import ClaudeClient
from backend.agents.llm.clients.ollama import OllamaClient
from backend.agents.llm.clients.perplexity import PerplexityClient


class TestLLMProvider:
    """Test LLMProvider enum."""

    def test_active_providers(self):
        """Active providers are defined."""
        assert LLMProvider.PERPLEXITY.value == "perplexity"
        assert LLMProvider.OLLAMA.value == "ollama"
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.ANTHROPIC.value == "anthropic"
        assert LLMProvider.CUSTOM.value == "custom"


class TestLLMMessage:
    """Test LLMMessage dataclass."""

    def test_to_dict_basic(self):
        """Basic message serialization."""
        msg = LLMMessage(role="user", content="Hello")
        d = msg.to_dict()
        assert d == {"role": "user", "content": "Hello"}

    def test_to_dict_with_name(self):
        """Message with name field."""
        msg = LLMMessage(role="assistant", content="Reply", name="bot")
        d = msg.to_dict()
        assert d["name"] == "bot"

    def test_to_dict_without_name(self):
        """Name is omitted when None."""
        msg = LLMMessage(role="system", content="System prompt")
        d = msg.to_dict()
        assert "name" not in d


class TestLLMResponse:
    """Test LLMResponse and cost estimation."""

    def test_estimated_cost_anthropic(self):
        """Anthropic cost estimation (Haiku model)."""
        resp = LLMResponse(
            content="test",
            model="claude-haiku-4-5-20251001",
            provider=LLMProvider.ANTHROPIC,
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
        )
        # Haiku: $0.80 input + $4.00 output per 1M tokens
        assert resp.estimated_cost > 0

    def test_estimated_cost_zero_tokens(self):
        """Zero tokens = zero cost."""
        resp = LLMResponse(
            content="test",
            model="claude-haiku-4-5-20251001",
            provider=LLMProvider.ANTHROPIC,
        )
        assert resp.estimated_cost == 0.0

    def test_estimated_cost_ollama_free(self):
        """Ollama is always free."""
        resp = LLMResponse(
            content="test",
            model="llama2",
            provider=LLMProvider.OLLAMA,
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
        )
        assert resp.estimated_cost == 0.0

    def test_reasoning_content_field(self):
        """Reasoning content is optional."""
        resp = LLMResponse(
            content="result",
            model="claude-sonnet-4-6",
            provider=LLMProvider.ANTHROPIC,
            reasoning_content="Step 1: ...",
        )
        assert resp.reasoning_content == "Step 1: ..."


class TestLLMConfig:
    """Test LLMConfig defaults."""

    def test_default_values(self):
        """Config has sensible defaults."""
        config = LLMConfig(provider=LLMProvider.ANTHROPIC)
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.timeout_seconds == 60
        assert config.max_retries == 3
        assert config.rate_limit_rpm == 60


class TestRateLimiter:
    """Test RateLimiter (deprecated) backward compatibility."""

    async def test_acquire_succeeds(self):
        """First acquire succeeds immediately."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            limiter = RateLimiter(rate_limit_rpm=60)
        result = await limiter.acquire()
        assert result is True

    async def test_multiple_acquires(self):
        """Multiple acquires work within limit."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            limiter = RateLimiter(rate_limit_rpm=100)
        for _ in range(10):
            result = await limiter.acquire()
            assert result is True

    async def test_tokens_decrease(self):
        """Tokens decrease after acquire."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            limiter = RateLimiter(rate_limit_rpm=60)
        initial_tokens = limiter.tokens
        await limiter.acquire()
        assert limiter.tokens < initial_tokens

    def test_deprecation_warning(self):
        """RateLimiter emits deprecation warning."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            RateLimiter(rate_limit_rpm=60)
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "TokenAwareRateLimiter" in str(w[0].message)


class TestClaudeClient:
    """Test ClaudeClient configuration."""

    def test_default_config(self):
        """Default Claude settings."""
        config = LLMConfig(provider=LLMProvider.ANTHROPIC, api_key="sk-ant-test-key")
        client = ClaudeClient(config)
        assert client.PROVIDER == LLMProvider.ANTHROPIC

    def test_custom_model(self):
        """Custom model override."""
        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            api_key="sk-ant-test-key",
            model="claude-sonnet-4-6",
        )
        client = ClaudeClient(config)
        assert client.model == "claude-sonnet-4-6"

    async def test_close_no_session(self):
        """Close without session doesn't error."""
        config = LLMConfig(provider=LLMProvider.ANTHROPIC, api_key="sk-ant-test-key")
        client = ClaudeClient(config)
        await client.close()  # Should not raise


class TestPerplexityClient:
    """Test PerplexityClient configuration."""

    def test_default_config(self):
        """Default Perplexity settings."""
        config = LLMConfig(provider=LLMProvider.PERPLEXITY, api_key="test-key")
        client = PerplexityClient(config)
        assert client.base_url == "https://api.perplexity.ai"
        assert client.model == "sonar-pro"
        assert client.PROVIDER == LLMProvider.PERPLEXITY


class TestOllamaClient:
    """Test OllamaClient configuration."""

    def test_default_config(self):
        """Default Ollama settings."""
        config = LLMConfig(provider=LLMProvider.OLLAMA)
        client = OllamaClient(config)
        assert client.base_url == "http://localhost:11434"
        assert client.model == "llama2"


class TestLLMClientFactory:
    """Test LLMClientFactory creation."""

    def test_create_claude(self):
        """Factory creates ClaudeClient."""
        config = LLMConfig(provider=LLMProvider.ANTHROPIC, api_key="sk-ant-test")
        client = LLMClientFactory.create(config)
        assert isinstance(client, ClaudeClient)

    def test_create_perplexity(self):
        """Factory creates PerplexityClient."""
        config = LLMConfig(provider=LLMProvider.PERPLEXITY, api_key="test")
        client = LLMClientFactory.create(config)
        assert isinstance(client, PerplexityClient)

    def test_create_ollama(self):
        """Factory creates OllamaClient."""
        config = LLMConfig(provider=LLMProvider.OLLAMA)
        client = LLMClientFactory.create(config)
        assert isinstance(client, OllamaClient)

    def test_create_unsupported_raises(self):
        """Unsupported provider raises ValueError."""
        config = LLMConfig(provider=LLMProvider.OPENAI, api_key="test")
        with pytest.raises(ValueError, match="Unsupported provider"):
            LLMClientFactory.create(config)


class TestLLMClientPool:
    """Test LLMClientPool load balancing and failover."""

    def test_empty_pool_raises(self):
        """Empty pool raises on chat."""
        pool = LLMClientPool()
        with pytest.raises(RuntimeError, match="No clients"):
            asyncio.run(pool.chat([LLMMessage(role="user", content="test")]))

    def test_add_client(self):
        """add_client() adds to pool."""
        pool = LLMClientPool()
        mock_client = MagicMock(spec=LLMClient)
        pool.add_client(mock_client)
        assert len(pool.clients) == 1

    async def test_close_all(self):
        """close_all() closes and clears all clients."""
        pool = LLMClientPool()
        c1 = AsyncMock(spec=LLMClient)
        c2 = AsyncMock(spec=LLMClient)
        pool.add_client(c1)
        pool.add_client(c2)

        await pool.close_all()

        c1.close.assert_called_once()
        c2.close.assert_called_once()
        assert len(pool.clients) == 0

    async def test_chat_uses_first_client(self):
        """Pool uses first healthy client."""
        pool = LLMClientPool()
        mock_client = AsyncMock(spec=LLMClient)
        expected_response = LLMResponse(
            content="Hello",
            model="test",
            provider=LLMProvider.ANTHROPIC,
        )
        mock_client.chat.return_value = expected_response
        pool.add_client(mock_client)

        messages = [LLMMessage(role="user", content="test")]
        result = await pool.chat(messages)
        assert result.content == "Hello"

    async def test_failover_to_second_client(self):
        """Pool fails over to second client when first fails."""
        pool = LLMClientPool()
        failing = AsyncMock(spec=LLMClient)
        failing.chat.side_effect = RuntimeError("API down")
        working = AsyncMock(spec=LLMClient)
        expected = LLMResponse(
            content="Backup",
            model="test",
            provider=LLMProvider.PERPLEXITY,
        )
        working.chat.return_value = expected

        pool.add_client(failing)
        pool.add_client(working)

        messages = [LLMMessage(role="user", content="test")]
        result = await pool.chat(messages)
        assert result.content == "Backup"


class TestOpenAICompatibleClient:
    """Test OpenAICompatibleClient shared behavior via PerplexityClient."""

    def test_build_payload(self):
        """Default payload building."""
        config = LLMConfig(provider=LLMProvider.PERPLEXITY, api_key="test")
        client = PerplexityClient(config)
        messages = [LLMMessage(role="user", content="hello")]

        payload = client._build_payload(messages)
        assert payload["model"] == "sonar-pro"
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 4096
        assert len(payload["messages"]) == 1

    def test_parse_response(self):
        """Default response parsing."""
        config = LLMConfig(provider=LLMProvider.PERPLEXITY, api_key="test")
        client = PerplexityClient(config)

        mock_data = {
            "choices": [
                {
                    "message": {"content": "Hello world"},
                    "finish_reason": "stop",
                }
            ],
            "model": "sonar-pro",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        resp = client._parse_response(mock_data, latency=100.0)
        assert resp.content == "Hello world"
        assert resp.model == "sonar-pro"
        assert resp.provider == LLMProvider.PERPLEXITY
        assert resp.total_tokens == 15
        assert resp.latency_ms == 100.0

    def test_stats_initialized_zero(self):
        """Stats start at zero."""
        config = LLMConfig(provider=LLMProvider.PERPLEXITY, api_key="test")
        client = PerplexityClient(config)
        assert client.total_requests == 0
        assert client.total_tokens == 0
        assert client.total_cost == 0.0


class TestBackwardCompatibility:
    """Test that connections.py re-exports work."""

    def test_import_from_connections(self):
        """All symbols importable from connections.py."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from backend.agents.llm import connections

        symbols = [
            "ClaudeClient",
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
        for sym in symbols:
            assert hasattr(connections, sym), f"connections.py missing {sym}"
            assert getattr(connections, sym) is not None
