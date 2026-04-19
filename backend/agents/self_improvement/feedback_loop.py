"""
Automatic Feedback Loop for Strategy Improvement

Implements the cycle: backtest → analysis → prompt improvement.

The FeedbackLoop connects:
1. BacktestBridge — runs strategy backtests
2. LLMSelfReflectionEngine — analyzes results via LLM
3. PromptEngineer — improves prompts based on reflection
4. StrategyEvolution — tracks improvement over generations

This creates a self-reinforcing improvement cycle where each
iteration learns from previous mistakes and builds on successes.

Flow:
    Strategy → Backtest → Reflect → Extract Insights → Improve Prompt
       ↑                                                       │
       └───────────────── Generate New Strategy ←──────────────┘
"""

from __future__ import annotations

import asyncio
import statistics
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class FeedbackEntry:
    """Single entry in the feedback loop."""

    id: str
    iteration: int
    strategy_name: str
    strategy_type: str
    strategy_params: dict[str, Any]
    backtest_metrics: dict[str, Any]
    fitness_score: float
    reflection_summary: list[str]
    improvement_actions: list[str]
    prompt_adjustments: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "id": self.id,
            "iteration": self.iteration,
            "strategy_name": self.strategy_name,
            "strategy_type": self.strategy_type,
            "fitness_score": self.fitness_score,
            "backtest_metrics": {
                k: round(v, 4) if isinstance(v, float) else v for k, v in self.backtest_metrics.items()
            },
            "reflection_summary": self.reflection_summary,
            "improvement_actions": self.improvement_actions,
            "prompt_adjustments": self.prompt_adjustments,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class FeedbackLoopResult:
    """Result of a complete feedback loop run."""

    loop_id: str
    total_iterations: int
    best_fitness: float = 0.0
    best_iteration: int = 0
    fitness_history: list[float] = field(default_factory=list)
    improvement_trend: float = 0.0
    converged: bool = False
    convergence_reason: str = ""
    entries: list[FeedbackEntry] = field(default_factory=list)
    total_duration_ms: float = 0.0
    accumulated_insights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "loop_id": self.loop_id,
            "total_iterations": self.total_iterations,
            "best_fitness": round(self.best_fitness, 2),
            "best_iteration": self.best_iteration,
            "fitness_history": [round(f, 2) for f in self.fitness_history],
            "improvement_trend": round(self.improvement_trend, 4),
            "converged": self.converged,
            "convergence_reason": self.convergence_reason,
            "total_duration_ms": round(self.total_duration_ms, 0),
            "accumulated_insights": self.accumulated_insights[:10],
            "entries_count": len(self.entries),
        }


# =============================================================================
# PROMPT IMPROVEMENT ENGINE
# =============================================================================


