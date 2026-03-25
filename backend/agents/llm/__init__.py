"""
LLM Integration Module

Provides real LLM API connections for AI agents.
Imports directly from base_client and clients/* (connections.py is deprecated).
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
from .clients.deepseek import DeepSeekClient
from .clients.ollama import OllamaClient
from .clients.perplexity import PerplexityClient
from .clients.qwen import QwenClient

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
