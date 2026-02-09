"""
Trading Strategy LangGraph Pipeline.

Builds an AgentGraph that implements the full AI strategy generation cycle:

    analyze_market ──► generate_strategies ──► parse_responses
         │                                          │
         │                                          ▼
         │                                    select_best
         │                                          │
         │                              ┌───────────┤
         │                              ▼           ▼
         │                          backtest     report
         │                              │
         │                              ▼
         └───────────────────────── evaluate ──► END

Uses StrategyController components but in a graph-based execution model
for better observability, retry logic, and conditional routing.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger

from backend.agents.langgraph_orchestrator import (
    AgentGraph,
    AgentNode,
    AgentState,
    FunctionAgent,
    register_graph,
)
from backend.agents.prompts.context_builder import MarketContextBuilder
from backend.agents.prompts.prompt_engineer import PromptEngineer
from backend.agents.prompts.response_parser import ResponseParser

# =============================================================================
# GRAPH NODES
# =============================================================================


class AnalyzeMarketNode(AgentNode):
    """Node 1: Analyze market data and build MarketContext."""

    def __init__(self) -> None:
        super().__init__(
            name="analyze_market",
            description="Analyze OHLCV data and detect market regime",
            timeout=30.0,
        )
        self._builder = MarketContextBuilder()

    async def execute(self, state: AgentState) -> AgentState:
        symbol = state.context.get("symbol", "BTCUSDT")
        timeframe = state.context.get("timeframe", "15")
        df = state.context.get("df")

        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            state.add_error(self.name, ValueError("No OHLCV data in state.context['df']"))
            return state

        context = self._builder.build_context(symbol, timeframe, df)
        state.set_result(
            self.name,
            {
                "market_context": context,
                "regime": context.market_regime,
                "trend": context.trend_direction,
                "current_price": context.current_price,
            },
        )
        state.add_message(
            "system",
            f"Market analysis: {symbol} {timeframe} — {context.market_regime}, trend={context.trend_direction}",
            self.name,
        )
        logger.info(f"📊 [Graph] Market: {symbol} regime={context.market_regime}")
        return state


class GenerateStrategiesNode(AgentNode):
    """Node 2: Generate strategy proposals from LLM agents."""

    def __init__(self) -> None:
        super().__init__(
            name="generate_strategies",
            description="Call LLM agents to generate strategy proposals",
            timeout=120.0,
            retry_count=1,
            retry_delay=2.0,
        )
        self._prompt_engineer = PromptEngineer()

    async def execute(self, state: AgentState) -> AgentState:
        market_result = state.get_result("analyze_market")
        if not market_result:
            state.add_error(self.name, ValueError("No market analysis result"))
            return state

        market_context = market_result["market_context"]
        agents = state.context.get("agents", ["deepseek"])
        platform_config = state.context.get(
            "platform_config",
            {
                "exchange": "Bybit",
                "commission": 0.0007,
                "max_leverage": 100,
            },
        )

        responses: list[dict[str, Any]] = []

        for agent_name in agents:
            prompt = self._prompt_engineer.create_strategy_prompt(
                context=market_context,
                platform_config=platform_config,
                agent_name=agent_name,
                include_examples=True,
            )
            system_msg = self._prompt_engineer.get_system_message(agent_name)

            try:
                response_text = await self._call_llm(agent_name, prompt, system_msg)
                if response_text:
                    responses.append(
                        {
                            "agent": agent_name,
                            "response": response_text,
                        }
                    )
            except Exception as e:
                logger.warning(f"[Graph] LLM call failed for {agent_name}: {e}")

        state.set_result(self.name, {"responses": responses})
        state.add_message(
            "system",
            f"Generated {len(responses)} responses from {len(agents)} agents",
            self.name,
        )
        return state

    async def _call_llm(self, agent_name: str, prompt: str, system_msg: str) -> str | None:
        """Call LLM using the connections module."""
        from backend.agents.llm.connections import (
            LLMConfig,
            LLMMessage,
            LLMProvider,
            create_llm_client,
        )
        from backend.security.key_manager import get_key_manager

        km = get_key_manager()

        provider_map = {
            "deepseek": (LLMProvider.DEEPSEEK, "DEEPSEEK_API_KEY", "deepseek-chat", 0.7),
            "qwen": (LLMProvider.QWEN, "QWEN_API_KEY", "qwen-plus", 0.4),
            "perplexity": (LLMProvider.PERPLEXITY, "PERPLEXITY_API_KEY", "llama-3.1-sonar-small-128k-online", 0.7),
        }

        if agent_name not in provider_map:
            return None

        provider, key_name, model, temp = provider_map[agent_name]
        api_key = km.get_decrypted_key(key_name)
        if not api_key:
            return None

        config = LLMConfig(provider=provider, api_key=api_key, model=model, temperature=temp, max_tokens=4096)
        client = create_llm_client(config)
        try:
            messages = [
                LLMMessage(role="system", content=system_msg),
                LLMMessage(role="user", content=prompt),
            ]
            response = await client.chat(messages)
            return response.content
        finally:
            await client.close()


class ParseResponsesNode(AgentNode):
    """Node 3: Parse LLM responses into StrategyDefinition objects."""

    def __init__(self) -> None:
        super().__init__(
            name="parse_responses",
            description="Parse LLM text responses into structured strategies",
            timeout=15.0,
        )
        self._parser = ResponseParser()

    async def execute(self, state: AgentState) -> AgentState:
        gen_result = state.get_result("generate_strategies")
        if not gen_result:
            state.add_error(self.name, ValueError("No generation results"))
            return state

        responses = gen_result.get("responses", [])
        proposals = []

        for item in responses:
            strategy = self._parser.parse_strategy(
                item["response"],
                agent_name=item["agent"],
            )
            if strategy:
                validation = self._parser.validate_strategy(strategy)
                proposals.append(
                    {
                        "strategy": strategy,
                        "validation": validation,
                        "agent": item["agent"],
                    }
                )

        state.set_result(self.name, {"proposals": proposals})
        state.add_message(
            "system",
            f"Parsed {len(proposals)} valid strategies from {len(responses)} responses",
            self.name,
        )
        return state


class SelectBestNode(AgentNode):
    """Node 4: Select the best strategy from proposals."""

    def __init__(self) -> None:
        super().__init__(
            name="select_best",
            description="Select best strategy by scoring proposals",
            timeout=10.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        parse_result = state.get_result("parse_responses")
        if not parse_result:
            state.add_error(self.name, ValueError("No parsed proposals"))
            return state

        proposals = parse_result.get("proposals", [])
        if not proposals:
            state.add_error(self.name, ValueError("No valid proposals to select from"))
            return state

        # Score and rank
        scored = []
        for p in proposals:
            score = p["validation"].quality_score
            # Bonus for having both entry and exit conditions
            if p["strategy"].exit_conditions:
                score += 0.1
            if p["strategy"].filters:
                score += 0.05
            scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]

        state.set_result(
            self.name,
            {
                "selected_strategy": best["strategy"],
                "selected_validation": best["validation"],
                "selected_agent": best["agent"],
                "candidates_count": len(proposals),
            },
        )
        state.context["selected_strategy"] = best["strategy"]

        logger.info(
            f"🏆 [Graph] Selected '{best['strategy'].strategy_name}' from {best['agent']} (score={scored[0][0]:.2f})"
        )
        return state


class BacktestNode(AgentNode):
    """Node 5 (optional): Run backtest on selected strategy."""

    def __init__(self) -> None:
        super().__init__(
            name="backtest",
            description="Backtest the selected strategy",
            timeout=120.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        from backend.agents.integration.backtest_bridge import BacktestBridge

        select_result = state.get_result("select_best")
        if not select_result:
            state.add_error(self.name, ValueError("No selected strategy"))
            return state

        strategy = select_result["selected_strategy"]
        df = state.context.get("df")
        symbol = state.context.get("symbol", "BTCUSDT")
        timeframe = state.context.get("timeframe", "15")

        bridge = BacktestBridge()
        metrics = await bridge.run_strategy(
            strategy=strategy,
            symbol=symbol,
            timeframe=timeframe,
            df=df,
            initial_capital=state.context.get("initial_capital", 10000),
            leverage=state.context.get("leverage", 1),
        )

        state.set_result(self.name, {"metrics": metrics})
        state.add_message(
            "system",
            f"Backtest complete: {metrics.get('total_trades', 0)} trades, Sharpe={metrics.get('sharpe_ratio', 0):.2f}",
            self.name,
        )
        return state


def _report_node(state: AgentState) -> AgentState:
    """Final node: compile all results into a report."""
    report = {
        "market_analysis": state.get_result("analyze_market"),
        "proposals_count": len((state.get_result("parse_responses") or {}).get("proposals", [])),
        "selected": state.get_result("select_best"),
        "backtest": state.get_result("backtest"),
        "errors": state.errors,
        "execution_path": state.execution_path,
    }
    state.set_result("report", report)
    state.add_message("system", "Pipeline report generated", "report")
    return state


# =============================================================================
# GRAPH BUILDER
# =============================================================================


def build_trading_strategy_graph(run_backtest: bool = True) -> AgentGraph:
    """
    Build the full Trading Strategy generation graph.

    Args:
        run_backtest: If True, includes the backtest node

    Returns:
        AgentGraph ready for execution

    Graph structure:
        analyze_market → generate_strategies → parse_responses → select_best
                                                                    │
                                                        ┌───────────┤
                                                        ▼           ▼
                                                    backtest     report
                                                        │
                                                        ▼
                                                      report → END
    """
    graph = AgentGraph(
        name="trading_strategy_pipeline",
        description="AI-powered trading strategy generation with LLM multi-agent consensus",
    )

    # Add nodes
    graph.add_node(AnalyzeMarketNode())
    graph.add_node(GenerateStrategiesNode())
    graph.add_node(ParseResponsesNode())
    graph.add_node(SelectBestNode())
    graph.add_node(FunctionAgent(name="report", func=_report_node, description="Final report"))

    # Linear chain: analyze → generate → parse → select
    graph.add_edge("analyze_market", "generate_strategies")
    graph.add_edge("generate_strategies", "parse_responses")
    graph.add_edge("parse_responses", "select_best")

    if run_backtest:
        graph.add_node(BacktestNode())
        graph.add_edge("select_best", "backtest")
        graph.add_edge("backtest", "report")
    else:
        graph.add_edge("select_best", "report")

    graph.set_entry_point("analyze_market")
    graph.add_exit_point("report")

    return graph


async def run_strategy_pipeline(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    agents: list[str] | None = None,
    run_backtest: bool = False,
    initial_capital: float = 10000,
    leverage: int = 1,
) -> AgentState:
    """
    Convenience function to run the full strategy generation pipeline.

    Args:
        symbol: Trading pair (e.g. "BTCUSDT")
        timeframe: Candle interval (e.g. "15")
        df: OHLCV DataFrame
        agents: LLM agents to use (default: ["deepseek"])
        run_backtest: Whether to backtest the generated strategy
        initial_capital: Starting capital
        leverage: Trading leverage

    Returns:
        AgentState with all results in state.results

    Example:
        state = await run_strategy_pipeline(
            symbol="BTCUSDT",
            timeframe="15",
            df=ohlcv_df,
            agents=["deepseek", "qwen"],
            run_backtest=True,
        )
        report = state.get_result("report")
        strategy = state.get_result("select_best")["selected_strategy"]
    """
    graph = build_trading_strategy_graph(run_backtest=run_backtest)

    initial_state = AgentState(
        context={
            "symbol": symbol,
            "timeframe": timeframe,
            "df": df,
            "agents": agents or ["deepseek"],
            "initial_capital": initial_capital,
            "leverage": leverage,
        }
    )

    result_state = await graph.execute(initial_state)

    logger.info(
        f"✅ [Graph] Pipeline complete: {len(result_state.execution_path)} nodes, {len(result_state.errors)} errors"
    )
    return result_state


# Register in global graph registry
register_graph(build_trading_strategy_graph(run_backtest=False))
