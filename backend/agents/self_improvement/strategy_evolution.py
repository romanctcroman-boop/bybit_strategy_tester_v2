"""
Strategy Evolution Engine — Self-Improving Strategy Pipeline.

Implements an autonomous evolution loop:
1. Generate strategy via LLM pipeline (StrategyController)
2. Backtest strategy (BacktestBridge / FallbackEngineV4)
3. Reflect on results (SelfReflectionEngine with real LLM)
4. Collect RLHF feedback (RLHFModule — rank strategies)
5. Generate improved strategy using reflection insights
6. Repeat until convergence or max iterations

This module connects all P0-P3 components into a single
self-improving system that gets better at generating strategies.

References:
- Reflexion (Shinn et al., 2023)
- Self-Refine (Madaan et al., 2023)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import pandas as pd
from loguru import logger

from backend.agents.integration.backtest_bridge import BacktestBridge
from backend.agents.prompts.context_builder import MarketContextBuilder
from backend.agents.prompts.response_parser import (
    ResponseParser,
    StrategyDefinition,
)
from backend.agents.self_improvement.rlhf_module import (
    FeedbackSample,
    PreferenceType,
    RLHFModule,
)
from backend.agents.self_improvement.self_reflection import (
    ReflectionResult,
    SelfReflectionEngine,
)

# =============================================================================
# DATA MODELS
# =============================================================================


class EvolutionStage(str, Enum):
    """Stages of the evolution loop."""

    GENERATE = "generate"
    BACKTEST = "backtest"
    REFLECT = "reflect"
    RANK = "rank"
    EVOLVE = "evolve"
    CONVERGED = "converged"
    FAILED = "failed"


@dataclass
class GenerationRecord:
    """Record of a single strategy generation + backtest."""

    generation: int
    strategy: StrategyDefinition
    backtest_metrics: dict[str, Any]
    reflection: ReflectionResult | None = None
    fitness_score: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "strategy_name": self.strategy.strategy_name,
            "strategy_type": self.strategy.get_strategy_type_for_engine(),
            "fitness_score": self.fitness_score,
            "net_profit": self.backtest_metrics.get("net_profit", 0),
            "sharpe_ratio": self.backtest_metrics.get("sharpe_ratio", 0),
            "max_drawdown_pct": self.backtest_metrics.get("max_drawdown_pct", 0),
            "win_rate": self.backtest_metrics.get("win_rate", 0),
            "total_trades": self.backtest_metrics.get("total_trades", 0),
            "profit_factor": self.backtest_metrics.get("profit_factor", 0),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class EvolutionResult:
    """Complete evolution loop result."""

    evolution_id: str
    symbol: str
    timeframe: str
    total_generations: int
    best_generation: GenerationRecord | None = None
    all_generations: list[GenerationRecord] = field(default_factory=list)
    converged: bool = False
    convergence_reason: str = ""
    total_duration_ms: float = 0.0
    rlhf_stats: dict[str, Any] = field(default_factory=dict)
    reflection_summary: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evolution_id": self.evolution_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "total_generations": self.total_generations,
            "converged": self.converged,
            "convergence_reason": self.convergence_reason,
            "total_duration_ms": self.total_duration_ms,
            "best_generation": (self.best_generation.to_dict() if self.best_generation else None),
            "all_generations": [g.to_dict() for g in self.all_generations],
            "rlhf_stats": self.rlhf_stats,
            "reflection_summary": self.reflection_summary,
        }


# =============================================================================
# FITNESS FUNCTION
# =============================================================================


def compute_fitness(
    metrics: dict[str, Any],
    weights: dict[str, float] | None = None,
) -> float:
    """
    Compute a fitness score (0-100) from backtest metrics.

    Higher is better. Combines multiple trading metrics into a
    single scalar for comparison and ranking.

    Args:
        metrics: Backtest metrics dict (from BacktestBridge or engine)
        weights: Optional custom weights for each component

    Returns:
        Fitness score 0-100
    """
    default_weights = {
        "sharpe_ratio": 0.25,
        "profit_factor": 0.20,
        "win_rate": 0.15,
        "net_profit_pct": 0.15,
        "max_drawdown_penalty": 0.15,
        "trade_count_bonus": 0.10,
    }
    w = weights or default_weights

    score = 0.0

    # Sharpe ratio: 0-3 → 0-25 points
    sharpe = float(metrics.get("sharpe_ratio", 0))
    sharpe_norm = max(0, min(sharpe / 3.0, 1.0))
    score += sharpe_norm * w.get("sharpe_ratio", 0.25) * 100

    # Profit factor: 0-3 → 0-20 points
    pf = float(metrics.get("profit_factor", 0))
    pf_norm = max(0, min(pf / 3.0, 1.0))
    score += pf_norm * w.get("profit_factor", 0.20) * 100

    # Win rate: 0-1 → 0-15 points
    wr = float(metrics.get("win_rate", 0))
    score += wr * w.get("win_rate", 0.15) * 100

    # Net profit % (normalized by initial capital)
    initial_capital = float(metrics.get("initial_capital", 10000))
    net_profit = float(metrics.get("net_profit", 0))
    net_pct = net_profit / initial_capital if initial_capital > 0 else 0
    net_norm = max(0, min((net_pct + 0.5) / 1.0, 1.0))  # -50% to +50% → 0-1
    score += net_norm * w.get("net_profit_pct", 0.15) * 100

    # Max drawdown penalty (lower is better)
    dd = float(metrics.get("max_drawdown_pct", 0))
    dd_norm = max(0, 1.0 - dd / 50.0)  # 0-50% drawdown → 1-0
    score += dd_norm * w.get("max_drawdown_penalty", 0.15) * 100

    # Trade count bonus (need sufficient trades for statistical significance)
    trades = int(metrics.get("total_trades", 0))
    trade_norm = min(trades / 30.0, 1.0)  # ≥30 trades = full bonus
    score += trade_norm * w.get("trade_count_bonus", 0.10) * 100

    return round(max(0, min(100, score)), 2)


# =============================================================================
# EVOLUTION PROMPTS
# =============================================================================

REFLECTION_SYSTEM_PROMPT = """You are an expert trading strategy analyst.
Your job is to analyze backtest results and identify:
1. What worked well and what didn't
2. Root causes of poor performance (if any)
3. Specific, actionable improvements to make the strategy better

