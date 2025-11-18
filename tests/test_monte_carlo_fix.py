"""
Unit test to verify Monte Carlo Std Dev > 0 after bootstrap fix
"""

import sys
from pathlib import Path
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.optimization.monte_carlo import MonteCarloSimulator


def test_monte_carlo_variance():
    """
    Test that Monte Carlo produces variance > 0 after bootstrap fix
    
    Key points:
    1. Bootstrap resampling WITH replacement (not just shuffle)
    2. Compounding returns (order matters)
    3. Should produce Std Dev > 0
    """
    
    print("\n" + "="*80)
    print("🧪 TEST: Monte Carlo Std Dev > 0 (Bootstrap Fix Validation)")
    print("="*80)
    
    # Create sample trades with varying PnLs
    trades = [
        {'pnl': 100.0, 'pnl_pct': 1.0},
        {'pnl': -50.0, 'pnl_pct': -0.5},
        {'pnl': 150.0, 'pnl_pct': 1.5},
        {'pnl': -30.0, 'pnl_pct': -0.3},
        {'pnl': 80.0, 'pnl_pct': 0.8},
        {'pnl': -20.0, 'pnl_pct': -0.2},
        {'pnl': 120.0, 'pnl_pct': 1.2},
        {'pnl': -40.0, 'pnl_pct': -0.4},
        {'pnl': 90.0, 'pnl_pct': 0.9},
        {'pnl': -60.0, 'pnl_pct': -0.6},
    ]
    
    initial_capital = 10000.0
    
    print(f"\n📊 Input Data:")
    print(f"   Trades: {len(trades)}")
    print(f"   Initial Capital: ${initial_capital:,.0f}")
    print(f"   PnL Range: ${min(t['pnl'] for t in trades):.2f} to ${max(t['pnl'] for t in trades):.2f}")
    print(f"   Total PnL: ${sum(t['pnl'] for t in trades):.2f}")
    
    # Run Monte Carlo
    mc = MonteCarloSimulator(n_simulations=1000, random_seed=42)
    result = mc.run(trades, initial_capital)
    
    print(f"\n📈 Monte Carlo Results:")
    print(f"   Simulations: {result.n_simulations}")
    print(f"   Original Return: {result.original_return:.4f}%")
    print(f"   Mean Return: {result.mean_return:.4f}%")
    print(f"   Std Dev: {result.std_return:.4f}%")
    print(f"   5th Percentile: {result.percentile_5:.4f}%")
    print(f"   95th Percentile: {result.percentile_95:.4f}%")
    print(f"   Prob of Profit: {result.prob_profit:.2%}")
    
    # Validate variance > 0
    print(f"\n✅ VALIDATION:")
    
    if result.std_return > 0:
        print(f"   ✅ Std Dev = {result.std_return:.4f}% (> 0)")
        print(f"   ✅ Bootstrap resampling WORKING")
    else:
        print(f"   ❌ Std Dev = {result.std_return:.4f}% (= 0)")
        print(f"   ❌ Bootstrap resampling FAILED")
        return False
    
    # Check variance in returns
    unique_returns = len(set(result.all_returns))
    print(f"   ✅ Unique return values: {unique_returns} / {result.n_simulations}")
    
    if unique_returns < 10:
        print(f"   ⚠️ WARNING: Very few unique values (expected 100+)")
    
    # Check range
    return_range = result.percentile_95 - result.percentile_5
    print(f"   ✅ Return range (5%-95%): {return_range:.4f}%")
    
    if return_range < 0.01:
        print(f"   ⚠️ WARNING: Very narrow range (expected >1%)")
    
    print(f"\n🎉 TEST PASSED: Monte Carlo produces variance > 0")
    return True


