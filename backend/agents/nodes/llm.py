"""LLM provider routing primitives.

Re-exports :class:`_LLMCallMixin` from the monolithic
``trading_strategy_graph`` module.  The mixin provides a unified
``_call_llm()`` entry point that:

* Resolves API keys via :class:`APIKeyPoolManager` (with KeyManager fallback).
* Passes every prompt through :class:`SecurityOrchestrator` (prompt-injection gate).
* Records pool telemetry (success / rate-limit / auth-error / error).
* Routes to the correct provider (Anthropic Claude vs Perplexity) based on
  the ``agent_name`` alias.
"""

from backend.agents.trading_strategy_graph import _LLMCallMixin

LLMCallMixin = _LLMCallMixin  # public alias — underscore prefix is historical

__all__ = ["LLMCallMixin", "_LLMCallMixin"]
