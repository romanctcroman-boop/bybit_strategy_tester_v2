"""Tests for config_validator.py."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from backend.agents.config_validator import (
    AgentConfig,
    MemoryConfig,
    PromptConfig,
    RateLimitConfig,
    SecurityConfig,
    validate_startup_config,
)


class TestPromptConfig:
    def test_defaults(self):
        config = PromptConfig()
        assert config.max_length == 16000
        assert config.truncate_notice == "[TRUNCATED]"
        assert config.max_drawdown_pct == 15.0
        assert config.min_sharpe_target == 1.0

    def test_validation_min_length(self):
        with pytest.raises(ValidationError):
            PromptConfig(max_length=500)

    def test_validation_max_length(self):
        with pytest.raises(ValidationError):
            PromptConfig(max_length=200000)


class TestRateLimitConfig:
    def test_defaults(self):
        config = RateLimitConfig()
        assert config.max_tokens_per_minute == 100_000
        assert config.max_tokens_per_hour == 2_000_000
        assert config.max_cost_per_hour_usd == 5.0
        assert config.max_cost_per_day_usd == 50.0


class TestSecurityConfig:
    def test_defaults(self):
        config = SecurityConfig()
        assert config.enable_prompt_guard is True
        assert config.enable_semantic_guard is False
        assert config.max_tool_calls == 10


class TestMemoryConfig:
    def test_defaults(self):
        config = MemoryConfig()
        assert config.backend == "sqlite"
        assert config.sqlite_path == "data/agent_memory.db"
        assert config.ttl_working_seconds == 300
        assert config.max_items_per_tier == 10000

    def test_invalid_backend(self):
        with pytest.raises(ValidationError):
            MemoryConfig(backend="postgres")


class TestAgentConfig:
    def test_defaults(self):
        config = AgentConfig()
        assert isinstance(config.prompt, PromptConfig)
        assert isinstance(config.security, SecurityConfig)
        assert isinstance(config.memory, MemoryConfig)
        assert "deepseek" in config.rate_limit

    def test_default_models(self):
        config = AgentConfig()
        assert config.deepseek_model == "deepseek-chat"
        assert config.qwen_model == "qwen-plus"
        assert config.perplexity_model == "sonar-pro"

    def test_default_urls(self):
        config = AgentConfig()
        assert "deepseek" in config.deepseek_base_url
        assert "dashscope" in config.qwen_base_url
        assert "perplexity" in config.perplexity_base_url

    def test_invalid_deepseek_model(self):
        with pytest.raises(ValidationError):
            AgentConfig(deepseek_model="gpt-4")

    def test_valid_deepseek_models(self):
        c1 = AgentConfig(deepseek_model="deepseek-chat")
        assert c1.deepseek_model == "deepseek-chat"
        c2 = AgentConfig(deepseek_model="deepseek-reasoner")
        assert c2.deepseek_model == "deepseek-reasoner"


class TestValidateStartupConfig:
    def test_missing_api_keys(self):
        with patch.dict(os.environ, {}, clear=True):
            import backend.agents.config_validator as cv

            cv._config = None
            errors = validate_startup_config()
            key_errors = [e for e in errors if "Missing required" in e]
            assert len(key_errors) >= 1

    def test_with_all_keys_present(self):
        env = {
            "DEEPSEEK_API_KEY": "sk-test",
            "QWEN_API_KEY": "sk-test",
            "PERPLEXITY_API_KEY": "sk-test",
        }
        with patch.dict(os.environ, env):
            import backend.agents.config_validator as cv

            cv._config = None
            errors = validate_startup_config()
            key_errors = [e for e in errors if "Missing required" in e]
            assert len(key_errors) == 0
