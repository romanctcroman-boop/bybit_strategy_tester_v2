"""
Prompt Engineer for LLM Trading Strategy Generation.

Provides high-level API for creating contextual prompts:
- Strategy generation with market context and agent specialization
- Market analysis prompts
- Optimization suggestion prompts
- Strategy validation prompts

Example:
    from backend.agents.prompts import PromptEngineer, MarketContextBuilder

    builder = MarketContextBuilder()
    context = builder.build_context("BTCUSDT", "15", df)

    engineer = PromptEngineer()
    prompt = engineer.create_strategy_prompt(
        context=context,
        platform_config={"leverage": 10, "commission": 0.0007},
        agent_name="deepseek",
    )
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from backend.agents.prompts.context_builder import MarketContext
from backend.agents.prompts.templates import (
    AGENT_SPECIALIZATIONS,
    MARKET_ANALYSIS_TEMPLATE,
    OPTIMIZATION_SUGGESTIONS_TEMPLATE,
    STRATEGY_EXAMPLE_MACD_TREND,
    STRATEGY_EXAMPLE_RSI_MEAN_REVERSION,
    STRATEGY_GENERATION_TEMPLATE,
    STRATEGY_VALIDATION_TEMPLATE,
)


class PromptEngineer:
    """
    Prompt engineering system for LLM trading agents.

    Creates contextual, specialized prompts for different tasks:
    - Strategy generation (with market context + agent role)
    - Market analysis
    - Optimization suggestions (based on backtest results)
    - Strategy validation

    Each prompt type supports agent specialization (DeepSeek/Qwen/Perplexity)
    and few-shot examples for better response quality.
    """

    def create_strategy_prompt(
        self,
        context: MarketContext,
        platform_config: dict[str, Any],
        agent_name: str = "deepseek",
        include_examples: bool = True,
    ) -> str:
        """
        Create a complete strategy generation prompt.

        Args:
            context: MarketContext from MarketContextBuilder
            platform_config: Platform settings (leverage, commission, etc.)
            agent_name: Agent name for specialization ("deepseek", "qwen", "perplexity")
            include_examples: Whether to append few-shot examples

        Returns:
            Complete prompt string ready for LLM API call
        """
        spec = AGENT_SPECIALIZATIONS.get(agent_name, AGENT_SPECIALIZATIONS["deepseek"])

        # Merge context with platform config
        prompt_vars = context.to_prompt_vars()
        prompt_vars.update(
            {
                "specialization": spec["description"],
                "position_type": platform_config.get("position_type", "both"),
                "leverage": platform_config.get("leverage", 10),
                "commission": platform_config.get("commission", 0.07),
                "initial_capital": platform_config.get("initial_capital", 10000),
                "start_date": platform_config.get("start_date", "2025-01-01"),
                "end_date": platform_config.get("end_date", "2025-06-01"),
            }
        )

        prompt = STRATEGY_GENERATION_TEMPLATE.format(**prompt_vars)

        if include_examples:
            prompt += "\n\nEXAMPLE STRATEGIES FOR REFERENCE:\n"
            # Choose example based on market regime
            if context.market_regime in ("trending_up", "trending_down"):
                prompt += STRATEGY_EXAMPLE_MACD_TREND
            else:
                prompt += STRATEGY_EXAMPLE_RSI_MEAN_REVERSION

        logger.debug(
            f"Created strategy prompt for {agent_name} "
            f"({context.symbol}/{context.timeframe}, regime={context.market_regime})"
        )

        return prompt

    def create_market_analysis_prompt(
        self,
        context: MarketContext,
        start_date: str = "",
        end_date: str = "",
    ) -> str:
        """
        Create a market analysis prompt.

        Args:
            context: MarketContext from MarketContextBuilder
            start_date: Analysis period start
            end_date: Analysis period end

        Returns:
            Market analysis prompt string
        """
        prompt_vars = context.to_prompt_vars()
        prompt_vars.update(
            {
                "start_date": start_date,
                "end_date": end_date,
            }
        )

        return MARKET_ANALYSIS_TEMPLATE.format(**prompt_vars)

    def create_optimization_prompt(
        self,
        strategy_name: str,
        strategy_type: str,
        strategy_params: dict[str, Any],
        backtest_results: dict[str, Any],
        issues: list[str] | None = None,
    ) -> str:
        """
        Create an optimization suggestions prompt based on backtest results.

        Args:
            strategy_name: Name of the strategy
            strategy_type: Type (e.g., "RSI", "MACD")
            strategy_params: Current parameter values
            backtest_results: Backtest metrics dict
            issues: List of identified issues/problems

        Returns:
            Optimization prompt string
        """
        issues_text = "\n".join(f"- {issue}" for issue in (issues or []))
        if not issues_text:
            issues_text = self._auto_detect_issues(backtest_results)

        prompt_vars = {
            "strategy_name": strategy_name,
            "strategy_type": strategy_type,
            "strategy_params": str(strategy_params),
            "net_pnl": backtest_results.get("net_pnl", 0),
            "total_return_pct": backtest_results.get("total_return_pct", 0),
            "sharpe_ratio": backtest_results.get("sharpe_ratio", 0),
            "max_drawdown_pct": backtest_results.get("max_drawdown_pct", 0),
            "win_rate": backtest_results.get("win_rate", 0),
            "profit_factor": backtest_results.get("profit_factor", 0),
            "total_trades": backtest_results.get("total_trades", 0),
            "avg_win": backtest_results.get("avg_win", 0),
            "avg_loss": backtest_results.get("avg_loss", 0),
            "issues": issues_text,
        }

        return OPTIMIZATION_SUGGESTIONS_TEMPLATE.format(**prompt_vars)

    def create_validation_prompt(
        self,
        strategy_json: str,
        commission: float = 0.0007,
        leverage: int = 10,
    ) -> str:
        """
        Create a strategy validation prompt.

        Args:
            strategy_json: JSON string of the strategy
            commission: Commission rate
            leverage: Leverage setting

        Returns:
            Validation prompt string
        """
        return STRATEGY_VALIDATION_TEMPLATE.format(
            strategy_json=strategy_json,
            commission=commission * 100,  # Convert to percentage
            leverage=leverage,
        )

    def get_system_message(self, agent_name: str = "deepseek") -> str:
        """
        Get system message for LLM API call based on agent specialization.

        Args:
            agent_name: Agent name

        Returns:
            System message string
        """
        spec = AGENT_SPECIALIZATIONS.get(agent_name, AGENT_SPECIALIZATIONS["deepseek"])
        strengths = ", ".join(spec.get("strengths", []))

        return (
            f"You are a {spec['description']}. "
            f"Your strengths are: {strengths}. "
            f"Your trading style is {spec.get('style', 'balanced')}. "
            "Always respond with valid JSON when asked for structured output. "
            "Be specific with parameter values — avoid generic defaults."
        )

    def _auto_detect_issues(self, results: dict[str, Any]) -> str:
        """Auto-detect issues from backtest results."""
        issues = []

        sharpe = results.get("sharpe_ratio", 0)
        if sharpe < 0:
            issues.append("Negative Sharpe Ratio — strategy is losing money on risk-adjusted basis")
        elif sharpe < 1.0:
            issues.append(f"Low Sharpe Ratio ({sharpe:.2f}) — below acceptable threshold of 1.0")

        max_dd = results.get("max_drawdown_pct", 0)
        if max_dd > 20:
            issues.append(f"High Max Drawdown ({max_dd:.1f}%) — exceeds 20% risk tolerance")
        elif max_dd > 15:
            issues.append(f"Elevated Max Drawdown ({max_dd:.1f}%) — approaching 15% limit")

        win_rate = results.get("win_rate", 0)
        if win_rate < 0.4:
            issues.append(f"Low Win Rate ({win_rate:.0%}) — too many losing trades")

        pf = results.get("profit_factor", 0)
        if pf < 1.0:
            issues.append(f"Profit Factor below 1.0 ({pf:.2f}) — losses exceed gains")

        total_trades = results.get("total_trades", 0)
        if total_trades < 30:
            issues.append(f"Insufficient trades ({total_trades}) — need 30+ for statistical significance")

        if not issues:
            issues.append("No major issues detected. Consider fine-tuning for better risk-adjusted returns.")

        return "\n".join(f"- {issue}" for issue in issues)
