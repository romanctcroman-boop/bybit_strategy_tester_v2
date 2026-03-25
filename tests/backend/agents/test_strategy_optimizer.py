"""
Tests for StrategyOptimizer — AI strategy parameter optimization.

Tests cover:
- Parameter extraction from StrategyDefinition
- Fitness calculation from metrics
- Genetic algorithm (population, selection, crossover, mutation)
- Grid search optimization
- Bayesian optimization
- Strategy parameter application and detection
- OptimizationResult model
- Edge cases (no params, empty signals, failures)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

from backend.agents.optimization.strategy_optimizer import (
    OptimizableParam,
    OptimizationResult,
    StrategyOptimizer,
)
from backend.agents.prompts.response_parser import (
    ExitCondition,
    ExitConditions,
    Signal,
    StrategyDefinition,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generate sample OHLCV data for backtesting."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2025-01-01", periods=n, freq="15min")
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": close + np.random.randn(n) * 0.1,
            "high": close + abs(np.random.randn(n) * 0.5),
            "low": close - abs(np.random.randn(n) * 0.5),
            "close": close,
            "volume": np.random.randint(100, 10000, n).astype(float),
        }
    )


@pytest.fixture
def rsi_strategy() -> StrategyDefinition:
    """RSI strategy with optimizable parameters."""
    return StrategyDefinition(
        strategy_name="RSI Mean Reversion",
        description="RSI-based strategy for optimization tests",
        signals=[
            Signal(
                id="signal_0",
                type="RSI",
                params={"period": 14, "oversold": 30, "overbought": 70},
                weight=1.0,
                condition="Buy when RSI < oversold",
            ),
        ],
        exit_conditions=ExitConditions(
            take_profit=ExitCondition(type="fixed_pct", value=2.0, description="2% TP"),
            stop_loss=ExitCondition(type="fixed_pct", value=1.0, description="1% SL"),
        ),
    )


@pytest.fixture
def multi_signal_strategy() -> StrategyDefinition:
    """Strategy with multiple signal types."""
    return StrategyDefinition(
        strategy_name="Multi-Signal Strategy",
        description="Multiple indicators for comprehensive testing",
        signals=[
            Signal(
                id="signal_0",
                type="RSI",
                params={"period": 14, "oversold": 30, "overbought": 70},
                weight=0.6,
            ),
            Signal(
                id="signal_1",
                type="EMA_Crossover",
                params={"fast": 9, "slow": 21},
                weight=0.4,
            ),
        ],
        exit_conditions=ExitConditions(
            take_profit=ExitCondition(type="fixed_pct", value=3.0),
            stop_loss=ExitCondition(type="fixed_pct", value=1.5),
        ),
    )


@pytest.fixture
def optimizer() -> StrategyOptimizer:
    """Create optimizer with fixed seed for reproducibility."""
    return StrategyOptimizer(seed=42)


@pytest.fixture
def good_metrics() -> dict:
    """Metrics representing a good strategy."""
    return {
        "sharpe_ratio": 2.5,
        "max_drawdown": 0.1,
        "win_rate": 0.65,
        "profit_factor": 2.0,
    }


@pytest.fixture
def bad_metrics() -> dict:
    """Metrics representing a poor strategy."""
    return {
        "sharpe_ratio": -0.5,
        "max_drawdown": 0.6,
        "win_rate": 0.3,
        "profit_factor": 0.5,
    }


# =============================================================================
# TestOptimizableParam
# =============================================================================


class TestOptimizableParam:
    """Tests for OptimizableParam model."""

    def test_random_value_int(self):
        """random_value returns int within range."""
        p = OptimizableParam(name="test", param_type="int", min_val=5, max_val=20, default_val=10)
        for _ in range(50):
            val = p.random_value()
            assert 5 <= val <= 20
            assert val == int(val)

    def test_random_value_float(self):
        """random_value returns float within range."""
        p = OptimizableParam(name="test", param_type="float", min_val=1.0, max_val=5.0, default_val=3.0)
        for _ in range(50):
            val = p.random_value()
            assert 1.0 <= val <= 5.0

    def test_grid_values_int(self):
        """grid_values generates correct integer grid."""
        p = OptimizableParam(name="test", param_type="int", min_val=5, max_val=15, default_val=10, step=2)
        values = p.grid_values()
        assert all(isinstance(v, int) for v in values)
        assert values[0] == 5
        assert values[-1] <= 15

    def test_grid_values_float(self):
        """grid_values generates correct float grid."""
        p = OptimizableParam(name="test", param_type="float", min_val=1.0, max_val=3.0, default_val=2.0, step=0.5)
        values = p.grid_values()
        assert len(values) >= 2
        assert values[0] == pytest.approx(1.0)

    def test_mutate_within_range(self):
        """mutate keeps value within bounds."""
        p = OptimizableParam(name="test", param_type="int", min_val=5, max_val=20, default_val=10)
        for _ in range(100):
            val = p.mutate(10.0, rate=1.0)  # Always mutate
            assert 5 <= val <= 20

    def test_mutate_preserves_with_low_rate(self):
        """mutate with rate=0 preserves original value."""
        p = OptimizableParam(name="test", param_type="float", min_val=1.0, max_val=5.0, default_val=3.0)
        val = p.mutate(3.0, rate=0.0)
        assert val == 3.0


# =============================================================================
# TestFitnessCalculation
# =============================================================================


class TestFitnessCalculation:
    """Tests for fitness calculation logic."""

    def test_fitness_good_metrics(self, good_metrics):
        """Good metrics yield high fitness."""
        fitness = StrategyOptimizer.calculate_fitness(good_metrics, num_signals=1)
        assert fitness > 1.0

    def test_fitness_bad_metrics(self, bad_metrics):
        """Bad metrics yield low fitness."""
        fitness = StrategyOptimizer.calculate_fitness(bad_metrics, num_signals=1)
        assert fitness < 0.5

    def test_fitness_formula_exact(self):
        """Verify exact fitness formula per spec 3.6.2."""
        metrics = {
            "sharpe_ratio": 1.0,
            "max_drawdown": 0.2,
            "win_rate": 0.5,
            "profit_factor": 1.5,
        }
        expected = 0.4 * 1.0 + 0.3 * (1 - 0.2) + 0.2 * 0.5 + 0.1 * 1.5
        fitness = StrategyOptimizer.calculate_fitness(metrics, num_signals=1)
        assert fitness == pytest.approx(expected, abs=1e-6)

    def test_fitness_complexity_penalty(self):
        """Fitness penalized for > 4 signals."""
        metrics = {"sharpe_ratio": 2.0, "max_drawdown": 0.1, "win_rate": 0.6, "profit_factor": 2.0}
        base = StrategyOptimizer.calculate_fitness(metrics, num_signals=3)
        penalized = StrategyOptimizer.calculate_fitness(metrics, num_signals=5)
        assert penalized == pytest.approx(base * 0.9, abs=1e-6)

    def test_fitness_max_drawdown_percentage_normalization(self):
        """max_drawdown > 1 treated as percentage (0-100)."""
        metrics_pct = {"sharpe_ratio": 1.0, "max_drawdown": 20, "win_rate": 50, "profit_factor": 1.5}
        metrics_ratio = {"sharpe_ratio": 1.0, "max_drawdown": 0.2, "win_rate": 0.5, "profit_factor": 1.5}
        f1 = StrategyOptimizer.calculate_fitness(metrics_pct, 1)
        f2 = StrategyOptimizer.calculate_fitness(metrics_ratio, 1)
        assert f1 == pytest.approx(f2, abs=1e-6)

    def test_fitness_missing_metrics(self):
        """Missing metrics default to 0."""
        fitness = StrategyOptimizer.calculate_fitness({}, num_signals=1)
        # 0.4*0 + 0.3*(1-1) + 0.2*0 + 0.1*0 = 0
        assert fitness == pytest.approx(0.0, abs=1e-6)

    def test_fitness_negative_sharpe(self):
        """Negative sharpe ratio handled correctly."""
        metrics = {"sharpe_ratio": -2.0, "max_drawdown": 0.5, "win_rate": 0.3, "profit_factor": 0.5}
        fitness = StrategyOptimizer.calculate_fitness(metrics, 1)
        assert fitness < 0  # Negative sharpe drags fitness down


# =============================================================================
# TestParameterExtraction
# =============================================================================


class TestParameterExtraction:
    """Tests for extracting optimizable parameters from strategies."""

    def test_extract_rsi_params(self, optimizer, rsi_strategy):
        """RSI strategy yields period, oversold, overbought params."""
        params = optimizer.extract_optimizable_parameters(rsi_strategy)
        names = [p.name for p in params]
        assert "signal_0_period" in names
        assert "signal_0_oversold" in names
        assert "signal_0_overbought" in names

    def test_extract_exit_params(self, optimizer, rsi_strategy):
        """Exit conditions yield take_profit_pct and stop_loss_pct."""
        params = optimizer.extract_optimizable_parameters(rsi_strategy)
        names = [p.name for p in params]
        assert "take_profit_pct" in names
        assert "stop_loss_pct" in names

    def test_extract_multi_signal_params(self, optimizer, multi_signal_strategy):
        """Multi-signal strategy extracts params for each signal."""
        params = optimizer.extract_optimizable_parameters(multi_signal_strategy)
        names = [p.name for p in params]
        # RSI signal
        assert "signal_0_period" in names
        # EMA_Crossover signal
        assert "signal_1_fast" in names
        assert "signal_1_slow" in names

    def test_extract_no_params_unknown_signal(self, optimizer):
        """Unknown signal type yields no signal params."""
        strategy = StrategyDefinition(
            strategy_name="Custom Strategy",
            signals=[Signal(id="s1", type="CustomIndicator", params={"x": 10})],
        )
        params = optimizer.extract_optimizable_parameters(strategy)
        assert len(params) == 0  # No known ranges for CustomIndicator

    def test_extract_no_exit_conditions(self, optimizer):
        """Strategy without exit conditions yields no exit params."""
        strategy = StrategyDefinition(
            strategy_name="No Exits",
            signals=[Signal(id="s1", type="RSI", params={"period": 14})],
        )
        params = optimizer.extract_optimizable_parameters(strategy)
        names = [p.name for p in params]
        assert "take_profit_pct" not in names
        assert "stop_loss_pct" not in names

    def test_param_ranges_correct(self, optimizer, rsi_strategy):
        """Parameter ranges match SIGNAL_PARAM_RANGES config."""
        params = optimizer.extract_optimizable_parameters(rsi_strategy)
        period_param = next(p for p in params if p.name == "signal_0_period")
        assert period_param.min_val == 7
        assert period_param.max_val == 21
        assert period_param.param_type == "int"

    def test_extract_all_supported_signal_types(self, optimizer):
        """All supported signal types have defined ranges."""
        for signal_type in StrategyOptimizer.SIGNAL_PARAM_RANGES:
            strategy = StrategyDefinition(
                strategy_name=f"{signal_type} test",
                signals=[Signal(id="s1", type=signal_type, params={})],
            )
            params = optimizer.extract_optimizable_parameters(strategy)
            assert len(params) > 0, f"No params extracted for {signal_type}"


# =============================================================================
# TestParameterApplication
# =============================================================================


class TestParameterApplication:
    """Tests for applying parameters to strategies."""

    def test_apply_signal_params(self, rsi_strategy):
        """_apply_params updates signal parameters."""
        values = {"signal_0_period": 21, "signal_0_oversold": 25}
        result = StrategyOptimizer._apply_params(rsi_strategy, values)
        assert result.signals[0].params["period"] == 21
        assert result.signals[0].params["oversold"] == 25

    def test_apply_exit_params(self, rsi_strategy):
        """_apply_params updates exit condition values."""
        values = {"take_profit_pct": 4.0, "stop_loss_pct": 2.0}
        result = StrategyOptimizer._apply_params(rsi_strategy, values)
        assert result.exit_conditions.take_profit.value == 4.0
        assert result.exit_conditions.stop_loss.value == 2.0

    def test_apply_preserves_other_fields(self, rsi_strategy):
        """_apply_params preserves strategy_name, description, etc."""
        result = StrategyOptimizer._apply_params(rsi_strategy, {})
        assert result.strategy_name == rsi_strategy.strategy_name
        assert result.description == rsi_strategy.description
        assert len(result.signals) == len(rsi_strategy.signals)

    def test_apply_does_not_mutate_original(self, rsi_strategy):
        """_apply_params creates new object, original unchanged."""
        original_period = rsi_strategy.signals[0].params["period"]
        StrategyOptimizer._apply_params(rsi_strategy, {"signal_0_period": 99})
        assert rsi_strategy.signals[0].params["period"] == original_period


# =============================================================================
# TestExtractCurrentParams
# =============================================================================


class TestExtractCurrentParams:
    """Tests for extracting current param values from strategy."""

    def test_extract_current_rsi(self, optimizer, rsi_strategy):
        """Extracts current RSI parameter values."""
        params = optimizer.extract_optimizable_parameters(rsi_strategy)
        values = StrategyOptimizer._extract_current_params(rsi_strategy, params)
        assert values["signal_0_period"] == 14
        assert values["signal_0_oversold"] == 30
        assert values["signal_0_overbought"] == 70

    def test_extract_current_exit(self, optimizer, rsi_strategy):
        """Extracts current exit condition values."""
        params = optimizer.extract_optimizable_parameters(rsi_strategy)
        values = StrategyOptimizer._extract_current_params(rsi_strategy, params)
        assert values["take_profit_pct"] == 2.0
        assert values["stop_loss_pct"] == 1.0


# =============================================================================
# TestDetectChangedParams
# =============================================================================


class TestDetectChangedParams:
    """Tests for detecting parameter changes."""

    def test_detect_signal_change(self, optimizer, rsi_strategy):
        """Detects changed signal parameters."""
        params = optimizer.extract_optimizable_parameters(rsi_strategy)
        modified = StrategyOptimizer._apply_params(rsi_strategy, {"signal_0_period": 21})
        changed = StrategyOptimizer._detect_changed_params(rsi_strategy, modified, params)
        assert "signal_0_period" in changed

    def test_detect_exit_change(self, optimizer, rsi_strategy):
        """Detects changed exit conditions."""
        params = optimizer.extract_optimizable_parameters(rsi_strategy)
        modified = StrategyOptimizer._apply_params(rsi_strategy, {"take_profit_pct": 4.0})
        changed = StrategyOptimizer._detect_changed_params(rsi_strategy, modified, params)
        assert "take_profit_pct" in changed

    def test_no_changes_detected(self, optimizer, rsi_strategy):
        """No changes when parameters identical."""
        params = optimizer.extract_optimizable_parameters(rsi_strategy)
        same = StrategyOptimizer._apply_params(rsi_strategy, {"signal_0_period": 14})
        changed = StrategyOptimizer._detect_changed_params(rsi_strategy, same, params)
        assert "signal_0_period" not in changed


# =============================================================================
# TestGeneticAlgorithm
# =============================================================================


class TestGeneticAlgorithm:
    """Tests for genetic algorithm optimization."""

    def test_initialize_population(self, optimizer, rsi_strategy):
        """Population initialized with correct size."""
        params = optimizer.extract_optimizable_parameters(rsi_strategy)
        pop = optimizer._initialize_population(rsi_strategy, params, pop_size=10)
        assert len(pop) == 10
        assert pop[0].strategy_name == rsi_strategy.strategy_name

    def test_tournament_selection(self, optimizer, rsi_strategy):
        """Tournament selection returns correct number of individuals."""
        params = optimizer.extract_optimizable_parameters(rsi_strategy)
        pop = optimizer._initialize_population(rsi_strategy, params, pop_size=10)
        fitnesses = [float(i) for i in range(10)]
        selected = optimizer._tournament_selection(pop, fitnesses, k=3)
        assert len(selected) == 10

    def test_crossover_produces_offspring(self, optimizer, rsi_strategy):
        """Crossover produces correct number of offspring."""
        params = optimizer.extract_optimizable_parameters(rsi_strategy)
        pop = optimizer._initialize_population(rsi_strategy, params, pop_size=6)
        offspring = optimizer._crossover(pop, params, crossover_rate=1.0)
        assert len(offspring) >= len(pop) - 1

    def test_mutate_individual(self, optimizer, rsi_strategy):
        """Mutation produces valid strategy."""
        params = optimizer.extract_optimizable_parameters(rsi_strategy)
        mutated = optimizer._mutate_individual(rsi_strategy, params, mutation_rate=1.0)
        assert mutated.strategy_name == rsi_strategy.strategy_name
        assert len(mutated.signals) == len(rsi_strategy.signals)

    @pytest.mark.asyncio
    async def test_genetic_optimization_runs(self, optimizer, rsi_strategy, sample_ohlcv):
        """Genetic optimization completes with mocked evaluator."""
        mock_metrics = {
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.15,
            "win_rate": 0.55,
            "profit_factor": 1.8,
        }
        with patch.object(
            optimizer,
            "_evaluate_strategy",
            new_callable=AsyncMock,
            return_value=StrategyOptimizer.calculate_fitness(mock_metrics, 1),
        ):
            params = optimizer.extract_optimizable_parameters(rsi_strategy)
            eval_ctx = {"df": sample_ohlcv, "symbol": "BTCUSDT", "timeframe": "15"}
            config = {"population_size": 5, "generations": 2, "mutation_rate": 0.1, "crossover_rate": 0.8}
            _best, fitness, history, evals = await optimizer._genetic_optimization(
                rsi_strategy, params, eval_ctx, config
            )
            assert fitness > 0
            assert len(history) == 2
            assert evals == 5 * 2  # pop_size * generations


# =============================================================================
# TestGridSearch
# =============================================================================


class TestGridSearch:
    """Tests for grid search optimization."""

    @pytest.mark.asyncio
    async def test_grid_search_runs(self, optimizer, rsi_strategy, sample_ohlcv):
        """Grid search completes with mocked evaluator."""
        mock_fitness = 1.5
        with patch.object(optimizer, "_evaluate_strategy", new_callable=AsyncMock, return_value=mock_fitness):
            params = optimizer.extract_optimizable_parameters(rsi_strategy)
            eval_ctx = {"df": sample_ohlcv, "symbol": "BTCUSDT", "timeframe": "15"}
            config = {"max_combinations": 5}
            _best, fitness, _history, evals = await optimizer._grid_search_optimization(
                rsi_strategy, params, eval_ctx, config
            )
            assert fitness == mock_fitness
            assert evals <= 5

    def test_sample_grid_combos(self, optimizer, rsi_strategy):
        """Grid combo sampling respects max_combos."""
        params = optimizer.extract_optimizable_parameters(rsi_strategy)
        grid_per_param = [p.grid_values() for p in params]
        combos = optimizer._sample_grid_combos(params, grid_per_param, max_combos=10)
        assert len(combos) == 10


# =============================================================================
# TestBayesianOptimization
# =============================================================================


class TestBayesianOptimization:
    """Tests for bayesian optimization."""

    @pytest.mark.asyncio
    async def test_bayesian_optimization_runs(self, optimizer, rsi_strategy, sample_ohlcv):
        """Bayesian optimization completes with mocked evaluator."""
        call_count = 0

        async def mock_eval(strategy, ctx):
            nonlocal call_count
            call_count += 1
            return 1.0 + call_count * 0.1  # Improving fitness

        with patch.object(optimizer, "_evaluate_strategy", side_effect=mock_eval):
            params = optimizer.extract_optimizable_parameters(rsi_strategy)
            eval_ctx = {"df": sample_ohlcv, "symbol": "BTCUSDT", "timeframe": "15"}
            config = {"n_iter": 8, "init_points": 3}
            _best, fitness, history, evals = await optimizer._bayesian_optimization(
                rsi_strategy, params, eval_ctx, config
            )
            assert evals == 8  # init_points + (n_iter - init_points)
            assert fitness > 1.0
            assert len(history) == 8


# =============================================================================
# TestOptimizeStrategy (full flow)
# =============================================================================


class TestOptimizeStrategy:
    """Tests for the full optimize_strategy method."""

    @pytest.mark.asyncio
    async def test_optimize_strategy_genetic(self, optimizer, rsi_strategy, sample_ohlcv):
        """Full genetic optimization produces OptimizationResult."""
        mock_metrics = {
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.15,
            "win_rate": 0.55,
            "profit_factor": 1.8,
        }
        with patch.object(
            optimizer,
            "_evaluate_strategy",
            new_callable=AsyncMock,
            return_value=StrategyOptimizer.calculate_fitness(mock_metrics, 1),
        ):
            result = await optimizer.optimize_strategy(
                strategy=rsi_strategy,
                df=sample_ohlcv,
                symbol="BTCUSDT",
                timeframe="15",
                method="genetic_algorithm",
                config_overrides={"population_size": 4, "generations": 2},
            )
            assert isinstance(result, OptimizationResult)
            assert result.strategy.strategy_name == rsi_strategy.strategy_name
            assert result.method == "genetic_algorithm"
            assert result.evaluations > 0

    @pytest.mark.asyncio
    async def test_optimize_strategy_grid(self, optimizer, rsi_strategy, sample_ohlcv):
        """Full grid search produces OptimizationResult."""
        with patch.object(optimizer, "_evaluate_strategy", new_callable=AsyncMock, return_value=1.5):
            result = await optimizer.optimize_strategy(
                strategy=rsi_strategy,
                df=sample_ohlcv,
                method="grid_search",
                config_overrides={"max_combinations": 3},
            )
            assert result.method == "grid_search"
            assert result.evaluations <= 3 + 1  # +1 for original eval

    @pytest.mark.asyncio
    async def test_optimize_strategy_bayesian(self, optimizer, rsi_strategy, sample_ohlcv):
        """Full bayesian optimization produces OptimizationResult."""
        with patch.object(optimizer, "_evaluate_strategy", new_callable=AsyncMock, return_value=1.5):
            result = await optimizer.optimize_strategy(
                strategy=rsi_strategy,
                df=sample_ohlcv,
                method="bayesian_optimization",
                config_overrides={"n_iter": 5, "init_points": 2},
            )
            assert result.method == "bayesian_optimization"

    @pytest.mark.asyncio
    async def test_optimize_invalid_method(self, optimizer, rsi_strategy, sample_ohlcv):
        """Invalid method raises ValueError."""
        with pytest.raises(ValueError, match="Unknown optimization method"):
            await optimizer.optimize_strategy(strategy=rsi_strategy, df=sample_ohlcv, method="invalid")

    @pytest.mark.asyncio
    async def test_optimize_no_params(self, optimizer, sample_ohlcv):
        """Strategy with no optimizable params returns original."""
        strategy = StrategyDefinition(
            strategy_name="No Params",
            signals=[Signal(id="s1", type="CustomSignal", params={"x": 5})],
        )
        result = await optimizer.optimize_strategy(strategy=strategy, df=sample_ohlcv)
        assert result.strategy is strategy
        assert result.evaluations == 0

    @pytest.mark.asyncio
    async def test_optimization_history_recorded(self, optimizer, rsi_strategy, sample_ohlcv):
        """Optimization run recorded in history."""
        assert len(optimizer.optimization_history) == 0
        with patch.object(optimizer, "_evaluate_strategy", new_callable=AsyncMock, return_value=1.0):
            await optimizer.optimize_strategy(
                strategy=rsi_strategy,
                df=sample_ohlcv,
                config_overrides={"population_size": 2, "generations": 1},
            )
        assert len(optimizer.optimization_history) == 1
        assert "method" in optimizer.optimization_history[0]


# =============================================================================
# TestOptimizationResult
# =============================================================================


class TestOptimizationResult:
    """Tests for OptimizationResult model."""

    def test_improved_property(self, rsi_strategy):
        """improved returns True when fitness increased."""
        r = OptimizationResult(
            strategy=rsi_strategy,
            original_strategy=rsi_strategy,
            best_fitness=2.0,
            original_fitness=1.0,
        )
        assert r.improved is True

    def test_not_improved(self, rsi_strategy):
        """improved returns False when fitness decreased."""
        r = OptimizationResult(
            strategy=rsi_strategy,
            original_strategy=rsi_strategy,
            best_fitness=0.5,
            original_fitness=1.0,
        )
        assert r.improved is False

    def test_to_dict(self, rsi_strategy):
        """to_dict serialization includes all fields."""
        r = OptimizationResult(
            strategy=rsi_strategy,
            original_strategy=rsi_strategy,
            best_fitness=2.0,
            original_fitness=1.0,
            improvement_pct=100.0,
            method="genetic_algorithm",
            evaluations=50,
            timestamp="2025-01-01T00:00:00Z",
        )
        d = r.to_dict()
        assert d["improved"] is True
        assert d["best_fitness"] == 2.0
        assert d["method"] == "genetic_algorithm"
        assert d["evaluations"] == 50


# =============================================================================
# TestEdgeCases
# =============================================================================


class TestEdgeCases:
    """Edge case and robustness tests."""

    def test_optimizer_seed_reproducibility(self, rsi_strategy):
        """Same seed produces deterministic RNG for selection/crossover/mutation."""
        opt1 = StrategyOptimizer(seed=42)
        opt2 = StrategyOptimizer(seed=42)
        # Verify both start with identical RNG state
        assert opt1._rng.random() == opt2._rng.random()
        # Verify internal state consistency
        assert opt1._seed == opt2._seed == 42

    def test_optimization_methods_constant(self):
        """OPTIMIZATION_METHODS has required keys."""
        assert "genetic_algorithm" in StrategyOptimizer.OPTIMIZATION_METHODS
        assert "grid_search" in StrategyOptimizer.OPTIMIZATION_METHODS
        assert "bayesian_optimization" in StrategyOptimizer.OPTIMIZATION_METHODS

    def test_signal_param_ranges_coverage(self):
        """SIGNAL_PARAM_RANGES covers key indicator types."""
        required = {"RSI", "MACD", "EMA_Crossover", "SMA_Crossover", "Bollinger"}
        assert required.issubset(set(StrategyOptimizer.SIGNAL_PARAM_RANGES.keys()))

    @pytest.mark.asyncio
    async def test_evaluate_strategy_failure(self, optimizer, rsi_strategy, sample_ohlcv):
        """Failed evaluation returns -inf."""
        eval_ctx = {"df": sample_ohlcv, "symbol": "BTCUSDT", "timeframe": "15"}

        # Patch the lazy import inside _evaluate_strategy
        mock_bridge = AsyncMock()
        mock_bridge.run_strategy = AsyncMock(side_effect=RuntimeError("boom"))
        with patch(
            "backend.agents.integration.backtest_bridge.BacktestBridge",
            return_value=mock_bridge,
        ):
            fitness = await optimizer._evaluate_strategy(rsi_strategy, eval_ctx)
            assert fitness == -float("inf")

    def test_five_signal_complexity_penalty(self, optimizer):
        """5+ signals trigger 0.9x fitness penalty."""
        metrics = {"sharpe_ratio": 2.0, "max_drawdown": 0.1, "win_rate": 0.6, "profit_factor": 2.0}
        f3 = StrategyOptimizer.calculate_fitness(metrics, 3)
        f5 = StrategyOptimizer.calculate_fitness(metrics, 5)
        assert f5 < f3
        assert f5 == pytest.approx(f3 * 0.9, abs=1e-6)
