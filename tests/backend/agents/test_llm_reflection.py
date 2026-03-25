"""
Tests for LLM-backed Self-Reflection (Task 4.1)

Tests LLMReflectionProvider and LLMSelfReflectionEngine.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.self_improvement.llm_reflection import (
    REFLECTION_PROMPTS,
    REFLECTION_SYSTEM_PROMPT,
    LLMReflectionProvider,
    LLMSelfReflectionEngine,
)

# =============================================================================
# Test REFLECTION_PROMPTS
# =============================================================================


class TestReflectionPrompts:
    """Test reflection prompt templates."""

    def test_all_prompt_keys_exist(self):
        """All 7 prompt keys must be defined."""
        expected_keys = {
            "task_analysis",
            "solution_quality",
            "what_worked",
            "what_didnt_work",
            "improvement",
            "knowledge_gap",
            "transferable_lessons",
        }
        assert set(REFLECTION_PROMPTS.keys()) == expected_keys

    def test_prompts_have_placeholders(self):
        """Prompts should have {task}, {solution} placeholders."""
        for key, prompt in REFLECTION_PROMPTS.items():
            assert "{task}" in prompt, f"Prompt '{key}' missing {{task}}"
            assert "{solution}" in prompt, f"Prompt '{key}' missing {{solution}}"

    def test_system_prompt_not_empty(self):
        """System prompt should be non-empty."""
        assert len(REFLECTION_SYSTEM_PROMPT) > 50
        assert "trading" in REFLECTION_SYSTEM_PROMPT.lower()


# =============================================================================
# Test LLMReflectionProvider
# =============================================================================


class TestLLMReflectionProvider:
    """Test LLMReflectionProvider."""

    def test_init_default_provider(self):
        """Default provider is deepseek."""
        provider = LLMReflectionProvider()
        assert provider.provider_name == "deepseek"
        assert provider._call_count == 0
        assert provider._error_count == 0

    def test_init_qwen_provider(self):
        """Can initialize with qwen."""
        provider = LLMReflectionProvider("qwen")
        assert provider.provider_name == "qwen"

    def test_init_perplexity_provider(self):
        """Can initialize with perplexity."""
        provider = LLMReflectionProvider("perplexity")
        assert provider.provider_name == "perplexity"

    def test_init_unknown_provider_raises(self):
        """Unknown provider should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMReflectionProvider("gpt4")

    def test_provider_configs_exist(self):
        """All 3 providers must have configs."""
        assert "deepseek" in LLMReflectionProvider.PROVIDER_CONFIGS
        assert "qwen" in LLMReflectionProvider.PROVIDER_CONFIGS
        assert "perplexity" in LLMReflectionProvider.PROVIDER_CONFIGS

    def test_provider_configs_have_required_fields(self):
        """Each config must have model, temperature, max_tokens."""
        for name, config in LLMReflectionProvider.PROVIDER_CONFIGS.items():
            assert "model" in config, f"{name} missing model"
            assert "temperature" in config, f"{name} missing temperature"
            assert "max_tokens" in config, f"{name} missing max_tokens"
            assert "system_prompt" in config, f"{name} missing system_prompt"
            assert "specialization" in config, f"{name} missing specialization"

    def test_get_system_prompt_default(self):
        """System prompt includes specialization."""
        provider = LLMReflectionProvider("deepseek")
        prompt = provider.get_system_prompt()
        assert "quantitative" in prompt.lower()

    def test_get_system_prompt_custom(self):
        """Custom system prompt overrides default."""
        custom = "My custom prompt"
        provider = LLMReflectionProvider("deepseek", custom_system_prompt=custom)
        assert provider.get_system_prompt() == custom

    def test_build_reflection_prompt(self):
        """Build prompt includes task, solution, question."""
        provider = LLMReflectionProvider()
        prompt = provider._build_reflection_prompt("What worked?", "Test strategy", "RSI parameters")
        assert "Test strategy" in prompt
        assert "RSI parameters" in prompt
        assert "What worked?" in prompt

    def test_get_stats_initial(self):
        """Initial stats should be zeros."""
        provider = LLMReflectionProvider()
        stats = provider.get_stats()
        assert stats["provider"] == "deepseek"
        assert stats["total_calls"] == 0
        assert stats["errors"] == 0
        assert stats["error_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_reflection_fn_returns_callable(self):
        """get_reflection_fn returns async callable."""
        provider = LLMReflectionProvider(api_key="test-key")
        with patch("backend.agents.llm.connections.LLMClientFactory.create") as mock_create:
            mock_client = AsyncMock()
            mock_create.return_value = mock_client
            fn = await provider.get_reflection_fn()
            assert callable(fn)

    @pytest.mark.asyncio
    async def test_reflection_fn_calls_llm(self):
        """Reflection function should call LLM and return response."""
        provider = LLMReflectionProvider(api_key="test-key")

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "Quality: 8/10. Strong risk-adjusted returns."
        mock_client.chat = AsyncMock(return_value=mock_response)

        with patch("backend.agents.llm.connections.LLMClientFactory.create") as mock_create:
            mock_create.return_value = mock_client
            fn = await provider.get_reflection_fn()
            result = await fn("Rate quality", "Test strategy", "RSI(21)")

        assert "Quality: 8/10" in result
        assert provider._call_count == 1

    @pytest.mark.asyncio
    async def test_reflection_fn_handles_error(self):
        """Reflection function should handle LLM errors gracefully."""
        provider = LLMReflectionProvider(api_key="test-key")

        mock_client = AsyncMock()
        mock_client.chat = AsyncMock(side_effect=Exception("API error"))

        with patch("backend.agents.llm.connections.LLMClientFactory.create") as mock_create:
            mock_create.return_value = mock_client
            fn = await provider.get_reflection_fn()
            result = await fn("Rate quality", "Test", "Solution")

        assert "Fallback" in result or "unavailable" in result
        assert provider._error_count == 1

    @pytest.mark.asyncio
    async def test_reflection_fn_no_client_fallback(self):
        """No client available → fallback response."""
        provider = LLMReflectionProvider()
        # Don't set up client (no API key in test env)
        provider._client = None

        with patch("backend.security.key_manager.KeyManager") as mock_km:
            mock_km.return_value.get_key.return_value = None
            fn = await provider.get_reflection_fn()
            result = await fn("Rate quality", "Test", "Solution")

        assert "Heuristic" in result or "no LLM" in result

    @pytest.mark.asyncio
    async def test_close(self):
        """Close should cleanup client."""
        provider = LLMReflectionProvider()
        provider._client = AsyncMock()
        await provider.close()
        assert provider._client is None


# =============================================================================
# Test LLMSelfReflectionEngine
# =============================================================================


class TestLLMSelfReflectionEngine:
    """Test LLMSelfReflectionEngine."""

    def test_init_default(self):
        """Default initialization."""
        engine = LLMSelfReflectionEngine(api_key="test-key")
        assert engine._active_provider == "deepseek"
        assert engine._fallback_providers == []

    def test_init_with_fallbacks(self):
        """Initialization with fallback providers."""
        engine = LLMSelfReflectionEngine(
            provider_name="deepseek",
            fallback_providers=["qwen", "perplexity"],
            api_key="test-key",
        )
        assert engine._fallback_providers == ["qwen", "perplexity"]

    def test_is_subclass_of_self_reflection_engine(self):
        """Must be subclass of SelfReflectionEngine."""
        from backend.agents.self_improvement.self_reflection import (
            SelfReflectionEngine,
        )

        engine = LLMSelfReflectionEngine(api_key="test-key")
        assert isinstance(engine, SelfReflectionEngine)

    @pytest.mark.asyncio
    async def test_reflect_on_task_with_mock_llm(self):
        """reflect_on_task should use LLM when available."""
        engine = LLMSelfReflectionEngine(api_key="test-key")

        # Mock the provider to return a reflection function
        async def mock_reflect(prompt, task, solution):
            if "quality" in prompt.lower():
                return "Quality: 7/10. Decent risk-adjusted returns."
            return "Analysis complete. Systematic approach worked well."

        engine.reflection_fn = mock_reflect

        result = await engine.reflect_on_task(
            task="Backtest RSI strategy",
            solution="RSI(21, 70, 25)",
            outcome={"success": True, "sharpe_ratio": 1.2},
        )

        assert result is not None
        assert result.quality_score > 0
        assert result.task == "Backtest RSI strategy"

    @pytest.mark.asyncio
    async def test_reflect_on_strategy_convenience(self):
        """reflect_on_strategy should format and call reflect_on_task."""
        engine = LLMSelfReflectionEngine(api_key="test-key")

        async def mock_reflect(prompt, task, solution):
            return "Quality: 8/10. Strong strategy with good risk management."

        engine.reflection_fn = mock_reflect

        result = await engine.reflect_on_strategy(
            strategy_name="RSI_v1",
            strategy_type="rsi",
            strategy_params={"period": 21, "overbought": 70},
            backtest_metrics={
                "sharpe_ratio": 1.5,
                "win_rate": 0.55,
                "max_drawdown_pct": 12.0,
            },
        )

        assert result is not None
        assert "RSI_v1" in result.task

    @pytest.mark.asyncio
    async def test_batch_reflect(self):
        """batch_reflect should process multiple tasks."""
        engine = LLMSelfReflectionEngine(api_key="test-key")

        async def mock_reflect(prompt, task, solution):
            return "Quality: 7/10. Good overall."

        engine.reflection_fn = mock_reflect

        tasks = [
            {
                "task": "Backtest RSI",
                "solution": "RSI(14)",
                "outcome": {"success": True},
            },
            {
                "task": "Backtest MACD",
                "solution": "MACD(12,26,9)",
                "outcome": {"success": False},
            },
        ]

        results = await engine.batch_reflect(tasks)
        assert len(results) == 2
        assert results[0].task == "Backtest RSI"
        assert results[1].task == "Backtest MACD"

    def test_get_provider_stats(self):
        """get_provider_stats should include provider and engine stats."""
        engine = LLMSelfReflectionEngine(api_key="test-key")
        stats = engine.get_provider_stats()
        assert "primary" in stats
        assert "engine_stats" in stats
        assert "active_provider" in stats

    @pytest.mark.asyncio
    async def test_close_cleanup(self):
        """close should cleanup provider."""
        engine = LLMSelfReflectionEngine(api_key="test-key")
        engine._provider._client = AsyncMock()
        await engine.close()
        assert engine._provider._client is None
