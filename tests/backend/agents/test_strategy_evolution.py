"""
Tests for P3: Self-Improvement components.

Tests cover:
- compute_fitness() — fitness function
- StrategyEvolution — evolution loop (with mocked LLM)
- RLHF ranking integration
- SelfReflectionEngine integration
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from backend.agents.prompts.response_parser import StrategyDefinition
from backend.agents.self_improvement.rlhf_module import (
    FeedbackSample,
    PreferenceType,
    RewardModel,
)
from backend.agents.self_improvement.self_reflection import (
    SelfReflectionEngine,
)
from backend.agents.self_improvement.strategy_evolution import (
    EvolutionResult,
    GenerationRecord,
    StrategyEvolution,
    compute_fitness,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generate sample OHLCV data for testing (200 candles)."""
    np.random.seed(42)
    n = 200
    base = 50000.0
    dates = pd.date_range("2025-01-01", periods=n, freq="15min")

    close = base + np.cumsum(np.random.randn(n) * 100)
    high = close + np.abs(np.random.randn(n) * 50)
    low = close - np.abs(np.random.randn(n) * 50)
    op = close + np.random.randn(n) * 20
    volume = np.abs(np.random.randn(n) * 1000) + 100

    return pd.DataFrame(
        {
            "open": op,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )


@pytest.fixture
def sample_strategy() -> StrategyDefinition:
    """Sample strategy definition."""
    return StrategyDefinition(
        strategy_name="RSI Mean Reversion",
        signals=[
            {
                "id": "s1",
                "type": "RSI",
                "params": {"period": 14, "overbought": 70, "oversold": 30},
                "weight": 1.0,
            }
        ],
        exit_conditions={
            "take_profit": {"type": "fixed_pct", "value": 3.0},
            "stop_loss": {"type": "fixed_pct", "value": 2.0},
        },
    )


@pytest.fixture
def good_metrics() -> dict:
    """Metrics representing a good strategy."""
    return {
        "sharpe_ratio": 2.1,
        "profit_factor": 1.8,
        "win_rate": 0.62,
        "net_profit": 1500.0,
        "initial_capital": 10000.0,
        "max_drawdown_pct": 8.0,
        "total_trades": 45,
    }


@pytest.fixture
def bad_metrics() -> dict:
    """Metrics representing a poor strategy."""
    return {
        "sharpe_ratio": -0.5,
        "profit_factor": 0.6,
        "win_rate": 0.35,
        "net_profit": -2000.0,
        "initial_capital": 10000.0,
        "max_drawdown_pct": 35.0,
        "total_trades": 10,
    }


# =============================================================================
# COMPUTE FITNESS TESTS
# =============================================================================


class TestComputeFitness:
    """Tests for the fitness function."""

    def test_good_strategy_high_fitness(self, good_metrics):
        """Good metrics should produce high fitness."""
        score = compute_fitness(good_metrics)
        assert score > 60.0
        assert score <= 100.0

    def test_bad_strategy_low_fitness(self, bad_metrics):
        """Bad metrics should produce low fitness."""
        score = compute_fitness(bad_metrics)
        assert score < 40.0

    def test_fitness_range(self):
        """Fitness should always be 0-100."""
        extreme_good = {
            "sharpe_ratio": 10.0,
            "profit_factor": 5.0,
            "win_rate": 0.95,
            "net_profit": 50000.0,
            "initial_capital": 10000.0,
            "max_drawdown_pct": 1.0,
            "total_trades": 100,
        }
        extreme_bad = {
            "sharpe_ratio": -5.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "net_profit": -10000.0,
            "initial_capital": 10000.0,
            "max_drawdown_pct": 80.0,
            "total_trades": 0,
        }
        assert 0.0 <= compute_fitness(extreme_good) <= 100.0
        assert 0.0 <= compute_fitness(extreme_bad) <= 100.0

    def test_empty_metrics_returns_zero(self):
        """Empty metrics should return minimal fitness."""
        score = compute_fitness({})
        assert score >= 0.0
        assert score < 50.0

    def test_custom_weights(self, good_metrics):
        """Custom weights should change the fitness score."""
        default_score = compute_fitness(good_metrics)
        sharpe_heavy = compute_fitness(
            good_metrics,
            weights={
                "sharpe_ratio": 0.80,
                "profit_factor": 0.05,
                "win_rate": 0.05,
                "net_profit_pct": 0.05,
                "max_drawdown_penalty": 0.025,
                "trade_count_bonus": 0.025,
            },
        )
        # With heavy sharpe weight and sharpe=2.1, score should differ
        assert sharpe_heavy != default_score

    def test_more_trades_higher_bonus(self):
        """More trades should give higher trade count bonus."""
        base = {
            "sharpe_ratio": 1.0,
            "profit_factor": 1.5,
            "win_rate": 0.50,
            "net_profit": 500.0,
            "initial_capital": 10000.0,
            "max_drawdown_pct": 10.0,
        }
        few = {**base, "total_trades": 5}
        many = {**base, "total_trades": 50}
        assert compute_fitness(many) > compute_fitness(few)


# =============================================================================
# REWARD MODEL TESTS
# =============================================================================


class TestRewardModel:
    """Tests for the RLHF RewardModel."""

    def test_extract_features_basic(self):
        """Test feature extraction produces expected keys."""
        model = RewardModel()
        features = model.extract_features("Explain RSI", "RSI is a momentum indicator.")
        assert "length_ratio" in features
        assert "keyword_overlap" in features
        assert "sentiment_score" in features
        assert "structure_score" in features
        assert "specificity_score" in features

    def test_predict_reward_returns_valid_range(self):
        """Reward prediction should be 0-1."""
        model = RewardModel()
        reward = model.predict_reward("test prompt", "test response content")
        assert 0.0 <= reward <= 1.0

    def test_training_updates_weights(self):
        """Training on preferences should update feature weights."""
        model = RewardModel()
        initial_weights = dict(model.feature_weights)

        samples = [
            FeedbackSample(
                id=f"test_{i}",
                prompt="Generate RSI strategy",
                response_a=f"Short response {i}",
                response_b=f"Detailed RSI strategy with period {14 + i}, "
                f"overbought at 70, oversold at 30. This approach "
                f"specifically targets mean reversion.",
                preference=1,
                preference_type=PreferenceType.AI,
                confidence=0.8,
            )
            for i in range(15)
        ]

        result = model.train(samples, epochs=5, use_early_stopping=False)
        assert result["accuracy"] >= 0.0
        assert result["samples"] == 15
        # Weights should have changed
        assert model.feature_weights != initial_weights


# =============================================================================
# SELF-REFLECTION TESTS
# =============================================================================


class TestSelfReflection:
    """Tests for SelfReflectionEngine."""

    @pytest.mark.asyncio
    async def test_reflect_on_task_heuristic(self):
        """Test heuristic reflection (no LLM)."""
        engine = SelfReflectionEngine()

        result = await engine.reflect_on_task(
            task="Generate RSI strategy",
            solution="RSI with period 14, overbought 70, oversold 30",
            outcome={"success": True, "fitness_score": 65.0},
        )

        assert result is not None
        assert result.quality_score > 0
        assert isinstance(result.lessons_learned, list)
        assert isinstance(result.improvement_actions, list)

    @pytest.mark.asyncio
    async def test_reflect_with_custom_fn(self):
        """Test reflection with custom async function."""

        async def custom_reflect(prompt, task, solution):
            return f"Quality: 9/10. The {task} was handled well."

        engine = SelfReflectionEngine(reflection_fn=custom_reflect)

        result = await engine.reflect_on_task(
            task="Generate MACD strategy",
            solution="MACD 12/26/9",
            outcome={"success": True},
        )

        assert result is not None
        assert result.quality_score == 9.0

    @pytest.mark.asyncio
    async def test_stats_updated_after_reflection(self):
        """Test that stats update after reflections."""
        engine = SelfReflectionEngine()

        await engine.reflect_on_task(
            task="Task 1",
            solution="Solution 1",
            outcome={"success": True},
        )
        await engine.reflect_on_task(
            task="Task 2",
            solution="Solution 2",
            outcome={"success": False, "errors": ["timeout"]},
        )

        assert engine.stats["total_reflections"] == 2
        assert engine.stats["avg_quality_score"] > 0


# =============================================================================
# STRATEGY EVOLUTION TESTS
# =============================================================================


class TestStrategyEvolution:
    """Tests for StrategyEvolution (with mocked LLM and backtest)."""

    @pytest.mark.asyncio
    async def test_evolution_basic_flow(self, sample_ohlcv, sample_strategy, good_metrics):
        """Test basic evolution flow with mocked components."""
        evo = StrategyEvolution()

        # Mock LLM client
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = (
            '```json\n{"strategy_name": "Evolved RSI",'
            '"signals": [{"id": "s1", "type": "RSI", '
            '"params": {"period": 21, "overbought": 75, "oversold": 25}}]}\n```'
        )
        mock_client.chat = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()
        evo._llm_client = mock_client

        # Mock backtest
        with patch.object(evo.bridge, "run_strategy", new_callable=AsyncMock) as mock_bt:
            mock_bt.return_value = good_metrics

            result = await evo.evolve(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                max_generations=2,
                initial_strategy=sample_strategy,
            )

        assert isinstance(result, EvolutionResult)
        assert result.total_generations >= 1
        assert result.best_generation is not None
        assert result.best_generation.fitness_score > 0

        await evo.close()

    @pytest.mark.asyncio
    async def test_evolution_convergence(self, sample_ohlcv, sample_strategy):
        """Test that evolution detects convergence."""
        evo = StrategyEvolution()
        evo.CONVERGENCE_THRESHOLD = 5.0
        evo.MIN_GENERATIONS = 2

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = (
            '```json\n{"strategy_name": "Same RSI",'
            '"signals": [{"id": "s1", "type": "RSI", '
            '"params": {"period": 14}}]}\n```'
        )
        mock_client.chat = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()
        evo._llm_client = mock_client

        # Same metrics every time = convergence
        stable_metrics = {
            "sharpe_ratio": 1.5,
            "profit_factor": 1.3,
            "win_rate": 0.55,
            "net_profit": 500.0,
            "initial_capital": 10000.0,
            "max_drawdown_pct": 12.0,
            "total_trades": 30,
        }

        with patch.object(evo.bridge, "run_strategy", new_callable=AsyncMock) as mock_bt:
            mock_bt.return_value = stable_metrics

            result = await evo.evolve(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                max_generations=10,
                initial_strategy=sample_strategy,
            )

        # Should converge before max_generations
        assert result.total_generations < 10
        assert "stagnant" in result.convergence_reason or "plateau" in result.convergence_reason

        await evo.close()

    @pytest.mark.asyncio
    async def test_evolution_handles_backtest_failure(self, sample_ohlcv, sample_strategy):
        """Test that evolution handles backtest failures gracefully."""
        evo = StrategyEvolution()
        evo.MAX_STAGNANT = 2

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = (
            '```json\n{"strategy_name": "Test","signals": [{"id": "s1", "type": "RSI", "params": {"period": 14}}]}\n```'
        )
        mock_client.chat = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()
        evo._llm_client = mock_client

        with patch.object(evo.bridge, "run_strategy", new_callable=AsyncMock) as mock_bt:
            mock_bt.return_value = None  # Backtest fails

            result = await evo.evolve(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                max_generations=5,
                initial_strategy=sample_strategy,
            )

        assert result.best_generation is None
        assert result.total_generations == 0

        await evo.close()

    @pytest.mark.asyncio
    async def test_rlhf_ranking_creates_feedback(self, sample_strategy, good_metrics, bad_metrics):
        """Test that RLHF ranking adds feedback samples."""
        evo = StrategyEvolution()

        gen_a = GenerationRecord(
            generation=1,
            strategy=sample_strategy,
            backtest_metrics=bad_metrics,
            fitness_score=25.0,
        )
        gen_b = GenerationRecord(
            generation=2,
            strategy=sample_strategy,
            backtest_metrics=good_metrics,
            fitness_score=70.0,
        )

        await evo._rank_strategies([gen_a, gen_b])

        assert len(evo.rlhf.feedback_buffer) == 1
        feedback = evo.rlhf.feedback_buffer[0]
        assert feedback.preference == 1  # B is better
        assert feedback.confidence > 0

    def test_generation_record_to_dict(self, sample_strategy, good_metrics):
        """Test serialization of GenerationRecord."""
        record = GenerationRecord(
            generation=1,
            strategy=sample_strategy,
            backtest_metrics=good_metrics,
            fitness_score=72.5,
        )
        d = record.to_dict()
        assert d["generation"] == 1
        assert d["fitness_score"] == 72.5
        assert d["strategy_name"] == "RSI Mean Reversion"
        assert d["sharpe_ratio"] == 2.1

    def test_evolution_result_to_dict(self):
        """Test EvolutionResult serialization."""
        result = EvolutionResult(
            evolution_id="evo_test123",
            symbol="BTCUSDT",
            timeframe="15",
            total_generations=3,
            converged=True,
            convergence_reason="plateau",
            total_duration_ms=5000.0,
        )
        d = result.to_dict()
        assert d["evolution_id"] == "evo_test123"
        assert d["converged"] is True
        assert d["total_generations"] == 3
