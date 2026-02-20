"""
MCP Configuration Integration

Extends AgentConfig with MCP-specific settings.
Addresses: MCP server configuration, API keys management, tool registry
"""

from __future__ import annotations

import os
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field, field_validator


class MCPServerConfig(BaseModel):
    """Configuration for individual MCP server."""

    enabled: bool = True
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    timeout: int = Field(default=120, ge=10, le=600)
    max_retries: int = Field(default=3, ge=1, le=10)


class MCPConfig(BaseModel):
    """MCP infrastructure configuration."""

    # Server configurations
    deepseek_enabled: bool = True
    bybit_enabled: bool = True
    perplexity_enabled: bool = True

    # Timeouts
    default_timeout: int = Field(default=120, ge=10, le=600)
    progressive_timeouts: list[int] = Field(default=[60, 120, 300, 600])

    # Circuit breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = Field(default=3, ge=1, le=10)
    circuit_breaker_timeout: int = Field(default=30, ge=10, le=300)

    # Tool validation
    validate_tool_args: bool = True
    strict_validation: bool = False

    # Metrics
    enable_metrics: bool = True
    metrics_port: int = Field(default=9090, ge=1024, le=65535)

    @field_validator("progressive_timeouts")
    @classmethod
    def validate_timeouts(cls, v: list[int]) -> list[int]:
        if not v or len(v) < 2:
            raise ValueError("progressive_timeouts must have at least 2 values")
        if v != sorted(v):
            raise ValueError("progressive_timeouts must be in ascending order")
        return v


def get_mcp_config() -> MCPConfig:
    """Get MCP configuration from environment."""
    config_data: dict[str, Any] = {}

    # Override from env vars
    env_mappings = {
        "MCP_DEEPSEEK_ENABLED": ("deepseek_enabled", lambda x: x.lower() == "true"),
        "MCP_BYBIT_ENABLED": ("bybit_enabled", lambda x: x.lower() == "true"),
        "MCP_PERPLEXITY_ENABLED": ("perplexity_enabled", lambda x: x.lower() == "true"),
        "MCP_DEFAULT_TIMEOUT": ("default_timeout", int),
        "MCP_CIRCUIT_BREAKER_ENABLED": (
            "circuit_breaker_enabled",
            lambda x: x.lower() == "true",
        ),
        "MCP_VALIDATE_ARGS": ("validate_tool_args", lambda x: x.lower() == "true"),
        "MCP_METRICS_PORT": ("metrics_port", int),
    }

    for env_key, (field, converter) in env_mappings.items():
        value = os.getenv(env_key)
        if value is not None:
            try:
                config_data[field] = converter(value)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid env var {env_key}={value}: {e}")

    config = MCPConfig(**config_data)
    logger.info(
        f"✅ MCP config: deepseek={config.deepseek_enabled}, "
        f"bybit={config.bybit_enabled}, perplexity={config.perplexity_enabled}, "
        f"timeout={config.default_timeout}s"
    )
    return config


def validate_mcp_startup() -> list[str]:
    """
    Validate MCP configuration at startup.
    Returns list of errors (empty = all OK).
    """
    errors: list[str] = []

    # Check API keys for enabled servers
    config = get_mcp_config()

    if config.deepseek_enabled and not os.getenv("DEEPSEEK_API_KEY"):
        errors.append("MCP: DeepSeek enabled but DEEPSEEK_API_KEY not set")

    if config.perplexity_enabled and not os.getenv("PERPLEXITY_API_KEY"):
        errors.append("MCP: Perplexity enabled but PERPLEXITY_API_KEY not set")

    # Validate MCP bridge is importable
    try:
        from backend.mcp.mcp_integration import get_mcp_bridge

        get_mcp_bridge()
    except Exception as e:
        errors.append(f"MCP: Failed to import MCP bridge: {e}")

    if errors:
        for err in errors:
            logger.error(f"❌ MCP startup error: {err}")
    else:
        logger.info("✅ MCP configuration validated successfully")

    return errors
