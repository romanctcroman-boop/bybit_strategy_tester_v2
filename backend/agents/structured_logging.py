"""
Structured Logging with Correlation IDs

Provides correlation ID propagation across all agent calls for distributed tracing.
Addresses audit finding: "Need structured logging with correlation IDs" (DeepSeek+Perplexity, P1)
"""

from __future__ import annotations

import contextvars
import uuid
from typing import Any

from loguru import logger

# Context variable for correlation ID propagation
_correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlation_id", default=None)


def get_correlation_id() -> str:
    """Get current correlation ID, creating one if needed."""
    cid = _correlation_id_var.get()
    if cid is None:
        cid = str(uuid.uuid4())[:12]
        _correlation_id_var.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current context."""
    _correlation_id_var.set(cid)


def new_correlation_id() -> str:
    """Generate and set a new correlation ID."""
    cid = str(uuid.uuid4())[:12]
    _correlation_id_var.set(cid)
    return cid


def agent_log(
    level: str,
    message: str,
    *,
    agent: str | None = None,
    component: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Structured log entry with correlation ID.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        message: Log message
        agent: Agent name (deepseek, qwen, perplexity)
        component: Component name (key_pool, rate_limiter, memory)
        extra: Additional structured data
    """
    cid = get_correlation_id()
    prefix_parts = [f"[{cid}]"]
    if agent:
        prefix_parts.append(f"[{agent}]")
    if component:
        prefix_parts.append(f"[{component}]")

    prefix = " ".join(prefix_parts)
    full_message = f"{prefix} {message}"

    log_func = getattr(logger, level.lower(), logger.info)

    if extra:
        log_func(f"{full_message} | {extra}")
    else:
        log_func(full_message)


class AgentLogger:
    """Pre-configured logger for a specific agent/component."""

    def __init__(self, agent: str, component: str | None = None):
        self.agent = agent
        self.component = component

    def debug(self, message: str, **extra: Any) -> None:
        agent_log("DEBUG", message, agent=self.agent, component=self.component, extra=extra or None)

    def info(self, message: str, **extra: Any) -> None:
        agent_log("INFO", message, agent=self.agent, component=self.component, extra=extra or None)

    def warning(self, message: str, **extra: Any) -> None:
        agent_log("WARNING", message, agent=self.agent, component=self.component, extra=extra or None)

    def error(self, message: str, **extra: Any) -> None:
        agent_log("ERROR", message, agent=self.agent, component=self.component, extra=extra or None)
