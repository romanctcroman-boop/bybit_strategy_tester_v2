"""
Advanced Optimization Module для Universal Math Engine.

Включает:
1. Bayesian Optimization (Optuna)
2. Genetic Algorithm (DEAP-style)
3. Walk-Forward Analysis
4. Monte Carlo Simulation

Автор: AI Agent
Версия: 1.0.0
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

try:
    from numba import njit, prange

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    prange = range

    def njit(*args, **kwargs):
        def decorator(func):
            return func

        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator


# Try to import optional dependencies
try:
    import optuna

    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    optuna = None


# =============================================================================
# ENUMS
# =============================================================================


class OptimizationMethod(Enum):
    """Методы оптимизации."""

    GRID = "grid"
    RANDOM = "random"
    BAYESIAN = "bayesian"
    GENETIC = "genetic"
    DIFFERENTIAL_EVOLUTION = "differential_evolution"


class WalkForwardMode(Enum):
    """Режимы Walk-Forward."""

    STANDARD = "standard"  # Fixed windows
    ANCHORED = "anchored"  # Expanding window
    ROLLING = "rolling"  # Rolling window


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class BayesianConfig:
    """Конфигурация Bayesian Optimization."""

    n_trials: int = 100
    n_startup_trials: int = 10  # Random trials before Bayesian
    sampler: str = "TPE"  # TPE, CMA-ES, Random
    pruner: str = "median"  # median, hyperband, none

    # Pruning settings
    n_warmup_steps: int = 5

    # Multi-objective
    directions: list[str] = field(default_factory=lambda: ["maximize"])

    # Timeout
    timeout_seconds: int | None = None


@dataclass
class GeneticConfig:
    """Конфигурация Genetic Algorithm."""

    population_size: int = 50
    n_generations: int = 30

    # Selection
    tournament_size: int = 3
    elite_count: int = 2  # Best individuals to preserve

    # Crossover
    crossover_prob: float = 0.7
    crossover_method: str = "two_point"  # uniform, one_point, two_point

    # Mutation
    mutation_prob: float = 0.1
    mutation_sigma: float = 0.2  # Gaussian mutation std

    # Early stopping
    stagnation_generations: int = 10


@dataclass
class WalkForwardConfig:
    """Конфигурация Walk-Forward Analysis."""

    mode: WalkForwardMode = WalkForwardMode.STANDARD

    # Window sizes (as ratios)
    train_ratio: float = 0.7
    test_ratio: float = 0.3

    # Number of folds
    n_folds: int = 5

    # Overlap between folds
    overlap_ratio: float = 0.0

    # Minimum data points per fold
    min_train_samples: int = 100
    min_test_samples: int = 20

    # Re-optimization frequency
    reoptimize_every_fold: bool = True


@dataclass
class MonteCarloConfig:
    """Конфигурация Monte Carlo Simulation."""

    n_simulations: int = 1000

    # Permutation methods
    shuffle_trades: bool = True
    shuffle_returns: bool = False

    # Bootstrap settings
    with_replacement: bool = True
    block_size: int = 1  # For block bootstrap

    # Confidence levels
    confidence_levels: list[float] = field(default_factory=lambda: [0.95, 0.99])

    # Seed for reproducibility
    seed: int | None = None


@dataclass
class WalkForwardResult:
    """Результат Walk-Forward Analysis."""

    fold_results: list[dict[str, Any]]
    in_sample_metrics: dict[str, float]
    out_of_sample_metrics: dict[str, float]
    optimal_params_per_fold: list[dict[str, Any]]
    robustness_ratio: float  # OOS/IS performance ratio
    consistency_score: float  # Percentage of profitable folds


@dataclass
class MonteCarloResult:
    """Результат Monte Carlo Simulation."""

    mean_return: float
    std_return: float
    confidence_intervals: dict[float, tuple[float, float]]
    var_95: float  # Value at Risk
    cvar_95: float  # Conditional VaR
    max_drawdown_distribution: np.ndarray
    win_rate_distribution: np.ndarray
    probability_of_ruin: float
    expected_shortfall: float


# =============================================================================
# NUMBA-ACCELERATED MONTE CARLO
# =============================================================================


@njit(cache=True)
def monte_carlo_shuffle_trades(
    pnls: np.ndarray,
    n_simulations: int,
    seed: int = 42,
) -> np.ndarray:
    """
    Monte Carlo simulation by shuffling trade PnLs.

    Returns:
        Array of shape (n_simulations, n_trades) with permuted PnLs
    """
    np.random.seed(seed)
    n_trades = len(pnls)
    results = np.zeros((n_simulations, n_trades), dtype=np.float64)

    for sim in range(n_simulations):
        # Fisher-Yates shuffle
        permuted = pnls.copy()
        for i in range(n_trades - 1, 0, -1):
            j = np.random.randint(0, i + 1)
            permuted[i], permuted[j] = permuted[j], permuted[i]
        results[sim] = permuted

    return results


@njit(cache=True)
def calculate_equity_curves(
    trade_pnls: np.ndarray,
    initial_capital: float,
) -> np.ndarray:
    """
    Calculate equity curves for multiple simulations.

    Args:
        trade_pnls: Array of shape (n_sims, n_trades)
        initial_capital: Starting capital

    Returns:
        Equity curves of shape (n_sims, n_trades + 1)
    """
    n_sims, n_trades = trade_pnls.shape
    equity = np.zeros((n_sims, n_trades + 1), dtype=np.float64)

    for sim in range(n_sims):
        equity[sim, 0] = initial_capital
        for t in range(n_trades):
            equity[sim, t + 1] = equity[sim, t] + trade_pnls[sim, t]

    return equity


@njit(cache=True)
def calculate_max_drawdowns(equity_curves: np.ndarray) -> np.ndarray:
    """Calculate max drawdown for each simulation."""
    n_sims = equity_curves.shape[0]
    max_dds = np.zeros(n_sims, dtype=np.float64)

    for sim in range(n_sims):
        equity = equity_curves[sim]
        peak = equity[0]
        max_dd = 0.0

        for i in range(len(equity)):
            if equity[i] > peak:
                peak = equity[i]
            dd = (peak - equity[i]) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        max_dds[sim] = max_dd

    return max_dds


@njit(cache=True)
def calculate_final_returns(equity_curves: np.ndarray) -> np.ndarray:
    """Calculate final return for each simulation."""
    n_sims = equity_curves.shape[0]
    returns = np.zeros(n_sims, dtype=np.float64)

    for sim in range(n_sims):
        initial = equity_curves[sim, 0]
        final = equity_curves[sim, -1]
        returns[sim] = (final - initial) / initial if initial > 0 else 0.0

    return returns


@njit(cache=True)
def calculate_win_rates(trade_pnls: np.ndarray) -> np.ndarray:
    """Calculate win rate for each simulation."""
    n_sims, n_trades = trade_pnls.shape
    win_rates = np.zeros(n_sims, dtype=np.float64)

    for sim in range(n_sims):
        wins = 0
        for t in range(n_trades):
            if trade_pnls[sim, t] > 0:
                wins += 1
        win_rates[sim] = wins / n_trades if n_trades > 0 else 0.0

    return win_rates


@njit(cache=True)
def calculate_var_cvar(
    returns: np.ndarray,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Calculate Value at Risk and Conditional VaR.

    Returns:
        (VaR, CVaR) tuple
    """
    n = len(returns)
    sorted_returns = np.sort(returns)

    # VaR: worst return at confidence level
    var_idx = int((1 - confidence) * n)
    var = sorted_returns[var_idx] if var_idx < n else sorted_returns[0]

    # CVaR: average of returns worse than VaR
    cvar_returns = sorted_returns[: var_idx + 1]
    cvar = np.mean(cvar_returns) if len(cvar_returns) > 0 else var

    return var, cvar


