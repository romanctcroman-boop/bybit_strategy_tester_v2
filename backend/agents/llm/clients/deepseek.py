"""
DeepSeek LLM Client

OpenAI-compatible API client for DeepSeek models.
"""

from __future__ import annotations

from backend.agents.llm.base_client import (
    LLMProvider,
    OpenAICompatibleClient,
)


class DeepSeekClient(OpenAICompatibleClient):
    """DeepSeek API client with circuit breaker protection."""

    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
    DEFAULT_MODEL = "deepseek-chat"
    PROVIDER = LLMProvider.DEEPSEEK
    BREAKER_NAME = "deepseek_llm_client"
    EMOJI = "🔵"


__all__ = ["DeepSeekClient"]
