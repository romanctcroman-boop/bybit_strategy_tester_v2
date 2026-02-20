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
- DeepSeek/Perplexity/Qwen/Ollama client initialization
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
from backend.agents.llm.clients.deepseek import DeepSeekClient
from backend.agents.llm.clients.ollama import OllamaClient
from backend.agents.llm.clients.perplexity import PerplexityClient
from backend.agents.llm.clients.qwen import QwenClient


class TestLLMProvider:
    """Test LLMProvider enum."""

    def test_all_providers(self):
        """All 7 providers are defined."""
        assert LLMProvider.DEEPSEEK.value == "deepseek"
        assert LLMProvider.PERPLEXITY.value == "perplexity"
        assert LLMProvider.QWEN.value == "qwen"
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

    def test_estimated_cost_deepseek(self):
        """DeepSeek cost estimation."""
        resp = LLMResponse(
            content="test",
            model="deepseek-chat",
            provider=LLMProvider.DEEPSEEK,
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
        )
        # 0.14 + 0.28 = 0.42 per 1M tokens
        assert abs(resp.estimated_cost - 0.42) < 0.01

    def test_estimated_cost_zero_tokens(self):
        """Zero tokens = zero cost."""
        resp = LLMResponse(
            content="test",
            model="test",
            provider=LLMProvider.DEEPSEEK,
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
            model="qwen-plus",
            provider=LLMProvider.QWEN,
            reasoning_content="Step 1: ...",
        )
        assert resp.reasoning_content == "Step 1: ..."


class TestLLMConfig:
    """Test LLMConfig defaults."""

    def test_default_values(self):
        """Config has sensible defaults."""
        config = LLMConfig(provider=LLMProvider.DEEPSEEK)
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


class TestDeepSeekClient:
    """Test DeepSeekClient configuration."""

    def test_default_config(self):
        """Default DeepSeek settings."""
        config = LLMConfig(provider=LLMProvider.DEEPSEEK, api_key="test-key")
        client = DeepSeekClient(config)
        assert client.base_url == "https://api.deepseek.com/v1"
        assert client.model == "deepseek-chat"
        assert client.PROVIDER == LLMProvider.DEEPSEEK

    def test_custom_model(self):
        """Custom model override."""
        config = LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            api_key="test-key",
            model="deepseek-reasoner",
        )
        client = DeepSeekClient(config)
        assert client.model == "deepseek-reasoner"

    async def test_close_no_session(self):
        """Close without session doesn't error."""
        config = LLMConfig(provider=LLMProvider.DEEPSEEK, api_key="test-key")
        client = DeepSeekClient(config)
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


