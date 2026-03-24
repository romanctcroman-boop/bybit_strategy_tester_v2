"""
🧬 Tests for Genetic Algorithm Optimizer — Main Optimizer

Integration tests for GeneticOptimizer.
"""

import numpy as np
import pandas as pd

from backend.backtesting.genetic.fitness import (
    MultiObjectiveFitness,
    SharpeRatioFitness,
)
from backend.backtesting.genetic.models import Chromosome, Individual
from backend.backtesting.genetic.optimizer import (
    GeneticOptimizationResult,
    GeneticOptimizer,
)


class MockBacktestEngine:
    """Mock backtest engine for testing"""

    def run(self, data, config):
        """Mock backtest run"""
        strategy = config.get("strategy")

        # Simulate results based on strategy parameters
        # Best params: period=14, threshold=30
        if hasattr(strategy, "period") and hasattr(strategy, "threshold"):
            period = strategy.period
            threshold = strategy.threshold

            # Optimal around period=14, threshold=30
            period_score = 1.0 - abs(period - 14) / 20
            threshold_score = 1.0 - abs(threshold - 30) / 50

            sharpe = (period_score + threshold_score) / 2 * 2.0
            total_return = sharpe * 10
            win_rate = 0.5 + sharpe * 0.1
            max_drawdown = -abs(sharpe * 0.05)
        else:
            sharpe = 0.5
            total_return = 5.0
            win_rate = 0.5
            max_drawdown = -0.1

        return {
            "metrics": {
                "sharpe_ratio": sharpe,
                "total_return": total_return,
                "win_rate": win_rate,
                "max_drawdown": max_drawdown,
                "total_trades": 50,
            }
        }


class MockStrategy:
    """Mock strategy for testing"""

    def __init__(self, period=10, threshold=20):
        self.period = period
        self.threshold = threshold


class TestGeneticOptimizer:
    """Tests for GeneticOptimizer"""

    def test_create_optimizer(self):
        """Test creating optimizer"""
        optimizer = GeneticOptimizer(
            population_size=20,
            n_generations=5,
        )

        assert optimizer.population_size == 20
        assert optimizer.n_generations == 5
        assert optimizer.fitness_function is not None

    def test_create_initial_population(self):
        """Test creating initial population"""
        optimizer = GeneticOptimizer(population_size=10)

        param_ranges = {
            "period": (5, 30),
            "threshold": (10, 50),
        }

        population = optimizer._create_initial_population(param_ranges)

        assert len(population) == 10
        assert all(ind.chromosome.genes.keys() == {"period", "threshold"} for ind in population.individuals)

    def test_optimize(self):
        """Test full optimization run"""
        optimizer = GeneticOptimizer(
            population_size=10,
            n_generations=3,
            fitness_function=SharpeRatioFitness(),
            random_state=42,
        )

        param_ranges = {
            "period": (5, 30),
            "threshold": (10, 50),
        }

        # Mock data
        dates = pd.date_range("2025-01-01", periods=100, freq="D")
        data = pd.DataFrame(
            {
                "open": np.random.randn(100).cumsum() + 100,
                "high": np.random.randn(100).cumsum() + 100,
                "low": np.random.randn(100).cumsum() + 100,
                "close": np.random.randn(100).cumsum() + 100,
            },
            index=dates,
        )

        engine = MockBacktestEngine()

        result = optimizer.optimize(
            strategy_class=MockStrategy,
            param_ranges=param_ranges,
            data=data,
            backtest_engine=engine,
        )

        assert isinstance(result, GeneticOptimizationResult)
        assert result.best_individual is not None
        assert result.best_individual.fitness is not None
        assert len(result.history.best_fitness_per_gen) <= 3
        assert result.n_evaluations > 0

    def test_optimize_with_early_stopping(self):
        """Test optimization with early stopping"""
        optimizer = GeneticOptimizer(
            population_size=10,
            n_generations=100,  # Large number
            early_stopping=True,
            patience=3,
            random_state=42,
        )

        param_ranges = {"period": (5, 30)}

        dates = pd.date_range("2025-01-01", periods=100, freq="D")
        data = pd.DataFrame({"close": np.random.randn(100).cumsum() + 100}, index=dates)

        engine = MockBacktestEngine()

        result = optimizer.optimize(
            strategy_class=MockStrategy,
            param_ranges=param_ranges,
            data=data,
            backtest_engine=engine,
        )

        # Should stop early
        assert len(result.history.best_fitness_per_gen) < 100

    def test_optimize_multi_objective(self):
        """Test multi-objective optimization"""
        optimizer = GeneticOptimizer(
            population_size=10,
            n_generations=3,
            fitness_function=MultiObjectiveFitness(
                weights={
                    "sharpe_ratio": 0.4,
                    "win_rate": 0.3,
                    "max_drawdown": 0.3,
                }
            ),
            random_state=42,
        )

        param_ranges = {
            "period": (5, 30),
            "threshold": (10, 50),
        }

        dates = pd.date_range("2025-01-01", periods=100, freq="D")
        data = pd.DataFrame(
            {
                "close": np.random.randn(100).cumsum() + 100,
            },
            index=dates,
        )

        engine = MockBacktestEngine()

        result = optimizer.optimize(
            strategy_class=MockStrategy,
            param_ranges=param_ranges,
            data=data,
            backtest_engine=engine,
        )

        assert isinstance(result, GeneticOptimizationResult)
        assert result.best_individual.fitness_multi is not None
        assert "sharpe_ratio" in result.best_individual.fitness_multi
        assert "win_rate" in result.best_individual.fitness_multi

    def test_result_to_dict(self):
        """Test result conversion to dictionary"""
        optimizer = GeneticOptimizer(
            population_size=5,
            n_generations=2,
            random_state=42,
        )

        param_ranges = {"period": (5, 30)}

        dates = pd.date_range("2025-01-01", periods=50, freq="D")
        data = pd.DataFrame({"close": np.random.randn(50).cumsum() + 100}, index=dates)

        engine = MockBacktestEngine()

        result = optimizer.optimize(
            strategy_class=MockStrategy,
            param_ranges=param_ranges,
            data=data,
            backtest_engine=engine,
        )

        result_dict = result.to_dict()

        assert "best_individual" in result_dict
        assert "best_fitness" in result_dict
        assert "best_params" in result_dict
        assert "n_evaluations" in result_dict
        assert "execution_time" in result_dict
        assert "generations" in result_dict
        assert "improvement_percent" in result_dict
        assert "history" in result_dict


class TestGeneticOptimizationResult:
    """Tests for GeneticOptimizationResult"""

    def test_result_creation(self):
        """Test creating result"""
        chrom = Chromosome(genes={"period": 14})
        individual = Individual(chromosome=chrom, fitness=1.5)
        population = Population(individuals=[individual])
        history = EvolutionHistory()

        result = GeneticOptimizationResult(
            best_individual=individual,
            population=population,
            history=history,
            n_evaluations=50,
            execution_time=10.5,
        )

        assert result.best_individual == individual
        assert result.n_evaluations == 50
        assert result.execution_time == 10.5


# Import Population and EvolutionHistory for the test above
from backend.backtesting.genetic.models import EvolutionHistory, Population
