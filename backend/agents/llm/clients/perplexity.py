"""
Perplexity LLM Client

OpenAI-compatible API client for Perplexity models.

Note: sonar-pro does NOT support response_format / json_mode — plain text only.
Responses may include a top-level ``citations`` list of source URLs.

Model routing:
  sonar-pro              — standard web search (default)
  sonar-reasoning-pro    — chain-of-thought + web search; use for complex regime analysis

Search parameters (pass as kwargs to chat()):
  search_context_size    — "low" / "medium" (default) / "high"
  search_domain_filter   — list of domains to include, e.g. CRYPTO_SEARCH_DOMAINS
"""

from __future__ import annotations

from typing import Any

from backend.agents.llm.base_client import (
    LLMProvider,
    LLMResponse,
    OpenAICompatibleClient,
)

# Authoritative crypto/finance domains for grounding queries
CRYPTO_SEARCH_DOMAINS = [
    "coinmarketcap.com",
    "coingecko.com",
    "tradingview.com",
    "bybit.com",
    "binance.com",
    "bloomberg.com",
    "reuters.com",
    "coindesk.com",
    "cointelegraph.com",
]


class PerplexityClient(OpenAICompatibleClient):
    """Perplexity API client with circuit breaker protection."""

    DEFAULT_BASE_URL = "https://api.perplexity.ai"
    DEFAULT_MODEL = "sonar-pro"
    PROVIDER = LLMProvider.PERPLEXITY
    BREAKER_NAME = "perplexity_llm_client"
    EMOJI = "🟣"

    def _build_payload(self, messages: list[Any], **kwargs: Any) -> dict[str, Any]:
        """Extend base payload with Perplexity search parameters.

        Extra kwargs (consumed here, not forwarded to OpenAI base):
          search_context_size (str): "low" | "medium" | "high"  (default: "medium")
          search_domain_filter (list[str]): restrict search to specific domains
        """
        search_context_size = kwargs.pop("search_context_size", "medium")
        search_domain_filter = kwargs.pop("search_domain_filter", None)

        payload = super()._build_payload(messages, **kwargs)
        payload["search_context_size"] = search_context_size
        if search_domain_filter:
            payload["search_domain_filter"] = list(search_domain_filter)
        return payload

    def _parse_response(self, data: dict[str, Any], latency: float) -> LLMResponse:
        """Parse response and extract Perplexity-specific ``citations`` field."""
        resp = super()._parse_response(data, latency)
        citations = data.get("citations")
        if citations:
            resp.citations = list(citations)
        return resp


__all__ = ["CRYPTO_SEARCH_DOMAINS", "PerplexityClient"]
