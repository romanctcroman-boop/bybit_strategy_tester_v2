"""
Agent Security Module

Provides security layers for AI agent interactions:
- PromptGuard: Detects and blocks prompt injection attacks
- OutputValidator: Validates LLM outputs for safety and compliance
- AgentRateLimiter: Per-agent rate limiting with sliding window

Usage:
    from backend.agents.security import PromptGuard, OutputValidator, AgentRateLimiter

    guard = PromptGuard()
    if guard.is_safe(user_prompt):
        response = await agent.ask(user_prompt)
        validated = OutputValidator().validate(response)
"""

from backend.agents.security.output_validator import (
    OutputValidator,
    ValidationResult,
    ValidationRule,
)
from backend.agents.security.prompt_guard import (
    PromptGuard,
    ThreatCategory,
    ThreatDetection,
)
from backend.agents.security.rate_limiter import (
    AgentRateLimiter,
    RateLimitConfig,
    RateLimitResult,
)

__all__ = [
    "AgentRateLimiter",
    "OutputValidator",
    "PromptGuard",
    "RateLimitConfig",
    "RateLimitResult",
    "ThreatCategory",
    "ThreatDetection",
    "ValidationResult",
    "ValidationRule",
]
