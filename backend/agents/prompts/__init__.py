"""
Prompt templates package for LLM agent system.

Provides structured prompt generation, response parsing,
and market context building for trading strategy generation.

Production Features (v2.0):
- Prompt validation (security)
- Prompt logging (audit trails)
- Dynamic examples (market regime aware)
- Adaptive temperature (confidence based)
- Prompt compression (cost optimization)
- Context caching (performance)
"""

from backend.agents.prompts.context_builder import MarketContextBuilder
from backend.agents.prompts.prompt_engineer import PromptEngineer
from backend.agents.prompts.response_parser import ResponseParser, StrategyDefinition

# P0: Security & Audit
from backend.agents.prompts.prompt_validator import PromptValidator, ValidationResult
from backend.agents.prompts.prompt_logger import PromptLogger, PromptLogEntry

# P1: Optimization
from backend.agents.prompts.temperature_adapter import TemperatureAdapter, TemperatureConfig
from backend.agents.prompts.prompt_compressor import PromptCompressor, CompressionResult

# P2: Performance
from backend.agents.prompts.context_cache import ContextCache, MarketContextCache, CacheEntry

__all__ = [
    # Core
    "MarketContextBuilder",
    "PromptEngineer",
    "ResponseParser",
    "StrategyDefinition",
    
    # P0: Security & Audit
    "PromptValidator",
    "ValidationResult",
    "PromptLogger",
    "PromptLogEntry",
    
    # P1: Optimization
    "TemperatureAdapter",
    "TemperatureConfig",
    "PromptCompressor",
    "CompressionResult",
    
    # P2: Performance
    "ContextCache",
    "MarketContextCache",
    "CacheEntry",
]
