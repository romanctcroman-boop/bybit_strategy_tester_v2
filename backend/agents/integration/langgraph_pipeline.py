"""
LangGraph Pipeline Integration — TradingStrategyGraph

Connects the LangGraph orchestrator (AgentGraph) with StrategyController
to provide a graph-based pipeline for strategy generation with:
- Conditional edges: Sharpe < 1.0 → re-optimize, DD > 20% → re-generate
- Parallel strategy generation across multiple agents
- State management via AgentState
- Configurable quality thresholds with re-run support

Graph topology:
    MarketAnalysis → ParallelGeneration → Consensus → Backtest → QualityCheck
                         ↑                                         ↓
                         └──────── re_generate ←── (DD > 20%)     │
                                                    re_optimize ←──┘ (Sharpe < 1.0)
                                                    Report ←───────┘ (PASS)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from loguru import logger

from backend.agents.langgraph_orchestrator import (
    AgentGraph,
    AgentNode,
    AgentState,
    ConditionalRouter,
    register_graph,
)

# =============================================================================
# PIPELINE CONFIGURATION
# =============================================================================


@dataclass
class PipelineConfig:
    """Configuration for the TradingStrategyGraph pipeline.

    Attributes:
        min_sharpe: Minimum Sharpe ratio to pass quality check (triggers re-optimize if below).
        max_drawdown_pct: Maximum drawdown percentage (triggers re-generate if above).
        max_reoptimize_cycles: Maximum number of re-optimization attempts.
        max_regenerate_cycles: Maximum number of re-generation attempts.
        agents: LLM agents to use for strategy generation.
        initial_capital: Starting capital for backtest.
        leverage: Trading leverage.
        commission: Commission rate (0.0007 = 0.07%, TradingView parity).
        direction: Trade direction ("both", "long", "short").
        enable_walk_forward: Whether to run walk-forward validation.
    """

    min_sharpe: float = 1.0
    max_drawdown_pct: float = 20.0
    max_reoptimize_cycles: int = 2
    max_regenerate_cycles: int = 1
    agents: list[str] = field(default_factory=lambda: ["deepseek", "qwen", "perplexity"])
    initial_capital: float = 10000.0
    leverage: float = 1.0
    commission: float = 0.0007  # TradingView parity — NEVER change
    direction: str = "both"
    enable_walk_forward: bool = False


# =============================================================================
# AGENT NODES
# =============================================================================


class MarketAnalysisNode(AgentNode):
    """
    Stage 1: Analyze market context.

    Reads OHLCV data from state.context and builds MarketContext
    via MarketContextBuilder. Stores result in state.results["market_analysis"].
    """

    def __init__(self):
        super().__init__(
            name="market_analysis",
            description="Analyze market data and build context",
            timeout=30.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        from backend.agents.prompts.context_builder import MarketContextBuilder

        df = state.context.get("df")
        symbol = state.context.get("symbol", "BTCUSDT")
        timeframe = state.context.get("timeframe", "15")

        if df is None or not isinstance(df, pd.DataFrame):
            raise ValueError("No OHLCV DataFrame provided in state.context['df']")

        builder = MarketContextBuilder()
        context = builder.build_context(symbol, timeframe, df)

        state.set_result("market_analysis", context)
        state.add_message(
            "system",
            f"Market analysis: regime={context.market_regime}, trend={context.trend_direction}",
            "market_analysis",
        )
        logger.info(f"📊 LG Market analysis: {symbol} {timeframe} — regime={context.market_regime}")
        return state


class ParallelGenerationNode(AgentNode):
    """
    Stage 2: Generate strategy proposals in parallel across agents.

    Creates prompts for each agent and calls LLMs concurrently via StrategyController.
    Stores list of StrategyDefinition in state.results["proposals"].
    """

    def __init__(self):
        super().__init__(
            name="parallel_generation",
            description="Generate strategies from multiple agents in parallel",
            timeout=120.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        from backend.agents.prompts.prompt_engineer import PromptEngineer
        from backend.agents.prompts.response_parser import ResponseParser
        from backend.agents.strategy_controller import StrategyController

        config: PipelineConfig = state.context.get("pipeline_config", PipelineConfig())
        market_context = state.get_result("market_analysis")
        agents = config.agents

        if not market_context:
            raise ValueError("No market_analysis result — run MarketAnalysisNode first")

        platform_config = {
            "exchange": "Bybit",
            "commission": config.commission,
            "max_leverage": 100,
            "min_order": 0.001,
        }

        controller = StrategyController()
        prompt_engineer = PromptEngineer()
        parser = ResponseParser()

        # Build prompts for all agents
        agent_tasks = []
        for agent_name in agents:
            prompt = prompt_engineer.create_strategy_prompt(
                context=market_context,
                platform_config=platform_config,
                agent_name=agent_name,
                include_examples=True,
            )
            system_msg = prompt_engineer.get_system_message(agent_name)
            agent_tasks.append((agent_name, prompt, system_msg))

        # Parallel LLM calls
        async def call_agent(agent_name, prompt, system_msg):
            try:
                response_text = await controller._call_llm(agent_name, prompt, system_msg)
                if response_text:
                    strategy = parser.parse_strategy(response_text, agent_name=agent_name)
                    return strategy
            except Exception as e:
                logger.error(f"LG Parallel generation — {agent_name} failed: {e}")
            return None

        results = await asyncio.gather(
            *[call_agent(name, prompt, sys_msg) for name, prompt, sys_msg in agent_tasks],
            return_exceptions=True,
        )

        proposals = [r for r in results if r is not None and not isinstance(r, Exception)]

        state.set_result("proposals", proposals)
        state.context["generation_attempt"] = state.context.get("generation_attempt", 0) + 1

        state.add_message(
            "system",
            f"Generated {len(proposals)} proposals from {len(agents)} agents "
            f"(attempt #{state.context['generation_attempt']})",
            "parallel_generation",
        )
        logger.info(f"📝 LG Generated {len(proposals)} proposals (parallel)")
        return state


class ConsensusNode(AgentNode):
    """
    Stage 3: Select best strategy via ConsensusEngine.

    Uses ConsensusEngine.aggregate() for multi-agent consensus.
    Stores selected StrategyDefinition in state.results["selected_strategy"].
    """

    def __init__(self):
        super().__init__(
            name="consensus",
            description="Select best strategy via multi-agent consensus",
            timeout=30.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        from backend.agents.consensus.consensus_engine import ConsensusEngine

        proposals = state.get_result("proposals") or []

        if not proposals:
            raise ValueError("No proposals available for consensus")

        if len(proposals) == 1:
            selected = proposals[0]
            summary = "Single proposal — no consensus needed"
        else:
            engine = ConsensusEngine()

            # Build agent_name → strategy mapping
            strategies = {}
            for idx, p in enumerate(proposals):
                agent_name = "unknown"
                if p.agent_metadata and p.agent_metadata.agent_name:
                    agent_name = p.agent_metadata.agent_name
                key = agent_name if agent_name not in strategies else f"{agent_name}_{idx}"
                strategies[key] = p

            try:
                result = engine.aggregate(strategies=strategies, method="weighted_voting")
                selected = result.strategy
                summary = (
                    f"Consensus: agreement={result.agreement_score:.2%}, "
                    f"method={result.method}, agents={result.input_agents}"
                )
            except Exception as e:
                logger.warning(f"ConsensusEngine failed: {e}, using first proposal")
                selected = proposals[0]
                summary = f"Consensus failed ({e}) — used first proposal"

        state.set_result("selected_strategy", selected)
        state.context["consensus_summary"] = summary
        state.add_message("system", summary, "consensus")
        logger.info(f"🤝 LG {summary}")
        return state


class BacktestNode(AgentNode):
    """
    Stage 4: Backtest the selected strategy.

    Uses BacktestBridge to run FallbackEngineV4 backtest.
    Stores metrics dict in state.results["backtest_metrics"].
    """

    def __init__(self):
        super().__init__(
            name="backtest",
            description="Backtest selected strategy with FallbackEngineV4",
            timeout=60.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        from backend.agents.integration.backtest_bridge import BacktestBridge

        strategy = state.get_result("selected_strategy")
        config: PipelineConfig = state.context.get("pipeline_config", PipelineConfig())
        df = state.context.get("df")
        symbol = state.context.get("symbol", "BTCUSDT")
        timeframe = state.context.get("timeframe", "15")

        if strategy is None:
            raise ValueError("No selected_strategy — run ConsensusNode first")

        bridge = BacktestBridge()
        metrics = await bridge.run_strategy(
            strategy=strategy,
            symbol=symbol,
            timeframe=timeframe,
            df=df,
            initial_capital=config.initial_capital,
            leverage=config.leverage,
            direction=config.direction,
        )

        state.set_result("backtest_metrics", metrics or {})

        sharpe = (metrics or {}).get("sharpe_ratio", 0.0)
        max_dd = abs((metrics or {}).get("max_drawdown", 0.0))

        state.context["last_sharpe"] = sharpe
        state.context["last_drawdown"] = max_dd
        state.context["optimize_attempt"] = state.context.get("optimize_attempt", 0) + 1

        state.add_message(
            "system",
            f"Backtest: Sharpe={sharpe:.2f}, MaxDD={max_dd:.1f}% (attempt #{state.context['optimize_attempt']})",
            "backtest",
        )
        logger.info(f"📈 LG Backtest: Sharpe={sharpe:.2f}, MaxDD={max_dd:.1f}%")
        return state


class QualityCheckNode(AgentNode):
    """
    Stage 5: Quality check with conditional routing.

    Evaluates backtest metrics against thresholds:
    - Sharpe < min_sharpe AND re-optimize attempts remaining → "re_optimize"
    - MaxDD > max_drawdown_pct AND re-generate attempts remaining → "re_generate"
    - Otherwise → "report" (PASS)

    Sets state.context["quality_decision"] to route the next node.
    """

    def __init__(self):
        super().__init__(
            name="quality_check",
            description="Check backtest quality and decide next action",
            timeout=10.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        from backend.agents.metrics_analyzer import MetricsAnalyzer

        config: PipelineConfig = state.context.get("pipeline_config", PipelineConfig())
        metrics = state.get_result("backtest_metrics") or {}

        sharpe = state.context.get("last_sharpe", 0.0)
        max_dd = state.context.get("last_drawdown", 0.0)
        optimize_attempt = state.context.get("optimize_attempt", 0)
        generation_attempt = state.context.get("generation_attempt", 0)

        # Evaluate with MetricsAnalyzer
        try:
            analyzer = MetricsAnalyzer()
            analysis = analyzer.analyze(metrics)
            state.context["analysis"] = analysis.to_dict()
        except Exception as e:
            logger.warning(f"MetricsAnalyzer failed: {e}")

        # Decision logic
        decision = "report"  # Default: pass

        if max_dd > config.max_drawdown_pct and generation_attempt <= config.max_regenerate_cycles:
            decision = "re_generate"
            logger.warning(
                f"⚠️ LG MaxDD {max_dd:.1f}% > {config.max_drawdown_pct}% — re-generating "
                f"(attempt {generation_attempt}/{config.max_regenerate_cycles})"
            )
        elif sharpe < config.min_sharpe and optimize_attempt <= config.max_reoptimize_cycles:
            decision = "re_optimize"
            logger.warning(
                f"⚠️ LG Sharpe {sharpe:.2f} < {config.min_sharpe} — re-optimizing "
                f"(attempt {optimize_attempt}/{config.max_reoptimize_cycles})"
            )
        else:
            if sharpe >= config.min_sharpe and max_dd <= config.max_drawdown_pct:
                logger.info(
                    f"✅ LG Quality PASS: Sharpe={sharpe:.2f} ≥ {config.min_sharpe}, "
                    f"MaxDD={max_dd:.1f}% ≤ {config.max_drawdown_pct}%"
                )
            else:
                logger.info(f"⚠️ LG Quality marginal but max retries reached: Sharpe={sharpe:.2f}, MaxDD={max_dd:.1f}%")

        state.context["quality_decision"] = decision
        state.add_message("system", f"Quality check: {decision}", "quality_check")
        return state


class ReOptimizeNode(AgentNode):
    """
    Re-optimization node: runs walk-forward optimization on current strategy.

    Triggered when Sharpe < min_sharpe. Uses WalkForwardBridge to find
    better parameters, then loops back to backtest.
    """

    def __init__(self):
        super().__init__(
            name="re_optimize",
            description="Re-optimize strategy parameters via walk-forward",
            timeout=120.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        from backend.agents.integration.walk_forward_bridge import WalkForwardBridge

        strategy = state.get_result("selected_strategy")
        config: PipelineConfig = state.context.get("pipeline_config", PipelineConfig())
        df = state.context.get("df")
        symbol = state.context.get("symbol", "BTCUSDT")
        timeframe = state.context.get("timeframe", "15")

        if strategy is None:
            raise ValueError("No selected_strategy for re-optimization")

        try:
            bridge = WalkForwardBridge(n_splits=3, train_ratio=0.7)
            wf_result = await bridge.run_walk_forward_async(
                strategy=strategy,
                df=df,
                symbol=symbol,
                timeframe=timeframe,
                initial_capital=config.initial_capital,
                direction=config.direction,
                metric="sharpe",
            )

            # Apply recommended params to strategy
            if wf_result.recommended_params:
                for param_name, param_value in wf_result.recommended_params.items():
                    for signal in strategy.signals:
                        if param_name in signal.params:
                            signal.params[param_name] = param_value

                state.context["wf_result"] = wf_result.to_dict()
                state.add_message(
                    "system",
                    f"Re-optimized with params: {wf_result.recommended_params}, overfit={wf_result.overfit_score:.2%}",
                    "re_optimize",
                )
                logger.info(
                    f"🔄 LG Re-optimized: params={wf_result.recommended_params}, overfit={wf_result.overfit_score:.2%}"
                )
            else:
                state.add_message(
                    "system",
                    "Re-optimization found no improvements",
                    "re_optimize",
                )
        except Exception as e:
            logger.error(f"Re-optimization failed: {e}")
            state.add_message("system", f"Re-optimization failed: {e}", "re_optimize")

        return state


class ReportNode(AgentNode):
    """
    Final node: compile pipeline results into a structured report.

    Gathers all stage results and produces a comprehensive output dict
    in state.results["report"].
    """

    def __init__(self):
        super().__init__(
            name="report",
            description="Generate final pipeline report",
            timeout=10.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        config: PipelineConfig = state.context.get("pipeline_config", PipelineConfig())
        strategy = state.get_result("selected_strategy")
        metrics = state.get_result("backtest_metrics") or {}
        proposals = state.get_result("proposals") or []

        report = {
            "success": True,
            "strategy": strategy.to_dict() if strategy else None,
            "backtest_metrics": metrics,
            "proposals_count": len(proposals),
            "consensus_summary": state.context.get("consensus_summary", ""),
            "quality_decision": state.context.get("quality_decision", "report"),
            "analysis": state.context.get("analysis"),
            "walk_forward": state.context.get("wf_result"),
            "generation_attempts": state.context.get("generation_attempt", 1),
            "optimize_attempts": state.context.get("optimize_attempt", 1),
            "sharpe": state.context.get("last_sharpe", 0.0),
            "max_drawdown": state.context.get("last_drawdown", 0.0),
            "agents": config.agents,
            "execution_path": state.execution_path,
            "errors": state.errors,
        }

        state.set_result("report", report)
        state.add_message("system", "Pipeline report generated", "report")
        logger.info(
            f"📋 LG Report: Sharpe={report['sharpe']:.2f}, "
            f"DD={report['max_drawdown']:.1f}%, "
            f"attempts={report['optimize_attempts']}"
        )
        return state


# =============================================================================
# GRAPH BUILDER
# =============================================================================


class TradingStrategyGraph:
    """
    Pre-built LangGraph pipeline for AI strategy generation.

    Graph topology:
        market_analysis → parallel_generation → consensus → backtest → quality_check
                              ↑                                           ↓
                              └────── (re_generate) ←── DD > 20%        │
                                       (re_optimize) ←── Sharpe < 1.0  │
                                       (report)     ←── PASS ──────────┘
    """

    @staticmethod
    def create_graph(config: PipelineConfig | None = None) -> AgentGraph:
        """
        Build the TradingStrategyGraph with conditional edges.

        Args:
            config: Pipeline configuration. Uses defaults if not provided.

        Returns:
            Configured AgentGraph ready for execution.
        """
        if config is None:
            config = PipelineConfig()

        graph = AgentGraph(
            name="trading_strategy_pipeline",
            description=(
                "Multi-agent strategy generation pipeline with conditional re-optimization and quality control"
            ),
            max_iterations=20,
        )

        # ── Add nodes ──
        graph.add_node(MarketAnalysisNode())
        graph.add_node(ParallelGenerationNode())
        graph.add_node(ConsensusNode())
        graph.add_node(BacktestNode())
        graph.add_node(QualityCheckNode())
        graph.add_node(ReOptimizeNode())
        graph.add_node(ReportNode())

        # ── Linear edges ──
        graph.add_edge("market_analysis", "parallel_generation")
        graph.add_edge("parallel_generation", "consensus")
        graph.add_edge("consensus", "backtest")
        graph.add_edge("backtest", "quality_check")

        # ── Conditional routing from quality_check ──
        router = ConditionalRouter(name="quality_router")

        router.add_route(
            lambda state: state.context.get("quality_decision") == "re_generate",
            "parallel_generation",
        )
        router.add_route(
            lambda state: state.context.get("quality_decision") == "re_optimize",
            "re_optimize",
        )
        router.set_default("report")

        graph.add_conditional_edges("quality_check", router)

        # ── Re-optimize loops back to backtest ──
        graph.add_edge("re_optimize", "backtest")

        # ── Entry and exit ──
        graph.set_entry_point("market_analysis")
        graph.add_exit_point("report")

        return graph

    @staticmethod
    async def run(
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        config: PipelineConfig | None = None,
    ) -> dict[str, Any]:
        """
        Execute the TradingStrategyGraph pipeline.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT")
            timeframe: Candle interval (e.g. "15", "60")
            df: OHLCV DataFrame
            config: Pipeline configuration

        Returns:
            Report dict from the report node

        Example:
            result = await TradingStrategyGraph.run(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv_df,
                config=PipelineConfig(min_sharpe=1.5),
            )
            print(f"Sharpe: {result['sharpe']}")
        """
        if config is None:
            config = PipelineConfig()

        graph = TradingStrategyGraph.create_graph(config)

        # Prepare initial state
        state = AgentState()
        state.context["symbol"] = symbol
        state.context["timeframe"] = timeframe
        state.context["df"] = df
        state.context["pipeline_config"] = config

        state.add_message(
            "user",
            f"Generate trading strategy for {symbol} on {timeframe} timeframe",
        )

        logger.info(
            f"🚀 LG Pipeline starting: {symbol} {timeframe}, "
            f"agents={config.agents}, "
            f"thresholds: Sharpe≥{config.min_sharpe}, DD≤{config.max_drawdown_pct}%"
        )

        start = time.monotonic()
        final_state = await graph.execute(initial_state=state)
        duration_ms = (time.monotonic() - start) * 1000

        report = final_state.get_result("report") or {
            "success": False,
            "errors": final_state.errors,
        }
        report["total_duration_ms"] = round(duration_ms, 1)
        report["graph_metrics"] = graph.get_metrics()

        logger.info(f"🏁 LG Pipeline completed in {duration_ms:.0f}ms")
        return report

    @staticmethod
    def visualize(config: PipelineConfig | None = None) -> str:
        """Get ASCII visualization of the pipeline graph."""
        graph = TradingStrategyGraph.create_graph(config)
        return graph.visualize()


# Register in global registry
try:
    _pipeline_graph = TradingStrategyGraph.create_graph()
    register_graph(_pipeline_graph)
except Exception as e:
    logger.debug(f"Could not register trading_strategy_pipeline graph: {e}")


__all__ = [
    "BacktestNode",
    "ConsensusNode",
    "MarketAnalysisNode",
    "ParallelGenerationNode",
    "PipelineConfig",
    "QualityCheckNode",
    "ReOptimizeNode",
    "ReportNode",
    "TradingStrategyGraph",
]
