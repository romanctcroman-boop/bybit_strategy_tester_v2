"""
DeepSeek LLM Client

OpenAI-compatible API client for DeepSeek models.
Supports automatic Context Caching (KV cache): cache hits cost 10% of normal
input price, yielding ~90% savings on repeated prefixes. No special request
parameters required — DeepSeek caches automatically and reports usage via
`prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` in the response.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from backend.agents.llm.base_client import (
    LLMProvider,
    LLMResponse,
    OpenAICompatibleClient,
)


class DeepSeekClient(OpenAICompatibleClient):
    """DeepSeek API client with circuit breaker protection and cache tracking."""

    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
    DEFAULT_MODEL = "deepseek-chat"
    PROVIDER = LLMProvider.DEEPSEEK
    BREAKER_NAME = "deepseek_llm_client"
    EMOJI = "🔵"

    def _parse_response(self, data: dict[str, Any], latency: float) -> LLMResponse:
        """Parse response and extract DeepSeek Context Cache metrics."""
        resp = super()._parse_response(data, latency)
        usage = data.get("usage", {})
        resp.prompt_cache_hit_tokens = usage.get("prompt_cache_hit_tokens", 0)
        resp.prompt_cache_miss_tokens = usage.get("prompt_cache_miss_tokens", 0)

        if resp.prompt_cache_hit_tokens:
            hit_pct = resp.prompt_cache_hit_tokens / max(resp.prompt_tokens, 1) * 100
            # 90% savings on cache hit tokens vs normal input price ($0.14/1M)
            savings_usd = (resp.prompt_cache_hit_tokens / 1_000_000) * 0.14 * 0.9
            logger.debug(
                f"🔵 DeepSeek cache hit: {resp.prompt_cache_hit_tokens:,} tokens "
                f"({hit_pct:.0f}% of prompt) — ~${savings_usd:.5f} saved"
            )

        return resp


__all__ = ["DeepSeekClient"]