Be quantitative and specific. Reference actual metrics.
Respond in a structured format with clear sections."""

EVOLUTION_PROMPT_TEMPLATE = """## Strategy Improvement Request

### Previous Strategy
Name: {strategy_name}
Type: {strategy_type}
Parameters: {strategy_params}

### Backtest Results
- Net Profit: ${net_profit:.2f} ({net_profit_pct:.1f}%)
- Sharpe Ratio: {sharpe_ratio:.2f}
- Win Rate: {win_rate:.1f}%
- Max Drawdown: {max_drawdown:.1f}%
- Profit Factor: {profit_factor:.2f}
- Total Trades: {total_trades}

### Reflection Insights
{reflection_insights}

### Market Context
{market_context}

### Task
Based on the above analysis, generate an IMPROVED trading strategy.
The new strategy should address the identified weaknesses while
preserving what worked well.

Return your strategy as a JSON object with the following structure:
```json
{{
  "strategy_name": "...",
  "description": "...",
  "signals": [...],
  "filters": [...],
  "entry_conditions": {{...}},
  "exit_conditions": {{...}},
  "position_management": {{...}},
  "optimization_hints": {{...}}
}}
```"""


# =============================================================================
# STRATEGY EVOLUTION ENGINE
# =============================================================================


class StrategyEvolution:
    """
    Self-improving strategy evolution engine.

    Runs an iterative loop of:
        generate → backtest → reflect → rank → evolve

    Each generation builds on feedback from previous ones,
    using real LLM calls for reflection and evolution.

    Example:
        evo = StrategyEvolution()
        result = await evo.evolve(
            symbol="BTCUSDT",
            timeframe="15",
            df=ohlcv_data,
            max_generations=5,
        )
        print(f"Best fitness: {result.best_generation.fitness_score}")
    """

    # Convergence detection
    CONVERGENCE_THRESHOLD = 2.0  # Fitness improvement < 2 points = converged
    MIN_GENERATIONS = 2  # Always run at least 2 generations
    MAX_STAGNANT = 3  # Stop after 3 generations with no improvement

    def __init__(
        self,
        *,
        persist_path: str | None = None,
        rlhf_module: RLHFModule | None = None,
        reflection_engine: SelfReflectionEngine | None = None,
    ):
        """
        Initialize evolution engine.

        Args:
            persist_path: Path to persist evolution data
            rlhf_module: Optional pre-configured RLHF module
            reflection_engine: Optional pre-configured reflection engine
        """
        self.context_builder = MarketContextBuilder()
        self.parser = ResponseParser()
        self.bridge = BacktestBridge()

        # Self-improvement components
        self.rlhf = rlhf_module or RLHFModule(
            persist_path=f"{persist_path}/rlhf" if persist_path else None,
            min_samples_for_training=5,
        )
        self.reflection = reflection_engine or SelfReflectionEngine(
            persist_path=f"{persist_path}/reflections" if persist_path else None,
        )

        # LLM client (initialized lazily)
        self._llm_client = None

        logger.info("🧬 StrategyEvolution engine initialized")

    async def _get_llm_client(self):
        """Lazily initialize LLM client for evolution prompts."""
        if self._llm_client is not None:
            return self._llm_client

        from backend.agents.llm.connections import (
            LLMConfig,
            LLMProvider,
            create_llm_client,
        )
        from backend.security.key_manager import KeyManager

        km = KeyManager()
        api_key = km.get_key("DEEPSEEK_API_KEY")

        if not api_key:
            logger.warning("No DEEPSEEK_API_KEY found, evolution LLM disabled")
            return None

        config = LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            api_key=api_key,
            model="deepseek-chat",
            temperature=0.7,
            max_tokens=4096,
        )
        self._llm_client = create_llm_client(config)
        return self._llm_client

    async def evolve(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        *,
        max_generations: int = 5,
        initial_strategy: StrategyDefinition | None = None,
        initial_capital: float = 10000.0,
        leverage: int = 1,
        direction: str = "both",
        fitness_weights: dict[str, float] | None = None,
        agent_name: str = "deepseek",
    ) -> EvolutionResult:
        """
        Run the full evolution loop.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            timeframe: Timeframe string (e.g., "15", "60", "D")
            df: OHLCV DataFrame
            max_generations: Maximum evolution iterations
            initial_strategy: Optional seed strategy (gen 0)
            initial_capital: Starting capital for backtest
            leverage: Leverage multiplier
            direction: Trade direction ("long", "short", "both")
            fitness_weights: Custom fitness function weights
            agent_name: LLM agent to use for evolution

        Returns:
            EvolutionResult with best strategy and history
        """
        evolution_id = f"evo_{uuid.uuid4().hex[:12]}"
        start_time = time.time()

        logger.info(f"🧬 Evolution started: {evolution_id} | {symbol} {timeframe} | max_gen={max_generations}")

        result = EvolutionResult(
            evolution_id=evolution_id,
            symbol=symbol,
            timeframe=timeframe,
            total_generations=0,
        )

        # Build market context once
        market_ctx = self.context_builder.build_context(symbol, timeframe, df)

        best_fitness = -1.0
        stagnant_count = 0
        current_strategy = initial_strategy

        for gen in range(max_generations):
            gen_start = time.time()
            logger.info(f"🧬 Generation {gen + 1}/{max_generations}")

            # === STEP 1: Generate or evolve strategy ===
            if current_strategy is None:
                # First generation — generate from scratch
                strategy = await self._generate_initial_strategy(market_ctx, agent_name)
            else:
                # Subsequent generations — evolve from previous
                prev_record = result.all_generations[-1] if result.all_generations else None
                strategy = await self._evolve_strategy(
                    current_strategy,
                    prev_record,
                    market_ctx,
                    agent_name,
                )

            if strategy is None:
                logger.warning(f"Generation {gen + 1}: failed to generate strategy")
                stagnant_count += 1
                if stagnant_count >= self.MAX_STAGNANT:
                    result.convergence_reason = "generation_failures"
                    break
                continue

            # === STEP 2: Backtest ===
            backtest_metrics = await self._run_backtest(
                strategy,
                symbol,
                timeframe,
                df,
                initial_capital=initial_capital,
                leverage=leverage,
                direction=direction,
            )

            if not backtest_metrics:
                logger.warning(f"Generation {gen + 1}: backtest failed")
                stagnant_count += 1
                continue

            # === STEP 3: Compute fitness ===
            fitness = compute_fitness(backtest_metrics, fitness_weights)

            # === STEP 4: Reflect on results ===
            reflection = await self._reflect_on_results(strategy, backtest_metrics, fitness)

            # === STEP 5: Record generation ===
            record = GenerationRecord(
                generation=gen + 1,
                strategy=strategy,
                backtest_metrics=backtest_metrics,
                reflection=reflection,
                fitness_score=fitness,
            )
            result.all_generations.append(record)
            result.total_generations = gen + 1

            gen_elapsed = (time.time() - gen_start) * 1000
            logger.info(
                f"🧬 Gen {gen + 1}: fitness={fitness:.1f} | "
                f"sharpe={backtest_metrics.get('sharpe_ratio', 0):.2f} | "
                f"profit={backtest_metrics.get('net_profit', 0):.2f} | "
                f"{gen_elapsed:.0f}ms"
            )

            # === STEP 6: RLHF ranking ===
            if len(result.all_generations) >= 2:
                await self._rank_strategies(result.all_generations)

            # === STEP 7: Convergence check ===
            improvement = fitness - best_fitness
            if fitness > best_fitness:
                best_fitness = fitness
                result.best_generation = record
                stagnant_count = 0
            else:
                stagnant_count += 1

            if gen >= self.MIN_GENERATIONS - 1 and improvement < self.CONVERGENCE_THRESHOLD and stagnant_count >= 2:
                result.converged = True
                result.convergence_reason = f"fitness_plateau (best={best_fitness:.1f}, improvement={improvement:.1f})"
                logger.info(f"🧬 Converged: {result.convergence_reason}")
                break

            if stagnant_count >= self.MAX_STAGNANT:
                result.convergence_reason = f"stagnant ({self.MAX_STAGNANT} generations without improvement)"
                break

            # Use best strategy as seed for next generation
            current_strategy = result.best_generation.strategy if result.best_generation else strategy

        # Finalize
        result.total_duration_ms = (time.time() - start_time) * 1000
        result.rlhf_stats = self.rlhf.get_stats()

        # Collect reflection lessons
        if self.reflection.reflection_history:
            for ref in self.reflection.reflection_history[-max_generations:]:
                result.reflection_summary.extend(ref.lessons_learned[:2])

        logger.info(
            f"🧬 Evolution complete: {result.total_generations} generations | "
            f"best_fitness={best_fitness:.1f} | "
            f"{result.total_duration_ms:.0f}ms"
        )

        return result

    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================

    async def _generate_initial_strategy(
        self,
        market_ctx,
        agent_name: str,
    ) -> StrategyDefinition | None:
        """Generate initial strategy from scratch using LLM."""
        from backend.agents.prompts.prompt_engineer import PromptEngineer

        pe = PromptEngineer()
        prompt = pe.create_strategy_prompt(
            context=market_ctx,
            platform_config={"exchange": "Bybit", "commission": 0.0007},
            agent_name=agent_name,
        )

        client = await self._get_llm_client()
        if not client:
            return None

        try:
            from backend.agents.llm.connections import LLMMessage

            response = await client.chat(
                [
                    LLMMessage(role="system", content=pe.get_system_message(agent_name)),
                    LLMMessage(role="user", content=prompt),
                ]
            )
            return self.parser.parse_strategy(response.content, agent_name=agent_name)
        except Exception as e:
            logger.error(f"Initial strategy generation failed: {e}")
            return None

    async def _evolve_strategy(
        self,
        prev_strategy: StrategyDefinition,
        prev_record: GenerationRecord | None,
        market_ctx,
        agent_name: str,
    ) -> StrategyDefinition | None:
        """Evolve strategy using reflection insights and previous results."""
        client = await self._get_llm_client()
        if not client:
            return None

        # Build evolution prompt with previous results
        metrics = prev_record.backtest_metrics if prev_record else {}
        initial_cap = float(metrics.get("initial_capital", 10000))
        net_profit = float(metrics.get("net_profit", 0))
        net_pct = (net_profit / initial_cap * 100) if initial_cap > 0 else 0

        # Gather reflection insights
        reflection_insights = "No prior reflection available."
        if prev_record and prev_record.reflection:
            ref = prev_record.reflection
            parts = []
            if ref.lessons_learned:
                parts.append("Lessons: " + "; ".join(ref.lessons_learned[:3]))
            if ref.improvement_actions:
                parts.append("Actions: " + "; ".join(ref.improvement_actions[:3]))
            if ref.knowledge_gaps:
                parts.append("Gaps: " + "; ".join(ref.knowledge_gaps[:2]))
            if parts:
                reflection_insights = "\n".join(parts)

        prompt = EVOLUTION_PROMPT_TEMPLATE.format(
            strategy_name=prev_strategy.strategy_name,
            strategy_type=prev_strategy.get_strategy_type_for_engine(),
            strategy_params=prev_strategy.get_engine_params(),
            net_profit=net_profit,
            net_profit_pct=net_pct,
            sharpe_ratio=float(metrics.get("sharpe_ratio", 0)),
            win_rate=float(metrics.get("win_rate", 0)) * 100,
            max_drawdown=float(metrics.get("max_drawdown_pct", 0)),
            profit_factor=float(metrics.get("profit_factor", 0)),
            total_trades=int(metrics.get("total_trades", 0)),
            reflection_insights=reflection_insights,
            market_context=market_ctx.to_prompt_vars().get("indicators_summary", "N/A"),
        )

        try:
            from backend.agents.llm.connections import LLMMessage

            response = await client.chat(
                [
                    LLMMessage(role="system", content=REFLECTION_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=prompt),
                ]
            )
            return self.parser.parse_strategy(response.content, agent_name=f"{agent_name}_evolved")
        except Exception as e:
            logger.error(f"Strategy evolution failed: {e}")
            return None

    async def _run_backtest(
        self,
        strategy: StrategyDefinition,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        *,
        initial_capital: float = 10000.0,
        leverage: int = 1,
        direction: str = "both",
    ) -> dict[str, Any] | None:
        """Run backtest for strategy via BacktestBridge."""
        try:
            return await self.bridge.run_strategy(
                strategy=strategy,
                symbol=symbol,
                timeframe=timeframe,
                df=df,
                initial_capital=initial_capital,
                leverage=leverage,
                direction=direction,
            )
        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            return None

    async def _reflect_on_results(
        self,
        strategy: StrategyDefinition,
        metrics: dict[str, Any],
        fitness: float,
    ) -> ReflectionResult | None:
        """
        Reflect on backtest results using real LLM.

        If LLM is available, uses it for deep analysis.
        Falls back to heuristic reflection otherwise.
        """
        # Build task description for reflection
        task = f"Backtest strategy '{strategy.strategy_name}' ({strategy.get_strategy_type_for_engine()})"
        solution = f"Parameters: {strategy.get_engine_params()}"
        outcome = {
            "success": fitness > 30,
            "fitness_score": fitness,
            "net_profit": metrics.get("net_profit", 0),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0),
            "win_rate": metrics.get("win_rate", 0),
            "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
            "profit_factor": metrics.get("profit_factor", 0),
            "total_trades": metrics.get("total_trades", 0),
        }

        # Try LLM-backed reflection
        client = await self._get_llm_client()
        if client:
            reflection_fn = self._create_llm_reflection_fn(client)
            self.reflection.reflection_fn = reflection_fn

        try:
            return await self.reflection.reflect_on_task(
                task=task,
                solution=solution,
                outcome=outcome,
            )
        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return None

    def _create_llm_reflection_fn(self, client):
        """Create an async reflection function that uses real LLM."""

        async def llm_reflect(prompt: str, task: str, solution: str) -> str:
            from backend.agents.llm.connections import LLMMessage

            full_prompt = (
                f"Reflect on the following trading strategy task:\n\n"
                f"Task: {task}\n"
                f"Solution: {solution}\n\n"
                f"Reflection Question: {prompt}\n\n"
                f"Provide a concise, analytical response (2-4 sentences). "
                f"Be specific about numbers and metrics."
            )
            try:
                response = await client.chat(
                    [
                        LLMMessage(
                            role="system",
                            content=REFLECTION_SYSTEM_PROMPT,
                        ),
                        LLMMessage(role="user", content=full_prompt),
                    ]
                )
                return response.content
            except Exception as e:
                logger.warning(f"LLM reflection failed: {e}")
                return f"Reflection unavailable: {e}"

        return llm_reflect

    async def _rank_strategies(
        self,
        generations: list[GenerationRecord],
    ) -> None:
        """
        Use RLHF to rank strategies via pairwise comparisons.

        Compares the two most recent generations and feeds
        preference signal to the reward model.
        """
        if len(generations) < 2:
            return

        recent = generations[-2:]
        gen_a, gen_b = recent[0], recent[1]

        # Determine preference based on fitness
        if gen_b.fitness_score > gen_a.fitness_score + 1.0:
            preference = 1  # B is better
        elif gen_a.fitness_score > gen_b.fitness_score + 1.0:
            preference = -1  # A is better
        else:
            preference = 0  # Tie

        # Create feedback sample
        sample = FeedbackSample(
            id=f"evo_{uuid.uuid4().hex[:8]}",
            prompt=(f"Generate trading strategy for {gen_a.strategy.get_strategy_type_for_engine()}"),
            response_a=f"Strategy: {gen_a.strategy.strategy_name} | "
            f"Fitness: {gen_a.fitness_score:.1f} | "
            f"Sharpe: {gen_a.backtest_metrics.get('sharpe_ratio', 0):.2f}",
            response_b=f"Strategy: {gen_b.strategy.strategy_name} | "
            f"Fitness: {gen_b.fitness_score:.1f} | "
            f"Sharpe: {gen_b.backtest_metrics.get('sharpe_ratio', 0):.2f}",
            preference=preference,
            preference_type=PreferenceType.AI,
            confidence=min(
                1.0,
                abs(gen_b.fitness_score - gen_a.fitness_score) / 20.0,
            ),
            reasoning=(
                f"Gen {gen_b.generation} fitness={gen_b.fitness_score:.1f} "
                f"vs Gen {gen_a.generation} fitness={gen_a.fitness_score:.1f}"
            ),
            metadata={
                "gen_a": gen_a.generation,
                "gen_b": gen_b.generation,
                "fitness_a": gen_a.fitness_score,
                "fitness_b": gen_b.fitness_score,
            },
        )

        self.rlhf._add_feedback(sample)

        # Train reward model if enough samples
        if len(self.rlhf.feedback_buffer) >= self.rlhf.min_samples_for_training:
            self.rlhf.train_reward_model()

    async def close(self) -> None:
        """Cleanup resources."""
        if self._llm_client:
            import contextlib

            with contextlib.suppress(Exception):
                await self._llm_client.close()
            self._llm_client = None


__all__ = [
    "EvolutionResult",
    "EvolutionStage",
    "GenerationRecord",
    "StrategyEvolution",
    "compute_fitness",
]
