"""
Strategy Controller — main orchestrator for the LLM strategy pipeline.

Full workflow:
1. Analyze market context (MarketContextBuilder)
2. Generate strategy proposals (PromptEngineer → LLM calls)
3. Parse responses (ResponseParser → StrategyDefinition)
4. Run deliberation / consensus (RealLLMDeliberation)
5. Backtest winning strategy (BacktestBridge → FallbackEngineV4)
6. Evaluate results and report

This is the single entry point for "generate a trading strategy with AI".
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, cast

import pandas as pd
from loguru import logger

from backend.agents.consensus.consensus_engine import ConsensusEngine
from backend.agents.metrics_analyzer import MetricsAnalyzer
from backend.agents.prompts.context_builder import MarketContextBuilder
from backend.agents.prompts.prompt_engineer import PromptEngineer
from backend.agents.prompts.response_parser import (
    ResponseParser,
    StrategyDefinition,
    ValidationResult,
)

# =============================================================================
# PIPELINE RESULT MODELS
# =============================================================================


class PipelineStage(str, Enum):
    """Pipeline execution stages."""

    CONTEXT = "context_analysis"
    GENERATION = "strategy_generation"
    PARSING = "response_parsing"
    CONSENSUS = "consensus"
    BACKTEST = "backtest"
    EVALUATION = "evaluation"
    WALK_FORWARD = "walk_forward"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class StageResult:
    """Result of a single pipeline stage."""

    stage: PipelineStage
    success: bool
    duration_ms: float
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class PipelineResult:
    """Complete pipeline execution result."""

    # Final strategy
    strategy: StrategyDefinition | None = None
    validation: ValidationResult | None = None

    # Backtest results (if run)
    backtest_metrics: dict[str, Any] = field(default_factory=dict)

    # Walk-forward validation (if run)
    walk_forward: dict[str, Any] = field(default_factory=dict)

    # Pipeline metadata
    stages: list[StageResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
    final_stage: PipelineStage = PipelineStage.FAILED

    # All proposals from agents
    proposals: list[StrategyDefinition] = field(default_factory=list)

    # AI deliberation summary
    consensus_summary: str = ""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def success(self) -> bool:
        """Pipeline completed successfully."""
        return self.final_stage == PipelineStage.COMPLETE

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API response."""
        return {
            "success": self.success,
            "strategy": self.strategy.to_dict() if self.strategy else None,
            "validation": self.validation.model_dump() if self.validation else None,
            "backtest_metrics": self.backtest_metrics,
            "walk_forward": self.walk_forward,
            "proposals_count": len(self.proposals),
            "consensus_summary": self.consensus_summary,
            "stages": [
                {
                    "stage": s.stage.value,
                    "success": s.success,
                    "duration_ms": round(s.duration_ms, 1),
                    "error": s.error,
                }
                for s in self.stages
            ],
            "total_duration_ms": round(self.total_duration_ms, 1),
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# STRATEGY CONTROLLER
# =============================================================================


class StrategyController:
    """
    Main orchestrator for AI-powered strategy generation pipeline.

    Coordinates all components:
    - MarketContextBuilder → analyze market data
    - PromptEngineer → create LLM prompts
    - LLM clients → call DeepSeek/Qwen/Perplexity
    - ResponseParser → parse and validate responses
    - RealLLMDeliberation → multi-agent consensus
    - BacktestBridge → run backtest on selected strategy

    Example:
        controller = StrategyController()

        result = await controller.generate_strategy(
            symbol="BTCUSDT",
            timeframe="15",
            df=ohlcv_dataframe,
            agents=["deepseek", "qwen"],
            run_backtest=True,
        )

        if result.success:
            print(f"Strategy: {result.strategy.strategy_name}")
            print(f"Sharpe: {result.backtest_metrics.get('sharpe_ratio')}")
    """

    def __init__(self) -> None:
        self._context_builder = MarketContextBuilder()
        self._prompt_engineer = PromptEngineer()
        self._response_parser = ResponseParser()
        self._consensus_engine = ConsensusEngine()
        self._metrics_analyzer = MetricsAnalyzer()

    async def generate_strategy(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        agents: list[str] | None = None,
        run_backtest: bool = False,
        enable_walk_forward: bool = False,
        backtest_config: dict[str, Any] | None = None,
        platform_config: dict[str, Any] | None = None,
    ) -> PipelineResult:
        """
        Run the full strategy generation pipeline.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT")
            timeframe: Candle interval (e.g. "15", "60", "D")
            df: OHLCV DataFrame with columns: open, high, low, close, volume
            agents: LLM agents to use (default: ["deepseek"])
            run_backtest: Whether to backtest the generated strategy
            enable_walk_forward: Whether to run walk-forward validation after backtest
            backtest_config: Additional backtest configuration
            platform_config: Platform constraints (commission, leverage, etc.)

        Returns:
            PipelineResult with strategy, validation, and optional backtest results
        """
        if agents is None:
            agents = ["deepseek"]

        if platform_config is None:
            platform_config = {
                "exchange": "Bybit",
                "commission": 0.0007,
                "max_leverage": 100,
                "min_order": 0.001,
                "available_indicators": [
                    "RSI (Universal: Range/Cross/Legacy modes)",
                    "MACD (Universal: CrossZero/CrossSignal modes)",
                    "EMA",
                    "SMA",
                    "Bollinger",
                    "ATR",
                    "ADX",
                    "SuperTrend (Universal: Filter/Signal modes)",
                    "Stochastic (Universal: Range/Cross/KD modes)",
                    "QQE (Universal: Cross signal mode)",
                    "ATR Volatility (compare fast/slow ATR for vol expansion/contraction)",
                    "Volume Filter (compare fast/slow Volume MA)",
                    "Highest/Lowest Bar (price near N-bar extremes)",
                    "Two MAs (MA Cross + MA1 Filter modes)",
                    "Accumulation Areas (consolidation breakout detection)",
                    "Keltner/Bollinger Channel (Rebound/Breakout modes)",
                    "RVI (Relative Vigor Index range filter)",
                    "MFI (Money Flow Index range filter)",
                    "CCI (Commodity Channel Index range filter)",
                    "Momentum (rate-of-change range filter)",
                    "Divergence (multi-oscillator: RSI/Stoch/Momentum/CMF/OBV/MFI)",
                    "Conditions (Crossover/Crossunder/GreaterThan/LessThan/Equals/Between)",
                    "DCA (Dollar-Cost Averaging grid)",
                    "Manual Grid (custom offset/volume orders)",
                ],
                "available_exits": [
                    "Static SL/TP (fixed % with optional breakeven)",
                    "Trailing Stop (activation + trail distance)",
                    "ATR Exit (volatility-adaptive SL/TP)",
                    "Multi TP Levels (partial close at 3 levels)",
                    "Close by Time (bars since entry)",
                    "Channel Close (Keltner/BB boundary exit)",
                    "Two MAs Close (MA crossover exit)",
                    "Close by RSI (reach zone / cross level exit)",
                    "Close by Stochastic (reach zone / cross level exit)",
                    "Close by Parabolic SAR (SAR flip exit)",
                ],
            }

        pipeline_start = time.monotonic()
        result = PipelineResult()

        # ── Stage 1: Market Context ──
        context = await self._run_stage(
            result,
            PipelineStage.CONTEXT,
            self._build_context,
            symbol=symbol,
            timeframe=timeframe,
            df=df,
        )
        if context is None:
            result.total_duration_ms = (time.monotonic() - pipeline_start) * 1000
            return result

        # ── Stage 2: Strategy Generation (multi-agent) ──
        proposals = await self._run_stage(
            result,
            PipelineStage.GENERATION,
            self._generate_proposals,
            context=context,
            platform_config=platform_config,
            agents=agents,
        )
        if not proposals:
            result.total_duration_ms = (time.monotonic() - pipeline_start) * 1000
            return result

        result.proposals = proposals

        # ── Stage 3: Select best strategy ──
        # If single agent, use its proposal directly.
        # If multiple agents, use consensus (when available).
        if len(proposals) == 1:
            selected = proposals[0]
            result.consensus_summary = f"Single agent ({agents[0]}) — no consensus needed"
        else:
            selected = await self._run_stage(
                result,
                PipelineStage.CONSENSUS,
                self._select_best_proposal,
                proposals=proposals,
            )
            if selected is None:
                # Fallback: pick first valid proposal
                selected = proposals[0]
                result.consensus_summary = "Consensus failed — used first proposal"

        result.strategy = selected

        # ── Stage 4: Validate ──
        validation = self._response_parser.validate_strategy(selected)
        result.validation = validation

        if not validation.is_valid:
            logger.warning(
                f"Strategy validation failed: {[i.message for i in validation.issues if i.severity == 'critical']}"
            )
            result.final_stage = PipelineStage.FAILED
            result.stages.append(
                StageResult(
                    stage=PipelineStage.EVALUATION,
                    success=False,
                    duration_ms=0,
                    error="Strategy validation failed",
                )
            )
            result.total_duration_ms = (time.monotonic() - pipeline_start) * 1000
            return result

        # ── Stage 5: Backtest (optional) ──
        if run_backtest:
            bt_result = await self._run_stage(
                result,
                PipelineStage.BACKTEST,
                self._run_backtest,
                strategy=selected,
                symbol=symbol,
                timeframe=timeframe,
                df=df,
                config=backtest_config or {},
            )
            if bt_result:
                result.backtest_metrics = bt_result

                # ── Stage 6: Evaluate backtest results ──
                try:
                    analysis = self._metrics_analyzer.analyze(bt_result)
                    result.backtest_metrics["_analysis"] = analysis.to_dict()
                    result.backtest_metrics["_analysis_prompt"] = analysis.to_prompt_context()

                    result.stages.append(
                        StageResult(
                            stage=PipelineStage.EVALUATION,
                            success=True,
                            duration_ms=0,
                            data={
                                "overall_score": analysis.overall_score,
                                "grade": analysis.grade.value,
                                "needs_optimization": analysis.needs_optimization,
                                "is_deployable": analysis.is_deployable,
                            },
                        )
                    )
                    logger.info(
                        f"📊 Evaluation: score={analysis.overall_score:.0%}, "
                        f"grade={analysis.grade.value}, "
                        f"deployable={analysis.is_deployable}"
                    )

                    # ── Feedback: update ConsensusEngine agent weights ──
                    self._update_agent_performance(
                        selected=selected,
                        bt_result=bt_result,
                        analysis=analysis,
                    )

                except Exception as e:
                    logger.warning(f"Metrics analysis failed: {e}")

            # ── Stage 7: Walk-Forward Validation (optional) ──
            if enable_walk_forward and bt_result:
                wf_result = await self._run_stage(
                    result,
                    PipelineStage.WALK_FORWARD,
                    self._run_walk_forward,
                    strategy=selected,
                    symbol=symbol,
                    timeframe=timeframe,
                    df=df,
                    config=backtest_config or {},
                )
                if wf_result:
                    result.walk_forward = wf_result

        # ── Complete ──
        result.final_stage = PipelineStage.COMPLETE
        result.total_duration_ms = (time.monotonic() - pipeline_start) * 1000

        logger.info(
            f"✅ Pipeline complete: '{selected.strategy_name}' "
            f"({len(proposals)} proposals, "
            f"quality={validation.quality_score:.0%}, "
            f"{result.total_duration_ms:.0f}ms)"
        )
        return result

    # ─────────────────────────────────────────────────────────────────
    # INTERNAL STAGE METHODS
    # ─────────────────────────────────────────────────────────────────

    async def _run_stage(
        self,
        result: PipelineResult,
        stage: PipelineStage,
        func,
        **kwargs,
    ) -> Any:
        """Run a pipeline stage with timing and error handling."""
        start = time.monotonic()
        try:
            output = await func(**kwargs)
            duration = (time.monotonic() - start) * 1000
            result.stages.append(
                StageResult(
                    stage=stage,
                    success=True,
                    duration_ms=duration,
                )
            )
            return output
        except Exception as e:
            duration = (time.monotonic() - start) * 1000
            logger.error(f"Stage {stage.value} failed: {e}")
            result.stages.append(
                StageResult(
                    stage=stage,
                    success=False,
                    duration_ms=duration,
                    error=str(e),
                )
            )
            result.final_stage = PipelineStage.FAILED
            return None

    async def _build_context(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
    ):
        """Stage 1: Build market context from OHLCV data."""
        context = self._context_builder.build_context(symbol, timeframe, df)

        # Guard: if context has zero price / unknown regime, the DataFrame
        # was empty or too short.  Raise so _run_stage records a failure
        # instead of silently feeding garbage to the LLM.
        if context.current_price == 0.0 or context.data_points == 0:
            raise ValueError(
                f"Insufficient market data for {symbol}/{timeframe}: "
                f"{context.data_points} rows, price={context.current_price}"
            )

        logger.info(
            f"📊 Market context: {symbol} {timeframe} — regime={context.market_regime}, trend={context.trend_direction}"
        )
        return context

    async def _generate_proposals(
        self,
        context,
        platform_config: dict[str, Any],
        agents: list[str],
    ) -> list[StrategyDefinition]:
        """Stage 2: Generate strategy proposals from each agent."""
        proposals: list[StrategyDefinition] = []

        # Generate prompts per agent
        tasks = []
        for agent_name in agents:
            prompt = self._prompt_engineer.create_strategy_prompt(
                context=context,
                platform_config=platform_config,
                agent_name=agent_name,
                include_examples=True,
            )
            system_msg = self._prompt_engineer.get_system_message(agent_name)
            tasks.append((agent_name, prompt, system_msg))

        # Call LLMs (sequentially for now — parallel in P1)
        for agent_name, prompt, system_msg in tasks:
            try:
                response_text = await self._call_llm(agent_name, prompt, system_msg)
                if response_text:
                    strategy = self._response_parser.parse_strategy(
                        response_text,
                        agent_name=agent_name,
                    )
                    if strategy:
                        proposals.append(strategy)
                    else:
                        logger.warning(f"Failed to parse response from {agent_name}")
                else:
                    logger.warning(f"Empty response from {agent_name}")
            except Exception as e:
                logger.error(f"LLM call failed for {agent_name}: {e}")

        logger.info(f"📝 Generated {len(proposals)} proposals from {len(agents)} agents")
        return proposals

    async def _call_llm(
        self,
        agent_name: str,
        prompt: str,
        system_message: str,
    ) -> str | None:
        """
        Call an LLM agent and return the response text.

        Uses the existing LLM client infrastructure from
        backend.agents.llm.connections.
        """
        try:
            from backend.agents.llm.base_client import (
                LLMClientFactory,
                LLMConfig,
                LLMMessage,
                LLMProvider,
            )
            from backend.security.key_manager import get_key_manager

            km = get_key_manager()

            # Map agent name to provider config
            provider_configs: dict[str, tuple[LLMProvider, str, str, float]] = {
                "deepseek": (LLMProvider.DEEPSEEK, "DEEPSEEK_API_KEY", "deepseek-chat", 0.7),
                "qwen": (LLMProvider.QWEN, "QWEN_API_KEY", "qwen-plus", 0.4),
                "perplexity": (LLMProvider.PERPLEXITY, "PERPLEXITY_API_KEY", "sonar-pro", 0.7),
            }

            if agent_name not in provider_configs:
                logger.warning(f"Unknown agent '{agent_name}', skipping")
                return None

            provider, key_name, model, temperature = provider_configs[agent_name]
            api_key = km.get_decrypted_key(key_name)
            if not api_key:
                logger.warning(f"No API key for {agent_name}")
                return None

            config = LLMConfig(
                provider=provider,
                api_key=api_key,
                model=model,
                temperature=temperature,
                max_tokens=4096,
            )

            client = LLMClientFactory.create(config)
            try:
                messages = [
                    LLMMessage(role="system", content=system_message),
                    LLMMessage(role="user", content=prompt),
                ]
                response = await client.chat(messages)
                logger.debug(f"🤖 {agent_name}: {response.total_tokens} tokens, {response.latency_ms:.0f}ms")
                return cast(str, response.content)
            finally:
                await client.close()

        except ImportError as e:
            logger.error(f"Import error calling {agent_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"LLM call error for {agent_name}: {e}")
            return None

    async def _select_best_proposal(
        self,
        proposals: list[StrategyDefinition],
    ) -> StrategyDefinition | None:
        """
        Select best strategy from multiple proposals using ConsensusEngine.

        Builds agent_name -> StrategyDefinition mapping from proposal metadata,
        then delegates to ConsensusEngine.aggregate() for structured consensus.
        Falls back to simple scoring if consensus fails.
        """
        if not proposals:
            return None
        if len(proposals) == 1:
            return proposals[0]

        # Build agent_name → strategy mapping from metadata
        strategies: dict[str, StrategyDefinition] = {}
        for idx, proposal in enumerate(proposals):
            agent_name = "unknown"
            if proposal.agent_metadata and proposal.agent_metadata.agent_name:
                agent_name = proposal.agent_metadata.agent_name
            # Ensure unique keys
            key = agent_name if agent_name not in strategies else f"{agent_name}_{idx}"
            strategies[key] = proposal

        try:
            consensus_result = self._consensus_engine.aggregate(
                strategies=strategies,
                method="weighted_voting",
            )
            logger.info(
                f"🤝 Consensus: agreement={consensus_result.agreement_score:.2%}, "
                f"method={consensus_result.method}, "
                f"agents={consensus_result.input_agents}"
            )
            return consensus_result.strategy
        except Exception as e:
            logger.warning(f"ConsensusEngine failed ({e}), falling back to scoring")
            # Fallback: simple scoring
            scored = [(self._score_proposal(p), p) for p in proposals]
            scored.sort(key=lambda x: x[0], reverse=True)
            return scored[0][1]

    def _score_proposal(self, strategy: StrategyDefinition) -> float:
        """
        Score a strategy proposal based on quality heuristics.

        Higher is better. Range: 0-10.
        """
        score = 5.0  # Base score

        # Signal quality
        n_signals = len(strategy.signals)
        if 1 <= n_signals <= 3:
            score += 1.0  # Good signal count
        elif n_signals > 4:
            score -= 0.5  # Too many signals = overfitting risk

        # Has exit conditions
        if strategy.exit_conditions:
            score += 1.0
            if strategy.exit_conditions.take_profit and strategy.exit_conditions.stop_loss:
                score += 0.5  # Both TP and SL defined

        # Has filters
        if strategy.filters:
            score += 0.5

        # Has optimization hints
        if strategy.optimization_hints and strategy.optimization_hints.parameters_to_optimize:
            score += 0.5

        # Entry conditions specified
        if strategy.entry_conditions and strategy.entry_conditions.long and strategy.entry_conditions.short:
            score += 0.5

        # Validation
        validation = self._response_parser.validate_strategy(strategy)
        score += validation.quality_score  # 0-1

        return min(10.0, score)

    def _update_agent_performance(
        self,
        selected: StrategyDefinition,
        bt_result: dict[str, Any],
        analysis: Any,
    ) -> None:
        """
        Feed backtest results back to ConsensusEngine for adaptive weighting.

        After a strategy is backtested, this updates the generating agent's
        performance record so future consensus rounds use historical accuracy
        as a weight factor (not just uniform weights).

        Args:
            selected: The strategy that was backtested
            bt_result: Raw backtest metrics dict from BacktestBridge
            analysis: MetricsAnalysis with overall_score, is_deployable, grade
        """
        agent_name = "unknown"
        if selected.agent_metadata and selected.agent_metadata.agent_name:
            agent_name = selected.agent_metadata.agent_name

        if agent_name == "unknown":
            logger.debug("Cannot update performance — agent_name not available")
            return

        sharpe = float(bt_result.get("sharpe_ratio", 0.0) or 0.0)
        profit_factor = float(bt_result.get("profit_factor", 0.0) or 0.0)
        win_rate = float(bt_result.get("win_rate", 0.0) or 0.0)
        backtest_passed = analysis.is_deployable

        self._consensus_engine.update_performance(
            agent_name=agent_name,
            sharpe=sharpe,
            profit_factor=profit_factor,
            win_rate=win_rate,
            backtest_passed=backtest_passed,
        )

        perf = self._consensus_engine.get_performance(agent_name)
        if perf:
            logger.info(
                f"🔄 Feedback → {agent_name}: "
                f"success_rate={perf.success_rate:.0%}, "
                f"avg_sharpe={perf.avg_sharpe:.2f}, "
                f"cumulative_score={perf.cumulative_score:.2f} "
                f"(total={perf.total_strategies})"
            )

    async def _run_backtest(
        self,
        strategy: StrategyDefinition,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Run a backtest on the generated strategy.

        Delegates to BacktestBridge (created in P0 task 4).
        Falls back to direct engine call if bridge not available.
        """
        try:
            from backend.agents.integration.backtest_bridge import BacktestBridge

            bridge = BacktestBridge()
            result = await bridge.run_strategy(
                strategy=strategy,
                symbol=symbol,
                timeframe=timeframe,
                df=df,
                initial_capital=config.get("initial_capital", 10000),
                leverage=config.get("leverage", 1),
                direction=config.get("direction", "both"),
            )
            return result
        except ImportError:
            logger.warning("BacktestBridge not available, skipping backtest")
            return None
        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            return None

    async def _run_walk_forward(
        self,
        strategy: StrategyDefinition,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Run walk-forward validation on the generated strategy.

        Uses WalkForwardBridge to convert StrategyDefinition to
        WalkForwardOptimizer-compatible format and run validation.

        Args:
            strategy: Selected StrategyDefinition
            symbol: Trading pair
            timeframe: Candle interval
            df: OHLCV DataFrame
            config: Additional config (initial_capital, direction, etc.)

        Returns:
            Dict with walk-forward results or None on failure
        """
        try:
            from backend.agents.integration.walk_forward_bridge import (
                WalkForwardBridge,
            )

            bridge = WalkForwardBridge(
                n_splits=config.get("wf_splits", 5),
                train_ratio=config.get("wf_train_ratio", 0.7),
            )
            wf_result = await bridge.run_walk_forward_async(
                strategy=strategy,
                df=df,
                symbol=symbol,
                timeframe=timeframe,
                initial_capital=config.get("initial_capital", 10000),
                direction=config.get("direction", "both"),
                metric=config.get("wf_metric", "sharpe"),
            )

            logger.info(
                f"🔄 Walk-forward: overfit={wf_result.overfit_score:.2%}, "
                f"consistency={wf_result.consistency_ratio:.0%}, "
                f"confidence={wf_result.confidence_level}, "
                f"recommended_params={wf_result.recommended_params}"
            )
            return wf_result.to_dict()
        except ImportError:
            logger.warning("WalkForwardBridge not available, skipping walk-forward")
            return None
        except ValueError as e:
            logger.warning(f"Walk-forward skipped: {e}")
            return None
        except Exception as e:
            logger.error(f"Walk-forward failed: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────
    # CONVENIENCE METHODS
    # ─────────────────────────────────────────────────────────────────

    async def quick_generate(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        agent: str = "deepseek",
    ) -> StrategyDefinition | None:
        """
        Quick strategy generation with a single agent, no backtest.

        Args:
            symbol: Trading pair
            timeframe: Candle interval
            df: OHLCV DataFrame
            agent: LLM agent to use

        Returns:
            StrategyDefinition or None
        """
        result = await self.generate_strategy(
            symbol=symbol,
            timeframe=timeframe,
            df=df,
            agents=[agent],
            run_backtest=False,
        )
        return result.strategy

    async def generate_and_backtest(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        agents: list[str] | None = None,
        initial_capital: float = 10000,
        leverage: float = 1,
        enable_walk_forward: bool = False,
    ) -> PipelineResult:
        """
        Generate strategy and immediately backtest it.

        Args:
            symbol: Trading pair
            timeframe: Candle interval
            df: OHLCV DataFrame
            agents: LLM agents to use
            initial_capital: Starting capital
            leverage: Trading leverage
            enable_walk_forward: Whether to run walk-forward validation

        Returns:
            PipelineResult with strategy and backtest metrics
        """
        return await self.generate_strategy(
            symbol=symbol,
            timeframe=timeframe,
            df=df,
            agents=agents,
            run_backtest=True,
            enable_walk_forward=enable_walk_forward,
            backtest_config={
                "initial_capital": initial_capital,
                "leverage": leverage,
            },
        )