class TestQwenClient:
    """Test QwenClient with thinking mode."""

    def test_default_config(self):
        """Default Qwen settings."""
        config = LLMConfig(provider=LLMProvider.QWEN, api_key="test-key")
        client = QwenClient(config)
        assert "dashscope-intl" in client.base_url
        assert client.model == "qwen-plus"
        assert client.PROVIDER == LLMProvider.QWEN

    def test_thinking_models_set(self):
        """Thinking models are defined."""
        assert "qwen-plus" in QwenClient.THINKING_MODELS
        assert "qwen-flash" in QwenClient.THINKING_MODELS
        assert "qwen3-max" in QwenClient.THINKING_MODELS

    def test_build_payload_basic(self):
        """Basic payload without thinking mode."""
        config = LLMConfig(provider=LLMProvider.QWEN, api_key="test-key")
        client = QwenClient(config)
        messages = [LLMMessage(role="user", content="test")]

        payload = client._build_payload(messages)
        assert payload["model"] == "qwen-plus"
        assert "enable_thinking" not in payload

    def test_build_payload_with_thinking(self):
        """Payload with thinking mode enabled."""
        config = LLMConfig(provider=LLMProvider.QWEN, api_key="test-key")
        client = QwenClient(config)
        messages = [LLMMessage(role="user", content="test")]

        payload = client._build_payload(messages, enable_thinking=True)
        assert payload["enable_thinking"] is True

    def test_build_payload_non_thinking_model(self):
        """Thinking mode ignored for non-thinking models."""
        config = LLMConfig(provider=LLMProvider.QWEN, api_key="test-key", model="random-model")
        client = QwenClient(config)
        messages = [LLMMessage(role="user", content="test")]

        payload = client._build_payload(messages, enable_thinking=True)
        assert "enable_thinking" not in payload


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

    def test_create_deepseek(self):
        """Factory creates DeepSeekClient."""
        config = LLMConfig(provider=LLMProvider.DEEPSEEK, api_key="test")
        client = LLMClientFactory.create(config)
        assert isinstance(client, DeepSeekClient)

    def test_create_perplexity(self):
        """Factory creates PerplexityClient."""
        config = LLMConfig(provider=LLMProvider.PERPLEXITY, api_key="test")
        client = LLMClientFactory.create(config)
        assert isinstance(client, PerplexityClient)

    def test_create_qwen(self):
        """Factory creates QwenClient."""
        config = LLMConfig(provider=LLMProvider.QWEN, api_key="test")
        client = LLMClientFactory.create(config)
        assert isinstance(client, QwenClient)

    def test_create_ollama(self):
        """Factory creates OllamaClient."""
        config = LLMConfig(provider=LLMProvider.OLLAMA)
        client = LLMClientFactory.create(config)
        assert isinstance(client, OllamaClient)

    def test_create_unsupported_raises(self):
        """Unsupported provider raises ValueError."""
        config = LLMConfig(provider=LLMProvider.ANTHROPIC, api_key="test")
        with pytest.raises(ValueError, match="Unsupported provider"):
            LLMClientFactory.create(config)


class TestLLMClientPool:
    """Test LLMClientPool load balancing and failover."""

    def test_empty_pool_raises(self):
        """Empty pool raises on chat."""
        pool = LLMClientPool()
        with pytest.raises(RuntimeError, match="No clients"):
            asyncio.get_event_loop().run_until_complete(pool.chat([LLMMessage(role="user", content="test")]))

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
            provider=LLMProvider.DEEPSEEK,
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
    """Test OpenAICompatibleClient shared behavior."""

    def test_build_payload(self):
        """Default payload building."""
        config = LLMConfig(provider=LLMProvider.DEEPSEEK, api_key="test")
        client = DeepSeekClient(config)
        messages = [LLMMessage(role="user", content="hello")]

        payload = client._build_payload(messages)
        assert payload["model"] == "deepseek-chat"
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 4096
        assert len(payload["messages"]) == 1

    def test_parse_response(self):
        """Default response parsing."""
        config = LLMConfig(provider=LLMProvider.DEEPSEEK, api_key="test")
        client = DeepSeekClient(config)

        mock_data = {
            "choices": [
                {
                    "message": {"content": "Hello world"},
                    "finish_reason": "stop",
                }
            ],
            "model": "deepseek-chat",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        resp = client._parse_response(mock_data, latency=100.0)
        assert resp.content == "Hello world"
        assert resp.model == "deepseek-chat"
        assert resp.provider == LLMProvider.DEEPSEEK
        assert resp.total_tokens == 15
        assert resp.latency_ms == 100.0

    def test_stats_initialized_zero(self):
        """Stats start at zero."""
        config = LLMConfig(provider=LLMProvider.DEEPSEEK, api_key="test")
        client = DeepSeekClient(config)
        assert client.total_requests == 0
        assert client.total_tokens == 0
        assert client.total_cost == 0.0


class TestBackwardCompatibility:
    """Test that connections.py re-exports work."""

    def test_import_from_connections(self):
        """All symbols importable from connections.py."""
        from backend.agents.llm import connections

        symbols = [
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
            "QwenClient",
            "RateLimiter",
        ]
        for sym in symbols:
            assert hasattr(connections, sym), f"connections.py missing {sym}"
            assert getattr(connections, sym) is not None
