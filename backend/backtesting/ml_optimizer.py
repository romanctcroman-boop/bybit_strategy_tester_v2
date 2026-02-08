"""
ML-Based Strategy Optimizer

Implements advanced optimization algorithms:
- Bayesian Optimization (Optuna/TPE)
- Genetic Algorithms (DEAP-style)
- Multi-objective optimization (Pareto front)

Usage:
    from backend.backtesting.ml_optimizer import MLOptimizer

    optimizer = MLOptimizer(
        objective='sharpe_ratio',
        n_trials=100,
        algorithm='bayesian'
    )

    best_params = optimizer.optimize(
        strategy_class=RSIStrategy,
        data=candles,
        param_space={
            'period': (10, 50),
            'overbought': (60, 80),
            'oversold': (20, 40),
        }
    )
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class OptimizationAlgorithm(str, Enum):
    """Available optimization algorithms."""

    BAYESIAN = "bayesian"  # Optuna TPE
    GENETIC = "genetic"  # Genetic Algorithm
    RANDOM = "random"  # Random Search (baseline)
    GRID = "grid"  # Grid Search (exhaustive)


class ObjectiveMetric(str, Enum):
    """Optimization objectives."""

    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    TOTAL_RETURN = "total_return"
    PROFIT_FACTOR = "profit_factor"
    WIN_RATE = "win_rate"
    CALMAR_RATIO = "calmar_ratio"
    MAX_DRAWDOWN = "max_drawdown"  # Minimize
    CUSTOM = "custom"


@dataclass
class ParameterSpace:
    """Definition of parameter search space."""

    name: str
    param_type: str  # 'int', 'float', 'categorical'
    low: float | None = None
    high: float | None = None
    choices: list[Any] | None = None
    step: float | None = None
    log_scale: bool = False

    def suggest(self, trial: Any) -> Any:
        """Suggest a value using Optuna trial."""
        if self.param_type == "int":
            return trial.suggest_int(
                self.name,
                int(self.low),
                int(self.high),
                step=int(self.step) if self.step else 1,
            )
        elif self.param_type == "float":
            if self.log_scale:
                return trial.suggest_float(self.name, self.low, self.high, log=True)
            return trial.suggest_float(self.name, self.low, self.high, step=self.step)
        elif self.param_type == "categorical":
            return trial.suggest_categorical(self.name, self.choices)
        else:
            raise ValueError(f"Unknown param_type: {self.param_type}")


@dataclass
class OptimizationResult:
    """Result of ML optimization."""

    best_params: dict[str, Any]
    best_value: float
    all_trials: list[dict[str, Any]]
    n_trials: int
    duration_seconds: float
    algorithm: str
    objective: str
    pareto_front: list[dict] | None = None

    def to_dict(self) -> dict:
        return {
            "best_params": self.best_params,
            "best_value": round(self.best_value, 6),
            "n_trials": self.n_trials,
            "duration_seconds": round(self.duration_seconds, 2),
            "algorithm": self.algorithm,
            "objective": self.objective,
            "top_10_trials": sorted(
                self.all_trials,
                key=lambda x: x.get("value", float("-inf")),
                reverse=True,
            )[:10],
            "pareto_front": self.pareto_front,
        }


class MLOptimizer:
    """
    ML-based strategy parameter optimizer.

    Supports:
    - Bayesian optimization (Optuna TPE sampler)
    - Genetic algorithms
    - Random search baseline
    - Multi-objective optimization
    """

    def __init__(
        self,
        objective: str = "sharpe_ratio",
        n_trials: int = 100,
        algorithm: str = "bayesian",
        n_jobs: int = 1,
        timeout_seconds: int | None = None,
        seed: int = 42,
    ):
        """
        Initialize ML optimizer.

        Args:
            objective: Metric to optimize (see ObjectiveMetric)
            n_trials: Number of trials to run
            algorithm: Optimization algorithm ('bayesian', 'genetic', 'random')
            n_jobs: Number of parallel jobs
            timeout_seconds: Maximum optimization time
            seed: Random seed for reproducibility
        """
        self.objective = (
            ObjectiveMetric(objective) if isinstance(objective, str) else objective
        )
        self.n_trials = n_trials
        self.algorithm = (
            OptimizationAlgorithm(algorithm)
            if isinstance(algorithm, str)
            else algorithm
        )
        self.n_jobs = n_jobs
        self.timeout_seconds = timeout_seconds
        self.seed = seed

        # State
        self._study = None
        self._trials: list[dict] = []

    def optimize(
        self,
        backtest_func: Callable[..., dict],
        param_space: dict[str, tuple | list | ParameterSpace],
        data: Any = None,
        **backtest_kwargs: Any,
    ) -> OptimizationResult:
        """
        Run optimization.

        Args:
            backtest_func: Function that runs backtest and returns metrics dict
            param_space: Parameter search space
                - tuple (low, high) for int/float ranges
                - list for categorical choices
                - ParameterSpace for full control
            data: Data to pass to backtest_func
            **backtest_kwargs: Additional kwargs for backtest_func

        Returns:
            OptimizationResult with best parameters
        """
        start_time = time.time()

        # Convert param_space to ParameterSpace objects
        spaces = self._parse_param_space(param_space)

        if self.algorithm == OptimizationAlgorithm.BAYESIAN:
            result = self._optimize_bayesian(
                backtest_func, spaces, data, **backtest_kwargs
            )
        elif self.algorithm == OptimizationAlgorithm.GENETIC:
            result = self._optimize_genetic(
                backtest_func, spaces, data, **backtest_kwargs
            )
        elif self.algorithm == OptimizationAlgorithm.RANDOM:
            result = self._optimize_random(
                backtest_func, spaces, data, **backtest_kwargs
            )
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")

        result.duration_seconds = time.time() - start_time
        return result

    def _parse_param_space(self, param_space: dict) -> list[ParameterSpace]:
        """Convert simple param_space to ParameterSpace objects."""
        spaces = []

        for name, spec in param_space.items():
            if isinstance(spec, ParameterSpace):
                spaces.append(spec)
            elif isinstance(spec, tuple) and len(spec) == 2:
                low, high = spec
                if isinstance(low, int) and isinstance(high, int):
                    spaces.append(
                        ParameterSpace(name=name, param_type="int", low=low, high=high)
                    )
                else:
                    spaces.append(
                        ParameterSpace(
                            name=name, param_type="float", low=low, high=high
                        )
                    )
            elif isinstance(spec, list):
                spaces.append(
                    ParameterSpace(name=name, param_type="categorical", choices=spec)
                )
            else:
                raise ValueError(f"Invalid param spec for {name}: {spec}")

        return spaces

    def _optimize_bayesian(
        self,
        backtest_func: Callable,
        spaces: list[ParameterSpace],
        data: Any,
        **kwargs,
    ) -> OptimizationResult:
        """Bayesian optimization using Optuna."""
        try:
            import optuna
            from optuna.samplers import TPESampler

            optuna.logging.set_verbosity(optuna.logging.WARNING)
        except ImportError:
            logger.warning("Optuna not installed, falling back to random search")
            return self._optimize_random(backtest_func, spaces, data, **kwargs)

        # Determine direction
        direction = (
            "minimize" if self.objective == ObjectiveMetric.MAX_DRAWDOWN else "maximize"
        )

        # Create study
        sampler = TPESampler(seed=self.seed)
        self._study = optuna.create_study(
            direction=direction,
            sampler=sampler,
            study_name=f"strategy_optimization_{int(time.time())}",
        )

        def objective(trial: optuna.Trial) -> float:
            # Suggest parameters
            params = {space.name: space.suggest(trial) for space in spaces}

            # Run backtest
            try:
                result = backtest_func(params=params, data=data, **kwargs)
                value = self._extract_metric(result)

                # Track trial
                self._trials.append(
                    {
                        "number": trial.number,
                        "params": params,
                        "value": value,
                        "metrics": result if isinstance(result, dict) else {},
                    }
                )

                return value

            except Exception as e:
                logger.warning(f"Trial {trial.number} failed: {e}")
                return float("-inf") if direction == "maximize" else float("inf")

        # Run optimization
        self._study.optimize(
            objective,
            n_trials=self.n_trials,
            n_jobs=self.n_jobs,
            timeout=self.timeout_seconds,
            show_progress_bar=False,
        )

        return OptimizationResult(
            best_params=self._study.best_params,
            best_value=self._study.best_value,
            all_trials=self._trials,
            n_trials=len(self._trials),
            duration_seconds=0,
            algorithm=self.algorithm.value,
            objective=self.objective.value,
        )

    def _optimize_genetic(
        self,
        backtest_func: Callable,
        spaces: list[ParameterSpace],
        data: Any,
        **kwargs,
    ) -> OptimizationResult:
        """Genetic algorithm optimization."""
        # Simple GA implementation without DEAP
        population_size = min(50, self.n_trials // 2)
        n_generations = self.n_trials // population_size
        mutation_rate = 0.2
        crossover_rate = 0.8

        # Initialize population
        population = [self._random_individual(spaces) for _ in range(population_size)]

        # Evaluate initial population
        fitness = [
            self._evaluate_individual(ind, backtest_func, spaces, data, **kwargs)
            for ind in population
        ]

        best_individual = population[np.argmax(fitness)]
        best_fitness = max(fitness)

        for generation in range(n_generations):
            # Selection (tournament)
            selected = self._tournament_selection(population, fitness, k=3)

            # Crossover
            children = []
            for i in range(0, len(selected) - 1, 2):
                if np.random.random() < crossover_rate:
                    c1, c2 = self._crossover(selected[i], selected[i + 1], spaces)
                    children.extend([c1, c2])
                else:
                    children.extend([selected[i], selected[i + 1]])

            # Mutation
            for child in children:
                if np.random.random() < mutation_rate:
                    self._mutate(child, spaces)

            # Evaluate children
            child_fitness = [
                self._evaluate_individual(ind, backtest_func, spaces, data, **kwargs)
                for ind in children
            ]

            # Replace population
            combined = list(zip(population + children, fitness + child_fitness))
            combined.sort(key=lambda x: x[1], reverse=True)
            population = [x[0] for x in combined[:population_size]]
            fitness = [x[1] for x in combined[:population_size]]

            # Track best
            if fitness[0] > best_fitness:
                best_fitness = fitness[0]
                best_individual = population[0]

            logger.debug(
                f"Generation {generation + 1}/{n_generations}: Best={best_fitness:.4f}"
            )

        # Convert best individual to params dict
        best_params = {space.name: best_individual[i] for i, space in enumerate(spaces)}

        return OptimizationResult(
            best_params=best_params,
            best_value=best_fitness,
            all_trials=self._trials,
            n_trials=len(self._trials),
            duration_seconds=0,
            algorithm=self.algorithm.value,
            objective=self.objective.value,
        )

    def _optimize_random(
        self,
        backtest_func: Callable,
        spaces: list[ParameterSpace],
        data: Any,
        **kwargs,
    ) -> OptimizationResult:
        """Random search baseline."""
        best_params = None
        best_value = float("-inf")

        for trial_num in range(self.n_trials):
            # Random parameters
            params = {}
            for space in spaces:
                if space.param_type == "int":
                    params[space.name] = np.random.randint(
                        int(space.low), int(space.high) + 1
                    )
                elif space.param_type == "float":
                    if space.log_scale:
                        params[space.name] = np.exp(
                            np.random.uniform(np.log(space.low), np.log(space.high))
                        )
                    else:
                        params[space.name] = np.random.uniform(space.low, space.high)
                elif space.param_type == "categorical":
                    params[space.name] = np.random.choice(space.choices)

            # Run backtest
            try:
                result = backtest_func(params=params, data=data, **kwargs)
                value = self._extract_metric(result)

                self._trials.append(
                    {
                        "number": trial_num,
                        "params": params,
                        "value": value,
                        "metrics": result if isinstance(result, dict) else {},
                    }
                )

                if value > best_value:
                    best_value = value
                    best_params = params

            except Exception as e:
                logger.warning(f"Trial {trial_num} failed: {e}")

        return OptimizationResult(
            best_params=best_params or {},
            best_value=best_value,
            all_trials=self._trials,
            n_trials=len(self._trials),
            duration_seconds=0,
            algorithm=self.algorithm.value,
            objective=self.objective.value,
        )

    def _extract_metric(self, result: dict | Any) -> float:
        """Extract optimization metric from backtest result."""
        if isinstance(result, dict):
            metrics = result.get("metrics", result)

            if self.objective == ObjectiveMetric.SHARPE_RATIO:
                return metrics.get("sharpe_ratio", 0)
            elif self.objective == ObjectiveMetric.SORTINO_RATIO:
                return metrics.get("sortino_ratio", 0)
            elif self.objective == ObjectiveMetric.TOTAL_RETURN:
                return metrics.get("total_return", 0)
            elif self.objective == ObjectiveMetric.PROFIT_FACTOR:
                return metrics.get("profit_factor", 0)
            elif self.objective == ObjectiveMetric.WIN_RATE:
                return metrics.get("win_rate", 0)
            elif self.objective == ObjectiveMetric.CALMAR_RATIO:
                return metrics.get("calmar_ratio", 0)
            elif self.objective == ObjectiveMetric.MAX_DRAWDOWN:
                # Return negative so we can maximize (minimize drawdown)
                return -abs(metrics.get("max_drawdown", 100))

        return 0

    def _random_individual(self, spaces: list[ParameterSpace]) -> list:
        """Generate random individual for GA."""
        individual = []
        for space in spaces:
            if space.param_type == "int":
                individual.append(
                    np.random.randint(int(space.low), int(space.high) + 1)
                )
            elif space.param_type == "float":
                individual.append(np.random.uniform(space.low, space.high))
            elif space.param_type == "categorical":
                individual.append(np.random.choice(space.choices))
        return individual

    def _evaluate_individual(
        self,
        individual: list,
        backtest_func: Callable,
        spaces: list[ParameterSpace],
        data: Any,
        **kwargs,
    ) -> float:
        """Evaluate GA individual."""
        params = {space.name: individual[i] for i, space in enumerate(spaces)}

        try:
            result = backtest_func(params=params, data=data, **kwargs)
            value = self._extract_metric(result)

            self._trials.append(
                {
                    "number": len(self._trials),
                    "params": params,
                    "value": value,
                }
            )

            return value

        except Exception as e:
            logger.warning(f"Individual evaluation failed: {e}")
            return float("-inf")

    def _tournament_selection(
        self, population: list, fitness: list, k: int = 3
    ) -> list:
        """Tournament selection for GA."""
        selected = []
        for _ in range(len(population)):
            contestants = np.random.choice(len(population), k, replace=False)
            winner = max(contestants, key=lambda i: fitness[i])
            selected.append(population[winner].copy())
        return selected

    def _crossover(
        self, parent1: list, parent2: list, spaces: list[ParameterSpace]
    ) -> tuple[list, list]:
        """Crossover for GA (blend crossover for numeric, swap for categorical)."""
        child1, child2 = parent1.copy(), parent2.copy()

        for i, space in enumerate(spaces):
            if space.param_type in ("int", "float"):
                # Blend crossover
                alpha = 0.5
                child1[i] = alpha * parent1[i] + (1 - alpha) * parent2[i]
                child2[i] = (1 - alpha) * parent1[i] + alpha * parent2[i]

                if space.param_type == "int":
                    child1[i] = int(round(child1[i]))
                    child2[i] = int(round(child2[i]))

                # Clamp to bounds
                child1[i] = max(space.low, min(space.high, child1[i]))
                child2[i] = max(space.low, min(space.high, child2[i]))

            else:
                # Swap categorical
                if np.random.random() < 0.5:
                    child1[i], child2[i] = child2[i], child1[i]

        return child1, child2

    def _mutate(self, individual: list, spaces: list[ParameterSpace]) -> None:
        """Mutate GA individual in-place."""
        for i, space in enumerate(spaces):
            if np.random.random() < 0.3:  # Gene mutation probability
                if space.param_type == "int":
                    delta = np.random.randint(-2, 3)
                    individual[i] = int(
                        max(space.low, min(space.high, individual[i] + delta))
                    )
                elif space.param_type == "float":
                    delta = np.random.normal(0, (space.high - space.low) * 0.1)
                    individual[i] = max(
                        space.low, min(space.high, individual[i] + delta)
                    )
                elif space.param_type == "categorical":
                    individual[i] = np.random.choice(space.choices)


class MultiObjectiveOptimizer(MLOptimizer):
    """
    Multi-objective optimizer for finding Pareto-optimal solutions.

    Optimizes multiple metrics simultaneously (e.g., maximize Sharpe, minimize drawdown).
    """

    def __init__(
        self,
        objectives: list[str],
        n_trials: int = 100,
        seed: int = 42,
    ):
        super().__init__(n_trials=n_trials, seed=seed)
        self.objectives = [
            ObjectiveMetric(obj) if isinstance(obj, str) else obj for obj in objectives
        ]

    def optimize(
        self,
        backtest_func: Callable,
        param_space: dict,
        data: Any = None,
        **kwargs,
    ) -> OptimizationResult:
        """Run multi-objective optimization."""
        try:
            import optuna
            from optuna.samplers import NSGAIISampler

            optuna.logging.set_verbosity(optuna.logging.WARNING)
        except ImportError:
            raise ImportError("Optuna required for multi-objective optimization")

        spaces = self._parse_param_space(param_space)

        # Determine directions
        directions = []
        for obj in self.objectives:
            if obj == ObjectiveMetric.MAX_DRAWDOWN:
                directions.append("minimize")
            else:
                directions.append("maximize")

        # Create study with NSGA-II
        sampler = NSGAIISampler(seed=self.seed)
        self._study = optuna.create_study(
            directions=directions,
            sampler=sampler,
        )

        def objective(trial: optuna.Trial) -> tuple:
            params = {space.name: space.suggest(trial) for space in spaces}

            try:
                result = backtest_func(params=params, data=data, **kwargs)

                values = []
                for obj in self.objectives:
                    self.objective = obj
                    values.append(self._extract_metric(result))

                self._trials.append(
                    {
                        "number": trial.number,
                        "params": params,
                        "values": values,
                        "metrics": result if isinstance(result, dict) else {},
                    }
                )

                return tuple(values)

            except Exception as e:
                logger.warning(f"Trial {trial.number} failed: {e}")
                return tuple(
                    float("-inf") if d == "maximize" else float("inf")
                    for d in directions
                )

        self._study.optimize(
            objective,
            n_trials=self.n_trials,
            show_progress_bar=False,
        )

        # Extract Pareto front
        pareto_trials = self._study.best_trials
        pareto_front = [
            {
                "params": trial.params,
                "values": {
                    obj.value: trial.values[i] for i, obj in enumerate(self.objectives)
                },
            }
            for trial in pareto_trials
        ]

        # Use first Pareto solution as "best"
        best_trial = pareto_trials[0] if pareto_trials else None

        return OptimizationResult(
            best_params=best_trial.params if best_trial else {},
            best_value=best_trial.values[0] if best_trial else 0,
            all_trials=self._trials,
            n_trials=len(self._trials),
            duration_seconds=0,
            algorithm="nsga2",
            objective=",".join(obj.value for obj in self.objectives),
            pareto_front=pareto_front,
        )
