"""
🤖 Optuna Optimizer Module
Implements Bayesian hyperparameter optimization using Optuna (state-of-the-art)
Based on world best practices 2024-2026
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

# Optuna is optional dependency
try:
    import optuna
    from optuna.pruners import HyperbandPruner, MedianPruner
    from optuna.samplers import CmaEsSampler, RandomSampler, TPESampler

    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    optuna = None  # type: ignore[assignment]

from loguru import logger


@dataclass
class OptunaOptimizationResult:
    """Result container for Optuna optimization"""

    best_params: dict[str, Any]
    best_value: float
    best_trial_number: int
    n_trials: int
    optimization_time_seconds: float
    study_name: str

    # Detailed results
    all_trials: list[dict[str, Any]] = field(default_factory=list)
    pareto_front: list[dict[str, Any]] = field(default_factory=list)  # For multi-objective

    # Convergence info
    value_history: list[float] = field(default_factory=list)
    best_value_history: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "best_params": self.best_params,
            "best_value": round(self.best_value, 6),
            "best_trial_number": self.best_trial_number,
            "n_trials": self.n_trials,
            "optimization_time_seconds": round(self.optimization_time_seconds, 2),
            "study_name": self.study_name,
            "n_pareto_solutions": len(self.pareto_front),
        }


class OptunaOptimizer:
    """
    Optuna-based hyperparameter optimizer for trading strategies.

    Uses Tree-structured Parzen Estimator (TPE) by default, which is
    "efficient for functions that are computationally expensive, noisy,
    or lack gradient information" - Industry standard for trading optimization.

    Features:
    - Single and multi-objective optimization
    - Automatic pruning of unpromising trials
    - Parallel execution support
    - Study persistence for continuation
    """

    def __init__(
        self,
        sampler_type: str = "tpe",
        pruner_type: str = "median",
        seed: int = 42,
        n_startup_trials: int = 10,
        n_warmup_steps: int = 5,
    ):
        """
        Initialize Optuna optimizer.

        Args:
            sampler_type: 'tpe' (default), 'random', or 'cmaes'
            pruner_type: 'median' (default), 'hyperband', or 'none'
            seed: Random seed for reproducibility
            n_startup_trials: Random trials before TPE kicks in
            n_warmup_steps: Steps before pruning can occur
        """
        if not OPTUNA_AVAILABLE:
            raise ImportError("Optuna is not installed. Install with: pip install optuna")

        self.sampler_type = sampler_type
        self.pruner_type = pruner_type
        self.seed = seed
        self.n_startup_trials = n_startup_trials
        self.n_warmup_steps = n_warmup_steps

        # Configure Optuna logging
        optuna.logging.set_verbosity(optuna.logging.WARNING)

    def _create_sampler(self) -> "optuna.samplers.BaseSampler":
        """Create the appropriate sampler"""
        if self.sampler_type == "tpe":
            return TPESampler(
                seed=self.seed,
                n_startup_trials=self.n_startup_trials,
                multivariate=True,  # Better for correlated params
            )
        elif self.sampler_type == "random":
            return RandomSampler(seed=self.seed)
        elif self.sampler_type == "cmaes":
            return CmaEsSampler(seed=self.seed)
        else:
            return TPESampler(seed=self.seed)

    def _create_pruner(self) -> Optional["optuna.pruners.BasePruner"]:
        """Create the appropriate pruner"""
        if self.pruner_type == "median":
            return MedianPruner(
                n_startup_trials=self.n_startup_trials,
                n_warmup_steps=self.n_warmup_steps,
            )
        elif self.pruner_type == "hyperband":
            return HyperbandPruner(min_resource=1, max_resource=100)
        else:
            return None

    def optimize_strategy(
        self,
        objective_fn: Callable,
        param_space: dict[str, Any],
        n_trials: int = 100,
        n_jobs: int = 1,
        timeout: float | None = None,
        study_name: str | None = None,
        direction: str = "maximize",
        show_progress: bool = True,
    ) -> OptunaOptimizationResult:
        """
        Optimize strategy parameters using Bayesian optimization.

        Args:
            objective_fn: Function that takes params dict and returns metric value
            param_space: Dictionary defining parameter search space
                Format: {'param_name': {'type': 'float/int/categorical',
                                        'low': x, 'high': y, 'step': z}}
            n_trials: Number of optimization trials
            n_jobs: Number of parallel jobs (-1 for all CPUs)
            timeout: Maximum optimization time in seconds
            study_name: Name for the study (for persistence)
            direction: 'maximize' or 'minimize'
            show_progress: Show progress bar

        Returns:
            OptunaOptimizationResult with best parameters and metrics
        """
        start_time = datetime.now()

        if study_name is None:
            study_name = f"strategy_opt_{start_time.strftime('%Y%m%d_%H%M%S')}"

        # Create study
        study = optuna.create_study(
            study_name=study_name,
            direction=direction,
            sampler=self._create_sampler(),
            pruner=self._create_pruner(),
        )

        # Create objective wrapper
        def objective(trial: "optuna.Trial") -> float:
            params = self._sample_params(trial, param_space)
            try:
                value = objective_fn(params)
                return value
            except Exception as e:
                logger.warning(f"Trial {trial.number} failed: {e}")
                # Return worst possible value
                return float("-inf") if direction == "maximize" else float("inf")

        # Run optimization
        study.optimize(
            objective,
            n_trials=n_trials,
            n_jobs=n_jobs,
            timeout=timeout,
            show_progress_bar=show_progress,
            gc_after_trial=True,
        )

        end_time = datetime.now()
        optimization_time = (end_time - start_time).total_seconds()

        # Extract results
        best_trial = study.best_trial

        # Collect all trial info
        all_trials = []
        value_history: list[float] = []
        best_value_history: list[float] = []
        running_best = float("-inf") if direction == "maximize" else float("inf")

        for trial in study.trials:
            if trial.state == optuna.trial.TrialState.COMPLETE:
                trial_info = {
                    "number": trial.number,
                    "params": trial.params,
                    "value": trial.value,
                    "datetime": trial.datetime_complete.isoformat() if trial.datetime_complete else None,
                }
                all_trials.append(trial_info)
                trial_val: float = trial.value if trial.value is not None else 0.0
                value_history.append(trial_val)

                running_best = max(running_best, trial_val) if direction == "maximize" else min(running_best, trial_val)
                best_value_history.append(running_best)

        logger.info(f"Optimization complete: {n_trials} trials in {optimization_time:.1f}s")
        logger.info(f"Best value: {best_trial.value:.6f}")
        logger.info(f"Best params: {best_trial.params}")

        best_value: float = best_trial.value if best_trial.value is not None else 0.0

        return OptunaOptimizationResult(
            best_params=best_trial.params,
            best_value=best_value,
            best_trial_number=best_trial.number,
            n_trials=len(all_trials),
            optimization_time_seconds=optimization_time,
            study_name=study_name,
            all_trials=all_trials,
            value_history=value_history,
            best_value_history=best_value_history,
        )

    def optimize_multi_objective(
        self,
        objective_fn: Callable,
        param_space: dict[str, Any],
        n_trials: int = 100,
        n_jobs: int = 1,
        directions: list[str] | None = None,
        metric_names: list[str] | None = None,
        study_name: str | None = None,
    ) -> OptunaOptimizationResult:
        """
        Multi-objective optimization (e.g., maximize Sharpe AND minimize DrawDown).

        Args:
            objective_fn: Function returning tuple of metric values
            param_space: Parameter search space
            n_trials: Number of trials
            n_jobs: Parallel jobs
            directions: List of 'maximize' or 'minimize' for each objective
            metric_names: Names for each metric
            study_name: Study name

        Returns:
            OptunaOptimizationResult with Pareto-optimal solutions
        """
        if directions is None:
            directions = ["maximize", "maximize"]
        if metric_names is None:
            metric_names = ["sharpe", "return"]
        start_time = datetime.now()

        if study_name is None:
            study_name = f"multi_obj_{start_time.strftime('%Y%m%d_%H%M%S')}"

        # Create multi-objective study
        study = optuna.create_study(study_name=study_name, directions=directions, sampler=self._create_sampler())

        def objective(trial: "optuna.Trial") -> tuple:
            params = self._sample_params(trial, param_space)
            try:
                values = objective_fn(params)
                return values
            except Exception as e:
                logger.warning(f"Trial {trial.number} failed: {e}")
                worst_values = tuple(float("-inf") if d == "maximize" else float("inf") for d in directions)
                return worst_values

        study.optimize(
            objective,
            n_trials=n_trials,
            n_jobs=n_jobs,
            show_progress_bar=True,
            gc_after_trial=True,
        )

        end_time = datetime.now()
        optimization_time = (end_time - start_time).total_seconds()

        # Get Pareto front
        pareto_trials = study.best_trials
        pareto_front = []

        for trial in pareto_trials:
            pareto_solution = {
                "number": trial.number,
                "params": trial.params,
                "values": dict(zip(metric_names, trial.values, strict=False)),
            }
            pareto_front.append(pareto_solution)

        # Use first Pareto solution as "best"
        best_trial = pareto_trials[0] if pareto_trials else study.trials[0]

        logger.info(f"Multi-objective optimization complete: {n_trials} trials")
        logger.info(f"Found {len(pareto_front)} Pareto-optimal solutions")

        return OptunaOptimizationResult(
            best_params=best_trial.params,
            best_value=best_trial.values[0] if best_trial.values else 0,
            best_trial_number=best_trial.number,
            n_trials=n_trials,
            optimization_time_seconds=optimization_time,
            study_name=study_name,
            pareto_front=pareto_front,
        )

    def _sample_params(self, trial: "optuna.Trial", param_space: dict[str, Any]) -> dict[str, Any]:
        """Sample parameters from the search space"""
        params = {}

        for name, spec in param_space.items():
            param_type = spec.get("type", "float")

            if param_type == "categorical":
                params[name] = trial.suggest_categorical(name, spec["choices"])
                continue

            # Guard: skip specs where low >= high — Optuna would raise ValueError
            low = spec.get("low", 0)
            high = spec.get("high", 1)
            if low >= high:
                logger.warning(f"_sample_params: skipping param '{name}' — low={low} >= high={high}")
                continue

            if param_type == "float":
                params[name] = trial.suggest_float(
                    name,
                    low,
                    high,
                    step=spec.get("step"),
                    log=spec.get("log", False),
                )
            elif param_type == "int":
                params[name] = trial.suggest_int(name, int(low), int(high), step=spec.get("step", 1))
            elif param_type == "loguniform":
                params[name] = trial.suggest_float(name, low, high, log=True)

        return params


class TradingStrategyOptimizer:
    """
    High-level optimizer for trading strategies.

    Combines Optuna with backtesting engine for easy strategy optimization.
    """

    def __init__(self, backtest_engine, metric: str = "sharpe_ratio", sampler_type: str = "tpe"):
        """
        Initialize trading strategy optimizer.

        Args:
            backtest_engine: Backtest engine instance
            metric: Metric to optimize ('sharpe_ratio', 'sortino_ratio', 'calmar_ratio', etc.)
            sampler_type: Optuna sampler type
        """
        self.engine = backtest_engine
        self.metric = metric
        self.optimizer = OptunaOptimizer(sampler_type=sampler_type)

    def optimize(
        self,
        data,
        strategy_class,
        param_space: dict[str, Any],
        n_trials: int = 100,
        n_jobs: int = 1,
        config_base: dict | None = None,
    ) -> OptunaOptimizationResult:
        """
        Optimize strategy parameters.

        Args:
            data: Market data (DataFrame)
            strategy_class: Strategy class to optimize
            param_space: Parameter search space
            n_trials: Number of trials
            n_jobs: Parallel jobs
            config_base: Base configuration dict

        Returns:
            OptunaOptimizationResult
        """
        config_base = config_base or {}

        def objective(params):
            # Merge with base config
            full_config = {**config_base, **params}

            # Create strategy
            strategy = strategy_class(params=params)
            signals = strategy.generate_signals(data)

            # Run backtest
            result = self.engine.run(full_config, data, signals)

            # Return metric value
            return getattr(result.metrics, self.metric, 0)

        return self.optimizer.optimize_strategy(
            objective_fn=objective,
            param_space=param_space,
            n_trials=n_trials,
            n_jobs=n_jobs,
        )


# Example usage factory function
def create_rsi_param_space() -> dict[str, Any]:
    """Create parameter space for RSI strategy optimization"""
    return {
        "period": {"type": "int", "low": 5, "high": 30, "step": 1},
        "overbought": {"type": "int", "low": 65, "high": 85, "step": 5},
        "oversold": {"type": "int", "low": 15, "high": 35, "step": 5},
    }


def create_sltp_param_space() -> dict[str, Any]:
    """Create parameter space for SL/TP optimization"""
    return {
        "stop_loss": {"type": "float", "low": 0.001, "high": 0.10, "step": 0.005},
        "take_profit": {"type": "float", "low": 0.02, "high": 0.20, "step": 0.01},
    }


def create_full_strategy_param_space() -> dict[str, Any]:
    """Full strategy parameter space"""
    return {
        # Strategy params
        "rsi_period": {"type": "int", "low": 5, "high": 30},
        "rsi_overbought": {"type": "int", "low": 65, "high": 85},
        "rsi_oversold": {"type": "int", "low": 15, "high": 35},
        # Risk params
        "stop_loss": {"type": "float", "low": 0.001, "high": 0.10, "step": 0.005},
        "take_profit": {"type": "float", "low": 0.02, "high": 0.20, "step": 0.01},
        # Position sizing
        "position_size": {"type": "float", "low": 0.1, "high": 1.0, "step": 0.1},
    }