class PromptImprovementEngine:
    """
    Extracts insights from reflections and generates prompt adjustments.

    This is the "brain" of the feedback loop — it takes reflection data
    (what worked, what didn't, knowledge gaps) and translates them into
    concrete prompt modifications.

    Example:
        engine = PromptImprovementEngine()
        adjustments = engine.generate_adjustments(
            reflection_summary=["RSI period too short", "Need trailing stop"],
            improvement_actions=["Increase RSI period", "Add ATR-based stop"],
            backtest_metrics={"sharpe_ratio": 0.8, "max_drawdown_pct": 25},
        )
    """

    # Metric thresholds for automatic adjustments
    METRIC_THRESHOLDS = {
        "sharpe_ratio": {"poor": 0.5, "good": 1.5, "excellent": 2.5},
        "win_rate": {"poor": 0.35, "good": 0.50, "excellent": 0.65},
        "max_drawdown_pct": {"poor": 30.0, "acceptable": 15.0, "good": 8.0},
        "profit_factor": {"poor": 0.8, "good": 1.5, "excellent": 2.5},
    }

    # Adjustment templates keyed by problem type
    ADJUSTMENT_TEMPLATES = {
        "high_drawdown": {
            "emphasis": "risk_management",
            "instructions": [
                "Add tighter stop-loss conditions",
                "Consider ATR-based dynamic stops",
                "Reduce position sizing",
                "Add drawdown-based exit rules",
            ],
        },
        "low_win_rate": {
            "emphasis": "entry_quality",
            "instructions": [
                "Add confirmation filters before entry",
                "Use multi-timeframe confirmation",
                "Require stronger signal threshold",
                "Add volume or volatility filters",
            ],
        },
        "low_sharpe": {
            "emphasis": "risk_adjusted_returns",
            "instructions": [
                "Optimize risk/reward ratio",
                "Consider reducing trade frequency",
                "Add trend filter to avoid choppy markets",
                "Improve exit timing to capture more profit",
            ],
        },
        "low_profit_factor": {
            "emphasis": "trade_quality",
            "instructions": [
                "Focus on higher-probability setups",
                "Widen take-profit targets",
                "Cut losing trades faster",
                "Filter out low-quality signals",
            ],
        },
        "few_trades": {
            "emphasis": "signal_frequency",
            "instructions": [
                "Relax entry conditions slightly",
                "Consider shorter indicator periods",
                "Add alternative entry triggers",
                "Allow multiple signal types",
            ],
        },
    }

    def __init__(self) -> None:
        """Initialize prompt improvement engine."""
        self._adjustment_history: list[dict[str, Any]] = []

    def generate_adjustments(
        self,
        reflection_summary: list[str],
        improvement_actions: list[str],
        backtest_metrics: dict[str, Any],
        knowledge_gaps: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Generate prompt adjustments based on feedback.

        Args:
            reflection_summary: Lessons learned from reflection
            improvement_actions: Suggested improvements
            backtest_metrics: Backtest results
            knowledge_gaps: Identified knowledge gaps

        Returns:
            Dict of prompt adjustments to apply
        """
        adjustments: dict[str, Any] = {
            "emphasis_areas": [],
            "specific_instructions": [],
            "parameter_hints": {},
            "avoid_patterns": [],
            "additional_context": [],
        }

        # 1. Metric-based adjustments
        metric_adj = self._analyze_metrics(backtest_metrics)
        adjustments["emphasis_areas"].extend(metric_adj.get("emphasis_areas", []))
        adjustments["specific_instructions"].extend(metric_adj.get("specific_instructions", []))

        # 2. Reflection-based adjustments
        for lesson in reflection_summary:
            lower = lesson.lower()
            if any(w in lower for w in ["stop", "drawdown", "risk"]):
                adjustments["emphasis_areas"].append("risk_management")
            if any(w in lower for w in ["entry", "signal", "filter"]):
                adjustments["emphasis_areas"].append("entry_quality")
            if any(w in lower for w in ["exit", "profit", "target"]):
                adjustments["emphasis_areas"].append("exit_optimization")

        # 3. Improvement action integration
        for action in improvement_actions:
            adjustments["specific_instructions"].append(action)

        # 4. Knowledge gap context
        if knowledge_gaps:
            for gap in knowledge_gaps:
                adjustments["additional_context"].append(f"Consider learning about: {gap}")

        # 5. Parameter hints from metrics
        adjustments["parameter_hints"] = self._extract_parameter_hints(backtest_metrics)

        # Deduplicate
        adjustments["emphasis_areas"] = list(set(adjustments["emphasis_areas"]))
        adjustments["specific_instructions"] = list(dict.fromkeys(adjustments["specific_instructions"]))[:10]

        # Track history
        self._adjustment_history.append(adjustments)

        return adjustments

    def format_adjustments_for_prompt(
        self,
        adjustments: dict[str, Any],
    ) -> str:
        """
        Format adjustments into text that can be injected into prompts.

        Args:
            adjustments: Adjustments dict from generate_adjustments()

        Returns:
            Formatted string for prompt injection
        """
        parts = []

        if adjustments.get("emphasis_areas"):
            areas = ", ".join(adjustments["emphasis_areas"])
            parts.append(f"EMPHASIS: Focus on {areas}.")

        if adjustments.get("specific_instructions"):
            instr = "\n".join(f"  - {i}" for i in adjustments["specific_instructions"][:5])
            parts.append(f"INSTRUCTIONS:\n{instr}")

        if adjustments.get("parameter_hints"):
            hints = adjustments["parameter_hints"]
            hint_str = ", ".join(f"{k}={v}" for k, v in hints.items())
            parts.append(f"PARAMETER HINTS: {hint_str}")

        if adjustments.get("avoid_patterns"):
            avoid = ", ".join(adjustments["avoid_patterns"][:3])
            parts.append(f"AVOID: {avoid}")

        return "\n\n".join(parts) if parts else ""

    def _analyze_metrics(
        self,
        metrics: dict[str, Any],
    ) -> dict[str, list[str]]:
        """Analyze metrics against thresholds and generate adjustments."""
        result: dict[str, list[str]] = {
            "emphasis_areas": [],
            "specific_instructions": [],
        }

        sharpe = float(metrics.get("sharpe_ratio", 0))
        win_rate = float(metrics.get("win_rate", 0))
        dd = float(metrics.get("max_drawdown_pct", 0))
        pf = float(metrics.get("profit_factor", 0))
        trades = int(metrics.get("total_trades", 0))

        if dd > self.METRIC_THRESHOLDS["max_drawdown_pct"]["poor"]:
            template = self.ADJUSTMENT_TEMPLATES["high_drawdown"]
            result["emphasis_areas"].append(template["emphasis"])
            result["specific_instructions"].extend(template["instructions"][:2])

        if win_rate < self.METRIC_THRESHOLDS["win_rate"]["poor"]:
            template = self.ADJUSTMENT_TEMPLATES["low_win_rate"]
            result["emphasis_areas"].append(template["emphasis"])
            result["specific_instructions"].extend(template["instructions"][:2])

        if sharpe < self.METRIC_THRESHOLDS["sharpe_ratio"]["poor"]:
            template = self.ADJUSTMENT_TEMPLATES["low_sharpe"]
            result["emphasis_areas"].append(template["emphasis"])
            result["specific_instructions"].extend(template["instructions"][:2])

        if pf < self.METRIC_THRESHOLDS["profit_factor"]["poor"]:
            template = self.ADJUSTMENT_TEMPLATES["low_profit_factor"]
            result["emphasis_areas"].append(template["emphasis"])
            result["specific_instructions"].extend(template["instructions"][:2])

        if trades < 10:
            template = self.ADJUSTMENT_TEMPLATES["few_trades"]
            result["emphasis_areas"].append(template["emphasis"])
            result["specific_instructions"].extend(template["instructions"][:2])

        return result

    def _extract_parameter_hints(
        self,
        metrics: dict[str, Any],
    ) -> dict[str, str]:
        """Extract parameter hints from metrics."""
        hints: dict[str, str] = {}

        dd = float(metrics.get("max_drawdown_pct", 0))
        if dd > 20:
            hints["stop_loss"] = "tighter (reduce by 20-30%)"

        win_rate = float(metrics.get("win_rate", 0))
        if win_rate < 0.4:
            hints["entry_threshold"] = "stricter (increase sensitivity)"

        trades = int(metrics.get("total_trades", 0))
        if trades < 10:
            hints["signal_sensitivity"] = "increase (lower thresholds)"
        elif trades > 200:
            hints["signal_sensitivity"] = "decrease (higher thresholds)"

        return hints

    def get_history(self) -> list[dict[str, Any]]:
        """Get adjustment history."""
        return list(self._adjustment_history)


# =============================================================================
# FEEDBACK LOOP
# =============================================================================


class FeedbackLoop:
    """
    Automatic feedback loop: backtest → reflect → improve → repeat.

    Connects the backtest engine, reflection engine, and prompt improvement
    into a self-reinforcing improvement cycle.

    Example:
        loop = FeedbackLoop()
        result = await loop.run(
            symbol="BTCUSDT",
            timeframe="15",
            df=ohlcv_data,
            strategy_type="rsi",
            initial_params={"period": 14, "overbought": 70, "oversold": 30},
            max_iterations=5,
        )
        print(f"Best fitness: {result.best_fitness}")
        print(f"Insights: {result.accumulated_insights}")
    """

    # Convergence detection
    CONVERGENCE_THRESHOLD = 1.5  # Fitness improvement < 1.5 = converged
    MIN_ITERATIONS = 2
    MAX_STAGNANT = 3

    def __init__(
        self,
        *,
        reflection_fn=None,
        improvement_engine: PromptImprovementEngine | None = None,
    ):
        """
        Initialize feedback loop.

        Args:
            reflection_fn: Optional reflection function (async)
            improvement_engine: Optional prompt improvement engine
        """
        self.improvement_engine = improvement_engine or PromptImprovementEngine()
        self._reflection_fn = reflection_fn

        # State
        self._entries: list[FeedbackEntry] = []
        self._accumulated_insights: list[str] = []

        logger.info("🔄 FeedbackLoop initialized")

    async def run(
        self,
        symbol: str,
        timeframe: str,
        df,
        *,
        strategy_type: str = "rsi",
        initial_params: dict[str, Any] | None = None,
        max_iterations: int = 5,
        initial_capital: float = 10000.0,
        leverage: int = 1,
        direction: str = "both",
    ) -> FeedbackLoopResult:
        """
        Run the full feedback loop.

        Args:
            symbol: Trading pair
            timeframe: Timeframe string
            df: OHLCV DataFrame
            strategy_type: Strategy type to optimize
            initial_params: Starting parameters
            max_iterations: Maximum loop iterations
            initial_capital: Starting capital
            leverage: Leverage multiplier
            direction: Trade direction

        Returns:
            FeedbackLoopResult with history and insights
        """
        # Lazy imports to avoid circular deps
        from backend.agents.integration.backtest_bridge import BacktestBridge
        from backend.agents.self_improvement.self_reflection import (
            SelfReflectionEngine,
        )
        from backend.agents.self_improvement.strategy_evolution import compute_fitness

        loop_id = f"loop_{uuid.uuid4().hex[:12]}"
        start_time = time.time()

        logger.info(f"🔄 Feedback loop started: {loop_id} | {symbol} {timeframe} | max_iter={max_iterations}")

        result = FeedbackLoopResult(
            loop_id=loop_id,
            total_iterations=0,
        )

        bridge = BacktestBridge()
        reflection = SelfReflectionEngine(reflection_fn=self._reflection_fn)

        current_params = dict(initial_params or {})
        best_fitness = -1.0
        stagnant_count = 0

        for iteration in range(1, max_iterations + 1):
            logger.info(f"🔄 Iteration {iteration}/{max_iterations}")

            # === STEP 1: Build strategy definition ===
            strategy_def = self._build_strategy_definition(strategy_type, current_params, iteration)

            # === STEP 2: Backtest ===
            try:
                metrics = await asyncio.wait_for(
                    bridge.run_strategy(
                        strategy=strategy_def,
                        symbol=symbol,
                        timeframe=timeframe,
                        df=df,
                        initial_capital=initial_capital,
                        leverage=leverage,
                        direction=direction,
                    ),
                    timeout=300.0,
                )
            except TimeoutError:
                logger.warning(f"Iteration {iteration}: backtest timed out (300s)")
                metrics = self._create_failed_metrics()
            except Exception as e:
                logger.warning(f"Iteration {iteration}: backtest failed: {e}")
                metrics = self._create_failed_metrics()

            # === STEP 3: Compute fitness ===
            fitness = compute_fitness(metrics)

            # === STEP 4: Reflect ===
            task = f"Backtest {strategy_type} strategy (iter {iteration})"
            solution = f"Parameters: {current_params}"
            outcome = {
                "success": fitness > 30,
                "fitness_score": fitness,
                **metrics,
            }

            try:
                ref_result = await reflection.reflect_on_task(task, solution, outcome)
                reflection_summary = ref_result.lessons_learned
                improvement_actions = ref_result.improvement_actions
                knowledge_gaps = ref_result.knowledge_gaps
            except Exception as e:
                logger.warning(f"Reflection failed: {e}")
                reflection_summary = []
                improvement_actions = []
                knowledge_gaps = []

            # === STEP 5: Generate prompt adjustments ===
            adjustments = self.improvement_engine.generate_adjustments(
                reflection_summary=reflection_summary,
                improvement_actions=improvement_actions,
                backtest_metrics=metrics,
                knowledge_gaps=knowledge_gaps,
            )

            # === STEP 6: Record entry ===
            entry = FeedbackEntry(
                id=f"fb_{uuid.uuid4().hex[:8]}",
                iteration=iteration,
                strategy_name=f"{strategy_type}_v{iteration}",
                strategy_type=strategy_type,
                strategy_params=dict(current_params),
                backtest_metrics=metrics,
                fitness_score=fitness,
                reflection_summary=reflection_summary,
                improvement_actions=improvement_actions,
                prompt_adjustments=adjustments,
            )
            result.entries.append(entry)
            self._entries.append(entry)
            result.fitness_history.append(fitness)
            result.total_iterations = iteration

            # Accumulate insights
            self._accumulated_insights.extend(reflection_summary[:2])

            logger.info(f"🔄 Iter {iteration}: fitness={fitness:.1f} | sharpe={metrics.get('sharpe_ratio', 0):.2f}")

            # === STEP 7: Apply improvements to params ===
            current_params = self._apply_adjustments(current_params, adjustments, metrics)

            # === STEP 8: Convergence check ===
            improvement = fitness - best_fitness
            if fitness > best_fitness:
                best_fitness = fitness
                result.best_fitness = fitness
                result.best_iteration = iteration
                stagnant_count = 0
            else:
                stagnant_count += 1

            if iteration >= self.MIN_ITERATIONS and improvement < self.CONVERGENCE_THRESHOLD and stagnant_count >= 2:
                result.converged = True
                result.convergence_reason = f"fitness_plateau (best={best_fitness:.1f})"
                break

            if stagnant_count >= self.MAX_STAGNANT:
                result.convergence_reason = "stagnant"
                break

        # Finalize
        result.total_duration_ms = (time.time() - start_time) * 1000
        result.accumulated_insights = list(set(self._accumulated_insights))[:10]

        # Calculate improvement trend
        if len(result.fitness_history) >= 2:
            diffs = [
                result.fitness_history[i + 1] - result.fitness_history[i]
                for i in range(len(result.fitness_history) - 1)
            ]
            result.improvement_trend = statistics.mean(diffs) if diffs else 0.0

        logger.info(
            f"🔄 Feedback loop complete: {result.total_iterations} iterations | "
            f"best_fitness={result.best_fitness:.1f} | "
            f"trend={result.improvement_trend:+.2f}"
        )

        return result

    def _build_strategy_definition(
        self,
        strategy_type: str,
        params: dict[str, Any],
        iteration: int,
    ):
        """Build a StrategyDefinition from type and params."""
        from backend.agents.prompts.response_parser import (
            ExitCondition,
            ExitConditions,
            Signal,
            StrategyDefinition,
        )

        oversold_val = params.get("oversold", params.get("threshold", 30))

        return StrategyDefinition(
            strategy_name=f"{strategy_type}_feedback_v{iteration}",
            description=f"Auto-improved {strategy_type} strategy (iteration {iteration})",
            signals=[
                Signal(
                    id=f"signal_{strategy_type}",
                    type=strategy_type.upper(),
                    params=params,
                    condition=f"crosses_above {oversold_val}",
                ),
            ],
            exit_conditions=ExitConditions(
                stop_loss=ExitCondition(
                    type="fixed_pct",
                    value=params.get("stop_loss_pct", 2.0),
                    description=f"Stop loss at {params.get('stop_loss_pct', 2.0)}%",
                ),
                take_profit=ExitCondition(
                    type="fixed_pct",
                    value=params.get("take_profit_pct", 3.0),
                    description=f"Take profit at {params.get('take_profit_pct', 3.0)}%",
                ),
            ),
        )

    def _create_failed_metrics(self) -> dict[str, Any]:
        """Create default metrics for failed backtest."""
        return {
            "net_profit": 0.0,
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "max_drawdown_pct": 100.0,
            "profit_factor": 0.0,
            "total_trades": 0,
        }

    def _apply_adjustments(
        self,
        current_params: dict[str, Any],
        adjustments: dict[str, Any],
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Apply prompt adjustments to strategy parameters.

        This is the parameter mutation step — it modifies strategy
        parameters based on feedback loop insights.
        """
        new_params = dict(current_params)

        # Adjust based on hints
        hints = adjustments.get("parameter_hints", {})

        if "stop_loss" in hints and "stop_loss_pct" in new_params:
            # Tighten stop loss
            current_sl = new_params["stop_loss_pct"]
            new_params["stop_loss_pct"] = round(current_sl * 0.8, 2)

        if "entry_threshold" in hints:
            # Adjust entry sensitivity
            if "oversold" in new_params:
                new_params["oversold"] = max(15, new_params["oversold"] - 5)
            if "overbought" in new_params:
                new_params["overbought"] = min(85, new_params["overbought"] + 5)

        if "signal_sensitivity" in hints:
            sensitivity = hints["signal_sensitivity"]
            if "increase" in sensitivity and "period" in new_params:
                new_params["period"] = max(5, new_params["period"] - 2)
            elif "decrease" in sensitivity and "period" in new_params:
                new_params["period"] = min(50, new_params["period"] + 2)

        return new_params

    def get_entries(self) -> list[FeedbackEntry]:
        """Get all feedback entries."""
        return list(self._entries)


__all__ = [
    "FeedbackEntry",
    "FeedbackLoop",
    "FeedbackLoopResult",
    "PromptImprovementEngine",
]
