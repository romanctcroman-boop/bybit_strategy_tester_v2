"""
Real LLM API Connections — Backward-compatible re-export module.

.. deprecated:: 2026-02-13
    This module is a backward-compatibility shim. Import directly from:
    - ``backend.agents.llm.base_client`` (LLMClient, LLMConfig, etc.)
    - ``backend.agents.llm.clients.claude`` (ClaudeClient)
    - ``backend.agents.llm.clients.perplexity`` (PerplexityClient)
    - ``backend.agents.llm.clients.ollama`` (OllamaClient)

System uses Claude (Anthropic) + Perplexity only.
DeepSeek and Qwen have been removed.
"""

import warnings

warnings.warn(
    "backend.agents.llm.connections is deprecated. "
    "Import from backend.agents.llm.base_client or backend.agents.llm.clients.* instead.",
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
from backend.agents.llm.clients.claude import ClaudeClient
from backend.agents.llm.clients.ollama import OllamaClient
from backend.agents.llm.clients.perplexity import PerplexityClient

__all__ = [
    "ClaudeClient",
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
    "RateLimiter",
]
