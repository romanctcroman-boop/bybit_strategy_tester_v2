"""
Perplexity LLM Client

OpenAI-compatible API client for Perplexity models.

Note: sonar-pro does NOT support response_format / json_mode — plain text only.
Responses may include a top-level ``citations`` list of source URLs.
"""

from __future__ import annotations

from typing import Any

from backend.agents.llm.base_client import (
    LLMProvider,
    LLMResponse,
    OpenAICompatibleClient,
)


class PerplexityClient(OpenAICompatibleClient):
    """Perplexity API client with circuit breaker protection."""

    DEFAULT_BASE_URL = "https://api.perplexity.ai"
    DEFAULT_MODEL = "sonar-pro"
    PROVIDER = LLMProvider.PERPLEXITY
    BREAKER_NAME = "perplexity_llm_client"
    EMOJI = "🟣"

    def _parse_response(self, data: dict[str, Any], latency: float) -> LLMResponse:
        """Parse response and extract Perplexity-specific ``citations`` field."""
        resp = super()._parse_response(data, latency)
        citations = data.get("citations")
        if citations:
            resp.citations = list(citations)
        return resp


__all__ = ["PerplexityClient"]
