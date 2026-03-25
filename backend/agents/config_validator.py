"""
Agent Configuration Validation

Centralized configuration with Pydantic Settings and fail-fast startup validation.
Addresses audit finding: "Configuration fragmented, no validation at startup" (DeepSeek+Qwen, P1)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    _Converter = Callable[[str], Any]

from loguru import logger
from pydantic import BaseModel, Field, field_validator

try:
    from backend.agents.mcp_config import MCPConfig, get_mcp_config, validate_mcp_startup
except ImportError:
    MCPConfig = None  # type: ignore
    get_mcp_config = None  # type: ignore
    validate_mcp_startup = None  # type: ignore


class PromptConfig(BaseModel):
    """Prompt engineering configuration."""

    max_length: int = Field(default=16000, ge=1000, le=100000)
    truncate_notice: str = "[TRUNCATED]"
    max_drawdown_pct: float = Field(default=15.0, ge=1.0, le=100.0)
    min_sharpe_target: float = Field(default=1.0, ge=0.0)


class RateLimitConfig(BaseModel):
    """Per-provider rate limiting configuration."""

    max_tokens_per_minute: int = Field(default=100_000, ge=1000)
    max_tokens_per_hour: int = Field(default=2_000_000, ge=10000)
    max_cost_per_hour_usd: float = Field(default=5.0, ge=0.0)
    max_cost_per_day_usd: float = Field(default=50.0, ge=0.0)


class SecurityConfig(BaseModel):
    """Security-related configuration."""

    enable_prompt_guard: bool = True
    enable_semantic_guard: bool = False
    max_tool_calls: int = Field(default=10, ge=1, le=100)
    blocked_patterns_file: str | None = None


class MemoryConfig(BaseModel):
    """Memory system configuration."""

    backend: str = Field(default="sqlite", pattern=r"^(sqlite|redis|memory)$")
    sqlite_path: str = "data/agent_memory.db"
    ttl_working_seconds: int = Field(default=300, ge=60)
    ttl_episodic_seconds: int = Field(default=86400, ge=3600)
    ttl_semantic_seconds: int = Field(default=2592000, ge=86400)
    max_items_per_tier: int = Field(default=10000, ge=100)


class AgentConfig(BaseModel):
    """Complete agent infrastructure configuration."""

    prompt: PromptConfig = Field(default_factory=PromptConfig)
    rate_limit: dict[str, RateLimitConfig] = Field(
        default_factory=lambda: {
            "deepseek": RateLimitConfig(),
            "qwen": RateLimitConfig(),
            "perplexity": RateLimitConfig(),
        }
    )
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    mcp: MCPConfig | None = None  # Optional MCP configuration

    # API endpoints
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    perplexity_base_url: str = "https://api.perplexity.ai"

    # Models
    deepseek_model: str = "deepseek-chat"
    qwen_model: str = "qwen-plus"
    perplexity_model: str = "sonar-pro"

    @field_validator("deepseek_model")
    @classmethod
    def validate_deepseek_model(cls, v: str) -> str:
        allowed = {"deepseek-chat", "deepseek-reasoner"}
        if v not in allowed:
            raise ValueError(f"deepseek_model must be one of {allowed}")
        return v


# Singleton
_config: AgentConfig | None = None


def get_agent_config() -> AgentConfig:
    """Get validated agent configuration (singleton)."""
    global _config
    if _config is None:
        _config = _load_config()
    return _config


def _load_config() -> AgentConfig:
    """Load configuration from environment and validate."""
    config_data: dict[str, Any] = {}

    # Override from env vars
    env_mappings: dict[str, tuple[str, str | None, _Converter]] = {
        "AGENT_PROMPT_MAX_LENGTH": ("prompt", "max_length", int),
        "AGENT_MAX_DRAWDOWN_PCT": ("prompt", "max_drawdown_pct", float),
        "AGENT_MEMORY_BACKEND": ("memory", "backend", str),
        "AGENT_MEMORY_SQLITE_PATH": ("memory", "sqlite_path", str),
        "AGENT_SECURITY_SEMANTIC_GUARD": ("security", "enable_semantic_guard", lambda x: x.lower() == "true"),
        "DEEPSEEK_MODEL": ("deepseek_model", None, str),
        "QWEN_MODEL": ("qwen_model", None, str),
        "PERPLEXITY_MODEL": ("perplexity_model", None, str),
    }

    for env_key, (section, field, converter) in env_mappings.items():
        value = os.getenv(env_key)
        if value is not None:
            try:
                converted = converter(value)  # type: ignore[operator]
                if field is not None:
                    config_data.setdefault(section, {})[field] = converted
                else:
                    config_data[section] = converted
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid env var {env_key}={value}: {e}")

    # Load MCP config if available
    if get_mcp_config is not None:
        try:
            config_data["mcp"] = get_mcp_config()
        except Exception as e:
            logger.warning(f"Failed to load MCP config: {e}")

    config = AgentConfig(**config_data)
    logger.info(
        f"✅ Agent config validated: memory={config.memory.backend}, "
        f"prompt_max={config.prompt.max_length}, "
        f"semantic_guard={config.security.enable_semantic_guard}, "
        f"mcp={config.mcp is not None}"
    )
    return config


def validate_startup_config() -> list[str]:
    """
    Validate all required configuration at startup.
    Returns list of errors (empty = all OK).

    Call this at app startup for fail-fast behavior.
    """
    errors: list[str] = []

    # Check API keys exist
    required_keys = ["DEEPSEEK_API_KEY", "QWEN_API_KEY", "PERPLEXITY_API_KEY"]
    for key in required_keys:
        if not os.getenv(key):
            errors.append(f"Missing required environment variable: {key}")

    # Validate config loads without errors
    try:
        config = get_agent_config()
        if config.memory.backend == "sqlite":
            from pathlib import Path

            db_dir = Path(config.memory.sqlite_path).parent
            if not db_dir.exists():
                db_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created memory database directory: {db_dir}")
    except Exception as e:
        errors.append(f"Configuration validation failed: {e}")

    # Validate MCP configuration if available
    if validate_mcp_startup is not None:
        try:
            mcp_errors = validate_mcp_startup()
            errors.extend(mcp_errors)
        except Exception as e:
            errors.append(f"MCP validation failed: {e}")

    if errors:
        for err in errors:
            logger.error(f"❌ Startup config error: {err}")
    else:
        logger.info("✅ All startup configuration validated successfully")

    return errors
