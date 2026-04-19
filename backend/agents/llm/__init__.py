"""
LLM Integration Module

Provides real LLM API connections for AI agents.
Supported providers: Claude (Anthropic), Perplexity, Ollama.
Claude and Claude have been removed — use ClaudeClient instead.
"""

from .base_client import (
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
from .clients.claude import ClaudeClient
from .clients.ollama import OllamaClient
from .clients.perplexity import PerplexityClient

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