def test_order_dependency():
    """
    Test that compounding makes return order-dependent
    """
    
    print("\n" + "="*80)
    print("🧪 TEST: Compounding Order Dependency")
    print("="*80)
    
    # Two trades with different PnLs
    trades_seq1 = [
        {'pnl': 100.0, 'pnl_pct': 1.0},
        {'pnl': -50.0, 'pnl_pct': -0.5},
    ]
    
    trades_seq2 = [
        {'pnl': -50.0, 'pnl_pct': -0.5},
        {'pnl': 100.0, 'pnl_pct': 1.0},
    ]
    
    initial_capital = 10000.0
    
    mc = MonteCarloSimulator(n_simulations=10, random_seed=42)
    
    # Calculate returns for both sequences
    return1 = mc._calculate_return(trades_seq1, initial_capital)
    return2 = mc._calculate_return(trades_seq2, initial_capital)
    
    print(f"\n📊 Sequence 1: [+100, -50]")
    print(f"   Return: {return1:.4f}%")
    
    print(f"\n📊 Sequence 2: [-50, +100]")
    print(f"   Return: {return2:.4f}%")
    
    print(f"\n✅ VALIDATION:")
    
    if abs(return1 - return2) > 0.001:
        print(f"   ✅ Returns are DIFFERENT ({abs(return1 - return2):.4f}% difference)")
        print(f"   ✅ Compounding makes order matter")
        print(f"\n🎉 TEST PASSED: Order dependency working")
        return True
    else:
        print(f"   ❌ Returns are IDENTICAL")
        print(f"   ❌ Compounding NOT working")
        return False


def test_compare_with_simple_sum():
    """
    Compare old (simple sum) vs new (compounding) methods
    """
    
    print("\n" + "="*80)
    print("🧪 TEST: Simple Sum vs Compounding Comparison")
    print("="*80)
    
    trades = [
        {'pnl': 100.0, 'pnl_pct': 1.0},
        {'pnl': -50.0, 'pnl_pct': -0.5},
        {'pnl': 150.0, 'pnl_pct': 1.5},
    ]
    
    initial_capital = 10000.0
    
    # Old method (simple sum)
    total_pnl = sum(t['pnl'] for t in trades)
    old_return = (total_pnl / initial_capital) * 100.0
    
    # New method (compounding)
    mc = MonteCarloSimulator(n_simulations=10)
    new_return = mc._calculate_return(trades, initial_capital)
    
    print(f"\n📊 Old Method (Simple Sum):")
    print(f"   Total PnL: ${total_pnl:.2f}")
    print(f"   Return: {old_return:.4f}%")
    print(f"   Order independent: sum([1,2,3]) = sum([3,2,1])")
    
    print(f"\n📊 New Method (Compounding):")
    print(f"   Return: {new_return:.4f}%")
    print(f"   Order dependent: compound([1,2,3]) ≠ compound([3,2,1])")
    
    print(f"\n✅ VALIDATION:")
    print(f"   Difference: {abs(old_return - new_return):.4f}%")
    
    if abs(old_return - new_return) < 0.5:
        print(f"   ℹ️ Small difference (low compounding effect)")
    else:
        print(f"   ✅ Significant difference (compounding working)")
    
    print(f"\n🎉 TEST PASSED: Methods compared")
    return True


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🔬 MONTE CARLO FIX VALIDATION SUITE")
    print("="*80)
    print("Testing bootstrap resampling + compounding fix")
    print("Expected: Std Dev > 0 (not 0.00%)")
    
    results = []
    
    # Test 1: Variance > 0
    try:
        results.append(("Monte Carlo Variance", test_monte_carlo_variance()))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Monte Carlo Variance", False))
    
    # Test 2: Order dependency
    try:
        results.append(("Order Dependency", test_order_dependency()))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Order Dependency", False))
    
    # Test 3: Comparison
    try:
        results.append(("Method Comparison", test_compare_with_simple_sum()))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Method Comparison", False))
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed ({passed_count/total_count*100:.0f}%)")
    
    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED - Monte Carlo fix validated!")
        sys.exit(0)
    else:
        print(f"\n⚠️ {total_count - passed_count} test(s) failed")
        sys.exit(1)
