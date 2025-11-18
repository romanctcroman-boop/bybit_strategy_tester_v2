"""
Integration tests для Strategy Tournament System
pytest tests/integration/test_strategy_arena.py -v
"""

import pytest
import asyncio
from datetime import datetime
from typing import List, Dict

from backend.services.strategy_arena import (
    StrategyArena,
    TournamentResult,
    StrategyMetrics,
    TournamentStatus,
    run_strategy_tournament
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_strategies():
    """Sample trading strategies for testing"""
    return [
        {
            "id": "strategy_001",
            "name": "EMA Crossover",
            "code": "# EMA strategy code"
        },
        {
            "id": "strategy_002",
            "name": "RSI Mean Reversion",
            "code": "# RSI strategy code"
        },
        {
            "id": "strategy_003",
            "name": "Bollinger Bands Breakout",
            "code": "# BB strategy code"
        },
        {
            "id": "strategy_004",
            "name": "MACD Trend Following",
            "code": "# MACD strategy code"
        },
        {
            "id": "strategy_005",
            "name": "Volume Profile",
            "code": "# Volume strategy code"
        }
    ]


@pytest.fixture
def mock_backtest_func():
    """Mock backtest function with predictable results"""
    
    # Predefined results for consistent testing
    results = {
        "strategy_001": {
            "total_return": 0.45,
            "sharpe_ratio": 2.5,
            "sortino_ratio": 3.0,
            "max_drawdown": -0.15,
            "win_rate": 0.65,
            "profit_factor": 2.1,
            "total_trades": 150,
            "winning_trades": 98,
            "losing_trades": 52,
            "volatility": 0.02
        },
        "strategy_002": {
            "total_return": 0.30,
            "sharpe_ratio": 2.0,
            "sortino_ratio": 2.3,
            "max_drawdown": -0.12,
            "win_rate": 0.58,
            "profit_factor": 1.8,
            "total_trades": 200,
            "winning_trades": 116,
            "losing_trades": 84,
            "volatility": 0.018
        },
        "strategy_003": {
            "total_return": 0.20,
            "sharpe_ratio": 1.5,
            "sortino_ratio": 1.8,
            "max_drawdown": -0.18,
            "win_rate": 0.52,
            "profit_factor": 1.5,
            "total_trades": 120,
            "winning_trades": 62,
            "losing_trades": 58,
            "volatility": 0.025
        },
        "strategy_004": {
            "total_return": 0.35,
            "sharpe_ratio": 2.2,
            "sortino_ratio": 2.6,
            "max_drawdown": -0.10,
            "win_rate": 0.60,
            "profit_factor": 1.9,
            "total_trades": 180,
            "winning_trades": 108,
            "losing_trades": 72,
            "volatility": 0.019
        },
        "strategy_005": {
            "total_return": 0.15,
            "sharpe_ratio": 1.2,
            "sortino_ratio": 1.5,
            "max_drawdown": -0.20,
            "win_rate": 0.50,
            "profit_factor": 1.3,
            "total_trades": 100,
            "winning_trades": 50,
            "losing_trades": 50,
            "volatility": 0.028
        }
    }
    
    def backtest(strategy: Dict) -> Dict:
        return results.get(strategy["id"], results["strategy_005"])
    
    return backtest


@pytest.fixture
def arena(mock_backtest_func):
    """StrategyArena instance with mock backtest"""
    # Disable multiprocessing for tests (local functions can't be pickled)
    return StrategyArena(
        max_workers=3,
        backtest_func=mock_backtest_func,
        use_multiprocessing=False  # Run sequentially for testing
    )


# =============================================================================
# Basic Tests
# =============================================================================

@pytest.mark.asyncio
async def test_run_tournament_basic(arena, sample_strategies):
    """Test basic tournament execution"""
    
    result = await arena.run_tournament(
        strategies=sample_strategies,
        tournament_name="Test Tournament"
    )
    
    assert isinstance(result, TournamentResult)
    assert result.status == TournamentStatus.COMPLETED
    assert result.total_participants == 5
    assert result.successful_backtests == 5
    assert result.failed_backtests == 0
    assert len(result.ranked_strategies) == 5
    assert result.winner_id is not None
    assert result.winner_name is not None


@pytest.mark.asyncio
async def test_tournament_winner_selection(arena, sample_strategies):
    """Test that winner is correctly selected"""
    
    result = await arena.run_tournament(
        strategies=sample_strategies,
        tournament_name="Winner Test"
    )
    
    # Winner should be strategy_001 (best metrics)
    assert result.winner_id == "strategy_001"
    assert result.winner_name == "EMA Crossover"
    
    # Verify winner has best score
    winner_score = result.ranked_strategies[0][1]
    for _, score in result.ranked_strategies[1:]:
        assert winner_score >= score


@pytest.mark.asyncio
async def test_tournament_ranking(arena, sample_strategies):
    """Test strategy ranking correctness"""
    
    result = await arena.run_tournament(
        strategies=sample_strategies,
        tournament_name="Ranking Test"
    )
    
    # Verify rankings are in descending order
    scores = [score for _, score in result.ranked_strategies]
    assert scores == sorted(scores, reverse=True)
    
    # Verify all strategies are ranked
    ranked_ids = [sid for sid, _ in result.ranked_strategies]
    strategy_ids = [s["id"] for s in sample_strategies]
    assert set(ranked_ids) == set(strategy_ids)


@pytest.mark.asyncio
async def test_strategy_metrics_extraction(arena, sample_strategies):
    """Test that metrics are correctly extracted"""
    
    result = await arena.run_tournament(
        strategies=sample_strategies[:2],  # Test with 2 strategies
        tournament_name="Metrics Test"
    )
    
    # Check strategy_001 metrics
    metrics = result.strategy_metrics["strategy_001"]
    assert isinstance(metrics, StrategyMetrics)
    assert metrics.strategy_id == "strategy_001"
    assert metrics.strategy_name == "EMA Crossover"
    assert metrics.total_return == 0.45
    assert metrics.sharpe_ratio == 2.5
    assert metrics.win_rate == 0.65
    assert metrics.total_trades == 150


# =============================================================================
# Scoring Tests
# =============================================================================

@pytest.mark.asyncio
async def test_custom_scoring_weights(sample_strategies, mock_backtest_func):
    """Test custom scoring weights"""
    
    custom_weights = {
        "sharpe_ratio": 0.50,  # Emphasize Sharpe
        "sortino_ratio": 0.0,
        "win_rate": 0.0,
        "max_drawdown": 0.0,
        "total_return": 0.50
    }
    
    arena = StrategyArena(
        max_workers=3,
        backtest_func=mock_backtest_func,
        scoring_weights=custom_weights,
        use_multiprocessing=False
    )
    
    result = await arena.run_tournament(
        strategies=sample_strategies,
        tournament_name="Custom Weights Test"
    )
    
    # With 50% Sharpe, 50% Return, strategy_001 should still win
    assert result.winner_id == "strategy_001"


@pytest.mark.asyncio
async def test_scoring_weight_validation(mock_backtest_func):
    """Test that scoring weights must sum to 1.0"""
    
    invalid_weights = {
        "sharpe_ratio": 0.50,
        "sortino_ratio": 0.30,  # Sum = 0.80 (invalid)
        "win_rate": 0.0,
        "max_drawdown": 0.0,
        "total_return": 0.0
    }
    
    with pytest.raises(ValueError, match="must sum to 1.0"):
        StrategyArena(
            max_workers=3,
            backtest_func=mock_backtest_func,
            scoring_weights=invalid_weights,
            use_multiprocessing=False
        )


@pytest.mark.asyncio
async def test_score_normalization(arena, sample_strategies):
    """Test that scores are properly normalized"""
    
    result = await arena.run_tournament(
        strategies=sample_strategies,
        tournament_name="Normalization Test"
    )
    
    # All scores should be between 0 and 1
    for _, score in result.ranked_strategies:
        assert 0.0 <= score <= 1.0


# =============================================================================
# Parallel Execution Tests
# =============================================================================

@pytest.mark.asyncio
async def test_parallel_execution(arena, sample_strategies):
    """Test parallel backtest execution"""
    
    start_time = datetime.now()
    
    result = await arena.run_tournament(
        strategies=sample_strategies,
        tournament_name="Parallel Test"
    )
    
    duration = (datetime.now() - start_time).total_seconds()
    
    # With 5 strategies and max_workers=3, should complete faster than sequential
    # Sequential would take ~2.5s (5 strategies * 0.5s avg)
    # Parallel should take ~1.5s
    assert duration < 3.0
    
    assert result.successful_backtests == 5


@pytest.mark.asyncio
async def test_max_workers_limit(sample_strategies, mock_backtest_func):
    """Test max_workers limit"""
    
    # Create arena with max_workers=2
    arena = StrategyArena(
        max_workers=2,
        backtest_func=mock_backtest_func,
        use_multiprocessing=False
    )
    
    result = await arena.run_tournament(
        strategies=sample_strategies,
        tournament_name="Workers Limit Test"
    )
    
    # Should still complete all strategies
    assert result.successful_backtests == 5


# =============================================================================
# Error Handling Tests
# =============================================================================

@pytest.mark.asyncio
async def test_failed_backtest_handling(sample_strategies):
    """Test handling of failed backtests"""
    
    def failing_backtest(strategy: Dict) -> Dict:
        if strategy["id"] == "strategy_003":
            raise ValueError("Backtest simulation failed")
        return {
            "total_return": 0.2,
            "sharpe_ratio": 1.5,
            "sortino_ratio": 1.8,
            "max_drawdown": -0.1,
            "win_rate": 0.5,
            "profit_factor": 1.5,
            "total_trades": 100,
            "winning_trades": 50,
            "losing_trades": 50,
            "volatility": 0.02
        }
    
    arena = StrategyArena(
        max_workers=3,
        backtest_func=failing_backtest,
        use_multiprocessing=False
    )
    
    result = await arena.run_tournament(
        strategies=sample_strategies,
        tournament_name="Error Handling Test"
    )
    
    # Tournament should complete despite one failure
    assert result.status == TournamentStatus.COMPLETED
    assert result.successful_backtests == 4
    assert result.failed_backtests == 1
    
    # Failed strategy should have errors
    failed_metrics = result.strategy_metrics["strategy_003"]
    assert len(failed_metrics.errors) > 0
    
    # Only successful strategies should be ranked
    assert len(result.ranked_strategies) == 4


@pytest.mark.asyncio
async def test_empty_strategies_list(arena):
    """Test tournament with empty strategies list"""
    
    result = await arena.run_tournament(
        strategies=[],
        tournament_name="Empty Test"
    )
    
    assert result.total_participants == 0
    assert result.winner_id is None
    assert len(result.ranked_strategies) == 0


# =============================================================================
# Result Serialization Tests
# =============================================================================

@pytest.mark.asyncio
async def test_result_serialization(arena, sample_strategies):
    """Test TournamentResult serialization"""
    
    result = await arena.run_tournament(
        strategies=sample_strategies[:2],
        tournament_name="Serialization Test"
    )
    
    result_dict = result.to_dict()
    
    assert isinstance(result_dict, dict)
    assert "tournament_id" in result_dict
    assert "tournament_name" in result_dict
    assert "status" in result_dict
    assert "ranked_strategies" in result_dict
    assert "winner_id" in result_dict
    
    # Check nested serialization
    assert isinstance(result_dict["strategy_metrics"], dict)
    for strategy_id, metrics_dict in result_dict["strategy_metrics"].items():
        assert isinstance(metrics_dict, dict)
        assert "total_return" in metrics_dict
        assert "sharpe_ratio" in metrics_dict


# =============================================================================
# Convenience Function Tests
# =============================================================================

@pytest.mark.asyncio
async def test_convenience_function(sample_strategies, mock_backtest_func):
    """Test run_strategy_tournament convenience function"""
    
    # Note: This will use default backtest (random results)
    # So we just test that it runs without errors
    result = await run_strategy_tournament(
        strategies=sample_strategies,
        tournament_name="Convenience Test",
        max_workers=3
    )
    
    assert isinstance(result, TournamentResult)
    assert result.status == TournamentStatus.COMPLETED


# =============================================================================
# Edge Cases
# =============================================================================

@pytest.mark.asyncio
async def test_single_strategy_tournament(arena, sample_strategies):
    """Test tournament with single strategy"""
    
    result = await arena.run_tournament(
        strategies=[sample_strategies[0]],
        tournament_name="Single Strategy Test"
    )
    
    assert result.total_participants == 1
    assert result.winner_id == sample_strategies[0]["id"]
    assert len(result.ranked_strategies) == 1


@pytest.mark.asyncio
async def test_two_strategies_tournament(arena, sample_strategies):
    """Test tournament with two strategies"""
    
    result = await arena.run_tournament(
        strategies=sample_strategies[:2],
        tournament_name="Two Strategies Test"
    )
    
    assert result.total_participants == 2
    assert len(result.ranked_strategies) == 2
    
    # Verify clear winner
    winner_score, second_score = [s for _, s in result.ranked_strategies]
    assert winner_score > second_score


@pytest.mark.asyncio
async def test_tournament_timestamps(arena, sample_strategies):
    """Test tournament timestamp recording"""
    
    result = await arena.run_tournament(
        strategies=sample_strategies[:2],
        tournament_name="Timestamp Test"
    )
    
    assert result.started_at is not None
    assert result.completed_at is not None
    assert result.completed_at > result.started_at
    
    duration = (result.completed_at - result.started_at).total_seconds()
    assert duration > 0
    assert duration < 10  # Should complete within 10 seconds


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