# =============================================================================
# GENETIC ALGORITHM
# =============================================================================


class GeneticOptimizer:
    """
    Genetic Algorithm Optimizer.

    DEAP-style implementation without external dependencies.
    """

    def __init__(
        self,
        config: GeneticConfig | None = None,
        param_bounds: dict[str, tuple[float, float]] | None = None,
    ):
        self.config = config or GeneticConfig()
        self.param_bounds = param_bounds or {}
        self.param_names = list(self.param_bounds.keys())
        self.n_params = len(self.param_names)

        # History
        self.population: list[np.ndarray] = []
        self.fitness_history: list[float] = []
        self.best_individual: np.ndarray | None = None
        self.best_fitness: float = float("-inf")

    def _initialize_population(self) -> list[np.ndarray]:
        """Initialize random population."""
        population = []

        for _ in range(self.config.population_size):
            individual = np.zeros(self.n_params)
            for i, name in enumerate(self.param_names):
                low, high = self.param_bounds[name]
                individual[i] = np.random.uniform(low, high)
            population.append(individual)

        return population

    def _decode_individual(self, individual: np.ndarray) -> dict[str, float]:
        """Convert array to parameter dict."""
        return {name: individual[i] for i, name in enumerate(self.param_names)}

    def _encode_params(self, params: dict[str, float]) -> np.ndarray:
        """Convert parameter dict to array."""
        return np.array([params[name] for name in self.param_names])

    def _tournament_select(
        self,
        population: list[np.ndarray],
        fitness: list[float],
    ) -> np.ndarray:
        """Tournament selection."""
        indices = np.random.choice(
            len(population), size=self.config.tournament_size, replace=False
        )
        best_idx = indices[0]
        for idx in indices[1:]:
            if fitness[idx] > fitness[best_idx]:
                best_idx = idx
        return population[best_idx].copy()

    def _crossover(
        self,
        parent1: np.ndarray,
        parent2: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Crossover operation."""
        if np.random.random() > self.config.crossover_prob:
            return parent1.copy(), parent2.copy()

        child1 = parent1.copy()
        child2 = parent2.copy()

        method = self.config.crossover_method

        if method == "uniform":
            for i in range(self.n_params):
                if np.random.random() < 0.5:
                    child1[i], child2[i] = child2[i], child1[i]

        elif method == "one_point":
            if self.n_params > 1:
                point = np.random.randint(1, self.n_params)
                child1[point:] = parent2[point:]
                child2[point:] = parent1[point:]
            else:
                # Only 1 param - just swap
                child1[0], child2[0] = parent2[0], parent1[0]

        elif method == "two_point":
            if self.n_params > 2:
                points = sorted(np.random.choice(self.n_params, 2, replace=False))
                child1[points[0] : points[1]] = parent2[points[0] : points[1]]
                child2[points[0] : points[1]] = parent1[points[0] : points[1]]
            elif self.n_params == 2:
                # Fall back to one-point
                child1[1] = parent2[1]
                child2[1] = parent1[1]
            else:
                # Only 1 param - just swap
                child1[0], child2[0] = parent2[0], parent1[0]

        return child1, child2

    def _mutate(self, individual: np.ndarray) -> np.ndarray:
        """Gaussian mutation."""
        mutant = individual.copy()

        for i, name in enumerate(self.param_names):
            if np.random.random() < self.config.mutation_prob:
                low, high = self.param_bounds[name]
                sigma = (high - low) * self.config.mutation_sigma
                mutant[i] += np.random.normal(0, sigma)
                mutant[i] = np.clip(mutant[i], low, high)

        return mutant

    def optimize(
        self,
        objective_func: Callable[[dict[str, float]], float],
        verbose: bool = True,
    ) -> dict[str, Any]:
        """
        Run genetic algorithm optimization.

        Args:
            objective_func: Function that takes params dict, returns fitness
            verbose: Print progress

        Returns:
            Dict with best_params, best_fitness, history
        """
        # Initialize
        population = self._initialize_population()
        fitness = [objective_func(self._decode_individual(ind)) for ind in population]

        self.fitness_history = [max(fitness)]
        stagnation = 0

        for gen in range(self.config.n_generations):
            # Track best
            best_idx = np.argmax(fitness)
            if fitness[best_idx] > self.best_fitness:
                self.best_fitness = fitness[best_idx]
                self.best_individual = population[best_idx].copy()
                stagnation = 0
            else:
                stagnation += 1

            # Early stopping
            if stagnation >= self.config.stagnation_generations:
                if verbose:
                    print(f"Early stopping at generation {gen} (stagnation)")
                break

            # Elitism - keep best individuals
            elite_indices = np.argsort(fitness)[-self.config.elite_count :]
            new_population = [population[i].copy() for i in elite_indices]
            new_fitness = [fitness[i] for i in elite_indices]

            # Fill rest with offspring
            while len(new_population) < self.config.population_size:
                # Selection
                parent1 = self._tournament_select(population, fitness)
                parent2 = self._tournament_select(population, fitness)

                # Crossover
                child1, child2 = self._crossover(parent1, parent2)

                # Mutation
                child1 = self._mutate(child1)
                child2 = self._mutate(child2)

                # Evaluate
                fit1 = objective_func(self._decode_individual(child1))
                fit2 = objective_func(self._decode_individual(child2))

                new_population.append(child1)
                new_fitness.append(fit1)

                if len(new_population) < self.config.population_size:
                    new_population.append(child2)
                    new_fitness.append(fit2)

            population = new_population
            fitness = new_fitness

            self.fitness_history.append(max(fitness))

            if verbose and (gen + 1) % 5 == 0:
                print(f"Gen {gen + 1}: Best = {max(fitness):.4f}")

        return {
            "best_params": self._decode_individual(self.best_individual),
            "best_fitness": self.best_fitness,
            "generations": len(self.fitness_history),
            "fitness_history": self.fitness_history,
        }


# =============================================================================
# BAYESIAN OPTIMIZATION (OPTUNA WRAPPER)
# =============================================================================


class BayesianOptimizer:
    """
    Bayesian Optimization using Optuna.
    """

    def __init__(
        self,
        config: BayesianConfig | None = None,
        param_bounds: dict[str, tuple[float, float]] | None = None,
        param_types: dict[str, str] | None = None,  # "float", "int", "categorical"
    ):
        if not OPTUNA_AVAILABLE:
            raise ImportError(
                "Optuna is required for Bayesian optimization. "
                "Install with: pip install optuna"
            )

        self.config = config or BayesianConfig()
        self.param_bounds = param_bounds or {}
        self.param_types = param_types or {}

        self.study: Any | None = None
        self.best_params: dict[str, Any] | None = None
        self.best_value: float | None = None

    def _create_sampler(self) -> Any:
        """Create Optuna sampler."""
        sampler_name = self.config.sampler.upper()

        if sampler_name == "TPE":
            return optuna.samplers.TPESampler(
                n_startup_trials=self.config.n_startup_trials
            )
        elif sampler_name == "CMA-ES" or sampler_name == "CMAES":
            return optuna.samplers.CmaEsSampler()
        elif sampler_name == "RANDOM":
            return optuna.samplers.RandomSampler()
        else:
            return optuna.samplers.TPESampler()

    def _create_pruner(self) -> Any:
        """Create Optuna pruner."""
        pruner_name = self.config.pruner.lower()

        if pruner_name == "median":
            return optuna.pruners.MedianPruner(
                n_warmup_steps=self.config.n_warmup_steps
            )
        elif pruner_name == "hyperband":
            return optuna.pruners.HyperbandPruner()
        elif pruner_name == "none":
            return optuna.pruners.NopPruner()
        else:
            return optuna.pruners.MedianPruner()

    def _suggest_params(self, trial: Any) -> dict[str, Any]:
        """Suggest parameters for a trial."""
        params = {}

        for name, bounds in self.param_bounds.items():
            param_type = self.param_types.get(name, "float")

            if param_type == "float":
                params[name] = trial.suggest_float(name, bounds[0], bounds[1])
            elif param_type == "int":
                params[name] = trial.suggest_int(name, int(bounds[0]), int(bounds[1]))
            elif param_type == "categorical":
                params[name] = trial.suggest_categorical(name, bounds)
            elif param_type == "log_float":
                params[name] = trial.suggest_float(name, bounds[0], bounds[1], log=True)

        return params

    def optimize(
        self,
        objective_func: Callable[[dict[str, Any]], float],
        direction: str = "maximize",
        verbose: bool = True,
    ) -> dict[str, Any]:
        """
        Run Bayesian optimization.

        Args:
            objective_func: Function that takes params dict, returns metric
            direction: "maximize" or "minimize"
            verbose: Print progress

        Returns:
            Dict with best_params, best_value, n_trials, history
        """

        # Wrap objective
        def objective(trial):
            params = self._suggest_params(trial)
            return objective_func(params)

        # Create study
        sampler = self._create_sampler()
        pruner = self._create_pruner()

        verbosity = optuna.logging.INFO if verbose else optuna.logging.WARNING
        optuna.logging.set_verbosity(verbosity)

        self.study = optuna.create_study(
            direction=direction,
            sampler=sampler,
            pruner=pruner,
        )

        # Run optimization
        self.study.optimize(
            objective,
            n_trials=self.config.n_trials,
            timeout=self.config.timeout_seconds,
            show_progress_bar=verbose,
        )

        self.best_params = self.study.best_params
        self.best_value = self.study.best_value

        # Get history
        history = [
            {"params": t.params, "value": t.value}
            for t in self.study.trials
            if t.value is not None
        ]

        return {
            "best_params": self.best_params,
            "best_value": self.best_value,
            "n_trials": len(self.study.trials),
            "history": history,
        }


# =============================================================================
# WALK-FORWARD ANALYSIS
# =============================================================================


class WalkForwardAnalyzer:
    """
    Walk-Forward Analysis для стратегий.
    """

    def __init__(self, config: WalkForwardConfig | None = None):
        self.config = config or WalkForwardConfig()
        self.results: WalkForwardResult | None = None

    def _create_folds(
        self,
        n_samples: int,
    ) -> list[tuple[np.ndarray, np.ndarray]]:
        """Create train/test fold indices."""
        folds = []
        n_folds = self.config.n_folds
        mode = self.config.mode

        if mode == WalkForwardMode.STANDARD:
            # Fixed window sizes
            fold_size = n_samples // n_folds
            train_size = int(fold_size * self.config.train_ratio)
            test_size = fold_size - train_size

            for i in range(n_folds):
                start = i * fold_size
                train_end = start + train_size
                test_end = min(start + fold_size, n_samples)

                train_idx = np.arange(start, train_end)
                test_idx = np.arange(train_end, test_end)

                if (
                    len(train_idx) >= self.config.min_train_samples
                    and len(test_idx) >= self.config.min_test_samples
                ):
                    folds.append((train_idx, test_idx))

        elif mode == WalkForwardMode.ANCHORED:
            # Expanding training window
            test_size = n_samples // (n_folds + 1)

            for i in range(n_folds):
                train_end = (i + 1) * test_size
                test_end = min(train_end + test_size, n_samples)

                train_idx = np.arange(0, train_end)
                test_idx = np.arange(train_end, test_end)

                if (
                    len(train_idx) >= self.config.min_train_samples
                    and len(test_idx) >= self.config.min_test_samples
                ):
                    folds.append((train_idx, test_idx))

        elif mode == WalkForwardMode.ROLLING:
            # Rolling window
            total_size = int(n_samples * (1 - self.config.overlap_ratio))
            fold_size = total_size // n_folds
            train_size = int(fold_size * self.config.train_ratio)
            test_size = fold_size - train_size

            step = fold_size - int(fold_size * self.config.overlap_ratio)

            for i in range(n_folds):
                start = i * step
                train_end = start + train_size
                test_end = min(train_end + test_size, n_samples)

                if test_end > n_samples:
                    break

                train_idx = np.arange(start, train_end)
                test_idx = np.arange(train_end, test_end)

                if (
                    len(train_idx) >= self.config.min_train_samples
                    and len(test_idx) >= self.config.min_test_samples
                ):
                    folds.append((train_idx, test_idx))

        return folds

    def analyze(
        self,
        data: np.ndarray,  # OHLCV data
        optimize_func: Callable[[np.ndarray], dict[str, Any]],
        backtest_func: Callable[[np.ndarray, dict[str, Any]], dict[str, float]],
        verbose: bool = True,
    ) -> WalkForwardResult:
        """
        Run Walk-Forward Analysis.

        Args:
            data: OHLCV array
            optimize_func: Function to optimize on training data -> params
            backtest_func: Function to backtest with params -> metrics
            verbose: Print progress

        Returns:
            WalkForwardResult
        """
        n_samples = len(data)
        folds = self._create_folds(n_samples)

        fold_results = []
        optimal_params_per_fold = []
        is_profits = []
        oos_profits = []

        for fold_idx, (train_idx, test_idx) in enumerate(folds):
            if verbose:
                print(
                    f"Fold {fold_idx + 1}/{len(folds)}: "
                    f"Train {len(train_idx)}, Test {len(test_idx)}"
                )

            # Train data
            train_data = data[train_idx]

            # Optimize on training
            if self.config.reoptimize_every_fold or fold_idx == 0:
                opt_result = optimize_func(train_data)
                best_params = opt_result.get("best_params", {})

            optimal_params_per_fold.append(best_params)

            # In-sample backtest
            is_metrics = backtest_func(train_data, best_params)

            # Out-of-sample backtest
            test_data = data[test_idx]
            oos_metrics = backtest_func(test_data, best_params)

            fold_results.append(
                {
                    "fold": fold_idx,
                    "train_size": len(train_idx),
                    "test_size": len(test_idx),
                    "in_sample": is_metrics,
                    "out_of_sample": oos_metrics,
                    "params": best_params,
                }
            )

            is_profits.append(is_metrics.get("total_return", 0))
            oos_profits.append(oos_metrics.get("total_return", 0))

        # Aggregate metrics
        avg_is_return = np.mean(is_profits) if is_profits else 0
        avg_oos_return = np.mean(oos_profits) if oos_profits else 0

        robustness = avg_oos_return / avg_is_return if avg_is_return > 0 else 0
        consistency = (
            sum(1 for p in oos_profits if p > 0) / len(oos_profits)
            if oos_profits
            else 0
        )

        self.results = WalkForwardResult(
            fold_results=fold_results,
            in_sample_metrics={
                "avg_return": avg_is_return,
                "std_return": float(np.std(is_profits)) if is_profits else 0,
            },
            out_of_sample_metrics={
                "avg_return": avg_oos_return,
                "std_return": float(np.std(oos_profits)) if oos_profits else 0,
            },
            optimal_params_per_fold=optimal_params_per_fold,
            robustness_ratio=robustness,
            consistency_score=consistency,
        )

        return self.results


# =============================================================================
# MONTE CARLO SIMULATOR
# =============================================================================


class MonteCarloSimulator:
    """
    Monte Carlo Simulation для оценки риска.
    """

    def __init__(self, config: MonteCarloConfig | None = None):
        self.config = config or MonteCarloConfig()
        self.results: MonteCarloResult | None = None

    def simulate(
        self,
        trade_pnls: np.ndarray,
        initial_capital: float = 10000.0,
        verbose: bool = True,
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation.

        Args:
            trade_pnls: Array of trade PnLs
            initial_capital: Starting capital
            verbose: Print progress

        Returns:
            MonteCarloResult
        """
        if self.config.seed is not None:
            np.random.seed(self.config.seed)

        n_sims = self.config.n_simulations
        seed = self.config.seed or 42

        if verbose:
            print(f"Running {n_sims} Monte Carlo simulations...")

        # Shuffle trades
        permuted_pnls = monte_carlo_shuffle_trades(trade_pnls, n_sims, seed)

        # Calculate equity curves
        equity_curves = calculate_equity_curves(permuted_pnls, initial_capital)

        # Calculate metrics
        final_returns = calculate_final_returns(equity_curves)
        max_drawdowns = calculate_max_drawdowns(equity_curves)
        win_rates = calculate_win_rates(permuted_pnls)

        # Statistics
        mean_return = float(np.mean(final_returns))
        std_return = float(np.std(final_returns))

        # Confidence intervals
        confidence_intervals = {}
        for level in self.config.confidence_levels:
            alpha = 1 - level
            lower = np.percentile(final_returns, alpha / 2 * 100)
            upper = np.percentile(final_returns, (1 - alpha / 2) * 100)
            confidence_intervals[level] = (float(lower), float(upper))

        # VaR and CVaR
        var_95, cvar_95 = calculate_var_cvar(final_returns, 0.95)

        # Probability of ruin (losing 50%+ of capital)
        ruin_threshold = -0.5
        prob_ruin = float(np.mean(final_returns < ruin_threshold))

        # Expected shortfall (average of worst 5%)
        worst_5_pct = np.percentile(final_returns, 5)
        expected_shortfall = float(np.mean(final_returns[final_returns <= worst_5_pct]))

        self.results = MonteCarloResult(
            mean_return=mean_return,
            std_return=std_return,
            confidence_intervals=confidence_intervals,
            var_95=float(var_95),
            cvar_95=float(cvar_95),
            max_drawdown_distribution=max_drawdowns,
            win_rate_distribution=win_rates,
            probability_of_ruin=prob_ruin,
            expected_shortfall=expected_shortfall,
        )

        if verbose:
            print(f"Mean Return: {mean_return:.2%}")
            print(f"Std Return: {std_return:.2%}")
            print(f"VaR 95%: {var_95:.2%}")
            print(f"CVaR 95%: {cvar_95:.2%}")
            print(f"P(Ruin): {prob_ruin:.2%}")

        return self.results


# =============================================================================
# UNIFIED ADVANCED OPTIMIZER
# =============================================================================


class AdvancedOptimizer:
    """
    Unified interface для всех методов оптимизации.
    """

    def __init__(
        self,
        method: OptimizationMethod = OptimizationMethod.BAYESIAN,
        param_bounds: dict[str, tuple[float, float]] | None = None,
        bayesian_config: BayesianConfig | None = None,
        genetic_config: GeneticConfig | None = None,
        walk_forward_config: WalkForwardConfig | None = None,
        monte_carlo_config: MonteCarloConfig | None = None,
    ):
        self.method = method
        self.param_bounds = param_bounds or {}

        self.bayesian_config = bayesian_config
        self.genetic_config = genetic_config
        self.walk_forward_config = walk_forward_config
        self.monte_carlo_config = monte_carlo_config

        self._optimizer: Any | None = None

    def optimize(
        self,
        objective_func: Callable[[dict[str, Any]], float],
        direction: str = "maximize",
        verbose: bool = True,
    ) -> dict[str, Any]:
        """
        Run optimization using selected method.
        """
        if self.method == OptimizationMethod.BAYESIAN:
            if not OPTUNA_AVAILABLE:
                raise ImportError("Optuna required for Bayesian optimization")
            self._optimizer = BayesianOptimizer(
                config=self.bayesian_config,
                param_bounds=self.param_bounds,
            )
            return self._optimizer.optimize(objective_func, direction, verbose)

        elif self.method == OptimizationMethod.GENETIC:
            self._optimizer = GeneticOptimizer(
                config=self.genetic_config,
                param_bounds=self.param_bounds,
            )
            return self._optimizer.optimize(objective_func, verbose)

        elif self.method in (OptimizationMethod.GRID, OptimizationMethod.RANDOM):
            # Import from base optimizer module
            from .optimizer import Optimizer as BaseOptimizer

            base_opt = BaseOptimizer(
                param_bounds=self.param_bounds,
                method="grid" if self.method == OptimizationMethod.GRID else "random",
            )
            return base_opt.optimize(objective_func, verbose=verbose)

        else:
            raise ValueError(f"Unsupported method: {self.method}")

    def walk_forward(
        self,
        data: np.ndarray,
        optimize_func: Callable,
        backtest_func: Callable,
        verbose: bool = True,
    ) -> WalkForwardResult:
        """Run Walk-Forward Analysis."""
        analyzer = WalkForwardAnalyzer(config=self.walk_forward_config)
        return analyzer.analyze(data, optimize_func, backtest_func, verbose)

    def monte_carlo(
        self,
        trade_pnls: np.ndarray,
        initial_capital: float = 10000.0,
        verbose: bool = True,
    ) -> MonteCarloResult:
        """Run Monte Carlo Simulation."""
        simulator = MonteCarloSimulator(config=self.monte_carlo_config)
        return simulator.simulate(trade_pnls, initial_capital, verbose)
