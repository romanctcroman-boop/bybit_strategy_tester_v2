"""
Perplexity LLM Client

OpenAI-compatible API client for Perplexity models.
"""

from __future__ import annotations

from backend.agents.llm.base_client import (
    LLMProvider,
    OpenAICompatibleClient,
)


class PerplexityClient(OpenAICompatibleClient):
    """Perplexity API client with circuit breaker protection."""

    DEFAULT_BASE_URL = "https://api.perplexity.ai"
    DEFAULT_MODEL = "sonar-pro"
    PROVIDER = LLMProvider.PERPLEXITY
    BREAKER_NAME = "perplexity_llm_client"
    EMOJI = "🟣"


__all__ = ["PerplexityClient"]
