"""
LLM Response Cache

Caches actual LLM responses (especially Perplexity market research calls)
to avoid redundant API calls and improve cache hit rate in PromptsMonitor.

Key design decisions:
- Singleton backed by ContextCache (already tracked by PromptsMonitor)
- Normalizes queries: strips timestamps, current prices, and ephemeral numbers
  so semantically identical questions get the same cache key
- TTL: 300s for Perplexity (market context changes slowly on minute scale)
        60s for DeepSeek strategy generation (more unique per request)
- Thread-safe: ContextCache uses dict, Python GIL covers single ops
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from loguru import logger

from backend.agents.prompts.context_cache import ContextCache

# Per-provider TTL in seconds
_TTL_BY_AGENT: dict[str, int] = {
    "perplexity": 300,   # 5 min — market regime doesn't change that fast
    "deepseek":    60,   # 1 min — strategy generation is more query-specific
    "qwen":        90,   # 1.5 min
}

# Patterns to strip before hashing (ephemeral, frequently-changing values)
_STRIP_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?Z?\b"),  # ISO timestamps
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),           # date strings  2026-03-19
    re.compile(r"\$[\d,]+(?:\.\d+)?\b"),             # dollar prices $84,000.50
    re.compile(r"\b\d{4,6}(?:\.\d+)?\s*(?:USDT?|BTC|ETH)\b", re.IGNORECASE),  # "84000 USDT"
    re.compile(r"\bcurrent(?:ly)? (?:at|trading at|price)[^.]*\.", re.IGNORECASE),  # "currently at …."
    re.compile(r"\btoday[''']?s price[^.]*\.", re.IGNORECASE),
]


def _normalize_text(text: str) -> str:
    """Strip ephemeral values from prompt text before cache-key computation."""
    result = text
    for pattern in _STRIP_PATTERNS:
        result = pattern.sub(" ", result)
    # Collapse multiple spaces
    result = re.sub(r" {2,}", " ", result).strip()
    return result


def _messages_cache_key(messages: list[dict], model: str, agent: str) -> str:
    """Compute a stable cache key from normalized messages."""
    normalized = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, str):
            content = _normalize_text(content)
        normalized.append({"role": role, "content": content})

    payload = json.dumps({"agent": agent, "model": model, "messages": normalized}, sort_keys=True)
    return "llm:" + hashlib.sha256(payload.encode()).hexdigest()[:24]


class LLMResponseCache:
    """
    Singleton LLM response cache backed by ContextCache.

    Usage::

        cache = get_llm_response_cache()
        key = cache.key(messages, model, agent)
        hit = cache.get(key)
        if hit is None:
            response = await api_call(...)
            cache.set(key, response, agent)

    The ContextCache instance is the **same object** that PromptsMonitor
    queries via ``ContextCache().get_stats()``, so hits will be reflected
    in the monitoring dashboard and stop the 0%-hit-rate alert storm.
    """

    def __init__(self) -> None:
        # Shared with PromptsMonitor — max_size=1000, default_ttl=300
        self._cache = ContextCache(max_size=1000, default_ttl=300, enable_stats=True)
        logger.info("🗃️ LLMResponseCache initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def key(self, messages: list[dict], model: str, agent: str) -> str:
        """Return a normalized, stable cache key for this request."""
        return _messages_cache_key(messages, model, agent)

    def get(self, cache_key: str) -> dict[str, Any] | None:
        """Return cached response or None."""
        return self._cache.get(cache_key)

    def set(self, cache_key: str, response: dict[str, Any], agent: str) -> None:
        """Cache a response with agent-appropriate TTL."""
        ttl = _TTL_BY_AGENT.get(agent, 120)
        # Store flat — ContextCache wraps in CacheEntry internally
        self._cache.set(response, ttl=ttl, key=cache_key)
        logger.debug(f"🗃️ LLM response cached ({agent}, ttl={ttl}s, key={cache_key[:16]}…)")

    def get_stats(self) -> dict[str, Any]:
        """Proxy to ContextCache.get_stats() — used by tests."""
        return self._cache.get_stats()

    def invalidate(self, cache_key: str) -> bool:
        """Remove a single entry (e.g., on forced refresh)."""
        return self._cache.delete(cache_key)

    def clear(self) -> int:
        """Clear all entries."""
        return self._cache.clear()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_instance: LLMResponseCache | None = None


def get_llm_response_cache() -> LLMResponseCache:
    """Return the process-level singleton LLMResponseCache."""
    global _instance
    if _instance is None:
        _instance = LLMResponseCache()
    return _instance
