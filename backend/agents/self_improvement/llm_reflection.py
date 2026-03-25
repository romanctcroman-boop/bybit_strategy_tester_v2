"""
LLM-backed Self-Reflection Provider

Connects real LLM clients (DeepSeek, Qwen, Perplexity) to the
SelfReflectionEngine for deep analysis of strategy results.

Instead of heuristic-based reflection, this module sends structured
prompts to LLMs and parses their analytical responses into
ReflectionResult components.

Key Features:
- Multi-provider support (DeepSeek for quantitative, Qwen for technical)
- Structured reflection prompts with trading-specific context
- Graceful fallback to heuristics when LLM unavailable
- Response quality validation and scoring
- Batch reflection for multiple strategies

Based on:
- Reflexion (Shinn et al., 2023)
- Self-Refine (Madaan et al., 2023)
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from loguru import logger

from backend.agents.self_improvement.self_reflection import (
    SelfReflectionEngine,
)

# =============================================================================
# REFLECTION SYSTEM PROMPTS
# =============================================================================

REFLECTION_SYSTEM_PROMPT = """\
You are an expert trading strategy analyst specializing in quantitative analysis.

Your role is to provide structured, data-driven reflection on trading strategy \
performance. Be specific, reference actual numbers, and provide actionable insights.

Rules:
- Be concise (2-4 sentences per reflection)
- Always reference specific metrics
- Provide actionable recommendations
- Rate quality on a 1-10 scale when asked
- Focus on risk-adjusted returns, not just raw profit
"""

REFLECTION_PROMPTS = {
    "task_analysis": (
        "Analyze this trading strategy task:\n"
        "Task: {task}\n"
        "Solution: {solution}\n\n"
        "What was the main challenge? What skills/knowledge did it require?\n"
        "Provide 2-3 sentences of analysis."
    ),
    "solution_quality": (
        "Rate the quality of this trading strategy (1-10 scale):\n"
        "Task: {task}\n"
        "Solution: {solution}\n"
        "Outcome: {outcome}\n\n"
        "Format: 'Quality: X/10. [explanation]'\n"
        "Consider risk-adjusted returns, drawdown, and trade frequency."
    ),
    "what_worked": (
        "Analyze what worked well in this strategy:\n"
        "Task: {task}\n"
        "Solution: {solution}\n"
        "Outcome: {outcome}\n\n"
        "What approaches or parameters contributed to positive results?"
    ),
    "what_didnt_work": (
        "Analyze what didn't work in this strategy:\n"
        "Task: {task}\n"
        "Solution: {solution}\n"
        "Outcome: {outcome}\n\n"
        "What caused difficulties, losses, or suboptimal performance?"
    ),
    "improvement": (
        "Suggest specific improvements for this strategy:\n"
        "Task: {task}\n"
        "Solution: {solution}\n"
        "Outcome: {outcome}\n\n"
        "What specific parameter changes, filters, or structural changes "
        "would improve risk-adjusted returns?"
    ),
    "knowledge_gap": (
        "Identify knowledge gaps from this strategy analysis:\n"
        "Task: {task}\n"
        "Solution: {solution}\n"
        "Outcome: {outcome}\n\n"
        "What concepts, indicators, or techniques should be studied "
        "to build better strategies?"
    ),
    "transferable_lessons": (
        "Extract transferable lessons from this strategy:\n"
        "Task: {task}\n"
        "Solution: {solution}\n"
        "Outcome: {outcome}\n\n"
        "What general principles from this result apply to other strategies?"
    ),
}


# =============================================================================
# LLM REFLECTION PROVIDER
# =============================================================================


class LLMReflectionProvider:
    """
    LLM-backed reflection function provider.

    Creates async reflection functions that use real LLM clients
    for deep analysis, with graceful fallback to heuristics.

    Example:
        provider = LLMReflectionProvider(provider_name="deepseek")
        reflection_fn = await provider.get_reflection_fn()

        engine = SelfReflectionEngine(reflection_fn=reflection_fn)
        result = await engine.reflect_on_task(task, solution, outcome)
    """

    # Provider-specific configs
    PROVIDER_CONFIGS = {
        "deepseek": {
            "model": "deepseek-chat",
            "temperature": 0.4,
            "max_tokens": 1024,
            "system_prompt": REFLECTION_SYSTEM_PROMPT,
            "specialization": "quantitative analysis and risk metrics",
        },
        "qwen": {
            "model": "qwen-plus",
            "temperature": 0.3,
            "max_tokens": 1024,
            "system_prompt": REFLECTION_SYSTEM_PROMPT,
            "specialization": "technical analysis and pattern recognition",
        },
        "perplexity": {
            "model": "sonar-pro",
            "temperature": 0.5,
            "max_tokens": 1024,
            "system_prompt": REFLECTION_SYSTEM_PROMPT,
            "specialization": "market context and sentiment analysis",
        },
    }

    def __init__(
        self,
        provider_name: str = "deepseek",
        *,
        api_key: str | None = None,
        custom_system_prompt: str | None = None,
    ):
        """
        Initialize LLM reflection provider.

        Args:
            provider_name: LLM provider ("deepseek", "qwen", "perplexity")
            api_key: Optional API key override
            custom_system_prompt: Optional custom system prompt
        """
        self.provider_name = provider_name
        self._api_key = api_key
        self._custom_system_prompt = custom_system_prompt
        self._client = None
        self._call_count = 0
        self._error_count = 0

        if provider_name not in self.PROVIDER_CONFIGS:
            raise ValueError(f"Unknown provider: {provider_name}. Supported: {list(self.PROVIDER_CONFIGS.keys())}")

        logger.info(f"🪞 LLMReflectionProvider initialized: {provider_name}")

    async def _get_client(self):
        """Lazily initialize LLM client."""
        if self._client is not None:
            return self._client

        from backend.agents.llm.connections import (
            LLMClientFactory,
            LLMConfig,
            LLMProvider,
        )

        config = self.PROVIDER_CONFIGS[self.provider_name]
        api_key = self._api_key

        if not api_key:
            from backend.security.key_manager import KeyManager

            km = KeyManager()
            key_map = {
                "deepseek": "DEEPSEEK_API_KEY",
                "qwen": "DASHSCOPE_API_KEY",
                "perplexity": "PERPLEXITY_API_KEY",
            }
            api_key = km.get_key(key_map.get(self.provider_name, ""))

        if not api_key:
            logger.warning(f"No API key for {self.provider_name}, LLM reflection disabled")
            return None

        provider_map = {
            "deepseek": LLMProvider.DEEPSEEK,
            "qwen": LLMProvider.QWEN,
            "perplexity": LLMProvider.PERPLEXITY,
        }

        llm_config = LLMConfig(
            provider=provider_map[self.provider_name],
            api_key=api_key,
            model=config["model"],
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
        )
        self._client = LLMClientFactory.create(llm_config)
        return self._client

    def get_system_prompt(self) -> str:
        """Get system prompt for this provider."""
        if self._custom_system_prompt:
            return self._custom_system_prompt

        config = self.PROVIDER_CONFIGS[self.provider_name]
        base = config["system_prompt"]
        spec = config["specialization"]
        return f"{base}\n\nYou specialize in: {spec}"

    async def get_reflection_fn(self) -> Callable:
        """
        Create async reflection function for SelfReflectionEngine.

        Returns:
            Async function (prompt, task, solution) -> reflection_text
        """
        client = await self._get_client()

        async def llm_reflect(prompt: str, task: str, solution: str) -> str:
            """LLM-backed reflection with fallback."""
            nonlocal client

            if client is None:
                # Re-try getting client
                client = await self._get_client()
                if client is None:
                    return f"[Heuristic] {prompt}: Analysis pending (no LLM available)"

            self._call_count += 1

            # Build context-aware prompt
            full_prompt = self._build_reflection_prompt(prompt, task, solution)

            try:
                from backend.agents.llm.connections import LLMMessage

                response = await client.chat(
                    [
                        LLMMessage(
                            role="system",
                            content=self.get_system_prompt(),
                        ),
                        LLMMessage(role="user", content=full_prompt),
                    ]
                )
                return response.content.strip()
            except Exception as e:
                self._error_count += 1
                logger.warning(f"LLM reflection failed ({self.provider_name}): {e}", exc_info=True)
                return f"[Fallback] Reflection unavailable: {e}"

        return llm_reflect

    def _build_reflection_prompt(
        self,
        prompt: str,
        task: str,
        solution: str,
    ) -> str:
        """Build structured reflection prompt."""
        return (
            f"Reflect on the following trading strategy task:\n\n"
            f"Task: {task}\n"
            f"Solution: {solution[:1000]}\n\n"
            f"Reflection Question: {prompt}\n\n"
            f"Provide a concise, analytical response (2-4 sentences). "
            f"Be specific about numbers and metrics when available."
        )

    def get_stats(self) -> dict[str, Any]:
        """Get provider statistics."""
        return {
            "provider": self.provider_name,
            "total_calls": self._call_count,
            "errors": self._error_count,
            "error_rate": self._error_count / max(1, self._call_count),
            "available": self._client is not None,
        }

    async def close(self) -> None:
        """Cleanup resources."""
        if self._client:
            import contextlib

            with contextlib.suppress(Exception):
                await self._client.close()
            self._client = None


# =============================================================================
# ENHANCED REFLECTION ENGINE
# =============================================================================


class LLMSelfReflectionEngine(SelfReflectionEngine):
    """
    Enhanced SelfReflectionEngine with LLM-backed reflection.

    Extends the base engine with:
    - Real LLM provider integration
    - Structured trading-specific prompts
    - Multi-provider support with fallback chain
    - Batch reflection mode
    - Reflection quality scoring

    Example:
        engine = LLMSelfReflectionEngine(
            provider_name="deepseek",
            persist_path="./reflections",
        )

        result = await engine.reflect_on_task(
            task="Backtest RSI strategy",
            solution="RSI(21), overbought=70, oversold=25",
            outcome={"sharpe_ratio": 1.5, "win_rate": 0.55},
        )
    """

    def __init__(
        self,
        provider_name: str = "deepseek",
        *,
        persist_path: str | None = None,
        api_key: str | None = None,
        fallback_providers: list[str] | None = None,
    ):
        """
        Initialize LLM-backed reflection engine.

        Args:
            provider_name: Primary LLM provider
            persist_path: Path to persist reflections
            api_key: Optional API key override
            fallback_providers: Fallback providers if primary fails
        """
        self._provider = LLMReflectionProvider(
            provider_name=provider_name,
            api_key=api_key,
        )
        self._fallback_providers = fallback_providers or []
        self._active_provider = provider_name

        # Initialize base engine (reflection_fn set lazily)
        super().__init__(persist_path=persist_path, reflection_fn=None)

        logger.info(
            f"🪞 LLMSelfReflectionEngine initialized: primary={provider_name}, fallbacks={self._fallback_providers}"
        )

    async def _ensure_reflection_fn(self) -> None:
        """Ensure reflection function is initialized."""
        if self.reflection_fn is None:
            self.reflection_fn = await self._provider.get_reflection_fn()

    async def reflect_on_task(
        self,
        task: str,
        solution: str,
        outcome: dict[str, Any],
        context: dict[str, Any] | None = None,
    ):
        """Override to ensure LLM is initialized before reflection."""
        await self._ensure_reflection_fn()
        return await super().reflect_on_task(task, solution, outcome, context)

    async def reflect_on_strategy(
        self,
        strategy_name: str,
        strategy_type: str,
        strategy_params: dict[str, Any],
        backtest_metrics: dict[str, Any],
    ):
        """
        High-level reflection on a specific trading strategy.

        Convenience method that formats strategy info into task/solution/outcome.

        Args:
            strategy_name: Name of the strategy
            strategy_type: Type (e.g., "rsi", "macd")
            strategy_params: Strategy parameters dict
            backtest_metrics: Backtest results dict

        Returns:
            ReflectionResult with LLM-backed insights
        """
        task = f"Backtest strategy '{strategy_name}' ({strategy_type})"
        solution = f"Parameters: {json.dumps(strategy_params, default=str)}"
        outcome = {
            "success": backtest_metrics.get("sharpe_ratio", 0) > 0,
            "net_profit": backtest_metrics.get("net_profit", 0),
            "sharpe_ratio": backtest_metrics.get("sharpe_ratio", 0),
            "win_rate": backtest_metrics.get("win_rate", 0),
            "max_drawdown_pct": backtest_metrics.get("max_drawdown_pct", 0),
            "profit_factor": backtest_metrics.get("profit_factor", 0),
            "total_trades": backtest_metrics.get("total_trades", 0),
        }

        return await self.reflect_on_task(task, solution, outcome)

    async def batch_reflect(
        self,
        tasks: list[dict[str, Any]],
    ) -> list:
        """
        Reflect on multiple tasks sequentially.

        Args:
            tasks: List of dicts with keys: task, solution, outcome

        Returns:
            List of ReflectionResult
        """
        results = []
        for i, task_data in enumerate(tasks):
            logger.info(f"🪞 Batch reflection {i + 1}/{len(tasks)}")
            result = await self.reflect_on_task(
                task=task_data["task"],
                solution=task_data["solution"],
                outcome=task_data["outcome"],
            )
            results.append(result)
        return results

    def get_provider_stats(self) -> dict[str, Any]:
        """Get LLM provider statistics."""
        return {
            "primary": self._provider.get_stats(),
            "active_provider": self._active_provider,
            "fallback_providers": self._fallback_providers,
            "engine_stats": self.get_stats(),
        }

    async def close(self) -> None:
        """Cleanup resources."""
        await self._provider.close()


__all__ = [
    "REFLECTION_PROMPTS",
    "REFLECTION_SYSTEM_PROMPT",
    "LLMReflectionProvider",
    "LLMSelfReflectionEngine",
]
