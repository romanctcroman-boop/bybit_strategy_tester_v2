"""
Real LLM API Connections — Backward-compatible re-export module.

.. deprecated:: 2026-02-13
    This module is a backward-compatibility shim. Import directly from:
    - ``backend.agents.llm.base_client`` (LLMClient, LLMConfig, etc.)
    - ``backend.agents.llm.clients.deepseek`` (DeepSeekClient)
    - ``backend.agents.llm.clients.perplexity`` (PerplexityClient)
    - ``backend.agents.llm.clients.qwen`` (QwenClient)
    - ``backend.agents.llm.clients.ollama`` (OllamaClient)

    See ``docs/DEPRECATION_SCHEDULE.md`` for removal timeline (Q2 2026).
"""

import warnings

warnings.warn(
    "backend.agents.llm.connections is deprecated. "
    "Import from backend.agents.llm.base_client or backend.agents.llm.clients.* instead. "
    "See docs/DEPRECATION_SCHEDULE.md for migration guide.",
    DeprecationWarning,
    stacklevel=2,
)

from backend.agents.llm.base_client import (
    LLMClient,
    LLMClientFactory,
    LLMClientPool,
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    OpenAICompatibleClient,
    RateLimiter,
)
from backend.agents.llm.clients.deepseek import DeepSeekClient
from backend.agents.llm.clients.ollama import OllamaClient
from backend.agents.llm.clients.perplexity import PerplexityClient
from backend.agents.llm.clients.qwen import QwenClient

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
    "OpenAICompatibleClient",
    "PerplexityClient",
    "QwenClient",
    "RateLimiter",
]
