"""
Query Mixin — High-level convenience query methods.

Extracted from UnifiedAgentInterface to reduce god-class size.
Provides query_deepseek() and query_perplexity() with caching support.
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger

from backend.agents.models import AgentType
from backend.agents.request_models import AgentRequest, AgentResponse


class QueryMixin:
    """Mixin providing high-level query convenience methods with caching."""

    async def query_deepseek(
        self,
        prompt: str,
        *,
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Convenient method to query DeepSeek AI with caching support.

        Args:
            prompt: The question or prompt.
            model: DeepSeek model name.
            temperature: Response randomness (0.0-2.0).
            max_tokens: Maximum response length.
            use_cache: Enable/disable caching for this request (default: True).
            **kwargs: Additional parameters forwarded to cache key.

        Returns:
            dict with keys: response, model, tokens_used, latency_ms,
            api_key_id, from_cache, success, error.
        """
        cached = self._try_cache_get(prompt, model, temperature, max_tokens, use_cache, **kwargs)
        if cached is not None:
            logger.info("⚡ Cache HIT for DeepSeek query (latency: ~0ms)")
            return cached

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="chat",
            prompt=prompt,
        )

        start_time = time.time()
        response: AgentResponse = await self.send_request(request)  # type: ignore[attr-defined]
        latency_ms = (time.time() - start_time) * 1000

        result = self._build_query_result(response, model, latency_ms)

        self._try_cache_set(prompt, model, temperature, max_tokens, use_cache, result, **kwargs)
        return result

    async def query_perplexity(
        self,
        prompt: str,
        *,
        model: str = "sonar-pro",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Convenient method to query Perplexity AI with caching support.

        Args:
            prompt: The question or prompt.
            model: Perplexity model name (default: sonar-pro).
            temperature: Response randomness (0.0-2.0).
            max_tokens: Maximum response length.
            use_cache: Enable/disable caching for this request (default: True).
            **kwargs: Additional parameters forwarded to cache key.

        Returns:
            dict with keys: response, model, tokens_used, latency_ms,
            api_key_id, from_cache, success, error.
        """
        cached = self._try_cache_get(prompt, model, temperature, max_tokens, use_cache, **kwargs)
        if cached is not None:
            logger.info("⚡ Cache HIT for Perplexity query (latency: ~0ms)")
            return cached

        request = AgentRequest(
            agent_type=AgentType.PERPLEXITY,
            task_type="search",
            prompt=prompt,
        )

        start_time = time.time()
        response: AgentResponse = await self.send_request(request)  # type: ignore[attr-defined]
        latency_ms = (time.time() - start_time) * 1000

        result = self._build_query_result(response, model, latency_ms)

        self._try_cache_set(prompt, model, temperature, max_tokens, use_cache, result, **kwargs)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_query_result(response: AgentResponse, model: str, latency_ms: float) -> dict[str, Any]:
        """Build standardized query result dict from AgentResponse."""
        tokens_used = None
        if response.tokens_used:
            tokens_used = {
                "prompt_tokens": response.tokens_used.prompt_tokens,
                "completion_tokens": response.tokens_used.completion_tokens,
                "total_tokens": response.tokens_used.total_tokens,
                "reasoning_tokens": getattr(response.tokens_used, "reasoning_tokens", None),
                "cost_usd": response.tokens_used.cost_usd,
            }
        return {
            "response": response.content,
            "model": model,
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
            "api_key_id": (str(response.api_key_index) if response.api_key_index is not None else None),
            "success": response.success,
            "error": response.error,
            "from_cache": False,
        }

    @staticmethod
    def _try_cache_get(
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        use_cache: bool,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Try to fetch response from AI cache."""
        if not use_cache:
            return None
        try:
            from backend.core.ai_cache import get_cache_manager

            cache_manager = get_cache_manager()
            return cache_manager.get(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception as e:
            logger.debug(f"Cache check failed: {e}, proceeding without cache")
            return None

    @staticmethod
    def _try_cache_set(
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        use_cache: bool,
        result: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Try to save successful response to AI cache."""
        if not use_cache or not result.get("success") or not result.get("response"):
            return
        try:
            from backend.core.ai_cache import get_cache_manager

            cache_manager = get_cache_manager()
            cache_manager.set(
                prompt=prompt,
                model=model,
                response=result,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            logger.debug("💾 Cached response")
        except Exception as e:
            logger.debug(f"Cache save failed: {e}")


__all__ = ["QueryMixin"]
