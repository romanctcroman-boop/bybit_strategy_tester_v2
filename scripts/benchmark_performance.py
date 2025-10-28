"""
Performance Benchmark Suite - ТЗ 9.2 Validation

Validates system performance against technical specification requirements:
- Backtest 10,000 bars: <5 seconds
- Grid optimization 100 combinations: <2 minutes
- Walk-Forward 10 periods: <10 minutes
- Monte Carlo 1,000 simulations: <30 seconds
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any

import pandas as pd
import numpy as np

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.backtest_engine import BacktestEngine
from backend.optimization import WalkForwardOptimizer, MonteCarloSimulator


def generate_large_dataset(n_bars: int = 10_000) -> pd.DataFrame:
    """Generate synthetic market data for performance testing."""
    np.random.seed(42)
    
    base_price = 50000.0
    
    # Generate realistic price movement using random walk with drift
    returns = np.random.normal(0.0001, 0.02, n_bars)
    prices = base_price * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame({
        'timestamp': pd.date_range('2023-01-01', periods=n_bars, freq='5min'),
        'open': prices,
        'high': prices * (1 + np.abs(np.random.normal(0, 0.01, n_bars))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.01, n_bars))),
        'close': prices * (1 + np.random.normal(0, 0.005, n_bars)),
        'volume': np.random.uniform(100, 1000, n_bars)
    })
    
    # Ensure high >= max(open, close) and low <= min(open, close)
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    return df


def simple_ma_cross_strategy(df: pd.DataFrame, fast_period: int = 10, slow_period: int = 20) -> pd.DataFrame:
    """Simple moving average crossover strategy - returns df with 'signal' column."""
    df = df.copy()
    df['fast_ma'] = df['close'].rolling(window=fast_period).mean()
    df['slow_ma'] = df['close'].rolling(window=slow_period).mean()
    
    # Generate signals: 1 = long, -1 = short, 0 = neutral
    df['signal'] = 0
    
    # Long when fast > slow
    long_mask = df['fast_ma'] > df['slow_ma']
    df.loc[long_mask, 'signal'] = 1
    
    # Short when fast < slow  
    short_mask = df['fast_ma'] < df['slow_ma']
    df.loc[short_mask, 'signal'] = -1
    
    return df


def benchmark_backtest_10k_bars() -> Dict[str, Any]:
    """
    ТЗ 9.2 Requirement: Backtest 10,000 bars in <5 seconds
    """
    print("\n" + "="*80)
    print("BENCHMARK 1: Backtest 10,000 bars")
    print("="*80)
    print("ТЗ Requirement: <5 seconds")
    
    # Generate data
    print("\nGenerating 10,000 bars dataset...")
    df = generate_large_dataset(n_bars=10_000)
    
    # Add signal column (simple MA cross)
    df = simple_ma_cross_strategy(df, fast_period=20, slow_period=50)
    
    # Strategy config
    strategy_config = {
        'take_profit_pct': 2.0,
        'stop_loss_pct': 1.0,
        'trailing_stop_pct': 0.5,
        'direction': 'both',
    }
    
    # Run backtest
    print("Running backtest...")
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.00075,
        leverage=1
    )
    
    start_time = time.time()
    results = engine.run(df, strategy_config)
    elapsed = time.time() - start_time
    
    # Results
    passed = elapsed < 5.0
    status = "✅ PASSED" if passed else "❌ FAILED"
    
    print(f"\n{status}")
    print(f"Execution Time: {elapsed:.3f} seconds")
    print(f"Requirement: <5.0 seconds")
    print(f"Total Trades: {results['total_trades']}")
    print(f"Final Capital: ${results['final_capital']:,.2f}")
    
    return {
        'benchmark': 'Backtest 10k bars',
        'requirement_seconds': 5.0,
        'actual_seconds': elapsed,
        'passed': passed,
        'bars': 10_000,
        'trades': results['total_trades']
    }


def benchmark_grid_100_combinations() -> Dict[str, Any]:
    """
    ТЗ 9.2 Requirement: Grid optimization 100 combinations in <2 minutes
    """
    print("\n" + "="*80)
    print("BENCHMARK 2: Grid Optimization 100 Combinations")
    print("="*80)
    print("ТЗ Requirement: <2 minutes (120 seconds)")
    
    # Generate data (use smaller dataset for grid)
    print("\nGenerating 5,000 bars dataset...")
    df = generate_large_dataset(n_bars=5_000)
    
    # Parameter grid: 10 x 10 = 100 combinations
    param_grid = {
        'fast_period': list(range(5, 15)),      # 10 values
        'slow_period': list(range(20, 30))      # 10 values
    }
    
    print(f"Parameter grid: {len(param_grid['fast_period'])} x {len(param_grid['slow_period'])} = 100 combinations")
    
    # Run grid search
    print("Running grid optimization...")
    start_time = time.time()
    
    best_result = None
    best_sharpe = -np.inf
    total_combinations = 0
    
    for fast in param_grid['fast_period']:
        for slow in param_grid['slow_period']:
            if fast >= slow:
                continue
            
            # Apply strategy
            df_strategy = simple_ma_cross_strategy(df, fast_period=fast, slow_period=slow)
            
            # Strategy config
            strategy_config = {
                'take_profit_pct': 2.0,
                'stop_loss_pct': 1.0,
                'trailing_stop_pct': 0.5,
                'direction': 'both',
            }
            
            # Run backtest
            engine = BacktestEngine(
                initial_capital=10000.0,
                commission=0.00075,
                leverage=1
            )
            results = engine.run(df_strategy, strategy_config)
            
            # Track best by Sharpe ratio
            if results['sharpe_ratio'] > best_sharpe:
                best_sharpe = results['sharpe_ratio']
                best_result = {
                    'fast_period': fast,
                    'slow_period': slow,
                    'sharpe_ratio': results['sharpe_ratio'],
                    'net_profit': results['metrics']['net_profit']
                }
            
            total_combinations += 1
    
    elapsed = time.time() - start_time
    
    # Results
    passed = elapsed < 120.0
    status = "✅ PASSED" if passed else "❌ FAILED"
    
    print(f"\n{status}")
    print(f"Execution Time: {elapsed:.3f} seconds ({elapsed/60:.2f} minutes)")
    print(f"Requirement: <120.0 seconds (2 minutes)")
    print(f"Combinations Tested: {total_combinations}")
    print(f"Best Parameters: Fast={best_result['fast_period']}, Slow={best_result['slow_period']}")
    print(f"Best Sharpe Ratio: {best_result['sharpe_ratio']:.4f}")
    
    return {
        'benchmark': 'Grid 100 combinations',
        'requirement_seconds': 120.0,
        'actual_seconds': elapsed,
        'passed': passed,
        'combinations': total_combinations,
        'best_sharpe': best_result['sharpe_ratio']
    }


def benchmark_walk_forward_10_periods() -> Dict[str, Any]:
    """
    ТЗ 9.2 Requirement: Walk-Forward 10 periods in <10 minutes
    """
    print("\n" + "="*80)
    print("BENCHMARK 3: Walk-Forward Optimization ~10 Periods")
    print("="*80)
    print("ТЗ Requirement: <10 minutes (600 seconds)")
    
    # Generate data
    print("\nGenerating 5,000 bars dataset...")
    df = generate_large_dataset(n_bars=5_000)
    
    # Add signal column (required by BacktestEngine)
    df['signal'] = 0
    
    # Walk-Forward parameters for ~10 periods
    # With 5000 bars: in=400, out=100, step=100 gives (5000-400-100)/100 = 45 periods
    # Let's use: in=800, out=200, step=400 gives (5000-800-200)/400 = 10 periods
    in_sample_size = 800
    out_sample_size = 200  
    step_size = 400
    
    expected_periods = (len(df) - in_sample_size - out_sample_size) // step_size + 1
    
    print(f"In-sample: {in_sample_size} bars")
    print(f"Out-sample: {out_sample_size} bars")
    print(f"Step size: {step_size} bars")
    print(f"Expected periods: ~{expected_periods}")
    
    # Parameter space (small for speed)
    param_space = {
        'take_profit_pct': [1.0, 2.0, 3.0],
        'stop_loss_pct': [0.5, 1.0, 1.5],
        'trailing_stop_pct': [0.3, 0.5],
    }
    
    total_combos = len(param_space['take_profit_pct']) * len(param_space['stop_loss_pct']) * len(param_space['trailing_stop_pct'])
    print(f"Parameter combinations: {total_combos}")
    print(f"Total backtests: ~{expected_periods * total_combos}")
    
    # Strategy config
    strategy_config = {
        'ema_fast': 20,
        'ema_slow': 50,
        'direction': 'both',
        'leverage': 1,
    }
    
    # Run Walk-Forward
    print("\nRunning Walk-Forward optimization...")
    optimizer = WalkForwardOptimizer(
        in_sample_size=in_sample_size,
        out_sample_size=out_sample_size,
        step_size=step_size,
        initial_capital=10000.0,
        commission=0.00075
    )
    
    start_time = time.time()
    
    try:
        results = optimizer.run(
            data=df,
            param_space=param_space,
            strategy_config=strategy_config,
            metric='sharpe_ratio'
        )
        elapsed = time.time() - start_time
        
        # Results
        passed = elapsed < 600.0
        status = "✅ PASSED" if passed else "❌ FAILED"
        
        actual_periods = len(results['walk_results'])
        
        print(f"\n{status}")
        print(f"Execution Time: {elapsed:.3f} seconds ({elapsed/60:.2f} minutes)")
        print(f"Requirement: <600.0 seconds (10 minutes)")
        print(f"Actual Periods: {actual_periods}")
        print(f"Avg Efficiency: {results['aggregated_metrics'].get('avg_efficiency', 0):.4f}")
        
        return {
            'benchmark': 'Walk-Forward ~10 periods',
            'requirement_seconds': 600.0,
            'actual_seconds': elapsed,
            'passed': passed,
            'periods': actual_periods,
            'efficiency': results['aggregated_metrics'].get('avg_efficiency', 0)
        }
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ FAILED")
        print(f"Execution Time: {elapsed:.3f} seconds")
        print(f"Error: {e}")
        
        return {
            'benchmark': 'Walk-Forward ~10 periods',
            'requirement_seconds': 600.0,
            'actual_seconds': elapsed,
            'passed': False,
            'error': str(e)
        }


def benchmark_monte_carlo_1000_sims() -> Dict[str, Any]:
    """
    ТЗ 9.2 Requirement: Monte Carlo 1,000 simulations in <30 seconds
    """
    print("\n" + "="*80)
    print("BENCHMARK 4: Monte Carlo 1,000 Simulations")
    print("="*80)
    print("ТЗ Requirement: <30 seconds")
    
    # Generate realistic trades (500 trades)
    print("\nGenerating 500 sample trades...")
    np.random.seed(42)
    
    trades = []
    for i in range(500):
        # Mix of winning and losing trades
        pnl = np.random.normal(50, 200)  # Mean profit $50, std $200
        pnl_pct = (pnl / 10000.0) * 100  # Percentage relative to capital
        
        # Create trade dict (not Trade object)
        trade = {
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'side': 'long' if i % 2 == 0 else 'short'
        }
        trades.append(trade)
    
    print(f"Generated {len(trades)} trades")
    
    # Run Monte Carlo
    print("Running 1,000 Monte Carlo simulations...")
    simulator = MonteCarloSimulator(n_simulations=1000, random_seed=42)
    
    start_time = time.time()
    results = simulator.run(trades)
    elapsed = time.time() - start_time
    
    # Results
    passed = elapsed < 30.0
    status = "✅ PASSED" if passed else "❌ FAILED"
    
    print(f"\n{status}")
    print(f"Execution Time: {elapsed:.3f} seconds")
    print(f"Requirement: <30.0 seconds")
    print(f"Simulations: {results.n_simulations}")
    print(f"Mean Return: {results.mean_return:.2f}%")
    print(f"Probability of Profit: {results.prob_profit:.1%}")
    print(f"Risk of Ruin: {results.prob_ruin:.1%}")
    
    return {
        'benchmark': 'Monte Carlo 1000 sims',
        'requirement_seconds': 30.0,
        'actual_seconds': elapsed,
        'passed': passed,
        'simulations': results.n_simulations,
        'prob_profit': results.prob_profit
    }


def main():
    """Run all performance benchmarks."""
    print("\n" + "="*80)
    print("PERFORMANCE BENCHMARK SUITE - ТЗ 9.2 Validation")
    print("="*80)
    print("Testing system performance against technical specification requirements")
    
    results = []
    
    # Run all benchmarks
    try:
        results.append(benchmark_backtest_10k_bars())
    except Exception as e:
        print(f"\n❌ Benchmark 1 FAILED with exception: {e}")
        results.append({
            'benchmark': 'Backtest 10k bars',
            'passed': False,
            'error': str(e)
        })
    
    try:
        results.append(benchmark_grid_100_combinations())
    except Exception as e:
        print(f"\n❌ Benchmark 2 FAILED with exception: {e}")
        results.append({
            'benchmark': 'Grid 100 combinations',
            'passed': False,
            'error': str(e)
        })
    
    try:
        results.append(benchmark_walk_forward_10_periods())
    except Exception as e:
        print(f"\n❌ Benchmark 3 FAILED with exception: {e}")
        results.append({
            'benchmark': 'Walk-Forward 10 periods',
            'passed': False,
            'error': str(e)
        })
    
    try:
        results.append(benchmark_monte_carlo_1000_sims())
    except Exception as e:
        print(f"\n❌ Benchmark 4 FAILED with exception: {e}")
        results.append({
            'benchmark': 'Monte Carlo 1000 sims',
            'passed': False,
            'error': str(e)
        })
    
    # Summary
    print("\n" + "="*80)
    print("BENCHMARK SUMMARY")
    print("="*80)
    
    total = len(results)
    passed = sum(1 for r in results if r.get('passed', False))
    
    for i, result in enumerate(results, 1):
        status = "✅ PASSED" if result.get('passed', False) else "❌ FAILED"
        benchmark = result['benchmark']
        
        if 'actual_seconds' in result:
            req = result['requirement_seconds']
            actual = result['actual_seconds']
            print(f"{i}. {benchmark}: {status}")
            print(f"   Time: {actual:.2f}s / {req:.0f}s required")
        else:
            print(f"{i}. {benchmark}: {status}")
            if 'error' in result:
                print(f"   Error: {result['error']}")
    
    print(f"\nOverall: {passed}/{total} benchmarks passed")
    
    if passed == total:
        print("\n🎉 All benchmarks PASSED! System meets ТЗ 9.2 performance requirements.")
    else:
        print(f"\n⚠️  {total - passed} benchmark(s) failed. Optimization needed.")
    
    return results


if __name__ == '__main__':
    main()
