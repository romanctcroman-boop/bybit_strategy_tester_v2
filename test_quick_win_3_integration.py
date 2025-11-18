"""
Quick Win #3 Integration Test

Tests all components together:
- Market Regime Detector
- Optuna Optimizer
- Tournament Orchestrator
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from backend.ml import (
    StrategyOptimizer,
    MarketRegimeDetector,
    MarketRegime,
    OptimizationConfig
)
from backend.services.tournament_orchestrator import (
    TournamentOrchestrator,
    TournamentConfig,
    StrategyEntry,
    TournamentStatus
)


def create_test_data(n=200):
    """Create test OHLCV data"""
    np.random.seed(42)
    
    # Trending market
    trend = np.linspace(0, 10, n)
    noise = np.random.randn(n) * 2
    close = 100 + trend + noise
    
    return pd.DataFrame({
        'open': close - np.random.rand(n) * 0.5,
        'high': close + np.random.rand(n) * 1.0,
        'low': close - np.random.rand(n) * 1.0,
        'close': close,
        'volume': np.random.randint(1000, 10000, n)
    })


async def test_market_regime_detector():
    """Test Market Regime Detector"""
    print("\n" + "="*60)
    print("TEST 1: Market Regime Detector")
    print("="*60)
    
    detector = MarketRegimeDetector()
    df = create_test_data()
    
    result = detector.detect_regime(df, return_details=True)
    
    print(f"✅ Regime: {result.regime.value}")
    print(f"✅ Confidence: {result.confidence:.2%}")
    print(f"✅ Trend Strength: {result.trend_strength:+.2f}")
    print(f"✅ Volatility: {result.volatility:.2f}%")
    print(f"✅ ADX: {result.adx_value:.2f}")
    print(f"✅ Wyckoff Phase: {result.wyckoff_phase or 'None'}")
    
    # Get regime statistics
    stats = detector.get_regime_statistics(df, window=100)
    print(f"\n📊 Regime Distribution:")
    for regime, pct in stats.items():
        if pct > 0:
            print(f"   {regime}: {pct:.1f}%")
    
    assert result.regime in MarketRegime
    assert 0 <= result.confidence <= 1
    assert -1 <= result.trend_strength <= 1
    
    print("\n✅ Market Regime Detector: PASSED")
    return True


async def test_optuna_optimizer():
    """Test Optuna Optimizer"""
    print("\n" + "="*60)
    print("TEST 2: Optuna Optimizer")
    print("="*60)
    
    optimizer = StrategyOptimizer(
        config=OptimizationConfig(n_trials=10)  # Quick test
    )
    
    df = create_test_data()
    
    param_space = {
        "period": {"type": "int", "low": 5, "high": 30},
        "threshold": {"type": "float", "low": 0.01, "high": 0.1}
    }
    
    print("Running optimization (10 trials)...")
    
    result = await optimizer.optimize_strategy(
        strategy_code="# Test strategy",
        data=df,
        param_space=param_space,
        objectives=["sharpe_ratio", "max_drawdown"],
        n_trials=10
    )
    
    print(f"\n✅ Best params: {result.best_params}")
    print(f"✅ Best values: {result.best_values}")
    print(f"✅ Trials completed: {result.n_trials}")
    print(f"✅ Optimization time: {result.optimization_time:.2f}s")
    
    assert result.best_params is not None
    assert result.n_trials == 10
    assert result.optimization_time > 0
    
    print("\n✅ Optuna Optimizer: PASSED")
    return True


async def test_tournament_orchestrator():
    """Test Tournament Orchestrator"""
    print("\n" + "="*60)
    print("TEST 3: Tournament Orchestrator")
    print("="*60)
    
    # Initialize components
    optimizer = StrategyOptimizer(
        config=OptimizationConfig(n_trials=5)
    )
    detector = MarketRegimeDetector()
    
    orchestrator = TournamentOrchestrator(
        optimizer=optimizer,
        regime_detector=detector
    )
    
    # Create test data
    df = create_test_data()
    
    # Define strategies
    strategies = [
        StrategyEntry(
            strategy_id="rsi_1",
            strategy_name="RSI Strategy",
            strategy_code="# RSI code",
            param_space={
                "rsi_period": {"type": "int", "low": 10, "high": 30}
            }
        ),
        StrategyEntry(
            strategy_id="ma_1",
            strategy_name="MA Crossover",
            strategy_code="# MA code",
            param_space={
                "fast": {"type": "int", "low": 5, "high": 20},
                "slow": {"type": "int", "low": 20, "high": 50}
            }
        ),
        StrategyEntry(
            strategy_id="bb_1",
            strategy_name="Bollinger Bands",
            strategy_code="# BB code",
            param_space={
                "period": {"type": "int", "low": 15, "high": 30},
                "std_dev": {"type": "float", "low": 1.5, "high": 3.0}
            }
        )
    ]
    
    # Run tournament
    print(f"Running tournament with {len(strategies)} strategies...")
    
    config = TournamentConfig(
        tournament_name="Quick Win #3 Test",
        enable_optimization=False,  # Disable for speed
        detect_market_regime=True,
        max_workers=2
    )
    
    result = await orchestrator.run_tournament(
        strategies=strategies,
        data=df,
        config=config
    )
    
    print(f"\n✅ Tournament: {result.tournament_name}")
    print(f"✅ Status: {result.status.value}")
    print(f"✅ Participants: {result.total_participants}")
    print(f"✅ Successful: {result.successful_backtests}")
    print(f"✅ Failed: {result.failed_backtests}")
    print(f"✅ Market Regime: {result.market_regime}")
    print(f"✅ Duration: {result.total_duration:.2f}s")
    
    if result.winner:
        print(f"\n🏆 Winner: {result.winner.strategy_name}")
        print(f"   Score: {result.winner.final_score:.4f}")
        print(f"   Rank: #{result.winner.rank}")
    
    print(f"\n📊 Rankings:")
    for i, s in enumerate(result.participants[:5], 1):
        print(f"   #{i}: {s.strategy_name} - Score: {s.final_score:.4f}")
    
    assert result.status == TournamentStatus.COMPLETED
    assert result.total_participants == len(strategies)
    assert result.winner is not None
    assert result.winner.rank == 1
    
    print("\n✅ Tournament Orchestrator: PASSED")
    return True


async def test_integration():
    """Test full integration"""
    print("\n" + "="*60)
    print("TEST 4: Full Integration")
    print("="*60)
    
    # Create components
    optimizer = StrategyOptimizer(
        config=OptimizationConfig(n_trials=5)
    )
    detector = MarketRegimeDetector()
    orchestrator = TournamentOrchestrator(
        optimizer=optimizer,
        regime_detector=detector
    )
    
    # Test data
    df = create_test_data()
    
    # Detect regime
    regime = detector.detect_regime(df)
    print(f"✅ Detected regime: {regime.regime.value}")
    
    # Optimize single strategy
    result = await optimizer.optimize_strategy(
        strategy_code="# Test",
        data=df,
        param_space={"p": {"type": "int", "low": 5, "high": 20}},
        n_trials=5
    )
    print(f"✅ Optimized params: {result.best_params}")
    
    # Run mini tournament
    strategies = [
        StrategyEntry(
            strategy_id=f"strat_{i}",
            strategy_name=f"Strategy {i}",
            strategy_code=f"# Code {i}",
            param_space={"p": {"type": "int", "low": 5, "high": 20}}
        )
        for i in range(3)
    ]
    
    tournament_result = await orchestrator.run_tournament(
        strategies=strategies,
        data=df,
        config=TournamentConfig(
            tournament_name="Integration Test",
            enable_optimization=False,
            detect_market_regime=True
        )
    )
    
    print(f"✅ Tournament completed: {tournament_result.winner.strategy_name} won!")
    
    print("\n✅ Full Integration: PASSED")
    return True


async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("🚀 QUICK WIN #3: INTEGRATION TESTS")
    print("="*60)
    
    tests = [
        ("Market Regime Detector", test_market_regime_detector),
        ("Optuna Optimizer", test_optuna_optimizer),
        ("Tournament Orchestrator", test_tournament_orchestrator),
        ("Full Integration", test_integration)
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            passed = await test_func()
            results.append((name, passed, None))
        except Exception as e:
            print(f"\n❌ {name}: FAILED")
            print(f"   Error: {e}")
            results.append((name, False, str(e)))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    
    for name, p, error in results:
        status = "✅ PASSED" if p else "❌ FAILED"
        print(f"{status}: {name}")
        if error:
            print(f"   Error: {error}")
    
    print(f"\n{'='*60}")
    print(f"TOTAL: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print(f"{'='*60}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Quick Win #3 is ready! 🚀")
        return 0
    else:
        print(f"\n⚠️ {total - passed} tests failed. Please review.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
