"""
Manual test script для Strategy Tournament System
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services.strategy_arena import StrategyArena, run_strategy_tournament


# =============================================================================
# Test Strategies
# =============================================================================

SAMPLE_STRATEGIES = [
    {
        "id": "ema_crossover_v1",
        "name": "EMA Crossover (12/26)",
        "code": "# EMA strategy code"
    },
    {
        "id": "rsi_mean_reversion_v1",
        "name": "RSI Mean Reversion (30/70)",
        "code": "# RSI strategy code"
    },
    {
        "id": "bollinger_breakout_v1",
        "name": "Bollinger Bands Breakout",
        "code": "# BB strategy code"
    },
    {
        "id": "macd_trend_v1",
        "name": "MACD Trend Following",
        "code": "# MACD strategy code"
    },
    {
        "id": "volume_profile_v1",
        "name": "Volume Profile Strategy",
        "code": "# Volume strategy code"
    },
    {
        "id": "stochastic_v1",
        "name": "Stochastic Oscillator",
        "code": "# Stochastic code"
    },
    {
        "id": "ichimoku_cloud_v1",
        "name": "Ichimoku Cloud",
        "code": "# Ichimoku code"
    }
]


async def test_basic_tournament():
    """Test basic tournament with 5 strategies"""
    print("\n" + "=" * 80)
    print("TEST 1: Basic Tournament (5 strategies)")
    print("=" * 80)
    
    result = await run_strategy_tournament(
        strategies=SAMPLE_STRATEGIES[:5],
        tournament_name="Test Tournament #1",
        max_workers=3
    )
    
    print(f"\n✅ Tournament completed: {result.tournament_name}")
    print(f"Status: {result.status}")
    print(f"Duration: {(result.completed_at - result.started_at).total_seconds():.2f}s")
    print(f"Participants: {result.total_participants}")
    print(f"Successful: {result.successful_backtests}")
    print(f"Failed: {result.failed_backtests}")
    
    print(f"\n🏆 Winner: {result.winner_name} (ID: {result.winner_id})")
    
    print("\n📊 Top 5 Rankings:")
    for rank, (strategy_id, score) in enumerate(result.ranked_strategies[:5], 1):
        metrics = result.strategy_metrics[strategy_id]
        print(f"\n{rank}. {metrics.strategy_name}")
        print(f"   Score: {score:.4f}")
        print(f"   Return: {metrics.total_return:.2%}")
        print(f"   Sharpe: {metrics.sharpe_ratio:.2f}")
        print(f"   Sortino: {metrics.sortino_ratio:.2f}")
        print(f"   Win Rate: {metrics.win_rate:.2%}")
        print(f"   Max DD: {metrics.max_drawdown:.2%}")
        print(f"   Trades: {metrics.total_trades}")


async def test_large_tournament():
    """Test tournament with all 7 strategies"""
    print("\n" + "=" * 80)
    print("TEST 2: Large Tournament (7 strategies)")
    print("=" * 80)
    
    result = await run_strategy_tournament(
        strategies=SAMPLE_STRATEGIES,
        tournament_name="Test Tournament #2 (Large)",
        max_workers=5
    )
    
    print(f"\n✅ Tournament completed: {result.tournament_name}")
    print(f"Duration: {(result.completed_at - result.started_at).total_seconds():.2f}s")
    print(f"\n🏆 Winner: {result.winner_name}")
    
    print("\n📊 Full Rankings:")
    for rank, (strategy_id, score) in enumerate(result.ranked_strategies, 1):
        metrics = result.strategy_metrics[strategy_id]
        print(f"{rank}. {metrics.strategy_name:30s} | Score: {score:.4f} | "
              f"Return: {metrics.total_return:7.2%} | Sharpe: {metrics.sharpe_ratio:5.2f}")


async def test_custom_weights():
    """Test custom scoring weights"""
    print("\n" + "=" * 80)
    print("TEST 3: Custom Scoring Weights")
    print("=" * 80)
    
    # Emphasize Sharpe Ratio and Win Rate
    custom_weights = {
        "sharpe_ratio": 0.40,
        "sortino_ratio": 0.10,
        "win_rate": 0.30,
        "max_drawdown": 0.10,
        "total_return": 0.10
    }
    
    print("\nCustom Weights:")
    for metric, weight in custom_weights.items():
        print(f"  {metric}: {weight:.0%}")
    
    arena = StrategyArena(
        max_workers=3,
        scoring_weights=custom_weights
    )
    
    result = await arena.run_tournament(
        strategies=SAMPLE_STRATEGIES[:5],
        tournament_name="Custom Weights Test"
    )
    
    print(f"\n🏆 Winner with custom weights: {result.winner_name}")
    
    print("\n📊 Top 3:")
    for rank, (strategy_id, score) in enumerate(result.ranked_strategies[:3], 1):
        metrics = result.strategy_metrics[strategy_id]
        print(f"{rank}. {metrics.strategy_name:30s} | Score: {score:.4f}")


async def test_performance():
    """Test parallel execution performance"""
    print("\n" + "=" * 80)
    print("TEST 4: Performance Test")
    print("=" * 80)
    
    import time
    
    # Test different max_workers settings
    workers_configs = [1, 3, 5]
    
    for max_workers in workers_configs:
        print(f"\n--- Testing with max_workers={max_workers} ---")
        
        start_time = time.time()
        
        result = await run_strategy_tournament(
            strategies=SAMPLE_STRATEGIES,
            tournament_name=f"Performance Test (workers={max_workers})",
            max_workers=max_workers
        )
        
        duration = time.time() - start_time
        
        print(f"Duration: {duration:.2f}s")
        print(f"Avg per strategy: {duration / len(SAMPLE_STRATEGIES):.2f}s")
        print(f"Winner: {result.winner_name}")


async def test_result_serialization():
    """Test result serialization"""
    print("\n" + "=" * 80)
    print("TEST 5: Result Serialization")
    print("=" * 80)
    
    result = await run_strategy_tournament(
        strategies=SAMPLE_STRATEGIES[:3],
        tournament_name="Serialization Test",
        max_workers=2
    )
    
    # Serialize to dict
    result_dict = result.to_dict()
    
    print("\n📄 Serialized Result Keys:")
    for key in result_dict.keys():
        print(f"  - {key}")
    
    print(f"\n✅ Serialization successful")
    print(f"Result size: {len(str(result_dict))} characters")
    
    # Check nested structures
    print(f"\nStrategy metrics keys:")
    first_strategy = list(result_dict["strategy_metrics"].values())[0]
    for key in first_strategy.keys():
        print(f"  - {key}")


async def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("STRATEGY TOURNAMENT SYSTEM - MANUAL TEST SUITE")
    print("=" * 80)
    
    try:
        # Test 1: Basic tournament
        await test_basic_tournament()
        
        # Test 2: Large tournament
        await test_large_tournament()
        
        # Test 3: Custom weights
        await test_custom_weights()
        
        # Test 4: Performance
        await test_performance()
        
        # Test 5: Serialization
        await test_result_serialization()
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
