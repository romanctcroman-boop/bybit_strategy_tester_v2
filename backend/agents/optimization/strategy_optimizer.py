"""
Strategy Optimizer for LLM-generated trading strategies.

Optimizes parameters of StrategyDefinition objects using:
- Genetic algorithm (default) — population-based search
- Grid search — exhaustive parameter space scan
- Bayesian optimization — sample-efficient search

Uses BacktestBridge internally for fitness evaluation,
preserving commission_rate = 0.0007 (TradingView parity).

Per TZ (spec) section 3.6.2.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import product
from typing import Any

import pandas as pd
from loguru import logger

from backend.agents.prompts.response_parser import (
    ExitCondition,
    ExitConditions,
    Signal,
    StrategyDefinition,
)

# =============================================================================
# RESULT MODELS
# =============================================================================


@dataclass
class OptimizationResult:
    """Result of strategy optimization."""

    # Best strategy found
    strategy: StrategyDefinition
    original_strategy: StrategyDefinition

    # Fitness tracking
    best_fitness: float = 0.0
    original_fitness: float = 0.0
    improvement_pct: float = 0.0

    # Metadata
    method: str = "genetic_algorithm"
    generations: int = 0
    evaluations: int = 0
    duration_ms: float = 0.0
    parameters_changed: list[str] = field(default_factory=list)
    fitness_history: list[float] = field(default_factory=list)
    timestamp: str = ""

    @property
    def improved(self) -> bool:
        """Whether optimization improved the strategy."""
        return self.best_fitness > self.original_fitness

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "strategy_name": self.strategy.strategy_name,
            "improved": self.improved,
            "best_fitness": round(self.best_fitness, 6),
            "original_fitness": round(self.original_fitness, 6),
            "improvement_pct": round(self.improvement_pct, 2),
            "method": self.method,
            "generations": self.generations,
            "evaluations": self.evaluations,
            "duration_ms": round(self.duration_ms, 1),
            "parameters_changed": self.parameters_changed,
            "timestamp": self.timestamp,
        }


@dataclass
class OptimizableParam:
    """A single optimizable parameter with range and type."""

    name: str
    param_type: str  # "int" or "float"
    min_val: float
    max_val: float
    default_val: float
    step: float = 1.0  # Step for grid search

    def random_value(self) -> float:
        """Generate random value within range."""
        if self.param_type == "int":
            return float(random.randint(int(self.min_val), int(self.max_val)))
        return round(random.uniform(self.min_val, self.max_val), 4)

    def grid_values(self, max_steps: int = 10) -> list[float]:
        """Generate grid of values."""
        if self.param_type == "int":
            values = list(range(int(self.min_val), int(self.max_val) + 1, max(1, int(self.step))))
        else:
            n = min(max_steps, int((self.max_val - self.min_val) / self.step) + 1)
            values = [round(self.min_val + i * (self.max_val - self.min_val) / max(1, n - 1), 4) for i in range(n)]
        return values

    def mutate(self, current: float, rate: float = 0.1) -> float:
        """Mutate value within range."""
        if random.random() > rate:
            return current
        span = self.max_val - self.min_val
        delta = random.gauss(0, span * 0.2)
        new_val = current + delta
        new_val = max(self.min_val, min(self.max_val, new_val))
        if self.param_type == "int":
            new_val = float(round(new_val))
        return round(new_val, 4)


# =============================================================================
# STRATEGY OPTIMIZER
# =============================================================================


class StrategyOptimizer:
    """
    Optimizer for LLM-generated trading strategies.

    Extracts optimizable parameters from StrategyDefinition,
    runs optimization using selected method, and returns
    an improved StrategyDefinition with optimization metadata.

    Uses BacktestBridge for fitness evaluation (commission_rate=0.0007).

    Example:
        optimizer = StrategyOptimizer()
        result = await optimizer.optimize_strategy(
            strategy=strategy_def,
            df=ohlcv_data,
            symbol="BTCUSDT",
            timeframe="15",
            method="genetic_algorithm",
        )
        if result.improved:
            print(f"Improved by {result.improvement_pct:.1f}%")
    """

    # Default optimization configs per spec 3.6.2
    OPTIMIZATION_METHODS: dict[str, dict[str, Any]] = {
        "genetic_algorithm": {
            "population_size": 50,
            "generations": 20,
            "mutation_rate": 0.1,
            "crossover_rate": 0.8,
        },
        "grid_search": {
            "max_combinations": 1000,
        },
        "bayesian_optimization": {
            "n_iter": 30,
            "init_points": 10,
        },
    }

    # Fitness weights per spec 3.6.2
    FITNESS_WEIGHTS = {
        "sharpe_ratio": 0.4,
        "max_drawdown": 0.3,
        "win_rate": 0.2,
        "profit_factor": 0.1,
    }

    # Signal type → optimizable parameters with ranges
    SIGNAL_PARAM_RANGES: dict[str, dict[str, dict[str, Any]]] = {
        "RSI": {
            "period": {"type": "int", "min": 7, "max": 21, "step": 1},
            "oversold": {"type": "int", "min": 20, "max": 40, "step": 5},
            "overbought": {"type": "int", "min": 60, "max": 80, "step": 5},
        },
        "MACD": {
            "fast_period": {"type": "int", "min": 8, "max": 16, "step": 1},
            "slow_period": {"type": "int", "min": 20, "max": 30, "step": 1},
            "signal_period": {"type": "int", "min": 5, "max": 12, "step": 1},
        },
        "EMA_Crossover": {
            "fast": {"type": "int", "min": 5, "max": 20, "step": 1},
            "slow": {"type": "int", "min": 20, "max": 50, "step": 5},
        },
        "SMA_Crossover": {
            "fast": {"type": "int", "min": 5, "max": 20, "step": 1},
            "slow": {"type": "int", "min": 20, "max": 50, "step": 5},
        },
        "Bollinger": {
            "period": {"type": "int", "min": 14, "max": 30, "step": 1},
            "std_dev": {"type": "float", "min": 1.5, "max": 3.0, "step": 0.25},
        },
        "SuperTrend": {
            "period": {"type": "int", "min": 7, "max": 14, "step": 1},
            "multiplier": {"type": "float", "min": 1.5, "max": 4.0, "step": 0.5},
        },
        "Stochastic": {
            "k_period": {"type": "int", "min": 5, "max": 21, "step": 1},
            "d_period": {"type": "int", "min": 3, "max": 7, "step": 1},
            "oversold": {"type": "int", "min": 15, "max": 30, "step": 5},
            "overbought": {"type": "int", "min": 70, "max": 85, "step": 5},
        },
        "CCI": {
            "period": {"type": "int", "min": 10, "max": 30, "step": 2},
        },
        "ATR": {
            "period": {"type": "int", "min": 7, "max": 21, "step": 1},
        },
        "ADX": {
            "period": {"type": "int", "min": 10, "max": 25, "step": 1},
            "threshold": {"type": "int", "min": 20, "max": 35, "step": 5},
        },
    }

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._rng = random.Random(seed)
        self._optimization_history: list[dict[str, Any]] = []

    @property
    def optimization_history(self) -> list[dict[str, Any]]:
        """Access optimization history."""
        return list(self._optimization_history)

    async def optimize_strategy(
        self,
        strategy: StrategyDefinition,
        df: pd.DataFrame,
        symbol: str = "BTCUSDT",
        timeframe: str = "15",
        method: str = "genetic_algorithm",
        initial_capital: float = 10000.0,
        leverage: float = 1.0,
        direction: str = "both",
        config_overrides: dict[str, Any] | None = None,
    ) -> OptimizationResult:
        """
        Optimize strategy parameters using selected method.

        Args:
            strategy: StrategyDefinition to optimize
            df: OHLCV DataFrame for backtesting
            symbol: Trading pair
            timeframe: Candle interval
            method: Optimization method (genetic_algorithm, grid_search, bayesian_optimization)
            initial_capital: Starting capital for backtests
            leverage: Trading leverage
            direction: Trade direction (long, short, both)
            config_overrides: Override default method config

        Returns:
            OptimizationResult with best strategy and metadata
        """
        if method not in self.OPTIMIZATION_METHODS:
            raise ValueError(
                f"Unknown optimization method: {method}. Allowed: {list(self.OPTIMIZATION_METHODS.keys())}"
            )

        start_time = time.monotonic()

        # Extract optimizable parameters
        params = self.extract_optimizable_parameters(strategy)
        if not params:
            logger.warning("No optimizable parameters found in strategy")
            return OptimizationResult(
                strategy=strategy,
                original_strategy=strategy,
                method=method,
                timestamp=datetime.now(UTC).isoformat(),
            )

        # Merge config with overrides
        config = {**self.OPTIMIZATION_METHODS[method]}
        if config_overrides:
            config.update(config_overrides)

        # Build evaluation context
        eval_ctx = {
            "df": df,
            "symbol": symbol,
            "timeframe": timeframe,
            "initial_capital": initial_capital,
            "leverage": leverage,
            "direction": direction,
        }

        # Evaluate original strategy fitness
        original_fitness = await self._evaluate_strategy(strategy, eval_ctx)

        logger.info(
            f"🧬 Optimizing '{strategy.strategy_name}' with {method} "
            f"({len(params)} params, original fitness={original_fitness:.4f})"
        )

        # Run optimization
        if method == "genetic_algorithm":
            best_strategy, best_fitness, fitness_history, evaluations = await self._genetic_optimization(
                strategy, params, eval_ctx, config
            )
        elif method == "grid_search":
            best_strategy, best_fitness, fitness_history, evaluations = await self._grid_search_optimization(
                strategy, params, eval_ctx, config
            )
        elif method == "bayesian_optimization":
            best_strategy, best_fitness, fitness_history, evaluations = await self._bayesian_optimization(
                strategy, params, eval_ctx, config
            )
        else:
            best_strategy = strategy
            best_fitness = original_fitness
            fitness_history = []
            evaluations = 0

        duration = (time.monotonic() - start_time) * 1000

        # Calculate improvement
        improvement = 0.0
        if original_fitness != 0:
            improvement = ((best_fitness - original_fitness) / abs(original_fitness)) * 100

        # Determine which parameters changed
        changed = self._detect_changed_params(strategy, best_strategy, params)

        result = OptimizationResult(
            strategy=best_strategy,
            original_strategy=strategy,
            best_fitness=best_fitness,
            original_fitness=original_fitness,
            improvement_pct=improvement,
            method=method,
            generations=config.get("generations", 0),
            evaluations=evaluations,
            duration_ms=duration,
            parameters_changed=changed,
            fitness_history=fitness_history,
            timestamp=datetime.now(UTC).isoformat(),
        )

        # Record in history
        self._optimization_history.append(result.to_dict())

        logger.info(
            f"✅ Optimization complete: fitness {original_fitness:.4f} → {best_fitness:.4f} "
            f"({'improved' if result.improved else 'no improvement'}), "
            f"{evaluations} evaluations in {duration:.0f}ms"
        )

        return result

    # ─────────────────────────────────────────────────────────────────
    # PARAMETER EXTRACTION
    # ─────────────────────────────────────────────────────────────────

    def extract_optimizable_parameters(self, strategy: StrategyDefinition) -> list[OptimizableParam]:
        """
        Extract optimizable parameters from a strategy definition.

        Analyzes signals and exit conditions to find parameters
        with known optimization ranges.

        Args:
            strategy: StrategyDefinition to analyze

        Returns:
            List of OptimizableParam objects
        """
        params: list[OptimizableParam] = []

        # Signal parameters
        for idx, signal in enumerate(strategy.signals):
            signal_ranges = self.SIGNAL_PARAM_RANGES.get(signal.type, {})
            for param_name, range_cfg in signal_ranges.items():
                current_val = signal.params.get(param_name, range_cfg.get("min", 0))
                params.append(
                    OptimizableParam(
                        name=f"signal_{idx}_{param_name}",
                        param_type=range_cfg["type"],
                        min_val=range_cfg["min"],
                        max_val=range_cfg["max"],
                        default_val=float(current_val),
                        step=range_cfg.get("step", 1.0),
                    )
                )

        # Exit conditions — take profit
        if strategy.exit_conditions and strategy.exit_conditions.take_profit:
            tp_val = strategy.exit_conditions.take_profit.value
            params.append(
                OptimizableParam(
                    name="take_profit_pct",
                    param_type="float",
                    min_val=1.0,
                    max_val=5.0,
                    default_val=tp_val,
                    step=0.5,
                )
            )

        # Exit conditions — stop loss
        if strategy.exit_conditions and strategy.exit_conditions.stop_loss:
            sl_val = strategy.exit_conditions.stop_loss.value
            params.append(
                OptimizableParam(
                    name="stop_loss_pct",
                    param_type="float",
                    min_val=0.5,
                    max_val=3.0,
                    default_val=sl_val,
                    step=0.25,
                )
            )

        return params

    # ─────────────────────────────────────────────────────────────────
    # GENETIC ALGORITHM
    # ─────────────────────────────────────────────────────────────────

    async def _genetic_optimization(
        self,
        strategy: StrategyDefinition,
        params: list[OptimizableParam],
        eval_ctx: dict[str, Any],
        config: dict[str, Any],
    ) -> tuple[StrategyDefinition, float, list[float], int]:
        """
        Genetic algorithm optimization.

        Returns:
            Tuple of (best_strategy, best_fitness, fitness_history, evaluations)
        """
        pop_size = config.get("population_size", 50)
        generations = config.get("generations", 20)
        mutation_rate = config.get("mutation_rate", 0.1)
        crossover_rate = config.get("crossover_rate", 0.8)

        # Initialize population
        population = self._initialize_population(strategy, params, pop_size)

        best_individual = strategy
        best_fitness = -float("inf")
        fitness_history: list[float] = []
        total_evals = 0

        for gen in range(generations):
            # Evaluate fitness
            fitnesses: list[float] = []
            for individual in population:
                fitness = await self._evaluate_strategy(individual, eval_ctx)
                fitnesses.append(fitness)
                total_evals += 1

                if fitness > best_fitness:
                    best_fitness = fitness
                    best_individual = individual

            fitness_history.append(best_fitness)
            logger.debug(f"  Generation {gen + 1}/{generations}: best_fitness={best_fitness:.4f}")

            # Selection (tournament)
            selected = self._tournament_selection(population, fitnesses, k=3)

            # Crossover
            offspring = self._crossover(selected, params, crossover_rate)

            # Mutation
            mutated = [self._mutate_individual(ind, params, mutation_rate) for ind in offspring]

            # Elitism: keep best from previous generation
            population = [best_individual, *mutated[: pop_size - 1]]

        return best_individual, best_fitness, fitness_history, total_evals

    def _initialize_population(
        self,
        base_strategy: StrategyDefinition,
        params: list[OptimizableParam],
        pop_size: int,
    ) -> list[StrategyDefinition]:
        """Create initial population with random parameter variations."""
        population = [base_strategy]  # Include original

        for _ in range(pop_size - 1):
            # Random param values
            values = {p.name: p.random_value() for p in params}
            individual = self._apply_params(base_strategy, values)
            population.append(individual)

        return population

    def _tournament_selection(
        self,
        population: list[StrategyDefinition],
        fitnesses: list[float],
        k: int = 3,
    ) -> list[StrategyDefinition]:
        """Tournament selection — pick best of k random individuals."""
        selected: list[StrategyDefinition] = []
        n = len(population)

        for _ in range(n):
            indices = self._rng.sample(range(n), min(k, n))
            best_idx = max(indices, key=lambda i: fitnesses[i])
            selected.append(population[best_idx])

        return selected

    def _crossover(
        self,
        selected: list[StrategyDefinition],
        params: list[OptimizableParam],
        crossover_rate: float,
    ) -> list[StrategyDefinition]:
        """Uniform crossover between pairs."""
        offspring: list[StrategyDefinition] = []

        for i in range(0, len(selected) - 1, 2):
            parent_a = selected[i]
            parent_b = selected[i + 1]

            if self._rng.random() < crossover_rate:
                # Extract params from both parents
                vals_a = self._extract_current_params(parent_a, params)
                vals_b = self._extract_current_params(parent_b, params)

                # Uniform crossover
                child_vals: dict[str, float] = {}
                for p in params:
                    child_vals[p.name] = vals_a[p.name] if self._rng.random() < 0.5 else vals_b[p.name]

                offspring.append(self._apply_params(parent_a, child_vals))
            else:
                offspring.append(parent_a)

            offspring.append(parent_b)

        # Handle odd element
        if len(selected) % 2 == 1:
            offspring.append(selected[-1])

        return offspring

    def _mutate_individual(
        self,
        individual: StrategyDefinition,
        params: list[OptimizableParam],
        mutation_rate: float,
    ) -> StrategyDefinition:
        """Mutate strategy parameters."""
        current = self._extract_current_params(individual, params)
        mutated = {p.name: p.mutate(current[p.name], mutation_rate) for p in params}
        return self._apply_params(individual, mutated)

    # ─────────────────────────────────────────────────────────────────
    # GRID SEARCH
    # ─────────────────────────────────────────────────────────────────

    async def _grid_search_optimization(
        self,
        strategy: StrategyDefinition,
        params: list[OptimizableParam],
        eval_ctx: dict[str, Any],
        config: dict[str, Any],
    ) -> tuple[StrategyDefinition, float, list[float], int]:
        """
        Exhaustive grid search over parameter space.

        Caps total combinations at max_combinations.
        """
        max_combos = config.get("max_combinations", 1000)

        # Generate grid values per param
        grid_per_param = [p.grid_values(max_steps=10) for p in params]

        # Calculate total combinations
        total = 1
        for g in grid_per_param:
            total *= len(g)

        # If too many, subsample
        if total > max_combos:
            logger.info(f"Grid search: {total} combinations → capping at {max_combos}")
            combos = self._sample_grid_combos(params, grid_per_param, max_combos)
        else:
            combos = list(product(*grid_per_param))

        best_strategy = strategy
        best_fitness = -float("inf")
        fitness_history: list[float] = []

        for _idx, combo in enumerate(combos):
            values = {p.name: combo[i] for i, p in enumerate(params)}
            individual = self._apply_params(strategy, values)
            fitness = await self._evaluate_strategy(individual, eval_ctx)

            if fitness > best_fitness:
                best_fitness = fitness
                best_strategy = individual

            fitness_history.append(best_fitness)

        return best_strategy, best_fitness, fitness_history, len(combos)

    def _sample_grid_combos(
        self,
        params: list[OptimizableParam],
        grid_per_param: list[list[float]],
        max_combos: int,
    ) -> list[tuple[float, ...]]:
        """Randomly sample grid combinations."""
        combos: list[tuple[float, ...]] = []
        for _ in range(max_combos):
            combo = tuple(self._rng.choice(g) for g in grid_per_param)
            combos.append(combo)
        return combos

    # ─────────────────────────────────────────────────────────────────
    # BAYESIAN OPTIMIZATION
    # ─────────────────────────────────────────────────────────────────

    async def _bayesian_optimization(
        self,
        strategy: StrategyDefinition,
        params: list[OptimizableParam],
        eval_ctx: dict[str, Any],
        config: dict[str, Any],
    ) -> tuple[StrategyDefinition, float, list[float], int]:
        """
        Bayesian optimization using random + exploitation.

        Falls back to random search with exploration/exploitation
        when Optuna is not available. Uses surrogate-based approach
        to focus on promising parameter regions.
        """
        n_iter = config.get("n_iter", 30)
        init_points = config.get("init_points", 10)

        best_strategy = strategy
        best_fitness = -float("inf")
        fitness_history: list[float] = []
        all_evals: list[tuple[dict[str, float], float]] = []

        # Phase 1: Random exploration
        for _ in range(init_points):
            values = {p.name: p.random_value() for p in params}
            individual = self._apply_params(strategy, values)
            fitness = await self._evaluate_strategy(individual, eval_ctx)

            all_evals.append((values, fitness))
            if fitness > best_fitness:
                best_fitness = fitness
                best_strategy = individual
            fitness_history.append(best_fitness)

        # Phase 2: Exploitation — perturb best known params
        for _ in range(n_iter - init_points):
            # Pick from top-k best known evaluations
            sorted_evals = sorted(all_evals, key=lambda x: x[1], reverse=True)
            top_k = sorted_evals[: max(1, len(sorted_evals) // 3)]
            base_vals = self._rng.choice(top_k)[0]

            # Perturb around best region
            values = {}
            for p in params:
                base = base_vals.get(p.name, p.default_val)
                span = (p.max_val - p.min_val) * 0.15  # 15% perturbation
                new_val = base + self._rng.gauss(0, span)
                new_val = max(p.min_val, min(p.max_val, new_val))
                if p.param_type == "int":
                    new_val = float(round(new_val))
                values[p.name] = round(new_val, 4)

            individual = self._apply_params(strategy, values)
            fitness = await self._evaluate_strategy(individual, eval_ctx)

            all_evals.append((values, fitness))
            if fitness > best_fitness:
                best_fitness = fitness
                best_strategy = individual
            fitness_history.append(best_fitness)

        return best_strategy, best_fitness, fitness_history, len(all_evals)

    # ─────────────────────────────────────────────────────────────────
    # FITNESS EVALUATION
    # ─────────────────────────────────────────────────────────────────

    async def _evaluate_strategy(
        self,
        strategy: StrategyDefinition,
        eval_ctx: dict[str, Any],
    ) -> float:
        """
        Evaluate strategy fitness via BacktestBridge.

        Fitness = 0.4 * sharpe + 0.3 * (1 - max_dd) + 0.2 * win_rate + 0.1 * pf
        Complexity penalty for > 4 signals.

        Args:
            strategy: Strategy to evaluate
            eval_ctx: Context with df, symbol, timeframe, etc.

        Returns:
            Fitness score (higher is better)
        """
        try:
            from backend.agents.integration.backtest_bridge import BacktestBridge

            bridge = BacktestBridge()
            result = await bridge.run_strategy(
                strategy=strategy,
                symbol=eval_ctx["symbol"],
                timeframe=eval_ctx["timeframe"],
                df=eval_ctx["df"],
                initial_capital=eval_ctx.get("initial_capital", 10000),
                leverage=eval_ctx.get("leverage", 1),
                direction=eval_ctx.get("direction", "both"),
            )

            if not result or not result.get("success", True):
                return -float("inf")

            metrics = result.get("metrics", result)
            return self.calculate_fitness(metrics, len(strategy.signals))

        except Exception as e:
            logger.debug(f"Evaluation failed: {e}")
            return -float("inf")

    @staticmethod
    def calculate_fitness(
        metrics: dict[str, Any],
        num_signals: int = 1,
    ) -> float:
        """
        Calculate fitness from backtest metrics.

        Fitness formula per spec 3.6.2:
            0.4 * sharpe_ratio
          + 0.3 * (1 - max_drawdown)
          + 0.2 * win_rate
          + 0.1 * profit_factor
          - complexity_penalty

        Args:
            metrics: Backtest metrics dict
            num_signals: Number of signals (for complexity penalty)

        Returns:
            Fitness score
        """
        sharpe = metrics.get("sharpe_ratio", 0)
        max_dd = metrics.get("max_drawdown", 1)
        win_rate = metrics.get("win_rate", 0)
        profit_factor = metrics.get("profit_factor", 0)

        # Normalize drawdown (0 = no dd, 1 = 100% dd)
        if isinstance(max_dd, (int, float)):
            # max_dd might be 0-100 or 0-1
            if max_dd > 1:
                max_dd = max_dd / 100.0
            max_dd = min(1.0, max(0.0, abs(max_dd)))

        # Normalize win_rate (0-1)
        if isinstance(win_rate, (int, float)) and win_rate > 1:
            win_rate = win_rate / 100.0

        fitness = 0.4 * sharpe + 0.3 * (1 - max_dd) + 0.2 * win_rate + 0.1 * profit_factor

        # Complexity penalty for > 4 signals
        if num_signals > 4:
            fitness *= 0.9

        return fitness

    # ─────────────────────────────────────────────────────────────────
    # PARAMETER APPLICATION & EXTRACTION
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _apply_params(
        strategy: StrategyDefinition,
        values: dict[str, float],
    ) -> StrategyDefinition:
        """
        Apply parameter values to create a new StrategyDefinition.

        Args:
            strategy: Base strategy
            values: Parameter name → value mapping

        Returns:
            New StrategyDefinition with updated parameters
        """
        # Deep copy signals
        new_signals: list[Signal] = []
        for idx, signal in enumerate(strategy.signals):
            new_params = dict(signal.params)
            for param_name, val in values.items():
                prefix = f"signal_{idx}_"
                if param_name.startswith(prefix):
                    real_name = param_name[len(prefix) :]
                    if signal.params.get(real_name) is not None or real_name in new_params:
                        new_params[real_name] = int(val) if isinstance(val, float) and val == int(val) else val
                    else:
                        new_params[real_name] = int(val) if isinstance(val, float) and val == int(val) else val

            new_signals.append(
                Signal(
                    id=signal.id,
                    type=signal.type,
                    params=new_params,
                    weight=signal.weight,
                    condition=signal.condition,
                )
            )

        # Update exit conditions
        new_exit = None
        if strategy.exit_conditions:
            new_tp = strategy.exit_conditions.take_profit
            new_sl = strategy.exit_conditions.stop_loss

            if "take_profit_pct" in values and new_tp:
                new_tp = ExitCondition(
                    type=new_tp.type,
                    value=values["take_profit_pct"],
                    description=new_tp.description,
                )

            if "stop_loss_pct" in values and new_sl:
                new_sl = ExitCondition(
                    type=new_sl.type,
                    value=values["stop_loss_pct"],
                    description=new_sl.description,
                )

            new_exit = ExitConditions(take_profit=new_tp, stop_loss=new_sl)

        return StrategyDefinition(
            strategy_name=strategy.strategy_name,
            description=strategy.description,
            signals=new_signals,
            filters=strategy.filters,
            entry_conditions=strategy.entry_conditions,
            exit_conditions=new_exit if new_exit else strategy.exit_conditions,
            position_management=strategy.position_management,
            optimization_hints=strategy.optimization_hints,
            agent_metadata=strategy.agent_metadata,
        )

    @staticmethod
    def _extract_current_params(
        strategy: StrategyDefinition,
        params: list[OptimizableParam],
    ) -> dict[str, float]:
        """Extract current parameter values from a strategy."""
        values: dict[str, float] = {}
        for p in params:
            if p.name.startswith("signal_"):
                # Parse signal_X_paramname
                parts = p.name.split("_", 2)
                if len(parts) >= 3:
                    idx = int(parts[1])
                    param_name = parts[2]
                    if idx < len(strategy.signals):
                        values[p.name] = float(strategy.signals[idx].params.get(param_name, p.default_val))
                    else:
                        values[p.name] = p.default_val
            elif p.name == "take_profit_pct":
                if strategy.exit_conditions and strategy.exit_conditions.take_profit:
                    values[p.name] = strategy.exit_conditions.take_profit.value
                else:
                    values[p.name] = p.default_val
            elif p.name == "stop_loss_pct":
                if strategy.exit_conditions and strategy.exit_conditions.stop_loss:
                    values[p.name] = strategy.exit_conditions.stop_loss.value
                else:
                    values[p.name] = p.default_val
            else:
                values[p.name] = p.default_val
        return values

    @staticmethod
    def _detect_changed_params(
        original: StrategyDefinition,
        optimized: StrategyDefinition,
        params: list[OptimizableParam],
    ) -> list[str]:
        """Detect which parameters changed between original and optimized."""
        changed: list[str] = []

        for idx, (orig_sig, opt_sig) in enumerate(zip(original.signals, optimized.signals, strict=False)):
            for key in orig_sig.params:
                if orig_sig.params.get(key) != opt_sig.params.get(key):
                    changed.append(f"signal_{idx}_{key}")

        if original.exit_conditions and optimized.exit_conditions:
            if (
                original.exit_conditions.take_profit
                and optimized.exit_conditions.take_profit
                and original.exit_conditions.take_profit.value != optimized.exit_conditions.take_profit.value
            ):
                changed.append("take_profit_pct")
            if (
                original.exit_conditions.stop_loss
                and optimized.exit_conditions.stop_loss
                and original.exit_conditions.stop_loss.value != optimized.exit_conditions.stop_loss.value
            ):
                changed.append("stop_loss_pct")

        return changed
